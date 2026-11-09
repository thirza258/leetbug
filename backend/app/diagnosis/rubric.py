"""Diagnosis rubrics (PRD 5.3, DR-004, DR-009).

A rubric lists the concepts a strong diagnosis mentions. Authored and administrator rubrics are
stored on ``Problem.diagnosis_rubric``; every other problem gets a deterministic rubric derived
from its taxonomy, hints, explanation, requirements, public tests and the lines its reference fix
changes. Rubrics are private grading data and are never returned to non-administrators.

Format::

    {"version": int, "source": "authored" | "derived" | "admin",
     "defect_categories": [taxonomy id, ...],            # first is primary
     "related_categories": [taxonomy id, ...],           # partial credit
     "root_cause": [[synonym, ...], ...],                # concept groups
     "component": [identifier or term, ...],
     "invariant": [[...], ...], "correction": [[...], ...], "reproduction": [[...], ...],
     "weights": {criterion: weight}  (optional),
     "explanation": {"why_failed": [[...]], "why_works": [[...]], "invariant": [[...]]}  (optional)}
"""
import difflib
import json
import logging
import math
import re
from collections import Counter
from functools import lru_cache

from app import taxonomy
from app.diagnosis.text import GENERIC_WORDS, INVARIANT_SHAPE, STOP_WORDS, split_identifier, stem, words

log = logging.getLogger(__name__)

RUBRIC_FORMAT_VERSION = 1
CRITERIA = ("defect_category", "root_cause", "invariant", "correction", "reproduction")
EXPLANATION_CRITERIA = ("why_failed", "why_works", "invariant", "side_effects", "additional_tests")
GROUP_SECTIONS = ("root_cause", "invariant", "correction", "reproduction")
MAX_GROUPS = 40
MAX_PHRASE = 80

# Surface-word synonyms. Keys and values are matched through the same stemmer as user text.
SYNONYMS = {
    "lock": ["mutex", "synchronized", "critical section"],
    "mutex": ["lock", "synchronized"],
    "atomic": ["atomically", "single step", "together", "transaction"],
    "race": ["concurrent", "interleave", "simultaneous", "parallel"],
    "concurrent": ["race", "parallel", "simultaneous", "interleave"],
    "thread": ["concurrent", "parallel", "goroutine"],
    "negative": ["below zero", "less than zero", "minus"],
    "empty": ["no elements", "no items", "zero length", "nothing"],
    "overflow": ["wraparound", "wrap around", "too large", "exceeds"],
    "duplicate": ["twice", "repeated", "double", "more than once", "redelivery"],
    "retry": ["redelivery", "duplicate", "resend", "again"],
    "idempotency": ["idempotent", "deduplicate", "dedupe", "processed", "already seen"],
    "null": ["none", "nil", "missing", "undefined", "absent"],
    "none": ["null", "nil", "missing"],
    "nil": ["null", "none", "missing"],
    "missing": ["absent", "none", "null", "undefined", "not present"],
    "boundary": ["off by one", "edge", "limit", "last element", "first element"],
    "cache": ["cached", "stale", "memoize"],
    "stale": ["outdated", "old value", "cache"],
    "timezone": ["time zone", "utc", "offset", "local time"],
    "utc": ["timezone", "time zone", "offset"],
    "transaction": ["rollback", "commit", "atomic"],
    "rollback": ["roll back", "revert", "undo", "transaction"],
    "validate": ["validation", "check", "verify", "reject", "guard"],
    "clamp": ["max", "min", "bound", "cap"],
    "round": ["rounding", "precision"],
    "precision": ["rounding", "float", "decimal"],
    "float": ["floating point", "decimal", "precision", "double"],
    "integer": ["int", "long", "whole number"],
    "long": ["64-bit", "wider", "widen", "int64"],
    "order": ["ordering", "sequence", "sort"],
    "sort": ["order", "ordering", "sorted"],
    "parse": ["parsing", "decode", "deserialize"],
    "encode": ["encoding", "serialize", "unicode"],
    "permission": ["authorization", "role", "access"],
    "role": ["permission", "rbac", "authorization"],
    "expire": ["expiry", "expiration", "ttl", "deadline"],
    "deadline": ["timeout", "expire", "expiry"],
    "timeout": ["deadline", "time out", "timed out"],
    "release": ["close", "free", "cleanup"],
    "leak": ["not released", "never closed", "exhausted"],
    "initialize": ["init", "initial value", "start value", "default"],
    "mutable": ["shared", "alias", "same object", "reference"],
    "alias": ["shared reference", "same object", "copy"],
    "copy": ["clone", "new object"],
}

