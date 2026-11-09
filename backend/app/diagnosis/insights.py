"""User competency insights (PRD 5.4 Debugging Reasoning Score, 12.3 progress dashboard).

Small samples are pulled toward a neutral prior (``scoring.shrink``) and labelled with a
confidence level, so a handful of attempts never reads as a definitive measure of ability.
"""
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select

from app import scoring, taxonomy
from app.models import (
    Assessment,
    AssessmentSession,
    ChallengeAttempt,
    Diagnosis,
    FixExplanation,
    Incident,
    IncidentSession,
    Problem,
    Submission,
    now,
)

REASONING_WEIGHTS = {"root_cause_accuracy": 25, "average_diagnosis": 20, "reproduction_quality": 15,
                     "attempts_to_cause": 15, "invariant_identification": 15, "explanation_quality": 10}
DIMENSION_LABELS = {
    "root_cause_accuracy": "Root-cause accuracy", "average_diagnosis": "Average diagnosis score",
    "reproduction_quality": "Reproduction quality", "attempts_to_cause": "Attempts before identifying the cause",
    "invariant_identification": "Invariant identification", "explanation_quality": "Explanation quality",
}
MESSAGES = {
    "insufficient": "Complete at least three challenges with a diagnosis for a meaningful score.",
    "low": "Provisional: based on fewer than ten completed challenges.",
    "moderate": "Moderate confidence: based on ten to twenty-four completed challenges.",
    "high": "High confidence: based on twenty-five or more completed challenges.",
}


def _criterion(record, name: str) -> float | None:
    value = scoring.criterion(record, name)
    return None if value is None else value * 100


def _week_start(value):
    day = value.date()
    return day - timedelta(days=day.weekday())


def _utc(value):
    return value.replace(tzinfo=now().tzinfo) if value is not None and value.tzinfo is None else value


def reasoning_score(db, user) -> dict:
    attempts = list(db.scalars(select(ChallengeAttempt).where(ChallengeAttempt.user_id == user.id)
                               .order_by(ChallengeAttempt.started_at.desc()).limit(300)))
    samples = []
    for attempt in attempts:
        evidence = scoring.attempt_evidence(db, attempt)
        diagnosis = evidence["diagnosis"]
        if diagnosis is None or not evidence["solved"]:
            continue
        attempts_to_cause = evidence["attempts_to_cause"]
        samples.append({
            "root_cause_accuracy": _criterion(diagnosis, "root_cause"),
            "average_diagnosis": diagnosis.score,
            "reproduction_quality": _criterion(diagnosis, "reproduction"),
            "attempts_to_cause": 0.0 if attempts_to_cause is None else 100 / (1 + 0.5 * attempts_to_cause),
            "invariant_identification": _criterion(diagnosis, "invariant"),
            "explanation_quality": evidence["explanation"].score if evidence["explanation"] is not None else None,
        })
    n = len(samples)
    dimensions = {name: scoring.mean(sample[name] for sample in samples) for name in REASONING_WEIGHTS}
    raw = scoring.weighted(dimensions, REASONING_WEIGHTS)
    level = scoring.confidence(n)
    return {
        "score": scoring.shrink(raw, n) if n else None, "raw_score": raw, "sample_size": n,
        "confidence": level, "provisional": n < 10, "message": MESSAGES[level],
        "dimensions": [{"id": name, "name": DIMENSION_LABELS[name], "score": dimensions[name],
                        "weight": REASONING_WEIGHTS[name]} for name in REASONING_WEIGHTS],
    }


