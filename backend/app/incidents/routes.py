"""Production incident API (PRD 6.7, 11.5).

Sessions are private to their owner (administrators may inspect them); artifacts are served only
inside a session. Administrators author incidents as drafts, validate that the documented
failure reproduces, and publish.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user, optional_user, require_admin, utc
from app.db import get_db
from app.events import audit
from app.incidents import service
from app.incidents.tasks import evaluate_resolution, validate_incident
from app.limits import rate_limit
from app.models import Incident, IncidentResolution, IncidentSession, User, now

router = APIRouter(prefix="/api", tags=["incidents"])
STALE_VALIDATION = timedelta(minutes=10)


class IncidentDiagnosisCreate(BaseModel):
    defect_category: str = Field(min_length=1, max_length=40)
    root_cause: str = Field(min_length=1, max_length=4000)
    affected_component: str = Field(min_length=1, max_length=2000)
    violated_invariant: str = Field(min_length=1, max_length=4000)
    proposed_correction: str = Field(min_length=1, max_length=4000)
    reproduction_strategy: str = Field(min_length=1, max_length=4000)
    language: str | None = Field(default=None, max_length=20)


class RegressionTest(BaseModel):
    name: str = Field(default="", max_length=120)
    input: object
    expected: object


class ResolutionCreate(BaseModel):
    impact_assessment: str = Field(min_length=20, max_length=6000)
    remediation: str = Field(min_length=20, max_length=6000)
    prevention: str = Field(min_length=20, max_length=6000)
    regression_tests: list[RegressionTest] = Field(default_factory=list, max_length=10)
    submission_id: str | None = Field(default=None, min_length=36, max_length=36)


def _enqueue(db, task, row, *args):
    try:
        task.delay(*args)
    except Exception as exc:
        if isinstance(row, IncidentResolution):
            row.status, row.error = "error", "The queue is temporarily unavailable. Retry the evaluation."
        db.commit()
        raise HTTPException(503, "The queue is temporarily unavailable. Please try again.") from exc


# ── learner endpoints ────────────────────────────────────────────────────────────────


@router.get("/incidents")
def incidents(user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return {"items": service.list_incidents(db, user)}


@router.get("/incidents/{slug}")
def incident_overview(slug: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    incident = service.get_incident(db, slug, user)
    problem = service.incident_problem(db, incident)
    data = service.overview(incident, problem)
    if user is not None:
        data["my_session"] = service.session_summary(service.latest_session(db, user.id, incident.id))
        data["best_score"] = service.best_score(db, user.id, incident.id)
    return data


@router.post("/incidents/{slug}/sessions", status_code=201)
def start_incident_session(slug: str, response: Response, user: User = Depends(current_user),
                           db: Session = Depends(get_db)):
    rate_limit(f"incident:{user.id}", 30)
    incident = service.get_incident(db, slug, user)
    session, created = service.start_session(db, user, incident)
    db.commit()
    if not created:
        response.status_code = 200
    return service.session_payload(db, session, user)


@router.get("/incidents/sessions/{session_id}")
def incident_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = service.get_session(db, session_id, user)
    payload = service.session_payload(db, session, user)
    db.commit()  # Persists any stale-evaluation expiry noticed while building the payload.
    return payload


@router.post("/incidents/sessions/{session_id}/artifacts/{artifact_id}/view")
def view_artifact(session_id: str, artifact_id: str, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    rate_limit(f"incident-view:{user.id}", 240)
    session = service.get_session(db, session_id, user)
    if session.user_id != user.id:
        raise HTTPException(404, "Incident session not found.")
    result = service.record_artifact_view(db, session, artifact_id)
    db.commit()
    return result


@router.post("/incidents/sessions/{session_id}/diagnosis", status_code=201)
def incident_diagnosis(session_id: str, data: IncidentDiagnosisCreate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Alias of POST /api/problems/{slug}/diagnosis bound to this incident session (PI-007)."""
    rate_limit(f"incident:{user.id}", 30)
    session = service.get_session(db, session_id, user)
    if session.user_id != user.id:
        raise HTTPException(404, "Incident session not found.")
    incident = db.get(Incident, session.incident_id)
    problem = service.incident_problem(db, incident)
    from app.diagnosis.service import create_diagnosis, diagnosis_view

    row = create_diagnosis(db, user, problem, data.model_dump(exclude_none=True), incident_session_id=session.id)
    db.commit()
    return diagnosis_view(row)


