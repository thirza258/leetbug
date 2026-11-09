import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app import tasks
from app.catalog import CATALOG
from app.config import settings
from app.diagnosis import tasks as diagnosis_tasks
from app.diagnosis.rubric import derive_rubric, rubric_for, validate_rubric
from app.diagnosis.scorer import score_diagnosis, score_explanation
from app.diagnosis.text import shingles
from app.llm import AIUnavailable
from app.models import (
    Assessment,
    AssessmentSession,
    AuditLog,
    ChallengeAttempt,
    Diagnosis,
    Problem,
    Submission,
    now,
)

EVAL = json.loads((Path(__file__).parent / "fixtures" / "diagnosis_eval.json").read_text())
GOOD = EVAL["problems"]["checkout-underflow"]["correct"]
POOR = EVAL["problems"]["checkout-underflow"]["incorrect"]
FIELDS = ("root_cause", "affected_component", "violated_invariant", "proposed_correction", "reproduction_strategy")
EXPLANATION = {
    "why_failed": "The total subtracted the discount without clamping, so a discount larger than the subtotal made the charge negative, and negative discounts were never validated.",
    "why_works": "Prices and the discount are clamped to nonnegative values, and the final total is clamped to zero with max, so subtracting can no longer cross zero.",
    "invariant_preserved": "The final total must never be negative and a discount must never increase the bill.",
    "side_effects": "No other callers depend on negative totals; the receipt format is unchanged, so there is no compatibility risk.",
    "additional_tests": "1. prices [100], discount 500 returns total 0\n2. prices [-5, 10], discount -3 returns total 10\n3. empty prices with discount 1 returns total 0",
}


def catalog_problem(slug):
    item = next(item for item in CATALOG if item["slug"] == slug)
    return SimpleNamespace(**item, rubric_version=1, diagnosis_rubric=None, taxonomy=None, id=1, extra=None)


def diagnose(client, slug="checkout-underflow", body=None, **extra):
    return client.post(f"/api/problems/{slug}/diagnosis", json={**(body or GOOD), **extra})


def passing_submission(client, monkeypatch, problem_id=1, code="def solve(data): return {'total': 0}", **extra):
    def execute(language, source, tests_):
        return {"results": [{"status": "ok", "output": test["expected"], "runtime_ms": 1} for test in tests_],
                "runtime_ms": 40, "memory_kb": 300}
    monkeypatch.setattr(tasks, "execute_code", execute)
    response = client.post("/api/submissions", json={"problem_id": problem_id, "language": "python", "code": code,
                                                     **extra})
    assert response.status_code == 202, response.text
    tasks.evaluate(response.json()["id"])
    return response.json()["id"]


def make_admin(monkeypatch, member):
    monkeypatch.setattr(settings, "admin_email", member["email"])


def test_every_catalog_problem_has_a_usable_derived_rubric():
    for item in CATALOG:
        rubric = derive_rubric(catalog_problem(item["slug"]))
        assert not validate_rubric(rubric), item["slug"]
        assert len(rubric["root_cause"]) >= 3, item["slug"]
        assert rubric["component"] and rubric["defect_categories"], item["slug"]
        assert rubric == derive_rubric(catalog_problem(item["slug"])), "derivation must be stable"