# Category vocabulary keeps derived rubrics anchored in the taxonomy even when hints are terse.
CATEGORY_VOCABULARY = {
    "race_condition": {"cause": ["race", "concurrent", "interleave", "simultaneous", "same time"],
                       "invariant": ["never negative", "consistent", "atomic"],
                       "correction": ["lock", "mutex", "atomic", "synchronized", "critical section"]},
    "deadlock": {"cause": ["deadlock", "wait forever", "circular wait", "blocked"],
                 "invariant": ["progress", "eventually", "terminate"],
                 "correction": ["lock order", "timeout", "buffered", "release"]},
    "retry_idempotency": {"cause": ["retry", "duplicate", "twice", "redelivery"],
                          "invariant": ["at most once", "exactly once", "only once"],
                          "correction": ["idempotency key", "deduplicate", "processed", "seen"]},
    "validation": {"cause": ["unchecked", "not checked", "missing check", "accepts", "unvalidated"],
                   "invariant": ["valid", "allowed", "within bounds", "permitted"],
                   "correction": ["validate", "reject", "guard", "check", "clamp"]},
    "boundary_condition": {"cause": ["off by one", "boundary", "empty", "last element", "limit"],
                           "invariant": ["every element", "inclusive", "exclusive", "empty input"],
                           "correction": ["range", "bound", "length", "inclusive", "guard"]},
    "nullability": {"cause": ["null", "none", "nil", "missing", "undefined"],
                    "invariant": ["present", "default", "optional"],
                    "correction": ["guard", "default", "null check", "initialize"]},
    "runtime_exception": {"cause": ["exception", "crash", "raises", "throws", "panic"],
                          "invariant": ["valid input", "never crash", "handled"],
                          "correction": ["guard", "handle", "check", "catch"]},
    "numeric_precision": {"cause": ["overflow", "rounding", "precision", "truncate", "integer division"],
                          "invariant": ["exact", "precise", "range"],
                          "correction": ["long", "widen", "decimal", "round", "integer cents"]},
    "state_corruption": {"cause": ["shared", "mutate", "mutable", "alias", "overwrite"],
                         "invariant": ["unchanged", "consistent", "isolated"],
                         "correction": ["copy", "new object", "immutable", "reset"]},
    "database_transactions": {"cause": ["transaction", "partial", "rollback", "commit"],
                              "invariant": ["all or nothing", "atomic", "consistent"],
                              "correction": ["transaction", "rollback", "commit", "atomic"]},
    "serialization": {"cause": ["parse", "encode", "format", "escape", "decode"],
                      "invariant": ["round trip", "valid format", "preserve"],
                      "correction": ["parse", "escape", "encode", "format"]},
    "caching": {"cause": ["cache", "stale", "invalidate", "expire"],
                "invariant": ["fresh", "latest", "consistent"],
                "correction": ["invalidate", "evict", "update cache", "ttl"]},
    "authentication": {"cause": ["token", "credential", "expired", "identity"],
                       "invariant": ["authenticated", "valid token"],
                       "correction": ["verify", "expiry check", "reject"]},
    "authorization": {"cause": ["permission", "role", "owner", "access"],
                      "invariant": ["only", "authorized", "deny"],
                      "correction": ["check permission", "deny", "verify owner"]},
    "distributed_consistency": {"cause": ["replica", "stale", "version", "quorum", "conflict"],
                                "invariant": ["consistent", "converge", "latest"],
                                "correction": ["version", "quorum", "compare", "merge"]},
    "configuration": {"cause": ["config", "setting", "default", "threshold"],
                      "invariant": ["within limit", "configured"],
                      "correction": ["setting", "configure", "limit", "default"]},
    "time_handling": {"cause": ["timezone", "utc", "offset", "clock", "deadline"],
                      "invariant": ["same instant", "chronological", "utc"],
                      "correction": ["utc", "aware", "offset", "normalize"]},
    "observability": {"cause": ["swallow", "hidden", "ignored", "aggregate"],
                      "invariant": ["reported", "visible", "counted"],
                      "correction": ["log", "report", "propagate", "count"]},
    "resource_leak": {"cause": ["leak", "not released", "never closed", "exhausted"],
                      "invariant": ["released", "bounded"],
                      "correction": ["finally", "close", "release", "context manager"]},
    "logic_error": {"cause": ["condition", "formula", "comparison", "operator"],
                    "invariant": ["every", "all", "correct"],
                    "correction": ["condition", "formula", "operator"]},
    "data_reasoning": {"cause": ["denominator", "metric", "leakage", "aggregate", "sample"],
                       "invariant": ["unbiased", "definition", "per"],
                       "correction": ["denominator", "per", "filter", "group"]},
}

