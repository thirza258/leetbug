"""Quality-pipeline tasks (MT-002, PRD 7.9).

All task names start with ``app.quality.`` so they route to the dedicated ``quality`` queue served
by the low-concurrency ``quality-worker`` (see ``app.celery_app``); mutation runs therefore never
compete with user submissions. Every task claims its row with a conditional update, so a redelivered
message is a no-op, and infrastructure failures are retried with backoff and never count as kills.
"""
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.celery_app import celery
from app.config import settings
from app.db import open_session
from app.events import record_event
from app.execution import SandboxUnavailable
from app.models import Event, MutationCase, MutationRun, Problem, now
from app.quality import pipeline

log = logging.getLogger(__name__)
MAX_ATTEMPTS = pipeline.MAX_EXECUTION_ATTEMPTS
STUCK_CASE = timedelta(minutes=10)
LOST_MESSAGE = timedelta(minutes=30)
STUCK_RUN = timedelta(minutes=30)
ORPHAN_SAMPLE = timedelta(hours=1)


def _backoff(attempts: int) -> int:
    return min(300, 5 * 2 ** max(0, attempts))


def _enqueue_case(case_id: str, countdown: int = 0) -> None:
    try:
        mutation_case.apply_async((case_id,), countdown=countdown)
    except Exception:
        # The recovery task requeues cases whose messages were lost.
        log.warning("Could not enqueue mutation case %s", case_id, exc_info=True)


@celery.task(name="app.quality.run")
def quality_run(run_id: str, inline: bool = False):
    """Validate the problem, create mutation cases, then execute them (inline or via the queue)."""
    with open_session() as db:
        claimed = db.execute(update(MutationRun).where(MutationRun.id == run_id, MutationRun.status == "queued")
                             .values(status="validating", started_at=now()))
        db.commit()
        if not claimed.rowcount:
            return None
        run = db.get(MutationRun, run_id)
        try:
            cases = pipeline.run_validation(db, run)
            db.commit()
        except SandboxUnavailable as exc:
            db.rollback()
            run = db.get(MutationRun, run_id)
            attempts = int((run.execution_metadata or {}).get("validation_attempts", 0)) + 1
            run.execution_metadata = {**(run.execution_metadata or {}), "validation_attempts": attempts}
            if attempts < MAX_ATTEMPTS:
                run.status, run.started_at = "queued", None
                db.commit()
                try:
                    quality_run.apply_async((run_id,), countdown=_backoff(attempts))
                except Exception:
                    log.warning("Could not requeue quality run %s", run_id, exc_info=True)
            else:
                run.status, run.error, run.completed_at = "failed", str(exc), now()
                db.commit()
            return None
        except Exception:
            db.rollback()
            log.exception("Quality validation failed: %s", run_id)
            run = db.get(MutationRun, run_id)
            run.status, run.error, run.completed_at = "failed", "Validation failed unexpectedly.", now()
            db.commit()
            return None
        pending = [case.id for case in cases if case.status == "queued"]
    for case_id in pending:
        if inline:
            mutation_case(case_id, inline=True)
        else:
            _enqueue_case(case_id)
    with open_session() as db:
        pipeline.maybe_finalize(db, run_id)
        db.commit()
    return None


@celery.task(name="app.quality.case")
def mutation_case(case_id: str, inline: bool = False):
    """Execute one mutant in the sandbox and classify it; finalize the run after the last case."""
    with open_session() as db:
        claimed = db.execute(update(MutationCase).where(MutationCase.id == case_id, MutationCase.status == "queued")
                             .values(status="running", attempts=MutationCase.attempts + 1))
        db.commit()
        if not claimed.rowcount:
            return None
        case = db.get(MutationCase, case_id)
        case.detail = {**(case.detail or {}), "claimed_at": now().isoformat()}
        db.commit()
        run = db.get(MutationRun, case.run_id)
        problem = db.get(Problem, run.problem_id)
        retry_in = None
        try:
            pipeline.execute_case(db, case, run, problem)
        except SandboxUnavailable as exc:
            if case.attempts < MAX_ATTEMPTS:
                case.status = "queued"
                retry_in = _backoff(case.attempts)
            else:
                case.status, case.failure_classification = "error", "infrastructure"
                case.detail = {**(case.detail or {}), "message": str(exc)}
                case.completed_at = now()
        except Exception:
            log.exception("Mutation case failed: %s", case_id)
            case.status, case.failure_classification = "error", "harness"
            case.detail = {**(case.detail or {}), "message": "The quality worker could not evaluate this mutant."}
            case.completed_at = now()
        db.commit()
        run_id = run.id
    if retry_in is not None:
        if inline:
            time.sleep(min(retry_in, 2) if not settings.testing else 0)
            return mutation_case(case_id, inline=True)
        _enqueue_case(case_id, retry_in)
        return None
    with open_session() as db:
        pipeline.maybe_finalize(db, run_id)
        db.commit()
    return None


