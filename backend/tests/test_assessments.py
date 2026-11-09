"""Assessment mode (PRD §9): configuration, sessions, policy, timing, scoring, reports and exports."""
import csv
import io
import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import tasks
from app.assessments import service
from app.assessments.catalog import ASSESSMENT_PACKS
from app.assessments.tasks import expire_sessions, finalize_session_task
from app.attempts import get_or_create_attempt
from app.catalog import CATALOG
from app.config import settings
from app.models import (
    Assessment,
    AssessmentSession,
    AuditLog,
    ChallengeAttempt,
    Diagnosis,
    FixExplanation,
    Problem,
    Submission,
    now,
)

PASSWORD = "StrongPassword123!"
ADMIN_EMAIL = "admin@example.com"


def register(client, email, username):
    response = client.post("/api/auth/register", json={"email": email, "username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()["user"]


def login(client, email):
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()["user"]


@pytest.fixture
def admin(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", ADMIN_EMAIL)
    return register(client, ADMIN_EMAIL, "admin_user")


@pytest.fixture
def fake_sandbox(monkeypatch):
    """Grade in-process: programs containing PASS return every expected output."""
    def execute(language, code, tests_):
        ok = "PASS" in code
        return {"results": [{"status": "ok", "output": test["expected"] if ok else "wrong", "runtime_ms": 1}
                            for test in tests_], "runtime_ms": 5, "memory_kb": 100}
    monkeypatch.setattr(tasks, "execute_code", execute)


def create_assessment(client, *, publish=True, **overrides):
    body = {"title": "Payments debugging check", "assessment_type": "individual", "duration_seconds": 1800,
            "configuration": {"problems": ["checkout-underflow", "missing-last-item"], "diagnosis_required": False},
            "assistance_policy": {"ai": "disabled", "hints": "disabled"}, "visibility": "public"}
    configuration = overrides.pop("configuration", {})
    body.update(overrides)
    body["configuration"] = {**body["configuration"], **configuration}
    response = client.post("/api/admin/assessments", json=body)
    assert response.status_code == 201, response.text
    row = response.json()
    if publish:
        published = client.post(f"/api/admin/assessments/{row['id']}/publish")
        assert published.status_code == 200, published.text
        row = published.json()
    return row


def problem_id(slug):
    return next(index for index, item in enumerate(CATALOG, 1) if item["slug"] == slug)


def start(client, assessment):
    response = client.post(f"/api/assessments/{assessment['slug']}/sessions")
    assert response.status_code in (200, 201), response.text
    return response.json()


def submit(client, session_id, slug="checkout-underflow", code="def solve(data): return 0  # PASS", **extra):
    return client.post("/api/submissions", json={"problem_id": problem_id(slug), "language": "python", "code": code,
                                                 "kind": "submit", "assessment_session_id": session_id, **extra})


def add_diagnosis(db_factory, session_id, user_id, slug="checkout-underflow", score=80.0):
    with db_factory() as db:
        attempt = get_or_create_attempt(db, user_id, problem_id(slug), assessment_session_id=session_id)
        db.add(Diagnosis(user_id=user_id, problem_id=problem_id(slug), attempt_id=attempt.id,
                         assessment_session_id=session_id, defect_category="validation",
                         root_cause="The discount is subtracted without clamping the total.",
                         affected_component="solve", violated_invariant="The total must never be negative.",
                         proposed_correction="Clamp the discount and the total at zero.",
                         reproduction_strategy="Apply a discount larger than the subtotal.", score=score,
                         evaluation_details={"criteria": {"reproduction": {"score": 0.8}}}))
        db.commit()


def expire(db_factory, session_id):
    with db_factory() as db:
        db.get(AssessmentSession, session_id).expires_at = now() - timedelta(seconds=1)
        db.commit()


def test_seeded_packs_are_valid_and_hide_problem_content(client, db_factory):
    listing = client.get("/api/assessments").json()
    slugs = {row["slug"] for row in listing["items"]}
    assert {pack["slug"] for pack in ASSESSMENT_PACKS} <= slugs
    by_slug = {item["slug"]: item for item in CATALOG}
    for pack in ASSESSMENT_PACKS:
        configuration = pack["configuration"]
        assert 4 <= len(configuration["problems"]) <= 6 and 45 * 60 <= pack["duration_seconds"] <= 90 * 60
        for slug in configuration["problems"]:
            assert slug in by_slug, slug
            languages = configuration["languages"] or list(by_slug[slug]["starters"])
            assert set(languages) & set(by_slug[slug]["starters"]), slug
        detail = client.get(f"/api/assessments/{pack['slug']}").json()
        assert detail["challenge_count"] == len(configuration["problems"])
        assert "problems" not in detail and "starters" not in json.dumps(detail)
        assert detail["status"] == "published" and detail["rules"]
    with db_factory() as db:
        for pack in ASSESSMENT_PACKS:
            assert not service.validation_errors(db, db.scalar(select(Assessment).where(Assessment.slug == pack["slug"])))
    go = client.get("/api/assessments/backend-engineer-go").json()
    assert go["assistance_policy"] == {"ai": "disabled", "hints": "disabled"} and go["languages"] == ["go"]
    assert client.get("/api/assessments/general-software-debugging").json()["assessment_type"] == "practice"


def test_admin_create_validate_publish_edit_archive(client, member, admin):
    login(client, member["email"])
    body = {"title": "Not allowed", "configuration": {"problems": ["checkout-underflow"]}}
    assert client.post("/api/admin/assessments", json=body).status_code == 403
    assert client.get("/api/admin/assessments").status_code == 403
    login(client, ADMIN_EMAIL)
    assert client.post("/api/admin/assessments", json={**body, "configuration": {"problems": ["a", "a"]}}).status_code == 422
    assert client.post("/api/admin/assessments", json={**body, "scoring_rubric": {"weights": {"speed": 10}}}).status_code == 422
    draft = create_assessment(client, publish=False, configuration={"problems": ["checkout-underflow", "no-such-case"]})
    assert draft["status"] == "draft" and draft["validation_errors"]
    blocked = client.post(f"/api/admin/assessments/{draft['id']}/publish")
    assert blocked.status_code == 422 and "no-such-case" in blocked.json()["detail"]
    wrong_language = client.patch(f"/api/admin/assessments/{draft['id']}", json={
        "configuration": {"problems": ["checkout-underflow"], "languages": ["go"]}})
    assert wrong_language.status_code == 200
    assert "does not offer an allowed language" in client.post(f"/api/admin/assessments/{draft['id']}/publish").json()["detail"]
    fixed = client.patch(f"/api/admin/assessments/{draft['id']}", json={
        "configuration": {"problems": ["checkout-underflow"], "languages": ["python"]}}).json()
    assert fixed["validation_errors"] == []
    assert fixed["configuration"]["diagnosis_required"] is False  # omitted fields keep their stored values
    published = client.post(f"/api/admin/assessments/{draft['id']}/publish").json()
    assert published["status"] == "published" and published["version"] == 1
    edited = client.patch(f"/api/admin/assessments/{draft['id']}", json={"duration_seconds": 2400}).json()
    assert edited["version"] == 2 and edited["duration_seconds"] == 2400
    bad = client.patch(f"/api/admin/assessments/{draft['id']}", json={"configuration": {"problems": ["missing-x"]}})
    assert bad.status_code == 422
    assert client.get(f"/api/admin/assessments/{draft['id']}").json()["configuration"]["problems"] == ["checkout-underflow"]
    interview = create_assessment(client, title="Interview loop", assessment_type="interview")
    assert interview["max_sessions"] == 1 and interview["candidate_report"] == "summary" and interview["feedback"] == "delayed"
    archived = client.post(f"/api/admin/assessments/{draft['id']}/archive").json()
    assert archived["status"] == "archived"
    assert client.patch(f"/api/admin/assessments/{draft['id']}", json={"title": "Changed title"}).status_code == 409
    assert draft["slug"] not in {row["slug"] for row in client.get("/api/assessments").json()["items"]}


def test_start_rules_visibility_invitations_window_and_session_limits(client, member, admin, db_factory):
    login(client, ADMIN_EMAIL)
    private = create_assessment(client, title="Invitation only", visibility="invitation",
                                configuration={"max_sessions": 1})
    invites = client.post(f"/api/admin/assessments/{private['id']}/invitations",
                          json={"emails": [member["email"].upper()]})
    assert invites.status_code == 201
    token = invites.json()["items"][0]["token"]
    assert invites.json()["items"][0]["email"] == member["email"]
    listing = client.get(f"/api/admin/assessments/{private['id']}/invitations").json()["items"]
    assert "token" not in listing[0] and listing[0]["status"] == "pending"
    register(client, "outsider@example.com", "outsider")
    assert private["slug"] not in {row["slug"] for row in client.get("/api/assessments").json()["items"]}
    assert client.get(f"/api/assessments/{private['slug']}").status_code == 404
    assert client.post(f"/api/assessments/{private['slug']}/sessions").status_code == 404
    assert client.post("/api/assessment-invitations/accept", json={"token": token}).status_code == 403
    assert client.post("/api/assessment-invitations/accept", json={"token": "x" * 40}).status_code == 404
    login(client, member["email"])
    accepted = client.post("/api/assessment-invitations/accept", json={"token": token})
    assert accepted.status_code == 200 and accepted.json()["invitation"]["status"] == "accepted"
    detail = client.get(f"/api/assessments/{private['slug']}").json()
    assert detail["can_start"] and detail["max_sessions"] == 1
    first = client.post(f"/api/assessments/{private['slug']}/sessions")
    assert first.status_code == 201
    session = first.json()
    assert session["status"] == "active" and 1700 < session["remaining_seconds"] <= 1800
    assert [row["slug"] for row in session["challenges"]] == ["checkout-underflow", "missing-last-item"]
    assert "starters" in session["challenges"][0]["problem"] and "solutions" not in session["challenges"][0]["problem"]
    again = client.post(f"/api/assessments/{private['slug']}/sessions")
    assert again.status_code == 200 and again.json()["id"] == session["id"]
    assert client.post(f"/api/assessment-sessions/{session['id']}/submit").status_code == 200
    limited = client.post(f"/api/assessments/{private['slug']}/sessions")
    assert limited.status_code == 409 and "1 session" in limited.json()["detail"]
    login(client, ADMIN_EMAIL)
    later = create_assessment(client, title="Opens tomorrow", available_from=(now() + timedelta(days=1)).isoformat())
    closed = create_assessment(client, title="Closed window",
                               available_from=(now() - timedelta(days=2)).isoformat(),
                               available_until=(now() - timedelta(days=1)).isoformat())
    login(client, member["email"])
    assert client.post(f"/api/assessments/{later['slug']}/sessions").json()["detail"] == "This assessment is not open yet."
    assert client.post(f"/api/assessments/{closed['slug']}/sessions").status_code == 409
    assert client.get(f"/api/assessments/{later['slug']}").json()["can_start"] is False


def test_randomized_order_is_stored_per_session(client, member, admin, db_factory):
    login(client, ADMIN_EMAIL)
    slugs = ["checkout-underflow", "missing-last-item", "role-confusion", "retry-budget", "wallet-race"]
    assessment = create_assessment(client, title="Shuffled order", configuration={"problems": slugs,
                                                                                  "randomize_order": True})
    login(client, member["email"])
    session = start(client, assessment)
    order = [row["slug"] for row in session["challenges"]]
    assert sorted(order) == sorted(slugs)
    with db_factory() as db:
        stored = db.get(AssessmentSession, session["id"])
        assert stored.challenge_order == [problem_id(slug) for slug in order]
        assert stored.config_snapshot["configuration"]["randomize_order"] is True
    assert [row["slug"] for row in client.get(f"/api/assessment-sessions/{session['id']}").json()["challenges"]] == order


def test_policy_applies_on_practice_endpoints_and_work_never_counts_as_practice(
        client, member, admin, db_factory, fake_sandbox, monkeypatch):
    login(client, ADMIN_EMAIL)
    assessment = create_assessment(client)
    login(client, member["email"])
    # Solve the problem in practice first: the solution is unlocked before the assessment.
    practice = client.post("/api/submissions", json={"problem_id": 1, "language": "python",
                                                     "code": "def solve(data): return 0  # PASS"})
    tasks.evaluate(practice.json()["id"])
    assert client.get("/api/problems/checkout-underflow/solutions").status_code == 200
    session = start(client, assessment)
    detail = client.get("/api/problems/checkout-underflow").json()
    assert detail["assistance"] == {"ai": "disabled", "hints": "disabled", "source": "assessment",
                                    "assessment_session_id": session["id"]}
    assert client.get("/api/problems/checkout-underflow/solutions").status_code == 403
    for _ in range(2):
        failing = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "kind": "run",
                                                        "code": "def solve(data): return 0"})
        tasks.evaluate(failing.json()["id"])
    hint = client.post("/api/problems/checkout-underflow/hints", json={"language": "python"})
    assert hint.status_code == 403 and hint.json()["detail"] == "Hints are disabled for this assessment."
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    ai = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "mode": "ai",
                                               "code": "def solve(data): return 0", "prompt": "Clamp the total at zero."})
    assert ai.status_code == 403 and ai.json()["detail"] == "AI assistance is disabled for this assessment."
    # Work from the practice page attaches to the active session automatically.
    auto = client.post("/api/submissions", json={"problem_id": 2, "language": "python",
                                                 "code": "def solve(data): return 0  # PASS"})
    assert auto.status_code == 202 and auto.json()["assessment_session_id"] == session["id"]
    tasks.evaluate(auto.json()["id"])
    explicit = submit(client, session["id"])
    assert explicit.json()["assessment_session_id"] == session["id"]
    tasks.evaluate(explicit.json()["id"])
    state = client.get(f"/api/assessment-sessions/{session['id']}").json()
    assert [row["status"] for row in state["challenges"]] == ["solved", "solved"]
    assert client.get("/api/problems?status=solved").json()["total"] == 1  # only the practice solve
    assert client.post(f"/api/assessment-sessions/{session['id']}/submit").status_code == 200
    # After the session, practice rules return: missing-last-item was solved only in the assessment.
    assert client.get("/api/problems/checkout-underflow/solutions").status_code == 200
    assert client.get("/api/problems/missing-last-item/solutions").status_code == 403
    assert client.get("/api/problems/checkout-underflow").json()["assistance"]["source"] == "practice"
    with db_factory() as db:
        attempts = list(db.scalars(select(ChallengeAttempt).where(ChallengeAttempt.assessment_session_id == session["id"])))
        assert {row.scope for row in attempts} == {f"assessment:{session['id']}"} and len(attempts) == 2


