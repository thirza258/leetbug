"""Automated problem validation pipeline (PRD 7.2, 7.5, 7.7; MT-002..MT-007, MT-011).

Schema validation -> starter failure verification -> reference verification (repeated for
stability) -> hidden test validation -> mutation generation -> mutation execution -> quality report
-> quality gate.

The pure functions here work on a plain problem *definition* dict, so the same code serves the
Celery tasks (database-backed runs), the CLI (in-memory, optionally without a database), and tests.
Every program runs through ``app.execution.execute_code`` — the isolated sandbox used for user
submissions — and is graded by ``app.execution.grade``; expectations never enter the container.
"""
import json
import logging
import math
import time
from collections import Counter
from textwrap import dedent

from sqlalchemy import select

from app import execution, taxonomy
from app.execution import SandboxUnavailable
from app.models import MutationCase, MutationRun, Problem, now
from app.quality import gates
from app.quality.mutation import (
    MUTATION_VERSION,
    OPERATORS,
    SYNTAX_MARKERS,
    generate,
    sha256,
)

log = logging.getLogger(__name__)
PIPELINE_VERSION = "quality-pipeline-v1"
STEP_NAMES = ["schema_validation", "starter_failure", "reference_verification", "hidden_test_validation",
              "solution_leakage", "mutation_generation", "mutation_execution", "quality_report", "quality_gate"]
TERMINAL_CASE = {"killed", "survived", "timeout", "invalid", "equivalent", "error"}
PENDING_CASE = {"queued", "running"}
MAX_EXECUTION_ATTEMPTS = 3
PAYLOAD_LIMIT = 240_000  # the sandbox harness reads at most 256,000 bytes of request JSON
EDGE_INDICATORS = ["empty_collection", "zero", "negative_number", "large_number", "duplicate_values",
                   "non_ascii_text", "null_value", "boolean_value", "single_element", "nested_structure"]


# ── Definitions ─────────────────────────────────────────────────────────────────────────────

def _code(source: str) -> str:
    return dedent(source).strip() + "\n"


def definition_from_problem(problem) -> dict:
    return {key: getattr(problem, key) for key in (
        "slug", "title", "summary", "description", "category", "difficulty", "tags", "requirements",
        "starters", "solutions", "tests", "explanation", "hints")} | {
        "id": getattr(problem, "id", None), "taxonomy": getattr(problem, "taxonomy", None)}


def definition_from_catalog(item: dict) -> dict:
    """A catalog or incident problem definition, normalized like the seeded database row."""
    return {
        "id": None, "slug": item["slug"], "title": item["title"], "summary": item.get("summary", ""),
        "description": item.get("description", item.get("summary", "")), "category": item.get("category", ""),
        "difficulty": item.get("difficulty", ""), "tags": list(item.get("tags", [])),
        "requirements": list(item.get("requirements", [])), "explanation": item.get("explanation", ""),
        "hints": list(item.get("hints", [])), "taxonomy": item.get("taxonomy"),
        "starters": {key: _code(value) for key, value in item["starters"].items()},
        "solutions": {key: _code(value) for key, value in item["solutions"].items()},
        "tests": item["tests"],
    }


