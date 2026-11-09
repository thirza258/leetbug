"""Incident background jobs: resolution evaluation and administrator reproduction checks.

Both are idempotent (a row is claimed with a conditional status update). Validity and detection
come only from repository-authored code — the incident's reference solution and original defect —
run on the user's JSON inputs; the user's linked submission also runs (in the same sandbox as every
submission) purely as informational feedback. Reference outputs are never returned. An unavailable sandbox is an infrastructure failure: the record becomes a retryable error and is
never scored as a user failure. There is no automatic retry; the owner (or an administrator)
re-queues explicitly, which keeps a broken sandbox from looping.
"""
import logging

from sqlalchemy import update

from app import execution
from app.celery_app import celery
from app.db import open_session
from app.incidents import service, validation
from app.models import Incident, IncidentResolution, IncidentSession, Problem, Submission, now

log = logging.getLogger(__name__)
INFRA_MESSAGE = "The isolated execution service is unavailable. Your resolution is saved; retry the evaluation shortly."


def _grade(language: str, source: str, tests: list[dict]) -> tuple[str, list[dict]]:
    return execution.grade(tests, execution.execute_code(language, source, tests))


@celery.task(name="app.incidents.evaluate_resolution")
def evaluate_resolution(resolution_id: str):
    with open_session() as db:
        claimed = db.execute(update(IncidentResolution).where(IncidentResolution.id == resolution_id,
                                                              IncidentResolution.status == "queued")
                             .values(status="running"))
        db.commit()
        if not claimed.rowcount:
            return
        row = db.get(IncidentResolution, resolution_id)
        try:
            session = db.get(IncidentSession, row.session_id)
            incident = db.get(Incident, session.incident_id)
            problem = db.get(Problem, incident.problem_id)
            submission = db.get(Submission, row.submission_id) if row.submission_id else None
            language = service.evaluation_language(problem, submission)
            tests = [{"name": test["name"], "input": test["input"], "expected": test["expected"],
                      "hidden": False, "assertions": []} for test in row.regression_tests or []]
            results: list[dict] = []
            if tests:
                ref_status, reference = _grade(language, problem.solutions[language], tests)
                old_status, starter = _grade(language, problem.starters[language], tests)
                fix = None
                if submission is not None and submission.language == language:
                    # Informational only: does the user's own patch satisfy their regression tests?
                    _, fix = _grade(language, submission.generated_code or submission.code, tests)
                results = service.classify_regression(tests, reference, starter, ref_status, old_status, fix)
            service.finish_resolution(db, row, results)
        except execution.SandboxUnavailable:
            db.rollback()
            row = db.get(IncidentResolution, resolution_id)
            row.status, row.error = "error", INFRA_MESSAGE
        except Exception:
            log.exception("Incident resolution evaluation failed: %s", resolution_id)
            db.rollback()
            row = db.get(IncidentResolution, resolution_id)
            row.status = "error"
            row.error = "The evaluation service encountered a problem. Retry the evaluation."
        db.commit()


@celery.task(name="app.incidents.validate")
def validate_incident(incident_id: int):
    """Reproduction check before publication: the original defect fails at least one scenario test
    and the reference solution passes every test, in every offered language."""
    with open_session() as db:
        incident = db.get(Incident, incident_id)
        if incident is None:
            return
        state = (incident.evaluation_config or {}).get("validation") or {}
        if state.get("status") != "queued":
            return
        problem = db.get(Problem, incident.problem_id)
        service.set_validation(incident, {**state, "status": "running"})
        db.commit()
        scenario_tests = {name for scenario in incident.scenarios or [] for name in scenario.get("tests", [])}
        checks = []
        try:
            for language in problem.starters:
                ref_status, reference = _grade(language, problem.solutions[language], problem.tests)
                _, starter = _grade(language, problem.starters[language], problem.tests)
                compiled = len(starter) == len(problem.tests)
                reproduced = [test["name"] for result, test in zip(starter, problem.tests, strict=True)
                              if test["name"] in scenario_tests and result["status"] != "passed"] if compiled else []
                checks.append({"language": language, "reference_status": ref_status,
                               "reference_passed": ref_status == "passed", "starter_compiles": compiled,
                               "reproduced_scenarios": reproduced,
                               "ok": ref_status == "passed" and compiled and bool(reproduced)})
            status = "passed" if checks and all(check["ok"] for check in checks) else "failed"
            error = None
        except execution.SandboxUnavailable:
            status, error = "error", "The isolated execution service is unavailable. Validate again shortly."
        except Exception:
            log.exception("Incident validation failed: %s", incident_id)
            status, error = "error", "Validation encountered a problem. Validate again."
        service.set_validation(incident, {
            "status": status, "error": error, "checks": checks, "version": incident.version,
            "content_hash": validation.content_hash({"starters": problem.starters, "solutions": problem.solutions,
                                                     "tests": problem.tests}),
            "requested_at": state.get("requested_at"), "requested_by": state.get("requested_by"),
            "completed_at": now().isoformat()})
        db.commit()
