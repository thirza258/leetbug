"""Production incident challenges (PRD §6): seeding, sessions, investigation, resolution scoring,
administrator authoring and isolation. The sandbox is replaced by an in-process executor for the
repository-authored fixture code below."""
import copy
import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app import execution, scoring
from app.catalog import CATALOG
from app.config import settings
from app.incidents import catalog, seed, validation
from app.incidents.tasks import evaluate_resolution, validate_incident
from app.models import (
    AuditLog,
    ChallengeAttempt,
    Diagnosis,
    Event,
    Incident,
    IncidentResolution,
    IncidentSession,
    Problem,
    Submission,
    now,
)

PASSWORD = "StrongPassword123!"


def fixture_incident(slug="duplicate-charge-fixture"):
    return {
        "slug": slug, "title": "Customers charged twice after timeouts",
        "summary": "A retry after a provider timeout charges the same order again.",
        "severity": "SEV-2", "level": 2, "category": "retry_idempotency",
        "taxonomy": {"bug_categories": ["retry_idempotency", "distributed_consistency"],
                     "skills": ["log_investigation", "reproduction"]},
        "affected_services": ["payments-api", "payment-worker"],
        "impact": ["Some customers are charged twice.", "Support tickets increase."],
        "expected_behavior": "Each idempotency key produces at most one charge.",
        "observed_symptoms": ["Duplicate charges after provider timeouts."],
        "objective": "Stop duplicate charges without breaking legitimate retries.",
        "timeline": [{"at": "2026-03-14T09:12:00Z", "kind": "deploy", "title": "Deploy 2026.03.14-2"},
                     {"at": "2026-03-14T09:40:00Z", "kind": "alert", "title": "Duplicate charge rate above 1%"}],
        "artifacts": [
            {"id": "payments-logs", "type": "logs", "title": "payments-api logs", "description": "Structured logs",
             "data": {"entries": [{"ts": "2026-03-14T09:41:02Z", "level": "warn", "service": "payments-api",
                                   "message": "provider timeout; retrying", "trace_id": "t-1",
                                   "fields": {"order": "o-17", "host": "10.0.3.12"}}]}},
            {"id": "charge-rate", "type": "metrics", "title": "Charges per order", "description": "",
             "data": {"series": [{"name": "charges_per_order", "unit": "ratio",
                                  "points": [["2026-03-14T09:00:00Z", 1.0], ["2026-03-14T09:45:00Z", 1.08]]}],
                      "annotations": [{"at": "2026-03-14T09:12:00Z", "label": "deploy"}]}},
            {"id": "retry-config", "type": "config", "title": "Retry policy", "description": "",
             "data": {"path": "config/payments.yaml", "language": "yaml",
                      "content": "retries: 3\ndatabase: postgres://payments:${DB_PASSWORD}@payments-db/payments\n"}},
        ],
        "scenarios": [{"id": "timeout-retry", "name": "Retry after timeout", "description": "Same key twice.",
                       "tests": ["Retry after timeout"]}],
        "rubric": {"version": 1, "source": "authored", "defect_categories": ["retry_idempotency"],
                   "related_categories": ["distributed_consistency"],
                   "root_cause": [["idempotency key", "idempotency"], ["retry", "retries"]],
                   "component": ["solve", "requests"], "invariant": [["at most once", "charged once"]],
                   "correction": [["deduplicate", "seen"]], "reproduction": [["same key", "retry"]]},
        "evaluation": {"remediation_concepts": [["idempotency key", "dedupe"], ["refund", "reverse"]],
                       "prevention_concepts": [["regression test", "test"], ["alert", "monitor"]],
                       "impact_concepts": [["customers", "users"], ["duplicate", "twice"]]},
        "problem": {
            "title": "Charged twice", "summary": "Deduplicate charges by idempotency key.",
            "category": "business", "difficulty": "medium", "tags": ["idempotency", "retries"],
            "requirements": ["Return {charges: n}, one charge per distinct key."],
            "starters": {"python": '''
                def solve(data):
                    charged = []
                    for request in data["requests"]:
                        charged.append(request["key"])
                    return {"charges": len(charged)}
            '''},
            "solutions": {"python": '''
                def solve(data):
                    seen = set()
                    for request in data["requests"]:
                        seen.add(request["key"])
                    return {"charges": len(seen)}
            '''},
            "tests": [
                {"name": "Retry after timeout", "input": {"requests": [{"key": "a"}, {"key": "a"}]},
                 "expected": {"charges": 1}, "hidden": False, "assertions": []},
                {"name": "Single request", "input": {"requests": [{"key": "a"}]}, "expected": {"charges": 1},
                 "hidden": False, "assertions": []},
                {"name": "Two customers", "input": {"requests": [{"key": "a"}, {"key": "b"}, {"key": "a"}]},
                 "expected": {"charges": 2}, "hidden": True, "assertions": []},
                {"name": "No requests", "input": {"requests": []}, "expected": {"charges": 0}, "hidden": True,
                 "assertions": []},
            ],
            "explanation": "Charge each idempotency key once.",
            "hints": ["What makes a retry different from a new order?", "Look at what is stored per request.",
                      "Track processed keys and skip repeats."],
            "minutes": 20,
        },
    }


