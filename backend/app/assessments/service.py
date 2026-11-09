"""Assessment lifecycle (PRD 9.4): configuration, validation, sessions, finalization, corrections.

Contract used by ``app.policy``:
    finalize_session(db, session, *, reason) — idempotent; "submitted" → completed, "expired" → expired.
    Closing happens immediately. The immutable report is computed once no evaluation of the session is
    still running (or after a grace period), so a fix submitted before the deadline is still counted.
    Does not commit.
"""
import copy
import hashlib
import logging
import random
import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app import scoring
from app.assessments import report as reports
from app.auth import utc
from app.events import audit, record_event
from app.models import (
    Assessment,
    AssessmentSession,
    ChallengeAttempt,
    CompetencyProfile,
    Problem,
    Submission,
    now,
)

log = logging.getLogger(__name__)
FINALIZE_GRACE_SECONDS = 300
TYPE_DEFAULTS = {
    "interview": {"max_sessions": 1, "candidate_report": "summary", "feedback": "delayed"},
}
SNAPSHOT_FIELDS = ("assessment_type", "duration_seconds", "configuration", "scoring_rubric", "assistance_policy")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "assessment")[:90]


def unique_slug(db, base: str) -> str:
    slug, index = base, 2
    while db.scalar(select(Assessment.id).where(Assessment.slug == slug)):
        slug, index = f"{base}-{index}", index + 1
    return slug


def get_assessment(db, key: str) -> Assessment | None:
    return db.get(Assessment, key) or db.scalar(select(Assessment).where(Assessment.slug == key))


def effective_configuration(assessment: Assessment) -> dict:
    """Stored configuration with type defaults filling absent or null keys (interviews allow one session)."""
    configuration = dict(assessment.configuration or {})
    for key, value in TYPE_DEFAULTS.get(assessment.assessment_type, {}).items():
        if configuration.get(key) is None:
            configuration[key] = value
    return configuration


def max_sessions(assessment: Assessment) -> int | None:
    return effective_configuration(assessment).get("max_sessions")


def weights_of(assessment: Assessment) -> dict:
    return dict((assessment.scoring_rubric or {}).get("weights") or scoring.ASSESSMENT_WEIGHTS)


def resolve_problems(db, slugs: list[str]) -> tuple[list[Problem], list[str]]:
    rows = {row.slug: row for row in db.scalars(select(Problem).where(Problem.slug.in_(slugs)))}
    missing = [slug for slug in slugs if slug not in rows]
    return [rows[slug] for slug in slugs if slug in rows], missing


def validation_errors(db, assessment: Assessment) -> list[str]:
    """Publication validation (PRD 9.4 "Validation")."""
    errors = []
    configuration = effective_configuration(assessment)
    slugs = configuration.get("problems") or []
    if not slugs:
        errors.append("Select at least one challenge.")
    problems, missing = resolve_problems(db, slugs)
    if missing:
        errors.append(f"Unknown challenges: {', '.join(missing)}.")
    languages = configuration.get("languages") or []
    for problem in problems:
        if problem.visibility not in {"public", "assessment"}:
            errors.append(f"{problem.slug} is not published for assessments ({problem.visibility}).")
        if languages and not set(languages) & set(problem.starters):
            errors.append(f"{problem.slug} does not offer an allowed language ({', '.join(languages)}).")
        if configuration.get("require_quality_approved") and problem.quality_status != "approved":
            errors.append(f"{problem.slug} has not passed the problem-quality gate ({problem.quality_status}).")
    weights = weights_of(assessment)
    if set(weights) - set(scoring.ASSESSMENT_WEIGHTS) or sum(float(value) for value in weights.values()) <= 0:
        errors.append("Scoring weights are invalid.")
    if not 300 <= (assessment.duration_seconds or 0) <= 4 * 3600:
        errors.append("Duration must be between 5 minutes and 4 hours.")
    if assessment.available_from and assessment.available_until and \
            utc(assessment.available_until) <= utc(assessment.available_from):
        errors.append("The availability window must end after it starts.")
    return errors


def snapshot(db, assessment: Assessment, problems: list[Problem]) -> dict:
    profile = db.get(CompetencyProfile, assessment.competency_profile_id) if assessment.competency_profile_id else None
    return {
        "assessment_id": assessment.id, "slug": assessment.slug, "title": assessment.title,
        "assessment_type": assessment.assessment_type, "version": assessment.version,
        "duration_seconds": assessment.duration_seconds,
        "configuration": copy.deepcopy(effective_configuration(assessment)),
        "scoring_rubric": {"weights": weights_of(assessment)},
        "assistance_policy": copy.deepcopy(assessment.assistance_policy or {"ai": "disabled", "hints": "disabled"}),
        "competency_profile": copy.deepcopy(profile.weights) if profile else None,
        "competency_profile_name": profile.name if profile else None,
        "organization_id": assessment.organization_id,
        "problems": [{"id": problem.id, "slug": problem.slug, "version": problem.version,
                      "content_hash": problem.content_hash} for problem in problems],
        "recovery_rule": reports.RECOVERY_RULE,
    }


