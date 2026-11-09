"""Shared scoring (PRD 5.3, 5.4, 6.6, 9.5, 10.2).

Every scoring path reads the same stored evidence: diagnoses, explanations, submissions and
attempt timing. Diagnosis, explanation and patch-quality scores are computed when those records
are created (``app.diagnosis``); this module aggregates them per attempt, per user and per
assessment. All scores are on a 0–100 scale.
"""
import math

from sqlalchemy import func, select

from app.models import (
    AIInteraction,
    ChallengeAttempt,
    Diagnosis,
    FixExplanation,
    Hint,
    Problem,
    Submission,
    now,
)

SCORING_VERSION = "scoring-v1"
TERMINAL = {"passed", "failed", "runtime_error", "time_limit", "memory_limit", "output_limit"}

# PRD 5.3 — configurable per rubric (``rubric["weights"]``), difficulty and category.
DIAGNOSIS_WEIGHTS = {"defect_category": 25, "root_cause": 30, "invariant": 20, "correction": 15, "reproduction": 10}
DIAGNOSIS_WEIGHTS_BY_DIFFICULTY = {
    # Hard problems reward the causal explanation over the label.
    "hard": {"defect_category": 20, "root_cause": 35, "invariant": 20, "correction": 15, "reproduction": 10},
}
DIAGNOSIS_PASS_THRESHOLD = 60.0
EXPLANATION_WEIGHTS = {"why_failed": 30, "why_works": 25, "invariant": 20, "side_effects": 10, "additional_tests": 15}
# PRD 10.2. Correctness is a gate, not a weighted dimension: incorrect patches get no quality score.
QUALITY_WEIGHTS = {"minimality": 25, "maintainability": 20, "error_handling": 20, "performance": 10,
                   "concurrency_safety": 10, "regression_risk": 15}
# PRD 6.6
INCIDENT_WEIGHTS = {"root_cause": 25, "investigation": 15, "fix": 25, "regression": 15, "remediation": 10,
                    "communication": 10}
# PRD 9.5
ASSESSMENT_WEIGHTS = {"diagnosis": 25, "correctness": 30, "verification": 15, "quality": 10, "explanation": 10,
                      "time": 10}


def diagnosis_weights(problem, rubric: dict | None = None) -> dict:
    if rubric and rubric.get("weights"):
        return dict(rubric["weights"])
    return dict(DIAGNOSIS_WEIGHTS_BY_DIFFICULTY.get(getattr(problem, "difficulty", ""), DIAGNOSIS_WEIGHTS))


def normalize_weights(weights: dict) -> dict:
    positive = {key: float(value) for key, value in weights.items() if value and float(value) > 0}
    total = sum(positive.values())
    return {key: value / total for key, value in positive.items()} if total else {}


def weighted(components: dict, weights: dict, *, missing: str = "skip") -> float | None:
    """Weighted 0–100 total. ``missing="skip"`` renormalizes over available components;
    ``missing="zero"`` scores an absent component as 0 (assessments)."""
    normalized = normalize_weights(weights)
    if missing == "zero":
        return round(sum(normalized[key] * float(components.get(key) or 0) for key in normalized), 2)
    present = {key: weight for key, weight in normalized.items() if components.get(key) is not None}
    total = sum(present.values())
    if not total:
        return None
    return round(sum(weight / total * float(components[key]) for key, weight in present.items()), 2)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def correctness_from_results(results: list | None) -> float:
    """Share of all graded cases (public and hidden) that passed, 0–100."""
    if not results:
        return 0.0
    passed = sum(1 for row in results if isinstance(row, dict) and row.get("status") == "passed")
    return round(passed / len(results) * 100, 2)