def run_in_process(language, code, tests):
    """Stand-in for the sandbox: executes repository-authored Python fixture code."""
    assert language == "python"
    namespace = {}
    exec(compile(code, "fixture", "exec"), namespace)
    results = []
    for test in tests:
        try:
            output = namespace["solve"](copy.deepcopy(test["input"]))
            results.append({"status": "ok", "output": json.loads(json.dumps(output)), "runtime_ms": 1})
        except Exception as exc:  # The program under test may crash; the grader records it.
            results.append({"status": "runtime_error", "stderr": type(exc).__name__})
    return {"results": results, "runtime_ms": 3, "memory_kb": 100}


@pytest.fixture
def fixture_catalog(monkeypatch):
    """Replace the bundled catalog before the database is seeded."""
    monkeypatch.setattr(catalog, "INCIDENTS", [fixture_incident()])
    return catalog.INCIDENTS


def register(client, name):
    result = client.post("/api/auth/register", json={"email": f"{name}@example.com", "username": name,
                                                     "password": PASSWORD})
    assert result.status_code == 201, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result.json()["user"]


def login(client, email):
    result = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]


def start(client, slug="duplicate-charge-fixture"):
    response = client.post(f"/api/incidents/{slug}/sessions")
    assert response.status_code in (200, 201), response.text
    return response.json()


def add_diagnosis(db_factory, user_id, session_id, *, score=80.0, reproduction=0.5):
    with db_factory() as db:
        attempt = db.scalar(select(ChallengeAttempt).where(ChallengeAttempt.scope == f"incident:{session_id}"))
        row = Diagnosis(user_id=user_id, problem_id=attempt.problem_id, attempt_id=attempt.id,
                        defect_category="retry_idempotency", root_cause="Retries reuse no idempotency key check.",
                        affected_component="solve", violated_invariant="Each key is charged at most once.",
                        proposed_correction="Track processed keys.", reproduction_strategy="Send the same key twice.",
                        score=score, deterministic_score=score,
                        evaluation_details={"criteria": {"reproduction": {"score": reproduction}}})
        db.add(row)
        db.commit()
        return attempt.id, row.id


def add_submission(db_factory, user_id, attempt_id, *, kind, status, minutes_ago=5):
    with db_factory() as db:
        attempt = db.get(ChallengeAttempt, attempt_id)
        results = [{"name": f"case {i}", "hidden": i > 1, "status": "passed" if status == "passed" else "failed"}
                   for i in range(1, 5)]
        row = Submission(user_id=user_id, problem_id=attempt.problem_id, language="python", mode="manual", kind=kind,
                         code="def solve(data): return {}", status=status, results=results, attempt_id=attempt_id,
                         created_at=now() - timedelta(minutes=minutes_ago), completed_at=now())
        db.add(row)
        db.commit()
        return row.id


