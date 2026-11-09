"""Incident sessions, investigation evidence, resolutions and administrator authoring (PRD §6).

Each user works in their own incident session. The incident's code lives in an ordinary
``Problem`` (visibility "incident") so the existing sandbox, submissions, hints and quality
pipeline all apply; the session's ``ChallengeAttempt`` ties diagnosis, patches and resolutions
together. Artifacts are static, fictional datasets that reach a user only through their session.
"""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from app import attempts, policy, scoring
from app.auth import utc
from app.catalog import code
from app.events import audit, record_event
from app.incidents import validation
from app.models import (
    ChallengeAttempt,
    Incident,
    IncidentResolution,
    IncidentSession,
    Problem,
    Submission,
    now,
)
from app.taxonomy import BUG_CATEGORIES

STALE_EVALUATION = timedelta(minutes=10)
ADMIN_PROBLEM_ID_FLOOR = 105000   # Administrator-authored incidents never collide with catalog IDs
ADMIN_INCIDENT_ID_FLOOR = 5000    # (catalog incidents use 1.. and problem IDs 100001..).
OVERVIEW_FIELDS = ("slug", "title", "summary", "severity", "level", "affected_services", "impact",
                   "expected_behavior", "observed_symptoms", "status", "version")


# ── lookups and views ────────────────────────────────────────────────────────────────


def incident_problem(db, incident: Incident) -> Problem:
    problem = db.get(Problem, incident.problem_id)
    if problem is None:
        raise HTTPException(404, "Incident not found.")
    return problem


def get_incident(db, slug: str, user=None) -> Incident:
    incident = db.scalar(select(Incident).where(Incident.slug == slug))
    if incident is None or (incident.status != "published" and not policy.is_admin(user)):
        raise HTTPException(404, "Incident not found.")
    return incident


def get_session(db, session_id: str, user) -> IncidentSession:
    session = db.get(IncidentSession, session_id)
    # Another user's session is indistinguishable from a missing one.
    if session is None or (session.user_id != user.id and not policy.is_admin(user)):
        raise HTTPException(404, "Incident session not found.")
    return session


def category_label(category: str) -> dict:
    return {"id": category, "name": BUG_CATEGORIES.get(category, {}).get("name", category)}


def artifact_manifest(incident: Incident) -> list[dict]:
    return [{key: artifact.get(key) for key in ("id", "type", "title", "description")}
            for artifact in incident.artifacts or []]


def overview(incident: Incident, problem: Problem | None = None) -> dict:
    data = {key: getattr(incident, key) for key in OVERVIEW_FIELDS}
    config = incident.evaluation_config or {}
    data.update(category=category_label(incident.category), timeline=incident.timeline or [],
                objective=config.get("objective", ""), artifacts=artifact_manifest(incident),
                scenarios=[{key: scenario.get(key) for key in ("id", "name", "description", "tests")}
                           for scenario in incident.scenarios or []],
                weights=config.get("weights") or scoring.INCIDENT_WEIGHTS)
    if problem is not None:
        data.update(problem_slug=problem.slug, difficulty=problem.difficulty, languages=list(problem.starters),
                    estimated_minutes=problem.estimated_minutes)
    return data


def session_summary(session: IncidentSession | None) -> dict | None:
    if session is None:
        return None
    return {"id": session.id, "status": session.status, "score": session.score, "started_at": session.started_at,
            "resolved_at": session.resolved_at}


def latest_session(db, user_id: str, incident_id: int) -> IncidentSession | None:
    return db.scalar(select(IncidentSession).where(IncidentSession.user_id == user_id,
                                                   IncidentSession.incident_id == incident_id)
                     .order_by(IncidentSession.started_at.desc()).limit(1))


def best_score(db, user_id: str, incident_id: int) -> float | None:
    return db.scalar(select(func.max(IncidentSession.score)).where(IncidentSession.user_id == user_id,
                                                                    IncidentSession.incident_id == incident_id))