def test_diagnosis_requirement_languages_and_max_attempts(client, member, admin, db_factory, fake_sandbox):
    login(client, ADMIN_EMAIL)
    assessment = create_assessment(client, configuration={"diagnosis_required": True, "max_attempts": 2,
                                                          "languages": ["python"]})
    login(client, member["email"])
    session = start(client, assessment)
    assert session["challenges"][0]["problem"]["diagnosis_required"] is True
    assert session["challenges"][0]["problem"]["languages"] == ["python"]
    assert set(session["challenges"][1]["problem"]["starters"]) == {"python"}
    run = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "kind": "run",
                                                "code": "def solve(data): return 0",
                                                "assessment_session_id": session["id"]})
    assert run.status_code == 202  # reproduction runs never need a diagnosis
    assert submit(client, session["id"]).status_code == 428
    add_diagnosis(db_factory, session["id"], member["id"])
    js = client.post("/api/submissions", json={"problem_id": 1, "language": "javascript", "kind": "submit",
                                               "code": "function solve() {}", "assessment_session_id": session["id"]})
    assert js.status_code == 422
    first = submit(client, session["id"], code="def solve(data): return 1")
    assert first.status_code == 202 and first.json()["diagnosis_id"]
    tasks.evaluate(first.json()["id"])
    tasks.evaluate(submit(client, session["id"], code="def solve(data): return 2").json()["id"])
    third = submit(client, session["id"])
    assert third.status_code == 409 and "2 submissions" in third.json()["detail"]
    state = client.get(f"/api/assessment-sessions/{session['id']}").json()
    assert state["challenges"][0]["submissions_used"] == 2 and state["challenges"][0]["diagnosis_submitted"]


