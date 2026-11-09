"""Publication quality gates (PRD 7.6; MT-008).

Thresholds come from code defaults, overridden by the ``default`` QualityGate row, overridden by a
row for the problem's category. The mutation score is one check among several, never the only one.
"""
from sqlalchemy import select

from app.config import settings
from app.models import Problem, QualityGate

KNOWN_CATEGORIES = ["runtime", "logic", "business", "edge", "system_design", "data_science", "data_analytics"]

DEFAULT_THRESHOLDS = {
    "min_mutation_score": 80.0,
    "min_critical_kill_percent": 100.0,
    "min_scored_mutants": 1,
    "require_reference_pass": True,
    "require_starter_failure": True,
    "min_hidden_tests": 1,
    "require_meaningful_hidden_test": True,
    "require_stability": True,
    "stability_runs": 2,
    "require_resource_headroom": True,
    "max_case_runtime_ms": 1500,
    "require_no_leakage": True,
    "count_timeouts_as_killed": True,
}
# key -> (type, minimum, maximum); booleans have no range.
THRESHOLD_SCHEMA = {
    "min_mutation_score": (float, 0, 100), "min_critical_kill_percent": (float, 0, 100),
    "min_scored_mutants": (int, 0, 60), "require_reference_pass": (bool, None, None),
    "require_starter_failure": (bool, None, None), "min_hidden_tests": (int, 0, 50),
    "require_meaningful_hidden_test": (bool, None, None), "require_stability": (bool, None, None),
    "stability_runs": (int, 1, 5), "require_resource_headroom": (bool, None, None),
    "max_case_runtime_ms": (int, 100, 2000), "require_no_leakage": (bool, None, None),
    "count_timeouts_as_killed": (bool, None, None),
}


def validate_thresholds(values: dict) -> dict:
    """Return a normalized copy or raise ValueError naming the first invalid entry."""
    if not isinstance(values, dict):
        raise ValueError("Thresholds must be an object.")
    clean = {}
    for key, value in values.items():
        if key not in THRESHOLD_SCHEMA:
            raise ValueError(f"Unknown threshold: {key}")
        kind, low, high = THRESHOLD_SCHEMA[key]
        if kind is bool:
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be true or false.")
            clean[key] = value
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a number.")
        if kind is int and float(value) != int(value):
            raise ValueError(f"{key} must be a whole number.")
        if not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}.")
        clean[key] = kind(value)
    return clean


def known_categories(db) -> list[str]:
    stored = set(db.scalars(select(Problem.category).distinct()))
    return sorted(set(KNOWN_CATEGORIES) | stored)


def effective_thresholds(db, category: str | None) -> dict:
    thresholds = dict(DEFAULT_THRESHOLDS)
    for key in ("default", category):
        if not key:
            continue
        row = db.get(QualityGate, key)
        if row is not None and isinstance(row.thresholds, dict):
            try:
                thresholds.update(validate_thresholds(row.thresholds))
            except ValueError:
                # A stored row that predates a schema change keeps the safer defaults.
                continue
    return thresholds


def sandbox_limits() -> dict:
    return {"memory_mb": settings.sandbox_memory_mb, "timeout_seconds": settings.sandbox_timeout_seconds,
            "per_case_deadline_ms": 2000}


def _check(name: str, passed: bool, detail: str, required: bool = True) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail, "required": required}