def list_incidents(db, user=None) -> list[dict]:
    query = select(Incident).order_by(Incident.level, Incident.id)
    if not policy.is_admin(user):
        query = query.where(Incident.status == "published")
    rows = []
    for incident in db.scalars(query):
        problem = db.get(Problem, incident.problem_id)
        row = {key: getattr(incident, key) for key in ("slug", "title", "summary", "severity", "level",
                                                        "affected_services", "status")}
        row.update(category=category_label(incident.category),
                   estimated_minutes=problem.estimated_minutes if problem else None,
                   languages=list(problem.starters) if problem else [],
                   artifact_count=len(incident.artifacts or []),
                   my_session=session_summary(latest_session(db, user.id, incident.id)) if user else None,
                   best_score=best_score(db, user.id, incident.id) if user else None)
        rows.append(row)
    return rows


def resolution_view(row: IncidentResolution) -> dict:
    """The submitter's view. Reference outputs are never included, only validity flags."""
    return {key: getattr(row, key) for key in (
        "id", "session_id", "diagnosis_id", "submission_id", "impact_assessment", "remediation", "prevention",
        "regression_tests", "regression_results", "status", "score", "scores", "error", "created_at", "evaluated_at")}


def expire_stale(db, row: IncidentResolution) -> bool:
    """A queued/running evaluation whose worker vanished becomes a retryable error."""
    if row.status in {"queued", "running"} and utc(row.created_at) < now() - STALE_EVALUATION:
        row.status = "error"
        row.error = "The evaluation worker did not finish. Retry the evaluation."
        return True
    return False


def session_attempt(db, user_id: str, session: IncidentSession, problem: Problem) -> ChallengeAttempt:
    return attempts.get_or_create_attempt(db, user_id, problem.id, incident_session_id=session.id)


def investigation_summary(incident: Incident, session: IncidentSession, db, attempt: ChallengeAttempt) -> dict:
    viewed = (session.investigation or {}).get("viewed", {})
    by_id = {artifact.get("id"): artifact.get("type") for artifact in incident.artifacts or []}
    viewed_types = sorted({by_id[artifact_id] for artifact_id in viewed if artifact_id in by_id})
    counts = dict(db.execute(select(Submission.kind, func.count()).where(Submission.attempt_id == attempt.id)
                             .group_by(Submission.kind)).all())
    return {"viewed": viewed, "viewed_types": viewed_types,
            "available_types": sorted(set(by_id.values())),
            "coverage": round(len(viewed_types) / len(set(by_id.values())), 4) if by_id else 0.0,
            "runs": counts.get("run", 0), "submissions": counts.get("submit", 0)}


def session_payload(db, session: IncidentSession, user) -> dict:
    from app.api import problem_payload

    incident = db.get(Incident, session.incident_id)
    problem = incident_problem(db, incident)
    attempt = session_attempt(db, session.user_id, session, problem)
    diagnosis = attempts.latest_diagnosis(db, attempt.id)
    resolutions = list(db.scalars(select(IncidentResolution).where(IncidentResolution.session_id == session.id)
                                  .order_by(IncidentResolution.created_at.desc())))
    for row in resolutions:
        expire_stale(db, row)
    submissions = list(db.scalars(select(Submission).where(Submission.attempt_id == attempt.id)
                                  .order_by(Submission.created_at.desc()).limit(20)))
    data = overview(incident, problem)
    data["artifacts"] = [dict(artifact) for artifact in incident.artifacts or []]
    return {
        "session": {**session_summary(session), "scores": session.scores or {}, "investigation":
                    investigation_summary(incident, session, db, attempt)},
        "incident": data,
        "problem": problem_payload(db, problem, user, include_progress=False),
        "attempt": {"id": attempt.id, "status": attempt.status, "scores": (attempt.scores or {}).get("components", {}),
                    "total": attempt.total_score},
        "diagnosis": {"required": True, "submitted": diagnosis is not None,
                      "latest": {"id": diagnosis.id, "score": diagnosis.score, "revision": diagnosis.revision,
                                 "created_at": diagnosis.created_at} if diagnosis is not None else None},
        "submissions": [{"id": row.id, "kind": row.kind, "status": row.status, "language": row.language,
                         "created_at": row.created_at} for row in submissions],
        "resolutions": [resolution_view(row) for row in resolutions],
    }