def test_diagnosis_submission_validation_ownership_and_history(client, member, db_factory):
    assert diagnose(client, defect_category="not-a-category").status_code == 422
    assert diagnose(client, body={**GOOD, "root_cause": "   "}).status_code == 422
    assert diagnose(client, body={**GOOD, "root_cause": "x" * 4001}).status_code == 422
    assert diagnose(client, slug="unknown-case").status_code == 404
    first = diagnose(client)
    assert first.status_code == 201, first.text
    row = first.json()
    assert row["revision"] == 1 and row["score"] >= 60 and row["passed"]
    assert set(row["criteria"]) == {"defect_category", "root_cause", "invariant", "correction", "reproduction"}
    assert all(item["level"] in {"strong", "partial", "missing"} for item in row["criteria"].values())
    second = diagnose(client, body=POOR)
    assert second.json()["revision"] == 2 and second.json()["score"] < 60
    status = client.get("/api/problems/checkout-underflow/diagnosis").json()
    assert status["submitted"] and status["latest"]["id"] == second.json()["id"]
    assert [item["revision"] for item in status["history"]] == [2, 1]
    assert status["context"] == "practice" and len(status["categories"]) >= 17
    history = client.get("/api/diagnosis/history").json()
    assert history["total"] == 2 and history["items"][0]["problem_slug"] == "checkout-underflow"
    assert client.get(f"/api/diagnosis/{row['id']}").status_code == 200

    client.post("/api/auth/logout")
    assert client.get(f"/api/diagnosis/{row['id']}").status_code == 401
    other = client.post("/api/auth/register", json={"email": "other@example.com", "username": "other",
                                                     "password": "StrongPassword123!"}).json()
    client.headers["X-CSRF-Token"] = other["csrf_token"]
    assert client.get(f"/api/diagnosis/{row['id']}").status_code == 404
    assert client.post(f"/api/diagnosis/{row['id']}/evaluate").status_code == 404
    assert client.get("/api/diagnosis/history").json()["total"] == 0
    assert not client.get("/api/problems/checkout-underflow/diagnosis").json()["submitted"]


def test_status_lookup_does_not_create_an_attempt(client, member, db_factory):
    status = client.get("/api/problems/missing-last-item/diagnosis").json()
    assert status["attempt_id"] is None and not status["submitted"] and not status["required"]
    with db_factory() as db:
        assert db.scalar(select(ChallengeAttempt)) is None


def test_passing_patch_does_not_imply_passing_diagnosis(client, member, monkeypatch):
    assert diagnose(client, body=POOR).status_code == 201
    passing_submission(client, monkeypatch)
    scores = client.get("/api/problems/checkout-underflow/scores").json()["attempt"]
    assert scores["correctness"] == 100 and scores["status"] == "solved"
    assert scores["diagnosis"] < 60, "a correct patch must not raise the diagnosis score"
    assert scores["quality"] is not None
    status = client.get("/api/problems/checkout-underflow/diagnosis").json()
    assert not status["latest"]["passed"] and status["solved"]


def test_required_diagnosis_gates_full_submissions_but_not_runs(client, member, db_factory):
    with db_factory() as db:
        db.scalar(select(Problem).where(Problem.slug == "checkout-underflow")).diagnosis_mode = "required"
        db.commit()
    assert client.get("/api/problems/checkout-underflow").json()["diagnosis_required"]
    body = {"problem_id": 1, "language": "python", "code": "def solve(data): return 0"}
    assert client.post("/api/submissions", json={**body, "kind": "run"}).status_code == 202
    blocked = client.post("/api/submissions", json=body)
    assert blocked.status_code == 428
    status = client.get("/api/problems/checkout-underflow/diagnosis").json()
    assert status["required"] and not status["submitted"]
    diagnosis = diagnose(client).json()
    accepted = client.post("/api/submissions", json=body)
    assert accepted.status_code == 202 and accepted.json()["diagnosis_id"] == diagnosis["id"]


def test_diagnosis_disabled_mode(client, member, db_factory):
    with db_factory() as db:
        db.scalar(select(Problem).where(Problem.slug == "checkout-underflow")).diagnosis_mode = "off"
        db.commit()
    assert diagnose(client).status_code == 409
    assert not client.get("/api/problems/checkout-underflow/diagnosis").json()["enabled"]


def test_scores_are_deterministic_and_independent_of_patch_results():
    problem = catalog_problem("wallet-race")
    rubric = rubric_for(problem)
    fields = EVAL["problems"]["wallet-race"]["correct"]
    first, second = score_diagnosis(problem, fields, rubric), score_diagnosis(problem, fields, rubric)
    assert first == second and first["evaluator_version"] == "deterministic-v1"
    explanation = score_explanation(catalog_problem("checkout-underflow"), EXPLANATION,
                                    rubric_for(catalog_problem("checkout-underflow")))
    assert explanation == score_explanation(catalog_problem("checkout-underflow"), EXPLANATION,
                                            rubric_for(catalog_problem("checkout-underflow")))


