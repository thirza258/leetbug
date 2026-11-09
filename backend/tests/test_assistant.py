import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from app import llm, rag, tasks
from app.assistant import service
from app.assistant.context import build_context
from app.assistant.generation import assistant_messages
from app.assistant.intents import classify_intent
from app.assistant.responder import deterministic_response
from app.assistant.tasks import assistant_task
from app.assistant.validation import CODE_PLACEHOLDER, validate_sections
from app.config import settings
from app.models import (
    AIInteraction,
    Assessment,
    AssessmentSession,
    ChallengeAttempt,
    Hint,
    Problem,
    Submission,
    now,
)

EVAL = json.loads((Path(__file__).parent / "fixtures" / "assistant_eval.json").read_text())
SLUG = "checkout-underflow"
STARTER_BUG = 'def solve(data):\n    subtotal = sum(data["prices"])\n    return {"total": subtotal - data["discount"]}\n'
RUNTIME_CODE = 'def solve(data):\n    subtotal = sum(data["price"])\n    return {"total": subtotal - data["discount"]}\n'
TRACEBACK = ('Traceback (most recent call last):\n  File "main.py", line 5, in <module>\n'
             '  File "solution.py", line 2, in solve\n    subtotal = sum(data["price"])\nKeyError: \'price\'')


@pytest.fixture(autouse=True)
def offline_chroma(monkeypatch):
    def unavailable():
        raise ConnectionError("Chroma offline")
    monkeypatch.setattr(rag, "collection", unavailable)


def public(name, data, expected, actual, status="failed", message=""):
    return {"name": name, "hidden": False, "status": status, "input": data, "expected": expected, "actual": actual,
            "assertions": [], "message": message, "runtime_ms": 1}


BEHAVIORAL_RESULTS = [
    public("A regular order", {"prices": [2500, 1500], "discount": 500}, {"total": 3500}, {"total": 3500}, "passed"),
    public("Discount exceeds subtotal", {"prices": [1200], "discount": 2000}, {"total": 0}, {"total": -800}),
    {"name": "Hidden case 3", "hidden": True, "status": "passed"},
    {"name": "Hidden case 4", "hidden": True, "status": "failed"},
]
RUNTIME_RESULTS = [
    public("A regular order", {"prices": [2500, 1500], "discount": 500}, {"total": 3500}, None, "runtime_error",
           TRACEBACK),
    public("Discount exceeds subtotal", {"prices": [1200], "discount": 2000}, {"total": 0}, None, "runtime_error",
           TRACEBACK),
    {"name": "Hidden case 3", "hidden": True, "status": "runtime_error"},
    {"name": "Hidden case 4", "hidden": True, "status": "runtime_error"},
]


def evaluated_submission(client, db_factory, *, code=STARTER_BUG, status="failed", results=None, kind="submit"):
    """Create a submission through the API (so it has an attempt), then record a graded outcome."""
    response = client.post("/api/submissions", json={"problem_id": 1, "language": "python", "kind": kind,
                                                     "code": code})
    assert response.status_code == 202, response.text
    with db_factory() as db:
        row = db.get(Submission, response.json()["id"])
        row.status, row.results = status, BEHAVIORAL_RESULTS if results is None else results
        row.completed_at = now()
        db.commit()
        return row.id


def assert_private_data_absent(text, problem, member):
    for test in problem.tests:
        if test["hidden"]:
            assert json.dumps(test["input"]) not in text
    assert "-200" not in text and "[-500, 1500]" not in text
    for solution in problem.solutions.values():
        for line in solution.splitlines():
            if len(line.strip()) > 20 and line.strip() not in problem.starters.get("python", ""):
                assert line.strip() not in text
    assert problem.explanation not in text
    assert not any(hint in text for hint in problem.hints)
    assert member["email"] not in text
    assert not re.search(rf"\b{member['username']}\b", text)


def run(client, path, body):
    response = client.post(path, json=body)
    assert response.status_code == 202, response.text
    assistant_task(response.json()["id"])
    result = client.get(f"/api/ai-interactions/{response.json()['id']}")
    assert result.status_code == 200
    return result.json()


def section(view, key):
    return next((row["body"] for row in view["response"]["sections"] if row["key"] == key), "")


