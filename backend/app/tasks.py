import logging
import time
from datetime import timedelta

import docker
from celery import Celery
from docker.errors import NotFound
from sqlalchemy import update

from app.auth import utc
from app.config import settings
from app.db import SessionLocal
from app.execution import SandboxUnavailable, execute_code, grade
from app.llm import AIUnavailable, patch_code
from app.models import Hint, Problem, Submission, now
from app.rag import generate_hint

log = logging.getLogger(__name__)
celery = Celery("leetbug", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_serializer="json", result_serializer="json", accept_content=["json"],
    task_ignore_result=True, task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, task_soft_time_limit=170, task_time_limit=180,
    broker_connection_retry_on_startup=True, broker_transport_options={"visibility_timeout": 240},
    beat_schedule={"clean-expired-jobs": {"task": "app.tasks.cleanup", "schedule": 60.0}},
)


@celery.task(name="app.tasks.evaluate")
def evaluate(submission_id):
    with SessionLocal() as db:
        claimed = db.execute(update(Submission).where(Submission.id == submission_id, Submission.status == "queued")
                             .values(status="running"))
        db.commit()
        if not claimed.rowcount:
            return
        submission = db.get(Submission, submission_id)
        problem = db.get(Problem, submission.problem_id)
        try:
            source = submission.code
            if submission.mode == "ai":
                source, submission.llm_tokens = patch_code(problem, submission.language, source, submission.prompt)
                submission.generated_code = source
                db.commit()
            tests = [t for t in problem.tests if submission.kind == "submit" or not t["hidden"]]
            execution = execute_code(submission.language, source, tests)
            submission.status, submission.results = grade(tests, execution)
            submission.runtime_ms = execution.get("runtime_ms")
            submission.memory_kb = execution.get("memory_kb")
            if execution.get("fatal_status"):
                submission.error = {
                    "time_limit": "Execution exceeded the sandbox time limit.",
                    "memory_limit": "Execution exceeded the sandbox memory limit.",
                }.get(submission.status, "The program exited without a valid result.")
        except (SandboxUnavailable, AIUnavailable) as exc:
            submission.status, submission.error = "error", str(exc)
        except Exception:
            log.exception("Submission failed: %s", submission_id)
            submission.status, submission.error = "error", "The evaluation service encountered a problem. Please try again."
        submission.completed_at = now()
        submission.turnaround_ms = round((submission.completed_at - utc(submission.created_at)).total_seconds() * 1000, 2)
        db.commit()


@celery.task(name="app.tasks.hint")
def hint_task(hint_id):
    with SessionLocal() as db:
        claimed = db.execute(update(Hint).where(Hint.id == hint_id, Hint.status == "queued").values(status="running"))
        db.commit()
        if not claimed.rowcount:
            return
        hint = db.get(Hint, hint_id)
        try:
            result = generate_hint(db.get(Problem, hint.problem_id), hint.language, hint.level)
            hint.text, hint.sources, hint.retrieval = result["text"], result["sources"], result["retrieval"]
            hint.status = "completed"
        except Exception:
            log.exception("Hint failed: %s", hint_id)
            hint.status, hint.error = "error", "The hint could not be generated. Please try again."
        db.commit()


@celery.task(name="app.tasks.cleanup")
def cleanup():
    cutoff = now() - timedelta(minutes=5)
    with SessionLocal() as db:
        db.execute(update(Submission).where(Submission.status.in_(["queued", "running"]), Submission.created_at < cutoff)
                   .values(status="error", error="The worker did not finish this attempt. Please run it again.", completed_at=now()))
        db.execute(update(Hint).where(Hint.status.in_(["queued", "running"]), Hint.created_at < cutoff)
                   .values(status="error", error="The hint worker timed out. Please try again."))
        db.commit()
    client = None
    try:
        client = docker.DockerClient(base_url=settings.docker_host, timeout=5)
        for container in client.containers.list(all=True, filters={"label": "app=leetbug-sandbox"}):
            try:
                if float(container.labels.get("expires_at", "0")) < time.time():
                    container.remove(force=True)
            except NotFound:
                # The evaluation worker may have removed it after the listing.
                continue
    except Exception:
        log.warning("Could not clean expired execution containers", exc_info=True)
    finally:
        if client is not None:
            client.close()
