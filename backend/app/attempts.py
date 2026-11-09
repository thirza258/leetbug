"""Challenge attempts: the shared container for diagnosis, patches, hints, AI use and explanations.

Practice work uses one attempt per user and problem. Each incident session and each assessment
session gets its own attempt per problem, so the same records feed every scoring path.
"""
import difflib
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import policy, scoring
from app.events import record_event
from app.models import (
    AssessmentSession,
    ChallengeAttempt,
    Diagnosis,
    Incident,
    IncidentSession,
    Problem,
    Submission,
    now,
)


@dataclass
class AttemptContext:
    attempt: ChallengeAttempt
    assessment_session: AssessmentSession | None = None
    incident_session: IncidentSession | None = None

    @property
    def context(self) -> str:
        return self.attempt.context


def scope_for(*, assessment_session_id: str | None = None, incident_session_id: str | None = None) -> tuple[str, str]:
    if assessment_session_id:
        return f"assessment:{assessment_session_id}", "assessment"
    if incident_session_id:
        return f"incident:{incident_session_id}", "incident"
    return "practice", "practice"


def get_or_create_attempt(db, user_id: str, problem_id: int, *, assessment_session_id: str | None = None,
                          incident_session_id: str | None = None) -> ChallengeAttempt:
    scope, context = scope_for(assessment_session_id=assessment_session_id, incident_session_id=incident_session_id)
    query = select(ChallengeAttempt).where(ChallengeAttempt.user_id == user_id,
                                           ChallengeAttempt.problem_id == problem_id,
                                           ChallengeAttempt.scope == scope)
    attempt = db.scalar(query)
    if attempt is not None:
        return attempt
    attempt = ChallengeAttempt(user_id=user_id, problem_id=problem_id, scope=scope, context=context,
                               assessment_session_id=assessment_session_id, incident_session_id=incident_session_id)
    try:
        with db.begin_nested():
            db.add(attempt)
            db.flush()
    except IntegrityError:
        # A concurrent request created the same attempt first.
        attempt = db.scalar(query)
    else:
        record_event(db, "attempt.started", user_id=user_id, problem_id=problem_id, attempt_id=attempt.id,
                     assessment_session_id=assessment_session_id, incident_session_id=incident_session_id,
                     context=context)
    return attempt


def resolve_context(db, user, problem: Problem, *, assessment_session_id: str | None = None,
                    incident_session_id: str | None = None, for_write: bool = True) -> AttemptContext:
    """Validate the requested context and return its attempt.

    Without an explicit session, an active assessment containing the problem is used automatically,
    so assessment policy and timing cannot be bypassed by working from the practice page.
    """
    assessment = incident = None
    if assessment_session_id:
        assessment = db.get(AssessmentSession, assessment_session_id)
        if assessment is None or assessment.user_id != user.id:
            raise HTTPException(404, "Assessment session not found.")
        if problem.id not in policy.session_problem_ids(assessment):
            raise HTTPException(404, "This challenge is not part of the assessment session.")
        if for_write:
            policy.ensure_session_open(db, assessment)
    elif incident_session_id:
        incident = db.get(IncidentSession, incident_session_id)
        if incident is None or incident.user_id != user.id:
            raise HTTPException(404, "Incident session not found.")
        owner = db.get(Incident, incident.incident_id)
        if owner is None or owner.problem_id != problem.id:
            raise HTTPException(404, "This code does not belong to the incident session.")
        if for_write and incident.status != "active":
            raise HTTPException(409, "This incident session is closed.")
    else:
        assessment = policy.assessment_session_for_problem(db, user.id, problem.id)
        if assessment is None and problem.visibility == "incident":
            incident = policy.incident_session_for_problem(db, user.id, problem.id, active_only=False)
            if incident is None or (for_write and incident.status != "active"):
                raise HTTPException(404, "Open this incident from the incident list to work on it.")
        elif assessment is None and problem.visibility == "assessment":
            raise HTTPException(404, "Case study not found.")
        elif assessment is None and problem.visibility == "draft" and not policy.is_admin(user):
            raise HTTPException(404, "Case study not found.")
    attempt = get_or_create_attempt(db, user.id, problem.id,
                                    assessment_session_id=assessment.id if assessment else None,
                                    incident_session_id=incident.id if incident else None)
    if for_write:
        attempt.last_activity_at = now()
        if incident is not None:
            incident.last_activity_at = now()
    return AttemptContext(attempt, assessment, incident)


def latest_diagnosis(db, attempt_id: str) -> Diagnosis | None:
    return db.scalar(select(Diagnosis).where(Diagnosis.attempt_id == attempt_id)
                     .order_by(Diagnosis.created_at.desc(), Diagnosis.revision.desc()).limit(1))


def diagnosis_required(problem: Problem, context: AttemptContext | None) -> bool:
    """DR-002/DR-008: configured per problem, and always for incidents or assessments that require it."""
    if context is not None and context.incident_session is not None:
        return True
    if context is not None and context.assessment_session is not None:
        configuration = (context.assessment_session.config_snapshot or {}).get("configuration", {})
        if configuration.get("diagnosis_required"):
            return True
    return problem.diagnosis_mode == "required"


def diff_stats(original: str, current: str) -> dict:
    """Line-level change summary between the starter and a submitted program."""
    original_lines, current_lines = original.splitlines(), current.splitlines()
    added = removed = 0
    changed_lines: list[int] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=original_lines, b=current_lines,
                                                       autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        removed += i2 - i1
        added += j2 - j1
        # Replacements/deletions mark the touched original lines; an insertion marks the line it follows.
        changed_lines.extend(range(i1 + 1, i2 + 1) if i2 > i1 else [max(1, i1)])
    return {"added": added, "removed": removed, "changed_original_lines": sorted(set(changed_lines))[:200],
            "original_lines": len(original_lines), "current_lines": len(current_lines),
            "unchanged": added == 0 and removed == 0}


def on_submission_complete(db, submission: Submission, problem: Problem) -> None:
    """Called by the evaluation worker after grading. Never alters the graded execution record."""
    if submission.status == "passed" and submission.kind == "submit" and submission.quality is None:
        from app.diagnosis.quality import score_patch
        submission.quality = score_patch(db, problem, submission)
    attempt = db.get(ChallengeAttempt, submission.attempt_id) if submission.attempt_id else None
    record_event(db, "submission.completed", user_id=submission.user_id, problem_id=submission.problem_id,
                 attempt_id=submission.attempt_id, assessment_session_id=submission.assessment_session_id,
                 kind=submission.kind, mode=submission.mode, status=submission.status,
                 turnaround_ms=submission.turnaround_ms, runtime_ms=submission.runtime_ms)
    if attempt is None:
        return
    attempt.last_activity_at = now()
    if submission.status == "passed" and submission.kind == "submit" and attempt.solved_at is None:
        attempt.solved_at = submission.completed_at or now()
    scoring.refresh_attempt(db, attempt)
