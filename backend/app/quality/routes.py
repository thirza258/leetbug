"""Administrator API for problem quality, publication, operations and calibration.

Every route requires the administrator account. Hidden test names and mutant source appear only
here, never in user-facing responses.
"""
import json
import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.catalog import case as test_case
from app.db import get_db
from app.events import audit
from app.limits import rate_limit
from app.models import MutationCase, MutationRun, Problem, ProblemSubmission, QualityGate, User, now
from app.quality import calibration as calibration_module
from app.quality import gates, metrics, pipeline
from app.quality.mutation import OPERATOR_LABELS, OPERATORS
from app.quality.tasks import quality_run
from app.schemas import Language

router = APIRouter(prefix="/api", tags=["quality"])
ACTIVE_RUN = ("queued", "validating", "running")
DRAFT_ID_START = 200001


class RunCreate(BaseModel):
    language: Language | None = None
    max_mutants: int = Field(default=24, ge=1, le=60)
    operators: list[str] | None = Field(default=None, max_length=len(OPERATORS))


class CaseUpdate(BaseModel):
    is_equivalent: bool
    note: str = Field(default="", max_length=500)


class GateUpdate(BaseModel):
    thresholds: dict


def _problem(db, slug: str) -> Problem:
    problem = db.scalar(select(Problem).where(Problem.slug == slug))
    if problem is None:
        raise HTTPException(404, "Problem not found.")
    return problem


def run_view(run: MutationRun, problem: Problem | None = None, *, include_report: bool = True) -> dict:
    view = {key: getattr(run, key) for key in (
        "id", "problem_id", "problem_version", "content_hash", "language", "status", "config", "total_mutations",
        "killed_mutations", "survived_mutations", "timed_out_mutations", "invalid_mutations", "equivalent_mutations",
        "error_mutations", "mutation_score", "gate_status", "error", "requested_by", "created_at", "started_at",
        "completed_at")}
    if problem is not None:
        view |= {"problem_slug": problem.slug, "problem_title": problem.title, "current_version": problem.version}
    if include_report:
        view["report"] = run.report or {}
        view["pipeline"] = (run.report or {}).get("pipeline") or [
            step for step in ((run.execution_metadata or {}).get("steps") or {}).values()]
    return view


def case_view(case: MutationCase, *, include_code: bool = False) -> dict:
    view = {key: getattr(case, key) for key in (
        "id", "run_id", "ordinal", "operator", "description", "line", "critical", "original_snippet",
        "mutated_snippet", "status", "failure_classification", "killing_tests", "is_equivalent", "attempts",
        "execution_duration_ms", "created_at", "completed_at")}
    view["operator_label"] = OPERATOR_LABELS.get(case.operator, case.operator)
    view["note"] = (case.detail or {}).get("equivalence_note", "")
    view["message"] = (case.detail or {}).get("message")
    if include_code:
        view["mutated_code"] = case.mutated_code
    return view


def _enqueue_run(db, run: MutationRun) -> None:
    try:
        quality_run.delay(run.id)
    except Exception as exc:
        run.status, run.error, run.completed_at = "failed", "The quality queue is temporarily unavailable.", now()
        db.commit()
        raise HTTPException(503, run.error) from exc


@router.get("/admin/quality/operators")
def operators(admin: User = Depends(require_admin)):
    return {"operators": [{"id": operator, "label": OPERATOR_LABELS[operator]} for operator in OPERATORS]}


