"""Shared foundation for PRD 2.0: schema migration, taxonomy, visibility, attempts, policy and scoring."""
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select

from app import attempts, scoring, taxonomy
from app.catalog import CATALOG
from app.config import settings
from app.models import (
    Assessment,
    AssessmentSession,
    ChallengeAttempt,
    Diagnosis,
    Event,
    Problem,
    Submission,
    now,
)

BACKEND = Path(__file__).resolve().parents[1]


def test_migrations_upgrade_and_downgrade_cleanly(tmp_path):
    database = tmp_path / "migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database}"}

    def alembic(*args):
        result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env,
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr[-2000:]

    alembic("upgrade", "head")
    tables = set(inspect(create_engine(f"sqlite:///{database}")).get_table_names())
    assert {"challenge_attempts", "diagnoses", "fix_explanations", "incidents", "incident_sessions",
            "incident_resolutions", "mutation_runs", "mutation_cases", "quality_gates", "ai_interactions",
            "assessments", "assessment_sessions", "assessment_invitations", "organizations",
            "organization_members", "competency_profiles", "audit_logs", "events"} <= tables
    columns = {column["name"] for column in inspect(create_engine(f"sqlite:///{database}")).get_columns("problems")}
    assert {"visibility", "version", "diagnosis_mode", "diagnosis_rubric", "rubric_version", "quality_status"} <= columns
    alembic("downgrade", "b2c8e4f19a23")
    assert "challenge_attempts" not in set(inspect(create_engine(f"sqlite:///{database}")).get_table_names())
    alembic("upgrade", "head")
    alembic("downgrade", "base")


def test_taxonomy_classifies_every_catalog_problem():
    for item in CATALOG:
        result = taxonomy.classify(item["category"], item["tags"])
        assert result["bug_categories"] and all(bug in taxonomy.BUG_CATEGORIES for bug in result["bug_categories"])
        assert result["skills"] and all(skill in taxonomy.DEBUGGING_SKILLS for skill in result["skills"])
    wallet = next(item for item in CATALOG if item["slug"] == "wallet-race")
    assert taxonomy.classify(wallet["category"], wallet["tags"])["bug_categories"][0] == "race_condition"
    assert "deadlock" in taxonomy.related_categories("race_condition")
    override = taxonomy.classify("business", ["validation"], {"bug_categories": ["caching"], "skills": ["reproduction"]})
    assert override == {"bug_categories": ["caching"], "skills": ["reproduction"]}
    document = taxonomy.taxonomy_document()
    assert len(document["skills"]) == 12 and {node["id"] for node in document["concept_graph"]} >= {"race-conditions"}
    for node in document["concept_graph"]:
        assert all(child in taxonomy.CONCEPT_GRAPH for child in node["children"])


def test_taxonomy_endpoint_and_problem_detail_metadata(client):
    assert client.get("/api/taxonomy").json()["version"] == taxonomy.TAXONOMY_VERSION
    detail = client.get("/api/problems/wallet-race").json()
    assert detail["taxonomy"]["bug_categories"][0] == {"id": "race_condition", "name": "Race condition"}
    assert detail["diagnosis_mode"] == "optional" and detail["diagnosis_required"] is False
    assert detail["assistance"]["source"] == "practice" and detail["visibility"] == "public"


def hidden_problem(db_factory, visibility, problem_id=900001):
    with db_factory() as db:
        source = db.get(Problem, 1)
        clone = Problem(id=problem_id, slug=f"{visibility}-clone", title=f"{visibility} clone", summary=source.summary,
                        description=source.description, category=source.category, difficulty=source.difficulty,
                        tags=source.tags, requirements=source.requirements, starters=source.starters,
                        solutions=source.solutions, explanation=source.explanation, hints=source.hints,
                        tests=source.tests, visibility=visibility)
        db.add(clone)
        db.commit()
        return clone.id


@pytest.mark.parametrize("visibility", ["assessment", "incident", "draft"])
def test_non_public_problems_are_hidden(client, member, db_factory, visibility):
    problem_id = hidden_problem(db_factory, visibility)
    assert client.get("/api/problems").json()["total"] == len(CATALOG)
    assert client.get("/api/meta").json()["problem_count"] == len(CATALOG)
    assert client.get(f"/api/problems/{visibility}-clone").status_code == 404
    body = {"problem_id": problem_id, "language": "python", "code": "def solve(data): return 0"}
    assert client.post("/api/submissions", json=body).status_code == 422
    assert client.post(f"/api/problems/{visibility}-clone/bookmark").status_code == 404
    stats = client.get("/api/analytics/me").json()
    assert stats["total_problems"] == len(CATALOG)