def content_hash(definition: dict) -> str:
    canonical = json.dumps({key: definition[key] for key in ("starters", "solutions", "tests")},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return sha256(canonical)


def sync_version(problem) -> bool:
    """MT-011: store the content hash; bump the problem version when the content changed."""
    current = content_hash(definition_from_problem(problem))
    if problem.content_hash is None:
        problem.content_hash = current
        return False
    if problem.content_hash != current:
        problem.version = (problem.version or 1) + 1
        problem.content_hash = current
        return True
    return False


def default_executor(language, code, tests):
    # Resolved at call time so tests can substitute ``app.execution.execute_code``.
    return execution.execute_code(language, code, tests)


def _step(name: str, status: str, detail: str, /, **data) -> dict:
    return {"step": name, "status": status, "detail": detail, "data": data}


# ── Grading helpers ─────────────────────────────────────────────────────────────────────────

def grade_output(tests: list, output: dict) -> dict:
    """Grade one execution. A compile or syntax error means the program never ran."""
    if output.get("compile_error"):
        return {"compiled": False, "status": "compile_error", "per_test": [],
                "message": str(output["compile_error"])[:1000], "case_runtimes": []}
    raw = output.get("results") or []
    if raw and len(raw) == len(tests) and all(
            isinstance(row, dict) and row.get("status") == "runtime_error"
            and any(marker in str(row.get("stderr", "")) for marker in SYNTAX_MARKERS) for row in raw):
        return {"compiled": False, "status": "syntax_error", "per_test": [],
                "message": str(raw[0].get("stderr", ""))[:1000], "case_runtimes": []}
    status, results = execution.grade(tests, output)
    per_test = [row.get("status") for row in results] if len(results) == len(tests) else []
    runtimes = [row.get("runtime_ms") for row in raw if isinstance(row, dict) and isinstance(row.get("runtime_ms"), (int, float))]
    return {"compiled": True, "status": status, "per_test": per_test, "message": None,
            "case_runtimes": runtimes, "runtime_ms": output.get("runtime_ms")}


def classify_outcome(tests: list, output: dict) -> dict:
    """Classify one mutant execution (PRD 7.4). Infrastructure failures raise before reaching here."""
    graded = grade_output(tests, output)
    if not graded["compiled"]:
        return {"status": "invalid", "failure_classification": graded["status"], "killing_tests": [],
                "per_test": [], "message": graded["message"]}
    per_test = graded["per_test"]
    failing = [{"name": test["name"], "hidden": bool(test["hidden"]), "status": status}
               for test, status in zip(tests, per_test, strict=False) if status != "passed"]
    status = graded["status"]
    if status == "passed":
        outcome, classification = "survived", None
    elif status == "time_limit":
        outcome, classification = "timeout", "time_limit"
    elif status == "failed":
        outcome, classification = "killed", "assertion"
    elif status in ("memory_limit", "output_limit"):
        outcome, classification = "killed", "resource_limit"
    else:
        outcome, classification = "killed", "runtime_error"
    return {"status": outcome, "failure_classification": classification, "killing_tests": failing,
            "per_test": per_test, "message": None}


# ── Pipeline steps ──────────────────────────────────────────────────────────────────────────

def validate_schema(definition: dict, language: str) -> dict:
    errors, warnings = [], []
    starters, solutions, tests = definition.get("starters") or {}, definition.get("solutions") or {}, definition.get("tests") or []
    if language not in starters:
        errors.append(f"No {language} starter.")
    if language not in solutions:
        errors.append(f"No {language} reference solution.")
    if set(starters) != set(solutions):
        errors.append("Starter and reference languages differ.")
    if language in starters and language in solutions and starters[language] == solutions[language]:
        errors.append("The starter is identical to the reference solution.")
    if not isinstance(tests, list) or not tests:
        errors.append("The problem has no tests.")
        tests = []
    names = [test.get("name") for test in tests if isinstance(test, dict)]
    if len(names) != len(set(names)):
        errors.append("Test names are not unique.")
    for index, test in enumerate(tests, 1):
        if not isinstance(test, dict) or not {"name", "input", "expected", "hidden"} <= set(test):
            errors.append(f"Test {index} is missing name, input, expected or hidden.")
            continue
        if not isinstance(test["input"], dict):
            errors.append(f"Test '{test['name']}' input must be a JSON object.")
        if not isinstance(test["hidden"], bool):
            errors.append(f"Test '{test['name']}' hidden flag must be a boolean.")
        try:
            json.dumps(test["input"], allow_nan=False)
            json.dumps(test["expected"], allow_nan=False)
        except (TypeError, ValueError):
            errors.append(f"Test '{test['name']}' is not JSON-serializable.")
        for assertion in test.get("assertions") or []:
            try:
                ok = execution.equal(execution.at_path(test["expected"], assertion["path"]), assertion["equals"])
            except (KeyError, IndexError, TypeError, ValueError):
                ok = False
            if not ok:
                errors.append(f"Test '{test['name']}' assertion '{assertion.get('path')}' contradicts its expected output.")
    if tests and not any(isinstance(test, dict) and not test.get("hidden") for test in tests):
        errors.append("At least one public test is required to reproduce the defect.")
    if len(definition.get("hints") or []) != 3:
        warnings.append("Problems normally provide exactly three progressive hints.")
    if not definition.get("requirements"):
        warnings.append("No requirements are listed.")
    if language in solutions:
        payload = json.dumps({"language": language, "code": solutions[language],
                              "inputs": [test.get("input") for test in tests if isinstance(test, dict)]})
        if len(payload.encode()) > PAYLOAD_LIMIT:
            errors.append("Code and test inputs exceed the sandbox request limit.")
    if errors:
        return _step("schema_validation", "failed", "; ".join(errors[:5]), errors=errors, warnings=warnings)
    return _step("schema_validation", "warning" if warnings else "passed",
                 "Definition is complete." if not warnings else "; ".join(warnings), errors=[], warnings=warnings)


def verify_starter(definition: dict, language: str, executor=default_executor) -> dict:
    """MT-007: the buggy starter compiles, runs, and fails at least one public test."""
    tests = definition["tests"]
    graded = grade_output(tests, executor(language, definition["starters"][language], tests))
    public_failures = [test["name"] for test, status in zip(tests, graded["per_test"], strict=False)
                       if not test["hidden"] and status != "passed"]
    hidden_failures = [test["name"] for test, status in zip(tests, graded["per_test"], strict=False)
                       if test["hidden"] and status != "passed"]
    data = {"compiled": graded["compiled"], "status": graded["status"], "public_failures": public_failures,
            "hidden_failures": hidden_failures, "per_test": graded["per_test"], "message": graded["message"]}
    if not graded["compiled"]:
        return _step("starter_failure", "failed", "The starter does not compile, so it cannot demonstrate the defect.", **data)
    if not graded["per_test"]:
        return _step("starter_failure", "failed",
                     f"The starter stopped with {graded['status'].replace('_', ' ')} before producing per-test results.", **data)
    if not public_failures:
        return _step("starter_failure", "failed", "The starter passes every public test, so the defect is not reproducible.", **data)
    return _step("starter_failure", "passed", f"The starter fails {len(public_failures)} public test(s).", **data)


def verify_reference(definition: dict, language: str, executor=default_executor, runs: int = 2) -> dict:
    """MT-006 and execution stability: the reference passes every test on repeated runs."""
    tests = definition["tests"]
    outcomes = []
    for _ in range(max(1, runs)):
        graded = grade_output(tests, executor(language, definition["solutions"][language], tests))
        outcomes.append({"status": graded["status"], "per_test": graded["per_test"],
                         "max_case_runtime_ms": max(graded["case_runtimes"], default=None),
                         "runtime_ms": graded.get("runtime_ms"), "message": graded["message"]})
    passed = all(outcome["status"] == "passed" for outcome in outcomes)
    stable = len({json.dumps(outcome["per_test"]) for outcome in outcomes}) == 1 and len(
        {outcome["status"] for outcome in outcomes}) == 1
    slowest = max((outcome["max_case_runtime_ms"] for outcome in outcomes if outcome["max_case_runtime_ms"] is not None),
                  default=None)
    failing = sorted({test["name"] for outcome in outcomes for test, status in
                      zip(tests, outcome["per_test"], strict=False) if status != "passed"})
    data = {"passed": passed, "stable": stable, "runs": outcomes, "max_case_runtime_ms": slowest,
            "failing_tests": failing}
    if not passed:
        return _step("reference_verification", "failed",
                     "The reference solution fails: " + (", ".join(failing[:5]) or outcomes[0]["status"]), **data)
    if not stable:
        return _step("reference_verification", "warning", "The reference passed, but results varied between runs.", **data)
    return _step("reference_verification", "passed", f"The reference passed every test in {len(outcomes)} runs.", **data)


def validate_hidden_tests(definition: dict) -> dict:
    tests = definition["tests"]
    public = [test for test in tests if not test["hidden"]]
    hidden = [test for test in tests if test["hidden"]]
    public_inputs = {json.dumps(test["input"], sort_keys=True) for test in public}
    duplicates = [test["name"] for test in hidden if json.dumps(test["input"], sort_keys=True) in public_inputs]
    distinct = len(hidden) - len(duplicates)
    expectations = {json.dumps(test["expected"], sort_keys=True) for test in tests}
    trivial = len(tests) > 1 and len(expectations) == 1
    data = {"public": len(public), "hidden": len(hidden), "distinct_hidden_inputs": distinct,
            "duplicate_inputs": duplicates, "trivial_expectations": trivial}
    if not hidden:
        return _step("hidden_test_validation", "failed", "There are no hidden tests.", **data)
    if distinct == 0:
        return _step("hidden_test_validation", "failed", "Every hidden input repeats a public input.", **data)
    if trivial:
        return _step("hidden_test_validation", "failed",
                     "Every test expects the same output, so a constant answer would pass.", **data)
    if duplicates:
        return _step("hidden_test_validation", "warning",
                     f"{len(duplicates)} hidden test(s) repeat a public input.", **data)
    return _step("hidden_test_validation", "passed", f"{len(hidden)} hidden test(s) with distinct inputs.", **data)


def _json_forms(value) -> set[str]:
    forms = {json.dumps(value), json.dumps(value, separators=(",", ":"))}
    return {form for form in forms if len(form) >= 12}


def check_leakage(definition: dict, *, api_payload: dict | None = None) -> dict:
    """Reference code or hidden-test data must not appear in public problem text or API output."""
    starter_lines = {line.strip() for code in definition["starters"].values() for line in code.split("\n")}
    solution_lines = sorted({line.strip() for code in definition["solutions"].values() for line in code.split("\n")
                             if len(line.strip()) >= 25 and line.strip() not in starter_lines})
    public_forms = set()
    for test in definition["tests"]:
        if not test["hidden"]:
            public_forms |= _json_forms(test["input"]) | _json_forms(test["expected"])
    hidden_forms = set()
    for test in definition["tests"]:
        if test["hidden"]:
            hidden_forms |= (_json_forms(test["input"]) | _json_forms(test["expected"])) - public_forms
    sources = [("summary", definition.get("summary") or "", "error"),
               ("description", definition.get("description") or "", "error"),
               ("requirements", "\n".join(definition.get("requirements") or []), "error"),
               # Hints unlock only after repeated failures and are meant to approach the fix.
               ("hints", "\n".join(definition.get("hints") or []), "warning")]
    if api_payload is not None:
        visible = {key: value for key, value in api_payload.items() if key not in ("starters", "public_tests")}
        sources.append(("problem API response", json.dumps(visible, default=str), "error"))
    findings = []
    for source, text, severity in sources:
        for line in solution_lines:
            if line in text:
                findings.append({"source": source, "kind": "reference_code", "severity": severity, "excerpt": line[:120]})
        for form in hidden_forms:
            if form in text:
                findings.append({"source": source, "kind": "hidden_test_data", "severity": severity, "excerpt": form[:120]})
    errors = [item for item in findings if item["severity"] == "error"]
    if errors:
        return _step("solution_leakage", "failed", f"{len(errors)} exposure(s) of hidden tests or reference code.",
                     findings=findings, api_checked=api_payload is not None)
    if findings:
        return _step("solution_leakage", "warning", "Hints quote reference code or hidden data.",
                     findings=findings, api_checked=api_payload is not None)
    return _step("solution_leakage", "passed", "No hidden tests or reference code are exposed.",
                 findings=[], api_checked=api_payload is not None)


def _walk_values(value, depth=0):
    yield value, depth
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item, depth + 1)