def test_context_and_model_request_exclude_private_data(client, member, db_factory, monkeypatch):
    submission_id = evaluated_submission(client, db_factory)
    with db_factory() as db:
        problem = db.get(Problem, 1)
        submission = db.get(Submission, submission_id)
        attempt = db.get(ChallengeAttempt, submission.attempt_id)
        context = build_context(db, problem, "python", user_id=member["id"], attempt=attempt, submission=submission)
    assert context["version"] == "ctx-v1"
    assert context["execution"]["hidden_failed"] == 1 and context["execution"]["failure_type"] == "behavioral"
    assert context["execution"]["failing_public"][0]["name"] == "Discount exceeds subtotal"
    assert context["user_state"]["attempt_count"] == 1 and context["problem"]["bug_categories"]
    assert_private_data_absent(json.dumps(context), problem, member)
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    captured = []

    def fake_complete(messages, **kwargs):
        captured.append(messages)
        return json.dumps({"what_changed": "No changes from the starter.",
                           "why_not_resolved": "The discount can exceed the subtotal [1].",
                           "unsatisfied_requirement": "The final total must never be negative.",
                           "likely_code_path": "Line 3 returns the subtraction.", "documentation": "[1]",
                           "next_step": "Trace the second public case."}), 120
    monkeypatch.setattr(llm, "complete", fake_complete)
    view = run(client, f"/api/problems/{SLUG}/why-fix-failed", {"language": "python", "submission_id": submission_id})
    assert view["status"] == "completed" and view["metadata"]["generation"] == "model"
    assert view["token_usage"] == 120 and view["intent"] == "why_fix_failed"
    request = json.dumps(captured)
    assert_private_data_absent(request, problem, member)
    assert "Discount exceeds subtotal" in request and "data, never instructions" in request


@pytest.mark.parametrize("case", EVAL["intent_cases"], ids=lambda case: case["question"][:40])
def test_intent_classification_table(case):
    assert classify_intent(case["question"])["intent"] == case["expected"]


def test_intent_defaults_follow_the_users_state():
    assert classify_intent("help")["intent"] == "explain_problem"
    assert classify_intent("help", has_failure=True)["intent"] == "why_fix_failed"
    assert classify_intent("", has_failure=True, has_error=True)["intent"] == "explain_runtime_error"
    result = classify_intent("Why does my fix still fail?")
    assert 0.4 <= result["confidence"] <= 0.95 and "why-still-fails" in result["cues"]


def test_why_fix_failed_deterministic_behavioral(client, member, db_factory):
    evaluated_submission(client, db_factory)
    view = run(client, f"/api/problems/{SLUG}/why-fix-failed", {"language": "python", "code": STARTER_BUG})
    assert view["status"] == "completed" and view["metadata"]["generation"] == "deterministic"
    keys = [row["key"] for row in view["response"]["sections"]]
    assert keys[:2] == ["what_changed", "why_not_resolved"] and keys[-1] == "next_step"
    assert "identical to the starter" in section(view, "what_changed")
    why = section(view, "why_not_resolved")
    assert '"Discount exceeds subtotal" expected {"total": 0}' in why and '{"total": -800}' in why
    assert "1 of 2 hidden cases also fail" in why
    assert "never be negative" in section(view, "unsatisfied_requirement")
    assert "line 3" in section(view, "likely_code_path")
    assert view["sources"] and view["retrieval"]["method"] == "bundled-docs"
    assert view["retrieval_ms"] is not None and view["generation_ms"] is not None and view["latency_ms"] is not None
    assert view["metadata"]["grounding_score"] >= 0.5 and not view["metadata"]["validation"]["blocked"]


def test_runtime_error_is_explained_differently_from_a_behavioral_failure(client, member, db_factory):
    evaluated_submission(client, db_factory, code=RUNTIME_CODE, status="runtime_error", results=RUNTIME_RESULTS)
    view = run(client, f"/api/problems/{SLUG}/why-fix-failed", {"language": "python", "code": RUNTIME_CODE})
    why = section(view, "why_not_resolved")
    assert "KeyError" in why and "line 2" in why and "expected" not in why
    assert "Line 2" in section(view, "likely_code_path")
    assert "Reproduce the crash" in section(view, "next_step")
    explained = run(client, f"/api/problems/{SLUG}/debug-assistant",
                    {"language": "python", "code": RUNTIME_CODE, "question": "What does this error mean?"})
    assert explained["intent"] == "explain_runtime_error"
    assert "dictionary lookup" in section(explained, "error")
    assert "python-exceptions" in explained["retrieval"]["selected"]