def resolution_body(tests=None):
    return {
        "impact_assessment": "About 120 customers were charged twice during the 40 minute window. "
                             "Support tickets rose sharply.",
        "remediation": "Refund the duplicate charges and deploy the idempotency key check on retries.",
        "prevention": "Add a regression test for retried requests and an alert on the duplicate charge rate.",
        "regression_tests": tests if tests is not None else [
            {"name": "duplicate key", "input": {"requests": [{"key": "x"}, {"key": "x"}]}, "expected": {"charges": 1}},
            {"name": "single key", "input": {"requests": [{"key": "x"}]}, "expected": {"charges": 1}},
            {"name": "wrong expectation", "input": {"requests": [{"key": "x"}]}, "expected": {"charges": 5}},
        ],
    }


# ── seeding and visibility ───────────────────────────────────────────────────────────


def test_seed_is_insert_only_with_reserved_ids(fixture_catalog, client, db_factory, monkeypatch):
    monkeypatch.setattr(catalog, "INCIDENTS", [fixture_incident(), fixture_incident("second-fixture")])
    with db_factory() as db:
        seed.seed_incidents(db)
        db.commit()
        first = db.get(Problem, 100001)
        first.title = "Locally edited"
        db.commit()
        seed.seed_incidents(db)
        seed.seed_incidents(db)
        db.commit()
        incidents = list(db.scalars(select(Incident).order_by(Incident.id)))
        assert [(row.id, row.slug, row.problem_id) for row in incidents] == [
            (1, "duplicate-charge-fixture", 100001), (2, "second-fixture", 100002)]
        assert db.get(Problem, 100001).title == "Locally edited"
        problem = db.get(Problem, 100002)
        assert problem.slug == "incident-second-fixture" and problem.visibility == "incident"
        assert problem.diagnosis_mode == "required" and problem.diagnosis_rubric["defect_categories"] == ["retry_idempotency"]
        assert problem.taxonomy["bug_categories"][0] == "retry_idempotency"
        assert problem.extra == {"incident_slug": "second-fixture"}
        assert problem.starters["python"].startswith("def solve(data):\n")
        assert problem.content_hash == validation.content_hash(
            {"starters": problem.starters, "solutions": problem.solutions, "tests": problem.tests})
        config = incidents[0].evaluation_config
        assert config["weights"] == scoring.INCIDENT_WEIGHTS and config["objective"].startswith("Stop duplicate")
        assert config["concepts"]["impact_concepts"][0] == ["customers", "users"]


def test_incidents_are_hidden_from_the_library(fixture_catalog, client, member):
    assert client.get("/api/problems").json()["total"] == len(CATALOG)
    assert client.get("/api/meta").json()["problem_count"] == len(CATALOG)
    assert client.get("/api/problems?q=Charged twice").json()["total"] == 0
    assert client.get("/api/problems/incident-duplicate-charge-fixture").status_code == 404
    listing = client.get("/api/incidents").json()["items"]
    assert [row["slug"] for row in listing] == ["duplicate-charge-fixture"]
    assert listing[0]["category"] == {"id": "retry_idempotency", "name": "Retry and idempotency"}
    assert listing[0]["my_session"] is None and listing[0]["artifact_count"] == 3
    overview = client.get("/api/incidents/duplicate-charge-fixture").json()
    assert [a["id"] for a in overview["artifacts"]] == ["payments-logs", "charge-rate", "retry-config"]
    assert all("data" not in artifact for artifact in overview["artifacts"])
    assert overview["problem_slug"] == "incident-duplicate-charge-fixture"
    assert "solutions" not in json.dumps(overview) and "rubric" not in overview
    assert client.get("/api/incidents/missing").status_code == 404


# ── sessions, artifacts and isolation ────────────────────────────────────────────────


