"""Deterministic diagnosis and explanation scoring (PRD 5.3, 5.2 Stage E; DR-004).

Each criterion yields a 0–1 score, a level and generic feedback. Feedback never names rubric
concepts, so it cannot reveal the root cause or the fix. The same input, rubric and evaluator
version always produce the same score.
"""
import re

from app import scoring, taxonomy
from app.diagnosis.rubric import CRITERIA, EXPLANATION_CRITERIA, method_words, observation_words
from app.diagnosis.text import (
    Text,
    coverage,
    has_invariant_shape,
    looks_like_gibberish,
    overlap_ratio,
    similarity,
    too_short,
    words,
)

EVALUATOR_VERSION = "deterministic-v1"
STRONG, PARTIAL = 0.75, 0.35

DIAGNOSIS_FIELDS = ("defect_category", "root_cause", "affected_component", "violated_invariant",
                    "proposed_correction", "reproduction_strategy")
EXPLANATION_FIELDS = ("why_failed", "why_works", "invariant_preserved", "side_effects", "additional_tests")

FEEDBACK = {
    "defect_category": {
        "strong": "The defect category matches how this program fails.",
        "partial": "The category is related, but a more specific category describes this failure better.",
        "missing": "The category does not match this failure. Compare the observed behavior with each category's description.",
    },
    "root_cause": {
        "strong": "You explain why the code fails and point to where it happens.",
        "partial": "You are on the right track. Name the exact operation or condition that goes wrong, and where it is in the code.",
        "missing": "Explain why the code fails, not only what the symptom is. Point to the operation that breaks the expected behavior.",
    },
    "invariant": {
        "strong": "You state the rule the program must always keep, and how it is broken.",
        "partial": "State the rule more precisely: what must always (or never) be true of the result or state?",
        "missing": "Describe the condition that should always hold for correct behavior, for example a bound, a uniqueness rule, or a conservation rule.",
    },
    "correction": {
        "strong": "Your proposed correction addresses the cause rather than the symptom.",
        "partial": "Your correction is plausible. Make it more specific about what changes and why it removes the cause.",
        "missing": "Describe, at a high level, the change that would remove the cause. Avoid fixes that only hide the symptom.",
    },
    "reproduction": {
        "strong": "Your reproduction names concrete inputs and what you would observe.",
        "partial": "Make the reproduction concrete: which input or sequence triggers the failure, and what result do you expect versus observe?",
        "missing": "Describe how you would trigger the failure on purpose: the input, the steps, and the observation that confirms it.",
    },
    "why_failed": {
        "strong": "You explain clearly why the original implementation failed.",
        "partial": "Connect the original failure to its cause more explicitly.",
        "missing": "Explain the mechanism that made the original implementation fail.",
    },
    "why_works": {
        "strong": "You explain why the new implementation is correct.",
        "partial": "Say more precisely why the change removes the cause, not only that the tests pass.",
        "missing": "Explain why your change works, beyond the tests passing.",
    },
    "side_effects": {
        "strong": "You considered the change's side effects and risks.",
        "partial": "Name a concrete risk your change could introduce, or explain why there is none.",
        "missing": "Consider whether the change could affect other behavior, performance, or compatibility.",
    },
    "additional_tests": {
        "strong": "You propose several concrete regression tests.",
        "partial": "Propose more, or more concrete, tests: name the input and the expected result for each.",
        "missing": "Propose tests that would catch this defect if it came back.",
    },
}
FEEDBACK["invariant_explanation"] = {
    "strong": "You name the rule your fix now preserves.",
    "partial": "State the preserved rule more precisely: what is now always (or never) true?",
    "missing": "Name the condition your fix guarantees from now on.",
}

NOTE_TEXT = {
    "too_short": "Some answers are too short to evaluate. Use full sentences.",
    "unreadable": "Some answers could not be read as explanations.",
    "restates_symptom": "The root cause mostly restates the problem description. Explain why it happens.",
    "duplicate_fields": "Several fields repeat the same text. Each field asks a different question.",
}
ACTION_WORDS = ("add", "check", "validate", "guard", "lock", "move", "wrap", "replace", "clamp", "use", "initialize",
                "reset", "reject", "ensure", "change", "store", "track", "compare", "convert", "release", "invalidate",
                "skip", "return", "handle", "normalize", "copy", "sort", "round", "widen", "cast", "limit", "retry")
