"""Assessment scoring and reports (PRD 9.5, 9.6).

Per-challenge scores come from ``app.scoring.refresh_attempt`` — the same evidence and evaluators
used in practice — so assessments never run separate evaluation logic. A report is computed once at
finalization and stored on the session; later changes go only through audited corrections.
"""
import csv
import io
import json
from collections import Counter

from sqlalchemy import func, select

from app import scoring, taxonomy
from app.auth import utc
from app.models import AIInteraction, Hint, Problem, Submission, User, now

REPORT_VERSION = "assessment-report-v1"
TERMINAL = scoring.TERMINAL
DIMENSION_NAMES = {"diagnosis": "Diagnosis and root cause", "correctness": "Patch correctness",
                   "verification": "Test coverage and verification", "quality": "Code quality",
                   "explanation": "Explanation quality", "time": "Time efficiency"}
RECOVERY_RULE = ("Work is saved on the server as it happens. After a disconnection, reopen the session before the "
                 "deadline to continue: the timer keeps running while you are away, and the session is finalized "
                 "automatically at the deadline with the work saved so far.")
RECOMMENDATIONS = {
    "race_condition": "Improve concurrency debugging: practice check-then-act races and atomic updates.",
    "deadlock": "Practice lock ordering and channel/queue hand-off analysis.",
    "database_transactions": "Practice transaction boundary analysis.",
    "retry_idempotency": "Review API idempotency patterns and safe retry design.",
    "caching": "Practice cache invalidation and read/write ordering traces.",
    "distributed_consistency": "Practice reasoning about replicas, quorums and event ordering.",
    "authorization": "Review ownership and permission checks on every path.",
    "authentication": "Review credential and token validation rules.",
    "validation": "Practice deriving validation rules from business invariants.",
    "time_handling": "Practice time-zone, deadline and clock reasoning.",
    "boundary_condition": "Practice boundary analysis: empty inputs, limits and off-by-one cases.",
    "nullability": "Practice tracing missing and optional values through the code.",
    "runtime_exception": "Practice reading stack traces back to the failing precondition.",
    "numeric_precision": "Review integer width, rounding and floating-point behavior.",
    "serialization": "Practice differential debugging of parsing and encoding paths.",
    "state_corruption": "Practice state inspection: aliasing, mutation and partial updates.",
    "resource_leak": "Review resource lifecycles and cleanup on error paths.",
    "configuration": "Review how limits, defaults and timeouts are configured.",
    "observability": "Practice log investigation and error aggregation.",
    "data_reasoning": "Review metric and model-evaluation definitions.",
    "logic_error": "Practice invariant reasoning on small reproductions.",
}
DIMENSION_RECOMMENDATIONS = {
    "diagnosis": ("Root-cause analysis", "Name the violated invariant and the exact operation that breaks it before "
                  "changing code."),
    "verification": ("Reproduction and verification", "Improve reproduction strategies: run the failing case "
                     "first and design targeted tests before submitting."),
    "explanation": ("Explaining fixes", "Strengthen test design and fix explanations: say why the original failed "
                    "and which cases guard the fix."),
    "quality": ("Patch quality", "Keep patches minimal and focused, and avoid swallowing errors."),
}


def _mean(values):
    return scoring.mean([value for value in values if value is not None])


def _label(classification):
    return {"bug_categories": classification["bug_categories"], "skills": classification["skills"]}


def session_problems(db, session) -> list[Problem]:
    problems = {row.id: row for row in db.scalars(select(Problem).where(Problem.id.in_(session.challenge_order or [])))}
    return [problems[int(pid)] for pid in session.challenge_order or [] if int(pid) in problems]


