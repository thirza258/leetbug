"""Assessment API (PRD 9, 11.5). Every rule is enforced here or in ``app.policy`` — never in the browser."""
import hashlib
import secrets
from collections import Counter
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import policy
from app.assessments import access, service
from app.assessments import report as reports
from app.assessments.schemas import (
    AssessmentConfiguration,
    AssessmentCreate,
    AssessmentUpdate,
    CorrectionCreate,
    InvitationAccept,
    InvitationCreate,
)
from app.attempts import latest_diagnosis
from app.auth import current_user, optional_user, utc
from app.db import get_db
from app.events import audit, record_event
from app.limits import rate_limit
from app.models import (
    Assessment,
    AssessmentInvitation,
    AssessmentSession,
    CompetencyProfile,
    Event,
    FixExplanation,
    Submission,
    User,
    now,
)

router = APIRouter(prefix="/api", tags=["assessments"])
CLOSED = {"completed", "expired", "cancelled"}
POLICY_TEXT = {
    "ai": {"disabled": "AI assistance is disabled.",
           "guided": "Only conceptual AI guidance is available; AI-written patches are disabled.",
           "enabled": "AI assistance is allowed and recorded in the report."},
    "hints": {"disabled": "Hints are disabled.", "restricted": "Only the first, conceptual hint is available.",
              "enabled": "Progressive hints are allowed and recorded in the report."},
}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def iso(value):
    return utc(value).isoformat() if value is not None else None


# ── views ─────────────────────────────────────────────────────────────────────────────────


def session_brief(session: AssessmentSession | None) -> dict | None:
    if session is None:
        return None
    return {"id": session.id, "status": session.status, "started_at": iso(session.started_at),
            "expires_at": iso(session.expires_at), "completed_at": iso(session.completed_at),
            "finalized_at": iso(session.finalized_at),
            "total_score": session.total_score if service.is_released(session) else None,
            "released": service.is_released(session)}


def assessment_card(db, assessment: Assessment, latest: AssessmentSession | None = None) -> dict:
    configuration = service.effective_configuration(assessment)
    problems, _ = service.resolve_problems(db, configuration.get("problems") or [])
    mix = Counter(problem.difficulty for problem in problems)
    offered = sorted({language for problem in problems for language in problem.starters})
    assistance = assessment.assistance_policy or {"ai": "disabled", "hints": "disabled"}
    return {
        "id": assessment.id, "slug": assessment.slug, "title": assessment.title,
        "description": assessment.description, "assessment_type": assessment.assessment_type,
        "duration_seconds": assessment.duration_seconds,
        "challenge_count": len(configuration.get("problems") or []),
        "difficulty_mix": {level: mix.get(level, 0) for level in ("easy", "medium", "hard")},
        "languages": configuration.get("languages") or offered,
        "assistance_policy": assistance,
        "diagnosis_required": bool(configuration.get("diagnosis_required")),
        "explanation_required": bool(configuration.get("explanation_required")),
        "max_attempts": configuration.get("max_attempts"), "max_sessions": service.max_sessions(assessment),
        "feedback": configuration.get("feedback", "immediate"),
        "candidate_report": configuration.get("candidate_report", "full"),
        "visibility": assessment.visibility, "status": assessment.status,
        "organization_id": assessment.organization_id, "version": assessment.version,
        "available_from": iso(assessment.available_from), "available_until": iso(assessment.available_until),
        "my_session": session_brief(latest),
    }


def rules(assessment: Assessment) -> list[str]:
    configuration = service.effective_configuration(assessment)
    assistance = assessment.assistance_policy or {}
    minutes = round(assessment.duration_seconds / 60)
    items = [f"You have {minutes} minutes from the moment you start. The timer runs on the server and keeps "
             "running if you close the page.",
             reports.RECOVERY_RULE,
             POLICY_TEXT["ai"].get(assistance.get("ai", "disabled"), ""),
             POLICY_TEXT["hints"].get(assistance.get("hints", "disabled"), ""),
             "Reference solutions stay locked during the assessment."]
    if configuration.get("diagnosis_required"):
        items.append("Submit a root-cause diagnosis before submitting a fix for each challenge.")
    if configuration.get("explanation_required"):
        items.append("Explain each accepted fix; a missing explanation scores zero for that dimension.")
    if configuration.get("max_attempts"):
        items.append(f"Each challenge allows {configuration['max_attempts']} full submissions. Public test runs "
                     "are unlimited.")
    if configuration.get("languages"):
        items.append(f"Allowed languages: {', '.join(configuration['languages'])}.")
    if configuration.get("feedback") == "delayed":
        items.append("Results are released after review.")
    return [item for item in items if item]


