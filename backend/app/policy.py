"""Server-side assistance and access policy (PRD 8.8, 9.5, 13.2; AR-011, AS-005).

While a user has an active assessment session that contains a problem, that session's policy
applies to the problem everywhere — including the ordinary practice workspace — so a candidate
cannot open the public page in another tab to obtain hints, AI help or the reference solution.
Browser restrictions are never relied on.
"""
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select

from app.auth import utc
from app.config import settings
from app.models import AssessmentSession, IncidentSession, Problem, now

AI_LEVELS = ("disabled", "guided", "enabled")
HINT_LEVELS = ("disabled", "restricted", "enabled")
# Intents allowed under a "guided" AI policy: conceptual help only, never patch review.
GUIDED_INTENTS = {"explain_problem", "explain_concept", "find_documentation", "progressive_hint"}
RESTRICTED_HINT_LEVEL = 1


@dataclass
class Assistance:
    ai: str = "enabled"
    hints: str = "enabled"
    session: AssessmentSession | None = None
    source: str = "practice"

    def as_dict(self) -> dict:
        return {"ai": self.ai, "hints": self.hints, "source": self.source,
                "assessment_session_id": self.session.id if self.session else None}


def session_policy(session: AssessmentSession) -> dict:
    policy = (session.config_snapshot or {}).get("assistance_policy") or {}
    ai = policy.get("ai", "disabled")
    hints = policy.get("hints", "disabled")
    return {"ai": ai if ai in AI_LEVELS else "disabled", "hints": hints if hints in HINT_LEVELS else "disabled"}


def session_problem_ids(session: AssessmentSession) -> list[int]:
    return [int(value) for value in (session.challenge_order or [])]


def expire_if_due(db, session: AssessmentSession) -> bool:
    """Finalize an active session whose server-side deadline has passed. Returns True if it expired."""
    if session.status != "active" or utc(session.expires_at) > now():
        return False
    from app.assessments.service import finalize_session
    finalize_session(db, session, reason="expired")
    db.commit()
    return True


def active_assessment_sessions(db, user_id: str) -> list[AssessmentSession]:
    rows = list(db.scalars(select(AssessmentSession).where(AssessmentSession.user_id == user_id,
                                                           AssessmentSession.status == "active")))
    return [row for row in rows if not expire_if_due(db, row)]


def assessment_session_for_problem(db, user_id: str, problem_id: int) -> AssessmentSession | None:
    for session in active_assessment_sessions(db, user_id):
        if problem_id in session_problem_ids(session):
            return session
    return None


def ensure_session_open(db, session: AssessmentSession) -> None:
    """Reject work on a session that is finalized or past its deadline (timer enforced here)."""
    if expire_if_due(db, session) or session.status != "active":
        raise HTTPException(409, "This assessment session has ended. Your work up to the deadline is saved.")


def assistance_for(db, user, problem: Problem, session: AssessmentSession | None = None) -> Assistance:
    if user is not None and session is None:
        session = assessment_session_for_problem(db, user.id, problem.id)
    if session is not None:
        policy = session_policy(session)
        return Assistance(ai=policy["ai"], hints=policy["hints"], session=session, source="assessment")
    return Assistance(ai="enabled" if settings.ai_enabled else "disabled", hints="enabled")


def ensure_ai_allowed(assistance: Assistance, intent: str | None = None, *, generation: bool = False) -> None:
    """``generation`` marks AI-written code (AI-mode submissions); only an open policy allows it."""
    if assistance.source != "assessment":
        return
    if assistance.ai == "disabled":
        raise HTTPException(403, "AI assistance is disabled for this assessment.")
    if assistance.ai == "guided" and (generation or (intent or "") not in GUIDED_INTENTS):
        raise HTTPException(403, "This assessment allows only conceptual AI guidance.")


def hint_level_cap(assistance: Assistance) -> int | None:
    if assistance.source != "assessment" or assistance.hints == "enabled":
        return None
    return 0 if assistance.hints == "disabled" else RESTRICTED_HINT_LEVEL


def ensure_hint_allowed(assistance: Assistance, level: int) -> None:
    cap = hint_level_cap(assistance)
    if cap is None:
        return
    if cap == 0:
        raise HTTPException(403, "Hints are disabled for this assessment.")
    if level > cap:
        raise HTTPException(403, "This assessment allows only the first, conceptual hint.")


def incident_session_for_problem(db, user_id: str, problem_id: int, *, active_only: bool = True):
    from app.models import Incident
    query = (select(IncidentSession).join(Incident, IncidentSession.incident_id == Incident.id)
             .where(IncidentSession.user_id == user_id, Incident.problem_id == problem_id))
    if active_only:
        query = query.where(IncidentSession.status == "active")
    return db.scalar(query.order_by(IncidentSession.started_at.desc()).limit(1))


def is_admin(user) -> bool:
    return bool(user and settings.admin_email and user.email == settings.admin_email)


def can_view_problem(db, user, problem: Problem) -> bool:
    if problem.visibility == "public":
        return True
    if user is None:
        return False
    if is_admin(user):
        return True
    if problem.visibility == "incident":
        return incident_session_for_problem(db, user.id, problem.id, active_only=False) is not None
    if problem.visibility == "assessment":
        return assessment_session_for_problem(db, user.id, problem.id) is not None
    return False


def solutions_locked(db, user, problem: Problem) -> str | None:
    """A reason the reference solution must stay hidden for this user, or None."""
    if user is None:
        return "Sign in to view solutions."
    if assessment_session_for_problem(db, user.id, problem.id) is not None:
        return "Solutions stay locked while this problem is part of your active assessment."
    if problem.visibility == "assessment":
        return "Assessment challenges do not release reference solutions."
    if problem.visibility == "draft" and not is_admin(user):
        return "This problem is not published."
    return None