def test_inventory(definition: dict) -> dict:
    """Test-suite indicators for the quality report (counts, edge-case coverage, probes)."""
    tests = definition["tests"]
    present = set()
    for test in tests:
        for value, depth in _walk_values(test["input"]):
            if isinstance(value, (list, dict, str)) and len(value) == 0:
                present.add("empty_collection")
            if isinstance(value, bool):
                present.add("boolean_value")
            elif isinstance(value, (int, float)):
                if value == 0:
                    present.add("zero")
                if value < 0:
                    present.add("negative_number")
                if abs(value) >= 2 ** 31:
                    present.add("large_number")
            if value is None:
                present.add("null_value")
            if isinstance(value, str) and any(ord(char) > 127 for char in value):
                present.add("non_ascii_text")
            if isinstance(value, list):
                if len(value) == 1:
                    present.add("single_element")
                serialized = [json.dumps(item, sort_keys=True) for item in value]
                if len(serialized) != len(set(serialized)):
                    present.add("duplicate_values")
            if depth >= 3:
                present.add("nested_structure")
    classification = taxonomy.classify(definition.get("category") or "", list(definition.get("tags") or []),
                                       definition.get("taxonomy"))
    concurrent = "race_condition" in classification["bug_categories"] or "deadlock" in classification["bug_categories"]
    probes = sum(1 for test in tests if isinstance(test["input"], dict) and any(
        isinstance(value, list) and len(value) >= 2 for value in test["input"].values())) if concurrent else 0
    return {
        "total": len(tests), "public": sum(not test["hidden"] for test in tests),
        "hidden": sum(bool(test["hidden"]) for test in tests),
        "with_state_assertions": sum(1 for test in tests if test.get("assertions")),
        "edge_case_coverage": {"present": [name for name in EDGE_INDICATORS if name in present],
                               "count": len(present), "total": len(EDGE_INDICATORS)},
        "concurrency_probes": probes if concurrent else None,
        "bug_categories": classification["bug_categories"],
    }