@pytest.mark.parametrize("slug", sorted(EVAL["problems"]))
def test_curated_evaluation_dataset_orders_diagnoses(slug):
    problem = catalog_problem(slug)
    rubric = rubric_for(problem)
    scores = {name: score_diagnosis(problem, fields, rubric)["score"] for name, fields in EVAL["problems"][slug].items()}
    assert scores["correct"] > scores["ambiguous"] > scores["partial"] > scores["incorrect"], scores
    assert scores["correct"] >= 60 > scores["incorrect"]


def test_restated_symptom_and_unreadable_answers_score_low():
    problem = catalog_problem("checkout-underflow")
    rubric = rubric_for(problem)
    restated = {**GOOD, "root_cause": problem.summary}
    assert score_diagnosis(problem, restated, rubric)["criteria"]["root_cause"]["score"] < \
        score_diagnosis(problem, GOOD, rubric)["criteria"]["root_cause"]["score"]
    noise = {key: "asdf asdf asdf asdf asdf asdf" for key in FIELDS} | {"defect_category": "validation"}
    result = score_diagnosis(problem, noise, rubric)
    assert all(result["criteria"][name]["score"] == 0 for name in ("root_cause", "invariant", "correction"))
    assert "unreadable" in result["notes"]


def test_responses_never_leak_rubric_or_reference_material(client, member, monkeypatch, db_factory):
    problem = catalog_problem("checkout-underflow")
    reference = shingles(" ".join([problem.explanation, *problem.hints, *problem.solutions.values()]))
    responses = [diagnose(client).json(), diagnose(client, body=POOR).json(),
                 client.get("/api/problems/checkout-underflow/diagnosis").json(),
                 client.get("/api/diagnosis/history").json()]
    passing_submission(client, monkeypatch)
    responses.append(client.post("/api/problems/checkout-underflow/explanation", json=EXPLANATION).json())
    responses.append(client.get("/api/problems/checkout-underflow/scores").json())
    user_text = [*GOOD.values(), *POOR.values(), *EXPLANATION.values(), "def solve(data): return {'total': 0}"]
    for response in responses:
        rendered = json.dumps(response, default=str)
        for value in sorted(user_text, key=len, reverse=True):
            rendered = rendered.replace(json.dumps(value)[1:-1], "")
        assert not shingles(rendered) & reference
        for marker in ("evidence", "matched_groups", "root_cause_groups", "rubric_source", problem.explanation[:40]):
            assert marker not in rendered


def test_ai_evaluation_blends_and_failure_keeps_deterministic_score(client, member, monkeypatch, db_factory):
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    body = {"problem_id": 1, "language": "python", "code": "def solve(data): return 0", "kind": "run"}
    run = client.post("/api/submissions", json=body).json()
    row = diagnose(client).json()
    assert row["ai_status"] == "queued"
    deterministic = row["score"]

    def unavailable(*args, **kwargs):
        raise AIUnavailable("down")
    monkeypatch.setattr(diagnosis_tasks, "complete", unavailable)
    diagnosis_tasks.evaluate_diagnosis_ai(row["id"])
    failed = client.get(f"/api/diagnosis/{row['id']}").json()
    assert failed["ai_status"] == "failed" and failed["score"] == deterministic
    assert client.get(f"/api/submissions/{run['id']}").json()["status"] == "queued"

    poor = diagnose(client, body=POOR).json()
    reply = json.dumps({"criteria": {name: 1.0 for name in ("defect_category", "root_cause", "invariant",
                                                            "correction", "reproduction")},
                        "feedback": {"root_cause": "Clamp the total with max(0, subtotal - discount)."}})
    monkeypatch.setattr(diagnosis_tasks, "complete", lambda *args, **kwargs: (f"```json\n{reply}\n```", 50))
    diagnosis_tasks.evaluate_diagnosis_ai(poor["id"])
    diagnosis_tasks.evaluate_diagnosis_ai(poor["id"])  # idempotent: already completed
    blended = client.get(f"/api/diagnosis/{poor['id']}").json()
    assert blended["ai_status"] == "completed" and blended["ai_score"] == 100
    assert blended["score"] == pytest.approx(round(0.7 * poor["score"] + 30, 2))
    assert blended["evaluator_version"] == "deterministic-v1+ai-v1"
    assert "ai" not in blended and "Clamp" not in json.dumps(blended)

    garbage = diagnose(client, body=POOR).json()
    monkeypatch.setattr(diagnosis_tasks, "complete", lambda *args, **kwargs: ("not json", 5))
    diagnosis_tasks.evaluate_diagnosis_ai(garbage["id"])
    assert client.get(f"/api/diagnosis/{garbage['id']}").json()["ai_status"] == "failed"
    with db_factory() as db:
        stored = db.get(Diagnosis, garbage["id"])
        assert stored.evaluation_details["ai_error"] == "invalid_response"