def test_session_payload_resume_and_isolation(fixture_catalog, client, member, db_factory, monkeypatch):
    created = client.post("/api/incidents/duplicate-charge-fixture/sessions")
    assert created.status_code == 201
    payload = created.json()
    session_id = payload["session"]["id"]
    again = client.post("/api/incidents/duplicate-charge-fixture/sessions")
    assert again.status_code == 200 and again.json()["session"]["id"] == session_id
    assert payload["incident"]["artifacts"][0]["data"]["entries"][0]["trace_id"] == "t-1"
    problem = payload["problem"]
    assert problem["slug"] == "incident-duplicate-charge-fixture" and problem["visibility"] == "incident"
    assert {"solutions", "tests", "hints", "explanation", "diagnosis_rubric"}.isdisjoint(problem)
    assert [test["name"] for test in problem["public_tests"]] == ["Retry after timeout", "Single request"]
    assert problem["hidden_test_count"] == 2 and problem["diagnosis_required"]
    assert "Two customers" not in json.dumps(payload) and "seen = set()" not in json.dumps(payload)
    assert payload["diagnosis"] == {"required": True, "submitted": False, "latest": None}
    with db_factory() as db:
        attempt = db.scalar(select(ChallengeAttempt).where(ChallengeAttempt.scope == f"incident:{session_id}"))
        assert attempt.context == "incident" and attempt.incident_session_id == session_id
        assert db.scalar(select(func.count()).select_from(Event).where(Event.type == "incident.session_started")) == 1
    # The owner can now open the incident's code; the listing shows the session.
    assert client.get("/api/problems/incident-duplicate-charge-fixture").status_code == 200
    assert client.get("/api/incidents").json()["items"][0]["my_session"]["id"] == session_id
    viewed = client.post(f"/api/incidents/sessions/{session_id}/artifacts/payments-logs/view")
    assert viewed.status_code == 200 and viewed.json()["first_view"]
    attempt_id, _ = add_diagnosis(db_factory, member["id"], session_id)
    add_submission(db_factory, member["id"], attempt_id, kind="submit", status="failed")
    client.post(f"/api/incidents/sessions/{session_id}/resolve", json=resolution_body())
    resolution_id = client.get(f"/api/incidents/sessions/{session_id}").json()["resolutions"][0]["id"]

    register(client, "intruder")
    assert client.get(f"/api/incidents/sessions/{session_id}").status_code == 404
    assert client.post(f"/api/incidents/sessions/{session_id}/artifacts/payments-logs/view").status_code == 404
    assert client.get(f"/api/incidents/resolutions/{resolution_id}").status_code == 404
    assert client.post(f"/api/incidents/sessions/{session_id}/resolve", json=resolution_body()).status_code == 404
    assert client.get("/api/problems/incident-duplicate-charge-fixture").status_code == 404
    assert client.post("/api/submissions", json={"problem_id": 100001, "language": "python", "kind": "run",
                                                 "code": "def solve(data): return 0",
                                                 "incident_session_id": session_id}).status_code == 422
    assert client.get("/api/incidents").json()["items"][0]["my_session"] is None
    # The intruder's own session is separate and starts clean.
    own = start(client)
    assert own["session"]["id"] != session_id and own["resolutions"] == []
    assert own["session"]["investigation"]["viewed"] == {}
    # Administrators may inspect any session but never add investigation evidence to it.
    monkeypatch.setattr(settings, "admin_email", "intruder@example.com")
    assert client.get(f"/api/incidents/sessions/{session_id}").status_code == 200
    assert client.get(f"/api/incidents/resolutions/{resolution_id}").status_code == 200
    assert client.post(f"/api/incidents/sessions/{session_id}/artifacts/charge-rate/view").status_code == 404


def test_artifact_view_tracking(fixture_catalog, client, member, db_factory):
    session_id = start(client)["session"]["id"]
    assert client.post(f"/api/incidents/sessions/{session_id}/artifacts/missing/view").status_code == 404
    for artifact in ("payments-logs", "charge-rate", "payments-logs"):
        assert client.post(f"/api/incidents/sessions/{session_id}/artifacts/{artifact}/view").status_code == 200
    investigation = client.get(f"/api/incidents/sessions/{session_id}").json()["session"]["investigation"]
    assert set(investigation["viewed"]) == {"payments-logs", "charge-rate"}
    assert investigation["viewed_types"] == ["logs", "metrics"]
    assert investigation["available_types"] == ["config", "logs", "metrics"]
    assert investigation["coverage"] == pytest.approx(2 / 3, abs=1e-3)
    with db_factory() as db:
        events = list(db.scalars(select(Event).where(Event.type == "incident.artifact_viewed").order_by(Event.id)))
        assert [event.data["artifact_id"] for event in events] == ["payments-logs", "charge-rate", "payments-logs"]
        assert [event.data["first_view"] for event in events] == [True, True, False]
        assert all(event.incident_session_id == session_id and event.user_id == member["id"] for event in events)
        assert db.get(IncidentSession, session_id).investigation["view_count"] == 3