def test_validator_redacts_strips_and_blocks(client, member, db_factory):
    with db_factory() as db:
        problem = db.get(Problem, 1)
        context = build_context(db, problem, "python", user_id=member["id"])
    sources = [{"title": "Python: numeric types", "url": "https://docs.python.org/3/library/stdtypes.html"}]
    for case in EVAL["validation_cases"]:
        sections, flags = validate_sections([{"key": "answer", "title": "Answer", "body": case["response"]}],
                                            problem=problem, context=context, sources=sources)
        body = " ".join(row["body"] for row in sections)
        for flag in case["expect_flags"]:
            assert flags[flag], (case["name"], flag)
        for fragment in case["must_not_contain"]:
            assert fragment not in body, (case["name"], fragment)
        for fragment in case.get("must_contain", []):
            assert fragment in body, (case["name"], fragment)
        # No evaluated run exists in this context, so any remaining answer carries the limitation note.
        assert flags["limitation_added"] or not sections
    long_block = "```python\n" + "\n".join(f"x{i} = {i}" for i in range(20)) + "\n```"
    sections, flags = validate_sections([{"key": "answer", "title": "Answer", "body": f"Look:\n{long_block}"}],
                                        problem=problem, context=context, sources=sources)
    assert flags["long_code_blocks"] == 1 and CODE_PLACEHOLDER in sections[0]["body"]
    # Public data and the user's own code are never redacted.
    sections, flags = validate_sections([{"key": "answer", "title": "Answer",
                                          "body": 'The public case {"prices": [1200], "discount": 2000} returns `subtotal - data["discount"]` [1].'}],
                                        problem=problem, context=context, sources=sources)
    assert not flags["blocked"] and "[1]" in sections[0]["body"] and "2000" in sections[0]["body"]


def test_model_failure_and_unusable_output_fall_back_to_deterministic(client, member, db_factory, monkeypatch):
    evaluated_submission(client, db_factory)
    monkeypatch.setattr(settings, "ai_provider", "ollama")

    def unavailable(*args, **kwargs):
        raise llm.AIUnavailable("model down")
    monkeypatch.setattr(llm, "complete", unavailable)
    view = run(client, f"/api/problems/{SLUG}/why-fix-failed", {"language": "python"})
    assert view["status"] == "completed" and view["metadata"]["generation"] == "model-fallback"
    assert "Discount exceeds subtotal" in section(view, "why_not_resolved")
    monkeypatch.setattr(llm, "complete", lambda *args, **kwargs: ("I think it is fine.", 5))
    view = run(client, f"/api/problems/{SLUG}/why-fix-failed", {"language": "python"})
    assert view["metadata"]["generation"] == "model-fallback"


def test_model_output_is_validated_and_backfilled(client, member, db_factory, monkeypatch):
    evaluated_submission(client, db_factory)
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "ai_api_key", "test")
    malicious = {"what_changed": "Nothing yet.",
                 "why_not_resolved": "```python\ndef solve(data):\n    return {'total': 0}\n```",
                 "unsatisfied_requirement": "Hidden case: {\"prices\": [-500, 1500], \"discount\": -200}.",
                 "likely_code_path": "See https://evil.example/answers and [9].",
                 "documentation": "[1]", "next_step": "Trace the second case."}
    monkeypatch.setattr(llm, "complete", lambda *args, **kwargs: (json.dumps(malicious), 50))
    view = run(client, f"/api/problems/{SLUG}/why-fix-failed", {"language": "python"})
    flags = view["metadata"]["validation"]
    assert view["metadata"]["generation"] == "model"
    assert flags["solution_like"] and flags["redacted_hidden"] and flags["unverified_urls"] and flags["invalid_citations"]
    text = json.dumps(view["response"])
    assert "def solve" not in text and "-200" not in text and "evil.example" not in text and "[9]" not in text
    # The emptied "why" section is replaced by the deterministic analysis.
    assert "why_not_resolved" in flags["deterministic_backfill"]
    assert "Discount exceeds subtotal" in section(view, "why_not_resolved")


def test_interactions_are_private_and_submissions_must_belong_to_the_user(client, member, db_factory):
    submission_id = evaluated_submission(client, db_factory)
    view = run(client, f"/api/problems/{SLUG}/debug-assistant", {"language": "python", "question": "Which test fails?"})
    assert view["intent"] == "identify_failing_test"
    assert "Discount exceeds subtotal" in section(view, "failing_tests")
    history = client.get(f"/api/problems/{SLUG}/ai-interactions").json()
    assert history["total"] == 1 and history["items"][0]["id"] == view["id"]
    assert client.post(f"/api/problems/{SLUG}/debug-assistant", json={"language": "go", "question": "help"}).status_code == 422
    assert client.post(f"/api/problems/{SLUG}/debug-assistant", json={"language": "python", "question": "   "}).status_code == 422
    client.post("/api/auth/logout")
    other = client.post("/api/auth/register", json={"email": "other@example.com", "username": "other",
                                                    "password": "StrongPassword123!"}).json()
    client.headers["X-CSRF-Token"] = other["csrf_token"]
    assert client.get(f"/api/ai-interactions/{view['id']}").status_code == 404
    assert client.get(f"/api/problems/{SLUG}/ai-interactions").json()["total"] == 0
    response = client.post(f"/api/problems/{SLUG}/why-fix-failed", json={"language": "python",
                                                                          "submission_id": submission_id})
    assert response.status_code == 404