def sessions_used(db, assessment: Assessment, user_id: str) -> int:
    return db.scalar(select(func.count()).select_from(AssessmentSession).where(
        AssessmentSession.assessment_id == assessment.id, AssessmentSession.user_id == user_id,
        AssessmentSession.status != "cancelled")) or 0


def active_session(db, assessment: Assessment, user_id: str) -> AssessmentSession | None:
    from app import policy
    rows = db.scalars(select(AssessmentSession).where(AssessmentSession.assessment_id == assessment.id,
                                                      AssessmentSession.user_id == user_id,
                                                      AssessmentSession.status == "active"))
    for row in rows:
        if not policy.expire_if_due(db, row):
            return row
    return None


def start_session(db, user, assessment: Assessment, invitation=None) -> AssessmentSession:
    """Create a session with an immutable configuration snapshot. Caller checks access and commits."""
    current = now()
    if assessment.available_from and utc(assessment.available_from) > current:
        raise HTTPException(409, "This assessment is not open yet.")
    if assessment.available_until and utc(assessment.available_until) <= current:
        raise HTTPException(409, "This assessment is closed.")
    limit = max_sessions(assessment)
    if limit is not None and sessions_used(db, assessment, user.id) >= int(limit):
        raise HTTPException(409, f"This assessment allows {limit} session(s) per candidate.")
    problems, missing = resolve_problems(db, effective_configuration(assessment).get("problems") or [])
    if missing or not problems:
        raise HTTPException(409, "This assessment is misconfigured. Please contact the organizer.")
    session = AssessmentSession(assessment_id=assessment.id, user_id=user.id, status="active", started_at=current,
                                expires_at=current + timedelta(seconds=assessment.duration_seconds),
                                invitation_id=invitation.id if invitation else None,
                                config_snapshot=snapshot(db, assessment, problems))
    db.add(session)
    db.flush()
    order = [problem.id for problem in problems]
    if session.config_snapshot["configuration"].get("randomize_order"):
        # Per-session deterministic order: reproducible from the stored session id.
        random.Random(int(hashlib.sha256(session.id.encode()).hexdigest(), 16)).shuffle(order)
    session.challenge_order = order
    if invitation is not None and invitation.status == "pending":
        invitation.status, invitation.accepted_at, invitation.accepted_by = "accepted", current, user.id
    record_event(db, "assessment.session_started", user_id=user.id, assessment_session_id=session.id,
                 assessment_id=assessment.id, assessment_version=assessment.version, challenge_order=order,
                 expires_at=session.expires_at.isoformat())
    return session


def session_attempts(db, session: AssessmentSession) -> dict[int, ChallengeAttempt]:
    rows = db.scalars(select(ChallengeAttempt).where(ChallengeAttempt.assessment_session_id == session.id,
                                                     ChallengeAttempt.user_id == session.user_id))
    return {row.problem_id: row for row in rows}


def pending_evaluations(db, session: AssessmentSession) -> int:
    return db.scalar(select(func.count()).select_from(Submission).where(
        Submission.assessment_session_id == session.id, Submission.status.in_(["queued", "running"]))) or 0


def close_session(db, session: AssessmentSession, *, reason: str) -> bool:
    """Stop accepting work. Conditional update so a concurrent submit and expiry cannot both apply."""
    if session.status != "active":
        return False
    status = "expired" if reason == "expired" else "completed"
    ended = utc(session.expires_at) if reason == "expired" else min(now(), utc(session.expires_at))
    claimed = db.execute(update(AssessmentSession).where(AssessmentSession.id == session.id,
                                                         AssessmentSession.status == "active")
                         .values(status=status, completed_at=ended)
                         .execution_options(synchronize_session="fetch"))
    if not claimed.rowcount:
        db.refresh(session)
        return False
    session.status, session.completed_at = status, ended
    record_event(db, "assessment.session_closed", user_id=session.user_id, assessment_session_id=session.id,
                 reason=reason, status=status)
    return True


def finalize_session(db, session: AssessmentSession, *, reason: str) -> None:
    if session.finalized_at is not None:
        return
    close_session(db, session, reason=reason)
    if session.status not in {"completed", "expired"} or session.finalized_at is not None:
        return
    pending = pending_evaluations(db, session)
    waited = (now() - utc(session.completed_at or now())).total_seconds()
    if pending and waited < FINALIZE_GRACE_SECONDS:
        return  # The scheduler (or the next report request) finalizes once evaluations finish.
    try:
        # A savepoint keeps a scoring failure from blocking the user: the session stays closed and the
        # scheduler retries finalization, instead of every policy check raising.
        with db.begin_nested():
            claimed = db.execute(update(AssessmentSession).where(AssessmentSession.id == session.id,
                                                                 AssessmentSession.finalized_at.is_(None))
                                 .values(finalized_at=now()).execution_options(synchronize_session="fetch"))
            if not claimed.rowcount:
                raise _AlreadyFinalized
            _store_report(db, session, reason=reason, pending=pending)
    except _AlreadyFinalized:
        db.refresh(session)
    except Exception:
        log.exception("Assessment finalization failed; it will be retried: %s", session.id)