def admin_view(db, assessment: Assessment) -> dict:
    sessions = list(db.scalars(select(AssessmentSession.status).where(
        AssessmentSession.assessment_id == assessment.id)))
    invitations = list(db.scalars(select(AssessmentInvitation.status).where(
        AssessmentInvitation.assessment_id == assessment.id)))
    return {**assessment_card(db, assessment), "configuration": service.effective_configuration(assessment),
            "scoring_rubric": {"weights": service.weights_of(assessment)},
            "competency_profile_id": assessment.competency_profile_id, "created_by": assessment.created_by,
            "created_at": iso(assessment.created_at), "updated_at": iso(assessment.updated_at),
            "session_counts": dict(Counter(sessions)), "invitation_counts": dict(Counter(invitations)),
            "validation_errors": service.validation_errors(db, assessment)}


def session_payload(db, session: AssessmentSession, user, viewer: str) -> dict:
    from app.api import problem_payload  # imported late: app.api is the core router module
    snapshot = session.config_snapshot or {}
    configuration = snapshot.get("configuration") or {}
    languages = configuration.get("languages") or []
    problems = reports.session_problems(db, session)
    attempts = service.session_attempts(db, session)
    active = session.status == "active"
    submissions: dict[int, list[Submission]] = {}
    for row in db.scalars(select(Submission).where(Submission.assessment_session_id == session.id)
                          .order_by(Submission.created_at.desc())):
        submissions.setdefault(row.problem_id, []).append(row)
    explained = set(db.scalars(select(FixExplanation.attempt_id).where(
        FixExplanation.attempt_id.in_([attempt.id for attempt in attempts.values()])))) if attempts else set()
    challenges = []
    for position, problem in enumerate(problems, 1):
        attempt = attempts.get(problem.id)
        rows = submissions.get(problem.id, [])
        solved = any(row.kind == "submit" and row.status == "passed" for row in rows)
        entry = {
            "position": position, "problem_id": problem.id, "slug": problem.slug, "title": problem.title,
            "difficulty": problem.difficulty, "category": problem.category,
            "status": "solved" if solved else "in_progress" if attempt or rows else "not_started",
            "submissions_used": sum(row.kind == "submit" for row in rows),
            "max_attempts": configuration.get("max_attempts"),
            "diagnosis_submitted": bool(attempt and latest_diagnosis(db, attempt.id)),
            "explanation_submitted": bool(attempt and attempt.id in explained),
            "submissions": [{"id": row.id, "kind": row.kind, "status": row.status, "language": row.language,
                             "mode": row.mode, "created_at": iso(row.created_at)} for row in rows[:10]],
        }
        if active and viewer == "candidate":
            payload = problem_payload(db, problem, user, include_progress=False)
            if languages:
                allowed = [language for language in payload["languages"] if language in languages]
                payload = {**payload, "languages": allowed,
                           "starters": {key: value for key, value in payload["starters"].items() if key in allowed}}
            entry["problem"] = payload
        challenges.append(entry)
    candidate = db.get(User, session.user_id)
    return {
        "id": session.id, "status": session.status, "viewer": viewer,
        "started_at": iso(session.started_at), "expires_at": iso(session.expires_at),
        "completed_at": iso(session.completed_at), "finalized_at": iso(session.finalized_at),
        "server_time": now().isoformat(),
        "remaining_seconds": max(0, int((utc(session.expires_at) - now()).total_seconds())) if active else 0,
        "candidate": {"id": session.user_id, "username": candidate.username if candidate else None},
        "assessment": {
            "id": snapshot.get("assessment_id"), "slug": snapshot.get("slug"), "title": snapshot.get("title"),
            "assessment_type": snapshot.get("assessment_type"), "version": snapshot.get("version"),
            "duration_seconds": snapshot.get("duration_seconds"),
            "assistance_policy": snapshot.get("assistance_policy") or {},
            "configuration": {key: configuration.get(key) for key in (
                "languages", "diagnosis_required", "explanation_required", "max_attempts", "feedback",
                "candidate_report")},
        },
        "challenges": challenges,
        "pending_evaluations": service.pending_evaluations(db, session),
        "report_ready": session.report is not None,
        "report_released": service.is_released(session),
        "recovery_rule": reports.RECOVERY_RULE,
    }