def challenge_result(db, session, position, problem, attempt, weights, configuration) -> dict:
    classification = taxonomy.classify_problem(problem)
    base = {"position": position, "problem_id": problem.id, "slug": problem.slug, "title": problem.title,
            "category": problem.category, "difficulty": problem.difficulty, "problem_version": problem.version,
            **_label(classification)}
    if attempt is None:
        components = {key: None for key in scoring.ASSESSMENT_WEIGHTS}
        used = {key: value for key, value in weights.items()
                if key != "explanation" or configuration.get("explanation_required")}
        return {**base, "status": "not_started", "attempt_id": None, "components": components,
                "weights": used, "total": scoring.weighted(components, used, missing="zero") or 0.0,
                "submissions": 0, "runs": 0, "time_spent_seconds": 0.0, "hints": 0, "ai_interactions": 0,
                "ai_submissions": 0, "diagnosis_revisions": 0, "diagnosis_submitted": False,
                "explanation_submitted": False, "failed_statuses": [], "attempts_to_cause": None,
                "versions": {"scoring": scoring.SCORING_VERSION}}
    breakdown = scoring.refresh_attempt(db, attempt, weights=weights, missing="zero")
    components = dict(breakdown["components"])
    used = dict(weights)
    # A missing optional explanation is not penalized; a required one scores zero.
    if components.get("explanation") is None and not configuration.get("explanation_required"):
        used.pop("explanation", None)
    total = scoring.weighted(components, used, missing="zero") or 0.0
    attempt.total_score = total
    evidence = breakdown["evidence"]
    status = "solved" if evidence["solved"] else "attempted" if (evidence["submissions"] or evidence["runs"]
                                                               or evidence["diagnosis_revisions"]) else "not_started"
    return {**base, "status": status, "attempt_id": attempt.id, "components": components, "weights": used,
            "total": total, "submissions": evidence["submissions"], "runs": evidence["runs"],
            "time_spent_seconds": evidence["time_spent_seconds"] if status != "not_started" else 0.0,
            "hints": evidence["hints"], "ai_interactions": evidence["ai_interactions"],
            "ai_submissions": evidence["ai_submissions"], "diagnosis_revisions": evidence["diagnosis_revisions"],
            "diagnosis_submitted": evidence["diagnosis_revisions"] > 0,
            "explanation_submitted": components.get("explanation") is not None,
            "failed_statuses": evidence["failed_statuses"], "attempts_to_cause": evidence["attempts_to_cause"],
            "versions": breakdown["versions"]}


def competency_breakdown(challenges: list[dict]) -> list[dict]:
    rows = []
    for area_id, area in taxonomy.COMPETENCY_AREAS.items():
        dimension = area["dimension"]
        relevant = challenges
        if area.get("bug_categories"):
            relevant = [row for row in challenges if set(row["bug_categories"]) & set(area["bug_categories"])]
        elif area.get("skills"):
            relevant = [row for row in challenges if set(row["skills"]) & set(area["skills"])] or challenges
        if dimension == "quality":
            values = [row["components"].get("quality") for row in relevant if row["status"] == "solved"]
            score = _mean(values)
        else:
            score = _mean([row["components"].get(dimension) or 0.0 for row in relevant]) if relevant else None
        rows.append({"id": area_id, "name": area["name"], "dimension": dimension, "score": score,
                     "evidence_count": len(relevant), "assessed": score is not None})
    return rows


def profile_match(challenges: list[dict], competencies: list[dict], weights: dict | None) -> dict | None:
    """Role-specific competency profile (Phase 6). Keys may be competency, bug-category or skill ids."""
    if not weights:
        return None
    by_area = {row["id"]: row["score"] for row in competencies}
    parts = []
    for key, weight in weights.items():
        if key in by_area:
            score = by_area[key]
        elif key in taxonomy.BUG_CATEGORIES:
            score = _mean([row["total"] for row in challenges if key in row["bug_categories"]])
        elif key in taxonomy.DEBUGGING_SKILLS:
            score = _mean([row["total"] for row in challenges if key in row["skills"]])
        else:
            score = None
        parts.append({"id": key, "weight": weight, "score": score})
    scored = [part for part in parts if part["score"] is not None and part["weight"] > 0]
    total_weight = sum(part["weight"] for part in scored)
    return {"score": round(sum(part["weight"] * part["score"] for part in scored) / total_weight, 2)
            if total_weight else None,
            "coverage": round(len(scored) / len(parts), 2) if parts else 0.0, "components": parts}


