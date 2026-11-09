"""Incident resolution scoring (PRD 6.6).

Six dimensions, weighted by ``scoring.INCIDENT_WEIGHTS`` unless the incident's
``evaluation_config["weights"]`` overrides them:

- root_cause: the diagnosis score for the session's attempt.
- investigation: diagnosis reproduction quality, artifact-type coverage, and whether a
  reproduction ran before the resolution was filed.
- fix: the attempt's patch correctness (hidden tests included).
- regression: the user's own regression tests — valid on the reference solution and failing on
  the original defect.
- remediation: operational remediation and prevention concepts covered.
- communication: impact assessment concepts and structure, plus the fix explanation when given.

Every score is deterministic for the same evidence and evaluation configuration.
"""
import math
import re

from sqlalchemy import select

from app import scoring
from app.models import Diagnosis, FixExplanation, Submission

SCORING_VERSION = "incident-scoring-v1"
COVERAGE_TARGET = 0.6  # Share of concept groups that earns full credit for a free-text section.
REGRESSION_FULL_MARKS_AT = 3
VALID_NOT_DETECTING_CREDIT = 0.3
PREVENTION_THRESHOLD = 60.0
SUFFIXES = ("ations", "ation", "ingly", "ings", "ing", "ency", "ence", "ents", "ent", "ions", "ion",
            "ers", "er", "ed", "es", "ly", "s")
QUANTITY = re.compile(r"\d|percent|%|\b(?:all|every|some|most|many|few|half|twice|double)\b")
IMPACT_WORDS = re.compile(r"\b(?:customer|customers|user|users|client|clients|revenue|support|ticket|tickets|order|"
                          r"orders|charge|charges|payment|payments|request|requests|latency|availability|data)\b")


def normalize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def stem(token: str) -> str:
    """A small suffix stripper so "retried", "retries" and "retry" (or "charged"/"charge") match."""
    if len(token) <= 4:
        return token
    if token.endswith(("ies", "ied")) and len(token) > 5:
        return token[:-3] + "y"
    for suffix in SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            token = token[:-len(suffix)]
            break
    return token[:-1] if token.endswith("e") and len(token) > 4 else token


def _contains(tokens: list[str], phrase: str) -> bool:
    words = [stem(word) for word in normalize(phrase)]
    if not words:
        return False
    stems = [stem(token) for token in tokens]
    width = len(words)
    return any(stems[index:index + width] == words for index in range(len(stems) - width + 1))


def coverage(text: str, groups: list[list[str]]) -> tuple[int, int, list[int]]:
    """How many synonym groups ``text`` mentions. Returns (matched, total, matched group indexes)."""
    tokens = normalize(text)
    matched = [index for index, group in enumerate(groups or []) if any(_contains(tokens, term) for term in group)]
    return len(matched), len(groups or []), matched


def saturated(matched: int, total: int, target: float = COVERAGE_TARGET) -> float:
    if total <= 0:
        return 0.0
    return min(1.0, matched / max(1, math.ceil(total * target)))


def regression_score(results: list[dict]) -> tuple[float, list[float]]:
    """0–100. Valid tests that fail on the original defect earn full credit; the best three count."""
    credits = []
    for row in results:
        if not row.get("valid"):
            credits.append(0.0)
        elif row.get("detects_bug"):
            credits.append(1.0)
        else:
            credits.append(VALID_NOT_DETECTING_CREDIT)
    if not credits:
        return 0.0, []
    counted = sorted(credits, reverse=True)[:REGRESSION_FULL_MARKS_AT]
    return round(sum(counted) / max(1, len(counted)) * 100, 2), credits


def artifact_coverage(incident, investigation: dict) -> tuple[float, dict]:
    types = {artifact.get("type") for artifact in incident.artifacts or []}
    by_id = {artifact.get("id"): artifact.get("type") for artifact in incident.artifacts or []}
    viewed = {by_id[artifact_id] for artifact_id in (investigation or {}).get("viewed", {}) if artifact_id in by_id}
    share = len(viewed) / len(types) if types else 0.0
    return round(share, 4), {"viewed_types": sorted(viewed), "available_types": sorted(types)}


def _ran_reproduction(db, attempt_id: str, before) -> bool:
    rows = db.scalars(select(Submission.created_at).where(
        Submission.attempt_id == attempt_id, Submission.kind == "run", Submission.status.in_(scoring.TERMINAL)))
    cutoff = scoring._utc(before)
    return any(scoring._utc(created) <= cutoff for created in rows)