def evaluate(parts: dict, thresholds: dict) -> dict:
    """Decide approved / requires_revision. ``parts`` holds the pipeline evidence:

    schema, starter, reference, hidden, leakage (pipeline step dicts), summary (mutation summary),
    meaningful_hidden (list of test names).
    """
    checks = []
    schema = parts.get("schema") or {}
    checks.append(_check("schema", schema.get("status") == "passed",
                         "Problem definition is complete and executable." if schema.get("status") == "passed"
                         else "; ".join((schema.get("data") or {}).get("errors", [])) or "Schema validation failed."))
    reference = (parts.get("reference") or {}).get("data") or {}
    if thresholds["require_reference_pass"]:
        checks.append(_check("reference_solution", reference.get("passed", False),
                             "Reference solution passes every test." if reference.get("passed")
                             else "The reference solution does not pass every required test."))
    starter = parts.get("starter") or {}
    if thresholds["require_starter_failure"]:
        checks.append(_check("starter_failure", starter.get("status") == "passed",
                             starter.get("detail") or "The buggy starter must fail a public test."))
    if thresholds["require_stability"]:
        runs = len(reference.get("runs", []))
        stable = reference.get("stable", False) and runs >= thresholds["stability_runs"]
        checks.append(_check("execution_stability", stable,
                             f"Reference produced identical results in {runs} runs." if stable
                             else f"Reference results were not stable across {thresholds['stability_runs']} runs."))
    hidden = (parts.get("hidden") or {}).get("data") or {}
    hidden_ok = hidden.get("hidden", 0) >= thresholds["min_hidden_tests"] and (parts.get("hidden") or {}).get(
        "status") in ("passed", "warning")
    checks.append(_check("hidden_tests", hidden_ok,
                         f"{hidden.get('hidden', 0)} hidden tests with distinct inputs." if hidden_ok
                         else (parts.get("hidden") or {}).get("detail") or "Hidden tests are missing or redundant."))
    meaningful = parts.get("meaningful_hidden") or []
    if thresholds["require_meaningful_hidden_test"]:
        checks.append(_check("meaningful_hidden_test", bool(meaningful),
                             f"Hidden tests that catch defects public tests miss: {', '.join(meaningful[:5])}."
                             if meaningful else "No hidden test detects a defect that the public tests miss."))
    summary = parts.get("summary") or {}
    score, scored = summary.get("score"), summary.get("scored", 0)
    score_ok = score is not None and scored >= thresholds["min_scored_mutants"] and score >= thresholds["min_mutation_score"]
    checks.append(_check("mutation_score", score_ok,
                         f"Mutation score {score}% over {scored} scorable mutants (minimum {thresholds['min_mutation_score']}%)."
                         if score is not None else "No scorable mutants: the mutation score is unavailable."))
    critical_total, critical_killed = summary.get("critical_scored", 0), summary.get("critical_killed", 0)
    critical_percent = critical_killed / critical_total * 100 if critical_total else None
    checks.append(_check(
        "critical_mutants", critical_percent is None or critical_percent >= thresholds["min_critical_kill_percent"],
        "No critical mutants were generated." if critical_percent is None
        else f"{critical_killed}/{critical_total} critical mutants killed "
             f"(minimum {thresholds['min_critical_kill_percent']}%)."))
    if thresholds["require_resource_headroom"]:
        limits = sandbox_limits()
        slowest = reference.get("max_case_runtime_ms")
        defined = limits["memory_mb"] > 0 and limits["timeout_seconds"] > 0
        headroom = slowest is not None and slowest <= thresholds["max_case_runtime_ms"]
        checks.append(_check("resource_limits", defined and headroom,
                             f"Sandbox limits {limits['memory_mb']} MB / {limits['timeout_seconds']} s; slowest reference "
                             f"case {slowest} ms (maximum {thresholds['max_case_runtime_ms']} ms)."))
    if thresholds["require_no_leakage"]:
        leakage = parts.get("leakage") or {}
        errors = [item for item in (leakage.get("data") or {}).get("findings", []) if item.get("severity") == "error"]
        checks.append(_check("solution_leakage", not errors,
                             "No hidden tests or reference answers are exposed." if not errors
                             else f"{len(errors)} exposure(s): " + "; ".join(
                                 f"{item['kind']} in {item['source']}" for item in errors[:4])))
    failed = [check for check in checks if check["required"] and not check["passed"]]
    return {"status": "requires_revision" if failed else "approved",
            "reasons": [check["detail"] for check in failed], "checks": checks, "thresholds": thresholds}