def behavioral_metrics(db, session, challenges: list[dict]) -> dict:
    started = [row for row in challenges if row["status"] != "not_started"]
    failed = Counter(dict(db.execute(
        select(Submission.status, func.count()).where(Submission.assessment_session_id == session.id,
                                                      Submission.kind == "submit",
                                                      Submission.status.in_(TERMINAL - {"passed"}))
        .group_by(Submission.status)).all()))
    diagnosed = [row for row in challenges if row["diagnosis_submitted"]]
    explained = [row for row in challenges if row["explanation_submitted"]]
    submissions = sum(row["submissions"] for row in challenges)
    return {
        "submissions": submissions, "runs": sum(row["runs"] for row in challenges),
        "avg_submissions_per_challenge": round(submissions / len(started), 2) if started else 0.0,
        "diagnosis_accuracy": _mean([row["components"].get("diagnosis") for row in diagnosed]),
        "diagnosis_coverage": round(len(diagnosed) / len(challenges), 2) if challenges else 0.0,
        "hints_used": sum(row["hints"] for row in challenges),
        "ai_interactions": sum(row["ai_interactions"] for row in challenges),
        "ai_submissions": sum(row["ai_submissions"] for row in challenges),
        "avg_time_per_challenge_seconds": _mean([row["time_spent_seconds"] for row in started]),
        "failed_test_patterns": dict(sorted(failed.items())),
        "explanation_quality": _mean([row["components"].get("explanation") for row in explained]),
        "explanations_submitted": len(explained),
        "challenges_started": len(started),
    }


def development_areas(db, challenges: list[dict]) -> list[dict]:
    exclude = {row["problem_id"] for row in challenges}
    areas = []
    by_category: dict[str, list[dict]] = {}
    for row in challenges:
        for bug in row["bug_categories"]:
            by_category.setdefault(bug, []).append(row)
    for bug, rows in by_category.items():
        average = _mean([row["total"] for row in rows])
        if average is None or average >= 60:
            continue
        solved = sum(row["status"] == "solved" for row in rows)
        areas.append({"id": bug, "area": taxonomy.BUG_CATEGORIES[bug]["name"], "score": average,
                      "evidence": f"{solved} of {len(rows)} challenge(s) involving "
                                  f"{taxonomy.BUG_CATEGORIES[bug]['name'].lower()} solved; average score "
                                  f"{average:.0f}%.",
                      "recommendation": RECOMMENDATIONS.get(bug, "Practice more challenges in this category."),
                      "practice": practice_suggestions(db, bug, exclude)})
    started = [row for row in challenges if row["status"] != "not_started"]
    for dimension, (name, recommendation) in DIMENSION_RECOMMENDATIONS.items():
        rows = [row for row in started if row["components"].get(dimension) is not None] if dimension in {
            "explanation", "quality"} else started
        values = [row["components"].get(dimension) or 0.0 for row in rows]
        average = _mean(values)
        threshold = 60 if dimension == "quality" else 50
        if average is None or average >= threshold:
            continue
        areas.append({"id": dimension, "area": name, "score": average,
                      "evidence": f"{DIMENSION_NAMES[dimension]} averaged {average:.0f}% across {len(rows)} "
                                  f"challenge(s).", "recommendation": recommendation, "practice": []})
    areas.sort(key=lambda row: (row["score"], row["area"]))
    return areas[:5]


def practice_suggestions(db, bug: str, exclude: set[int], limit: int = 3) -> list[dict]:
    order = {"easy": 0, "medium": 1, "hard": 2}
    rows = [problem for problem in db.scalars(select(Problem).where(Problem.visibility == "public")
                                              .order_by(Problem.id))
            if problem.id not in exclude and bug in taxonomy.classify_problem(problem)["bug_categories"]]
    rows.sort(key=lambda problem: (order.get(problem.difficulty, 3), problem.id))
    return [{"slug": problem.slug, "title": problem.title, "difficulty": problem.difficulty} for problem in rows[:limit]]