# ── Mutation results ────────────────────────────────────────────────────────────────────────

def summarize_cases(cases: list[dict], *, count_timeouts_as_killed: bool = True) -> dict:
    """Counts and the mutation score K / (M - E) x 100 (PRD 7.4).

    E excludes invalid, equivalent and infrastructure-error mutants (and timeouts, when timeouts are
    configured not to count as detections). Pending cases are not scored yet.
    """
    counts = Counter(case["status"] for case in cases)
    total = len(cases)
    killed, timeouts = counts["killed"], counts["timeout"]
    numerator = killed + (timeouts if count_timeouts_as_killed else 0)
    excluded = counts["invalid"] + counts["equivalent"] + counts["error"] + (0 if count_timeouts_as_killed else timeouts)
    pending = counts["queued"] + counts["running"]
    scored = total - excluded - pending
    score = round(numerator / scored * 100, 2) if scored > 0 else None
    detected = {"killed", "timeout"} if count_timeouts_as_killed else {"killed"}
    scorable = detected | {"survived"}
    critical = [case for case in cases if case.get("critical")]
    by_operator = {}
    for case in cases:
        row = by_operator.setdefault(case["operator"], Counter())
        row["total"] += 1
        row[case["status"]] += 1
    return {
        "total": total, "killed": killed, "timed_out": timeouts, "survived": counts["survived"],
        "invalid": counts["invalid"], "equivalent": counts["equivalent"], "errors": counts["error"],
        "pending": pending, "scored": scored, "detected": numerator, "score": score,
        "count_timeouts_as_killed": count_timeouts_as_killed,
        "critical_total": len(critical),
        "critical_scored": sum(1 for case in critical if case["status"] in scorable),
        "critical_killed": sum(1 for case in critical if case["status"] in detected),
        "critical_survived": sum(1 for case in critical if case["status"] == "survived"),
        "by_operator": {operator: dict(by_operator[operator]) for operator in OPERATORS if operator in by_operator},
    }


