"""Problem quality pipeline, mutation runs, gates and publication (PRD §7; MT-002..MT-011)."""
import copy
import json
import sys
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import execution
from app.celery_app import celery
from app.config import settings
from app.execution import SandboxUnavailable
from app.models import AuditLog, MutationCase, MutationRun, Problem, ProblemSubmission, now
from app.quality import pipeline
from app.quality import tasks as quality_tasks
from app.quality.__main__ import main as cli


class StepLimit(Exception):
    pass


def run_python(code, data, limit=200_000):
    """Execute repository-authored code in process with a deterministic step budget."""
    count = 0

    def tracer(frame, event, arg):
        nonlocal count
        if event == "line":
            count += 1
            if count > limit:
                raise StepLimit()
        return tracer

    previous = sys.gettrace()
    namespace = {"__name__": "solution"}
    sys.settrace(tracer)
    try:
        exec(compile(code, "solution.py", "exec"), namespace)
        return namespace["solve"](copy.deepcopy(data))
    finally:
        sys.settrace(previous)


def fake_executor(language, code, tests):
    """Runner-shaped results, like the sandbox's Python harness (syntax errors surface per test)."""
    assert language == "python"
    try:
        compile(code, "solution.py", "exec")
    except SyntaxError as exc:
        return {"results": [{"status": "runtime_error", "stderr": f"SyntaxError: {exc}", "runtime_ms": 1.0}
                            for _ in tests], "runtime_ms": 5.0, "memory_kb": 100}
    results = []
    for test in tests:
        try:
            output = json.loads(json.dumps(run_python(code, test["input"]), allow_nan=False))
            results.append({"status": "ok", "output": output, "runtime_ms": 1.0})
        except StepLimit:
            results.append({"status": "time_limit", "stderr": "", "runtime_ms": 2000.0})
        except Exception as exc:
            results.append({"status": "runtime_error", "stderr": f"{type(exc).__name__}: {exc}", "runtime_ms": 1.0})
    return {"results": results, "runtime_ms": 10.0, "memory_kb": 1000}


