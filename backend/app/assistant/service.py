"""Context-aware debugging assistant and adaptive hints (PRD §8; AR-001..AR-011).

``create_interaction`` validates a request (ownership, assessment policy) and stores a queued
``AIInteraction``; the worker then calls ``respond``. ``generate_adaptive_hint`` is the hint worker's
generator. Both degrade to deterministic, context-derived answers when no model is configured or the
provider fails, so manual debugging never depends on AI availability.
"""
import logging
import re
import time

from fastapi import HTTPException
from sqlalchemy import select

from app import attempts, policy
from app.assistant.context import CONTEXT_VERSION, build_context, context_summary
from app.assistant.generation import ModelResponseError, model_hint, model_sections
from app.assistant.intents import INTENT_LABELS, INTENT_PLAN, classify_intent
from app.assistant.responder import TITLES, deterministic_response
from app.assistant.retrieval import adaptive_retrieve
from app.assistant.validation import validate_sections, validate_text
from app.config import settings
from app.events import record_event
from app.llm import AIUnavailable
from app.models import AIInteraction, ChallengeAttempt, Problem, Submission, now
from app.scoring import TERMINAL

log = logging.getLogger(__name__)
HINT_FOCUS = {1: "conceptual", 2: "investigation", 3: "diagnostic"}
REPETITION_THRESHOLD = 0.6


def _submission_for(db, user, problem, submission_id: str | None) -> Submission | None:
    if not submission_id:
        return None
    submission = db.get(Submission, submission_id)
    if submission is None or submission.user_id != user.id or submission.problem_id != problem.id:
        raise HTTPException(404, "Submission not found.")
    return submission


def _failure_flags(db, attempt: ChallengeAttempt, submission: Submission | None) -> tuple[bool, bool]:
    row = submission or db.scalar(select(Submission).where(Submission.attempt_id == attempt.id,
                                                          Submission.status.in_(TERMINAL))
                                  .order_by(Submission.created_at.desc()).limit(1))
    if row is None:
        return False, False
    return row.status != "passed", row.status == "runtime_error"


def create_interaction(db, user, problem: Problem, *, language: str, question: str = "", code: str | None = None,
                       submission_id: str | None = None, assessment_session_id: str | None = None,
                       incident_session_id: str | None = None, intent: str | None = None) -> AIInteraction:
    """Validate and queue an assistant request. Flushes; the caller commits and enqueues."""
    if language not in problem.starters:
        raise HTTPException(422, "Choose a supported language.")
    context = attempts.resolve_context(db, user, problem, assessment_session_id=assessment_session_id,
                                       incident_session_id=incident_session_id)
    submission = _submission_for(db, user, problem, submission_id)
    assistance = policy.assistance_for(db, user, problem, context.assessment_session)
    classification = None
    if intent is None:
        has_failure, has_error = _failure_flags(db, context.attempt, submission)
        classification = classify_intent(question, has_failure=has_failure, has_error=has_error)
        intent = classification["intent"]
    policy.ensure_ai_allowed(assistance, intent)
    if intent == "progressive_hint" and policy.hint_level_cap(assistance) == 0:
        raise HTTPException(403, "Hints are disabled for this assessment.")
    interaction = AIInteraction(
        user_id=user.id, problem_id=problem.id, attempt_id=context.attempt.id,
        assessment_session_id=context.assessment_session.id if context.assessment_session else None,
        intent=intent, question=(question or "").strip(), status="queued", context_version=CONTEXT_VERSION,
        payload={"language": language, "code": code, "submission_id": submission.id if submission else None,
                 "assistance": assistance.as_dict(),
                 "incident_session_id": context.incident_session.id if context.incident_session else None},
        response_metadata={"intent_confidence": classification["confidence"] if classification else 1.0,
                           "intent_cues": classification["cues"] if classification else ["explicit"]},
    )
    db.add(interaction)
    db.flush()
    record_event(db, "ai.requested", user_id=user.id, problem_id=problem.id, attempt_id=context.attempt.id,
                 assessment_session_id=interaction.assessment_session_id,
                 incident_session_id=context.incident_session.id if context.incident_session else None,
                 intent=intent, interaction_id=interaction.id)
    return interaction


def _render_text(sections: list[dict]) -> str:
    return "\n\n".join(f"{section['title']}\n{section['body']}" for section in sections)