# ── sessions and investigation ───────────────────────────────────────────────────────


def start_session(db, user, incident: Incident) -> tuple[IncidentSession, bool]:
    existing = db.scalar(select(IncidentSession).where(IncidentSession.user_id == user.id,
                                                       IncidentSession.incident_id == incident.id,
                                                       IncidentSession.status == "active")
                         .order_by(IncidentSession.started_at.desc()).limit(1))
    if existing is not None:
        return existing, False
    session = IncidentSession(incident_id=incident.id, user_id=user.id, investigation={"viewed": {}})
    db.add(session)
    db.flush()
    problem = incident_problem(db, incident)
    attempt = session_attempt(db, user.id, session, problem)
    record_event(db, "incident.session_started", user_id=user.id, problem_id=problem.id, attempt_id=attempt.id,
                 incident_session_id=session.id, incident=incident.slug, incident_version=incident.version)
    return session, True


def record_artifact_view(db, session: IncidentSession, artifact_id: str) -> dict:
    incident = db.get(Incident, session.incident_id)
    artifact = next((item for item in incident.artifacts or [] if item.get("id") == artifact_id), None)
    if artifact is None:
        raise HTTPException(404, "Artifact not found.")
    investigation = dict(session.investigation or {})
    viewed = dict(investigation.get("viewed") or {})
    first = artifact_id not in viewed
    if first:
        viewed[artifact_id] = now().isoformat()
    investigation["viewed"] = viewed
    investigation["view_count"] = int(investigation.get("view_count", 0)) + 1
    # Reassign so the JSON column change is persisted.
    session.investigation = investigation
    session.last_activity_at = now()
    record_event(db, "incident.artifact_viewed", user_id=session.user_id, problem_id=incident.problem_id,
                 incident_session_id=session.id, artifact_id=artifact_id, artifact_type=artifact.get("type"),
                 first_view=first)
    return {"artifact_id": artifact_id, "first_view": first, "viewed": sorted(viewed)}


# ── resolutions ──────────────────────────────────────────────────────────────────────


def create_resolution(db, user, session: IncidentSession, data: dict) -> IncidentResolution:
    if session.user_id != user.id:
        raise HTTPException(404, "Incident session not found.")
    if session.status != "active":
        raise HTTPException(409, "This incident session is closed.")
    incident = db.get(Incident, session.incident_id)
    problem = incident_problem(db, incident)
    attempt = session_attempt(db, user.id, session, problem)
    pending = list(db.scalars(select(IncidentResolution).where(
        IncidentResolution.session_id == session.id, IncidentResolution.status.in_(["queued", "running"]))))
    if any(not expire_stale(db, row) for row in pending):
        raise HTTPException(409, "Wait for the current resolution to finish evaluating.")
    diagnosis = attempts.latest_diagnosis(db, attempt.id)
    if diagnosis is None:
        raise HTTPException(428, "Submit your root-cause diagnosis before resolving the incident.")
    submission_id = data.get("submission_id")
    if submission_id:
        submission = db.get(Submission, submission_id)
        if submission is None or submission.attempt_id != attempt.id:
            raise HTTPException(404, "That submission does not belong to this incident session.")
    try:
        tests = validation.normalize_regression_tests(data.get("regression_tests") or [])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row = IncidentResolution(session_id=session.id, user_id=user.id, diagnosis_id=diagnosis.id,
                             submission_id=submission_id, impact_assessment=data.get("impact_assessment", ""),
                             remediation=data.get("remediation", ""), prevention=data.get("prevention", ""),
                             regression_tests=tests, regression_results=[], status="queued",
                             rubric_version=problem.rubric_version)
    db.add(row)
    db.flush()
    session.last_activity_at = now()
    attempt.last_activity_at = now()
    record_event(db, "incident.resolution_submitted", user_id=user.id, problem_id=problem.id,
                 attempt_id=attempt.id, incident_session_id=session.id, resolution_id=row.id,
                 regression_tests=len(tests))
    return row