def assistance_summary(db, session, challenges: list[dict]) -> dict:
    policy = (session.config_snapshot or {}).get("assistance_policy") or {}
    hints = db.scalar(select(func.count()).select_from(Hint).where(Hint.assessment_session_id == session.id)) or 0
    interactions = db.scalar(select(func.count()).select_from(AIInteraction)
                             .where(AIInteraction.assessment_session_id == session.id)) or 0
    ai_submissions = db.scalar(select(func.count()).select_from(Submission).where(
        Submission.assessment_session_id == session.id, Submission.mode == "ai")) or 0
    ai, hint_policy = policy.get("ai", "disabled"), policy.get("hints", "disabled")
    return {"policy": {"ai": ai, "hints": hint_policy}, "hints_used": hints, "ai_interactions": interactions,
            "ai_submissions": ai_submissions, "assisted": bool(hints or interactions or ai_submissions),
            "unaided_policy": ai == "disabled" and hint_policy == "disabled"}


def disclaimers(session, challenges: list[dict], assistance: dict, unfinished: int) -> list[str]:
    snapshot = session.config_snapshot or {}
    notes = [f"This report reflects one timed assessment of {len(challenges)} challenge(s). It is evidence about "
             "specific debugging tasks, not a measure of overall engineering ability."]
    policy = assistance["policy"]
    if policy["ai"] != "disabled":
        used = assistance["ai_interactions"] + assistance["ai_submissions"]
        notes.append(f"AI assistance was permitted ({policy['ai']}) and used {used} time(s). This result does not "
                     "represent unaided ability.")
    if policy["hints"] != "disabled":
        notes.append(f"Hints were permitted ({policy['hints']}) and {assistance['hints_used']} were used.")
    if snapshot.get("assessment_type") == "practice":
        notes.append("Practice assessment: results support learning and are reported separately from "
                     "restricted assessments.")
    if session.status == "expired":
        notes.append("The session ended at its time limit; challenges without accepted work score according to "
                     "the evidence recorded before the deadline.")
    if unfinished:
        notes.append(f"{unfinished} evaluation(s) did not finish before finalization and were not counted.")
    return notes


def build_report(db, session, attempts: dict, *, unfinished: int = 0) -> dict:
    snapshot = session.config_snapshot or {}
    configuration = snapshot.get("configuration") or {}
    weights = ((snapshot.get("scoring_rubric") or {}).get("weights")) or dict(scoring.ASSESSMENT_WEIGHTS)
    problems = session_problems(db, session)
    challenges = [challenge_result(db, session, position, problem, attempts.get(problem.id), weights, configuration)
                  for position, problem in enumerate(problems, 1)]
    return assemble(db, session, challenges, weights, unfinished=unfinished)


def assemble(db, session, challenges: list[dict], weights: dict, *, unfinished: int = 0,
             corrections: list | None = None, report_version: int = 1) -> dict:
    snapshot = session.config_snapshot or {}
    user = db.get(User, session.user_id)
    total = round(sum(row["total"] for row in challenges) / len(challenges), 2) if challenges else 0.0
    competencies = competency_breakdown(challenges)
    assistance = assistance_summary(db, session, challenges)
    ended = utc(session.completed_at) if session.completed_at else now()
    return {
        "version": REPORT_VERSION, "report_version": report_version,
        "summary": {
            "candidate": {"id": session.user_id, "username": user.username if user else None},
            "assessment": {"id": snapshot.get("assessment_id"), "slug": snapshot.get("slug"),
                           "title": snapshot.get("title"), "type": snapshot.get("assessment_type"),
                           "version": snapshot.get("version")},
            "status": session.status, "total_score": total,
            "time_spent_seconds": round(max(0.0, (ended - utc(session.started_at)).total_seconds()), 1),
            "duration_seconds": snapshot.get("duration_seconds"),
            "challenges_completed": sum(row["status"] == "solved" for row in challenges),
            "challenges_total": len(challenges),
            "started_at": utc(session.started_at).isoformat(), "ended_at": ended.isoformat(),
            "evaluated_at": now().isoformat(),
        },
        "weights": weights, "challenges": challenges, "competencies": competencies,
        "profile": profile_match(challenges, competencies, snapshot.get("competency_profile")),
        "behavior": behavioral_metrics(db, session, challenges),
        "development_areas": development_areas(db, challenges),
        "assistance": assistance,
        "disclaimers": disclaimers(session, challenges, assistance, unfinished),
        "recovery_rule": RECOVERY_RULE,
        "versions": {"report": REPORT_VERSION, "scoring": scoring.SCORING_VERSION,
                     "taxonomy": taxonomy.TAXONOMY_VERSION, "assessment": snapshot.get("version")},
        "corrections": corrections or [],
    }


