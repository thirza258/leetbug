"""Organizational expansion (PRD 9.7, Phase 6): company accounts, roles, private packs, candidate
reporting, comparison, exports and competency profiles."""
import csv
import io
import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import tasks
from app.catalog import CATALOG
from app.config import settings
from app.models import AssessmentSession, AuditLog, User, now

PASSWORD = "StrongPassword123!"
ADMIN_EMAIL = "platform-admin@example.com"


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
def fake_sandbox(monkeypatch):
    """Programs containing PASS return every expected output; others return a wrong answer."""
    def execute(language, code, tests_):
        ok = "PASS" in code
        return {"results": [{"status": "ok", "output": test["expected"] if ok else "wrong", "runtime_ms": 1}
                            for test in tests_], "runtime_ms": 5, "memory_kb": 100}
    monkeypatch.setattr(tasks, "execute_code", execute)


@pytest.fixture
def people(client):
    """An owner with an organization, plus an admin, a reviewer and an outsider account."""
    users = {name: register(client, f"{name}@example.com", name) for name in ("orgadmin", "reviewer", "outsider")}
    users["owner"] = register(client, "owner@example.com", "owner")
    created = client.post("/api/organizations", json={"name": "Acme Hiring"})
    assert created.status_code == 201, created.text
    org = created.json()
    for name, role in (("orgadmin", "admin"), ("reviewer", "reviewer")):
        added = client.post(f"/api/organizations/{org['slug']}/members", json={"email": f"{name}@example.com", "role": role})
        assert added.status_code == 201, added.text
    return {"org": org, **users}


def problem_id(slug):
    return next(index for index, item in enumerate(CATALOG, 1) if item["slug"] == slug)


