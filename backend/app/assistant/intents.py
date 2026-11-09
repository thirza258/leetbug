"""Deterministic debugging-intent classification (PRD 8.4, AR-004).

The intent decides which context sections the assistant uses, how retrieval is focused, and which
assessment policies allow the request. Classification is rule-based so it is fast, explainable and
identical with or without a model provider.
"""
import re

INTENT_LABELS = {
    "explain_problem": "Explain the problem",
    "explain_runtime_error": "Explain a runtime error",
    "identify_failing_test": "Identify a failing test",
    "review_patch": "Review my patch",
    "why_fix_failed": "Why did my fix fail?",
    "reproduction_strategy": "Suggest a reproduction strategy",
    "explain_concept": "Explain a programming concept",
    "find_documentation": "Find relevant documentation",
    "progressive_hint": "Provide a progressive hint",
    "review_diagnosis": "Review my diagnosis",
}

# More specific intents win ties.
PRIORITY = ["review_diagnosis", "why_fix_failed", "explain_runtime_error", "identify_failing_test", "review_patch",
            "reproduction_strategy", "progressive_hint", "find_documentation", "explain_concept", "explain_problem"]

_CUES = [
    ("why_fix_failed", 3, "why-still-fails",
     r"\bwhy\b.{0,60}\b(still|fail|fails|failing|failed|wrong|broken|not work|doesn'?t work|didn'?t work|not pass|doesn'?t pass)"),
    ("why_fix_failed", 2, "fix-not-working",
     r"\b(my|the|this) (fix|patch|change|changes|solution)\b.{0,40}\b(fail|fails|failed|wrong|not|doesn'?t|didn'?t|still)"),
    ("why_fix_failed", 2, "still-failing", r"\bstill (fail|fails|failing|wrong|broken|red)\b"),
    ("explain_runtime_error", 3, "error-term",
     r"\b(error|exception|traceback|stack ?trace|panic|panics|crash|crashes|crashed|segfault|segmentation|keyerror|"
     r"indexerror|typeerror|valueerror|zerodivisionerror|attributeerror|nullpointerexception|npe|undefined|"
     r"nil pointer|nil map|compile|compiler|compilation|syntax error|does not compile|doesn'?t compile)\b"),
    ("explain_runtime_error", 1, "what-does-mean", r"\bwhat does\b.{0,60}\bmean\b"),
    ("identify_failing_test", 3, "which-test", r"\bwhich (test|tests|case|cases|example|examples)\b"),
    ("identify_failing_test", 2, "failing-test", r"\b(failing|failed|broken) (test|tests|case|cases)\b"),
    ("identify_failing_test", 1, "hidden-tests", r"\bhidden (test|tests|case|cases|check|checks)\b"),
    ("review_patch", 3, "review-code",
     r"\b(review|check|look at|critique|assess)\b.{0,20}\b(my|this|the) (patch|fix|change|changes|code|diff|solution|approach)\b"),
    ("review_patch", 2, "is-fix-correct",
     r"\b(is|does|will) (my|this|the) (fix|patch|change|approach|solution|code) (correct|right|ok|okay|good|enough|work|safe)"),
    ("reproduction_strategy", 3, "reproduce", r"\b(reproduce|reproduction|repro|replicate|trigger|provoke)\b"),
    ("reproduction_strategy", 1, "minimal-input", r"\b(minimal (input|example|case)|test case for)\b"),
    ("explain_concept", 3, "concept-question",
     r"\b(what is|what are|what's|whats|how does|how do|difference between|meaning of|explain (the )?concept)\b"),
    ("find_documentation", 3, "documentation",
     r"\b(doc|docs|documentation|reference|manual|spec|specification|link|links|rfc|official)\b"),
    ("progressive_hint", 3, "hint",
     r"\b(hint|nudge|clue|stuck|tip|pointer|where (should|do|can) i (start|look|begin))\b"),
    ("review_diagnosis", 4, "diagnosis", r"\b(diagnosis|diagnose|root cause|root-cause|hypothesis|theory)\b"),
    ("explain_problem", 2, "problem-question",
     r"\b(problem|task|challenge|requirement|requirements|what should|expected behaviou?r|supposed to|what is asked)\b"),
    ("explain_problem", 1, "confused", r"\b(understand|confused|confusing|don'?t get|unclear)\b"),
]
CUES = [(intent, weight, name, re.compile(pattern, re.IGNORECASE)) for intent, weight, name, pattern in _CUES]

# Context sections each intent uses and the retrieval focus (PRD 8.4: "which context and retrieval
# strategy are relevant").
INTENT_PLAN = {
    "explain_problem": {"sections": ["problem", "requirements", "examples"], "focus": "problem"},
    "explain_runtime_error": {"sections": ["problem", "execution", "current_code", "diff"], "focus": "error"},
    "identify_failing_test": {"sections": ["problem", "requirements", "examples", "execution", "diff"],
                              "focus": "failure"},
    "review_patch": {"sections": ["problem", "requirements", "diff", "current_code", "execution", "diagnosis"],
                     "focus": "patch"},
    "why_fix_failed": {"sections": ["problem", "requirements", "original_code", "current_code", "diff", "execution",
                                    "diagnosis", "previous_hints"], "focus": "failure"},
    "reproduction_strategy": {"sections": ["problem", "requirements", "examples", "execution", "diagnosis"],
                              "focus": "reproduction"},
    "explain_concept": {"sections": ["problem"], "focus": "concept"},
    "find_documentation": {"sections": ["problem"], "focus": "concept"},
    "progressive_hint": {"sections": ["problem", "requirements", "execution", "current_code", "previous_hints"],
                         "focus": "hint"},
    "review_diagnosis": {"sections": ["problem", "requirements", "diagnosis", "execution", "diff"],
                         "focus": "diagnosis"},
}

GENERIC = re.compile(r"^\s*(help|help me|\?+|what now|now what|hmm+|ok(ay)?|please)\s*[.!?]*\s*$", re.IGNORECASE)


def classify_intent(question: str, *, has_failure: bool = False, has_error: bool = False) -> dict:
    """Return {"intent", "confidence", "cues", "scores"} for a free-text debugging request."""
    text = (question or "").strip()
    scores: dict[str, int] = {}
    cues: list[str] = []
    if text and not GENERIC.match(text):
        for intent, weight, name, pattern in CUES:
            if pattern.search(text):
                scores[intent] = scores.get(intent, 0) + weight
                cues.append(name)
    if not scores:
        # No recognisable cue: answer the most useful question for the user's current state.
        intent = "explain_runtime_error" if has_error else "why_fix_failed" if has_failure else "explain_problem"
        return {"intent": intent, "confidence": 0.3, "cues": ["context-default"], "scores": {}}
    best = max(scores.values())
    tied = [intent for intent in PRIORITY if scores.get(intent) == best]
    intent = tied[0]
    # An error question about a run that did not crash is really a "why does it fail" question.
    if intent == "explain_runtime_error" and has_failure and not has_error and scores.get("why_fix_failed"):
        intent = "why_fix_failed"
    confidence = round(min(0.95, 0.4 + 0.6 * best / max(1, sum(scores.values()))), 2)
    return {"intent": intent, "confidence": confidence, "cues": cues, "scores": scores}