def _parse(value) -> datetime | None:
    try:
        return pipeline.aware(datetime.fromisoformat(value)) if value else None
    except (TypeError, ValueError):
        return None


def _observe_orphans(db) -> None:
    """Record how many expired sandbox containers exist (PRD 13.4). Only workers reach the daemon."""
    client = None
    try:
        import docker
        client = docker.DockerClient(base_url=settings.docker_host, timeout=5)
        containers = client.containers.list(all=True, filters={"label": "app=leetbug-sandbox"})
        expired = sum(1 for container in containers
                      if float(container.labels.get("expires_at", "0") or 0) < time.time())
        latest = db.scalar(select(Event).where(Event.type == "sandbox.orphans").order_by(Event.created_at.desc()).limit(1))
        # Record changes promptly, and otherwise one sample an hour, to keep the event log small.
        if latest is None or (latest.data or {}).get("count") != expired \
                or now() - pipeline.aware(latest.created_at) >= ORPHAN_SAMPLE:
            record_event(db, "sandbox.orphans", count=expired, containers=len(containers))
    except Exception:
        log.info("Sandbox daemon unavailable for orphan observation")
    finally:
        if client is not None:
            client.close()


@celery.task(name="app.quality.recover")
def recover_quality_jobs():
    """Requeue lost or stuck work and fail runs that cannot complete (scheduled by Celery beat)."""
    current = now()
    requeue_cases, requeue_runs = [], []
    with open_session() as db:
        for case in db.scalars(select(MutationCase).where(MutationCase.status.in_(["running", "queued"]))):
            detail = case.detail or {}
            if case.status == "running":
                claimed = _parse(detail.get("claimed_at")) or pipeline.aware(case.created_at)
                if current - claimed < STUCK_CASE:
                    continue
                if case.attempts < MAX_ATTEMPTS:
                    case.status = "queued"
                    requeue_cases.append(case.id)
                else:
                    case.status, case.failure_classification, case.completed_at = "error", "infrastructure", current
                    case.detail = {**detail, "message": "The worker did not finish this mutant."}
            else:
                last = _parse(detail.get("requeued_at")) or pipeline.aware(case.created_at)
                # Only messages that were plausibly lost: a long quality queue is not a failure.
                if current - last >= LOST_MESSAGE:
                    case.detail = {**detail, "requeued_at": current.isoformat()}
                    requeue_cases.append(case.id)
        for run in db.scalars(select(MutationRun).where(MutationRun.status.in_(["queued", "validating", "running"]))):
            started = pipeline.aware(run.started_at or run.created_at)
            if run.status == "queued" and current - started >= LOST_MESSAGE:
                run.execution_metadata = {**(run.execution_metadata or {}), "requeued_at": current.isoformat()}
                requeue_runs.append(run.id)
            elif run.status in ("validating", "running") and current - started >= STUCK_RUN:
                db.flush()
                if run.status == "running" and pipeline.finalize_run(db, run):
                    continue
                run.status, run.error, run.completed_at = "failed", "The quality run timed out.", current
        _observe_orphans(db)
        db.commit()
    for case_id in requeue_cases:
        _enqueue_case(case_id)
    for run_id in requeue_runs:
        try:
            quality_run.apply_async((run_id,))
        except Exception:
            log.warning("Could not requeue quality run %s", run_id, exc_info=True)
    return {"cases": len(requeue_cases), "runs": len(requeue_runs)}