def report_for(session: AssessmentSession, viewer: str) -> dict:
    report = session.report
    released = service.is_released(session)
    if viewer == "reviewer":
        return {**reports.full_view(report), "released": released, "viewer": viewer}
    if not released:
        summary = report["summary"]
        return {"level": "pending_review", "released": False, "viewer": viewer,
                "summary": {key: summary[key] for key in ("assessment", "status", "challenges_total", "ended_at")},
                "disclaimers": ["Your results will be available after the organizer reviews them."]}
    configuration = (session.config_snapshot or {}).get("configuration") or {}
    view = reports.full_view if configuration.get("candidate_report", "full") == "full" else reports.summary_view
    return {**view(report), "released": True, "viewer": viewer}


# ── loading and authorization helpers ──────────────────────────────────────────────────────


def load_assessment(db, key: str, user) -> Assessment:
    assessment = service.get_assessment(db, key)
    if assessment is None or not access.can_view(db, user, assessment):
        raise HTTPException(404, "Assessment not found.")
    return assessment


def managed_assessment(db, assessment_id: str, user) -> Assessment:
    assessment = service.get_assessment(db, assessment_id)
    if assessment is None or not access.can_review(db, user, assessment):
        raise HTTPException(404, "Assessment not found.")
    if not access.can_manage(db, user, assessment):
        raise HTTPException(403, "You cannot manage this assessment.")
    return assessment


def reviewed_assessment(db, assessment_id: str, user) -> Assessment:
    assessment = service.get_assessment(db, assessment_id)
    if assessment is None or not access.can_review(db, user, assessment):
        raise HTTPException(404, "Assessment not found.")
    return assessment


def load_session(db, session_id: str, user) -> tuple[AssessmentSession, Assessment, str]:
    session = db.get(AssessmentSession, session_id)
    assessment = db.get(Assessment, session.assessment_id) if session else None
    viewer = access.session_viewer(db, user, session, assessment) if session and assessment else None
    if viewer is None:
        raise HTTPException(404, "Assessment session not found.")
    return session, assessment, viewer


def validate_profile(db, profile_id: str | None, organization_id: str | None) -> None:
    if not profile_id:
        return
    profile = db.get(CompetencyProfile, profile_id)
    if profile is None or profile.organization_id not in (None, organization_id):
        raise HTTPException(422, "That competency profile is not available for this assessment.")


def configuration_from(data: AssessmentConfiguration, assessment_type: str) -> dict:
    """Explicit fields win; type defaults (e.g. interviews share a summary after review) fill the rest."""
    explicit = data.model_dump(exclude_unset=True)
    configuration = data.model_dump()
    for key, value in service.TYPE_DEFAULTS.get(assessment_type, {}).items():
        if key not in explicit:
            configuration[key] = value
    return configuration


# ── candidate endpoints ───────────────────────────────────────────────────────────────────


