"""Assessment background jobs: deadline expiry and deferred finalization (PRD 11.3)."""
from sqlalchemy import select

from app.auth import utc
from app.celery_app import celery
from app.db import open_session
from app.models import AssessmentSession, now


@celery.task(name="app.assessments.finalize")
def finalize_session_task(session_id: str, reason: str = "submitted"):
    """Finalize one session. Idempotent; an active session is only closed when its deadline passed."""
    from app.assessments.service import finalize_session
    with open_session() as db:
        session = db.get(AssessmentSession, session_id)
        if session is None or session.finalized_at is not None:
            return None
        if session.status == "active":
            due = utc(session.expires_at) <= now()
            if reason == "expired" and not due:
                return None
            finalize_session(db, session, reason="expired" if due else reason)
        else:
            finalize_session(db, session, reason="expired" if session.status == "expired" else "submitted")
        db.commit()
        return session.status


@celery.task(name="app.assessments.expire_sessions")
def expire_sessions():
    """Close every active session past its deadline and finalize closed sessions whose evaluations finished."""
    from app.assessments.service import finalize_session
    closed = finalized = 0
    with open_session() as db:
        due = list(db.scalars(select(AssessmentSession).where(AssessmentSession.status == "active",
                                                              AssessmentSession.expires_at <= now())))
        for session in due:
            finalize_session(db, session, reason="expired")
            db.commit()
            closed += 1
        waiting = list(db.scalars(select(AssessmentSession).where(
            AssessmentSession.status.in_(["completed", "expired"]), AssessmentSession.finalized_at.is_(None))))
        for session in waiting:
            finalize_session(db, session, reason="expired" if session.status == "expired" else "submitted")
            db.commit()
            finalized += session.finalized_at is not None
    return {"closed": closed, "finalized": finalized}