RISK_WORDS = ("regression", "performance", "side effect", "compatib", "behavior", "behaviour", "contention", "latency",
              "memory", "slower", "callers", "edge case", "breaking", "risk", "throughput", "deadlock", "none because",
              "no other", "only affects", "unchanged", "migration", "existing")


def level(score: float) -> str:
    return "strong" if score >= STRONG else "partial" if score >= PARTIAL else "missing"


def _criterion(name: str, score: float, feedback_key: str | None = None) -> dict:
    score = round(max(0.0, min(1.0, score)), 4)
    grade = level(score)
    return {"score": score, "level": grade, "feedback": FEEDBACK[feedback_key or name][grade]}


def _component_score(texts: list[Text], rubric: dict, starter_identifiers: set[str]) -> float:
    terms = [term for term in rubric.get("component", []) if term]
    for text in texts:
        for term in terms:
            lowered = term.lower()
            if lowered in text.identifiers or text.has_phrase(" ".join(words(term))):
                return 1.0
    mentioned = set().union(*(text.identifiers for text in texts)) if texts else set()
    generic = {"solve", "data", "return", "the", "code", "function"}
    if (mentioned & starter_identifiers) - generic:
        return 0.5
    return 0.0


def _starter_identifiers(problem) -> set[str]:
    found: set[str] = set()
    for source in (problem.starters or {}).values():
        found.update(item.lower() for item in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", source))
    return found


def _mechanism_groups(problem, rubric: dict) -> list[list[str]]:
    """Concepts that describe how the failure happens: the fix vocabulary and the category's cause.

    Groups that only name the symptom's subject (words from the problem statement or the affected
    component) are excluded, so restating "the total goes negative" does not count as a mechanism.
    """
    from app.diagnosis.rubric import CATEGORY_VOCABULARY
    symptom = Text(f"{problem.summary} {problem.description} {' '.join(rubric.get('component', []))}")
    groups = [group for group in rubric.get("correction", []) if not symptom.matches_group(group)]
    category = (rubric.get("defect_categories") or [None])[0]
    if category in CATEGORY_VOCABULARY:
        groups.append(CATEGORY_VOCABULARY[category]["cause"])
    return groups


def _structural(fields: dict, names: tuple[str, ...]) -> tuple[dict[str, str], list[str]]:
    """Per-field problems (too short / unreadable) and overall notes."""
    issues: dict[str, str] = {}
    for name in names:
        raw = fields.get(name) or ""
        if looks_like_gibberish(raw):
            issues[name] = "unreadable"
        elif too_short(raw):
            issues[name] = "too_short"
    notes = sorted({value for value in issues.values()})
    return issues, notes


def _cap(score: float, issue: str | None) -> float:
    if issue == "unreadable":
        return 0.0
    if issue == "too_short":
        return min(score, 0.25)
    return score


def category_score(selected: str, rubric: dict) -> float:
    accepted = rubric.get("defect_categories") or []
    if not selected or selected not in taxonomy.BUG_CATEGORIES:
        return 0.0
    if accepted and selected == accepted[0]:
        return 1.0
    if selected in accepted:
        return 0.8
    if selected in (rubric.get("related_categories") or []):
        return 0.4
    # "Logic error" is never wrong, only unspecific.
    if selected == "logic_error":
        return 0.25
    return 0.0


def reproduction_score(text: Text, groups: list[list[str]]) -> tuple[float, dict]:
    concrete, matched = coverage(text, groups, 0.34) if groups else (0.0, [])
    method = 1.0 if text.matches_group(list(method_words())) else 0.0
    observation = 1.0 if text.matches_group(list(observation_words())) else 0.0
    has_value = 1.0 if re.search(r"\d|\[|\{|\"", text.raw) else 0.0
    specificity = max(concrete, 0.6 * has_value)
    return 0.5 * specificity + 0.25 * method + 0.25 * observation, {
        "matched_groups": matched, "groups": len(groups), "method": bool(method), "observation": bool(observation)}


def score_diagnosis(problem, fields: dict, rubric: dict) -> dict:
    """Score a structured diagnosis. Returns score (0–100), criteria, notes and private evidence."""
    texts = {name: Text(str(fields.get(name) or "")) for name in DIAGNOSIS_FIELDS}
    issues, notes = _structural(fields, DIAGNOSIS_FIELDS[1:])
    starter_ids = _starter_identifiers(problem)
    evidence: dict = {}

    defect = category_score(str(fields.get("defect_category") or ""), rubric)

    cause_text = Text(f"{texts['root_cause'].raw}\n{texts['affected_component'].raw}")
    concept, matched = coverage(cause_text, rubric.get("root_cause", []), 0.34)
    mechanism = 1.0 if any(texts["root_cause"].matches_group(group) for group in _mechanism_groups(problem, rubric)) else 0.0
    component = _component_score([texts["affected_component"], texts["root_cause"]], rubric, starter_ids)
    root = 0.7 * (0.6 * concept + 0.4 * mechanism) + 0.3 * component
    summary = Text(f"{problem.summary} {problem.description}")
    if len(texts["root_cause"].content_stems()) >= 5 and overlap_ratio(texts["root_cause"], summary) >= 0.8:
        root *= 0.5
        notes.append("restates_symptom")
    root = _cap(root, issues.get("root_cause"))
    if issues.get("affected_component") and issues.get("root_cause"):
        root = min(root, 0.2)
    evidence["root_cause"] = {"matched_groups": matched, "groups": len(rubric.get("root_cause", [])),
                              "mechanism": bool(mechanism), "component": component}

    invariant_cov, matched = coverage(texts["violated_invariant"], rubric.get("invariant", []), 0.5)
    shape = 1.0 if has_invariant_shape(texts["violated_invariant"]) else 0.0
    invariant = _cap(0.8 * invariant_cov + 0.2 * shape, issues.get("violated_invariant"))
    evidence["invariant"] = {"matched_groups": matched, "groups": len(rubric.get("invariant", [])), "shape": bool(shape)}

    correction_cov, matched = coverage(texts["proposed_correction"], rubric.get("correction", []), 0.3)
    action = 1.0 if texts["proposed_correction"].matches_group(list(ACTION_WORDS)) else 0.0
    correction = 0.85 * correction_cov + 0.15 * action
    if similarity(texts["proposed_correction"].raw, texts["root_cause"].raw) >= 0.9 and len(texts["root_cause"].raw) >= 20:
        correction *= 0.5
        notes.append("duplicate_fields")
    correction = _cap(correction, issues.get("proposed_correction"))
    evidence["correction"] = {"matched_groups": matched, "groups": len(rubric.get("correction", [])), "action": bool(action)}

    reproduction, detail = reproduction_score(texts["reproduction_strategy"], rubric.get("reproduction", []))
    reproduction = _cap(reproduction, issues.get("reproduction_strategy"))
    evidence["reproduction"] = detail

    values = {"defect_category": defect, "root_cause": root, "invariant": invariant, "correction": correction,
              "reproduction": reproduction}
    criteria = {name: _criterion(name, values[name]) for name in CRITERIA}
    weights = scoring.diagnosis_weights(problem, rubric)
    total = scoring.weighted({name: criteria[name]["score"] * 100 for name in CRITERIA}, weights, missing="zero")
    return {"score": total, "criteria": criteria, "weights": weights, "notes": sorted(set(notes)),
            "evidence": evidence, "rubric_source": rubric.get("source", "derived"),
            "rubric_version": rubric.get("version", 1), "evaluator_version": EVALUATOR_VERSION,
            "passed": (total or 0) >= scoring.DIAGNOSIS_PASS_THRESHOLD}


def _test_ideas(raw: str) -> list[str]:
    parts = re.split(r"\n+|;|(?:^|\s)(?:\d+[.)]|[-*•])\s+", raw or "")
    ideas = [part.strip() for part in parts if part and len(words(part)) >= 3]
    if len(ideas) <= 1:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", raw or "") if len(words(part)) >= 3]
        ideas = sentences if len(sentences) > len(ideas) else ideas
    return ideas


def score_explanation(problem, fields: dict, rubric: dict) -> dict:
    """Score a post-solution explanation (Stage E)."""
    texts = {name: Text(str(fields.get(name) or "")) for name in EXPLANATION_FIELDS}
    issues, notes = _structural({key: value for key, value in fields.items() if key != "side_effects"},
                                ("why_failed", "why_works", "invariant_preserved", "additional_tests"))
    explanation = rubric.get("explanation") or {}
    starter_ids = _starter_identifiers(problem)
    evidence: dict = {}

    failed_groups = explanation.get("why_failed") or rubric.get("root_cause", [])
    failed_cov, matched = coverage(texts["why_failed"], failed_groups, 0.34)
    component = _component_score([texts["why_failed"]], rubric, starter_ids)
    why_failed = _cap(0.8 * failed_cov + 0.2 * component, issues.get("why_failed"))
    evidence["why_failed"] = {"matched_groups": matched, "groups": len(failed_groups)}

    works_groups = explanation.get("why_works") or rubric.get("correction", [])
    works_cov, matched = coverage(texts["why_works"], works_groups, 0.34)
    why_works = _cap(works_cov, issues.get("why_works"))
    evidence["why_works"] = {"matched_groups": matched, "groups": len(works_groups)}

    invariant_groups = explanation.get("invariant") or rubric.get("invariant", [])
    invariant_cov, matched = coverage(texts["invariant_preserved"], invariant_groups, 0.5)
    shape = 1.0 if has_invariant_shape(texts["invariant_preserved"]) else 0.0
    invariant = _cap(0.8 * invariant_cov + 0.2 * shape, issues.get("invariant_preserved"))
    evidence["invariant"] = {"matched_groups": matched, "groups": len(invariant_groups)}

    side_raw = (fields.get("side_effects") or "").strip()
    if not side_raw or looks_like_gibberish(side_raw):
        side_effects = 0.0
    elif texts["side_effects"].matches_group(list(RISK_WORDS)) and not too_short(side_raw, min_chars=15):
        side_effects = 1.0
    else:
        side_effects = 0.5 if not too_short(side_raw, min_chars=10, min_words=2) else 0.25

    ideas = _test_ideas(fields.get("additional_tests") or "")
    count = {0: 0.0, 1: 0.45, 2: 0.75}.get(len(ideas), 1.0)
    concrete = sum(1 for idea in ideas if re.search(r"\d|\[|\{|\"", idea)
                   or Text(idea).matches_group([phrase for group in rubric.get("reproduction", []) for phrase in group] or ["input"]))
    tests = count * (0.6 + 0.4 * (concrete / len(ideas) if ideas else 0))
    tests = _cap(tests, issues.get("additional_tests"))
    evidence["additional_tests"] = {"ideas": len(ideas), "concrete": concrete}

    values = {"why_failed": why_failed, "why_works": why_works, "invariant": invariant,
              "side_effects": side_effects, "additional_tests": tests}
    criteria = {name: _criterion(name, values[name], "invariant_explanation" if name == "invariant" else None)
                for name in EXPLANATION_CRITERIA}
    weights = dict(scoring.EXPLANATION_WEIGHTS)
    total = scoring.weighted({name: criteria[name]["score"] * 100 for name in EXPLANATION_CRITERIA}, weights,
                             missing="zero")
    return {"score": total, "criteria": criteria, "weights": weights, "notes": notes, "evidence": evidence,
            "rubric_source": rubric.get("source", "derived"), "rubric_version": rubric.get("version", 1),
            "evaluator_version": EVALUATOR_VERSION}


def feedback_for(name: str, score: float) -> str:
    return FEEDBACK[name][level(score)]


def note_text(code: str) -> str:
    return NOTE_TEXT.get(code, "")
