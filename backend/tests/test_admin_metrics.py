"""Operational metrics (PRD 13.4) and difficulty calibration (PRD 10.3)."""
from datetime import timedelta

import pytest

from app.config import settings
from app.models import (
    AIInteraction,
    Assessment,
    AssessmentSession,
    ChallengeAttempt,
    Diagnosis,
    Problem,
    Submission,
    User,
    now,
)
from app.quality import metrics as metrics_module


@pytest.fixture
def admin(client, member, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", member["email"])
    return member


@pytest.fixture
def redis_down(monkeypatch):
    def offline(*args, **kwargs):
        raise ConnectionError("redis offline")

    monkeypatch.setattr(metrics_module.redis_client, "ping", offline)
    monkeypatch.setattr(metrics_module.redis_client, "llen", offline)


def test_metrics_report_latency_percentiles_and_failure_rates(client, admin, db_factory, redis_down):
    with db_factory() as db:
        for index, runtime in enumerate([100, 200, 300, 400, 1000], 1):
            db.add(Submission(user_id=admin["id"], problem_id=1, language="python", mode="manual", kind="submit",
                              code="x", status="passed", runtime_ms=runtime, turnaround_ms=runtime * 2,
                              created_at=now() - timedelta(hours=index)))
        db.add(Submission(user_id=admin["id"], problem_id=1, language="go", mode="manual", kind="run", code="x",
                          status="error", created_at=now() - timedelta(hours=1)))
        db.add(Submission(user_id=admin["id"], problem_id=1, language="python", mode="manual", kind="submit",
                          code="x", status="passed", runtime_ms=99999, created_at=now() - timedelta(days=30)))
        for retrieval, generation, status in [(10, 900, "completed"), (20, 1100, "completed"), (30, None, "error")]:
            db.add(AIInteraction(user_id=admin["id"], problem_id=1, intent="why_fix_failed", status=status,
                                 retrieval_ms=retrieval, generation_ms=generation, latency_ms=(generation or 0) + retrieval))
        attempt = ChallengeAttempt(user_id=admin["id"], problem_id=1)
        db.add(attempt)
        db.flush()
        for ai_status in ("completed", "completed", "failed"):
            db.add(Diagnosis(user_id=admin["id"], problem_id=1, attempt_id=attempt.id, defect_category="validation",
                             root_cause="r", affected_component="c", violated_invariant="i",
                             proposed_correction="p", reproduction_strategy="s", ai_status=ai_status))
        assessment = Assessment(slug="metrics-pack", title="Metrics pack")
        db.add(assessment)
        db.flush()
        db.add(AssessmentSession(assessment_id=assessment.id, user_id=admin["id"], status="completed",
                                 expires_at=now() + timedelta(hours=1), completed_at=now() - timedelta(seconds=3),
                                 finalized_at=now()))
        db.commit()
    data = client.get("/api/admin/metrics?days=7").json()
    assert data["health"] == {"database": "ok", "redis": "unavailable"}
    assert data["queues"] == {"celery": None, "quality": None}
    execution = data["execution"]
    assert execution["evaluations"] == 6 and execution["service_errors"] == 1
    assert execution["runtime_ms"] == {"samples": 5, "p50": 300, "p95": 1000, "p99": 1000}
    assert execution["by_language"]["python"]["turnaround_ms"]["p50"] == 600
    ai = data["ai"]
    assert ai["interactions"] == 3 and ai["error_rate"] == 33.33
    assert ai["retrieval_ms"]["p50"] == 20 and ai["generation_ms"]["samples"] == 2
    assert data["ai_evaluation"]["diagnoses"] == {"completed": 2, "failed": 1, "failure_rate": 33.33}
    assert data["assessments"]["finalized"] == 1
    assert data["assessments"]["finalization_latency_ms"]["p50"] >= 3000
    assert data["sandbox"]["orphaned_containers"] is None
    assert set(data["jobs_in_progress"]) == {"submissions", "hints", "ai_interactions", "mutation_cases", "mutation_runs"}
    assert client.get("/api/admin/metrics?days=0").status_code == 422


def test_metrics_report_queue_depth_when_redis_is_available(client, admin, monkeypatch):
    monkeypatch.setattr(metrics_module.redis_client, "ping", lambda: True)
    monkeypatch.setattr(metrics_module.redis_client, "llen", lambda queue: {"celery": 4, "quality": 9}[queue])
    data = client.get("/api/admin/metrics").json()
    assert data["health"]["redis"] == "ok" and data["queues"] == {"celery": 4, "quality": 9}


def learners(db_factory, problem_id, solved_minutes, unsolved=0, *, abandoned_days=0, assessment=False):
    with db_factory() as db:
        start = now() - timedelta(days=abandoned_days + 1)
        rows = []
        for index, minutes in enumerate(list(solved_minutes) + [None] * unsolved):
            user = User(email=f"learner{problem_id}-{index}-{assessment}@example.com",
                        username=f"l{problem_id}x{index}{int(assessment)}", password_hash="x")
            db.add(user)
            db.flush()
            session_id = None
            if assessment:
                pack = Assessment(slug=f"pack-{problem_id}-{index}", title="Pack")
                db.add(pack)
                db.flush()
                session = AssessmentSession(assessment_id=pack.id, user_id=user.id, expires_at=now())
                db.add(session)
                db.flush()
                session_id = session.id
            db.add(Submission(user_id=user.id, problem_id=problem_id, language="python", mode="manual", kind="submit",
                              code="x", status="failed", created_at=start, assessment_session_id=session_id,
                              results=[{"name": "p", "hidden": False, "status": "passed"},
                                       {"name": "Hidden case 2", "hidden": True, "status": "failed"}]))
            if minutes is not None:
                done = start + timedelta(minutes=minutes)
                db.add(Submission(user_id=user.id, problem_id=problem_id, language="python", mode="manual",
                                  kind="submit", code="x", status="passed", created_at=done, completed_at=done,
                                  assessment_session_id=session_id, results=[]))
            rows.append(user.id)
        db.commit()
        return rows


def test_calibration_requires_sample_size_and_never_changes_difficulty(client, admin, db_factory):
    with db_factory() as db:
        first = db.get(Problem, 1)
        label, estimate = first.difficulty, first.estimated_minutes
    learners(db_factory, 1, [2] * 22, abandoned_days=10)
    learners(db_factory, 2, [5, 6], unsolved=1, abandoned_days=10)
    learners(db_factory, 3, [1] * 30, assessment=True)
    data = client.get("/api/admin/calibration").json()
    items = {item["problem_id"]: item for item in data["items"]}
    assert 3 not in items, "assessment work must not calibrate practice difficulty"
    easy = items[1]
    assert easy["samples"] == 22 and easy["solve_rate"] == 100.0 and easy["median_solve_seconds"] == 120.0
    assert easy["avg_submissions"] == 2.0 and easy["hidden_failure_rate"] == 50.0
    assert easy["confidence"] == "moderate" and easy["cohorts"]["novice"]["samples"] == 22
    assert easy["suggestion"]["applied"] is False
    if label != "easy" and 2 <= 0.6 * estimate:
        assert easy["suggestion"]["direction"] == "easier"
    small = items[2]
    assert small["samples"] == 3 and small["suggestion"] is None and small["confidence"] == "low"
    assert small["abandonment_rate"] == 33.3 and small["solve_rate"] == 66.7
    assert client.get("/api/admin/calibration?min_samples=5").json()["min_samples"] == 5
    assert client.get("/api/admin/calibration?min_samples=1").status_code == 422
    with db_factory() as db:
        assert db.get(Problem, 1).difficulty == label