def time_efficiency(seconds: float | None, estimated_minutes: int | None, solved: bool) -> float:
    """Limited-influence speed score. Unsolved work earns nothing for speed (PRD 9.5)."""
    if not solved or seconds is None:
        return 0.0
    budget = max(60.0, float(estimated_minutes or 15) * 60)
    ratio = seconds / budget
    if ratio <= 1:
        return 100.0
    # Linear decline to a floor of 20 at three times the estimate.
    return round(clamp(100 - (ratio - 1) / 2 * 80, 20, 100), 2)


def shrink(mean: float | None, n: int, prior: float = 50.0, k: int = 5) -> float | None:
    """Pull small samples toward a neutral prior so a few attempts never look definitive (PRD 5.4)."""
    if mean is None:
        return None
    return round((n * mean + k * prior) / (n + k), 2)


def confidence(n: int) -> str:
    if n < 3:
        return "insufficient"
    if n < 10:
        return "low"
    if n < 25:
        return "moderate"
    return "high"


def _utc(value):
    return value.replace(tzinfo=now().tzinfo) if value is not None and value.tzinfo is None else value


def attempt_evidence(db, attempt: ChallengeAttempt) -> dict:
    """Behavioral evidence for one attempt: counts, timing, and the records that scores use."""
    rows = list(db.scalars(select(Submission).where(Submission.attempt_id == attempt.id)
                           .order_by(Submission.created_at)))
    submits = [row for row in rows if row.kind == "submit" and row.status in TERMINAL]
    runs = [row for row in rows if row.kind == "run" and row.status in TERMINAL]
    passed = [row for row in submits if row.status == "passed"]
    first_pass = passed[0] if passed else None
    failed_before_pass = sum(1 for row in submits
                             if row.status != "passed" and (first_pass is None or row.created_at <= first_pass.created_at))
    diagnoses = list(db.scalars(select(Diagnosis).where(Diagnosis.attempt_id == attempt.id)
                                .order_by(Diagnosis.created_at)))
    solved_at = _utc(attempt.solved_at)
    scored_diagnosis = None
    for row in diagnoses:
        if solved_at is None or _utc(row.created_at) <= solved_at:
            scored_diagnosis = row
    if scored_diagnosis is None and diagnoses:
        scored_diagnosis = diagnoses[-1]
    explanation = db.scalar(select(FixExplanation).where(FixExplanation.attempt_id == attempt.id)
                            .order_by(FixExplanation.created_at.desc()).limit(1))
    hints = db.scalar(select(func.count()).select_from(Hint).where(Hint.attempt_id == attempt.id)) or 0
    ai_interactions = db.scalar(select(func.count()).select_from(AIInteraction)
                                .where(AIInteraction.attempt_id == attempt.id)) or 0
    first_submit = submits[0] if submits else None
    ran_before_submit = bool(runs and (first_submit is None or runs[0].created_at <= first_submit.created_at))
    end = solved_at or _utc(attempt.last_activity_at) or now()
    seconds = max(0.0, (end - _utc(attempt.started_at)).total_seconds())
    # Diagnosis revisions and failed submissions before the diagnosis first reached the pass mark.
    attempts_to_cause = None
    for index, row in enumerate(diagnoses):
        if (row.score or 0) >= DIAGNOSIS_PASS_THRESHOLD:
            failed_earlier = sum(1 for sub in submits if sub.status != "passed" and sub.created_at <= row.created_at)
            attempts_to_cause = index + failed_earlier
            break
    return {
        "submissions": len(submits), "runs": len(runs), "passed_submissions": len(passed),
        "failed_before_pass": failed_before_pass, "ran_before_submit": ran_before_submit,
        "hints": hints, "ai_interactions": ai_interactions,
        "ai_submissions": sum(1 for row in rows if row.mode == "ai"),
        "diagnosis_revisions": len(diagnoses), "attempts_to_cause": attempts_to_cause,
        "time_spent_seconds": round(seconds, 1), "solved": bool(passed),
        "best_submission": first_pass or max(submits, key=lambda row: correctness_from_results(row.results), default=None),
        "diagnosis": scored_diagnosis, "explanation": explanation,
        "failed_statuses": sorted({row.status for row in submits if row.status != "passed"}),
    }