def test_timer_is_enforced_server_side_and_expiry_finalizes(client, member, admin, db_factory, fake_sandbox):
    login(client, ADMIN_EMAIL)
    assessment = create_assessment(client)
    login(client, member["email"])
    session = start(client, assessment)
    tasks.evaluate(submit(client, session["id"]).json()["id"])
    expire(db_factory, session["id"])
    late = submit(client, session["id"], slug="missing-last-item")
    assert late.status_code == 409 and "has ended" in late.json()["detail"]
    # Practice requests for the same problem no longer fall under the expired session.
    detail = client.get("/api/problems/checkout-underflow").json()
    assert detail["assistance"]["source"] == "practice"
    state = client.get(f"/api/assessment-sessions/{session['id']}").json()
    assert state["status"] == "expired" and state["report_ready"] and state["remaining_seconds"] == 0
    assert "problem" not in state["challenges"][0]
    report = client.get(f"/api/assessment-sessions/{session['id']}/report").json()
    assert report["summary"]["status"] == "expired" and report["summary"]["challenges_completed"] == 1
    assert any("time limit" in note for note in report["disclaimers"])
    assert client.post(f"/api/assessment-sessions/{session['id']}/submit").status_code == 409
    # The scheduler closes sessions that nobody touches after the deadline.
    login(client, ADMIN_EMAIL)
    second = create_assessment(client, title="Scheduler expiry")
    login(client, member["email"])
    idle = start(client, second)
    expire(db_factory, idle["id"])
    assert expire_sessions() == {"closed": 1, "finalized": 0}
    with db_factory() as db:
        row = db.get(AssessmentSession, idle["id"])
        assert row.status == "expired" and row.finalized_at is not None and row.total_score == 0
    assert finalize_session_task(idle["id"]) is None