def start_session(db_factory, member, *, problem_ids=(1,), policy=None, configuration=None, expires_in=3600):
    with db_factory() as db:
        assessment = Assessment(slug=f"pack-{len(db.scalars(select(Assessment)).all())}", title="Pack",
                                configuration=configuration or {}, assistance_policy=policy or {},
                                status="published")
        db.add(assessment)
        db.flush()
        session = AssessmentSession(
            assessment_id=assessment.id, user_id=member["id"], expires_at=now() + timedelta(seconds=expires_in),
            challenge_order=list(problem_ids),
            config_snapshot={"configuration": configuration or {}, "assistance_policy": policy or {}})
        db.add(session)
        db.commit()
        return session.id


def test_assessment_policy_applies_to_practice_endpoints(client, member, db_factory, monkeypatch):
    # Solved in practice before the assessment: the solution is normally unlocked.
    with db_factory() as db:
        db.add(Submission(user_id=member["id"], problem_id=1, language="python", mode="manual", kind="submit",
                          code="x", status="passed", results=[]))
        db.add_all([Submission(user_id=member["id"], problem_id=1, language="python", mode="manual", kind="submit",
                               code="x", status="failed", results=[]) for _ in range(2)])
        db.commit()
    assert client.get("/api/problems/checkout-underflow/solutions").status_code == 200
    session_id = start_session(db_factory, member, policy={"ai": "disabled", "hints": "disabled"})
    assert client.get("/api/problems/checkout-underflow/solutions").status_code == 403
    assert client.post("/api/problems/checkout-underflow/hints", json={"language": "python"}).status_code == 403
    detail = client.get("/api/problems/checkout-underflow").json()
    assert detail["assistance"] == {"ai": "disabled", "hints": "disabled", "source": "assessment",
                                    "assessment_session_id": session_id}
    assert detail["hints_unlocked"] is False
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    body = {"problem_id": 1, "language": "python", "code": "def solve(data): return 0"}
    assert client.post("/api/submissions", json={**body, "mode": "ai", "prompt": "Fix the negative totals"}).status_code == 403
    # Practice-page work is attributed to the active session and does not count as practice progress.
    response = client.post("/api/submissions", json=body)
    assert response.status_code == 202
    assert response.json()["assessment_session_id"] == session_id
    with db_factory() as db:
        attempt = db.get(ChallengeAttempt, response.json()["attempt_id"])
        assert attempt.context == "assessment" and attempt.scope == f"assessment:{session_id}"


def test_restricted_hint_policy_caps_hint_level(client, member, db_factory):
    start_session(db_factory, member, policy={"ai": "guided", "hints": "restricted"})
    with db_factory() as db:
        db.add_all([Submission(user_id=member["id"], problem_id=1, language="python", mode="manual", kind="submit",
                               code="x", status="failed", results=[]) for _ in range(2)])
        db.commit()
    first = client.post("/api/problems/checkout-underflow/hints", json={"language": "python"})
    assert first.status_code == 202 and first.json()["level"] == 1
    with db_factory() as db:
        from app.models import Hint
        hint = db.get(Hint, first.json()["id"])
        hint.status, hint.text = "completed", "Think about the zero boundary."
        db.commit()
    # A second request returns the existing conceptual hint instead of a more specific one.
    assert client.post("/api/problems/checkout-underflow/hints", json={"language": "python"}).json()["level"] == 1


def test_expired_assessment_rejects_work_and_is_finalized(client, member, db_factory):
    session_id = start_session(db_factory, member, expires_in=-5)
    body = {"problem_id": 1, "language": "python", "code": "def solve(data): return 0",
            "assessment_session_id": session_id}
    assert client.post("/api/submissions", json=body).status_code == 409
    with db_factory() as db:
        session = db.get(AssessmentSession, session_id)
        assert session.status == "expired" and session.finalized_at is not None
    # The expired session no longer constrains practice.
    assert client.get("/api/problems/checkout-underflow").json()["assistance"]["source"] == "practice"