@router.post("/admin/problems/{slug}/mutation-runs", status_code=202)
def start_run(slug: str, data: RunCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rate_limit(f"quality:{admin.id}", 20)
    problem = _problem(db, slug)
    language = data.language or next(iter(problem.starters))
    if language not in problem.starters:
        raise HTTPException(422, "That language is not available for this problem.")
    if data.operators and set(data.operators) - set(OPERATORS):
        raise HTTPException(422, "Unknown mutation operators: " + ", ".join(sorted(set(data.operators) - set(OPERATORS))))
    if db.scalar(select(MutationRun.id).where(MutationRun.problem_id == problem.id, MutationRun.language == language,
                                              MutationRun.status.in_(ACTIVE_RUN)).limit(1)):
        raise HTTPException(409, "A quality run for this problem and language is already in progress.")
    run = pipeline.create_run(db, problem, language=language, max_mutants=data.max_mutants,
                              operators=data.operators, requested_by=admin.id)
    audit(db, admin.id, "quality.run_requested", "problem", problem.id, run_id=run.id, language=language,
          max_mutants=data.max_mutants, version=problem.version)
    db.commit()
    _enqueue_run(db, run)
    return run_view(run, problem)


@router.get("/admin/problems/{slug}/mutation-runs")
def list_runs(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    problem = _problem(db, slug)
    runs = db.scalars(select(MutationRun).where(MutationRun.problem_id == problem.id)
                      .order_by(MutationRun.created_at.desc()).limit(50))
    return {"problem": {"id": problem.id, "slug": problem.slug, "title": problem.title, "version": problem.version,
                        "visibility": problem.visibility, "quality_status": problem.quality_status,
                        "languages": list(problem.starters), "source": (problem.extra or {}).get("source", "catalog")},
            "items": [run_view(run, problem, include_report=False) for run in runs]}


@router.get("/admin/problems/{slug}/quality-history")
def quality_history(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """MT-011: quality across problem versions (newest completed run per version and language)."""
    problem = _problem(db, slug)
    runs = list(db.scalars(select(MutationRun).where(MutationRun.problem_id == problem.id,
                                                     MutationRun.status == "completed")
                           .order_by(MutationRun.created_at.desc())))
    latest = {}
    for run in runs:
        latest.setdefault((run.problem_version, run.language), run)
    versions = sorted({version for version, _ in latest}, reverse=True)
    return {"problem_id": problem.id, "slug": problem.slug, "current_version": problem.version,
            "current_hash": pipeline.content_hash(pipeline.definition_from_problem(problem)),
            "versions": [{"version": version, "runs": [
                {"run_id": run.id, "language": language, "mutation_score": run.mutation_score,
                 "gate_status": run.gate_status, "content_hash": run.content_hash, "completed_at": run.completed_at}
                for (run_version, language), run in latest.items() if run_version == version]}
                for version in versions]}


@router.get("/admin/mutation-runs/{run_id}")
def get_run(run_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    run = db.get(MutationRun, run_id)
    if run is None:
        raise HTTPException(404, "Quality run not found.")
    return run_view(run, db.get(Problem, run.problem_id))


@router.get("/admin/mutation-runs/{run_id}/cases")
def run_cases(run_id: str, status: str = "", critical: bool | None = None, operator: str = "",
              include_code: bool = False, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.get(MutationRun, run_id) is None:
        raise HTTPException(404, "Quality run not found.")
    query = select(MutationCase).where(MutationCase.run_id == run_id)
    if status:
        query = query.where(MutationCase.status == status)
    if critical is not None:
        query = query.where(MutationCase.critical.is_(critical))
    if operator:
        query = query.where(MutationCase.operator == operator)
    return {"items": [case_view(case, include_code=include_code)
                      for case in db.scalars(query.order_by(MutationCase.ordinal))]}


@router.patch("/admin/mutation-cases/{case_id}")
def update_case(case_id: str, data: CaseUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Mark or unmark an equivalent mutant; the run's score and gate are recomputed."""
    case = db.get(MutationCase, case_id)
    if case is None:
        raise HTTPException(404, "Mutant not found.")
    run = db.get(MutationRun, case.run_id)
    if case.status in ("queued", "running"):
        raise HTTPException(409, "Wait for this mutant to finish executing.")
    detail = dict(case.detail or {})
    previous = case.status
    if data.is_equivalent and case.status != "equivalent":
        detail["status_before_equivalence"] = case.status
        case.status, case.is_equivalent = "equivalent", True
    elif not data.is_equivalent and case.status == "equivalent":
        case.status = detail.pop("status_before_equivalence", "survived")
        case.is_equivalent = False
    detail["equivalence_note"] = data.note.strip()
    case.detail = detail
    db.flush()
    if run.status == "completed":
        pipeline.finalize_run(db, run)
    audit(db, admin.id, "quality.mutant_equivalence", "mutation_case", case.id, run_id=run.id,
          is_equivalent=data.is_equivalent, previous_status=previous, note=data.note.strip()[:200],
          mutation_score=run.mutation_score, gate_status=run.gate_status)
    db.commit()
    return {"case": case_view(case), "run": run_view(run, db.get(Problem, run.problem_id), include_report=False)}


@router.get("/admin/quality-gates")
def get_gates(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = {row.category: row for row in db.scalars(select(QualityGate))}
    categories = gates.known_categories(db)
    return {"defaults": gates.DEFAULT_THRESHOLDS,
            "schema": {key: {"type": kind.__name__, "min": low, "max": high}
                       for key, (kind, low, high) in gates.THRESHOLD_SCHEMA.items()},
            "overrides": [{"category": row.category, "thresholds": row.thresholds, "updated_at": row.updated_at,
                           "updated_by": row.updated_by} for row in rows.values()],
            "effective": {category: gates.effective_thresholds(db, category) for category in ["default", *categories]},
            "categories": categories}


@router.put("/admin/quality-gates/{category}")
def put_gate(category: str, data: GateUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if category != "default" and category not in gates.known_categories(db):
        raise HTTPException(404, "Unknown problem category.")
    try:
        thresholds = gates.validate_thresholds(data.thresholds)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row = db.get(QualityGate, category)
    before = dict(row.thresholds) if row else None
    if row is None:
        row = QualityGate(category=category, thresholds=thresholds, updated_by=admin.id)
        db.add(row)
    else:
        row.thresholds, row.updated_by, row.updated_at = thresholds, admin.id, now()
    audit(db, admin.id, "quality.gate_updated", "quality_gate", category, before=before, after=thresholds)
    db.commit()
    return {"category": category, "thresholds": row.thresholds, "effective": gates.effective_thresholds(db, category)}


@router.delete("/admin/quality-gates/{category}", status_code=204)
def delete_gate(category: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(QualityGate, category)
    if row is None:
        raise HTTPException(404, "No override exists for this category.")
    audit(db, admin.id, "quality.gate_removed", "quality_gate", category, before=row.thresholds)
    db.delete(row)
    db.commit()


@router.get("/admin/quality/overview")
def overview(q: str = Query("", max_length=100), category: str = "", visibility: str = "",
             gate: Literal["", "approved", "requires_revision", "unvalidated", "stale"] = "",
             page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200),
             admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    query = select(Problem).order_by(Problem.id)
    if category:
        query = query.where(Problem.category == category)
    if visibility:
        query = query.where(Problem.visibility == visibility)
    problems = [problem for problem in db.scalars(query)
                if q.lower() in f"{problem.slug} {problem.title}".lower()]
    latest: dict[int, MutationRun] = {}
    for run in db.scalars(select(MutationRun).order_by(MutationRun.created_at.desc())):
        latest.setdefault(run.problem_id, run)
    rows = []
    for problem in problems:
        run = latest.get(problem.id)
        # Compare with the live content so edits made without a new run are reported as stale.
        stale = bool(run and run.status == "completed" and (
            run.content_hash != pipeline.content_hash(pipeline.definition_from_problem(problem))
            or run.problem_version != problem.version))
        state = "stale" if stale else problem.quality_status
        if gate and state != gate:
            continue
        rows.append({"id": problem.id, "slug": problem.slug, "title": problem.title, "category": problem.category,
                     "difficulty": problem.difficulty, "visibility": problem.visibility, "version": problem.version,
                     "languages": list(problem.starters), "quality_status": problem.quality_status, "stale": stale,
                     "source": (problem.extra or {}).get("source", "catalog"),
                     "latest_run": None if run is None else {
                         "id": run.id, "status": run.status, "language": run.language,
                         "mutation_score": run.mutation_score, "gate_status": run.gate_status,
                         "problem_version": run.problem_version, "created_at": run.created_at,
                         "completed_at": run.completed_at}})
    counts = {"approved": 0, "requires_revision": 0, "unvalidated": 0}
    for problem in db.scalars(select(Problem)):
        counts[problem.quality_status] = counts.get(problem.quality_status, 0) + 1
    published_new = [problem for problem in db.scalars(select(Problem).where(Problem.id >= DRAFT_ID_START,
                                                                             Problem.visibility == "public"))]
    return {"items": rows[(page - 1) * limit:page * limit], "total": len(rows), "page": page, "limit": limit,
            "summary": {**counts, "validated_problems": counts["approved"] + counts["requires_revision"],
                        "published_new": len(published_new),
                        "published_new_approved_rate": pipeline.percent(
                            sum(problem.quality_status == "approved" for problem in published_new), len(published_new))},
            "categories": gates.known_categories(db)}


@router.post("/admin/problems/{slug}/publish")
def publish(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """MT-008 publication gate: only drafts whose current version passed the quality gate."""
    problem = _problem(db, slug)
    if problem.visibility != "draft":
        raise HTTPException(409, "Only draft problems can be published.")
    run = pipeline.latest_valid_run(db, problem)
    if run is None:
        raise HTTPException(409, "Run quality validation on the current version before publishing.")
    if run.gate_status != "approved":
        reasons = (run.report or {}).get("gate", {}).get("reasons", [])
        raise HTTPException(409, "The quality gate requires revision: " + ("; ".join(reasons[:3]) or "see the report."))
    problem.visibility = "public"
    problem.quality_status = "approved"
    audit(db, admin.id, "problem.published", "problem", problem.id, run_id=run.id, version=problem.version,
          mutation_score=run.mutation_score)
    db.commit()
    return {"id": problem.id, "slug": problem.slug, "visibility": problem.visibility, "version": problem.version}


@router.post("/admin/problems/{slug}/unpublish")
def unpublish(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    problem = _problem(db, slug)
    if (problem.extra or {}).get("source") != "community":
        raise HTTPException(409, "Only community-contributed problems can be unpublished here.")
    if problem.visibility != "public":
        raise HTTPException(409, "This problem is not published.")
    problem.visibility = "draft"
    audit(db, admin.id, "problem.unpublished", "problem", problem.id, version=problem.version)
    db.commit()
    return {"id": problem.id, "slug": problem.slug, "visibility": problem.visibility}


def _parse_json(value, *, label: str, require_object: bool):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            if require_object:
                raise HTTPException(422, f"{label} is not valid JSON.") from None
    if require_object and not isinstance(value, dict):
        raise HTTPException(422, f"{label} must be a JSON object.")
    return value


@router.get("/admin/quality/community")
def community(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(ProblemSubmission, User.username).join(User, ProblemSubmission.author_id == User.id)
                      .where(ProblemSubmission.status == "approved").order_by(ProblemSubmission.created_at.desc()))
    items = []
    for submission, username in rows:
        problem = db.get(Problem, submission.problem_id) if submission.problem_id else None
        items.append({"id": submission.id, "title": submission.title, "author_username": username,
                      "language": submission.language, "category": submission.category,
                      "created_at": submission.created_at, "test_case_count": len(submission.test_cases or []),
                      "problem": None if problem is None else {
                          "id": problem.id, "slug": problem.slug, "visibility": problem.visibility,
                          "quality_status": problem.quality_status, "version": problem.version}})
    return {"items": items}


@router.post("/admin/problem-submissions/{submission_id}/draft", status_code=201)
def create_draft(submission_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Turn an approved community submission into a draft problem that must pass the quality gate."""
    submission = db.get(ProblemSubmission, submission_id)
    if submission is None:
        raise HTTPException(404, "Submission not found.")
    if submission.status != "approved":
        raise HTTPException(409, "Approve the submission before creating a draft problem.")
    if submission.problem_id:
        raise HTTPException(409, "A draft problem already exists for this submission.")
    cases = submission.test_cases or []
    if len(cases) < 2:
        raise HTTPException(422, "At least two test cases are needed: one public and one hidden.")
    public_count = max(1, len(cases) // 2)
    tests = []
    for index, raw in enumerate(cases, 1):
        if not isinstance(raw, dict) or "input" not in raw or "expected" not in raw:
            raise HTTPException(422, f"Test case {index} needs an input and an expected value.")
        hidden = index > public_count
        tests.append(test_case(f"Hidden check {index - public_count}" if hidden else f"Example {index}",
                               _parse_json(raw["input"], label=f"Test case {index} input", require_object=True),
                               _parse_json(raw["expected"], label=f"Test case {index} expected", require_object=False),
                               hidden))
    slug = submission.slug
    if db.scalar(select(Problem.id).where(Problem.slug == slug)):
        slug = f"{slug[:90]}-draft"
    hint = submission.hint.strip()
    for _ in range(3):
        next_id = max(DRAFT_ID_START - 1, db.scalar(select(func.max(Problem.id))
                                                    .where(Problem.id >= DRAFT_ID_START)) or 0) + 1
        problem = Problem(
            id=next_id, slug=slug, title=submission.title, summary=submission.summary,
            description=submission.description, category=submission.category, difficulty=submission.difficulty,
            tags=list(submission.tags or []), requirements=[submission.summary],
            starters={submission.language: submission.buggy_code.rstrip() + "\n"},
            solutions={submission.language: submission.fixed_code.rstrip() + "\n"},
            explanation=hint or "Community-contributed problem.", tests=tests, estimated_minutes=15,
            hints=["Reproduce the failing example and compare the actual output with the expected output.",
                   hint or "Find the first operation that produces a value outside the expected behavior.",
                   "Fix the root cause with the smallest change that satisfies every requirement."],
            visibility="draft", diagnosis_mode="optional", quality_status="unvalidated",
            extra={"source": "community", "problem_submission_id": submission.id, "author_id": submission.author_id})
        try:
            with db.begin_nested():
                db.add(problem)
                db.flush()
            break
        except IntegrityError:
            continue
    else:
        raise HTTPException(409, "Could not allocate a problem ID. Please retry.")
    pipeline.sync_version(problem)
    submission.problem_id = problem.id
    audit(db, admin.id, "problem.draft_created", "problem", problem.id, problem_submission_id=submission.id,
          public_tests=public_count, hidden_tests=len(cases) - public_count)
    db.commit()
    return {"id": problem.id, "slug": problem.slug, "title": problem.title, "visibility": problem.visibility,
            "version": problem.version, "languages": list(problem.starters), "tests": len(tests)}


@router.get("/admin/metrics")
def admin_metrics(days: int = Query(7, ge=1, le=90), admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return metrics.admin_metrics(db, days=days)


@router.get("/admin/calibration")
def admin_calibration(min_samples: int = Query(20, ge=5, le=1000), page: int = Query(1, ge=1),
                      limit: int = Query(50, ge=1, le=200), admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    items = calibration_module.calibration(db, min_samples=min_samples)
    return {"items": items[(page - 1) * limit:page * limit], "total": len(items), "page": page, "limit": limit,
            "min_samples": min_samples, "pages": max(1, math.ceil(len(items) / limit)),
            "note": "Suggestions are advisory and require at least the minimum sample size; difficulty is never changed automatically."}
