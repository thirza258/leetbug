"""Product instrumentation and administrative audit trail.

Both helpers only add rows; the caller's transaction decides when they are committed.
"""
from app.models import AuditLog, Event


def record_event(db, event_type: str, *, user_id=None, problem_id=None, attempt_id=None,
                 assessment_session_id=None, incident_session_id=None, **data) -> Event:
    event = Event(type=event_type, user_id=user_id, problem_id=problem_id, attempt_id=attempt_id,
                  assessment_session_id=assessment_session_id, incident_session_id=incident_session_id,
                  data=data)
    db.add(event)
    return event


def audit(db, actor_id, action: str, entity_type: str, entity_id, **details) -> AuditLog:
    row = AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=str(entity_id),
                   details=details)
    db.add(row)
    return row
