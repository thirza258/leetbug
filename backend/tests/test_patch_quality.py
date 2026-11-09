from types import SimpleNamespace

from sqlalchemy import select

from app import tasks
from app.diagnosis.quality import score_patch
from app.models import Problem, Submission

STARTER_FIX = '''def solve(data):
    subtotal = sum(max(0, price) for price in data["prices"])
    return {"total": max(0, subtotal - max(0, data["discount"]))}
'''
SWALLOWING_FIX = '''def solve(data):
    try:
        subtotal = sum(max(0, price) for price in data["prices"])
        return {"total": max(0, subtotal - max(0, data["discount"]))}
    except Exception:
        pass
'''
BLOATED_FIX = '''import math


def clamp(value):
    if value < 0:
        return 0
    return value


def total_of(prices):
    running = 0
    for price in prices:
        running = running + clamp(price)
    return running


def solve(data):
    # TODO: tidy this up later
    subtotal = total_of(data["prices"])
    discount = clamp(data["discount"])
    result = subtotal - discount
    result = clamp(result)
    print("debug", result, file=__import__("sys").stderr)
    return {"total": result}
'''


def submission(code, status="passed", kind="submit", runtime_ms=50.0, problem_id=1, sid="s-1"):
    return SimpleNamespace(id=sid, status=status, kind=kind, language="python", code=code, generated_code=None,
                           runtime_ms=runtime_ms, problem_id=problem_id)


def problem_by_slug(db, slug):
    return db.scalar(select(Problem).where(Problem.slug == slug))


def test_quality_is_gated_on_correctness(db_factory):
    with db_factory() as db:
        problem = problem_by_slug(db, "checkout-underflow")
        assert score_patch(db, problem, submission(STARTER_FIX, status="failed")) is None
        assert score_patch(db, problem, submission(STARTER_FIX, kind="run")) is None
        assert score_patch(db, problem, None) is None


def test_focused_fix_scores_higher_than_a_noisy_rewrite(db_factory):
    with db_factory() as db:
        problem = problem_by_slug(db, "checkout-underflow")
        focused = score_patch(db, problem, submission(STARTER_FIX))
        noisy = score_patch(db, problem, submission(BLOATED_FIX))
    assert focused["version"] == "quality-v1" and 0 <= noisy["score"] < focused["score"] <= 100
    assert focused["dimensions"]["minimality"]["score"] == 1.0
    assert noisy["dimensions"]["minimality"]["score"] < 1.0
    assert noisy["dimensions"]["maintainability"]["score"] < focused["dimensions"]["maintainability"]["score"]
    assert "concurrency_safety" not in focused["dimensions"]
    assert focused["dimensions"]["performance"]["score"] is None
    assert focused["dimensions"]["performance"]["flag"] == "insufficient_data"
    assert "def solve" not in str(focused), "quality output never contains reference code"


def test_swallowed_exceptions_lower_error_handling(db_factory):
    with db_factory() as db:
        problem = problem_by_slug(db, "checkout-underflow")
        clean = score_patch(db, problem, submission(STARTER_FIX))
        swallowing = score_patch(db, problem, submission(SWALLOWING_FIX))
    assert clean["dimensions"]["error_handling"]["score"] == 1.0
    assert swallowing["dimensions"]["error_handling"]["score"] < 1.0


def test_concurrency_dimension_applies_to_race_conditions(db_factory):
    with db_factory() as db:
        problem = problem_by_slug(db, "wallet-race")
        locked = score_patch(db, problem, submission(problem.solutions["python"], problem_id=problem.id))
        unlocked_code = problem.solutions["python"].replace("with lock:", "if True:").replace(
            "lock = threading.Lock()", "lock = None")
        unlocked = score_patch(db, problem, submission(unlocked_code, problem_id=problem.id))
    assert locked["dimensions"]["concurrency_safety"]["score"] == 1.0
    assert unlocked["dimensions"]["concurrency_safety"]["score"] < 1.0


def test_performance_compares_with_enough_accepted_runs(db_factory, member):
    with db_factory() as db:
        for index in range(5):
            db.add(Submission(user_id=member["id"], problem_id=1, language="python", mode="manual", kind="submit",
                              code="x", status="passed", results=[], runtime_ms=100.0 + index))
        db.commit()
        problem = problem_by_slug(db, "checkout-underflow")
        fast = score_patch(db, problem, submission(STARTER_FIX, runtime_ms=90.0))
        slow = score_patch(db, problem, submission(STARTER_FIX, runtime_ms=400.0))
    assert fast["dimensions"]["performance"]["score"] == 1.0
    assert slow["dimensions"]["performance"]["score"] < 1.0


def test_worker_stores_quality_for_accepted_submissions_only(client, member, monkeypatch):
    def execute(language, source, tests_):
        return {"results": [{"status": "ok", "output": test["expected"], "runtime_ms": 1} for test in tests_],
                "runtime_ms": 40, "memory_kb": 300}
    monkeypatch.setattr(tasks, "execute_code", execute)
    accepted = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "code": STARTER_FIX}).json()
    tasks.evaluate(accepted["id"])
    run = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "code": STARTER_FIX,
                                                "kind": "run"}).json()
    tasks.evaluate(run["id"])
    stored = client.get(f"/api/submissions/{accepted['id']}").json()
    assert stored["status"] == "passed" and stored["quality"]["version"] == "quality-v1"
    assert client.get(f"/api/submissions/{run['id']}").json()["quality"] is None