def test_ai_feedback_is_filtered_and_admin_only(client, member, monkeypatch):
    make_admin(monkeypatch, member)
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    row = diagnose(client).json()
    problem = catalog_problem("checkout-underflow")
    leaking = " ".join(problem.explanation.split()[:8])
    reply = {"criteria": {name: 0.5 for name in ("defect_category", "root_cause", "invariant", "correction",
                                                 "reproduction")},
             "feedback": {"root_cause": leaking, "invariant": "State the rule as a precise condition."}}
    monkeypatch.setattr(diagnosis_tasks, "complete", lambda *args, **kwargs: (json.dumps(reply), 10))
    diagnosis_tasks.evaluate_diagnosis_ai(row["id"])
    admin_view = client.get(f"/api/diagnosis/{row['id']}").json()
    assert admin_view["ai"]["feedback"] == {"invariant": "State the rule as a precise condition."}


def test_reevaluate_requires_ai_and_ownership(client, member, monkeypatch):
    row = diagnose(client).json()
    assert client.post(f"/api/diagnosis/{row['id']}/evaluate").status_code == 409
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    assert client.post(f"/api/diagnosis/{row['id']}/evaluate").json()["ai_status"] == "queued"


def test_explanation_requires_a_passed_full_submission(client, member, monkeypatch, db_factory):
    blocked = client.post("/api/problems/checkout-underflow/explanation", json=EXPLANATION)
    assert blocked.status_code == 409
    passing_submission(client, monkeypatch)
    response = client.post("/api/problems/checkout-underflow/explanation", json=EXPLANATION)
    assert response.status_code == 201, response.text
    explanation = response.json()
    assert explanation["score"] >= 60
    assert set(explanation["criteria"]) == {"why_failed", "why_works", "invariant", "side_effects", "additional_tests"}
    weak = client.post("/api/problems/checkout-underflow/explanation",
                       json={"why_failed": "It was broken.", "why_works": "Now it works.", "invariant_preserved": "Good."})
    assert weak.status_code == 201 and weak.json()["score"] < explanation["score"]
    status = client.get("/api/problems/checkout-underflow/diagnosis").json()
    assert status["explanation"]["id"] == weak.json()["id"]
    assert status["scores"]["status"] == "completed" and status["scores"]["explanation"] == weak.json()["score"]
    with db_factory() as db:
        failed = Submission(user_id=member["id"], problem_id=1, language="python", mode="manual", kind="submit",
                            code="x", status="failed", results=[], attempt_id=status["attempt_id"])
        db.add(failed)
        db.commit()
        failed_id = failed.id
    assert client.post("/api/problems/checkout-underflow/explanation",
                       json={**EXPLANATION, "submission_id": failed_id}).status_code == 409


