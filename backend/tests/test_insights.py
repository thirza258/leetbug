import json
from datetime import timedelta
from pathlib import Path

from app import scoring, tasks
from app.catalog import CATALOG
from app.models import Assessment, AssessmentSession, Incident, IncidentSession, Problem, now

EVAL = json.loads((Path(__file__).parent / "fixtures" / "diagnosis_eval.json").read_text())


def solve_with_diagnosis(client, monkeypatch, slug, fields):
    def execute(language, source, tests_):
        return {"results": [{"status": "ok", "output": test["expected"], "runtime_ms": 1} for test in tests_],
                "runtime_ms": 40, "memory_kb": 300}
    monkeypatch.setattr(tasks, "execute_code", execute)
    assert client.post(f"/api/problems/{slug}/diagnosis", json=fields).status_code == 201
    problem_id = next(index for index, item in enumerate(CATALOG, 1) if item["slug"] == slug)
    response = client.post("/api/submissions", json={"problem_id": problem_id, "language": "python",
                                                     "code": "def solve(data): return 0"})
    assert response.status_code == 202, response.text
    tasks.evaluate(response.json()["id"])


def test_shrinkage_and_confidence_levels():
    assert scoring.shrink(None, 0) is None
    assert scoring.shrink(90, 1) == round((90 + 5 * 50) / 6, 2)
    assert abs(scoring.shrink(90, 40) - 90) < abs(scoring.shrink(90, 2) - 90)
    assert [scoring.confidence(n) for n in (0, 2, 3, 9, 10, 24, 25)] == [
        "insufficient", "insufficient", "low", "low", "moderate", "moderate", "high"]


def test_insights_require_sign_in_and_report_insufficient_data(client):
    assert client.get("/api/insights/me").status_code == 401
    client.post("/api/auth/register", json={"email": "new@example.com", "username": "newcomer",
                                            "password": "StrongPassword123!"})
    data = client.get("/api/insights/me").json()
    reasoning = data["reasoning"]
    assert reasoning["score"] is None and reasoning["sample_size"] == 0
    assert reasoning["confidence"] == "insufficient" and reasoning["provisional"]
    assert len(reasoning["dimensions"]) == 6 and len(data["trend"]) == 12
    assert 1 <= len(data["recommendations"]) <= 5 and all(row["reason"] for row in data["recommendations"])


def test_reasoning_score_is_shrunk_for_small_samples(client, member, monkeypatch):
    for slug in ("checkout-underflow", "missing-last-item", "wallet-race"):
        solve_with_diagnosis(client, monkeypatch, slug, EVAL["problems"][slug]["correct"])
    data = client.get("/api/insights/me").json()
    reasoning = data["reasoning"]
    assert reasoning["sample_size"] == 3 and reasoning["confidence"] == "low" and reasoning["provisional"]
    assert reasoning["raw_score"] > 60
    assert 50 < reasoning["score"] < reasoning["raw_score"], "three samples must be pulled toward the prior"
    assert data["solved"] == 3 and data["patch_correctness"] == 100
    assert data["engineering_quality"] is not None
    categories = {row["id"]: row for row in data["categories"]}
    assert categories["race_condition"]["solved"] == 1 and categories["race_condition"]["confidence"] == "insufficient"
    assert all(row["slug"] not in {"checkout-underflow", "missing-last-item", "wallet-race"}
               for row in data["recommendations"])
    assert sum(week["diagnoses"] for week in data["trend"]) == 3


def test_unsolved_diagnoses_do_not_count_toward_the_reasoning_sample(client, member):
    assert client.post("/api/problems/checkout-underflow/diagnosis",
                       json=EVAL["problems"]["checkout-underflow"]["correct"]).status_code == 201
    assert client.get("/api/insights/me").json()["reasoning"]["sample_size"] == 0


def test_incident_and_assessment_history_respect_delayed_feedback(client, member, db_factory):
    with db_factory() as db:
        problem = db.get(Problem, 1)
        # Seeded incidents use low ids; this fixture takes an unused one.
        incident = Incident(id=9001, slug="duplicate-charges-fixture", problem_id=problem.id,
                            title="Duplicate charges", summary="Retries charge twice.", severity="SEV-2", level=2,
                            category="retry_idempotency")
        db.add(incident)
        db.add(IncidentSession(incident_id=9001, user_id=member["id"], status="resolved", score=72.5))
        delayed = Assessment(slug="delayed", title="Delayed feedback", status="published")
        immediate = Assessment(slug="immediate", title="Immediate feedback", status="published")
        db.add_all([delayed, immediate])
        db.flush()
        for assessment, feedback in ((delayed, "delayed"), (immediate, "immediate")):
            db.add(AssessmentSession(assessment_id=assessment.id, user_id=member["id"], status="completed",
                                     expires_at=now() + timedelta(hours=1), finalized_at=now(), total_score=81.0,
                                     config_snapshot={"configuration": {"feedback": feedback}}))
        db.commit()
    data = client.get("/api/insights/me").json()
    assert data["incidents"][0]["score"] == 72.5 and data["incidents"][0]["incident_slug"] == "duplicate-charges-fixture"
    scores = {row["assessment_slug"]: row for row in data["assessments"]}
    assert scores["delayed"]["score"] is None and scores["delayed"]["score_hidden"]
    assert scores["immediate"]["score"] == 81.0
