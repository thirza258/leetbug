"""Diagnosis and explanation records (PRD 5.2 Stages B and E; DR-001..DR-006).

Other features call these functions (incidents, assessments). They resolve the challenge attempt,
score deterministically, queue the optional AI evaluation after the caller commits, and refresh
the attempt's cached scores. They flush but never commit.
"""
import logging

from fastapi import HTTPException
from sqlalchemy import event, func, select

from app import attempts, scoring, taxonomy
from app.config import settings
from app.diagnosis.rubric import rubric_for
from app.diagnosis.scorer import (
    DIAGNOSIS_FIELDS,
    EVALUATOR_VERSION,
    EXPLANATION_FIELDS,
    note_text,
    score_diagnosis,
    score_explanation,
)
from app.events import record_event
from app.models import AssessmentSession, Diagnosis, FixExplanation, Submission, now

log = logging.getLogger(__name__)

FIELD_LIMITS = {"root_cause": 4000, "affected_component": 1000, "violated_invariant": 2000,
                "proposed_correction": 4000, "reproduction_strategy": 4000, "why_failed": 4000,
                "why_works": 4000, "invariant_preserved": 2000, "side_effects": 2000, "additional_tests": 4000}
OPTIONAL_EXPLANATION_FIELDS = {"side_effects", "additional_tests"}
STALE_AI_SECONDS = 600


def _clean_text(fields: dict, names: tuple[str, ...], optional: set[str] = frozenset()) -> dict:
    cleaned = {}
    for name in names:
        value = fields.get(name)
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise HTTPException(422, f"{name}: expected text.")
        value = value.strip()
        if not value and name not in optional:
            raise HTTPException(422, f"{name}: this field is required.")
        if len(value) > FIELD_LIMITS.get(name, 4000):
            raise HTTPException(422, f"{name}: at most {FIELD_LIMITS.get(name, 4000)} characters.")
        cleaned[name] = value
    return cleaned


def validate_diagnosis_fields(fields: dict) -> dict:
    category = fields.get("defect_category")
    if not isinstance(category, str) or category not in taxonomy.BUG_CATEGORIES:
        raise HTTPException(422, "defect_category: choose a category from the taxonomy.")
    cleaned = _clean_text(fields, DIAGNOSIS_FIELDS[1:])
    cleaned["defect_category"] = category
    language = fields.get("language")
    cleaned["language"] = language if language in {"python", "java", "javascript", "cpp", "go"} else None
    return cleaned


def validate_explanation_fields(fields: dict) -> dict:
    return _clean_text(fields, EXPLANATION_FIELDS, OPTIONAL_EXPLANATION_FIELDS)


def _enqueue_after_commit(db, task, record_id: str) -> None:
    """Queue background work only once the record is committed, so the worker can read it."""
    def send(_session):
        try:
            task.delay(record_id)
        except Exception:
            log.warning("Could not queue AI evaluation for %s", record_id, exc_info=True)
    event.listen(db, "after_commit", send, once=True)


def _session_finalized(db, assessment_session_id) -> bool:
    if not assessment_session_id:
        return False
    session = db.get(AssessmentSession, assessment_session_id)
    return bool(session and session.finalized_at is not None)


def refresh_scores(db, attempt) -> None:
    """Refresh cached attempt scores unless the attempt belongs to a finalized assessment."""
    if attempt is not None and not _session_finalized(db, attempt.assessment_session_id):
        scoring.refresh_attempt(db, attempt)