def respond(db, interaction: AIInteraction) -> None:
    """Build context, retrieve, generate (model or deterministic), validate and store the answer."""
    started = time.perf_counter()
    problem = db.get(Problem, interaction.problem_id)
    payload = interaction.payload or {}
    language = payload.get("language") if payload.get("language") in problem.starters else next(iter(problem.starters))
    attempt = db.get(ChallengeAttempt, interaction.attempt_id) if interaction.attempt_id else None
    submission = db.get(Submission, payload["submission_id"]) if payload.get("submission_id") else None
    context = build_context(db, problem, language, user_id=interaction.user_id, attempt=attempt,
                            code=payload.get("code"), submission=submission,
                            assessment_session_id=interaction.assessment_session_id)
    intent = interaction.intent if interaction.intent in INTENT_PLAN else "why_fix_failed"
    previous_urls = {url for row in context["previous_hints"] for url in row["sources"]}
    retrieval_started = time.perf_counter()
    docs, retrieval = adaptive_retrieve(context, intent, interaction.question, previous_urls=previous_urls)
    interaction.retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
    allowed = (payload.get("assistance") or {}).get("ai", "enabled")
    generation_started = time.perf_counter()
    generation, tokens, model_error = "deterministic", None, None
    deterministic = deterministic_response(context, intent, docs)
    sections = deterministic
    if settings.ai_enabled and allowed != "disabled":
        try:
            sections, tokens = model_sections(context, intent, interaction.question, docs)
            generation = "model"
        except (AIUnavailable, ModelResponseError) as exc:
            generation, model_error = "model-fallback", str(exc)[:200]
            sections = deterministic
    interaction.generation_ms = round((time.perf_counter() - generation_started) * 1000, 2)
    sections, flags = validate_sections(sections, problem=problem, context=context, sources=docs)
    if generation == "model":
        # A section the validator emptied (for example code that resembled the reference solution) is
        # replaced by its deterministic counterpart so the user still gets an answer.
        present = {section["key"] for section in sections}
        backfill = [section for section in deterministic if section["key"] not in present]
        if backfill:
            extra, _ = validate_sections(backfill, problem=problem, context=context, sources=docs)
            order = {section["key"]: index for index, section in enumerate(deterministic)}
            sections = sorted(sections + extra, key=lambda section: order.get(section["key"], 99))
            flags["deterministic_backfill"] = [section["key"] for section in extra]
    limitations = []
    if context["execution"] is None:
        limitations.append("No evaluated run is available yet.")
    elif not context["execution"].get("matches_current_code", True):
        limitations.append("The latest evaluated run used different code than the code you sent.")
    if context["execution"] and not context["execution"]["hidden_evaluated"]:
        limitations.append("Hidden cases have not been evaluated for this run.")
    if not docs:
        limitations.append("No matching official documentation was retrieved.")
    interaction.response = {"intent": intent, "label": INTENT_LABELS[intent], "sections": sections,
                            "generation": generation}
    interaction.response_text = _render_text(sections)
    interaction.sources = [{"title": doc["title"], "url": doc["url"], "excerpt": doc["text"],
                            "language": doc["language"], "score": doc["score"]} for doc in docs]
    interaction.retrieval_metadata = retrieval
    interaction.context_summary = context_summary(context, INTENT_PLAN[intent]["sections"])
    interaction.response_metadata = {
        **(interaction.response_metadata or {}), "generation": generation,
        "model": settings.ai_model if generation == "model" else None, "model_error": model_error,
        "validation": flags, "grounding_score": flags["grounding_score"], "limitations": limitations,
        "assistance": payload.get("assistance"),
    }
    interaction.token_usage = tokens
    interaction.latency_ms = round((time.perf_counter() - started) * 1000, 2)
    record_event(db, "ai.completed", user_id=interaction.user_id, problem_id=interaction.problem_id,
                 attempt_id=interaction.attempt_id, assessment_session_id=interaction.assessment_session_id,
                 intent=intent, generation=generation, latency_ms=interaction.latency_ms,
                 retrieval_ms=interaction.retrieval_ms, generation_ms=interaction.generation_ms,
                 grounding_score=flags["grounding_score"], blocked=flags["blocked"])