@pytest.fixture
def admin(client, member, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", member["email"])
    return member


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setattr(execution, "execute_code", fake_executor)


def start(client, slug, **body):
    response = client.post(f"/api/admin/problems/{slug}/mutation-runs", json=body)
    assert response.status_code == 202, response.text
    return response.json()["id"]


def drain(db_factory, run_id):
    quality_tasks.quality_run(run_id)
    with db_factory() as db:
        queued = list(db.scalars(select(MutationCase.id).where(MutationCase.run_id == run_id,
                                                               MutationCase.status == "queued")))
    for case_id in queued:
        quality_tasks.mutation_case(case_id)


SUBMISSION = {
    "title": "Positive totals only", "summary": "Add up the positive values in a list of adjustments.",
    "description": "The adjustment service should ignore refunds and zero rows when computing the total.",
    "category": "logic", "difficulty": "easy", "tags": ["arrays"], "language": "python",
    "buggy_code": 'def solve(data):\n    return {"total": sum(value for value in data["values"])}\n',
    "fixed_code": 'def solve(data):\n    return {"total": sum(value for value in data["values"] if value > 0)}\n',
    "test_cases": [{"input": '{"values": [1, -2, 3]}', "expected": '{"total": 4}'},
                   {"input": '{"values": [-1, -5]}', "expected": '{"total": 0}'},
                   {"input": '{"values": [0, 5, -3]}', "expected": '{"total": 5}'},
                   {"input": '{"values": []}', "expected": '{"total": 0}'}],
    "hint": "Which values should contribute to a total of positive adjustments?",
}


def community_draft(client, **overrides):
    response = client.post("/api/problem-submissions", json={**SUBMISSION, **overrides})
    assert response.status_code == 201, response.text
    submission_id = response.json()["id"]
    assert client.post(f"/api/admin/problem-submissions/{submission_id}/draft").status_code == 409
    assert client.patch(f"/api/admin/problem-submissions/{submission_id}",
                        json={"action": "approved"}).status_code == 200
    draft = client.post(f"/api/admin/problem-submissions/{submission_id}/draft")
    assert draft.status_code == 201, draft.text
    assert client.post(f"/api/admin/problem-submissions/{submission_id}/draft").status_code == 409
    return submission_id, draft.json()


def test_classification_distinguishes_outcomes_and_excludes_infrastructure():
    tests = [{"name": "public", "input": {}, "expected": 1, "hidden": False, "assertions": []},
             {"name": "hidden", "input": {}, "expected": 2, "hidden": True, "assertions": []}]
    ok = lambda *values: {"results": [{"status": "ok", "output": v, "runtime_ms": 1} for v in values]}  # noqa: E731
    assert pipeline.classify_outcome(tests, ok(1, 2))["status"] == "survived"
    killed = pipeline.classify_outcome(tests, ok(1, 3))
    assert killed["status"] == "killed" and killed["failure_classification"] == "assertion"
    assert killed["killing_tests"] == [{"name": "hidden", "hidden": True, "status": "failed"}]
    crash = pipeline.classify_outcome(tests, {"results": [{"status": "runtime_error", "stderr": "KeyError"}] * 2})
    assert (crash["status"], crash["failure_classification"]) == ("killed", "runtime_error")
    slow = pipeline.classify_outcome(tests, {"results": [{"status": "ok", "output": 1}, {"status": "time_limit"}]})
    assert (slow["status"], slow["failure_classification"]) == ("timeout", "time_limit")
    assert pipeline.classify_outcome(tests, {"compile_error": "error: expected ';'"})["status"] == "invalid"
    syntax = {"results": [{"status": "runtime_error", "stderr": "SyntaxError: invalid syntax"}] * 2}
    assert pipeline.classify_outcome(tests, syntax)["status"] == "invalid"
    oom = pipeline.classify_outcome(tests, {"fatal_status": "memory_limit", "results": []})
    assert (oom["status"], oom["failure_classification"]) == ("killed", "resource_limit")

    def case(status, critical=False):
        return {"status": status, "critical": critical, "operator": "comparison"}

    cases = [case("killed", True), case("killed"), case("killed"), case("timeout", True), case("survived", True),
             case("invalid"), case("equivalent"), case("error", True)]
    summary = pipeline.summarize_cases(cases)
    # K / (M - E): (3 killed + 1 timeout) / (8 - invalid - equivalent - error) = 4 / 5.
    assert summary["score"] == 80.0 and summary["scored"] == 5 and summary["errors"] == 1
    assert (summary["critical_scored"], summary["critical_killed"]) == (3, 2)
    strict = pipeline.summarize_cases(cases, count_timeouts_as_killed=False)
    assert strict["score"] == 75.0 and strict["timed_out"] == 1
    assert pipeline.summarize_cases([case("error"), case("invalid")])["score"] is None


def test_quality_tasks_route_to_dedicated_queue():
    for name in ("app.quality.run", "app.quality.case", "app.quality.recover"):
        assert celery.amqp.router.route({}, name, (), {})["queue"].name == "quality"
    assert celery.amqp.router.route({}, "app.tasks.evaluate", (), {})["queue"].name == "celery"


def test_catalog_problems_validate_end_to_end(client, admin, sandbox, db_factory):
    strong = start(client, "checkout-underflow", max_mutants=12)
    drain(db_factory, strong)
    run = client.get(f"/api/admin/mutation-runs/{strong}").json()
    assert run["status"] == "completed" and run["gate_status"] == "approved"
    assert run["mutation_score"] == 100.0 and run["killed_mutations"] == run["total_mutations"] > 0
    steps = {step["step"]: step for step in run["pipeline"]}
    assert [step["step"] for step in run["pipeline"]] == pipeline.STEP_NAMES
    assert steps["starter_failure"]["status"] == "passed" and steps["reference_verification"]["status"] == "passed"
    assert steps["solution_leakage"]["data"]["api_checked"] is True
    report = run["report"]
    assert report["tests"]["hidden"] == 2 and report["tests"]["public"] == 2
    assert report["tests"]["meaningful_hidden_tests"] and report["reference"]["runs"] == 2
    assert report["tests"]["edge_case_coverage"]["total"] == 10
    assert {"total", "killed", "survived", "invalid", "score"} <= set(report["mutation"])

    weak = start(client, "inventory-retry")
    drain(db_factory, weak)
    run = client.get(f"/api/admin/mutation-runs/{weak}").json()
    assert run["gate_status"] == "requires_revision"
    assert run["survived_mutations"] >= 1 and run["mutation_score"] < 100
    assert any("critical mutants killed" in reason for reason in run["report"]["gate"]["reasons"])
    cases = client.get(f"/api/admin/mutation-runs/{weak}/cases?status=survived").json()["items"]
    assert cases and all(case["status"] == "survived" and case["mutated_snippet"] for case in cases)
    killed = client.get(f"/api/admin/mutation-runs/{weak}/cases?status=killed&include_code=true").json()["items"]
    assert killed[0]["mutated_code"] and killed[0]["killing_tests"]
    with db_factory() as db:
        problem = db.scalar(select(Problem).where(Problem.slug == "inventory-retry"))
        assert problem.quality_status == "requires_revision" and problem.content_hash
    # Quality data never reaches the user-facing problem API.
    detail = client.get("/api/problems/inventory-retry").json()
    assert "Existing reservation" not in json.dumps(detail) and "mutation" not in json.dumps(detail).lower()
    overview = client.get("/api/admin/quality/overview?q=inventory").json()
    assert overview["items"][0]["latest_run"]["gate_status"] == "requires_revision"
    assert client.get("/api/admin/quality/overview?gate=approved").json()["items"][0]["slug"] == "checkout-underflow"


def test_results_are_reproducible_for_the_same_version_and_configuration(client, admin, sandbox, db_factory):
    outcomes = []
    for _ in range(2):
        run_id = start(client, "inventory-retry", max_mutants=10)
        drain(db_factory, run_id)
        with db_factory() as db:
            run = db.get(MutationRun, run_id)
            cases = db.scalars(select(MutationCase).where(MutationCase.run_id == run_id).order_by(MutationCase.ordinal))
            outcomes.append((run.problem_version, run.content_hash, run.config["max_mutants"], run.mutation_score,
                             run.gate_status, [(case.mutated_code_hash, case.status, case.failure_classification)
                                               for case in cases]))
    assert outcomes[0] == outcomes[1]


def test_redelivered_tasks_are_noops(client, admin, sandbox, db_factory):
    run_id = start(client, "missing-last-item")
    quality_tasks.quality_run(run_id)
    quality_tasks.quality_run(run_id)
    with db_factory() as db:
        cases = list(db.scalars(select(MutationCase).where(MutationCase.run_id == run_id)))
        assert len(cases) == db.get(MutationRun, run_id).total_mutations > 0
    for case in cases:
        quality_tasks.mutation_case(case.id)
        quality_tasks.mutation_case(case.id)
    with db_factory() as db:
        assert all(row.attempts == 1 for row in db.scalars(select(MutationCase).where(MutationCase.run_id == run_id)))
        run = db.get(MutationRun, run_id)
        assert run.status == "completed" and run.mutation_score == 100.0
    assert client.post("/api/admin/problems/missing-last-item/mutation-runs", json={}).status_code == 202


def test_infrastructure_failures_retry_and_never_count_as_killed(client, admin, db_factory, monkeypatch):
    def flaky(language, code, tests):
        if "sum(data[\"nums\"])" in code:
            return fake_executor(language, code, tests)
        if "range(len(data" in code:
            return fake_executor(language, code, tests)
        raise SandboxUnavailable("daemon offline")

    monkeypatch.setattr(execution, "execute_code", flaky)
    run_id = start(client, "missing-last-item")
    quality_tasks.quality_run(run_id)
    with db_factory() as db:
        case_id = db.scalar(select(MutationCase.id).where(MutationCase.run_id == run_id))
    for attempt in range(1, 4):
        quality_tasks.mutation_case(case_id)
        with db_factory() as db:
            case = db.get(MutationCase, case_id)
            assert case.attempts == attempt
            assert case.status == ("queued" if attempt < 3 else "error")
    with db_factory() as db:
        case, run = db.get(MutationCase, case_id), db.get(MutationRun, run_id)
        assert case.failure_classification == "infrastructure"
        assert run.status == "completed" and run.killed_mutations == 0 and run.error_mutations == 1
        assert run.mutation_score is None and run.gate_status == "requires_revision"

    def offline(language, code, tests):
        raise SandboxUnavailable("daemon offline")

    monkeypatch.setattr(execution, "execute_code", offline)
    second = start(client, "checkout-underflow")
    for expected in ("queued", "queued", "failed"):
        quality_tasks.quality_run(second)
        with db_factory() as db:
            assert db.get(MutationRun, second).status == expected
            if expected == "queued":
                assert not db.scalars(select(MutationCase).where(MutationCase.run_id == second)).first()


def test_equivalent_mutants_and_publication_gate(client, admin, sandbox, db_factory):
    submission_id, draft = community_draft(client)
    assert draft["id"] >= 200001 and draft["visibility"] == "draft" and draft["tests"] == 4
    slug = draft["slug"]
    assert client.get(f"/api/problems?q={SUBMISSION['title']}").json()["total"] == 0
    blocked = client.post(f"/api/admin/problems/{slug}/publish")
    assert blocked.status_code == 409 and "Run quality validation" in blocked.json()["detail"]

    run_id = start(client, slug)
    drain(db_factory, run_id)
    run = client.get(f"/api/admin/mutation-runs/{run_id}").json()
    # `value >= 0` behaves like `value > 0` in a sum: an equivalent mutant survives.
    assert run["gate_status"] == "requires_revision" and run["survived_mutations"] == 1
    assert run["report"]["tests"]["meaningful_hidden_tests"]
    refused = client.post(f"/api/admin/problems/{slug}/publish")
    assert refused.status_code == 409 and "requires revision" in refused.json()["detail"]
    survivor = client.get(f"/api/admin/mutation-runs/{run_id}/cases?status=survived").json()["items"][0]
    assert ">= 0" in survivor["mutated_snippet"] and survivor["critical"]
    marked = client.patch(f"/api/admin/mutation-cases/{survivor['id']}",
                          json={"is_equivalent": True, "note": "Zero adds nothing to the sum."}).json()
    assert marked["case"]["status"] == "equivalent" and marked["run"]["mutation_score"] == 100.0
    assert marked["run"]["gate_status"] == "approved"
    published = client.post(f"/api/admin/problems/{slug}/publish")
    assert published.status_code == 200 and published.json()["visibility"] == "public"
    assert client.get(f"/api/problems?q={SUBMISSION['title']}").json()["total"] == 1
    with db_factory() as db:
        actions = {row.action for row in db.scalars(select(AuditLog))}
        assert {"problem.draft_created", "quality.run_requested", "quality.mutant_equivalence",
                "problem.published"} <= actions
        assert db.get(ProblemSubmission, submission_id).problem_id == draft["id"]

    # Editing the content makes the approved run stale; the next run records version 2.
    assert client.post(f"/api/admin/problems/{slug}/unpublish").status_code == 200
    with db_factory() as db:
        problem = db.get(Problem, draft["id"])
        problem.tests = [*problem.tests, {"name": "Hidden check 3", "input": {"values": [7]}, "expected": {"total": 7},
                                          "hidden": True, "assertions": []}]
        db.commit()
    assert client.get("/api/admin/quality/overview?gate=stale").json()["items"][0]["slug"] == slug
    stale = client.post(f"/api/admin/problems/{slug}/publish")
    assert stale.status_code == 409 and "current version" in stale.json()["detail"]
    second = start(client, slug)
    with db_factory() as db:
        assert db.get(MutationRun, second).problem_version == 2 and db.get(Problem, draft["id"]).version == 2
    drain(db_factory, second)
    history = client.get(f"/api/admin/problems/{slug}/quality-history").json()
    assert [version["version"] for version in history["versions"]] == [2, 1]
    assert client.post("/api/admin/problems/checkout-underflow/unpublish").status_code == 409


def test_leakage_and_weak_hidden_tests_block_publication(client, admin, sandbox, db_factory):
    _, draft = community_draft(client, title="Leaky positive totals",
                               description='Example hidden check: {"values": [0, 5, -3]} must return five.')
    run_id = start(client, draft["slug"])
    drain(db_factory, run_id)
    run = client.get(f"/api/admin/mutation-runs/{run_id}").json()
    leakage = next(step for step in run["pipeline"] if step["step"] == "solution_leakage")
    assert leakage["status"] == "failed"
    assert any(finding["kind"] == "hidden_test_data" for finding in leakage["data"]["findings"])
    assert any("exposure" in reason for reason in run["report"]["gate"]["reasons"])

    definition = pipeline.definition_from_catalog({
        "slug": "constant", "title": "Constant", "summary": "s", "starters": {"python": "def solve(d):\n    return 1\n"},
        "solutions": {"python": "def solve(d):\n    return 2\n"},
        "tests": [{"name": "a", "input": {"x": 1}, "expected": 2, "hidden": False, "assertions": []},
                  {"name": "b", "input": {"x": 1}, "expected": 2, "hidden": True, "assertions": []}]})
    hidden = pipeline.validate_hidden_tests(definition)
    assert hidden["status"] == "failed"
    schema = pipeline.validate_schema({**definition, "tests": definition["tests"][:1] + [
        {"name": "a", "input": [], "expected": 2, "hidden": "yes",
         "assertions": [{"path": "missing", "equals": 1}]}]}, "python")
    assert schema["status"] == "failed" and len(schema["data"]["errors"]) >= 3


def test_quality_gate_configuration_applies_per_category(client, admin, sandbox, db_factory):
    gates = client.get("/api/admin/quality-gates").json()
    assert gates["defaults"]["min_mutation_score"] == 80.0 and "business" in gates["categories"]
    assert client.put("/api/admin/quality-gates/business", json={"thresholds": {"bogus": 1}}).status_code == 422
    assert client.put("/api/admin/quality-gates/business",
                      json={"thresholds": {"min_mutation_score": 120}}).status_code == 422
    assert client.put("/api/admin/quality-gates/business",
                      json={"thresholds": {"require_stability": "yes"}}).status_code == 422
    assert client.put("/api/admin/quality-gates/unknown", json={"thresholds": {}}).status_code == 404
    saved = client.put("/api/admin/quality-gates/business", json={"thresholds": {"min_critical_kill_percent": 50}})
    assert saved.status_code == 200 and saved.json()["effective"]["min_critical_kill_percent"] == 50
    assert client.put("/api/admin/quality-gates/default", json={"thresholds": {"min_mutation_score": 85}}).status_code == 200
    effective = client.get("/api/admin/quality-gates").json()["effective"]
    assert effective["business"]["min_mutation_score"] == 85 and effective["logic"]["min_critical_kill_percent"] == 100
    run_id = start(client, "inventory-retry")
    drain(db_factory, run_id)
    run = client.get(f"/api/admin/mutation-runs/{run_id}").json()
    assert run["config"]["thresholds"]["min_critical_kill_percent"] == 50 and run["gate_status"] == "approved"
    assert client.delete("/api/admin/quality-gates/business").status_code == 204
    assert client.delete("/api/admin/quality-gates/business").status_code == 404


def test_non_admins_cannot_use_quality_endpoints(client, member, db_factory):
    calls = [("get", "/api/admin/quality/overview"), ("get", "/api/admin/quality-gates"),
             ("post", "/api/admin/problems/checkout-underflow/mutation-runs"),
             ("get", "/api/admin/problems/checkout-underflow/mutation-runs"),
             ("get", "/api/admin/mutation-runs/x"), ("get", "/api/admin/mutation-runs/x/cases"),
             ("patch", "/api/admin/mutation-cases/x"), ("put", "/api/admin/quality-gates/default"),
             ("post", "/api/admin/problems/checkout-underflow/publish"), ("get", "/api/admin/metrics"),
             ("get", "/api/admin/calibration"), ("post", "/api/admin/problem-submissions/x/draft"),
             ("get", "/api/admin/quality/community")]
    for method, path in calls:
        body = {"json": {"is_equivalent": True}} if method == "patch" else {"json": {"thresholds": {}}} \
            if method == "put" else {"json": {}} if method == "post" else {}
        assert getattr(client, method)(path, **body).status_code == 403, path
    client.post("/api/auth/logout")
    assert client.get("/api/admin/quality/overview").status_code == 401


def test_recovery_requeues_stuck_work_and_records_orphans(client, admin, sandbox, db_factory, monkeypatch):
    run_id = start(client, "missing-last-item")
    quality_tasks.quality_run(run_id)
    old = (now() - timedelta(minutes=20)).isoformat()
    with db_factory() as db:
        case = db.scalar(select(MutationCase).where(MutationCase.run_id == run_id))
        case.status, case.attempts, case.detail = "running", 1, {"claimed_at": old}
        stuck = MutationRun(problem_id=1, language="python", status="validating", config={},
                            started_at=now() - timedelta(minutes=40))
        db.add(stuck)
        db.commit()
        stuck_id, case_id = stuck.id, case.id

    class Container:
        def __init__(self, expires):
            self.labels = {"expires_at": str(expires)}

    class Docker:
        def __init__(self, **kwargs):
            self.containers = self

        def list(self, **kwargs):
            return [Container(1), Container(10 ** 12)]

        def close(self):
            pass

    monkeypatch.setattr("docker.DockerClient", Docker)
    assert quality_tasks.recover_quality_jobs() == {"cases": 1, "runs": 0}
    with db_factory() as db:
        assert db.get(MutationCase, case_id).status == "queued"
        assert db.get(MutationRun, stuck_id).status == "failed"
    quality_tasks.mutation_case(case_id)
    with db_factory() as db:
        assert db.get(MutationRun, run_id).status == "completed"
    sandbox_metrics = client.get("/api/admin/metrics").json()["sandbox"]
    assert sandbox_metrics["orphaned_containers"] == 1


def test_cli_validates_catalog_definitions(client, admin, sandbox, db_factory, capsys):
    assert cli(["validate", "checkout-underflow", "--from-catalog", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["gate"]["status"] == "approved" and report["problem"]["slug"] == "checkout-underflow"
    assert cli(["validate", "inventory-retry", "--from-catalog"]) == 1
    assert "requires_revision" in capsys.readouterr().out
    assert cli(["validate", "checkout-underflow", "--from-catalog", "--operators", "bogus"]) == 2
    assert cli(["validate", "no-such-problem", "--from-catalog"]) == 2
    # Database mode records a run and executes it synchronously.
    assert cli(["validate", "missing-last-item", "--max-mutants", "5"]) == 0
    with db_factory() as db:
        run = db.scalar(select(MutationRun).where(MutationRun.status == "completed"))
        assert run is not None and run.config["max_mutants"] == 5