def create_diagnosis(db, user, problem, fields, *, assessment_session_id=None, incident_session_id=None):
    context = attempts.resolve_context(db, user, problem, assessment_session_id=assessment_session_id,
                                       incident_session_id=incident_session_id)
    if problem.diagnosis_mode == "off" and not attempts.diagnosis_required(problem, context):
        raise HTTPException(409, "Diagnosis is not enabled for this case study.")
    data = validate_diagnosis_fields(fields)
    rubric = rubric_for(problem)
    result = score_diagnosis(problem, data, rubric)
    attempt = context.attempt
    revision = (db.scalar(select(func.count()).select_from(Diagnosis).where(Diagnosis.attempt_id == attempt.id)) or 0) + 1
    ai = settings.ai_enabled
    row = Diagnosis(
        user_id=user.id, problem_id=problem.id, attempt_id=attempt.id,
        assessment_session_id=context.assessment_session.id if context.assessment_session else None,
        revision=revision, language=data["language"], defect_category=data["defect_category"],
        root_cause=data["root_cause"], affected_component=data["affected_component"],
        violated_invariant=data["violated_invariant"], proposed_correction=data["proposed_correction"],
        reproduction_strategy=data["reproduction_strategy"], score=result["score"],
        deterministic_score=result["score"], evaluation_details=_details(result),
        rubric_version=rubric.get("version", problem.rubric_version), evaluator_version=EVALUATOR_VERSION,
        ai_status="queued" if ai else "skipped")
    db.add(row)
    db.flush()
    record_event(db, "diagnosis.submitted", user_id=user.id, problem_id=problem.id, attempt_id=attempt.id,
                 assessment_session_id=row.assessment_session_id,
                 incident_session_id=context.incident_session.id if context.incident_session else None,
                 diagnosis_id=row.id, revision=revision, score=row.score, defect_category=row.defect_category)
    refresh_scores(db, attempt)
    if ai:
        from app.diagnosis.tasks import evaluate_diagnosis_ai
        _enqueue_after_commit(db, evaluate_diagnosis_ai, row.id)
    return row


def create_explanation(db, user, problem, fields, *, submission_id=None, assessment_session_id=None,
                       incident_session_id=None):
    context = attempts.resolve_context(db, user, problem, assessment_session_id=assessment_session_id,
                                       incident_session_id=incident_session_id)
    attempt = context.attempt
    data = validate_explanation_fields(fields)
    if submission_id:
        submission = db.get(Submission, submission_id)
        if submission is None or submission.user_id != user.id or submission.attempt_id != attempt.id:
            raise HTTPException(404, "Submission not found.")
        if submission.kind != "submit" or submission.status != "passed":
            raise HTTPException(409, "Explain your fix after a full submission passes all tests.")
    else:
        submission = db.scalar(select(Submission).where(
            Submission.attempt_id == attempt.id, Submission.kind == "submit", Submission.status == "passed")
            .order_by(Submission.created_at.desc()).limit(1))
        if submission is None:
            raise HTTPException(409, "Explain your fix after a full submission passes all tests.")
    rubric = rubric_for(problem)
    result = score_explanation(problem, data, rubric)
    ai = settings.ai_enabled
    row = FixExplanation(
        user_id=user.id, problem_id=problem.id, attempt_id=attempt.id, submission_id=submission.id,
        why_failed=data["why_failed"], why_works=data["why_works"], invariant_preserved=data["invariant_preserved"],
        side_effects=data["side_effects"], additional_tests=data["additional_tests"], score=result["score"],
        deterministic_score=result["score"], evaluation_details=_details(result),
        rubric_version=rubric.get("version", problem.rubric_version), evaluator_version=EVALUATOR_VERSION,
        ai_status="queued" if ai else "skipped")
    db.add(row)
    db.flush()
    record_event(db, "explanation.submitted", user_id=user.id, problem_id=problem.id, attempt_id=attempt.id,
                 assessment_session_id=attempt.assessment_session_id, explanation_id=row.id, score=row.score)
    refresh_scores(db, attempt)
    if ai:
        from app.diagnosis.tasks import evaluate_explanation_ai
        _enqueue_after_commit(db, evaluate_explanation_ai, row.id)
    return row


def _details(result: dict) -> dict:
    return {"criteria": result["criteria"], "weights": result["weights"], "notes": result["notes"],
            "evidence": result["evidence"], "rubric_source": result["rubric_source"],
            "deterministic": {name: value["score"] for name, value in result["criteria"].items()}}