@router.post("/incidents/sessions/{session_id}/resolve", status_code=202)
def resolve_incident(session_id: str, data: ResolutionCreate, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    rate_limit(f"incident-resolve:{user.id}", 6)
    session = service.get_session(db, session_id, user)
    # Lock the session so two simultaneous resolutions cannot both pass the pending check.
    db.scalar(select(IncidentSession).where(IncidentSession.id == session.id).with_for_update())
    row = service.create_resolution(db, user, session, data.model_dump())
    db.commit()
    _enqueue(db, evaluate_resolution, row, row.id)
    return service.resolution_view(row)


def _owned_resolution(db, resolution_id: str, user) -> IncidentResolution:
    row = db.get(IncidentResolution, resolution_id)
    if row is None or (row.user_id != user.id and not service.policy.is_admin(user)):
        raise HTTPException(404, "Resolution not found.")
    return row


@router.get("/incidents/resolutions/{resolution_id}")
def incident_resolution(resolution_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = _owned_resolution(db, resolution_id, user)
    if service.expire_stale(db, row):
        db.commit()
    return service.resolution_view(row)


@router.post("/incidents/resolutions/{resolution_id}/retry", status_code=202)
def retry_resolution(resolution_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(f"incident-resolve:{user.id}", 6)
    row = _owned_resolution(db, resolution_id, user)
    service.expire_stale(db, row)
    if row.status != "error":
        raise HTTPException(409, "Only a failed evaluation can be retried.")
    row.status, row.error = "queued", None
    db.commit()
    _enqueue(db, evaluate_resolution, row, row.id)
    return service.resolution_view(row)


# ── administration (PI-001, PI-002) ──────────────────────────────────────────────────


def _admin_incident(db, slug: str) -> Incident:
    incident = db.scalar(select(Incident).where(Incident.slug == slug))
    if incident is None:
        raise HTTPException(404, "Incident not found.")
    return incident


@router.get("/admin/incidents")
def admin_incidents(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Incident).order_by(Incident.id))
    return {"items": [service.admin_view(db, incident) for incident in rows]}


@router.get("/admin/incidents/{slug}")
def admin_incident(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    incident = _admin_incident(db, slug)
    data = service.admin_view(db, incident)
    data["artifacts"] = incident.artifacts or []
    data["evaluation_config"] = incident.evaluation_config or {}
    return data


@router.post("/admin/incidents", status_code=201)
def admin_create_incident(definition: dict = Body(...), admin: User = Depends(require_admin),
                          db: Session = Depends(get_db)):
    rate_limit(f"incident-admin:{admin.id}", 10)
    incident = service.create_draft(db, admin, definition)
    db.commit()
    return service.admin_view(db, incident)


@router.post("/admin/incidents/{slug}/validate", status_code=202)
def admin_validate_incident(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rate_limit(f"incident-admin:{admin.id}", 10)
    incident = _admin_incident(db, slug)
    state = (incident.evaluation_config or {}).get("validation") or {}
    requested = state.get("requested_at")
    if state.get("status") in {"queued", "running"} and requested \
            and utc(datetime.fromisoformat(requested)) > now() - STALE_VALIDATION:
        raise HTTPException(409, "A validation run is already in progress.")
    service.set_validation(incident, {"status": "queued", "version": incident.version,
                                      "requested_at": now().isoformat(), "requested_by": admin.id})
    audit(db, admin.id, "incident.validation_requested", "incident", incident.slug, version=incident.version)
    db.commit()
    _enqueue(db, validate_incident, incident, incident.id)
    return service.admin_view(db, incident)


@router.post("/admin/incidents/{slug}/publish")
def admin_publish_incident(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    incident = _admin_incident(db, slug)
    service.publish(db, admin, incident)
    db.commit()
    return service.admin_view(db, incident)


@router.post("/admin/incidents/{slug}/unpublish")
def admin_unpublish_incident(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    incident = _admin_incident(db, slug)
    service.unpublish(db, admin, incident)
    db.commit()
    return service.admin_view(db, incident)