def criterion(record, name: str) -> float | None:
    """A 0–1 criterion score from a diagnosis/explanation ``evaluation_details``."""
    if record is None:
        return None
    value = (record.evaluation_details or {}).get("criteria", {}).get(name, {})
    score = value.get("score") if isinstance(value, dict) else None
    return float(score) if isinstance(score, (int, float)) else None


def verification_from(evidence: dict) -> float | None:
    parts = {
        "reproduction": criterion(evidence["diagnosis"], "reproduction"),
        "ran_before_submit": 1.0 if evidence["ran_before_submit"] else 0.0 if evidence["submissions"] else None,
        "additional_tests": criterion(evidence["explanation"], "additional_tests"),
        "focus": (1 / (1 + 0.5 * max(0, evidence["failed_before_pass"] - 1))) if evidence["submissions"] else None,
    }
    weights = {"reproduction": 35, "ran_before_submit": 25, "additional_tests": 25, "focus": 15}
    return weighted({key: None if value is None else value * 100 for key, value in parts.items()}, weights)


def refresh_attempt(db, attempt: ChallengeAttempt, *, weights: dict | None = None,
                    missing: str = "skip") -> dict:
    """Recompute and persist an attempt's dimension scores from stored evidence (idempotent)."""
    problem = db.get(Problem, attempt.problem_id)
    evidence = attempt_evidence(db, attempt)
    best = evidence["best_submission"]
    solved = evidence["solved"]
    diagnosis, explanation = evidence["diagnosis"], evidence["explanation"]
    components = {
        "diagnosis": diagnosis.score if diagnosis is not None else None,
        "correctness": 100.0 if solved else (correctness_from_results(best.results) if best else None),
        "verification": verification_from(evidence),
        "quality": (best.quality or {}).get("score") if solved and best is not None and best.quality else None,
        "explanation": explanation.score if explanation is not None else None,
        "time": time_efficiency(evidence["time_spent_seconds"], problem.estimated_minutes if problem else None, solved)
        if evidence["submissions"] else None,
    }
    total = weighted(components, weights or ASSESSMENT_WEIGHTS, missing=missing)
    attempt.diagnosis_score = components["diagnosis"]
    attempt.correctness_score = components["correctness"]
    attempt.verification_score = components["verification"]
    attempt.quality_score = components["quality"]
    attempt.explanation_score = components["explanation"]
    attempt.time_score = components["time"]
    attempt.total_score = total
    if solved and attempt.solved_at is None:
        attempt.solved_at = best.completed_at or best.created_at
    if attempt.status not in {"expired"}:
        attempt.status = "completed" if solved and explanation is not None else "solved" if solved else "in_progress"
        if attempt.status == "completed" and attempt.completed_at is None:
            attempt.completed_at = now()
    public_evidence = {key: value for key, value in evidence.items()
                       if key not in {"best_submission", "diagnosis", "explanation"}}
    breakdown = {
        "components": components, "total": total, "evidence": public_evidence,
        "best_submission_id": best.id if best is not None else None,
        "diagnosis_id": diagnosis.id if diagnosis is not None else None,
        "explanation_id": explanation.id if explanation is not None else None,
        "versions": {
            "scoring": SCORING_VERSION,
            "diagnosis_rubric": diagnosis.rubric_version if diagnosis is not None else None,
            "diagnosis_evaluator": diagnosis.evaluator_version if diagnosis is not None else None,
            "explanation_evaluator": explanation.evaluator_version if explanation is not None else None,
            "quality": (best.quality or {}).get("version") if best is not None and best.quality else None,
        },
    }
    attempt.scores = breakdown
    return breakdown


def mean(values) -> float | None:
    values = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    return round(sum(values) / len(values), 2) if values else None