def create_pack(client, slug, **overrides):
    body = {"title": "Acme backend debugging", "duration_seconds": 1800,
            "configuration": {"problems": ["checkout-underflow", "missing-last-item"], "diagnosis_required": False},
            "assistance_policy": {"ai": "disabled", "hints": "disabled"}, **overrides}
    response = client.post(f"/api/organizations/{slug}/assessments", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def run_candidate(client, email, username, assessment, *, code):
    """Register an invited candidate, start the pack, submit one challenge and finish."""
    register(client, email, username)
    session = client.post(f"/api/assessments/{assessment['slug']}/sessions")
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    submitted = client.post("/api/submissions", json={
        "problem_id": problem_id("checkout-underflow"), "language": "python", "code": code, "kind": "submit",
        "assessment_session_id": session_id})
    assert submitted.status_code == 202, submitted.text
    tasks.evaluate(submitted.json()["id"])
    assert client.post(f"/api/assessment-sessions/{session_id}/submit").status_code == 200
    return session_id


def test_company_accounts_roles_and_last_owner_protection(client, people, db_factory):
    org = people["org"]
    slug = org["slug"]
    assert org["slug"] == "acme-hiring" and org["role"] == "owner" and org["permissions"]["manage"]
    assert client.post("/api/organizations", json={"name": "Other", "slug": slug}).status_code == 409
    assert client.post("/api/organizations", json={"name": "Bad slug", "slug": "UPPER"}).status_code == 422
    listing = client.get("/api/organizations").json()
    assert [(row["slug"], row["role"]) for row in listing["items"]] == [(slug, "owner")]
    members = client.get(f"/api/organizations/{slug}/members").json()["items"]
    assert [(row["username"], row["role"]) for row in members] == [
        ("owner", "owner"), ("orgadmin", "admin"), ("reviewer", "reviewer")]
    assert client.post(f"/api/organizations/{slug}/members", json={"email": "nobody@example.com"}).status_code == 404
    assert client.post(f"/api/organizations/{slug}/members", json={"email": "reviewer@example.com"}).status_code == 409
    # The last owner can neither leave nor be demoted.
    owner_id = people["owner"]["id"]
    assert client.patch(f"/api/organizations/{slug}/members/{owner_id}", json={"role": "admin"}).status_code == 409
    assert client.delete(f"/api/organizations/{slug}/members/{owner_id}").status_code == 409
    assert client.patch(f"/api/organizations/{slug}", json={"name": "Acme Talent"}).json()["name"] == "Acme Talent"

    # Non-members cannot discover the organization or any of its data.
    login(client, "outsider@example.com")
    for path in ("", "/members", "/assessments", "/candidates", "/analytics", "/invitations", "/competency-profiles",
                 "/compare?sessions=a,b"):
        assert client.get(f"/api/organizations/{slug}{path}").status_code == 404, path
    assert client.patch(f"/api/organizations/{slug}", json={"name": "Hijacked"}).status_code == 404
    assert client.get("/api/organizations").json()["items"] == []

    # Reviewers read but cannot manage.
    login(client, "reviewer@example.com")
    assert client.get(f"/api/organizations/{slug}").json()["permissions"] == {"manage": False, "review": True,
                                                                            "owner": False}
    assert client.get(f"/api/organizations/{slug}/members").status_code == 200
    assert client.post(f"/api/organizations/{slug}/members", json={"email": "outsider@example.com"}).status_code == 403
    assert client.patch(f"/api/organizations/{slug}", json={"name": "Nope"}).status_code == 403

    # Admins manage members but cannot grant or change the owner role.
    login(client, "orgadmin@example.com")
    assert client.post(f"/api/organizations/{slug}/members",
                       json={"email": "outsider@example.com", "role": "owner"}).status_code == 403
    assert client.post(f"/api/organizations/{slug}/members",
                       json={"email": "outsider@example.com", "role": "reviewer"}).status_code == 201
    assert client.patch(f"/api/organizations/{slug}/members/{owner_id}", json={"role": "reviewer"}).status_code == 403
    assert client.delete(f"/api/organizations/{slug}/members/{owner_id}").status_code == 403
    assert client.delete(f"/api/organizations/{slug}/members/{people['outsider']['id']}").status_code == 204

    # A second owner allows the first to leave.
    login(client, "owner@example.com")
    assert client.patch(f"/api/organizations/{slug}/members/{people['orgadmin']['id']}",
                        json={"role": "owner"}).json()["role"] == "owner"
    assert client.delete(f"/api/organizations/{slug}/members/{owner_id}").status_code == 204
    assert client.get(f"/api/organizations/{slug}").status_code == 404
    with db_factory() as db:
        actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    for action in ("organization.created", "organization.member_added", "organization.renamed",
                   "organization.member_role_changed", "organization.member_removed"):
        assert action in actions, action


def test_platform_admin_can_view_but_is_not_listed_as_member(client, people, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", ADMIN_EMAIL)
    register(client, ADMIN_EMAIL, "platformadmin")
    slug = people["org"]["slug"]
    assert client.get(f"/api/organizations/{slug}").json()["role"] == "owner"
    assert client.get("/api/organizations").json()["items"] == []
    assert len(client.get(f"/api/organizations/{slug}/members").json()["items"]) == 3


def test_private_pack_invitations_reports_compare_and_export(client, people, db_factory, fake_sandbox):
    slug = people["org"]["slug"]
    login(client, "reviewer@example.com")
    body = {"title": "Reviewer cannot", "configuration": {"problems": ["checkout-underflow"]}}
    assert client.post(f"/api/organizations/{slug}/assessments", json=body).status_code == 403
    login(client, "owner@example.com")
    # Organization packs are never public, through either endpoint.
    assert client.post(f"/api/organizations/{slug}/assessments", json={**body, "visibility": "public"}).status_code == 422
    org_id = people["org"]["id"]
    generic = client.post("/api/admin/assessments", json={**body, "organization_id": org_id, "visibility": "public"})
    assert generic.status_code == 422
    assert client.post("/api/admin/assessments", json={**body, "organization_id": "0" * 36}).status_code == 403
    pack = create_pack(client, slug)
    assert pack["organization_id"] == org_id and pack["visibility"] == "invitation" and pack["status"] == "draft"
    assert client.patch(f"/api/admin/assessments/{pack['id']}", json={"visibility": "public"}).status_code == 422
    assert client.post(f"/api/admin/assessments/{pack['id']}/publish").status_code == 200
    assert client.get(f"/api/admin/assessments?organization_id={org_id}").json()["total"] == 1
    invited = client.post(f"/api/admin/assessments/{pack['id']}/invitations",
                          json={"emails": ["cand1@example.com", "cand2@example.com"]})
    assert invited.status_code == 201
    listed = client.get(f"/api/organizations/{slug}/assessments").json()["items"]
    assert [row["slug"] for row in listed] == [pack["slug"]]

    # Uninvited users neither see nor start the pack.
    login(client, "outsider@example.com")
    assert pack["slug"] not in {row["slug"] for row in client.get("/api/assessments").json()["items"]}
    assert client.post(f"/api/assessments/{pack['slug']}/sessions").status_code == 404

    first = run_candidate(client, "cand1@example.com", "cand1", pack, code="def solve(data): return 0  # PASS")
    # Candidates see only their own work.
    assert client.get(f"/api/organizations/{slug}/candidates").status_code == 404
    second = run_candidate(client, "cand2@example.com", "cand2", pack, code="def solve(data): return 0")
    assert client.get(f"/api/assessment-sessions/{first}/report").status_code == 404
    assert client.get(f"/api/organizations/{slug}/compare?sessions={first},{second}").status_code == 404

    login(client, "reviewer@example.com")
    candidates = client.get(f"/api/organizations/{slug}/candidates").json()
    by_session = {row["session_id"]: row for row in candidates["items"]}
    assert set(by_session) == {first, second} and candidates["notes"]
    assert by_session[first]["total_score"] > by_session[second]["total_score"]
    assert by_session[first]["candidate"]["email"] == "cand1@example.com"
    assert client.get(f"/api/organizations/{slug}/candidates?assessment_id={'0' * 36}").status_code == 404
    report = client.get(f"/api/assessment-sessions/{first}/report")
    assert report.status_code == 200 and report.json()["viewer"] == "reviewer" and report.json()["level"] == "full"
    assert client.get(f"/api/admin/assessments/{pack['id']}/sessions").json()["total"] == 2
    # Reviewers cannot manage the pack.
    assert client.post(f"/api/admin/assessments/{pack['id']}/archive").status_code == 403

    comparison = client.get(f"/api/organizations/{slug}/compare?sessions={second},{first}").json()
    assert [column["session_id"] for column in comparison["sessions"]] == [second, first]
    assert comparison["same_assessment"] and any("do not replace" in note for note in comparison["notes"])
    assert {row["key"] for row in comparison["challenges"]} == {"checkout-underflow", "missing-last-item"}
    assert comparison["sessions"][1]["challenges"]["checkout-underflow"]["status"] == "solved"
    assert "root_cause_analysis" in comparison["sessions"][0]["competencies"]
    assert client.get(f"/api/organizations/{slug}/compare?sessions={first}").status_code == 422
    assert client.get(f"/api/organizations/{slug}/compare?sessions={first},{'0' * 36}").status_code == 404

    exported = client.get(f"/api/organizations/{slug}/assessments/{pack['id']}/export?format=csv")
    assert exported.status_code == 200 and exported.headers["content-type"].startswith("text/csv")
    assert f'{slug}-{pack["slug"]}-results.csv' in exported.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(exported.text)))
    assert rows[0][:3] == ["session_id", "candidate_username", "candidate_email"]
    assert "challenge:checkout-underflow" in rows[0] and "competency:root_cause_analysis" in rows[0]
    assert {row[1] for row in rows[1:]} == {"cand1", "cand2"}
    as_json = json.loads(client.get(f"/api/organizations/{slug}/assessments/{pack['id']}/export?format=json").text)
    assert len(as_json["sessions"]) == 2 and as_json["sessions"][0]["report"]["level"] == "full"

    analytics = client.get(f"/api/organizations/{slug}/analytics").json()
    assert analytics["totals"]["finalized"] == 2 and analytics["totals"]["completion_rate"] == 1.0
    assert sum(bucket["count"] for bucket in analytics["score_distribution"]) == 2
    assert analytics["assessments"][0]["median_score"] is not None
    assert all(row["discrimination_status"] == "insufficient_data" and row["discrimination_index"] is None
               for row in analytics["challenges"])
    assert analytics["assistance"]["ai_usage_share"] == 0
    assert client.get(f"/api/organizations/{slug}/analytics?assessment_id={'0' * 36}").status_code == 404

    # Invitation overview and expiry management.
    invitations = client.get(f"/api/organizations/{slug}/invitations").json()
    assert invitations["status_counts"] == {"accepted": 2}
    accepted = invitations["items"][0]["id"]
    login(client, "owner@example.com")
    assert client.patch(f"/api/organizations/{slug}/invitations/{accepted}", json={"extend_days": 3}).status_code == 409
    third = client.post(f"/api/admin/assessments/{pack['id']}/invitations", json={"emails": ["cand3@example.com"],
                                                                                 "expires_in_days": 1}).json()
    pending = third["items"][0]["id"]
    extended = client.patch(f"/api/organizations/{slug}/invitations/{pending}", json={"extend_days": 5}).json()
    assert extended["status"] == "pending"
    assert client.patch(f"/api/organizations/{slug}/invitations/{pending}", json={}).status_code == 422
    login(client, "reviewer@example.com")
    assert client.delete(f"/api/organizations/{slug}/invitations/{pending}").status_code == 403
    login(client, "owner@example.com")
    assert client.delete(f"/api/organizations/{slug}/invitations/{pending}").status_code == 204
    statuses = {row["email"]: row["status"] for row in client.get(f"/api/organizations/{slug}/invitations").json()["items"]}
    assert statuses["cand3@example.com"] == "revoked"
    closes = (now() + timedelta(days=7)).isoformat()
    updated = client.patch(f"/api/organizations/{slug}/assessments/{pack['id']}/expiration",
                           json={"available_until": closes}).json()
    assert updated["available_until"] and updated["version"] == pack["version"]