def test_finalization_waits_for_running_evaluations(client, member, admin, db_factory, fake_sandbox):
    login(client, ADMIN_EMAIL)
    assessment = create_assessment(client)
    login(client, member["email"])
    session = start(client, assessment)
    pending = submit(client, session["id"]).json()
    finished = client.post(f"/api/assessment-sessions/{session['id']}/submit").json()
    assert finished["status"] == "completed" and not finished["report_ready"] and finished["pending_evaluations"] == 1
    response = client.get(f"/api/assessment-sessions/{session['id']}/report")
    assert response.status_code == 202 and response.json()["level"] == "finalizing"
    tasks.evaluate(pending["id"])
    report = client.get(f"/api/assessment-sessions/{session['id']}/report")
    assert report.status_code == 200
    challenge = report.json()["challenges"][0]
    assert challenge["status"] == "solved" and challenge["components"]["correctness"] == 100


def test_finalize_is_idempotent_immutable_and_corrections_are_audited(
        client, member, admin, db_factory, fake_sandbox):
    login(client, ADMIN_EMAIL)
    assessment = create_assessment(client, configuration={"explanation_required": True})
    login(client, member["email"])
    session = start(client, assessment)
    add_diagnosis(db_factory, session["id"], member["id"], score=70.0)
    accepted = submit(client, session["id"]).json()
    tasks.evaluate(accepted["id"])
    assert client.post(f"/api/assessment-sessions/{session['id']}/submit").status_code == 200
    assert client.post(f"/api/assessment-sessions/{session['id']}/submit").status_code == 409
    report = client.get(f"/api/assessment-sessions/{session['id']}/report").json()
    first, second = report["challenges"]
    assert first["status"] == "solved" and first["components"]["diagnosis"] == 70.0
    assert first["components"]["explanation"] is None and "explanation" in first["weights"]  # required → zero
    assert second["status"] == "not_started" and second["total"] == 0
    assert report["summary"]["total_score"] == round((first["total"] + second["total"]) / 2, 2)
    assert {row["id"] for row in report["competencies"]} >= {"root_cause_analysis", "code_correctness"}
    assert report["assistance"]["unaided_policy"] is True and report["versions"]["scoring"]
    total = report["summary"]["total_score"]
    with db_factory() as db:
        row = db.get(AssessmentSession, session["id"])
        service.finalize_session(db, row, reason="submitted")
        # Later practice-side activity does not rewrite the stored report.
        attempt = db.scalar(select(ChallengeAttempt).where(ChallengeAttempt.assessment_session_id == session["id"]))
        db.add(FixExplanation(user_id=member["id"], problem_id=1, attempt_id=attempt.id, why_failed="x",
                              why_works="y", invariant_preserved="z", score=100.0))
        db.commit()
        assert db.get(AssessmentSession, session["id"]).total_score == total
    assert client.get(f"/api/assessment-sessions/{session['id']}/report").json()["summary"]["total_score"] == total
    correction = {"reason": "Explanation was submitted by email during an outage.",
                  "challenge_scores": {"checkout-underflow": {"explanation": 90}}}
    assert client.post(f"/api/admin/assessment-sessions/{session['id']}/corrections", json=correction).status_code == 404
    login(client, ADMIN_EMAIL)
    assert client.post(f"/api/admin/assessment-sessions/{session['id']}/corrections",
                       json={"reason": "No adjustment given here."}).status_code == 422
    corrected = client.post(f"/api/admin/assessment-sessions/{session['id']}/corrections", json=correction).json()
    assert corrected["report_version"] == 2 and corrected["total_score"] > total
    assert corrected["report"]["corrections"][0]["before_total"] == total
    assert corrected["report"]["challenges"][0]["corrected"] is True
    override = client.post(f"/api/admin/assessment-sessions/{session['id']}/corrections",
                           json={"reason": "Calibrated against the panel review.", "total_score": 55}).json()
    assert override["report_version"] == 3 and override["total_score"] == 55
    with db_factory() as db:
        logs = list(db.scalars(select(AuditLog).where(AuditLog.action == "assessment.correction")))
        assert len(logs) == 2 and logs[0].details["before_total"] == total
        assert [entry["report_version"] for entry in db.get(AssessmentSession, session["id"]).scoring_details["history"]] == [1, 2, 3]
    events = client.get(f"/api/admin/assessment-sessions/{session['id']}/events").json()["items"]
    types = [row["type"] for row in events]
    for expected in ("assessment.session_started", "submission.created", "submission.completed",
                     "assessment.session_closed", "assessment.finalized", "assessment.corrected"):
        assert expected in types, expected


