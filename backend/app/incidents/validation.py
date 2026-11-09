"""Structural validation for incident definitions and user regression tests (PRD 6.7, 6.8).

The same checks guard the bundled catalog (tests), administrator-authored incidents, and the
publication gate. They also reject anything that looks like a real credential, customer contact
or public infrastructure address: incidents are fictional by construction.
"""
import hashlib
import ipaddress
import json
import re

from app.taxonomy import BUG_CATEGORIES, DEBUGGING_SKILLS

SEVERITIES = ("SEV-1", "SEV-2", "SEV-3", "SEV-4")
ARTIFACT_TYPES = ("logs", "metrics", "traces", "database", "config", "diff", "architecture", "source",
                  "api_contract", "runbook")
TEXT_ARTIFACTS = ("config", "source", "api_contract", "runbook")
TIMELINE_KINDS = ("deploy", "alert", "symptom", "action", "note")
PROBLEM_CATEGORIES = ("runtime", "logic", "business", "edge", "system_design", "data_science", "data_analytics")
DIFFICULTIES = ("easy", "medium", "hard")
LANGUAGES = ("python", "java", "javascript", "cpp", "go")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ARTIFACT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
CONCEPT_SECTIONS = ("remediation_concepts", "prevention_concepts", "impact_concepts")
RUBRIC_GROUP_SECTIONS = ("root_cause", "invariant", "correction", "reproduction")

MAX_REGRESSION_TESTS = 10
MAX_REGRESSION_TEST_BYTES = 5 * 1024
MAX_REGRESSION_NAME = 120