def test_discrimination_index_with_enough_finalized_sessions(client, people, db_factory):
    slug = people["org"]["slug"]
    pack = create_pack(client, slug)
    with db_factory() as db:
        for index in range(12):
            user = User(email=f"synthetic{index}@example.com", username=f"synthetic{index}", password_hash="x")
            db.add(user)
            db.flush()
            strong = index >= 6
            total = 40 + index * 5
            challenges = [
                {"slug": "checkout-underflow", "title": "Checkout", "difficulty": "medium",
                 "status": "solved" if strong else "attempted", "total": total,
                 "components": {"correctness": 100.0 if strong else 40.0}},
                {"slug": "missing-last-item", "title": "Missing", "difficulty": "easy", "status": "solved",
                 "total": 80.0, "components": {"correctness": 100.0}},
            ]
            report = {"summary": {"total_score": total, "challenges_completed": 2 if strong else 1, "challenges_total": 2,
                                  "time_spent_seconds": 600},
                      "challenges": challenges,
                      "competencies": [{"id": "root_cause_analysis", "name": "Root-cause analysis", "score": total}],
                      "assistance": {"policy": {"ai": "enabled", "hints": "disabled"}, "hints_used": 0,
                                     "ai_interactions": 1 if index % 2 else 0, "ai_submissions": 0}}
            db.add(AssessmentSession(assessment_id=pack["id"], user_id=user.id, status="completed",
                                     expires_at=now(), completed_at=now(), finalized_at=now(),
                                     total_score=total, report=report, report_version=1,
                                     config_snapshot={"version": 1}, challenge_order=[1, 2]))
        # An active session counts toward volume but not toward statistics.
        db.add(AssessmentSession(assessment_id=pack["id"], user_id=people["outsider"]["id"], status="active",
                                 expires_at=now() + timedelta(hours=1), challenge_order=[1, 2]))
        db.commit()
    analytics = client.get(f"/api/organizations/{slug}/analytics?assessment_id={pack['id']}").json()
    assert analytics["totals"] == {"sessions": 13, "finalized": 12, "active": 1, "completion_rate": 1.0,
                                   "mean_score": 67.5, "median_score": 67.5}
    by_slug = {row["slug"]: row for row in analytics["challenges"]}
    assert by_slug["checkout-underflow"]["discrimination_status"] == "ok"
    assert by_slug["checkout-underflow"]["discrimination_index"] == 1.0
    assert by_slug["missing-last-item"]["discrimination_index"] == 0.0
    assert by_slug["checkout-underflow"]["mean_correctness"] == 70.0
    # Hardest challenge (lowest mean correctness) first.
    assert analytics["challenges"][0]["slug"] == "checkout-underflow"
    assert analytics["assistance"]["ai_usage_share"] == 0.5
    assert analytics["competencies"][0] == {"id": "root_cause_analysis", "name": "Root-cause analysis",
                                            "mean": 67.5, "sessions": 12}
    assert sum(bucket["count"] for bucket in analytics["score_distribution"]) == 12