def test_assessment_language_and_attempt_limits(client, member, db_factory):
    session_id = start_session(db_factory, member, problem_ids=(2,),
                               configuration={"languages": ["python"], "max_attempts": 1})
    body = {"problem_id": 2, "language": "java", "code": "class Solution {}", "assessment_session_id": session_id}
    assert client.post("/api/submissions", json=body).status_code == 422
    body = {**body, "language": "python", "code": "def solve(data): return 0"}
    assert client.post("/api/submissions", json=body).status_code == 202
    assert client.post("/api/submissions", json=body).status_code == 409
    other = {**body, "problem_id": 1}
    assert client.post("/api/submissions", json=other).status_code == 404


def test_required_diagnosis_gates_full_submissions_only(client, member, db_factory):
    with db_factory() as db:
        db.get(Problem, 1).diagnosis_mode = "required"
        db.commit()
    assert client.get("/api/problems/checkout-underflow").json()["diagnosis_required"] is True
    body = {"problem_id": 1, "language": "python", "code": "def solve(data): return 0"}
    assert client.post("/api/submissions", json={**body, "kind": "run"}).status_code == 202
    assert client.post("/api/submissions", json=body).status_code == 428
    with db_factory() as db:
        attempt = db.scalar(select(ChallengeAttempt).where(ChallengeAttempt.user_id == member["id"]))
        db.add(Diagnosis(user_id=member["id"], problem_id=1, attempt_id=attempt.id, defect_category="validation",
                         root_cause="The discount is never clamped", affected_component="solve",
                         violated_invariant="Totals are never negative", proposed_correction="Clamp",
                         reproduction_strategy="Discount larger than subtotal", score=70))
        db.commit()
    response = client.post("/api/submissions", json=body)
    assert response.status_code == 202 and response.json()["diagnosis_id"]
    assert response.json()["diff_stats"]["added"] == 1


def test_attempt_scoring_from_stored_evidence(client, member, db_factory, monkeypatch):
    from app import tasks
    monkeypatch.setattr(tasks, "execute_code", lambda language, code, tests: {
        "results": [{"status": "ok", "output": test["expected"], "runtime_ms": 1} for test in tests],
        "runtime_ms": 40, "memory_kb": 100})
    run = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "kind": "run",
                                                "code": "def solve(data): return 0"}).json()
    tasks.evaluate(run["id"])
    submitted = client.post("/api/submissions", json={"problem_id": 1, "language": "python",
                                                      "code": "def solve(data): return 0"}).json()
    tasks.evaluate(submitted["id"])
    with db_factory() as db:
        attempt = db.get(ChallengeAttempt, submitted["attempt_id"])
        assert attempt.solved_at is not None and attempt.status == "solved"
        assert attempt.correctness_score == 100 and attempt.time_score == 100
        assert attempt.scores["evidence"]["ran_before_submit"] is True
        assert attempt.scores["versions"]["scoring"] == scoring.SCORING_VERSION
        types = [row.type for row in db.scalars(select(Event).where(Event.attempt_id == attempt.id))]
        assert {"attempt.started", "submission.created", "submission.completed"} <= set(types)
    # The practice solve still unlocks the solution and library progress.
    assert client.get("/api/problems?status=solved").json()["total"] == 1


def test_scoring_primitives():
    assert scoring.weighted({"a": 100, "b": None}, {"a": 1, "b": 1}) == 100
    assert scoring.weighted({"a": 100, "b": None}, {"a": 1, "b": 1}, missing="zero") == 50
    assert scoring.correctness_from_results([{"status": "passed"}, {"status": "failed"}]) == 50
    assert scoring.time_efficiency(600, 15, True) == 100
    assert scoring.time_efficiency(10_000, 15, False) == 0
    assert 20 <= scoring.time_efficiency(10_000, 15, True) < 100
    assert scoring.shrink(100, 1) < scoring.shrink(100, 20) < 100
    assert [scoring.confidence(n) for n in (0, 3, 10, 25)] == ["insufficient", "low", "moderate", "high"]
    assert scoring.diagnosis_weights(type("P", (), {"difficulty": "hard"})())["root_cause"] == 35


def test_diff_stats_and_attempt_uniqueness(db_factory, member):
    stats = attempts.diff_stats("a\nb\nc\n", "a\nB\nc\nd\n")
    assert stats["added"] == 2 and stats["removed"] == 1 and stats["changed_original_lines"] == [2, 3]
    with db_factory() as db:
        first = attempts.get_or_create_attempt(db, member["id"], 1)
        second = attempts.get_or_create_attempt(db, member["id"], 1)
        other = attempts.get_or_create_attempt(db, member["id"], 1, incident_session_id=None,
                                               assessment_session_id=None)
        assert first.id == second.id == other.id
        db.commit()