def test_incident_submissions_need_a_diagnosis_and_use_the_incident_attempt(fixture_catalog, client, member,
                                                                            db_factory):
    session_id = start(client)["session"]["id"]
    body = {"problem_id": 100001, "language": "python", "code": "def solve(data): return {}",
            "incident_session_id": session_id}
    blocked = client.post("/api/submissions", json={**body, "kind": "submit"})
    assert blocked.status_code == 428
    run = client.post("/api/submissions", json={**body, "kind": "run"})
    assert run.status_code == 202
    add_diagnosis(db_factory, member["id"], session_id)
    submitted = client.post("/api/submissions", json={**body, "kind": "submit"})
    assert submitted.status_code == 202
    with db_factory() as db:
        attempt = db.scalar(select(ChallengeAttempt).where(ChallengeAttempt.scope == f"incident:{session_id}"))
        rows = list(db.scalars(select(Submission).where(Submission.problem_id == 100001)))
        assert {row.attempt_id for row in rows} == {attempt.id} and len(rows) == 2
        assert all(row.assessment_session_id is None for row in rows)
    # Incident work never appears as library progress.
    assert client.get("/api/problems?status=attempted").json()["total"] == 0
    payload = client.get(f"/api/incidents/sessions/{session_id}").json()
    assert payload["diagnosis"]["submitted"] and payload["session"]["investigation"]["runs"] == 1
    assert [row["kind"] for row in payload["submissions"]] == ["submit", "run"]


# ── resolution evaluation ────────────────────────────────────────────────────────────


def test_resolution_regression_tests_and_score_breakdown(fixture_catalog, client, member, db_factory, monkeypatch):
    monkeypatch.setattr(execution, "execute_code", run_in_process)
    session_id = start(client)["session"]["id"]
    for artifact in ("payments-logs", "charge-rate"):
        client.post(f"/api/incidents/sessions/{session_id}/artifacts/{artifact}/view")
    attempt_id, diagnosis_id = add_diagnosis(db_factory, member["id"], session_id, score=80.0, reproduction=0.5)
    add_submission(db_factory, member["id"], attempt_id, kind="run", status="failed", minutes_ago=9)
    passed_id = add_submission(db_factory, member["id"], attempt_id, kind="submit", status="passed", minutes_ago=4)
    response = client.post(f"/api/incidents/sessions/{session_id}/resolve",
                           json={**resolution_body(), "submission_id": passed_id})
    assert response.status_code == 202, response.text
    resolution = response.json()
    assert resolution["status"] == "queued" and resolution["diagnosis_id"] == diagnosis_id
    evaluate_resolution(resolution["id"])
    evaluate_resolution(resolution["id"])  # Redelivery is a no-op.
    row = client.get(f"/api/incidents/resolutions/{resolution['id']}").json()
    assert row["status"] == "evaluated", row
    flags = [(r["name"], r["valid"], r["detects_bug"], r["credit"]) for r in row["regression_results"]]
    assert flags == [("duplicate key", True, True, 1.0), ("single key", True, False, 0.3),
                     ("wrong expectation", False, False, 0.0)]
    # Validity flags only: the reference implementation's outputs never reach the user.
    assert all({"output", "actual", "expected_output"}.isdisjoint(r) for r in row["regression_results"])
    # The linked submission returns {} — informational only, it never changes the score.
    assert row["regression_results"][0]["your_fix_status"] == "failed"
    components = row["scores"]["components"]
    assert components["root_cause"] == 80.0 and components["fix"] == 100.0
    assert components["investigation"] == pytest.approx((0.5 * 0.5 + 0.25 * 2 / 3 + 0.25) * 100, abs=0.01)
    assert components["regression"] == pytest.approx(130 / 3, abs=0.01)
    assert components["remediation"] == 100.0 and components["communication"] == 100.0
    expected_total = scoring.weighted(components, scoring.INCIDENT_WEIGHTS, missing="zero")
    assert row["score"] == expected_total == pytest.approx(81.5, abs=0.01)
    assert row["scores"]["outcome"] == {"fixed_immediate_defect": True, "prevented_recurrence": False,
                                        "detecting_regression_tests": 1}
    assert row["scores"]["details"]["ran_reproduction_before_resolving"] is True
    assert row["scores"]["versions"]["incident_scoring"] == "incident-scoring-v1"
    payload = client.get(f"/api/incidents/sessions/{session_id}").json()
    assert payload["session"]["status"] == "resolved" and payload["session"]["score"] == row["score"]
    assert payload["session"]["scores"]["best_resolution_id"] == resolution["id"]
    assert client.get("/api/incidents").json()["items"][0]["best_score"] == row["score"]
    # A resolved session is closed for further work; a new investigation starts a fresh session.
    assert client.post(f"/api/incidents/sessions/{session_id}/resolve", json=resolution_body()).status_code == 409
    assert start(client)["session"]["id"] != session_id


