"""Diagnosis, explanation, score, insight and rubric-administration endpoints (PRD §5, 11.5)."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import attempts, policy, scoring, taxonomy
from app.auth import current_user, require_admin
from app.config import settings
from app.db import get_db
from app.diagnosis import service
from app.diagnosis.rubric import derive_rubric, rubric_for, validate_rubric
from app.events import audit
from app.limits import rate_limit
from app.models import (
    AssessmentSession,
    ChallengeAttempt,
    Diagnosis,
    FixExplanation,
    Incident,
    IncidentSession,
    Problem,
    Submission,
    User,
)

router = APIRouter(prefix="/api", tags=["diagnosis"])

SessionField = Field(default=None, min_length=36, max_length=36)


class _Stripped(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class DiagnosisCreate(_Stripped):
    defect_category: str = Field(min_length=1, max_length=40)
    root_cause: str = Field(min_length=1, max_length=4000)
    affected_component: str = Field(min_length=1, max_length=1000)
    violated_invariant: str = Field(min_length=1, max_length=2000)
    proposed_correction: str = Field(min_length=1, max_length=4000)
    reproduction_strategy: str = Field(min_length=1, max_length=4000)
    language: Literal["python", "java", "javascript", "cpp", "go"] | None = None
    assessment_session_id: str | None = SessionField
    incident_session_id: str | None = SessionField


class ExplanationCreate(_Stripped):
    why_failed: str = Field(min_length=1, max_length=4000)
    why_works: str = Field(min_length=1, max_length=4000)
    invariant_preserved: str = Field(min_length=1, max_length=2000)
    side_effects: str = Field(default="", max_length=2000)
    additional_tests: str = Field(default="", max_length=4000)
    submission_id: str | None = SessionField
    assessment_session_id: str | None = SessionField
    incident_session_id: str | None = SessionField


class DiagnosisModeUpdate(BaseModel):
    mode: Literal["off", "optional", "required"]


def _problem(db, slug, user) -> Problem:
    from app.api import get_problem
    return get_problem(db, slug, user)


def _existing_context(db, user, problem, assessment_session_id, incident_session_id):
    """Find (without creating) the attempt and sessions a request refers to.

    Mirrors ``attempts.resolve_context``: an active assessment that contains the problem applies
    even when the request does not name it.
    """
    assessment = incident = None
    if assessment_session_id:
        assessment = db.get(AssessmentSession, assessment_session_id)
        if assessment is None or assessment.user_id != user.id or problem.id not in policy.session_problem_ids(assessment):
            raise HTTPException(404, "Assessment session not found.")
    elif incident_session_id:
        incident = db.get(IncidentSession, incident_session_id)
        owner = db.get(Incident, incident.incident_id) if incident else None
        if incident is None or incident.user_id != user.id or owner is None or owner.problem_id != problem.id:
            raise HTTPException(404, "Incident session not found.")
    else:
        assessment = policy.assessment_session_for_problem(db, user.id, problem.id)
        if assessment is None and problem.visibility == "incident":
            incident = policy.incident_session_for_problem(db, user.id, problem.id, active_only=False)
    scope, _ = attempts.scope_for(assessment_session_id=assessment.id if assessment else None,
                                  incident_session_id=incident.id if incident else None)
    attempt = db.scalar(select(ChallengeAttempt).where(ChallengeAttempt.user_id == user.id,
                                                       ChallengeAttempt.problem_id == problem.id,
                                                       ChallengeAttempt.scope == scope))
    return attempt, attempts.AttemptContext(attempt, assessment, incident)


def _categories() -> list[dict]:
    return [{"id": key, "name": value["name"], "description": value["description"]}
            for key, value in taxonomy.BUG_CATEGORIES.items()]


@router.post("/problems/{slug}/diagnosis", status_code=201)
def submit_diagnosis(slug: str, data: DiagnosisCreate, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    rate_limit(f"diagnosis:{user.id}", 20)
    problem = _problem(db, slug, user)
    row = service.create_diagnosis(db, user, problem,
                                   data.model_dump(exclude={"assessment_session_id", "incident_session_id"}),
                                   assessment_session_id=data.assessment_session_id,
                                   incident_session_id=data.incident_session_id)
    db.commit()
    return service.diagnosis_view(row)


@router.get("/problems/{slug}/diagnosis")
def diagnosis_status(slug: str, assessment_session_id: str | None = Query(None, max_length=36),
                     incident_session_id: str | None = Query(None, max_length=36),
                     user: User = Depends(current_user), db: Session = Depends(get_db)):
    problem = _problem(db, slug, user)
    attempt, context = _existing_context(db, user, problem, assessment_session_id, incident_session_id)
    history = list(db.scalars(select(Diagnosis).where(Diagnosis.attempt_id == attempt.id)
                              .order_by(Diagnosis.created_at.desc(), Diagnosis.revision.desc()))) if attempt else []
    explanation = db.scalar(select(FixExplanation).where(FixExplanation.attempt_id == attempt.id)
                            .order_by(FixExplanation.created_at.desc()).limit(1)) if attempt else None
    solved = bool(attempt and db.scalar(select(Submission.id).where(
        Submission.attempt_id == attempt.id, Submission.kind == "submit", Submission.status == "passed").limit(1)))
    return {
        "required": attempts.diagnosis_required(problem, context), "mode": problem.diagnosis_mode,
        "enabled": problem.diagnosis_mode != "off" or attempts.diagnosis_required(problem, context),
        "submitted": bool(history), "attempt_id": attempt.id if attempt else None,
        "context": "assessment" if context.assessment_session else "incident" if context.incident_session else "practice",
        "latest": service.diagnosis_view(history[0]) if history else None,
        "history": [service.diagnosis_view(row) for row in history],
        "explanation": service.explanation_view(explanation) if explanation else None,
        "solved": solved, "scores": service.attempt_scores_view(attempt),
        "categories": _categories(), "pass_threshold": scoring.DIAGNOSIS_PASS_THRESHOLD,
    }


def _owned_or_admin(row, user):
    if row is None or (row.user_id != user.id and not policy.is_admin(user)):
        raise HTTPException(404, "Diagnosis not found.")
    return row


@router.get("/diagnosis/history")
def diagnosis_history(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Diagnosis).where(Diagnosis.user_id == user.id))
    rows = db.execute(select(Diagnosis, Problem).join(Problem, Diagnosis.problem_id == Problem.id)
                      .where(Diagnosis.user_id == user.id).order_by(Diagnosis.created_at.desc())
                      .offset((page - 1) * limit).limit(limit)).all()
    ids = [row.id for row, _ in rows]
    linked: dict[str, list] = {}
    if ids:
        for submission in db.scalars(select(Submission).where(Submission.diagnosis_id.in_(ids))
                                     .order_by(Submission.created_at)):
            linked.setdefault(submission.diagnosis_id, []).append(
                {"id": submission.id, "kind": submission.kind, "status": submission.status,
                 "language": submission.language, "created_at": submission.created_at})
    return {"items": [{**service.diagnosis_view(row), "problem_slug": problem.slug, "problem_title": problem.title,
                       "submissions": linked.get(row.id, [])} for row, problem in rows],
            "total": total, "page": page, "limit": limit}


@router.get("/diagnosis/{diagnosis_id}")
def diagnosis_detail(diagnosis_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = _owned_or_admin(db.get(Diagnosis, diagnosis_id), user)
    return service.diagnosis_view(row, admin=policy.is_admin(user))


@router.post("/diagnosis/{diagnosis_id}/evaluate", status_code=202)
def reevaluate(diagnosis_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = _owned_or_admin(db.get(Diagnosis, diagnosis_id), user)
    if not settings.ai_enabled:
        raise HTTPException(409, "AI evaluation needs a configured model. The deterministic score stands.")
    if row.ai_status in {"queued", "running"} and service._ai_status(row) != "failed":
        return service.diagnosis_view(row)
    rate_limit(f"diagnosis-eval:{user.id}", 5)
    session = db.get(AssessmentSession, row.assessment_session_id) if row.assessment_session_id else None
    if session is not None and session.finalized_at is not None:
        raise HTTPException(409, "Finalized assessment results cannot be re-evaluated.")
    from app.diagnosis.tasks import evaluate_diagnosis_ai
    row.ai_status = "queued"
    db.commit()
    try:
        evaluate_diagnosis_ai.delay(row.id)
    except Exception as exc:
        row.ai_status = "failed"
        db.commit()
        raise HTTPException(503, "The evaluation queue is temporarily unavailable.") from exc
    return service.diagnosis_view(row)


@router.post("/problems/{slug}/explanation", status_code=201)
def submit_explanation(slug: str, data: ExplanationCreate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    rate_limit(f"explanation:{user.id}", 20)
    problem = _problem(db, slug, user)
    row = service.create_explanation(
        db, user, problem, data.model_dump(exclude={"submission_id", "assessment_session_id", "incident_session_id"}),
        submission_id=data.submission_id, assessment_session_id=data.assessment_session_id,
        incident_session_id=data.incident_session_id)
    db.commit()
    return service.explanation_view(row)


@router.get("/problems/{slug}/scores")
def attempt_scores(slug: str, assessment_session_id: str | None = Query(None, max_length=36),
                   incident_session_id: str | None = Query(None, max_length=36),
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    problem = _problem(db, slug, user)
    attempt, _ = _existing_context(db, user, problem, assessment_session_id, incident_session_id)
    if attempt is None:
        return {"attempt": None}
    before = attempt.scores
    service.refresh_scores(db, attempt)
    if attempt.scores != before:
        db.commit()
    return {"attempt": service.attempt_scores_view(attempt), "weights": scoring.ASSESSMENT_WEIGHTS}


@router.get("/insights/me")
def my_insights(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.diagnosis.insights import user_insights
    return user_insights(db, user)


# ── administration (DR-008, DR-009) ───────────────────────────────────────────


def _admin_problem(db, slug) -> Problem:
    problem = db.scalar(select(Problem).where(Problem.slug == slug))
    if problem is None:
        raise HTTPException(404, "Case study not found.")
    return problem


def _rubric_source(problem) -> str:
    stored = problem.diagnosis_rubric
    if isinstance(stored, dict) and stored and not validate_rubric(stored):
        return stored.get("source") if stored.get("source") in {"authored", "admin"} else "authored"
    return "derived"


@router.get("/admin/rubrics")
def admin_rubrics(q: str = Query("", max_length=100), page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100),
                  admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    query = select(Problem)
    if q:
        query = query.where(or_(Problem.title.icontains(q, autoescape=True), Problem.slug.icontains(q, autoescape=True)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Problem.id).offset((page - 1) * limit).limit(limit))
    return {"items": [{"id": row.id, "slug": row.slug, "title": row.title, "category": row.category,
                       "visibility": row.visibility, "diagnosis_mode": row.diagnosis_mode,
                       "rubric_version": row.rubric_version, "rubric_source": _rubric_source(row)} for row in rows],
            "total": total, "page": page, "limit": limit}


@router.get("/admin/problems/{slug}/rubric")
def admin_rubric(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    problem = _admin_problem(db, slug)
    return {"slug": problem.slug, "title": problem.title, "rubric_version": problem.rubric_version,
            "diagnosis_mode": problem.diagnosis_mode, "source": _rubric_source(problem),
            "effective": rubric_for(problem), "derived": derive_rubric(problem), "stored": problem.diagnosis_rubric,
            "categories": _categories()}


@router.put("/admin/problems/{slug}/rubric")
def admin_update_rubric(slug: str, rubric: dict, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    problem = _admin_problem(db, slug)
    errors = validate_rubric(rubric)
    if errors:
        raise HTTPException(422, "The rubric is invalid: " + " ".join(errors))
    previous = problem.diagnosis_rubric
    extra = dict(problem.extra or {})
    if isinstance(previous, dict) and previous.get("source") == "authored":
        # Keep the authored rubric so reverting an override restores it.
        extra["authored_rubric"] = previous
    problem.rubric_version = (problem.rubric_version or 1) + 1
    problem.diagnosis_rubric = {**rubric, "source": "admin", "version": problem.rubric_version}
    problem.extra = extra
    audit(db, admin.id, "rubric.updated", "problem", problem.id, slug=problem.slug,
          rubric_version=problem.rubric_version, previous_source=_rubric_source_value(previous))
    db.commit()
    return admin_rubric(slug, admin, db)


def _rubric_source_value(stored) -> str:
    return stored.get("source", "authored") if isinstance(stored, dict) and stored else "derived"


@router.delete("/admin/problems/{slug}/rubric")
def admin_revert_rubric(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    problem = _admin_problem(db, slug)
    previous = problem.diagnosis_rubric
    if _rubric_source(problem) != "admin":
        raise HTTPException(409, "Only an administrator override can be reverted.")
    extra = dict(problem.extra or {})
    restored = extra.pop("authored_rubric", None)
    problem.rubric_version = (problem.rubric_version or 1) + 1
    problem.diagnosis_rubric = {**restored, "version": problem.rubric_version} if restored else None
    problem.extra = extra or None
    audit(db, admin.id, "rubric.reverted", "problem", problem.id, slug=problem.slug,
          rubric_version=problem.rubric_version, previous_source=_rubric_source_value(previous),
          restored="authored" if restored else "derived")
    db.commit()
    return admin_rubric(slug, admin, db)


@router.patch("/admin/problems/{slug}/diagnosis-mode")
def admin_diagnosis_mode(slug: str, data: DiagnosisModeUpdate, admin: User = Depends(require_admin),
                         db: Session = Depends(get_db)):
    problem = _admin_problem(db, slug)
    previous = problem.diagnosis_mode
    problem.diagnosis_mode = data.mode
    audit(db, admin.id, "diagnosis_mode.updated", "problem", problem.id, slug=problem.slug,
          previous=previous, mode=data.mode)
    db.commit()
    return {"slug": problem.slug, "diagnosis_mode": problem.diagnosis_mode}
