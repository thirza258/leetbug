"""Organization reporting (PRD 9.7, 14.5): candidate lists, analytics, comparison and exports.

Everything here reads the immutable reports stored on finalized assessment sessions, so numbers match
what candidates and reviewers saw (including audited corrections). Statistics that need a sample are
withheld below a threshold instead of being shown with false precision.
"""
import csv
import io
import json
import statistics
from collections import Counter

from fastapi import HTTPException

from app import taxonomy
from app.assessments import report as reports
from app.models import Assessment, AssessmentSession
from app.organizations import service

DISCRIMINATION_MIN_SESSIONS = 10
GROUP_SHARE = 0.27
BUCKETS = [(start, start + 10) for start in range(0, 100, 10)]
HIRING_CAVEAT = ("These results are evidence about specific debugging tasks. They support, and do not replace, "
                 "human hiring decisions; review each candidate's full report and context.")


def _round(value):
    return None if value is None else round(float(value), 2)


def _mean(values):
    values = [float(value) for value in values if value is not None]
    return _round(sum(values) / len(values)) if values else None


def _usage(report: dict) -> dict:
    assistance = report.get("assistance") or {}
    return {"ai": (assistance.get("ai_interactions") or 0) + (assistance.get("ai_submissions") or 0),
            "hints": assistance.get("hints_used") or 0,
            "policy": assistance.get("policy") or {"ai": "disabled", "hints": "disabled"}}


def session_row(session: AssessmentSession, assessment: Assessment, candidate) -> dict:
    report = session.report or {}
    summary = report.get("summary") or {}
    usage = _usage(report)
    return {
        "session_id": session.id, "assessment_id": assessment.id, "assessment_slug": assessment.slug,
        "assessment_title": assessment.title, "assessment_version": (session.config_snapshot or {}).get("version"),
        "candidate": {"id": candidate.id, "username": candidate.username, "email": candidate.email},
        "status": session.status, "started_at": service.iso(session.started_at),
        "completed_at": service.iso(session.completed_at), "finalized_at": service.iso(session.finalized_at),
        "total_score": session.total_score, "report_version": session.report_version,
        "released": bool((session.scoring_details or {}).get("released_at")),
        "challenges_completed": summary.get("challenges_completed"),
        "challenges_total": summary.get("challenges_total"),
        "time_spent_seconds": summary.get("time_spent_seconds"),
        "ai_used": usage["ai"], "hints_used": usage["hints"], "assistance_policy": usage["policy"],
        "corrected": bool(report.get("corrections")),
    }


def candidates(db, org, assessment_id: str | None = None) -> list[dict]:
    rows = service.finalized_sessions(db, org, assessment_id)
    return [session_row(session, assessment, candidate) for session, assessment, candidate in reversed(rows)]