def evaluation_language(problem: Problem, submission: Submission | None) -> str:
    if submission is not None and submission.language in problem.solutions:
        return submission.language
    return "python" if "python" in problem.solutions else next(iter(problem.solutions))


def classify_regression(tests: list[dict], reference: list[dict], starter: list[dict],
                        reference_status: str, starter_status: str, fix: list[dict] | None = None) -> list[dict]:
    """Per-test validity (passes on the reference) and detection (fails on the original defect)."""
    rows = []
    for index, test in enumerate(tests):
        ref = reference[index] if len(reference) == len(tests) else {"status": reference_status}
        old = starter[index] if len(starter) == len(tests) else {"status": starter_status}
        valid = ref.get("status") == "passed"
        detects = valid and old.get("status") != "passed"
        if detects:
            reason = "Fails on the original defect and passes on the correct behaviour."
        elif valid:
            reason = "Valid, but the original defect also passes it, so it would not catch a regression."
        elif ref.get("status") == "failed":
            reason = "Its expected value does not match the correct behaviour for that input."
        else:
            reason = "The correct implementation cannot process this input; check the input shape."
        row = {"name": test["name"], "valid": valid, "detects_bug": detects,
               "reference_status": ref.get("status"), "starter_status": old.get("status"),
               "credit": 1.0 if detects else 0.3 if valid else 0.0, "reason": reason}
        if fix is not None:
            mine = fix[index] if len(fix) == len(tests) else {}
            row["your_fix_status"] = mine.get("status")
        rows.append(row)
    return rows


def finish_resolution(db, row: IncidentResolution, regression_results: list[dict]) -> dict:
    """Score a resolution whose regression tests ran, and update the session (idempotent)."""
    from app.incidents.scoring import score_resolution

    session = db.get(IncidentSession, row.session_id)
    incident = db.get(Incident, session.incident_id)
    problem = incident_problem(db, incident)
    attempt = session_attempt(db, session.user_id, session, problem)
    row.regression_results = regression_results
    breakdown = score_resolution(db, row, session, incident, problem, attempt)
    row.scores = breakdown
    row.score = breakdown["total"]
    row.status, row.error, row.evaluated_at = "evaluated", None, now()
    if session.score is None or (row.score or 0) >= session.score:
        session.score = row.score
        session.scores = {"best_resolution_id": row.id, **breakdown}
    if breakdown["outcome"]["fixed_immediate_defect"] and session.status == "active":
        session.status, session.resolved_at = "resolved", now()
    record_event(db, "incident.resolution_evaluated", user_id=session.user_id, problem_id=problem.id,
                 attempt_id=attempt.id, incident_session_id=session.id, resolution_id=row.id, score=row.score,
                 fixed=breakdown["outcome"]["fixed_immediate_defect"],
                 prevented=breakdown["outcome"]["prevented_recurrence"])
    return breakdown


# ── administrator authoring ──────────────────────────────────────────────────────────


def problem_fields(definition: dict) -> dict:
    spec = definition["problem"]
    return {
        "slug": f"incident-{definition['slug']}", "title": spec["title"], "summary": spec["summary"],
        "description": spec.get("description") or spec["summary"], "category": spec["category"],
        "difficulty": spec["difficulty"], "tags": list(spec.get("tags", [])),
        "requirements": list(spec["requirements"]),
        "starters": {language: code(source) for language, source in spec["starters"].items()},
        "solutions": {language: code(source) for language, source in spec["solutions"].items()},
        "explanation": spec["explanation"], "hints": list(spec["hints"]), "tests": spec["tests"],
        "estimated_minutes": spec.get("minutes", 30), "visibility": "incident", "diagnosis_mode": "required",
        "diagnosis_rubric": definition["rubric"], "taxonomy": definition["taxonomy"],
        "extra": {"incident_slug": definition["slug"]},
    }