def meaningful_hidden_tests(tests: list[dict], cases: list[dict], starter_per_test: list | None) -> list[str]:
    """Hidden tests that catch a defect no public test catches (or that the starter fails)."""
    meaningful = []
    for test, status in zip(tests, starter_per_test or [], strict=False):
        if test["hidden"] and status != "passed":
            meaningful.append(test["name"])
    for case in cases:
        per_test = case.get("per_test") or []
        if case["status"] not in ("killed", "timeout") or len(per_test) != len(tests):
            continue
        if any(status != "passed" for test, status in zip(tests, per_test, strict=True) if not test["hidden"]):
            continue
        meaningful.extend(test["name"] for test, status in zip(tests, per_test, strict=True)
                          if test["hidden"] and status != "passed")
    return list(dict.fromkeys(meaningful))


def per_test_kills(tests: list[dict], cases: list[dict]) -> dict:
    kills = {test["name"]: 0 for test in tests}
    for case in cases:
        for item in case.get("killing_tests") or []:
            if item["name"] in kills:
                kills[item["name"]] += 1
    return kills


def build_report(definition: dict, language: str, steps: dict, cases: list[dict], *, thresholds: dict,
                 generation: dict, problem_version: int | None, problem_hash: str) -> dict:
    tests_meta = [{"name": test["name"], "hidden": bool(test["hidden"])} for test in definition["tests"]]
    summary = summarize_cases(cases, count_timeouts_as_killed=thresholds["count_timeouts_as_killed"])
    starter = steps.get("starter_failure") or {}
    meaningful = meaningful_hidden_tests(tests_meta, cases, (starter.get("data") or {}).get("per_test"))
    executed = summary["total"] - summary["pending"]
    execution_step = _step(
        "mutation_execution", "skipped" if not cases else "passed" if not summary["pending"] else "running",
        "No mutants were executed." if not cases else
        f"{executed}/{summary['total']} mutants executed; {summary['errors']} infrastructure error(s).", **summary)
    gate = gates.evaluate({"schema": steps.get("schema_validation"), "starter": starter,
                           "reference": steps.get("reference_verification"),
                           "hidden": steps.get("hidden_test_validation"), "leakage": steps.get("solution_leakage"),
                           "summary": summary, "meaningful_hidden": meaningful}, thresholds)
    ordered = [steps[name] for name in STEP_NAMES[:6] if name in steps] + [execution_step]
    ordered.append(_step("quality_report", "passed", "Quality report generated."))
    ordered.append(_step("quality_gate", "passed" if gate["status"] == "approved" else "failed",
                         "Approved for publication." if gate["status"] == "approved"
                         else "Requires revision: " + "; ".join(gate["reasons"][:3])))
    reference = (steps.get("reference_verification") or {}).get("data") or {}
    return {
        "pipeline_version": PIPELINE_VERSION, "mutation_version": MUTATION_VERSION,
        "problem": {"slug": definition["slug"], "title": definition["title"], "category": definition.get("category"),
                    "difficulty": definition.get("difficulty"), "version": problem_version, "content_hash": problem_hash},
        "language": language, "pipeline": ordered, "mutation": summary, "generation": generation,
        "tests": {**generation.get("inventory", {}), "meaningful_hidden_tests": meaningful,
                  "per_test_kills": per_test_kills(tests_meta, cases)},
        "reference": {"passed": reference.get("passed", False), "stable": reference.get("stable", False),
                      "max_case_runtime_ms": reference.get("max_case_runtime_ms"),
                      "runs": len(reference.get("runs", []))},
        "starter": {key: (starter.get("data") or {}).get(key) for key in
                    ("compiled", "status", "public_failures", "hidden_failures")},
        "leakage": (steps.get("solution_leakage") or {}).get("data") or {"findings": []},
        "resource_limits": gates.sandbox_limits(),
        "mutants": [{key: case.get(key) for key in ("ordinal", "operator", "description", "line", "critical", "status",
                                                    "failure_classification")}
                    | {"killing_tests": [item["name"] for item in case.get("killing_tests") or []]} for case in cases],
        "gate": gate, "generated_at": now().isoformat(),
    }


