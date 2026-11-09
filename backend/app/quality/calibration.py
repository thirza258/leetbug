"""Difficulty calibration from observed behavior (PRD 10.3).

Suggestions appear only when a problem has enough independent learners, and they are advisory:
nothing here changes a problem's difficulty. Assessment work is excluded so that restricted,
timed sessions do not distort practice difficulty.
"""
from collections import defaultdict
from datetime import timedelta
from statistics import median

from sqlalchemy import select

from app.analytics import TERMINAL
from app.models import AIInteraction, ChallengeAttempt, Diagnosis, Hint, Problem, Submission, now
from app.quality.pipeline import aware
from app.scoring import confidence

ABANDONED_AFTER = timedelta(days=7)
EXPERIENCED_SOLVES = 10
DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def _hidden_only_failure(results: list) -> bool:
    public = [row for row in results or [] if isinstance(row, dict) and not row.get("hidden")]
    hidden = [row for row in results or [] if isinstance(row, dict) and row.get("hidden")]
    return bool(public) and all(row.get("status") == "passed" for row in public) and any(
        row.get("status") != "passed" for row in hidden)


def suggest(item: dict, difficulty: str, estimated_minutes: int, min_samples: int) -> dict | None:
    if item["samples"] < min_samples:
        return None
    solve_rate = (item["solve_rate"] or 0) / 100
    median_seconds = item["median_solve_seconds"]
    budget = max(60, (estimated_minutes or 15) * 60)
    index = DIFFICULTY_ORDER.index(difficulty) if difficulty in DIFFICULTY_ORDER else 1
    if solve_rate >= 0.85 and median_seconds is not None and median_seconds <= 0.6 * budget and index > 0:
        return {"difficulty": DIFFICULTY_ORDER[index - 1], "direction": "easier", "applied": False,
                "reason": f"{item['solve_rate']}% solve rate with a median solve time well under the estimate."}
    if (solve_rate <= 0.35 or (median_seconds is not None and median_seconds >= 2 * budget)) and index < 2:
        return {"difficulty": DIFFICULTY_ORDER[index + 1], "direction": "harder", "applied": False,
                "reason": f"{item['solve_rate']}% solve rate; median solve time "
                          f"{'n/a' if median_seconds is None else round(median_seconds / 60, 1)} min vs "
                          f"{estimated_minutes} min estimated."}
    return {"difficulty": difficulty, "direction": "consistent", "applied": False,
            "reason": "Observed behavior matches the labeled difficulty."}


def calibration(db, *, min_samples: int = 20) -> list[dict]:
    problems = {problem.id: problem for problem in db.scalars(select(Problem).where(Problem.visibility == "public"))}
    rows = list(db.execute(select(Submission.user_id, Submission.problem_id, Submission.kind, Submission.status,
                                  Submission.mode, Submission.results, Submission.created_at, Submission.completed_at)
                           .where(Submission.assessment_session_id.is_(None))
                           .order_by(Submission.created_at)))
    started = {(row.user_id, row.problem_id): aware(row.started_at) for row in db.execute(
        select(ChallengeAttempt.user_id, ChallengeAttempt.problem_id, ChallengeAttempt.started_at)
        .where(ChallengeAttempt.context == "practice"))}
    hints = {(row.user_id, row.problem_id) for row in db.execute(select(Hint.user_id, Hint.problem_id))}
    assistant = {(row.user_id, row.problem_id) for row in db.execute(select(AIInteraction.user_id,
                                                                            AIInteraction.problem_id))}
    diagnosis_scores = defaultdict(list)
    for row in db.execute(select(Diagnosis.user_id, Diagnosis.problem_id, Diagnosis.score)
                          .where(Diagnosis.assessment_session_id.is_(None))):
        if row.score is not None:
            diagnosis_scores[(row.user_id, row.problem_id)].append(row.score)
    learners: dict[tuple, dict] = {}
    solved_per_user = defaultdict(set)
    for row in rows:
        if row.problem_id not in problems:
            continue
        key = (row.user_id, row.problem_id)
        entry = learners.setdefault(key, {"first": aware(row.created_at), "last": aware(row.created_at),
                                          "solved_at": None, "submits": 0, "hidden_failures": 0, "ai": False})
        entry["last"] = max(entry["last"], aware(row.completed_at or row.created_at))
        entry["ai"] = entry["ai"] or row.mode == "ai"
        if row.kind == "submit" and row.status in TERMINAL and entry["solved_at"] is None:
            entry["submits"] += 1
            if _hidden_only_failure(row.results):
                entry["hidden_failures"] += 1
            if row.status == "passed":
                entry["solved_at"] = aware(row.completed_at or row.created_at)
                solved_per_user[row.user_id].add(row.problem_id)
    by_problem = defaultdict(list)
    for (user_id, problem_id), entry in learners.items():
        entry["start"] = min(value for value in (entry["first"], started.get((user_id, problem_id))) if value)
        entry["user_id"] = user_id
        entry["hint"] = (user_id, problem_id) in hints
        entry["ai"] = entry["ai"] or (user_id, problem_id) in assistant
        scores = diagnosis_scores.get((user_id, problem_id))
        entry["diagnosis"] = scores[-1] if scores else None
        by_problem[problem_id].append(entry)
    current = now()
    items = []
    for problem_id, entries in by_problem.items():
        problem = problems[problem_id]
        solved = [entry for entry in entries if entry["solved_at"]]
        solve_times = [(entry["solved_at"] - entry["start"]).total_seconds() for entry in solved]
        submits = sum(entry["submits"] for entry in entries)
        diagnoses = [entry["diagnosis"] for entry in entries if entry["diagnosis"] is not None]
        cohorts = {}
        for name, members in (("novice", [e for e in entries if len(solved_per_user[e["user_id"]]) < EXPERIENCED_SOLVES]),
                              ("experienced", [e for e in entries if len(solved_per_user[e["user_id"]]) >= EXPERIENCED_SOLVES])):
            cohorts[name] = {"samples": len(members),
                             "solve_rate": _rate(sum(1 for e in members if e["solved_at"]), len(members))
                             if len(members) >= 5 else None}
        item = {
            "problem_id": problem.id, "slug": problem.slug, "title": problem.title, "category": problem.category,
            "difficulty": problem.difficulty, "estimated_minutes": problem.estimated_minutes,
            "samples": len(entries), "solved": len(solved), "solve_rate": _rate(len(solved), len(entries)),
            "median_solve_seconds": round(median(solve_times), 1) if solve_times else None,
            "avg_submissions": round(submits / len(entries), 2) if entries else None,
            "diagnosis_accuracy": round(sum(diagnoses) / len(diagnoses), 1) if diagnoses else None,
            "hint_usage_rate": _rate(sum(1 for entry in entries if entry["hint"]), len(entries)),
            "abandonment_rate": _rate(sum(1 for entry in entries if not entry["solved_at"]
                                          and current - entry["last"] >= ABANDONED_AFTER), len(entries)),
            "hidden_failure_rate": _rate(sum(entry["hidden_failures"] for entry in entries), submits),
            "ai_dependency_rate": _rate(sum(1 for entry in solved if entry["ai"]), len(solved)),
            "cohorts": cohorts, "confidence": confidence(len(entries)),
        }
        item["suggestion"] = suggest(item, problem.difficulty, problem.estimated_minutes, min_samples)
        items.append(item)
    items.sort(key=lambda item: (-item["samples"], item["problem_id"]))
    return items