# Patterns for material that must never appear in a fictional incident.
SECRET_PATTERNS = [
    ("an AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("a private key", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    ("an API secret key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{16,}\b|\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("a GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("a Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("a bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{32,}=*")),
    ("a JSON web token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("a credential in a connection string", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s:/@]*:([^\s@/]+)@")),
]
PLACEHOLDER_SECRETS = {"redacted", "password", "secret", "changeme", "example", "placeholder", "hidden"}
# Environment references, templates and masks are placeholders, not credentials.
PLACEHOLDER_PATTERN = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|\{\{.*\}\}|<[^>]*>|%\(.*\)s|[*xX•.]+")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
SAFE_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "example")
SAFE_EMAIL_SUFFIXES = (".example", ".test", ".invalid", ".local", ".internal")
# Not preceded by a word character or dot, so version strings such as v2.14.0.1 are ignored.
IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
DOCUMENTATION_NETWORKS = [ipaddress.ip_network(net) for net in
                          ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


def _strings(value, path="$"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")


def _safe_ip(text: str) -> bool:
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return True  # Version strings such as 1.2.3.4000 are not addresses.
    return (address.is_private or address.is_loopback or address.is_unspecified or address.is_link_local
            or address.is_reserved or any(address in network for network in DOCUMENTATION_NETWORKS))


def scan_sensitive(value) -> list[str]:
    """Findings for credentials, real-looking contacts and public addresses anywhere in ``value``."""
    findings = []
    for path, text in _strings(value):
        for label, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                secret = (match.group(1) if pattern.groups else match.group(0)).strip()
                if secret.lower() in PLACEHOLDER_SECRETS or PLACEHOLDER_PATTERN.fullmatch(secret):
                    continue
                findings.append(f"{path} contains what looks like {label}.")
                break
        for match in EMAIL.finditer(text):
            domain = match.group(1).lower()
            if domain in SAFE_EMAIL_DOMAINS or domain.endswith(tuple("." + d for d in SAFE_EMAIL_DOMAINS)) \
                    or domain.endswith(SAFE_EMAIL_SUFFIXES):
                continue
            findings.append(f"{path} contains a non-example email address; use example.com.")
            break
        for match in IPV4.finditer(text):
            if not _safe_ip(match.group(1)):
                findings.append(f"{path} contains a public IP address; use a private or documentation range.")
                break
    return findings


def _is_group_list(value) -> bool:
    return isinstance(value, list) and all(
        isinstance(group, list) and group and all(isinstance(term, str) and term.strip() for term in group)
        for group in value)


def _check_artifact(artifact: dict, errors: list[str]):
    where = f"artifact {artifact.get('id')!r}"
    kind, data = artifact.get("type"), artifact.get("data")
    if kind not in ARTIFACT_TYPES:
        errors.append(f"{where} has unknown type {kind!r}.")
        return
    if not isinstance(data, dict):
        errors.append(f"{where} needs a data object.")
        return
    if kind == "logs":
        entries = data.get("entries")
        if not isinstance(entries, list) or not entries:
            errors.append(f"{where} needs log entries.")
        elif not all(isinstance(e, dict) and {"ts", "level", "service", "message"} <= set(e) for e in entries):
            errors.append(f"{where} log entries need ts, level, service and message.")
    elif kind == "metrics":
        series = data.get("series")
        if not isinstance(series, list) or not series:
            errors.append(f"{where} needs metric series.")
        else:
            for row in series:
                points = row.get("points") if isinstance(row, dict) else None
                if not isinstance(row, dict) or not row.get("name") or not isinstance(points, list) or not points \
                        or not all(isinstance(p, list) and len(p) == 2 and isinstance(p[1], (int, float))
                                   and not isinstance(p[1], bool) for p in points):
                    errors.append(f"{where} series need a name and [timestamp, number] points.")
                    break
    elif kind == "traces":
        traces = data.get("traces")
        if not isinstance(traces, list) or not traces:
            errors.append(f"{where} needs traces.")
        else:
            for trace in traces:
                spans = trace.get("spans") if isinstance(trace, dict) else None
                if not isinstance(spans, list) or not spans or not all(
                        isinstance(s, dict) and {"span_id", "service", "name", "start_ms", "duration_ms"} <= set(s)
                        for s in spans):
                    errors.append(f"{where} traces need spans with span_id, service, name, start_ms, duration_ms.")
                    break
    elif kind == "database":
        tables = data.get("tables")
        if not isinstance(tables, list) or not tables or not all(
                isinstance(t, dict) and t.get("name") and isinstance(t.get("columns"), list)
                and isinstance(t.get("rows"), list) and all(isinstance(r, list) and len(r) == len(t["columns"])
                                                            for r in t["rows"]) for t in tables):
            errors.append(f"{where} tables need a name, columns and rows matching the columns.")
    elif kind in TEXT_ARTIFACTS:
        if not isinstance(data.get("content"), str) or not data.get("content").strip():
            errors.append(f"{where} needs text content.")
    elif kind == "diff":
        if not isinstance(data.get("content"), str) or not data.get("content").strip():
            errors.append(f"{where} needs diff content.")
    elif kind == "architecture":
        nodes, edges = data.get("nodes"), data.get("edges", [])
        ids = {n.get("id") for n in nodes} if isinstance(nodes, list) and all(isinstance(n, dict) for n in nodes) else None
        if not ids or not isinstance(edges, list) or not all(
                isinstance(e, dict) and e.get("from") in ids and e.get("to") in ids for e in edges):
            errors.append(f"{where} needs nodes and edges between known nodes.")


def _check_tests(tests, errors: list[str]) -> set[str]:
    public = set()
    if not isinstance(tests, list) or not tests:
        errors.append("problem.tests must be a non-empty list.")
        return public
    names = set()
    for index, test in enumerate(tests):
        if not isinstance(test, dict) or not {"name", "input", "expected", "hidden"} <= set(test):
            errors.append(f"problem.tests[{index}] needs name, input, expected and hidden.")
            continue
        if not isinstance(test["name"], str) or not test["name"].strip():
            errors.append(f"problem.tests[{index}] needs a name.")
            continue
        if test["name"] in names:
            errors.append(f"Test name {test['name']!r} is duplicated.")
        names.add(test["name"])
        if not isinstance(test["hidden"], bool):
            errors.append(f"Test {test['name']!r} needs a boolean hidden flag.")
        if not isinstance(test.get("assertions", []), list) or not all(
                isinstance(a, dict) and isinstance(a.get("path"), str) and "equals" in a
                for a in test.get("assertions", [])):
            errors.append(f"Test {test['name']!r} assertions need a path and an expected value.")
        try:
            json.dumps(test["input"], allow_nan=False)
            json.dumps(test["expected"], allow_nan=False)
        except (TypeError, ValueError):
            errors.append(f"Test {test['name']!r} must contain JSON values only.")
        if not test["hidden"]:
            public.add(test["name"])
    if not public:
        errors.append("At least one public test must reproduce the failure.")
    if len(public) == len(names):
        errors.append("At least one hidden regression test is required.")
    return public


def validate_definition(definition) -> list[str]:
    """Return every problem with an incident definition (an empty list means it is valid)."""
    errors: list[str] = []
    if not isinstance(definition, dict):
        return ["The incident definition must be a JSON object."]
    slug = definition.get("slug")
    if not isinstance(slug, str) or not SLUG.match(slug) or len(slug) > 80:
        errors.append("slug must be lowercase words separated by hyphens (at most 80 characters).")
    for key in ("title", "summary", "expected_behavior", "objective"):
        if not isinstance(definition.get(key), str) or not definition[key].strip():
            errors.append(f"{key} is required.")
    if isinstance(definition.get("title"), str) and len(definition["title"]) > 150:
        errors.append("title must be at most 150 characters.")
    if definition.get("severity") not in SEVERITIES:
        errors.append(f"severity must be one of {', '.join(SEVERITIES)}.")
    if definition.get("level") not in (1, 2, 3, 4):
        errors.append("level must be 1, 2, 3 or 4.")
    if definition.get("category") not in BUG_CATEGORIES:
        errors.append("category must be a taxonomy bug category.")
    taxonomy = definition.get("taxonomy")
    if not isinstance(taxonomy, dict) or not taxonomy.get("bug_categories") \
            or not all(bug in BUG_CATEGORIES for bug in taxonomy.get("bug_categories", [])) \
            or not all(skill in DEBUGGING_SKILLS for skill in taxonomy.get("skills", [])):
        errors.append("taxonomy needs known bug_categories and skills.")
    for key in ("affected_services", "impact", "observed_symptoms"):
        value = definition.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
            errors.append(f"{key} must be a non-empty list of text.")
    timeline = definition.get("timeline")
    if not isinstance(timeline, list) or not timeline or not all(
            isinstance(t, dict) and isinstance(t.get("at"), str) and t.get("kind") in TIMELINE_KINDS
            and isinstance(t.get("title"), str) for t in timeline):
        errors.append(f"timeline entries need at, title and a kind of {', '.join(TIMELINE_KINDS)}.")
    artifacts = definition.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("At least one artifact is required.")
        artifacts = []
    seen = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("id"), str) \
                or not ARTIFACT_ID.match(artifact["id"]):
            errors.append("Every artifact needs an id of lowercase letters, digits, - or _.")
            continue
        if artifact["id"] in seen:
            errors.append(f"Artifact id {artifact['id']!r} is duplicated.")
        seen.add(artifact["id"])
        if not isinstance(artifact.get("title"), str) or not artifact["title"].strip():
            errors.append(f"artifact {artifact['id']!r} needs a title.")
        _check_artifact(artifact, errors)
    problem = definition.get("problem")
    public: set[str] = set()
    if not isinstance(problem, dict):
        errors.append("problem is required.")
    else:
        for key in ("title", "summary", "explanation"):
            if not isinstance(problem.get(key), str) or not problem[key].strip():
                errors.append(f"problem.{key} is required.")
        if problem.get("category") not in PROBLEM_CATEGORIES:
            errors.append("problem.category must be an existing library category.")
        if problem.get("difficulty") not in DIFFICULTIES:
            errors.append("problem.difficulty must be easy, medium or hard.")
        if not isinstance(problem.get("tags"), list) or not all(isinstance(t, str) for t in problem["tags"]):
            errors.append("problem.tags must be a list of text.")
        requirements = problem.get("requirements")
        if not isinstance(requirements, list) or not requirements or not all(isinstance(r, str) for r in requirements):
            errors.append("problem.requirements must be a non-empty list of text.")
        starters, solutions = problem.get("starters"), problem.get("solutions")
        if not isinstance(starters, dict) or not starters or not isinstance(solutions, dict) \
                or set(starters) != set(solutions) or not set(starters) <= set(LANGUAGES):
            errors.append("problem.starters and problem.solutions need the same supported languages.")
        else:
            for language in starters:
                for name, sources in (("starter", starters), ("solution", solutions)):
                    if not isinstance(sources[language], str) or not sources[language].strip() \
                            or len(sources[language]) > 50000:
                        errors.append(f"The {language} {name} must be non-empty source under 50,000 characters.")
                if starters[language].strip() == solutions[language].strip():
                    errors.append(f"The {language} starter must differ from its reference solution.")
        hints = problem.get("hints")
        if not isinstance(hints, list) or len(hints) != 3 or not all(isinstance(h, str) and h.strip() for h in hints):
            errors.append("problem.hints must contain three progressive hints.")
        minutes = problem.get("minutes", 30)
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not 5 <= minutes <= 240:
            errors.append("problem.minutes must be between 5 and 240.")
        public = _check_tests(problem.get("tests"), errors)
    scenarios = definition.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("At least one reproduction scenario is required.")
    else:
        for scenario in scenarios:
            if not isinstance(scenario, dict) or not scenario.get("id") or not scenario.get("name") \
                    or not isinstance(scenario.get("tests"), list) or not scenario["tests"]:
                errors.append("Scenarios need an id, a name and public test names.")
                continue
            unknown = [name for name in scenario["tests"] if name not in public]
            if unknown:
                errors.append(f"Scenario {scenario['id']!r} references non-public or unknown tests: {unknown}.")
    rubric = definition.get("rubric")
    if not isinstance(rubric, dict) or not rubric.get("defect_categories") \
            or not all(bug in BUG_CATEGORIES for bug in rubric.get("defect_categories", [])):
        errors.append("rubric.defect_categories must list known bug categories.")
    elif not all(_is_group_list(rubric.get(section, [])) for section in RUBRIC_GROUP_SECTIONS) \
            or not rubric.get("root_cause"):
        errors.append("rubric concept sections must be lists of synonym lists.")
    evaluation = definition.get("evaluation")
    if not isinstance(evaluation, dict) or not all(
            _is_group_list(evaluation.get(section)) and evaluation.get(section) for section in CONCEPT_SECTIONS):
        errors.append(f"evaluation needs {', '.join(CONCEPT_SECTIONS)} as lists of synonym lists.")
    errors.extend(scan_sensitive(definition))
    return errors


def content_hash(problem_fields: dict) -> str:
    """Stable hash of the executable part of a problem (code and tests)."""
    payload = {key: problem_fields.get(key) for key in ("starters", "solutions", "tests")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalize_regression_tests(tests) -> list[dict]:
    """Validate user-authored regression tests. Raises ValueError with a user-facing message."""
    if not isinstance(tests, list):
        raise ValueError("Regression tests must be a list.")
    if len(tests) > MAX_REGRESSION_TESTS:
        raise ValueError(f"Add at most {MAX_REGRESSION_TESTS} regression tests.")
    normalized, names = [], set()
    for index, test in enumerate(tests, 1):
        if not isinstance(test, dict) or "input" not in test or "expected" not in test:
            raise ValueError(f"Regression test {index} needs an input and an expected value.")
        name = str(test.get("name") or f"Regression test {index}").strip()[:MAX_REGRESSION_NAME]
        if name in names:
            raise ValueError(f"Regression test names must be unique ({name!r} repeats).")
        names.add(name)
        try:
            size = len(json.dumps({"input": test["input"], "expected": test["expected"]}, allow_nan=False).encode())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Regression test {name!r} must contain JSON values only.") from exc
        if size > MAX_REGRESSION_TEST_BYTES:
            raise ValueError(f"Regression test {name!r} exceeds the 5 KB limit.")
        normalized.append({"name": name, "input": test["input"], "expected": test["expected"]})
    return normalized