class _AlreadyFinalized(Exception):
    pass


def _store_report(db, session: AssessmentSession, *, reason: str, pending: int) -> None:
    started = now()
    report = reports.build_report(db, session, session_attempts(db, session), unfinished=pending)
    session.report = report
    session.report_version = 1
    session.total_score = report["summary"]["total_score"]
    session.assistance_metadata = report["assistance"]
    configuration = (session.config_snapshot or {}).get("configuration") or {}
    released = configuration.get("feedback", "immediate") == "immediate"
    session.scoring_details = {
        "weights": report["weights"],
        "challenges": {str(row["problem_id"]): {"total": row["total"], "components": row["components"]}
                       for row in report["challenges"]},
        "finalization": {"reason": reason, "unfinished_evaluations": pending,
                         "latency_ms": round((now() - started).total_seconds() * 1000, 2),
                         "after_deadline_seconds": round(max(0.0, (now() - utc(session.expires_at)).total_seconds()), 1)},
        "released_at": now().isoformat() if released else None,
        "history": [{"report_version": 1, "total_score": session.total_score, "at": now().isoformat(),
                     "reason": "finalized"}],
    }
    record_event(db, "assessment.finalized", user_id=session.user_id, assessment_session_id=session.id,
                 reason=reason, total_score=session.total_score, unfinished_evaluations=pending)


def finalize_ready(db, session: AssessmentSession) -> bool:
    """Finalize a closed session whose evaluations have finished. Returns whether the report exists."""
    if session.finalized_at is None and session.status in {"completed", "expired"}:
        finalize_session(db, session, reason="expired" if session.status == "expired" else "submitted")
    return session.finalized_at is not None and session.report is not None


def is_released(session: AssessmentSession) -> bool:
    return bool((session.scoring_details or {}).get("released_at"))


def release_report(db, session: AssessmentSession, actor) -> None:
    details = copy.deepcopy(session.scoring_details or {})
    if details.get("released_at"):
        return
    details["released_at"] = now().isoformat()
    session.scoring_details = details
    audit(db, actor.id, "assessment.report_released", "assessment_session", session.id)
    record_event(db, "assessment.report_released", user_id=session.user_id, assessment_session_id=session.id,
                 actor_id=actor.id)


def apply_correction(db, session: AssessmentSession, actor, data) -> dict:
    """Auditable administrative correction (PRD 9.9): finalized results change only here."""
    if session.report is None:
        raise HTTPException(409, "Only finalized sessions can be corrected.")
    report = copy.deepcopy(session.report)
    before = session.total_score
    by_key = {}
    for row in report["challenges"]:
        by_key[row["slug"]] = row
        by_key[str(row["problem_id"])] = row
    for key, components in data.challenge_scores.items():
        row = by_key.get(key)
        if row is None:
            raise HTTPException(422, f"{key} is not a challenge in this session.")
        row["components"].update({name: float(value) for name, value in components.items()})
        row["total"] = scoring.weighted(row["components"], row["weights"], missing="zero") or 0.0
        row["corrected"] = True
    version = (session.report_version or 1) + 1
    correction = {"report_version": version, "actor_id": actor.id, "reason": data.reason,
                  "adjustments": {"challenge_scores": data.challenge_scores, "total_score": data.total_score},
                  "before_total": before, "at": now().isoformat()}
    corrections = report.get("corrections", []) + [correction]
    rebuilt = reports.assemble(db, session, report["challenges"], report["weights"],
                               corrections=corrections, report_version=version)
    # Keep the original evaluation context; only scores and derived sections change.
    rebuilt["summary"].update({key: report["summary"][key] for key in ("evaluated_at", "time_spent_seconds",
                                                                        "started_at", "ended_at", "status")})
    rebuilt["disclaimers"] = report["disclaimers"]
    if data.total_score is not None:
        rebuilt["summary"]["total_score"] = round(float(data.total_score), 2)
    correction["after_total"] = rebuilt["summary"]["total_score"]
    session.report = rebuilt
    session.report_version = version
    session.total_score = rebuilt["summary"]["total_score"]
    details = copy.deepcopy(session.scoring_details or {})
    details.setdefault("history", []).append({"report_version": version, "total_score": session.total_score,
                                               "at": correction["at"], "reason": data.reason,
                                               "actor_id": actor.id})
    details["challenges"] = {str(row["problem_id"]): {"total": row["total"], "components": row["components"]}
                             for row in rebuilt["challenges"]}
    session.scoring_details = details
    audit(db, actor.id, "assessment.correction", "assessment_session", session.id, reason=data.reason,
          adjustments=correction["adjustments"], before_total=before, after_total=session.total_score,
          report_version=version)
    record_event(db, "assessment.corrected", user_id=session.user_id, assessment_session_id=session.id,
                 actor_id=actor.id, report_version=version)
    return rebuilt