def interaction_view(row: AIInteraction) -> dict:
    metadata = row.response_metadata or {}
    retrieval = row.retrieval_metadata or {}
    return {
        "id": row.id, "problem_id": row.problem_id, "attempt_id": row.attempt_id,
        "assessment_session_id": row.assessment_session_id, "intent": row.intent,
        "intent_label": INTENT_LABELS.get(row.intent, row.intent), "question": row.question, "status": row.status,
        "context_version": row.context_version, "context": row.context_summary or {}, "response": row.response,
        "response_text": row.response_text, "sources": row.sources or [],
        "retrieval": {key: retrieval.get(key) for key in ("method", "selected", "topics", "latency_ms")},
        "metadata": {key: metadata.get(key) for key in ("generation", "model", "grounding_score", "limitations",
                                                         "validation", "intent_confidence")},
        "token_usage": row.token_usage, "latency_ms": row.latency_ms, "retrieval_ms": row.retrieval_ms,
        "generation_ms": row.generation_ms, "error": row.error, "created_at": row.created_at,
        "completed_at": row.completed_at,
    }


# ── Adaptive hints (AR-007, PRD 8.7) ─────────────────────────────────────────────────────


def _content_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z][a-z0-9_]{2,}", (text or "").lower())
            if word not in {"the", "and", "that", "this", "with", "your", "you", "for", "are", "from"}}


def similarity(a: str, b: str) -> float:
    left, right = _content_words(a), _content_words(b)
    return len(left & right) / len(left | right) if left and right else 0.0


def personalize(curated: str, context: dict) -> str:
    """Deterministic adaptive hint: the curated hint for this level, anchored to the user's latest run."""
    execution = context.get("execution")
    if execution is None or execution["failure_type"] == "none":
        return curated
    if execution["failing_public"]:
        prefix = f"Your latest run still fails \"{execution['failing_public'][0]['name']}\"."
    elif execution["failure_type"] in {"runtime_error", "compile_error"}:
        prefix = "Your latest run stops with an error before returning a result."
    elif execution["hidden_failed"]:
        prefix = "Your latest run passes the visible examples but not every hidden case."
    else:
        prefix = "Your latest run is still not accepted."
    return f"{prefix} {curated}"


def generate_adaptive_hint(db, hint, *, base):
    """Context-aware progressive hint. ``base`` (the documentation hint) is the non-adaptive fallback."""
    problem = db.get(Problem, hint.problem_id)
    try:
        attempt = db.get(ChallengeAttempt, hint.attempt_id) if hint.attempt_id else None
        context = build_context(db, problem, hint.language, user_id=hint.user_id, attempt=attempt,
                                code=(hint.context or {}).get("code"),
                                assessment_session_id=hint.assessment_session_id, exclude_hint_id=hint.id)
        previous_urls = {url for row in context["previous_hints"] for url in row["sources"]}
        docs, retrieval = adaptive_retrieve(context, "progressive_hint", previous_urls=previous_urls)
    except Exception:
        log.warning("Adaptive hint context unavailable; using the documentation hint", exc_info=True)
        return base(problem, hint.language, hint.level)
    curated = problem.hints[min(hint.level - 1, len(problem.hints) - 1)]
    generation, text, tokens, repetition_avoided = "deterministic", None, None, False
    if settings.ai_enabled:
        try:
            text, tokens = model_hint(context, hint.level, curated, docs)
            generation = "model"
        except AIUnavailable:
            generation = "model-fallback"
    flags = {}
    if text:
        text, flags = validate_text(text, problem=problem, context=context, sources=docs)
        if flags["blocked"] or len(text) < 20:
            text, generation = None, "model-rejected"
        elif any(similarity(text, row["text"]) >= REPETITION_THRESHOLD for row in context["previous_hints"]):
            text, repetition_avoided = None, True
    if not text:
        # Curated hints are reviewed, level-appropriate content; only the run summary is added.
        text = personalize(curated, context)
    hint.context = {**(hint.context or {}), "adaptive": {
        "context_version": CONTEXT_VERSION, "level_focus": HINT_FOCUS.get(hint.level, "diagnostic"),
        "generation": generation, "tokens": tokens, "previous_hints": len(context["previous_hints"]),
        "repetition_avoided": repetition_avoided, "validation": flags,
        "failure_type": (context["execution"] or {}).get("failure_type"),
        "retrieval": {key: retrieval[key] for key in ("method", "selected", "topics", "latency_ms")},
    }}
    label = retrieval["method"] + "+adaptive" + ("+model-fallback" if generation == "model-fallback" else "")
    return {"text": text, "sources": [{"title": doc["title"], "url": doc["url"], "excerpt": doc["text"]}
                                      for doc in docs], "retrieval": label[:40]}


def mark_failed(interaction: AIInteraction, message: str) -> None:
    interaction.status, interaction.error = "error", message
    interaction.payload = None
    interaction.completed_at = now()


__all__ = ["create_interaction", "respond", "interaction_view", "generate_adaptive_hint", "TITLES"]