def test_unfixed_incident_scores_zero_fix_and_stays_open(fixture_catalog, client, member, db_factory, monkeypatch):
    monkeypatch.setattr(execution, "execute_code", run_in_process)
    session_id = start(client)["session"]["id"]
    attempt_id, _ = add_diagnosis(db_factory, member["id"], session_id, score=40.0, reproduction=0.0)
    add_submission(db_factory, member["id"], attempt_id, kind="submit", status="failed")
    body = {**resolution_body([]), "remediation": "We will look at it again tomorrow morning.",
            "prevention": "Nothing specific comes to mind right now."}
    resolution_id = client.post(f"/api/incidents/sessions/{session_id}/resolve", json=body).json()["id"]
    evaluate_resolution(resolution_id)
    row = client.get(f"/api/incidents/resolutions/{resolution_id}").json()
    components = row["scores"]["components"]
    assert row["status"] == "evaluated" and components["fix"] == 0.0 and components["regression"] == 0.0
    assert components["investigation"] == 0.0 and components["remediation"] == 0.0
    assert row["scores"]["outcome"]["fixed_immediate_defect"] is False
    assert client.get(f"/api/incidents/sessions/{session_id}").json()["session"]["status"] == "active"


def test_resolution_preconditions_and_limits(fixture_catalog, client, member, db_factory):
    session_id = start(client)["session"]["id"]
    url = f"/api/incidents/sessions/{session_id}/resolve"
    assert client.post(url, json=resolution_body()).status_code == 428
    attempt_id, _ = add_diagnosis(db_factory, member["id"], session_id)
    too_many = [{"name": f"t{i}", "input": {"requests": []}, "expected": {"charges": 0}} for i in range(11)]
    assert client.post(url, json=resolution_body(too_many)).status_code == 422
    huge = [{"name": "big", "input": {"requests": [{"key": "x" * 6000}]}, "expected": {"charges": 1}}]
    assert "5 KB" in client.post(url, json=resolution_body(huge)).json()["detail"]
    duplicate = [{"name": "same", "input": {}, "expected": 1}, {"name": "same", "input": {}, "expected": 2}]
    assert client.post(url, json=resolution_body(duplicate)).status_code == 422
    assert client.post(url, json={**resolution_body(), "remediation": "short"}).status_code == 422
    with db_factory() as db:
        practice = Submission(user_id=member["id"], problem_id=1, language="python", mode="manual", kind="submit",
                              code="x", status="passed", results=[])
        db.add(practice)
        db.commit()
        foreign_id = practice.id
    assert client.post(url, json={**resolution_body(), "submission_id": foreign_id}).status_code == 404
    first = client.post(url, json=resolution_body())
    assert first.status_code == 202
    assert client.post(url, json=resolution_body()).status_code == 409
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(IncidentResolution)) == 1
        assert db.get(ChallengeAttempt, attempt_id).context == "incident"