def incident_fields(definition: dict) -> dict:
    from app.scoring import INCIDENT_WEIGHTS

    return {
        "slug": definition["slug"], "title": definition["title"], "summary": definition["summary"],
        "severity": definition["severity"], "level": definition["level"], "category": definition["category"],
        "affected_services": definition["affected_services"], "impact": definition["impact"],
        "expected_behavior": definition["expected_behavior"], "observed_symptoms": definition["observed_symptoms"],
        "timeline": definition["timeline"], "artifacts": definition["artifacts"],
        "scenarios": definition["scenarios"],
        "evaluation_config": {"concepts": definition["evaluation"], "objective": definition.get("objective", ""),
                              "weights": dict(definition.get("weights") or INCIDENT_WEIGHTS)},
    }


def create_draft(db, admin, definition: dict) -> Incident:
    errors = validation.validate_definition(definition)
    if errors:
        raise HTTPException(422, "The incident definition is invalid: " + " ".join(errors[:20]))
    problem_slug = f"incident-{definition['slug']}"
    if db.scalar(select(Incident.id).where(Incident.slug == definition["slug"])) \
            or db.scalar(select(Problem.id).where(Problem.slug == problem_slug)):
        raise HTTPException(409, "An incident with that slug already exists.")
    problem_id = max(db.scalar(select(func.max(Problem.id)).where(Problem.id > ADMIN_PROBLEM_ID_FLOOR)) or 0,
                     ADMIN_PROBLEM_ID_FLOOR) + 1
    incident_id = max(db.scalar(select(func.max(Incident.id)).where(Incident.id > ADMIN_INCIDENT_ID_FLOOR)) or 0,
                      ADMIN_INCIDENT_ID_FLOOR) + 1
    fields = problem_fields(definition)
    problem = Problem(id=problem_id, content_hash=validation.content_hash(fields), **fields)
    db.add(problem)
    db.flush()
    incident = Incident(id=incident_id, problem_id=problem.id, status="draft", version=1, **incident_fields(definition))
    db.add(incident)
    db.flush()
    audit(db, admin.id, "incident.created", "incident", incident.slug, problem_id=problem.id, status="draft")
    return incident


def validation_state(incident: Incident, problem: Problem) -> dict:
    state = dict((incident.evaluation_config or {}).get("validation") or {})
    current = validation.content_hash({"starters": problem.starters, "solutions": problem.solutions,
                                       "tests": problem.tests})
    state["current"] = (state.get("status") == "passed" and state.get("version") == incident.version
                        and state.get("content_hash") == current)
    return state


def set_validation(incident: Incident, state: dict) -> None:
    incident.evaluation_config = {**(incident.evaluation_config or {}), "validation": state}


def publish(db, admin, incident: Incident) -> None:
    problem = incident_problem(db, incident)
    if not validation_state(incident, problem)["current"]:
        raise HTTPException(409, "Validate this version of the incident successfully before publishing it.")
    incident.status = "published"
    audit(db, admin.id, "incident.published", "incident", incident.slug, version=incident.version)


def unpublish(db, admin, incident: Incident) -> None:
    incident.status = "draft"
    audit(db, admin.id, "incident.unpublished", "incident", incident.slug, version=incident.version)


def admin_view(db, incident: Incident) -> dict:
    problem = incident_problem(db, incident)
    sessions = db.scalar(select(func.count()).select_from(IncidentSession)
                         .where(IncidentSession.incident_id == incident.id)) or 0
    return {**overview(incident, problem), "id": incident.id, "problem_id": problem.id,
            "validation": validation_state(incident, problem), "sessions": sessions,
            "updated_at": incident.updated_at}