def test_report_access_summary_release_and_exports(client, member, admin, db_factory, fake_sandbox):
    login(client, ADMIN_EMAIL)
    interview = create_assessment(client, title="Interview pack", assessment_type="interview")
    login(client, member["email"])
    session = start(client, interview)
    tasks.evaluate(submit(client, session["id"]).json()["id"])
    client.post(f"/api/assessment-sessions/{session['id']}/submit")
    pending = client.get(f"/api/assessment-sessions/{session['id']}/report").json()
    assert pending["level"] == "pending_review" and "challenges" not in pending
    assert client.get(f"/api/assessment-sessions/{session['id']}/report/export?format=json").status_code == 403
    register(client, "stranger@example.com", "stranger")
    for path in ("", "/report", "/report/export?format=md"):
        assert client.get(f"/api/assessment-sessions/{session['id']}{path}").status_code == 404
    assert client.post(f"/api/admin/assessment-sessions/{session['id']}/release").status_code == 404
    login(client, ADMIN_EMAIL)
    full = client.get(f"/api/assessment-sessions/{session['id']}/report").json()
    assert full["level"] == "full" and full["viewer"] == "reviewer" and full["released"] is False
    sessions = client.get(f"/api/admin/assessments/{interview['id']}/sessions").json()["items"]
    assert sessions[0]["candidate"]["email"] == member["email"]
    assert client.post(f"/api/admin/assessment-sessions/{session['id']}/release").json() == {"released": True}
    login(client, member["email"])
    summary = client.get(f"/api/assessment-sessions/{session['id']}/report").json()
    assert summary["level"] == "summary" and summary["released"] is True
    assert "competencies" not in summary and "behavior" not in summary
    assert set(summary["challenges"][0]) == {"position", "title", "status", "total"}
    exported = client.get(f"/api/assessment-sessions/{session['id']}/report/export?format=json")
    assert exported.headers["content-type"].startswith("application/json")
    assert "attachment;" in exported.headers["content-disposition"]
    assert exported.json()["level"] == "summary"
    rows = list(csv.reader(io.StringIO(client.get(
        f"/api/assessment-sessions/{session['id']}/report/export?format=csv").text)))
    assert rows[0] == ["assessment", "Interview pack"] and ["position", "challenge", "status", "total"] in rows
    markdown = client.get(f"/api/assessment-sessions/{session['id']}/report/export?format=md")
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert markdown.text.startswith("# Interview pack") and "## Competencies" not in markdown.text
    login(client, ADMIN_EMAIL)
    detailed = client.get(f"/api/assessment-sessions/{session['id']}/report/export?format=md").text
    assert "## Competencies" in detailed and "## Behavioral metrics" in detailed
    assert client.get(f"/api/assessment-sessions/{session['id']}/report/export?format=xml").status_code == 422
    history = client.get("/api/me/assessment-sessions").json()
    assert history["total"] == 0  # the admin took no assessments
    login(client, member["email"])
    mine = client.get("/api/me/assessment-sessions").json()["items"]
    assert mine[0]["id"] == session["id"] and mine[0]["released"] is True