@router.get("/assessments")
def list_assessments(user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    latest: dict[str, AssessmentSession] = {}
    if user:
        for row in db.scalars(select(AssessmentSession).where(AssessmentSession.user_id == user.id)
                              .order_by(AssessmentSession.started_at)):
            latest[row.assessment_id] = row
        for row in latest.values():
            policy.expire_if_due(db, row)
    rows = db.scalars(select(Assessment).where(Assessment.status == "published")
                      .order_by(Assessment.created_at, Assessment.title))
    items = [assessment_card(db, row, latest.get(row.id)) for row in rows if access.can_view(db, user, row)]
    return {"items": items, "total": len(items)}


@router.get("/assessments/{key}")
def assessment_detail(key: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    assessment = load_assessment(db, key, user)
    active = service.active_session(db, assessment, user.id) if user else None
    latest = active or (db.scalar(select(AssessmentSession).where(
        AssessmentSession.assessment_id == assessment.id, AssessmentSession.user_id == user.id)
        .order_by(AssessmentSession.started_at.desc()).limit(1)) if user else None)
    blocker = access.start_denial(db, user, assessment)
    used = service.sessions_used(db, assessment, user.id) if user else 0
    limit = service.max_sessions(assessment)
    if blocker is None and active is None:
        current = now()
        if assessment.available_from and utc(assessment.available_from) > current:
            blocker = "This assessment is not open yet."
        elif assessment.available_until and utc(assessment.available_until) <= current:
            blocker = "This assessment is closed."
        elif limit is not None and used >= int(limit):
            blocker = f"You have used all {limit} session(s) for this assessment."
    return {**assessment_card(db, assessment, latest), "rules": rules(assessment),
            "recovery_rule": reports.RECOVERY_RULE, "sessions_used": used,
            "active_session_id": active.id if active else None,
            "can_start": blocker is None, "start_blocker": blocker}


@router.post("/assessments/{key}/sessions", status_code=201)
def start_assessment(key: str, response: Response, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    rate_limit(f"assessment-start:{user.id}", 10)
    assessment = load_assessment(db, key, user)
    denial = access.start_denial(db, user, assessment)
    if denial:
        raise HTTPException(403 if assessment.status == "published" else 409, denial)
    # Serialize starts per account so two tabs cannot open two sessions.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    existing = service.active_session(db, assessment, user.id)
    if existing is not None:
        response.status_code = 200
        return session_payload(db, existing, user, "candidate")
    session = service.start_session(db, user, assessment, access.invitation_for(db, user, assessment))
    db.commit()
    return session_payload(db, session, user, "candidate")


@router.get("/me/assessment-sessions")
def my_sessions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(AssessmentSession).where(AssessmentSession.user_id == user.id)
                           .order_by(AssessmentSession.started_at.desc()).limit(100)))
    for row in rows:
        policy.expire_if_due(db, row)
    items = []
    for row in rows:
        snapshot = row.config_snapshot or {}
        items.append({**session_brief(row), "assessment": {
            "id": snapshot.get("assessment_id"), "slug": snapshot.get("slug"), "title": snapshot.get("title"),
            "assessment_type": snapshot.get("assessment_type")}, "challenge_count": len(row.challenge_order or [])})
    return {"items": items, "total": len(items)}


@router.get("/assessment-sessions/{session_id}")
def get_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session, _, viewer = load_session(db, session_id, user)
    policy.expire_if_due(db, session)
    if session.status in CLOSED and session.finalized_at is None:
        service.finalize_ready(db, session)
        db.commit()
    return session_payload(db, session, user, viewer)


@router.post("/assessment-sessions/{session_id}/submit")
def finish_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(f"assessment-finish:{user.id}", 10)
    session, _, viewer = load_session(db, session_id, user)
    if viewer != "candidate":
        raise HTTPException(403, "Only the candidate can finish this assessment.")
    if policy.expire_if_due(db, session) or session.status != "active":
        raise HTTPException(409, "This assessment session has already ended.")
    service.finalize_session(db, session, reason="submitted")
    db.commit()
    return session_payload(db, session, user, viewer)


@router.get("/assessment-sessions/{session_id}/report")
def get_report(session_id: str, response: Response, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    session, _, viewer = load_session(db, session_id, user)
    policy.expire_if_due(db, session)
    if session.status == "active":
        raise HTTPException(409, "The report is available after the session ends.")
    ready = service.finalize_ready(db, session)
    db.commit()
    if not ready:
        response.status_code = 202
        return {"level": "finalizing", "status": session.status,
                "pending_evaluations": service.pending_evaluations(db, session)}
    return report_for(session, viewer)


@router.get("/assessment-sessions/{session_id}/report/export")
def export_report(session_id: str, format: Literal["json", "csv", "md"] = "json",
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    session, _, viewer = load_session(db, session_id, user)
    if session.report is None:
        raise HTTPException(409, "The report is not finalized yet.")
    view = report_for(session, viewer)
    if view["level"] == "pending_review":
        raise HTTPException(403, "This report has not been released yet.")
    body, media_type = reports.export(view, format)
    slug = (session.config_snapshot or {}).get("slug") or "assessment"
    record_event(db, "assessment.report_exported", user_id=user.id, assessment_session_id=session.id,
                 format=format, viewer=viewer)
    db.commit()
    return Response(content=body, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{slug}-{session.id[:8]}-report.{format}"'})


@router.post("/assessment-invitations/accept")
def accept_invitation(data: InvitationAccept, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(f"assessment-invitation:{user.id}", 10)
    row = db.scalar(select(AssessmentInvitation).where(AssessmentInvitation.token_hash == hash_token(data.token)))
    if row is None or row.status == "revoked":
        raise HTTPException(404, "This invitation is not valid.")
    if row.email != user.email.lower():
        raise HTTPException(403, "This invitation was sent to a different email address. Sign in with that address.")
    if row.status == "accepted" and row.accepted_by not in (None, user.id):
        raise HTTPException(409, "This invitation has already been used.")
    if row.status == "pending" and row.expires_at is not None and utc(row.expires_at) <= now():
        row.status = "expired"
        db.commit()
    if row.status == "expired":
        raise HTTPException(410, "This invitation has expired. Ask the organizer for a new one.")
    if row.status == "pending":
        row.status, row.accepted_at, row.accepted_by = "accepted", now(), user.id
        record_event(db, "assessment.invitation_accepted", user_id=user.id, invitation_id=row.id,
                     assessment_id=row.assessment_id)
        db.commit()
    assessment = db.get(Assessment, row.assessment_id)
    return {"assessment": assessment_card(db, assessment),
            "invitation": {"id": row.id, "status": row.status, "email": row.email}}


# ── administration ────────────────────────────────────────────────────────────────────────


@router.get("/admin/assessments")
def admin_list(organization_id: str | None = None, status_filter: str = Query("", alias="status"),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Assessment)
    if organization_id:
        if not access.can_create(db, user, organization_id):
            raise HTTPException(403, "You cannot manage this organization's assessments.")
        query = query.where(Assessment.organization_id == organization_id)
    elif not policy.is_admin(user):
        raise HTTPException(403, "Admin access required.")
    if status_filter:
        query = query.where(Assessment.status == status_filter)
    rows = db.scalars(query.order_by(Assessment.created_at.desc(), Assessment.title))
    items = [admin_view(db, row) for row in rows]
    return {"items": items, "total": len(items)}


@router.post("/admin/assessments", status_code=201)
def admin_create(data: AssessmentCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not access.can_create(db, user, data.organization_id):
        raise HTTPException(403, "You cannot create assessments here.")
    visibility_problem = access.visibility_error(data.organization_id, data.visibility)
    if visibility_problem:
        raise HTTPException(422, visibility_problem)
    validate_profile(db, data.competency_profile_id, data.organization_id)
    if data.slug and db.scalar(select(Assessment.id).where(Assessment.slug == data.slug)):
        raise HTTPException(409, "That assessment slug is already in use.")
    assessment = Assessment(
        slug=data.slug or service.unique_slug(db, service.slugify(data.title)), title=data.title,
        description=data.description, assessment_type=data.assessment_type, duration_seconds=data.duration_seconds,
        configuration=configuration_from(data.configuration, data.assessment_type),
        scoring_rubric=data.scoring_rubric.model_dump(), assistance_policy=data.assistance_policy.model_dump(),
        visibility=data.visibility, status="draft", organization_id=data.organization_id,
        competency_profile_id=data.competency_profile_id, available_from=data.available_from,
        available_until=data.available_until, created_by=user.id)
    db.add(assessment)
    db.flush()
    audit(db, user.id, "assessment.created", "assessment", assessment.id, slug=assessment.slug,
          organization_id=assessment.organization_id)
    db.commit()
    return admin_view(db, assessment)


@router.get("/admin/assessments/{assessment_id}")
def admin_get(assessment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return admin_view(db, reviewed_assessment(db, assessment_id, user))


@router.patch("/admin/assessments/{assessment_id}")
def admin_update(assessment_id: str, data: AssessmentUpdate, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    assessment = managed_assessment(db, assessment_id, user)
    if assessment.status == "archived":
        raise HTTPException(409, "Archived assessments cannot be edited.")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("visibility"):
        visibility_problem = access.visibility_error(assessment.organization_id, changes["visibility"])
        if visibility_problem:
            raise HTTPException(422, visibility_problem)
    if "competency_profile_id" in changes:
        validate_profile(db, data.competency_profile_id, assessment.organization_id)
    for key, value in changes.items():
        if key == "configuration" and data.configuration is not None:
            # Fields sent replace stored ones; omitted fields keep their stored values.
            merged = {**(assessment.configuration or {}), **data.configuration.model_dump(exclude_unset=True)}
            value = AssessmentConfiguration(**merged).model_dump()
        elif key in {"scoring_rubric", "assistance_policy"} and value is not None:
            value = getattr(data, key).model_dump()
        elif value is None and key in {"title", "assessment_type", "duration_seconds", "configuration",
                                       "scoring_rubric", "assistance_policy", "visibility"}:
            continue
        setattr(assessment, key, value)
    if assessment.available_from and assessment.available_until and \
            utc(assessment.available_until) <= utc(assessment.available_from):
        db.rollback()
        raise HTTPException(422, "The availability window must end after it starts.")
    if assessment.status == "published":
        errors = service.validation_errors(db, assessment)
        if errors:
            db.rollback()
            raise HTTPException(422, "Cannot update a published assessment: " + " ".join(errors))
        # Running sessions keep their snapshot; new sessions use the new version.
        assessment.version = (assessment.version or 1) + 1
    audit(db, user.id, "assessment.updated", "assessment", assessment.id, fields=sorted(changes),
          version=assessment.version)
    db.commit()
    return admin_view(db, assessment)


@router.post("/admin/assessments/{assessment_id}/publish")
def admin_publish(assessment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    assessment = managed_assessment(db, assessment_id, user)
    if assessment.status == "archived":
        raise HTTPException(409, "Archived assessments cannot be published again.")
    errors = service.validation_errors(db, assessment)
    if errors:
        raise HTTPException(422, "Cannot publish: " + " ".join(errors))
    if assessment.status != "published":
        assessment.status = "published"
        audit(db, user.id, "assessment.published", "assessment", assessment.id, version=assessment.version)
        db.commit()
    return admin_view(db, assessment)


@router.post("/admin/assessments/{assessment_id}/archive")
def admin_archive(assessment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    assessment = managed_assessment(db, assessment_id, user)
    if assessment.status != "archived":
        assessment.status = "archived"
        audit(db, user.id, "assessment.archived", "assessment", assessment.id)
        db.commit()
    return admin_view(db, assessment)


@router.get("/admin/assessments/{assessment_id}/sessions")
def admin_sessions(assessment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    assessment = reviewed_assessment(db, assessment_id, user)
    rows = list(db.execute(select(AssessmentSession, User).join(User, AssessmentSession.user_id == User.id)
                           .where(AssessmentSession.assessment_id == assessment.id)
                           .order_by(AssessmentSession.started_at.desc())))
    for session, _ in rows:
        policy.expire_if_due(db, session)
    items = [{**session_brief(session), "total_score": session.total_score, "report_version": session.report_version,
              "candidate": {"id": candidate.id, "username": candidate.username, "email": candidate.email},
              "assessment_version": (session.config_snapshot or {}).get("version")}
             for session, candidate in rows]
    return {"items": items, "total": len(items)}


@router.post("/admin/assessments/{assessment_id}/invitations", status_code=201)
def admin_invite(assessment_id: str, data: InvitationCreate, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    assessment = managed_assessment(db, assessment_id, user)
    if assessment.status == "archived":
        raise HTTPException(409, "Archived assessments cannot send invitations.")
    rate_limit(f"assessment-invite:{user.id}", 20)
    results = []
    for email in dict.fromkeys(str(value).lower() for value in data.emails):
        for previous in db.scalars(select(AssessmentInvitation).where(
                AssessmentInvitation.assessment_id == assessment.id, AssessmentInvitation.email == email,
                AssessmentInvitation.status == "pending")):
            previous.status = "revoked"
        token = secrets.token_urlsafe(32)
        row = AssessmentInvitation(assessment_id=assessment.id, email=email, token_hash=hash_token(token),
                                   invited_by=user.id, expires_at=now() + timedelta(days=data.expires_in_days))
        db.add(row)
        db.flush()
        # The token is returned once; only its hash is stored.
        results.append({"id": row.id, "email": email, "token": token, "path": f"/assessment-invitations/{token}",
                        "expires_at": iso(row.expires_at)})
    audit(db, user.id, "assessment.invitations_created", "assessment", assessment.id,
          emails=[row["email"] for row in results])
    db.commit()
    return {"items": results}


@router.get("/admin/assessments/{assessment_id}/invitations")
def admin_invitations(assessment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    assessment = managed_assessment(db, assessment_id, user)
    rows = db.scalars(select(AssessmentInvitation).where(AssessmentInvitation.assessment_id == assessment.id)
                      .order_by(AssessmentInvitation.created_at.desc()))
    items = []
    for row in rows:
        status = row.status
        if status == "pending" and row.expires_at is not None and utc(row.expires_at) <= now():
            status = "expired"
        items.append({"id": row.id, "email": row.email, "status": status, "created_at": iso(row.created_at),
                      "expires_at": iso(row.expires_at), "accepted_at": iso(row.accepted_at)})
    return {"items": items, "total": len(items)}


@router.delete("/admin/assessment-invitations/{invitation_id}", status_code=204)
def admin_revoke_invitation(invitation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(AssessmentInvitation, invitation_id)
    if row is None:
        raise HTTPException(404, "Invitation not found.")
    managed_assessment(db, row.assessment_id, user)
    if row.status != "revoked":
        row.status = "revoked"
        audit(db, user.id, "assessment.invitation_revoked", "assessment_invitation", row.id, email=row.email)
        db.commit()


@router.post("/admin/assessment-sessions/{session_id}/corrections")
def admin_correct(session_id: str, data: CorrectionCreate, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    session = db.get(AssessmentSession, session_id)
    if session is None:
        raise HTTPException(404, "Assessment session not found.")
    managed_assessment(db, session.assessment_id, user)
    report = service.apply_correction(db, session, user, data)
    db.commit()
    return {"report": reports.full_view(report), "report_version": session.report_version,
            "total_score": session.total_score}


@router.post("/admin/assessment-sessions/{session_id}/release")
def admin_release(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = db.get(AssessmentSession, session_id)
    if session is None:
        raise HTTPException(404, "Assessment session not found.")
    managed_assessment(db, session.assessment_id, user)
    if session.report is None:
        raise HTTPException(409, "Only finalized sessions can be released.")
    service.release_report(db, session, user)
    db.commit()
    return {"released": True}


@router.get("/admin/assessment-sessions/{session_id}/events")
def admin_session_events(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = db.get(AssessmentSession, session_id)
    if session is None:
        raise HTTPException(404, "Assessment session not found.")
    reviewed_assessment(db, session.assessment_id, user)
    rows = db.scalars(select(Event).where(Event.assessment_session_id == session.id).order_by(Event.id))
    items = [{"id": row.id, "type": row.type, "created_at": iso(row.created_at), "problem_id": row.problem_id,
              "attempt_id": row.attempt_id, "data": row.data} for row in rows]
    return {"items": items, "total": len(items)}