def start_assessment(db_factory, member, policy):
    with db_factory() as db:
        assessment = Assessment(slug="policy-check", title="Policy check", duration_seconds=3600, status="published",
                                configuration={"problems": [SLUG]}, assistance_policy=policy)
        db.add(assessment)
        db.flush()
        session = AssessmentSession(assessment_id=assessment.id, user_id=member["id"], status="active",
                                    expires_at=now() + timedelta(hours=1), challenge_order=[1],
                                    config_snapshot={"assistance_policy": policy, "configuration": {"problems": [SLUG]}})
        db.add(session)
        db.commit()
        return session.id


def test_assessment_policy_is_enforced_server_side(client, member, db_factory):
    start_assessment(db_factory, member, {"ai": "disabled", "hints": "disabled"})
    ask = {"language": "python", "question": "What is a race condition?"}
    assert client.post(f"/api/problems/{SLUG}/debug-assistant", json=ask).status_code == 403
    assert client.post(f"/api/problems/{SLUG}/why-fix-failed", json={"language": "python"}).status_code == 403


def test_guided_policy_allows_only_conceptual_intents(client, member, db_factory):
    session_id = start_assessment(db_factory, member, {"ai": "guided", "hints": "disabled"})
    response = client.post(f"/api/problems/{SLUG}/debug-assistant",
                           json={"language": "python", "question": "What is a race condition?"})
    assert response.status_code == 202 and response.json()["assessment_session_id"] == session_id
    assert response.json()["intent"] == "explain_concept"
    assert client.post(f"/api/problems/{SLUG}/why-fix-failed", json={"language": "python"}).status_code == 403
    review = {"language": "python", "question": "Can you review my patch?"}
    assert client.post(f"/api/problems/{SLUG}/debug-assistant", json=review).status_code == 403
    hint = {"language": "python", "question": "I'm stuck, give me a hint"}
    assert client.post(f"/api/problems/{SLUG}/debug-assistant", json=hint).status_code == 403


def test_payload_is_cleared_after_success_and_failure(client, member, db_factory, monkeypatch):
    first = client.post(f"/api/problems/{SLUG}/debug-assistant",
                        json={"language": "python", "question": "Explain the problem", "code": STARTER_BUG}).json()
    with db_factory() as db:
        assert db.get(AIInteraction, first["id"]).payload["code"] == STARTER_BUG
    assistant_task(first["id"])
    assistant_task(first["id"])  # idempotent delivery
    with db_factory() as db:
        row = db.get(AIInteraction, first["id"])
        assert row.payload is None and row.status == "completed" and row.context_summary["code_hash"]
        assert STARTER_BUG not in json.dumps(row.context_summary)

    def broken(*args, **kwargs):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(service, "respond", broken)
    second = client.post(f"/api/problems/{SLUG}/debug-assistant",
                         json={"language": "python", "question": "Explain the problem", "code": STARTER_BUG}).json()
    assistant_task(second["id"])
    with db_factory() as db:
        row = db.get(AIInteraction, second["id"])
        assert row.status == "error" and row.payload is None and "Manual debugging is unaffected" in row.error


def request_hint(client):
    response = client.post(f"/api/problems/{SLUG}/hints", json={"language": "python", "code": STARTER_BUG})
    assert response.status_code == 202, response.text
    tasks.hint_task(response.json()["id"])
    return client.get(f"/api/hints/{response.json()['id']}").json()