def test_practice_pack_records_assistance_and_disclaims_unaided_ability(
        client, member, db_factory, fake_sandbox):
    session = start(client, {"slug": "general-software-debugging"})
    assert session["assessment"]["assistance_policy"] == {"ai": "enabled", "hints": "enabled"}
    challenge = next(row for row in session["challenges"] if row["slug"] == "checkout-underflow")
    assert challenge["problem"]["assistance"]["hints"] == "enabled"
    for _ in range(2):
        tasks.evaluate(submit(client, session["id"], code="def solve(data): return 0").json()["id"])
    hint = client.post("/api/problems/checkout-underflow/hints", json={"language": "python"})
    assert hint.status_code == 202
    client.post(f"/api/assessment-sessions/{session['id']}/submit")
    report = client.get(f"/api/assessment-sessions/{session['id']}/report").json()
    assert report["assistance"]["hints_used"] == 1 and report["assistance"]["assisted"] is True
    assert any("does not represent unaided ability" in note for note in report["disclaimers"])
    assert any("Practice assessment" in note for note in report["disclaimers"])
    assert report["behavior"]["failed_test_patterns"] == {"failed": 2}
    assert report["development_areas"], "an unsolved challenge set should produce evidence-based suggestions"
    with db_factory() as db:
        problem_ids = {row.id for row in db.scalars(select(Problem).where(Problem.visibility == "public"))}
        for area in report["development_areas"]:
            for item in area["practice"]:
                assert db.scalar(select(Problem.id).where(Problem.slug == item["slug"])) in problem_ids
        assert db.scalar(select(Submission).where(Submission.assessment_session_id == session["id"])) is not None