def test_infrastructure_failure_is_retryable_not_a_user_failure(fixture_catalog, client, member, db_factory,
                                                               monkeypatch):
    def unavailable(*args):
        raise execution.SandboxUnavailable("offline")
    monkeypatch.setattr(execution, "execute_code", unavailable)
    session_id = start(client)["session"]["id"]
    attempt_id, _ = add_diagnosis(db_factory, member["id"], session_id)
    resolution_id = client.post(f"/api/incidents/sessions/{session_id}/resolve", json=resolution_body()).json()["id"]
    evaluate_resolution(resolution_id)
    row = client.get(f"/api/incidents/resolutions/{resolution_id}").json()
    assert row["status"] == "error" and row["score"] is None and "retry" in row["error"].lower()
    assert client.get(f"/api/incidents/sessions/{session_id}").json()["session"]["score"] is None
    assert client.post(f"/api/incidents/resolutions/{resolution_id}/retry").json()["status"] == "queued"
    assert client.post(f"/api/incidents/resolutions/{resolution_id}/retry").status_code == 409
    monkeypatch.setattr(execution, "execute_code", run_in_process)
    evaluate_resolution(resolution_id)
    assert client.get(f"/api/incidents/resolutions/{resolution_id}").json()["status"] == "evaluated"


def test_stale_evaluation_becomes_retryable(fixture_catalog, client, member, db_factory):
    session_id = start(client)["session"]["id"]
    add_diagnosis(db_factory, member["id"], session_id)
    resolution_id = client.post(f"/api/incidents/sessions/{session_id}/resolve", json=resolution_body()).json()["id"]
    with db_factory() as db:
        row = db.get(IncidentResolution, resolution_id)
        row.status, row.created_at = "running", now() - timedelta(minutes=30)
        db.commit()
    assert client.get(f"/api/incidents/resolutions/{resolution_id}").json()["status"] == "error"
    # A stuck evaluation no longer blocks a new resolution.
    assert client.post(f"/api/incidents/sessions/{session_id}/resolve", json=resolution_body()).status_code == 202


# ── administrator authoring and publication ─────────────────────────────────────────


def test_admin_create_validate_and_publish(fixture_catalog, client, member, db_factory, monkeypatch):
    definition = fixture_incident("cache-stampede-draft")
    assert client.post("/api/admin/incidents", json=definition).status_code == 403
    assert client.get("/api/admin/incidents").status_code == 403
    monkeypatch.setattr(settings, "admin_email", member["email"])
    invalid = {**definition, "severity": "SEV-9", "scenarios": [{"id": "x", "name": "x", "tests": ["Two customers"]}]}
    rejected = client.post("/api/admin/incidents", json=invalid)
    assert rejected.status_code == 422
    assert "severity" in rejected.json()["detail"] and "non-public or unknown" in rejected.json()["detail"]
    leaked = copy.deepcopy(definition)
    leaked["artifacts"][2]["data"]["content"] += "aws_key: AKIAABCDEFGHIJKLMNOP\n"
    assert "AWS access key" in client.post("/api/admin/incidents", json=leaked).json()["detail"]
    created = client.post("/api/admin/incidents", json=definition)
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "draft" and draft["problem_id"] > 105000 and draft["id"] > 5000
    assert client.post("/api/admin/incidents", json=definition).status_code == 409
    # Drafts are invisible to learners and cannot be published before a passing validation.
    assert client.post("/api/admin/incidents/cache-stampede-draft/publish").status_code == 409
    queued = client.post("/api/admin/incidents/cache-stampede-draft/validate")
    assert queued.status_code == 202 and queued.json()["validation"]["status"] == "queued"
    assert client.post("/api/admin/incidents/cache-stampede-draft/validate").status_code == 409
    monkeypatch.setattr(execution, "execute_code", run_in_process)
    validate_incident(draft["id"])
    detail = client.get("/api/admin/incidents/cache-stampede-draft").json()
    assert detail["validation"]["status"] == "passed" and detail["validation"]["current"]
    assert detail["validation"]["checks"][0]["reproduced_scenarios"] == ["Retry after timeout"]
    published = client.post("/api/admin/incidents/cache-stampede-draft/publish")
    assert published.status_code == 200 and published.json()["status"] == "published"
    monkeypatch.setattr(settings, "admin_email", "")
    assert "cache-stampede-draft" in [row["slug"] for row in client.get("/api/incidents").json()["items"]]
    monkeypatch.setattr(settings, "admin_email", member["email"])
    assert client.post("/api/admin/incidents/cache-stampede-draft/unpublish").json()["status"] == "draft"
    monkeypatch.setattr(settings, "admin_email", "")
    assert client.get("/api/incidents/cache-stampede-draft").status_code == 404
    assert client.post("/api/incidents/cache-stampede-draft/sessions").status_code == 404
    with db_factory() as db:
        actions = list(db.scalars(select(AuditLog.action).where(AuditLog.entity_id == "cache-stampede-draft")
                                  .order_by(AuditLog.id)))
        assert actions == ["incident.created", "incident.validation_requested", "incident.published",
                           "incident.unpublished"]


