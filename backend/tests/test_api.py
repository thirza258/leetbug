from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app import seed, tasks
from app.catalog import CATALOG
from app.config import settings
from app.models import Activity, Bookmark, Hint, Problem, Submission, now


def create_attempt(db_factory, member, *, status="failed", kind="submit", mode="manual", problem_id=1):
    with db_factory() as db:
        row = Submission(user_id=member["id"], problem_id=problem_id, language="python", mode=mode,
                         kind=kind, code="def solve(data): return 0", prompt="fix the total", prompt_words=3,
                         status=status, results=[], turnaround_ms=123.0, runtime_ms=100)
        db.add(row)
        db.commit()
        return row.id


def test_auth_session_csrf_logout_and_duplicate(client, member):
    assert client.get("/api/auth/me").json()["user"]["id"] == member["id"]
    assert "httponly" in str(client.cookies).lower() or client.cookies.get("leetbug_session")
    duplicate = client.post("/api/auth/register", json={"email": member["email"], "username": "another", "password": "StrongPassword123!"})
    assert duplicate.status_code == 409
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/auth/logout").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    old_cookie = client.cookies.get("leetbug_session")
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json()["user"] is None
    client.cookies.set("leetbug_session", old_cookie)
    assert client.get("/api/auth/me").json()["user"] is None
    assert client.post("/api/auth/login", json={"email": member["email"], "password": "incorrect"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": member["email"], "password": "StrongPassword123!"}).status_code == 200


def test_origin_and_payload_limits(client):
    result = client.post("/api/auth/login", headers={"Origin": "https://untrusted.example"}, json={"email": "a@example.com", "password": "x"})
    assert result.status_code == 403
    result = client.post("/api/auth/login", content='{"password":"' + "x" * 100000 + '"}', headers={"Content-Type": "application/json"})
    assert result.status_code == 413


def test_catalog_filters_and_no_private_oracles(client, member):
    response = client.get("/api/problems").json()
    assert response["total"] == len(CATALOG) == 324
    assert len(response["items"]) == 20
    second_page = client.get("/api/problems?page=2").json()
    assert len(second_page["items"]) == 20
    assert second_page["items"][-1]["slug"] == "shipment-transitions"
    assert not {row["id"] for row in response["items"]} & {row["id"] for row in second_page["items"]}
    page_count = (len(CATALOG) + 19) // 20
    pages = [response, second_page] + [client.get(f"/api/problems?page={page}").json() for page in range(3, page_count + 1)]
    assert all(len(page["items"]) == 20 for page in pages[:-1])
    assert [row["slug"] for page in pages for row in page["items"]] == [item["slug"] for item in CATALOG]
    assert pages[4]["items"][-1]["slug"] == "waitlist-promotion"
    assert pages[-1]["items"][-1]["id"] == len(CATALOG)
    assert pages[5]["items"][0]["slug"] == "choosing-the-right-system-design"
    assert pages[6]["items"][0]["slug"] == "circuit-breaker-cooldown"
    assert pages[11]["items"][0]["slug"] == "bounded-admission-queue"
    assert pages[13]["items"][10]["slug"] == "autoscaler-ceiling-replicas"
    assert pages[-1]["items"][-1]["slug"] == "smooth-weighted-round-robin"
    assert client.get(f"/api/problems?page={page_count + 1}").json()["items"] == []
    assert client.get("/api/meta").json()["problem_count"] == len(CATALOG)
    for category in ("runtime", "logic", "business", "edge"):
        assert client.get(f"/api/problems?category={category}").json()["total"] == 69
    assert client.get("/api/problems?category=system_design").json()["total"] == 48
    assert client.get("/api/problems?category=business&language=python&difficulty=medium").json()["total"] == sum(
        item["category"] == "business" and "python" in item["starters"] and item["difficulty"] == "medium"
        for item in CATALOG
    )
    assert client.get("/api/problems?q=overflow").json()["total"] == 3
    assert client.get("/api/problems?language=go").json()["total"] == 34
    assert client.get("/api/problems?tag=rollback").json()["total"] == 1
    assert client.get("/api/problems?page=2&limit=5").json()["items"][0]["id"] == 6
    assert client.get("/api/problems?limit=0").status_code == 422
    assert client.get("/api/problems/unknown").status_code == 404
    detail = client.get("/api/problems/checkout-underflow").json()
    assert "solutions" not in detail and "tests" not in detail and "hints" not in detail
    assert len(detail["public_tests"]) == 2 and detail["hidden_test_count"] == 2
    assert client.post("/api/problems/checkout-underflow/bookmark").json()["bookmarked"]
    assert client.get("/api/problems?bookmarked=true").json()["total"] == 1
    assert not client.post("/api/problems/checkout-underflow/bookmark").json()["bookmarked"]
    for item in CATALOG[13:]:
        expanded = client.get(f"/api/problems/{item['slug']}").json()
        assert set(expanded["starters"]) == set(item["starters"])
        assert "solutions" not in expanded and "tests" not in expanded and "hints" not in expanded
        assert expanded["hidden_test_count"] == sum(test["hidden"] for test in item["tests"])
        assert len(expanded["public_tests"]) == sum(not test["hidden"] for test in item["tests"])


@pytest.mark.parametrize("original_count", [40, 100, 101, 121, 221, 271])
def test_catalog_upgrade_preserves_existing_content_and_progress(db_factory, client, member, original_count):
    submission_id = create_attempt(db_factory, member, status="passed", problem_id=original_count)
    with db_factory() as db:
        # Reproduce installations from each previous catalog version.
        db.execute(delete(Problem).where(Problem.id > original_count))
        db.get(Problem, original_count).title = "Locally edited case"
        db.add(Bookmark(user_id=member["id"], problem_id=original_count))
        db.commit()
        original = [(p.id, p.slug, p.title) for p in db.scalars(select(Problem).order_by(Problem.id))]
    seed.seed()
    seed.seed()
    with db_factory() as db:
        problems = list(db.scalars(select(Problem).order_by(Problem.id)))
        assert len(problems) == len(CATALOG)
        assert [(p.id, p.slug, p.title) for p in problems[:original_count]] == original
        assert [(p.id, p.slug) for p in problems[original_count:]] == [
            (index, item["slug"]) for index, item in enumerate(CATALOG[original_count:], original_count + 1)
        ]
        attempt = db.get(Submission, submission_id)
        assert attempt.problem_id == original_count and attempt.status == "passed"
        assert db.get(Bookmark, (member["id"], original_count)) is not None
    assert client.get("/api/problems?status=solved").json()["items"][0]["id"] == original_count


def test_system_design_discovery_and_progress(client, member, db_factory):
    result = client.get("/api/problems?category=system_design&language=javascript&difficulty=medium&q=architecture").json()
    assert result["total"] == 1
    problem = result["items"][0]
    assert problem["slug"] == "choosing-the-right-system-design"
    create_attempt(db_factory, member, status="passed", problem_id=problem["id"])
    stats = client.get("/api/analytics/me").json()
    assert {"category": "system_design", "total": 48, "solved": 1} in stats["categories"]
    assert sum(category["total"] for category in stats["categories"]) == stats["total_problems"]
    solutions = client.get(f"/api/problems/{problem['slug']}/solutions").json()
    assert set(solutions["solutions"]) == {"python", "javascript"}


def test_solution_unlock_requires_full_submission_and_share_opt_in(client, member, db_factory):
    create_attempt(db_factory, member, status="passed", kind="run")
    assert client.get("/api/problems/checkout-underflow/solutions").status_code == 403
    row_id = create_attempt(db_factory, member, status="passed")
    result = client.get("/api/problems/checkout-underflow/solutions").json()
    assert "python" in result["solutions"] and result["community"] == []
    assert client.post(f"/api/submissions/{row_id}/share").json()["shared"]
    assert len(client.get("/api/problems/checkout-underflow/solutions").json()["community"]) == 1
    assert not client.post(f"/api/submissions/{row_id}/share").json()["shared"]
    assert client.get("/api/problems?status=solved").json()["total"] == 1


def test_submission_authorization_capacity_and_ai_configuration(client, member, db_factory):
    body = {"problem_id": 1, "language": "python", "code": "def solve(data): return 0"}
    assert client.post("/api/submissions", json={**body, "language": "go"}).status_code == 422
    assert client.post("/api/submissions", json={**body, "mode": "ai", "prompt": "fix the total"}).status_code == 503
    first = client.post("/api/submissions", json=body)
    assert first.status_code == 202
    assert client.post("/api/submissions", json=body).status_code == 202
    assert client.post("/api/submissions", json=body).status_code == 409
    row_id = first.json()["id"]
    assert client.post(f"/api/submissions/{row_id}/share").status_code == 403
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get(f"/api/submissions/{row_id}").status_code == 401
    other = client.post("/api/auth/register", json={"email": "other@example.com", "username": "other", "password": "StrongPassword123!"}).json()
    client.headers["X-CSRF-Token"] = other["csrf_token"]
    assert client.get(f"/api/submissions/{row_id}").status_code == 404
    assert client.post(f"/api/submissions/{row_id}/share").status_code == 404
    assert client.get("/api/submissions").json()["total"] == 0


def test_hints_gate_levels_ownership_and_queue(client, member, db_factory, monkeypatch):
    assert client.post("/api/problems/checkout-underflow/hints", json={"language": "python"}).status_code == 403
    create_attempt(db_factory, member)
    create_attempt(db_factory, member)
    assert client.get("/api/problems/checkout-underflow").json()["hints_unlocked"]
    monkeypatch.setattr(tasks, "generate_hint", lambda *args: {"text": "Validate before updating state.", "sources": [{"title": "Official docs", "url": "https://docs.python.org/3/", "excerpt": "context"}], "retrieval": "chroma-lexical"})
    for level in range(1, 4):
        response = client.post("/api/problems/checkout-underflow/hints", json={"language": "python"})
        assert response.status_code == 202
        hint_id = response.json()["id"]
        same = client.post("/api/problems/checkout-underflow/hints", json={"language": "python"})
        assert same.json()["id"] == hint_id
        tasks.hint_task(hint_id)
        ready = client.get(f"/api/hints/{hint_id}").json()
        assert ready["level"] == level and ready["status"] == "completed"
    assert client.post("/api/problems/checkout-underflow/hints", json={"language": "python"}).json()["level"] == 3
    assert client.post("/api/problems/checkout-underflow/hints", json={"language": "go"}).status_code == 422
    with db_factory() as db:
        assert len(db.query(Hint).all()) == 3


def test_discussion_reply_vote_and_ownership(client, member):
    body = {"title": "How should we handle a retry?", "body": "I think an order identifier can prevent repeated changes.", "problem_id": 9}
    response = client.post("/api/discussions", json=body)
    assert response.status_code == 201
    row_id = response.json()["id"]
    assert client.post(f"/api/discussions/{row_id}/vote").json()["votes"] == 1
    assert client.post(f"/api/discussions/{row_id}/vote").json()["votes"] == 0
    reply = client.post(f"/api/discussions/{row_id}/replies", json={"body": "The check and update should be atomic."})
    assert reply.status_code == 201 and reply.json()["reply_count"] == 1
    assert client.get("/api/discussions?q=retry&problem_id=9").json()["total"] == 1
    assert client.post("/api/discussions", json={**body, "body": " " * 20}).status_code == 422
    client.post("/api/auth/logout")
    other = client.post("/api/auth/register", json={"email": "other@example.com", "username": "other", "password": "StrongPassword123!"}).json()
    client.headers["X-CSRF-Token"] = other["csrf_token"]
    assert client.delete(f"/api/discussions/{row_id}").status_code == 403
    assert client.delete(f"/api/replies/{reply.json()['replies'][0]['id']}").status_code == 403


def test_metrics_deduplicate_solves_exclude_runs_and_track_retention(client, member, db_factory):
    create_attempt(db_factory, member, status="passed")
    create_attempt(db_factory, member, status="passed", mode="ai")
    create_attempt(db_factory, member, status="failed")
    create_attempt(db_factory, member, status="error")
    create_attempt(db_factory, member, status="passed", kind="run")
    with db_factory() as db:
        db.add(Activity(user_id=member["id"], day=now().date() - timedelta(days=10)))
        db.add(Activity(user_id=member["id"], day=now().date() - timedelta(days=5)))
        db.commit()
    stats = client.get("/api/analytics/me").json()
    assert stats["solved"] == 1 and stats["attempts"] == 3
    assert stats["completion_rate"] == 66.7 and stats["ai_attempts"] == 1
    assert len(stats["activity"]) == 91
    platform = client.get("/api/analytics/platform").json()
    assert platform["retention_7d"] == 0 and platform["monthly_active_users"] == 1
    assert platform["manual_p95_ms"] == 123
    rank = client.get("/api/leaderboard?mode=ai").json()["items"][0]
    assert rank["solved"] == 1 and rank["prompt_words"] == 3
    with db_factory() as db:
        for days_ago in [10, 5]:
            db.add(Submission(user_id=member["id"], problem_id=1, language="python", mode="manual",
                              kind="run", code="source", status="failed", created_at=now() - timedelta(days=days_ago)))
        db.commit()
    # Revisiting the same case also does not satisfy the PRD's "another problem" metric.
    assert client.get("/api/analytics/platform").json()["retention_7d"] == 0
    with db_factory() as db:
        db.add(Submission(user_id=member["id"], problem_id=2, language="python", mode="manual",
                          kind="run", code="source", status="failed", created_at=now() - timedelta(days=5)))
        db.commit()
    assert client.get("/api/analytics/platform").json()["retention_7d"] == 100


def test_queue_failure_is_persisted(client, member, db_factory, monkeypatch):
    def unavailable(*args):
        raise ConnectionError("offline")
    monkeypatch.setattr(tasks.evaluate, "delay", unavailable)
    response = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "code": "def solve(data): return 0"})
    assert response.status_code == 503
    assert client.get("/api/submissions").json()["items"][0]["status"] == "error"


def test_worker_ai_persistence_grading_and_idempotent_delivery(client, member, db_factory, monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(tasks, "patch_code", lambda *args: ('def solve(data): return {"total": 0}', 42))
    calls = []
    def execute(language, code, tests):
        calls.append(code)
        return {"results": [{"status": "ok", "output": t["expected"], "runtime_ms": 1} for t in tests], "runtime_ms": 50, "memory_kb": 500}
    monkeypatch.setattr(tasks, "execute_code", execute)
    response = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "code": "old source", "mode": "ai", "prompt": "Validate all negative totals."})
    row_id = response.json()["id"]
    tasks.evaluate(row_id)
    tasks.evaluate(row_id)
    row = client.get(f"/api/submissions/{row_id}").json()
    assert len(calls) == 1 and row["status"] == "passed" and row["llm_tokens"] == 42
    assert row["generated_code"].startswith("def solve")
    hidden = [r for r in row["results"] if r["hidden"]]
    assert hidden and all(set(r) == {"name", "hidden", "status"} for r in hidden)
