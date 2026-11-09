import logging
import time
from datetime import timedelta

import docker
from docker.errors import NotFound
from sqlalchemy import update

from app import attempts
from app.auth import utc
from app.celery_app import celery
from app.config import settings
from app.db import SessionLocal
from app.execution import SandboxUnavailable, execute_code, grade
from app.llm import AIUnavailable, patch_code
from app.models import AIInteraction, Hint, Problem, Submission, now
from app.rag import generate_hint

log = logging.getLogger(__name__)
__all__ = ["celery", "evaluate", "hint_task", "cleanup", "generate_hint"]


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
        # Attempt bookkeeping and patch-quality scoring are secondary: a failure here must never
        # change or block the persisted execution record above.
        try:
            attempts.on_submission_complete(db, submission, problem)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("Post-evaluation scoring failed: %s", submission_id)


@celery.task(name="app.tasks.hint")
def hint_task(hint_id):
    with SessionLocal() as db:
        claimed = db.execute(update(Hint).where(Hint.id == hint_id, Hint.status == "queued").values(status="running"))
        db.commit()
        if not claimed.rowcount:
            return
        hint = db.get(Hint, hint_id)
        try:
            from app.assistant.service import generate_adaptive_hint
            # The documentation hint generator is passed in so it can be substituted in tests.
            result = generate_adaptive_hint(db, hint, base=generate_hint)
            hint.text, hint.sources, hint.retrieval = result["text"], result["sources"], result["retrieval"]
            hint.status = "completed"
        except Exception:
            log.exception("Hint failed: %s", hint_id)
            hint.status, hint.error = "error", "The hint could not be generated. Please try again."
        # Adaptive context may include the user's current code; keep only non-sensitive metadata.
        if hint.context and "code" in hint.context:
            hint.context = {key: value for key, value in hint.context.items() if key != "code"}
        db.commit()


@celery.task(name="app.tasks.cleanup")
def cleanup():
    cutoff = now() - timedelta(minutes=5)
    with SessionLocal() as db:
        db.execute(update(Submission).where(Submission.status.in_(["queued", "running"]), Submission.created_at < cutoff)
                   .values(status="error", error="The worker did not finish this attempt. Please run it again.", completed_at=now()))
        db.execute(update(Hint).where(Hint.status.in_(["queued", "running"]), Hint.created_at < cutoff)
                   .values(status="error", error="The hint worker timed out. Please try again."))
        db.execute(update(AIInteraction).where(AIInteraction.status.in_(["queued", "running"]),
                                               AIInteraction.created_at < cutoff)
                   .values(status="error", error="The assistant timed out. Please try again.", payload=None))
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