def test_validation_fails_when_the_defect_does_not_reproduce(fixture_catalog, client, member, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", member["email"])
    definition = fixture_incident("silent-draft")
    # The starter equals the reference behaviour, so the documented failure cannot be reproduced.
    definition["problem"]["starters"]["python"] = '''
        def solve(data):
            return {"charges": len({request["key"] for request in data["requests"]})}
    '''
    draft = client.post("/api/admin/incidents", json=definition).json()
    client.post("/api/admin/incidents/silent-draft/validate")
    monkeypatch.setattr(execution, "execute_code", run_in_process)
    validate_incident(draft["id"])
    state = client.get("/api/admin/incidents/silent-draft").json()["validation"]
    assert state["status"] == "failed" and state["checks"][0]["reproduced_scenarios"] == []
    assert client.post("/api/admin/incidents/silent-draft/publish").status_code == 409


def test_bundled_incident_catalog_is_valid_and_seeded(client, db_factory):
    if not catalog.INCIDENTS:
        pytest.skip("The incident catalog has no entries yet.")
    with db_factory() as db:
        for index, item in enumerate(catalog.INCIDENTS, 1):
            assert validation.validate_definition(item) == [], item["slug"]
            incident = db.get(Incident, index)
            assert incident is not None and incident.slug == item["slug"] and incident.status == "published"
            problem = db.get(Problem, 100000 + index)
            assert problem.slug == f"incident-{item['slug']}" and problem.visibility == "incident"
            assert incident.problem_id == problem.id
    listing = {row["slug"] for row in client.get("/api/incidents").json()["items"]}
    assert listing == {item["slug"] for item in catalog.INCIDENTS}
    assert client.get("/api/problems").json()["total"] == len(CATALOG)


def test_incident_diagnosis_alias(fixture_catalog, client, member):
    """Runs once the diagnosis service (implemented separately) replaces its stub."""
    from app.diagnosis import service as diagnosis_service

    if (diagnosis_service.__doc__ or "").lstrip().startswith("STUB"):
        pytest.skip("The diagnosis service is not integrated yet.")
    session_id = start(client)["session"]["id"]
    response = client.post(f"/api/incidents/sessions/{session_id}/diagnosis", json={
        "defect_category": "retry_idempotency",
        "root_cause": "A retried request after a provider timeout is charged again because no idempotency key "
                      "is checked before charging.",
        "affected_component": "solve, the loop over requests",
        "violated_invariant": "Each idempotency key is charged at most once.",
        "proposed_correction": "Deduplicate by key: track the keys already seen and skip repeats.",
        "reproduction_strategy": "Send the same key twice, as a retry after a timeout would.",
    })
    assert response.status_code == 201, response.text
    payload = client.get(f"/api/incidents/sessions/{session_id}").json()
    assert payload["diagnosis"]["submitted"] and payload["diagnosis"]["latest"]["id"] == response.json()["id"]
    register(client, "outsider")
    assert client.post(f"/api/incidents/sessions/{session_id}/diagnosis",
                       json={"defect_category": "x", "root_cause": "x", "affected_component": "x",
                             "violated_invariant": "x", "proposed_correction": "x",
                             "reproduction_strategy": "x"}).status_code == 404
