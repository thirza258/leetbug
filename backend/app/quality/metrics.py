"""Operational metrics for administrators (PRD 13.4, 14.3).

Computed from durable records (PostgreSQL) plus Redis queue lengths. The API process has no Docker
access by design, so orphaned-container counts come from the latest observation that the quality
worker records while running its recovery task.
"""
from datetime import timedelta

from sqlalchemy import func, select, text

from app.limits import redis_client
from app.models import (
    AIInteraction,
    AssessmentSession,
    Diagnosis,
    Event,
    FixExplanation,
    Hint,
    MutationCase,
    MutationRun,
    Submission,
    now,
)
from app.quality.pipeline import aware, nearest_rank, percent

QUEUES = ("celery", "quality")


def percentiles(values) -> dict:
    values = [value for value in values if value is not None]
    return {"samples": len(values), "p50": nearest_rank(values, 0.50), "p95": nearest_rank(values, 0.95),
            "p99": nearest_rank(values, 0.99)}


def _health(db) -> dict:
    health = {"database": "ok", "redis": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        health["database"] = "unavailable"
    try:
        redis_client.ping()
    except Exception:
        health["redis"] = "unavailable"
    return health


def _queues() -> dict:
    depths = {}
    for queue in QUEUES:
        try:
            depths[queue] = int(redis_client.llen(queue))
        except Exception:
            depths[queue] = None
    return depths


def _count(db, model, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def admin_metrics(db, *, days: int = 7) -> dict:
    since = now() - timedelta(days=days)
    submissions = list(db.execute(select(Submission.language, Submission.status, Submission.runtime_ms,
                                         Submission.turnaround_ms).where(Submission.created_at >= since)))
    evaluated = [row for row in submissions if row.status not in ("queued", "running")]
    by_language = {}
    for language in sorted({row.language for row in evaluated}):
        rows = [row for row in evaluated if row.language == language and row.status != "error"]
        by_language[language] = {"runtime_ms": percentiles(row.runtime_ms for row in rows),
                                 "turnaround_ms": percentiles(row.turnaround_ms for row in rows)}
    service_errors = sum(1 for row in evaluated if row.status == "error")
    cases = list(db.execute(select(MutationCase.status, MutationCase.execution_duration_ms)
                            .join(MutationRun, MutationCase.run_id == MutationRun.id)
                            .where(MutationRun.created_at >= since)))
    finished_cases = [row for row in cases if row.status not in ("queued", "running")]
    runs = list(db.execute(select(MutationRun.status, MutationRun.mutation_score, MutationRun.gate_status,
                                  MutationRun.execution_metadata).where(MutationRun.created_at >= since)))
    run_status = {}
    for row in runs:
        run_status[row.status] = run_status.get(row.status, 0) + 1
    interactions = list(db.execute(select(AIInteraction.status, AIInteraction.retrieval_ms, AIInteraction.generation_ms,
                                          AIInteraction.latency_ms).where(AIInteraction.created_at >= since)))
    evaluations = {}
    for name, model in (("diagnoses", Diagnosis), ("explanations", FixExplanation)):
        completed = _count(db, model, model.ai_status == "completed", model.created_at >= since)
        failed = _count(db, model, model.ai_status == "failed", model.created_at >= since)
        evaluations[name] = {"completed": completed, "failed": failed, "failure_rate": percent(failed, completed + failed)}
    total_completed = sum(item["completed"] for item in evaluations.values())
    total_failed = sum(item["failed"] for item in evaluations.values())
    sessions = list(db.execute(select(AssessmentSession.status, AssessmentSession.completed_at,
                                      AssessmentSession.expires_at, AssessmentSession.finalized_at)
                               .where(AssessmentSession.finalized_at.is_not(None),
                                      AssessmentSession.finalized_at >= since)))
    finalization = []
    for row in sessions:
        reference = row.expires_at if row.status == "expired" else (row.completed_at or row.expires_at)
        if reference is not None:
            finalization.append(max(0.0, (aware(row.finalized_at) - aware(reference)).total_seconds() * 1000))
    orphan_event = db.scalar(select(Event).where(Event.type == "sandbox.orphans").order_by(Event.created_at.desc()).limit(1))
    return {
        "generated_at": now().isoformat(), "window_days": days,
        "health": _health(db), "queues": _queues(),
        "jobs_in_progress": {
            "submissions": _count(db, Submission, Submission.status.in_(["queued", "running"])),
            "hints": _count(db, Hint, Hint.status.in_(["queued", "running"])),
            "ai_interactions": _count(db, AIInteraction, AIInteraction.status.in_(["queued", "running"])),
            "mutation_cases": _count(db, MutationCase, MutationCase.status.in_(["queued", "running"])),
            "mutation_runs": _count(db, MutationRun, MutationRun.status.in_(["queued", "validating", "running"])),
        },
        "execution": {
            "evaluations": len(evaluated), "service_errors": service_errors,
            "service_error_rate": percent(service_errors, len(evaluated)),
            "runtime_ms": percentiles(row.runtime_ms for row in evaluated if row.status != "error"),
            "turnaround_ms": percentiles(row.turnaround_ms for row in evaluated if row.status != "error"),
            "by_language": by_language,
        },
        "mutation": {
            "cases": len(finished_cases),
            "infrastructure_error_rate": percent(sum(row.status == "error" for row in finished_cases), len(finished_cases)),
            "invalid_rate": percent(sum(row.status == "invalid" for row in finished_cases), len(finished_cases)),
            "timeout_rate": percent(sum(row.status == "timeout" for row in finished_cases), len(finished_cases)),
            "equivalent_rate": percent(sum(row.status == "equivalent" for row in finished_cases), len(finished_cases)),
            "case_duration_ms": percentiles(row.execution_duration_ms for row in finished_cases),
            "runs": run_status,
            "approved_runs": sum(1 for row in runs if row.gate_status == "approved"),
            "validation_duration_ms": percentiles((row.execution_metadata or {}).get("duration_ms") for row in runs),
        },
        "ai": {
            "interactions": len(interactions),
            "error_rate": percent(sum(row.status == "error" for row in interactions),
                                  sum(row.status in ("completed", "error") for row in interactions)),
            "retrieval_ms": percentiles(row.retrieval_ms for row in interactions),
            "generation_ms": percentiles(row.generation_ms for row in interactions),
            "latency_ms": percentiles(row.latency_ms for row in interactions),
        },
        "ai_evaluation": {**evaluations, "failure_rate": percent(total_failed, total_completed + total_failed)},
        "assessments": {"finalized": len(sessions), "finalization_latency_ms": percentiles(finalization)},
        "sandbox": {
            "orphaned_containers": (orphan_event.data or {}).get("count") if orphan_event else None,
            "observed_at": orphan_event.created_at.isoformat() if orphan_event else None,
            "note": "Observed by the quality worker; the API has no Docker access.",
        },
    }