def test_assessment_context_requires_and_scopes_the_diagnosis(client, member, db_factory):
    with db_factory() as db:
        assessment = Assessment(slug="debug-check", title="Debug check", duration_seconds=1800, status="published")
        db.add(assessment)
        db.flush()
        session = AssessmentSession(assessment_id=assessment.id, user_id=member["id"],
                                    expires_at=now() + timedelta(minutes=30), challenge_order=[1],
                                    config_snapshot={"configuration": {"diagnosis_required": True},
                                                     "assistance_policy": {"ai": "disabled", "hints": "disabled"}})
        db.add(session)
        db.commit()
        session_id = session.id
    status = client.get("/api/problems/checkout-underflow/diagnosis").json()
    assert status["required"] and status["context"] == "assessment"
    assert client.post("/api/submissions", json={"problem_id": 1, "language": "python",
                                                  "code": "def solve(data): return 0"}).status_code == 428
    row = diagnose(client).json()
    assert row["assessment_session_id"] == session_id
    explicit = client.get(f"/api/problems/checkout-underflow/diagnosis?assessment_session_id={session_id}").json()
    assert explicit["submitted"] and explicit["latest"]["id"] == row["id"]


def test_admin_rubric_management_is_audited(client, member, monkeypatch, db_factory):
    assert client.get("/api/admin/rubrics").status_code == 403
    assert client.get("/api/admin/problems/checkout-underflow/rubric").status_code == 403
    make_admin(monkeypatch, member)
    listing = client.get("/api/admin/rubrics?q=checkout").json()
    assert listing["total"] >= 1 and listing["items"][0]["rubric_source"] == "derived"
    detail = client.get("/api/admin/problems/checkout-underflow/rubric").json()
    assert detail["source"] == "derived" and detail["effective"]["root_cause"]
    assert client.put("/api/admin/problems/checkout-underflow/rubric", json={"root_cause": []}).status_code == 422
    custom = {"defect_categories": ["validation"], "related_categories": [], "root_cause": [["clamp"], ["discount"], ["negative"]],
              "component": ["discount"], "invariant": [["negative"]], "correction": [["clamp"]],
              "reproduction": [["discount"]]}
    updated = client.put("/api/admin/problems/checkout-underflow/rubric", json=custom).json()
    assert updated["source"] == "admin" and updated["rubric_version"] == 2
    assert updated["effective"]["root_cause"] == [["clamp"], ["discount"], ["negative"]]
    row = diagnose(client).json()
    assert row["rubric_version"] == 2
    reverted = client.delete("/api/admin/problems/checkout-underflow/rubric").json()
    assert reverted["source"] == "derived" and reverted["rubric_version"] == 3
    assert client.delete("/api/admin/problems/checkout-underflow/rubric").status_code == 409
    mode = client.patch("/api/admin/problems/checkout-underflow/diagnosis-mode", json={"mode": "required"})
    assert mode.json()["diagnosis_mode"] == "required"
    assert client.patch("/api/admin/problems/checkout-underflow/diagnosis-mode", json={"mode": "maybe"}).status_code == 422
    with db_factory() as db:
        actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["rubric.updated", "rubric.reverted", "diagnosis_mode.updated"]


def test_authored_rubric_is_restored_after_an_override_is_reverted(client, member, monkeypatch, db_factory):
    make_admin(monkeypatch, member)
    authored = {"source": "authored", "version": 1, "defect_categories": ["retry_idempotency"],
                "root_cause": [["idempotency key"], ["retry"], ["charge"]], "component": ["process_payment"]}
    with db_factory() as db:
        db.get(Problem, 1).diagnosis_rubric = authored
        db.commit()
    assert client.get("/api/admin/problems/checkout-underflow/rubric").json()["source"] == "authored"
    assert client.delete("/api/admin/problems/checkout-underflow/rubric").status_code == 409, "authored rubrics stay"
    custom = {**authored, "root_cause": [["clamp"]], "source": "ignored"}
    assert client.put("/api/admin/problems/checkout-underflow/rubric", json=custom).json()["source"] == "admin"
    restored = client.delete("/api/admin/problems/checkout-underflow/rubric").json()
    assert restored["source"] == "authored"
    assert restored["effective"]["root_cause"] == [["idempotency key"], ["retry"], ["charge"]]
    assert restored["effective"]["invariant"], "missing authored sections fall back to derived concepts"