def summary_view(report: dict) -> dict:
    """What a candidate sees when the assessment shares only a summary (typical for interviews)."""
    return {"version": report["version"], "report_version": report["report_version"], "level": "summary",
            "summary": report["summary"],
            "challenges": [{key: row[key] for key in ("position", "title", "status", "total")}
                           for row in report["challenges"]],
            "disclaimers": report["disclaimers"], "recovery_rule": report.get("recovery_rule")}


def full_view(report: dict) -> dict:
    return {**report, "level": "full"}


def export(report: dict, fmt: str) -> tuple[str, str]:
    """Return (body, media type) for json, csv or md."""
    if fmt == "json":
        return json.dumps(report, indent=2, default=str), "application/json"
    summary = report["summary"]
    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["assessment", summary["assessment"]["title"]])
        writer.writerow(["candidate", summary["candidate"]["username"]])
        writer.writerow(["status", summary["status"]])
        writer.writerow(["total_score", summary["total_score"]])
        writer.writerow([])
        dims = list(scoring.ASSESSMENT_WEIGHTS)
        detailed = report.get("level") == "full"
        writer.writerow(["position", "challenge", "status", "total"] + (dims + ["submissions", "time_spent_seconds"]
                                                                         if detailed else []))
        for row in report["challenges"]:
            values = [row["position"], row["title"], row["status"], row["total"]]
            if detailed:
                values += [row["components"].get(dim) for dim in dims] + [row["submissions"],
                                                                          row["time_spent_seconds"]]
            writer.writerow(values)
        if detailed:
            writer.writerow([])
            writer.writerow(["competency", "score", "evidence_count"])
            for row in report["competencies"]:
                writer.writerow([row["name"], row["score"], row["evidence_count"]])
        return buffer.getvalue(), "text/csv"
    lines = [f"# {summary['assessment']['title']} — assessment report", "",
             f"- Candidate: {summary['candidate']['username']}", f"- Status: {summary['status']}",
             f"- Total score: {summary['total_score']}",
             f"- Challenges completed: {summary['challenges_completed']} of {summary['challenges_total']}",
             f"- Time spent: {round(summary['time_spent_seconds'] / 60, 1)} min", "", "## Challenges", "",
             "| # | Challenge | Status | Score |", "| --- | --- | --- | --- |"]
    lines += [f"| {row['position']} | {row['title']} | {row['status']} | {row['total']} |" for row in report["challenges"]]
    if report.get("level") == "full":
        lines += ["", "## Competencies", "", "| Area | Score | Evidence |", "| --- | --- | --- |"]
        lines += [f"| {row['name']} | {'—' if row['score'] is None else row['score']} | {row['evidence_count']} |"
                  for row in report["competencies"]]
        behavior = report["behavior"]
        lines += ["", "## Behavioral metrics", "", f"- Submissions: {behavior['submissions']}",
                  f"- Diagnosis accuracy: {behavior['diagnosis_accuracy']}",
                  f"- Hints used: {behavior['hints_used']}",
                  f"- AI interactions: {behavior['ai_interactions']} (AI submissions: {behavior['ai_submissions']})",
                  f"- Failed test patterns: {behavior['failed_test_patterns'] or 'none'}"]
        if report["development_areas"]:
            lines += ["", "## Recommended development areas", ""]
            lines += [f"- **{row['area']}** — {row['evidence']} {row['recommendation']}"
                      for row in report["development_areas"]]
        if report.get("corrections"):
            lines += ["", "## Corrections", ""]
            lines += [f"- v{row['report_version']}: {row['reason']} ({row['before_total']} → {row['after_total']})"
                      for row in report["corrections"]]
    lines += ["", "## Notes", ""] + [f"- {note}" for note in report["disclaimers"]]
    return "\n".join(lines) + "\n", "text/markdown"