def validation_steps(definition: dict, language: str, *, executor=default_executor, runs: int = 2,
                     api_payload: dict | None = None) -> dict:
    """Steps 1–4 plus the leakage check. SandboxUnavailable propagates (an infrastructure failure)."""
    steps = {"schema_validation": validate_schema(definition, language)}
    if steps["schema_validation"]["status"] == "failed":
        for name in ("starter_failure", "reference_verification", "hidden_test_validation", "solution_leakage"):
            steps[name] = _step(name, "skipped", "Skipped because the definition is invalid.")
        return steps
    steps["starter_failure"] = verify_starter(definition, language, executor)
    steps["reference_verification"] = verify_reference(definition, language, executor, runs)
    steps["hidden_test_validation"] = validate_hidden_tests(definition)
    steps["solution_leakage"] = check_leakage(definition, api_payload=api_payload)
    return steps


def mutation_stage(definition: dict, language: str, steps: dict, *, max_mutants: int, operators=None):
    """Generate mutants when the reference is valid; returns (mutants, generation metadata)."""
    inventory = test_inventory(definition)
    if (steps.get("reference_verification") or {}).get("status") not in ("passed", "warning"):
        steps["mutation_generation"] = _step("mutation_generation", "skipped",
                                             "Skipped: mutants of a failing reference are not meaningful.")
        return [], {"candidates": 0, "selected": 0, "by_operator": {}, "inventory": inventory}
    generated = generate(language, definition["solutions"][language], starter=definition["starters"].get(language),
                         max_mutants=max_mutants, operators=operators)
    invalid = sum(1 for mutant in generated.mutants if mutant["valid"] is False)
    metadata = {"candidates": generated.candidates, "selected": len(generated.mutants),
                "by_operator": generated.by_operator, "critical": sum(m["critical"] for m in generated.mutants),
                "invalid_precheck": invalid, "max_mutants": max_mutants, "operators": operators or OPERATORS,
                "version": MUTATION_VERSION, "inventory": inventory}
    steps["mutation_generation"] = _step(
        "mutation_generation", "passed" if generated.mutants else "warning",
        f"{len(generated.mutants)} of {generated.candidates} candidate mutants selected"
        f" ({metadata['critical']} critical).", **{key: value for key, value in metadata.items() if key != "inventory"})
    return generated.mutants, metadata