STOP_IDENTIFIERS = frozenset("""
solve data def return if else elif for while in not and or is none true false import from as class self pass
break continue try except finally raise with lambda yield global nonlocal assert del print len int str float
bool list dict set tuple range enumerate zip sorted reversed sum min max abs map filter any all isinstance type
object append extend insert pop get keys items values update copy json loads dumps function const let var new
this null undefined return typeof instanceof module exports require console log math number string boolean
array object promise async await of public private protected static final void int long double char byte short
boolean string integer system out println util java import package gson jsonobject jsonarray jsonelement
jsonprimitive jsonnull getasint getaslong getasdouble getasstring getasboolean getasjsonarray getasjsonobject
addproperty add size isempty contains equals hashcode tostring include nlohmann json std auto const vector map
unordered_map string size_t uint64_t int64_t push_back emplace_back begin end at value cout cerr endl func package
main interface float64 int64 make nil err error fmt sprintf errors string strconv go type struct case switch default
""".split())

CODE_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
STRING_KEY = re.compile(r"""["']([A-Za-z_][A-Za-z0-9_]{2,40})["']""")
DEFINITION = re.compile(r"^\s*(?:def|function|func|(?:public|private|protected|static|\s)+[\w<>\[\], ]+)\s+(\w+)\s*\(")
SHAPE_SENTENCE = re.compile(r"\b(must|never|always|only|at most|at least|exactly|should|cannot|every|each)\b", re.I)
METHOD_WORDS = ("run", "test", "call", "input", "case", "reproduce", "execute", "invoke", "trigger", "example",
                "scenario", "request", "send", "concurrent", "thread", "replay", "simulate", "feed", "pass")
OBSERVATION_WORDS = ("expect", "expected", "actual", "should", "instead", "returns", "observe", "output", "assert",
                     "compare", "result", "error", "crash", "exception", "mismatch", "differs", "wrong", "fails")


class RubricError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


SHAPE_WORDS = frozenset(word for phrase in INVARIANT_SHAPE for word in phrase.split())


def _surface_words(text: str) -> list[str]:
    return [word for word in words(text)
            if word not in STOP_WORDS and word not in GENERIC_WORDS and word not in SHAPE_WORDS
            and len(word) >= 3 and not word[0].isdigit()]


@lru_cache(maxsize=1)
def _corpus() -> tuple[int, Counter]:
    """Catalog-wide document frequency of word stems, used to weight generic words down."""
    from app.catalog import CATALOG
    frequency = Counter()
    for item in CATALOG:
        text = " ".join([item["summary"], item["explanation"], *item["requirements"], *item["hints"]])
        frequency.update({stem(word) for word in _surface_words(text)})
    return len(CATALOG), frequency


def _idf(word_stem: str) -> float:
    documents, frequency = _corpus()
    return math.log((documents + 1) / (frequency.get(word_stem, 0) + 1)) + 1


def _ranked_keywords(weighted_texts: list[tuple[str, float]], limit: int, exclude: set[str] = frozenset()) -> list[str]:
    scores: Counter = Counter()
    surface: dict[str, str] = {}
    for text, weight in weighted_texts:
        for word in _surface_words(text):
            key = stem(word)
            if key in exclude:
                continue
            scores[key] += weight
            surface.setdefault(key, word)
    ranked = sorted(scores, key=lambda key: (-scores[key] * _idf(key), key))
    return [surface[key] for key in ranked[:limit]]


def _group(word: str) -> list[str]:
    synonyms = SYNONYMS.get(word) or next((values for key, values in SYNONYMS.items() if stem(key) == stem(word)), [])
    return list(dict.fromkeys([word, *synonyms]))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def _enclosing_definition(lines: list[str], index: int) -> str | None:
    for position in range(min(index, len(lines) - 1), -1, -1):
        match = DEFINITION.match(lines[position])
        if match:
            return match.group(1)
    return None


