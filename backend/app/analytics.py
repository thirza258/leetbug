import math
from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import func, select

from app.models import Activity, Problem, Submission, User, now

TERMINAL = {"passed", "failed", "runtime_error", "time_limit", "memory_limit", "output_limit"}


def percentile(values, q=0.95):
    ordered = sorted(value for value in values if value is not None)
    if not ordered:
        return None
    return round(ordered[max(0, math.ceil(q * len(ordered)) - 1)], 2)


def summary(rows):
    evaluated = [row for row in rows if row.kind == "submit" and row.status in TERMINAL]
    mode_counts = Counter(row.mode for row in evaluated)
    passed = sum(row.status == "passed" for row in evaluated)
    return {
        "attempts": len(evaluated), "passed_attempts": passed,
        "completion_rate": round(passed / len(evaluated) * 100, 1) if evaluated else 0,
        "manual_attempts": mode_counts["manual"], "ai_attempts": mode_counts["ai"],
        "manual_p95_ms": percentile([row.turnaround_ms for row in evaluated if row.mode == "manual"]),
        "ai_p95_ms": percentile([row.turnaround_ms for row in evaluated if row.mode == "ai"]),
    }


def personal_stats(db, user):
    rows = list(db.scalars(select(Submission).where(Submission.user_id == user.id)))
    solved = {row.problem_id for row in rows if row.kind == "submit" and row.status == "passed"}
    problems = list(db.scalars(select(Problem)))
    activities = set(db.scalars(select(Activity.day).where(Activity.user_id == user.id)))
    today = now().date()
    cursor = today if today in activities else today - timedelta(days=1)
    streak = 0
    while cursor in activities:
        streak += 1
        cursor -= timedelta(days=1)
    daily = Counter(row.created_at.date() for row in rows if row.kind == "submit" and row.status in TERMINAL)
    categories = [{"category": category, "solved": sum(p.id in solved and p.category == category for p in problems),
                   "total": sum(p.category == category for p in problems)}
                  for category in ["runtime", "logic", "business", "edge"]]
    return {**summary(rows), "solved": len(solved), "total_problems": len(problems), "streak": streak,
            "categories": categories,
            "activity": [{"date": (today - timedelta(days=offset)).isoformat(),
                          "count": daily[today - timedelta(days=offset)]} for offset in reversed(range(91))],
            "achievements": [
                {"name": "First fix", "description": "Solve your first case study", "unlocked": bool(solved)},
                {"name": "Bug explorer", "description": "Solve a case in all four categories", "unlocked": all(c["solved"] for c in categories)},
                {"name": "Lead engineer", "description": "Solve a case with an AI directive", "unlocked": any(r.status == "passed" and r.kind == "submit" and r.mode == "ai" for r in rows)},
                {"name": "In the flow", "description": "Be active for seven consecutive days", "unlocked": streak >= 7},
            ]}


def platform_stats(db):
    today = now().date()
    rows = list(db.scalars(select(Submission)))
    active = list(db.execute(select(Activity.user_id, Activity.day)))
    first = {}
    for user_id, day in active:
        first[user_id] = min(first.get(user_id, day), day)
    mature = [user_id for user_id, day in first.items() if day <= today - timedelta(days=7)]
    first_cases = defaultdict(set)
    for row in rows:
        if row.status in TERMINAL and row.created_at.date() == first.get(row.user_id):
            first_cases[row.user_id].add(row.problem_id)
    # A later login alone is not debugging retention: evaluate a new case on a later day.
    returned = {
        row.user_id for row in rows
        if row.status in TERMINAL and row.user_id in first
        and first[row.user_id] < row.created_at.date() <= first[row.user_id] + timedelta(days=7)
        and row.problem_id not in first_cases[row.user_id]
    }
    retained = sum(user_id in returned for user_id in mature)
    return {**summary(rows), "registered_users": db.scalar(select(func.count()).select_from(User)),
            "monthly_active_users": len({uid for uid, day in active if day >= today - timedelta(days=29)}),
            "retention_7d": round(retained / len(mature) * 100, 1) if mature else None,
            "retention_cohort_size": len(mature), "manual_target_ms": 2500, "ai_target_ms": 5000}


def leaderboard_rows(db, mode, problem_id):
    query = select(Submission, User.username).join(User, Submission.user_id == User.id).where(
        Submission.kind == "submit", Submission.status == "passed")
    if mode == "ai":
        query = query.where(Submission.mode == "ai")
    if problem_id:
        query = query.where(Submission.problem_id == problem_id)
    grouped = {}
    for submission, username in db.execute(query):
        user = grouped.setdefault(submission.user_id, {"user_id": submission.user_id, "username": username, "best": {}})
        old = user["best"].get(submission.problem_id)
        key = (submission.prompt_words, submission.runtime_ms or math.inf) if mode == "ai" else (submission.runtime_ms or math.inf,)
        if old is None or key < old[0]:
            user["best"][submission.problem_id] = (key, submission)
    result = []
    for user in grouped.values():
        best = [item[1] for item in user.pop("best").values()]
        result.append({**user, "solved": len(best),
                       "prompt_words": round(sum(row.prompt_words for row in best) / len(best), 1) if mode == "ai" else None,
                       "runtime_ms": round(sum(row.runtime_ms or 0 for row in best) / len(best), 2)})
    result.sort(key=lambda row: (-row["solved"], row["prompt_words"] or 0, row["runtime_ms"], row["username"]))
    return [{**row, "rank": index} for index, row in enumerate(result[:100], 1)]