def execute_mutant(language: str, code: str, tests: list, executor=default_executor, *, retries: int = 0,
                   backoff: float = 0.5) -> dict:
    """Run and classify one mutant in memory, retrying infrastructure failures (CLI path)."""
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            outcome = classify_outcome(tests, executor(language, code, tests))
        except SandboxUnavailable as exc:
            if attempt >= retries:
                return {"status": "error", "failure_classification": "infrastructure", "killing_tests": [],
                        "per_test": [], "message": str(exc), "duration_ms": None}
            time.sleep(backoff * 2 ** attempt)
            continue
        outcome["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
        return outcome
    raise AssertionError("unreachable")


def run_in_memory(definition: dict, language: str | None = None, *, max_mutants: int = 24, operators=None,
                  executor=default_executor, thresholds: dict | None = None, retries: int = 2) -> dict:
    """The complete pipeline without a database (CLI ``--dry-run`` / ``--from-catalog``)."""
    language = language or next(iter(definition["starters"]))
    thresholds = {**gates.DEFAULT_THRESHOLDS, **(thresholds or {})}
    steps = validation_steps(definition, language, executor=executor, runs=thresholds["stability_runs"])
    mutants, generation = ([], {"candidates": 0, "selected": 0, "by_operator": {},
                                "inventory": test_inventory(definition)}) \
        if steps["schema_validation"]["status"] == "failed" else mutation_stage(
            definition, language, steps, max_mutants=max_mutants, operators=operators)
    cases = []
    for mutant in mutants:
        base = {key: mutant[key] for key in ("ordinal", "operator", "description", "line", "critical")}
        if mutant["valid"] is False:
            cases.append({**base, "status": "invalid", "failure_classification": "syntax_error", "killing_tests": [],
                          "per_test": []})
            continue
        cases.append({**base, **execute_mutant(language, mutant["code"], definition["tests"], executor,
                                               retries=retries)})
    return build_report(definition, language, steps, cases, thresholds=thresholds, generation=generation,
                        problem_version=None, problem_hash=content_hash(definition))


# ── Database-backed runs ────────────────────────────────────────────────────────────────────

def create_run(db, problem, *, language: str | None = None, max_mutants: int = 24, operators=None,
               requested_by: str | None = None) -> MutationRun:
    language = language or next(iter(problem.starters))
    if language not in problem.starters or language not in problem.solutions:
        raise ValueError(f"{language} is not available for this problem.")
    if operators:
        unknown = set(operators) - set(OPERATORS)
        if unknown:
            raise ValueError(f"Unknown mutation operators: {', '.join(sorted(unknown))}")
    sync_version(problem)
    thresholds = gates.effective_thresholds(db, problem.category)
    config = {"language": language, "max_mutants": int(max_mutants),
              "operators": sorted(operators) if operators else None,
              "count_timeouts_as_killed": thresholds["count_timeouts_as_killed"],
              "stability_runs": thresholds["stability_runs"], "thresholds": thresholds,
              "mutation_version": MUTATION_VERSION, "pipeline_version": PIPELINE_VERSION}
    run = MutationRun(problem_id=problem.id, problem_version=problem.version, content_hash=problem.content_hash,
                      language=language, status="queued", config=config, requested_by=requested_by,
                      report={}, execution_metadata={})
    db.add(run)
    db.flush()
    return run


def api_payload_for(db, problem) -> dict | None:
    """The public problem-detail payload, as an anonymous visitor would receive it."""
    try:
        from app.api import problem_payload
        return problem_payload(db, problem, None)
    except Exception:
        log.warning("Could not build the problem payload for the leakage check", exc_info=True)
        return None


def run_validation(db, run: MutationRun, *, executor=default_executor) -> list[MutationCase]:
    """Run the validation steps and create mutation cases. Raises SandboxUnavailable on infra failure."""
    problem = db.get(Problem, run.problem_id)
    definition = definition_from_problem(problem)
    steps = validation_steps(definition, run.language, executor=executor,
                             runs=int(run.config.get("stability_runs", 2)), api_payload=api_payload_for(db, problem))
    if steps["schema_validation"]["status"] == "failed":
        mutants, generation = [], {"candidates": 0, "selected": 0, "by_operator": {},
                                   "inventory": test_inventory(definition)}
    else:
        mutants, generation = mutation_stage(definition, run.language, steps,
                                             max_mutants=int(run.config.get("max_mutants", 24)),
                                             operators=run.config.get("operators"))
    cases = []
    for mutant in mutants:
        invalid = mutant["valid"] is False
        case = MutationCase(
            run_id=run.id, ordinal=mutant["ordinal"], operator=mutant["operator"], description=mutant["description"],
            line=mutant["line"], critical=mutant["critical"], original_snippet=mutant["original_snippet"],
            mutated_snippet=mutant["mutated_snippet"], original_code_hash=mutant["original_hash"],
            mutated_code_hash=mutant["code_hash"], mutated_code=mutant["code"],
            status="invalid" if invalid else "queued", failure_classification="syntax_error" if invalid else None,
            killing_tests=[], detail={"per_test": []}, completed_at=now() if invalid else None)
        db.add(case)
        cases.append(case)
    run.total_mutations = len(cases)
    run.execution_metadata = {**(run.execution_metadata or {}), "steps": steps, "generation": generation,
                              "tests": [{"name": test["name"], "hidden": bool(test["hidden"])}
                                        for test in definition["tests"]],
                              "validated_at": now().isoformat()}
    run.status = "running"
    db.flush()
    return cases


def case_dict(case: MutationCase) -> dict:
    return {"ordinal": case.ordinal, "operator": case.operator, "description": case.description, "line": case.line,
            "critical": case.critical, "status": case.status, "failure_classification": case.failure_classification,
            "killing_tests": case.killing_tests or [], "per_test": (case.detail or {}).get("per_test") or []}


def execute_case(db, case: MutationCase, run: MutationRun, problem, *, executor=default_executor) -> None:
    """Execute and classify one claimed case. Raises SandboxUnavailable for infrastructure failures."""
    started = time.monotonic()
    outcome = classify_outcome(problem.tests, executor(run.language, case.mutated_code, problem.tests))
    case.status = outcome["status"]
    case.failure_classification = outcome["failure_classification"]
    case.killing_tests = outcome["killing_tests"]
    case.detail = {**(case.detail or {}), "per_test": outcome["per_test"], "message": outcome["message"]}
    case.execution_duration_ms = round((time.monotonic() - started) * 1000, 2)
    case.completed_at = now()


def finalize_run(db, run: MutationRun) -> bool:
    """Recompute counts, score, report and gate from the cases. Idempotent; False while cases are pending."""
    cases = list(db.scalars(select(MutationCase).where(MutationCase.run_id == run.id).order_by(MutationCase.ordinal)))
    if any(case.status in PENDING_CASE for case in cases):
        return False
    problem = db.get(Problem, run.problem_id)
    metadata = run.execution_metadata or {}
    steps = metadata.get("steps") or {}
    definition = {**definition_from_problem(problem), "tests": [
        {"name": test["name"], "hidden": test["hidden"]} for test in metadata.get("tests", [])]}
    thresholds = {**gates.DEFAULT_THRESHOLDS, **(run.config or {}).get("thresholds", {})}
    report = build_report(definition, run.language, steps, [case_dict(case) for case in cases], thresholds=thresholds,
                          generation=metadata.get("generation") or {}, problem_version=run.problem_version,
                          problem_hash=run.content_hash)
    summary = report["mutation"]
    run.total_mutations = summary["total"]
    run.killed_mutations = summary["killed"]
    run.timed_out_mutations = summary["timed_out"]
    run.survived_mutations = summary["survived"]
    run.invalid_mutations = summary["invalid"]
    run.equivalent_mutations = summary["equivalent"]
    run.error_mutations = summary["errors"]
    run.mutation_score = summary["score"]
    run.gate_status = report["gate"]["status"]
    if run.report and run.report.get("generated_at"):
        report["first_generated_at"] = run.report.get("first_generated_at") or run.report["generated_at"]
    run.report = report
    run.status = "completed"
    run.completed_at = run.completed_at or now()
    if run.started_at:
        duration = (aware(run.completed_at) - aware(run.started_at)).total_seconds() * 1000
        run.execution_metadata = {**metadata, "duration_ms": round(duration, 2)}
    if problem is not None and problem.content_hash == run.content_hash:
        problem.quality_status = run.gate_status
    return True


def maybe_finalize(db, run_id: str) -> bool:
    run = db.scalar(select(MutationRun).where(MutationRun.id == run_id).with_for_update())
    if run is None or run.status not in ("running", "completed"):
        return False
    return finalize_run(db, run)


def latest_valid_run(db, problem) -> MutationRun | None:
    """The newest completed run for the problem's current content (used by the publication gate)."""
    current = content_hash(definition_from_problem(problem))
    return db.scalar(select(MutationRun).where(MutationRun.problem_id == problem.id,
                                               MutationRun.status == "completed",
                                               MutationRun.content_hash == current,
                                               MutationRun.problem_version == problem.version)
                     .order_by(MutationRun.created_at.desc()).limit(1))


def aware(value):
    return value.replace(tzinfo=now().tzinfo) if value is not None and value.tzinfo is None else value


def percent(part: float, whole: float) -> float | None:
    return round(part / whole * 100, 2) if whole else None


def nearest_rank(values, q: float):
    ordered = sorted(value for value in values if value is not None)
    if not ordered:
        return None
    return round(ordered[max(0, math.ceil(q * len(ordered)) - 1)], 2)