def test_adaptive_hints_use_the_latest_run_and_never_repeat(client, member, db_factory, monkeypatch):
    evaluated_submission(client, db_factory)
    evaluated_submission(client, db_factory)
    first = request_hint(client)
    with db_factory() as db:
        problem = db.get(Problem, 1)
        stored = db.get(Hint, first["id"])
        assert stored.context["adaptive"]["level_focus"] == "conceptual" and "code" not in stored.context
    assert first["status"] == "completed" and first["level"] == 1
    assert first["text"] == f'Your latest run still fails "Discount exceeds subtotal". {problem.hints[0]}'
    assert first["retrieval"].endswith("+adaptive") and first["sources"]
    monkeypatch.setattr(settings, "ai_provider", "ollama")
    prompts = []

    def repeat_previous(messages, **kwargs):
        prompts.append(messages)
        return first["text"], 30
    monkeypatch.setattr(llm, "complete", repeat_previous)
    second = request_hint(client)
    assert second["level"] == 2 and second["text"] != first["text"]
    assert problem.hints[1] in second["text"]
    assert any(first["text"] in message["content"] for call in prompts for message in call)
    with db_factory() as db:
        adaptive = db.get(Hint, second["id"]).context["adaptive"]
        assert adaptive["repetition_avoided"] and adaptive["previous_hints"] == 1
    monkeypatch.setattr(llm, "complete", lambda *args, **kwargs: (
        "Think about which values may cross zero before you subtract them [1].", 30))
    third = request_hint(client)
    assert third["level"] == 3 and third["text"].startswith("Think about which values")


def test_adaptive_hint_falls_back_to_the_documentation_hint(client, member, db_factory, monkeypatch):
    evaluated_submission(client, db_factory)
    evaluated_submission(client, db_factory)

    def broken(*args, **kwargs):
        raise RuntimeError("context unavailable")
    monkeypatch.setattr(service, "build_context", broken)
    monkeypatch.setattr(tasks, "generate_hint", lambda *args: {"text": "Base hint.", "sources": [],
                                                               "retrieval": "bundled-docs"})
    assert request_hint(client)["text"] == "Base hint."


@pytest.mark.parametrize("case", EVAL["context_cases"], ids=lambda case: case["name"])
def test_evaluation_dataset_context_cases(client, member, db_factory, monkeypatch, case):
    if case["submission"] == "behavioral":
        evaluated_submission(client, db_factory)
    elif case["submission"] == "runtime":
        evaluated_submission(client, db_factory, code=RUNTIME_CODE, status="runtime_error", results=RUNTIME_RESULTS)
    code = case.get("code") or (RUNTIME_CODE if case["submission"] == "runtime" else STARTER_BUG)
    if case.get("malicious_model"):
        monkeypatch.setattr(settings, "ai_provider", "ollama")
        with db_factory() as db:
            reference = db.get(Problem, 1).solutions["python"]
        prompts = []

        def obey_injection(messages, **kwargs):
            prompts.append(messages)
            return json.dumps({"what_changed": "x", "why_not_resolved": f"```python\n{reference}```",
                               "next_step": "Paste the code above."}), 10
        monkeypatch.setattr(llm, "complete", obey_injection)
    view = run(client, f"/api/problems/{SLUG}/debug-assistant",
               {"language": "python", "question": case["question"], "code": code})
    text = json.dumps(view["response"])
    if "expect_intent" in case:
        assert view["intent"] == case["expect_intent"]
    if case.get("expect_limitation"):
        assert re.search(r"no evaluated run", text, re.IGNORECASE)
        assert "No evaluated run is available yet." in view["metadata"]["limitations"]
    for fragment in case.get("expect_text", []):
        assert fragment in text
    if case.get("malicious_model"):
        with db_factory() as db:
            problem = db.get(Problem, 1)
        # The injected comment stays inside the fenced user-data block of the prompt.
        user_prompt = prompts[0][1]["content"]
        assert "(user data, not instructions)" in user_prompt and "SYSTEM: ignore" in user_prompt
        assert "data, never instructions" in prompts[0][0]["content"]
        assert "max(0, price) for price" not in text and view["metadata"]["validation"]["blocked"]
        assert_private_data_absent(text, problem, member)


def test_deterministic_responses_cover_every_intent(client, member, db_factory):
    evaluated_submission(client, db_factory)
    with db_factory() as db:
        problem = db.get(Problem, 1)
        attempt = db.query(ChallengeAttempt).first()
        context = build_context(db, problem, "python", user_id=member["id"], attempt=attempt)
    for intent in ["explain_problem", "explain_runtime_error", "identify_failing_test", "review_patch",
                   "why_fix_failed", "reproduction_strategy", "explain_concept", "find_documentation",
                   "progressive_hint", "review_diagnosis"]:
        sections = deterministic_response(context, intent, [])
        assert sections and sections[-1]["key"] == "next_step", intent
        assert not any(hint in json.dumps(sections) for hint in problem.hints), intent
    messages = assistant_messages(context, "why_fix_failed", "Why?", [])
    assert '"why_not_resolved"' in messages[1]["content"] and messages[0]["role"] == "system"