def communication_score(resolution, concepts: dict, explanation: FixExplanation | None) -> tuple[float, dict]:
    text = resolution.impact_assessment or ""
    matched, total, _ = coverage(text, concepts.get("impact_concepts", []))
    sentences = [part for part in re.split(r"[.!?\n]+", text) if len(part.strip()) > 12]
    lowered = text.lower()
    structure = (0.35 * (len(text.strip()) >= 80) + 0.25 * (len(sentences) >= 2)
                 + 0.2 * bool(QUANTITY.search(lowered)) + 0.2 * bool(IMPACT_WORDS.search(lowered)))
    parts = {"impact_concepts": saturated(matched, total) * 100, "structure": structure * 100,
             "explanation": explanation.score if explanation is not None and explanation.score is not None else None}
    value = scoring.weighted(parts, {"impact_concepts": 50, "structure": 30, "explanation": 20}) or 0.0
    return value, {"impact_concepts_matched": matched, "impact_concepts_total": total,
                   "structure": round(structure, 2), "explanation_score": parts["explanation"]}


def remediation_score(resolution, concepts: dict) -> tuple[float, dict, float]:
    remediation, prevention = resolution.remediation or "", resolution.prevention or ""
    combined = f"{remediation}\n{prevention}"
    rem_matched, rem_total, _ = coverage(combined, concepts.get("remediation_concepts", []))
    pre_matched, pre_total, _ = coverage(combined, concepts.get("prevention_concepts", []))
    remediation_part = saturated(rem_matched, rem_total) if remediation.strip() else 0.0
    prevention_part = saturated(pre_matched, pre_total) if prevention.strip() else 0.0
    value = round((remediation_part * 0.5 + prevention_part * 0.5) * 100, 2)
    return value, {"remediation_concepts_matched": rem_matched, "remediation_concepts_total": rem_total,
                   "prevention_concepts_matched": pre_matched, "prevention_concepts_total": pre_total}, prevention_part


def score_resolution(db, resolution, session, incident, problem, attempt) -> dict:
    """Score a resolution from stored evidence. ``resolution.regression_results`` must be populated."""
    config = incident.evaluation_config or {}
    concepts = config.get("concepts") or {}
    weights = config.get("weights") or scoring.INCIDENT_WEIGHTS
    attempt_breakdown = scoring.refresh_attempt(db, attempt)
    diagnosis = db.get(Diagnosis, resolution.diagnosis_id) if resolution.diagnosis_id else None
    if diagnosis is None:
        diagnosis = db.scalar(select(Diagnosis).where(Diagnosis.attempt_id == attempt.id)
                              .order_by(Diagnosis.created_at.desc()).limit(1))
    explanation = db.scalar(select(FixExplanation).where(FixExplanation.attempt_id == attempt.id)
                            .order_by(FixExplanation.created_at.desc()).limit(1))
    coverage_share, coverage_detail = artifact_coverage(incident, session.investigation or {})
    reproduction = scoring.criterion(diagnosis, "reproduction")
    ran = _ran_reproduction(db, attempt.id, resolution.created_at)
    investigation = round((0.5 * (reproduction or 0.0) + 0.25 * coverage_share + 0.25 * ran) * 100, 2)
    regression, credits = regression_score(resolution.regression_results or [])
    remediation, remediation_detail, prevention_part = remediation_score(resolution, concepts)
    communication, communication_detail = communication_score(resolution, concepts, explanation)
    correctness = attempt_breakdown["components"].get("correctness")
    solved = bool(attempt_breakdown["evidence"].get("solved"))
    components = {
        "root_cause": diagnosis.score if diagnosis is not None and diagnosis.score is not None else 0.0,
        "investigation": investigation,
        "fix": correctness if correctness is not None else 0.0,
        "regression": regression,
        "remediation": remediation,
        "communication": communication,
    }
    total = scoring.weighted(components, weights, missing="zero")
    detecting = sum(1 for row in resolution.regression_results or [] if row.get("valid") and row.get("detects_bug"))
    return {
        "components": components, "total": total, "weights": dict(weights),
        # PRD 6.6: fixing the immediate defect is reported separately from preventing recurrence.
        "outcome": {
            "fixed_immediate_defect": solved,
            "prevented_recurrence": regression >= PREVENTION_THRESHOLD and prevention_part >= 0.5,
            "detecting_regression_tests": detecting,
        },
        "details": {
            "diagnosis_id": diagnosis.id if diagnosis is not None else None,
            "reproduction_criterion": reproduction, "artifact_coverage": coverage_share, **coverage_detail,
            "ran_reproduction_before_resolving": ran, "regression_credits": credits,
            **remediation_detail, **communication_detail,
            "attempt_components": attempt_breakdown["components"],
        },
        "versions": {"incident_scoring": SCORING_VERSION, "scoring": scoring.SCORING_VERSION,
                     "diagnosis_rubric": diagnosis.rubric_version if diagnosis is not None else None,
                     "diagnosis_evaluator": diagnosis.evaluator_version if diagnosis is not None else None,
                     "incident_version": incident.version},
    }