def _component_terms(problem) -> tuple[list[str], list[str]]:
    """Identifiers the defect lives in (from the starter) and identifiers the fix introduces."""
    component: Counter = Counter()
    introduced: Counter = Counter()
    for language in list(problem.starters)[:2]:
        starter = (problem.starters.get(language) or "").splitlines()
        solution = (problem.solutions.get(language) or "").splitlines()
        if not starter or not solution:
            continue
        matcher = difflib.SequenceMatcher(a=starter, b=solution, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            context = starter[i1:i2] or starter[max(0, i1 - 1):i1 + 1]
            for line in context:
                for name in CODE_IDENTIFIER.findall(line) + STRING_KEY.findall(line):
                    if name.lower() not in STOP_IDENTIFIERS and len(name) >= 3:
                        component[name] += 1
            definition = _enclosing_definition(starter, i1)
            if definition and definition.lower() not in STOP_IDENTIFIERS:
                component[definition] += 2
            starter_names = {name for line in starter for name in CODE_IDENTIFIER.findall(line)}
            for line in solution[j1:j2]:
                for name in CODE_IDENTIFIER.findall(line):
                    if name not in starter_names and name.lower() not in STOP_IDENTIFIERS and len(name) >= 3:
                        introduced[name] += 1
    ordered = [name for name, _ in sorted(component.items(), key=lambda pair: (-pair[1], pair[0]))]
    return ordered[:8], [name for name, _ in sorted(introduced.items(), key=lambda pair: (-pair[1], pair[0]))][:4]


def _input_keys(problem) -> list[str]:
    keys: list[str] = []
    for test in problem.tests:
        if not test.get("hidden") and isinstance(test.get("input"), dict):
            keys.extend(key for key in test["input"] if isinstance(key, str))
    return list(dict.fromkeys(keys))


def _unique_groups(groups: list[list[str]], limit: int) -> list[list[str]]:
    seen: set[str] = set()
    result = []
    for group in groups:
        cleaned = [phrase.strip().lower()[:MAX_PHRASE] for phrase in group if phrase and phrase.strip()]
        cleaned = list(dict.fromkeys(cleaned))
        if not cleaned:
            continue
        key = stem(words(cleaned[0])[0]) if words(cleaned[0]) else cleaned[0]
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def derive_rubric(problem) -> dict:
    """A deterministic rubric for problems without an authored one."""
    classification = taxonomy.classify_problem(problem)
    bugs = classification["bug_categories"] or ["logic_error"]
    related = sorted({item for bug in bugs for item in taxonomy.related_categories(bug)} - set(bugs))
    vocabulary = CATEGORY_VOCABULARY.get(bugs[0], CATEGORY_VOCABULARY["logic_error"])
    hints = list(problem.hints or []) + ["", "", ""]
    explanation_sentences = _sentences(problem.explanation)
    # Complexity notes ("Time O(n)...") are not about the defect.
    explanation_sentences = [s for s in explanation_sentences if not re.match(r"^(time|space|extra)\b", s, re.I)]
    component, introduced = _component_terms(problem)

    cause_words = _ranked_keywords([(hints[1], 1.2), (hints[2], 1.0), (" ".join(explanation_sentences[:2]), 1.0),
                                    (hints[0], 0.6), (problem.summary, 0.4)], 8)
    if len(cause_words) < 3:
        cause_words += _ranked_keywords([(problem.summary, 1.0), (problem.description, 0.5)], 6,
                                        exclude={stem(word) for word in cause_words})
    root_cause = _unique_groups([_group(word) for word in cause_words] + [vocabulary["cause"]], 10)

    requirement_text = " ".join(problem.requirements or [])
    shaped = " ".join(s for s in _sentences(requirement_text) if SHAPE_SENTENCE.search(s)) or requirement_text
    invariant = _unique_groups([_group(word) for word in _ranked_keywords([(shaped, 1.0)], 5)]
                               + [vocabulary["invariant"]], 7)

    correction_words = _ranked_keywords([(hints[2], 1.4), (" ".join(explanation_sentences[:1]), 1.0)], 6)
    correction = _unique_groups([_group(word) for word in correction_words]
                                + [[name.lower(), *split_identifier(name)] for name in introduced[:2]]
                                + [vocabulary["correction"]], 9)

    reproduction: list[list[str]] = []
    for test in problem.tests:
        if not test.get("hidden"):
            names = _surface_words(test.get("name", ""))
            if names:
                reproduction.append(names[:4])
    keys = _input_keys(problem)
    if keys:
        reproduction.append([key.lower() for key in keys][:8])
    reproduction = _unique_groups(reproduction, 8)

    if not component:
        component = keys[:4] or _ranked_keywords([(problem.summary, 1.0)], 3) or ["solve"]

    return {
        "version": getattr(problem, "rubric_version", 1) or 1,
        "format": RUBRIC_FORMAT_VERSION,
        "source": "derived",
        "defect_categories": bugs,
        "related_categories": related,
        "root_cause": root_cause,
        "component": component,
        "invariant": invariant or [vocabulary["invariant"]],
        "correction": correction or [vocabulary["correction"]],
        "reproduction": reproduction or [["input", "example"]],
    }


def _validate_groups(name: str, value, errors: list[str], *, required: bool) -> None:
    if value is None:
        if required:
            errors.append(f"{name}: at least one concept group is required.")
        return
    if not isinstance(value, list) or (required and not value):
        errors.append(f"{name}: expected a non-empty list of concept groups.")
        return
    if len(value) > MAX_GROUPS:
        errors.append(f"{name}: at most {MAX_GROUPS} groups.")
    for index, group in enumerate(value):
        if not isinstance(group, list) or not group:
            errors.append(f"{name}[{index}]: each group is a non-empty list of phrases.")
            continue
        for phrase in group:
            if not isinstance(phrase, str) or not phrase.strip() or len(phrase) > MAX_PHRASE or not words(phrase):
                errors.append(f"{name}[{index}]: phrases are non-empty text of at most {MAX_PHRASE} characters.")
                break


def validate_rubric(rubric) -> list[str]:
    """Return human-readable format errors; an empty list means the rubric is valid."""
    errors: list[str] = []
    if not isinstance(rubric, dict):
        return ["The rubric must be a JSON object."]
    try:
        if len(json.dumps(rubric)) > 50000:
            errors.append("The rubric exceeds 50 KB.")
    except (TypeError, ValueError):
        return ["The rubric must contain only JSON values."]
    categories = rubric.get("defect_categories")
    if not isinstance(categories, list) or not categories:
        errors.append("defect_categories: list at least one taxonomy category.")
    else:
        unknown = [value for value in categories if value not in taxonomy.BUG_CATEGORIES]
        if unknown:
            errors.append(f"defect_categories: unknown categories {unknown}.")
    related = rubric.get("related_categories", [])
    if not isinstance(related, list) or any(value not in taxonomy.BUG_CATEGORIES for value in related):
        errors.append("related_categories: use taxonomy category ids.")
    _validate_groups("root_cause", rubric.get("root_cause"), errors, required=True)
    for section in ("invariant", "correction", "reproduction"):
        _validate_groups(section, rubric.get(section), errors, required=False)
    component = rubric.get("component")
    if not isinstance(component, list) or not component or not all(
            isinstance(term, str) and term.strip() and len(term) <= MAX_PHRASE for term in component):
        errors.append("component: list at least one identifier or term.")
    weights = rubric.get("weights")
    if weights is not None:
        if not isinstance(weights, dict) or not weights or any(key not in CRITERIA for key in weights) or any(
                not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 for value in weights.values()) \
                or not sum(weights.values()):
            errors.append(f"weights: map criteria {list(CRITERIA)} to nonnegative numbers with a positive sum.")
    explanation = rubric.get("explanation")
    if explanation is not None:
        if not isinstance(explanation, dict) or any(key not in {"why_failed", "why_works", "invariant"} for key in explanation):
            errors.append("explanation: allowed keys are why_failed, why_works and invariant.")
        else:
            for key, value in explanation.items():
                _validate_groups(f"explanation.{key}", value, errors, required=True)
    return errors


def normalize_rubric(stored: dict, derived: dict) -> dict:
    """Fill sections an authored rubric omits from the derived rubric; lowercase phrases."""
    result = dict(derived)
    for key in ("defect_categories", "related_categories", "weights", "explanation"):
        if stored.get(key) is not None:
            result[key] = stored[key]
    for section in GROUP_SECTIONS:
        if stored.get(section):
            result[section] = [[phrase.strip().lower() for phrase in group] for group in stored[section]]
    if stored.get("component"):
        result["component"] = [term.strip() for term in stored["component"]]
    if result.get("explanation"):
        result["explanation"] = {key: [[phrase.strip().lower() for phrase in group] for group in groups]
                                 for key, groups in result["explanation"].items()}
    return result


def rubric_for(problem) -> dict:
    """The effective rubric: an authored or administrator rubric, else the derived one."""
    derived = derive_rubric(problem)
    stored = problem.diagnosis_rubric
    version = getattr(problem, "rubric_version", 1) or 1
    if isinstance(stored, dict) and stored:
        errors = validate_rubric(stored)
        if not errors:
            rubric = normalize_rubric(stored, derived)
            rubric["source"] = stored.get("source") if stored.get("source") in {"authored", "admin"} else "authored"
            rubric["version"] = version
            return rubric
        log.warning("Ignoring invalid stored rubric for %s: %s", problem.slug, errors)
    derived["version"] = version
    return derived


def method_words() -> tuple[str, ...]:
    return METHOD_WORDS


def observation_words() -> tuple[str, ...]:
    return OBSERVATION_WORDS