def histogram(scores: list[float]) -> list[dict]:
    counts = [0] * len(BUCKETS)
    for value in scores:
        counts[min(len(BUCKETS) - 1, max(0, int(float(value) // 10)))] += 1
    return [{"from": start, "to": end, "count": count} for (start, end), count in zip(BUCKETS, counts, strict=True)]


def challenge_statistics(sessions: list[AssessmentSession]) -> list[dict]:
    """Per-challenge difficulty (mean correctness) and discrimination index.

    Discrimination compares the share of candidates who solved a challenge in the top and bottom 27%
    of total scores. It is only reported with at least ``DISCRIMINATION_MIN_SESSIONS`` sessions.
    """
    ranked = sorted(sessions, key=lambda row: (row.total_score or 0.0, row.id), reverse=True)
    group = max(1, round(len(ranked) * GROUP_SHARE))
    upper, lower = ranked[:group], ranked[-group:]
    by_slug: dict[str, dict] = {}
    for session in ranked:
        for row in (session.report or {}).get("challenges", []):
            slug = row.get("slug") or str(row.get("problem_id"))
            entry = by_slug.setdefault(slug, {"slug": slug, "title": row.get("title"),
                                              "difficulty": row.get("difficulty"), "rows": {}})
            entry["rows"][session.id] = row

    def solved_share(group_sessions, rows):
        present = [rows[session.id] for session in group_sessions if session.id in rows]
        return sum(row.get("status") == "solved" for row in present) / len(present) if present else None

    items = []
    for entry in by_slug.values():
        rows = entry["rows"]
        values = list(rows.values())
        sufficient = len(values) >= DISCRIMINATION_MIN_SESSIONS
        high, low = solved_share(upper, rows), solved_share(lower, rows)
        items.append({
            "slug": entry["slug"], "title": entry["title"], "difficulty_label": entry["difficulty"],
            "sessions": len(values),
            "mean_correctness": _mean([(row.get("components") or {}).get("correctness") or 0.0 for row in values]),
            "mean_score": _mean([row.get("total") for row in values]),
            "solve_rate": _round(sum(row.get("status") == "solved" for row in values) / len(values)) if values else None,
            "discrimination_index": _round(high - low) if sufficient and high is not None and low is not None else None,
            "discrimination_status": "ok" if sufficient else "insufficient_data",
        })
    items.sort(key=lambda row: (row["mean_correctness"] if row["mean_correctness"] is not None else 101))
    return items


def analytics(db, org, assessment_id: str | None = None) -> dict:
    from sqlalchemy import select
    assessments = list(db.scalars(select(Assessment).where(Assessment.organization_id == org.id)
                                  .order_by(Assessment.created_at)))
    if assessment_id and assessment_id not in {row.id for row in assessments}:
        raise HTTPException(404, "Assessment not found.")
    selected = [row for row in assessments if not assessment_id or row.id == assessment_id]
    ids = [row.id for row in selected]
    all_sessions = list(db.scalars(select(AssessmentSession).where(AssessmentSession.assessment_id.in_(ids)))) if ids else []
    finalized = [row for row in all_sessions if row.finalized_at is not None and row.report]
    per_assessment = []
    for assessment in selected:
        rows = [row for row in all_sessions if row.assessment_id == assessment.id]
        done = [row for row in rows if row.finalized_at is not None and row.report]
        closed = [row for row in rows if row.status in {"completed", "expired"}]
        scores = [row.total_score for row in done if row.total_score is not None]
        per_assessment.append({
            "id": assessment.id, "slug": assessment.slug, "title": assessment.title, "status": assessment.status,
            "visibility": assessment.visibility, "sessions": len(rows),
            "status_counts": dict(Counter(row.status for row in rows)), "finalized": len(done),
            "completion_rate": _round(sum(row.status == "completed" for row in closed) / len(closed)) if closed else None,
            "mean_score": _mean(scores), "median_score": _round(statistics.median(scores)) if scores else None,
        })
    scores = [row.total_score for row in finalized if row.total_score is not None]
    competencies = []
    for area_id, area in taxonomy.COMPETENCY_AREAS.items():
        values = [entry.get("score") for row in finalized for entry in (row.report or {}).get("competencies", [])
                  if entry.get("id") == area_id]
        assessed = [value for value in values if value is not None]
        competencies.append({"id": area_id, "name": area["name"], "mean": _mean(assessed),
                             "sessions": len(assessed)})
    usage = [_usage(row.report) for row in finalized]
    closed = [row for row in all_sessions if row.status in {"completed", "expired"}]
    return {
        "organization": {"id": org.id, "slug": org.slug, "name": org.name},
        "assessment_id": assessment_id, "assessments": per_assessment,
        "totals": {
            "sessions": len(all_sessions), "finalized": len(finalized),
            "active": sum(row.status == "active" for row in all_sessions),
            "completion_rate": _round(sum(row.status == "completed" for row in closed) / len(closed)) if closed else None,
            "mean_score": _mean(scores), "median_score": _round(statistics.median(scores)) if scores else None,
        },
        "score_distribution": histogram(scores),
        "competencies": competencies,
        "challenges": challenge_statistics(finalized),
        "assistance": {
            "ai_usage_share": _round(sum(row["ai"] > 0 for row in usage) / len(usage)) if usage else None,
            "hint_usage_share": _round(sum(row["hints"] > 0 for row in usage) / len(usage)) if usage else None,
            "ai_policies": dict(Counter(row["policy"].get("ai", "disabled") for row in usage)),
            "hint_policies": dict(Counter(row["policy"].get("hints", "disabled") for row in usage)),
        },
        "thresholds": {"discrimination_min_sessions": DISCRIMINATION_MIN_SESSIONS, "group_share": GROUP_SHARE},
        "notes": [HIRING_CAVEAT,
                  f"Discrimination indices need at least {DISCRIMINATION_MIN_SESSIONS} finalized sessions per "
                  "challenge; smaller samples are marked as insufficient data."],
    }


def compare(db, org, session_ids: list[str]) -> dict:
    ids = list(dict.fromkeys(value for value in session_ids if value))
    if not 2 <= len(ids) <= 6:
        raise HTTPException(422, "Choose between 2 and 6 finalized sessions to compare.")
    rows = {session.id: (session, assessment, candidate)
            for session, assessment, candidate in service.finalized_sessions(db, org)}
    missing = [value for value in ids if value not in rows]
    if missing:
        # Unknown, unfinished and other organizations' sessions are indistinguishable.
        raise HTTPException(404, "One or more sessions were not found among this organization's finalized sessions.")
    columns, challenge_keys = [], {}
    for value in ids:
        session, assessment, candidate = rows[value]
        report = session.report or {}
        challenges = {}
        for row in report.get("challenges", []):
            key = row.get("slug") or str(row.get("problem_id"))
            challenge_keys.setdefault(key, row.get("title"))
            challenges[key] = {"status": row.get("status"), "total": row.get("total"),
                               "components": row.get("components") or {}}
        columns.append({
            **session_row(session, assessment, candidate),
            "competencies": {entry["id"]: entry.get("score") for entry in report.get("competencies", [])},
            "behavior": report.get("behavior") or {}, "profile": report.get("profile"),
            "challenges": challenges, "disclaimers": report.get("disclaimers") or [],
        })
    return {
        "sessions": columns,
        "challenges": [{"key": key, "title": title} for key, title in challenge_keys.items()],
        "competency_areas": [{"id": key, "name": value["name"]} for key, value in taxonomy.COMPETENCY_AREAS.items()],
        "same_assessment": len({column["assessment_id"] for column in columns}) == 1,
        "notes": [HIRING_CAVEAT,
                  "Columns follow the order you selected; they are not a ranking.",
                  "Assistance policies differ between sessions" if len({json.dumps(column["assistance_policy"],
                                                                                  sort_keys=True)
                                                                       for column in columns}) > 1
                  else "All compared sessions ran under the same assistance policy."],
    }


def export(db, org, assessment: Assessment, fmt: str) -> tuple[str, str]:
    rows = service.finalized_sessions(db, org, assessment.id)
    if fmt == "json":
        payload = {"organization": {"id": org.id, "slug": org.slug, "name": org.name},
                   "assessment": {"id": assessment.id, "slug": assessment.slug, "title": assessment.title,
                                  "version": assessment.version},
                   "notes": [HIRING_CAVEAT],
                   "sessions": [{**session_row(session, assessment, candidate),
                                 "report": reports.full_view(session.report)} for session, _, candidate in rows]}
        return json.dumps(payload, indent=2, default=str), "application/json"
    slugs = list((service_configuration(assessment)).get("problems") or [])
    for session, _, _ in rows:
        for row in (session.report or {}).get("challenges", []):
            if row.get("slug") and row["slug"] not in slugs:
                slugs.append(row["slug"])
    areas = list(taxonomy.COMPETENCY_AREAS)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["session_id", "candidate_username", "candidate_email", "status", "started_at", "completed_at",
                     "assessment_version", "report_version", "total_score", "challenges_completed",
                     "challenges_total", "time_spent_seconds", "ai_used", "hints_used", "ai_policy", "hint_policy"]
                    + [f"competency:{area}" for area in areas] + [f"challenge:{slug}" for slug in slugs])
    for session, _, candidate in rows:
        row = session_row(session, assessment, candidate)
        report = session.report or {}
        competencies = {entry["id"]: entry.get("score") for entry in report.get("competencies", [])}
        totals = {entry.get("slug"): entry.get("total") for entry in report.get("challenges", [])}
        writer.writerow([row["session_id"], row["candidate"]["username"], row["candidate"]["email"], row["status"],
                         row["started_at"], row["completed_at"], row["assessment_version"], row["report_version"],
                         row["total_score"], row["challenges_completed"], row["challenges_total"],
                         row["time_spent_seconds"], row["ai_used"], row["hints_used"],
                         row["assistance_policy"].get("ai"), row["assistance_policy"].get("hints")]
                        + [competencies.get(area) for area in areas] + [totals.get(slug) for slug in slugs])
    return buffer.getvalue(), "text/csv"


def service_configuration(assessment: Assessment) -> dict:
    from app.assessments.service import effective_configuration
    return effective_configuration(assessment)