def _ai_status(row) -> str:
    status = row.ai_status
    updated = row.updated_at or row.created_at
    if status in {"queued", "running"} and updated is not None:
        updated = updated.replace(tzinfo=now().tzinfo) if updated.tzinfo is None else updated
        if (now() - updated).total_seconds() > STALE_AI_SECONDS:
            return "failed"
    return status


def _criteria_view(details: dict) -> dict:
    weights = scoring.normalize_weights(details.get("weights") or {})
    return {name: {"score": value.get("score"), "level": value.get("level"), "feedback": value.get("feedback"),
                   "weight": round(weights.get(name, 0) * 100, 1)}
            for name, value in (details.get("criteria") or {}).items()}


def diagnosis_view(row, *, admin: bool = False) -> dict:
    """API view. Never includes rubric concepts or reference material; ``admin`` adds match evidence."""
    details = row.evaluation_details or {}
    category = taxonomy.BUG_CATEGORIES.get(row.defect_category, {})
    view = {
        "id": row.id, "problem_id": row.problem_id, "attempt_id": row.attempt_id,
        "assessment_session_id": row.assessment_session_id, "revision": row.revision, "language": row.language,
        "defect_category": row.defect_category, "defect_category_name": category.get("name", row.defect_category),
        "root_cause": row.root_cause, "affected_component": row.affected_component,
        "violated_invariant": row.violated_invariant, "proposed_correction": row.proposed_correction,
        "reproduction_strategy": row.reproduction_strategy, "score": row.score,
        "deterministic_score": row.deterministic_score, "ai_score": row.ai_score,
        "passed": row.score is not None and row.score >= scoring.DIAGNOSIS_PASS_THRESHOLD,
        "pass_threshold": scoring.DIAGNOSIS_PASS_THRESHOLD,
        "criteria": _criteria_view(details), "notes": [note_text(code) for code in details.get("notes", []) if note_text(code)],
        "rubric_version": row.rubric_version, "evaluator_version": row.evaluator_version,
        "ai_status": _ai_status(row), "created_at": row.created_at, "updated_at": row.updated_at,
    }
    if admin:
        view["evidence"] = details.get("evidence", {})
        view["rubric_source"] = details.get("rubric_source")
        view["ai"] = details.get("ai")
    return view


def explanation_view(row, *, admin: bool = False) -> dict:
    details = row.evaluation_details or {}
    view = {
        "id": row.id, "problem_id": row.problem_id, "attempt_id": row.attempt_id, "submission_id": row.submission_id,
        "why_failed": row.why_failed, "why_works": row.why_works, "invariant_preserved": row.invariant_preserved,
        "side_effects": row.side_effects, "additional_tests": row.additional_tests, "score": row.score,
        "deterministic_score": row.deterministic_score, "ai_score": row.ai_score,
        "criteria": _criteria_view(details), "notes": [note_text(code) for code in details.get("notes", []) if note_text(code)],
        "rubric_version": row.rubric_version, "evaluator_version": row.evaluator_version,
        "ai_status": _ai_status(row), "created_at": row.created_at,
    }
    if admin:
        view["evidence"] = details.get("evidence", {})
        view["ai"] = details.get("ai")
    return view


def attempt_scores_view(attempt) -> dict | None:
    if attempt is None:
        return None
    breakdown = attempt.scores or {}
    return {
        "attempt_id": attempt.id, "context": attempt.context, "status": attempt.status,
        "diagnosis": attempt.diagnosis_score, "correctness": attempt.correctness_score,
        "quality": attempt.quality_score, "explanation": attempt.explanation_score,
        "verification": attempt.verification_score, "time": attempt.time_score, "total": attempt.total_score,
        # Behavioral counts (submissions, runs, hints, time); no grading material.
        "activity": breakdown.get("evidence", {}), "versions": breakdown.get("versions", {}),
        "solved_at": attempt.solved_at, "started_at": attempt.started_at,
    }