def test_competency_profiles_validation_scope_and_attachment(client, people, monkeypatch, db_factory, fake_sandbox):
    slug = people["org"]["slug"]
    base = f"/api/organizations/{slug}/competency-profiles"
    assert client.post(base, json={"name": "Bad", "weights": {"not-a-skill": 1}}).status_code == 422
    assert client.post(base, json={"name": "Zero", "weights": {"concurrency": 0}}).status_code == 422
    assert client.post(base, json={"name": "Empty", "weights": {}}).status_code == 422
    profile = client.post(base, json={"name": "Backend platform", "weights": {
        "concurrency": 3, "race_condition": 2, "reproduction": 1}})
    assert profile.status_code == 201, profile.text
    profile = profile.json()
    assert profile["scope"] == "organization" and profile["slug"] == "backend-platform"
    assert client.post(base, json={"name": "Duplicate", "slug": "backend-platform", "weights": {"concurrency": 1}}).status_code == 409
    renamed = client.patch(f"{base}/{profile['id']}", json={"weights": {"concurrency": 5}}).json()
    assert renamed["weights"] == {"concurrency": 5.0}

    login(client, "reviewer@example.com")
    assert client.post(base, json={"name": "Reviewer", "weights": {"concurrency": 1}}).status_code == 403
    assert client.get(base).json()["total"] == 1
    login(client, "outsider@example.com")
    assert client.get(f"/api/competency-profiles?organization_id={people['org']['id']}").status_code == 404
    assert client.post("/api/admin/competency-profiles", json={"name": "Global", "weights": {"concurrency": 1}}).status_code == 403

    monkeypatch.setattr(settings, "admin_email", ADMIN_EMAIL)
    register(client, ADMIN_EMAIL, "platformadmin")
    template = client.post("/api/admin/competency-profiles", json={"name": "General debugging", "weights": {
        "root_cause_analysis": 2, "code_correctness": 1}})
    assert template.status_code == 201 and template.json()["scope"] == "global"
    other = client.post("/api/organizations", json={"name": "Other Co"}).json()
    foreign = client.post(f"/api/organizations/{other['slug']}/competency-profiles",
                          json={"name": "Foreign", "weights": {"concurrency": 1}}).json()

    login(client, "owner@example.com")
    assert client.get("/api/competency-profiles/global").json()["total"] == 1
    picker = client.get(f"/api/competency-profiles?organization_id={people['org']['id']}").json()
    assert [row["slug"] for row in picker["items"]] == ["backend-platform", "general-debugging"]
    # Another organization's profile cannot be attached; the own or a global one can.
    body = {"title": "Profiled pack", "configuration": {"problems": ["checkout-underflow"], "diagnosis_required": False}}
    assert client.post(f"/api/organizations/{slug}/assessments",
                       json={**body, "competency_profile_id": foreign["id"]}).status_code == 422
    pack = create_pack(client, slug, title="Profiled pack", competency_profile_id=profile["id"],
                       configuration={"problems": ["checkout-underflow"], "diagnosis_required": False})
    client.post(f"/api/admin/assessments/{pack['id']}/publish")
    client.post(f"/api/admin/assessments/{pack['id']}/invitations", json={"emails": ["profiled@example.com"]})
    session_id = run_candidate(client, "profiled@example.com", "profiled", pack, code="def solve(data): return 0  # PASS")
    login(client, "owner@example.com")
    report = client.get(f"/api/assessment-sessions/{session_id}/report").json()
    assert report["profile"]["components"][0]["id"] == "concurrency"
    # Profiles in use cannot be deleted; later edits never rewrite finished reports.
    assert client.delete(f"{base}/{profile['id']}").status_code == 409
    client.patch(f"{base}/{profile['id']}", json={"weights": {"reproduction": 1}})
    with db_factory() as db:
        assert db.get(AssessmentSession, session_id).config_snapshot["competency_profile"] == {"concurrency": 5.0}
    client.post(f"/api/admin/assessments/{pack['id']}/archive")
    assert client.delete(f"{base}/{profile['id']}").status_code == 204
    with db_factory() as db:
        actions = {row.action for row in db.scalars(select(AuditLog))}
    assert {"competency_profile.created", "competency_profile.updated", "competency_profile.deleted"} <= actions