def user_insights(db, user) -> dict:
    problems = {problem.id: problem for problem in db.scalars(select(Problem))}
    practice = list(db.scalars(select(Submission).where(Submission.user_id == user.id,
                                                        Submission.assessment_session_id.is_(None))))
    solved = {row.problem_id for row in practice if row.kind == "submit" and row.status == "passed"}
    attempted = {row.problem_id for row in practice}
    attempts = list(db.scalars(select(ChallengeAttempt).where(ChallengeAttempt.user_id == user.id)))
    diagnoses = list(db.scalars(select(Diagnosis).where(Diagnosis.user_id == user.id)))
    latest_diagnosis: dict[int, Diagnosis] = {}
    for row in sorted(diagnoses, key=lambda item: _utc(item.created_at)):
        latest_diagnosis[row.problem_id] = row

    correctness = scoring.mean(attempt.correctness_score for attempt in attempts if attempt.context == "practice")
    quality = scoring.mean(attempt.quality_score for attempt in attempts)

    by_category: dict[str, dict] = defaultdict(lambda: {"attempted": 0, "solved": 0, "diagnosis": []})
    by_skill: dict[str, dict] = defaultdict(lambda: {"attempted": 0, "solved": 0, "diagnosis": []})
    for problem_id in attempted | set(latest_diagnosis):
        problem = problems.get(problem_id)
        if problem is None:
            continue
        classification = taxonomy.classify_problem(problem)
        diagnosis = latest_diagnosis.get(problem_id)
        for bucket, keys in ((by_category, classification["bug_categories"]), (by_skill, classification["skills"])):
            for key in keys:
                entry = bucket[key]
                entry["attempted"] += 1
                entry["solved"] += problem_id in solved
                if diagnosis is not None and diagnosis.score is not None:
                    entry["diagnosis"].append(diagnosis.score)

    def mastery_rows(bucket, catalog):
        rows = []
        for key, entry in bucket.items():
            if key not in catalog:
                continue
            solve_rate = entry["solved"] / entry["attempted"] * 100 if entry["attempted"] else 0
            diagnosis = scoring.mean(entry["diagnosis"])
            raw = solve_rate if diagnosis is None else 0.6 * solve_rate + 0.4 * diagnosis
            rows.append({"id": key, "name": catalog[key]["name"], "attempted": entry["attempted"],
                         "solved": entry["solved"], "diagnosis_score": diagnosis,
                         "mastery": scoring.shrink(raw, entry["attempted"], prior=50, k=3),
                         "confidence": scoring.confidence(entry["attempted"])})
        return sorted(rows, key=lambda row: (-row["attempted"], row["name"]))

    categories = mastery_rows(by_category, taxonomy.BUG_CATEGORIES)
    skills = mastery_rows(by_skill, taxonomy.DEBUGGING_SKILLS)

    incident_rows = db.execute(select(IncidentSession, Incident).join(Incident, IncidentSession.incident_id == Incident.id)
                               .where(IncidentSession.user_id == user.id)
                               .order_by(IncidentSession.started_at.desc()).limit(20)).all()
    incidents = [{"session_id": session.id, "incident_slug": incident.slug, "title": incident.title,
                  "severity": incident.severity, "status": session.status, "score": session.score,
                  "started_at": session.started_at, "resolved_at": session.resolved_at}
                 for session, incident in incident_rows]

    assessment_rows = db.execute(select(AssessmentSession, Assessment)
                                 .join(Assessment, AssessmentSession.assessment_id == Assessment.id)
                                 .where(AssessmentSession.user_id == user.id)
                                 .order_by(AssessmentSession.started_at.desc()).limit(20)).all()
    assessments = []
    for session, assessment in assessment_rows:
        configuration = (session.config_snapshot or {}).get("configuration") or {}
        delayed = configuration.get("feedback") == "delayed"
        assessments.append({"session_id": session.id, "assessment_slug": assessment.slug, "title": assessment.title,
                            "status": session.status, "finalized": session.finalized_at is not None,
                            "score": None if delayed else session.total_score, "score_hidden": delayed,
                            "started_at": session.started_at, "completed_at": session.completed_at})

    today = now()
    weeks = [_week_start(today) - timedelta(weeks=offset) for offset in reversed(range(12))]
    weekly: dict = {week: {"diagnosis": [], "submits": 0, "passed": 0} for week in weeks}
    for row in diagnoses:
        week = _week_start(_utc(row.created_at))
        if week in weekly and row.score is not None:
            weekly[week]["diagnosis"].append(row.score)
    for row in practice:
        if row.kind != "submit" or row.status not in scoring.TERMINAL:
            continue
        week = _week_start(_utc(row.created_at))
        if week in weekly:
            weekly[week]["submits"] += 1
            weekly[week]["passed"] += row.status == "passed"
    trend = [{"week": week.isoformat(), "diagnosis_score": scoring.mean(entry["diagnosis"]),
              "diagnoses": len(entry["diagnosis"]), "submissions": entry["submits"],
              "pass_rate": round(entry["passed"] / entry["submits"] * 100, 1) if entry["submits"] else None}
             for week, entry in weekly.items()]

    weakest = [row["id"] for row in sorted(categories, key=lambda row: (row["mastery"] or 0, row["name"]))][:3]
    if not weakest:
        weakest = list(taxonomy.BUG_CATEGORIES)[:3]
    recommendations = []
    order = {"easy": 0, "medium": 1, "hard": 2}
    for problem in sorted((p for p in problems.values() if p.visibility == "public"),
                          key=lambda item: (order.get(item.difficulty, 3), item.id)):
        if problem.id in solved or len(recommendations) >= 5:
            continue
        bugs = taxonomy.classify_problem(problem)["bug_categories"]
        match = next((bug for bug in weakest if bug in bugs), None)
        if match is None:
            continue
        recommendations.append({"slug": problem.slug, "title": problem.title, "difficulty": problem.difficulty,
                                "category": problem.category, "reason": taxonomy.BUG_CATEGORIES[match]["name"]})

    explanations = db.scalars(select(FixExplanation.score).where(FixExplanation.user_id == user.id))
    return {
        "reasoning": reasoning_score(db, user),
        "patch_correctness": correctness, "engineering_quality": quality,
        "explanation_quality": scoring.mean(explanations),
        "diagnoses": len(diagnoses), "solved": len(solved), "attempted": len(attempted),
        "categories": categories, "skills": skills, "incidents": incidents, "assessments": assessments,
        "trend": trend, "recommendations": recommendations,
        "recommended_concepts": [{"id": concept, "name": taxonomy.CONCEPT_GRAPH[concept]["name"]}
                                 for concept in taxonomy.concepts_for(weakest)][:5],
    }