def test_guided_policy_restricted_hints_and_invitation_lifecycle(client, member, admin, db_factory, fake_sandbox,
                                                                  monkeypatch):
    login(client, member["email"])
    session = start(client, {"slug": "ai-backend-engineer"})
    challenge = next(row for row in session["challenges"] if row["slug"] == "backoff-cap-before-growth")
    assert challenge["problem"]["assistance"] | {"assessment_session_id": None} == {
        "ai": "guided", "hints": "restricted", "source": "assessment", "assessment_session_id": None}
    slug, pid = challenge["slug"], challenge["problem_id"]
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    ai = client.post("/api/submissions", json={"problem_id": pid, "language": "python", "mode": "ai",
                                               "code": "def solve(data): return 0", "prompt": "Cap the delay before growth."})
    assert ai.status_code == 403 and "conceptual" in ai.json()["detail"]
    for _ in range(2):
        run = client.post("/api/submissions", json={"problem_id": pid, "language": "python", "kind": "run",
                                                    "code": "def solve(data): return 0"})
        tasks.evaluate(run.json()["id"])
    first = client.post(f"/api/problems/{slug}/hints", json={"language": "python"})
    assert first.status_code == 202 and first.json()["level"] == 1
    tasks.hint_task(first.json()["id"])
    second = client.post(f"/api/problems/{slug}/hints", json={"language": "python"})
    assert second.json()["id"] == first.json()["id"] and second.json()["level"] == 1  # capped at the first hint
    # A reviewer sees the session without problem content; candidates see their own work only.
    login(client, ADMIN_EMAIL)
    reviewed = client.get(f"/api/assessment-sessions/{session['id']}").json()
    assert reviewed["viewer"] == "reviewer" and all("problem" not in row for row in reviewed["challenges"])
    private = create_assessment(client, title="Invite lifecycle", visibility="invitation")
    tokens = client.post(f"/api/admin/assessments/{private['id']}/invitations",
                         json={"emails": [member["email"], "late@example.com"]}).json()["items"]
    rotated = client.post(f"/api/admin/assessments/{private['id']}/invitations", json={"emails": [member["email"]]}).json()
    statuses = {row["email"]: row["status"] for row in client.get(
        f"/api/admin/assessments/{private['id']}/invitations").json()["items"] if row["status"] != "revoked"}
    assert statuses == {member["email"]: "pending", "late@example.com": "pending"}
    late = next(row for row in tokens if row["email"] == "late@example.com")
    assert client.delete(f"/api/admin/assessment-invitations/{late['id']}").status_code == 204
    with db_factory() as db:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "assessment.invitation_revoked")) is not None
    login(client, member["email"])
    old_token = next(row for row in tokens if row["email"] == member["email"])["token"]
    assert client.post("/api/assessment-invitations/accept", json={"token": old_token}).status_code == 404
    with db_factory() as db:
        from app.models import AssessmentInvitation
        row = db.scalar(select(AssessmentInvitation).where(AssessmentInvitation.id == rotated["items"][0]["id"]))
        row.expires_at = now() - timedelta(minutes=1)
        db.commit()
    expired = client.post("/api/assessment-invitations/accept", json={"token": rotated["items"][0]["token"]})
    assert expired.status_code == 410
    assert client.post(f"/api/assessments/{private['slug']}/sessions").status_code == 404
