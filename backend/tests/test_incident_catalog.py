"""The bundled production-incident catalog: format, evidence, and executable behavior (PRD §6)."""
import json
import re
from copy import deepcopy
from datetime import datetime

import pytest

from app.execution import at_path, equal
from app.incidents.catalog import INCIDENTS
from app.incidents.validation import validate_definition
from app.taxonomy import BUG_CATEGORIES, DEBUGGING_SKILLS

REQUIRED_KEYS = {"slug", "title", "summary", "severity", "level", "category", "taxonomy", "affected_services",
                 "impact", "expected_behavior", "observed_symptoms", "objective", "timeline", "artifacts",
                 "scenarios", "rubric", "evaluation", "problem"}
REQUIRED_ARTIFACTS = {"logs", "metrics", "traces", "database", "config", "diff", "architecture"}
ARTIFACT_TYPES = REQUIRED_ARTIFACTS | {"source", "api_contract", "runbook"}
TEXT_TYPES = {"config", "source", "api_contract", "runbook"}
NODE_KINDS = {"service", "database", "cache", "queue", "external"}
LOG_LEVELS = {"DEBUG", "INFO", "WARN", "ERROR"}
RUBRIC_GROUPS = ("root_cause", "invariant", "correction", "reproduction")
CONCEPT_SECTIONS = ("remediation_concepts", "prevention_concepts", "impact_concepts")
ids = [incident["slug"] for incident in INCIDENTS]


def parse_time(value: str) -> datetime:
    # Accept whole seconds and millisecond log timestamps, always in UTC.
    return datetime.strptime(value.replace("Z", "+0000"),
                             "%Y-%m-%dT%H:%M:%S.%f%z" if "." in value else "%Y-%m-%dT%H:%M:%S%z")


def run(source: str, data):
    # Repository-authored reference and starter programs, executed in process like the catalog tests.
    namespace = {}
    exec(compile(source, "incident", "exec"), namespace)
    return json.loads(json.dumps(namespace["solve"](deepcopy(data)), allow_nan=False))


def is_concept_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(group, list) and group and all(isinstance(term, str) and term.strip() and term == term.lower()
                                                  for term in group) for group in value)


def test_catalog_is_append_only_and_covers_the_initial_scope():
    # Positions determine seeded incident and problem IDs; only append new incidents.
    assert ids == ["inventory-reservation-race", "duplicate-payment-retries", "stale-price-cache",
                   "connection-pool-exhaustion", "retry-amplification-storm", "scheduler-dst-shift"]
    assert len(set(ids)) == len(ids)
    assert len({incident["problem"]["title"] for incident in INCIDENTS}) == len(INCIDENTS)
    assert {1, 2, 3} <= {incident["level"] for incident in INCIDENTS}
    assert {incident["category"] for incident in INCIDENTS} == {
        "race_condition", "retry_idempotency", "caching", "resource_leak", "time_handling"}
    assert len({incident["severity"] for incident in INCIDENTS}) >= 3


@pytest.mark.parametrize("incident", INCIDENTS, ids=ids)
def test_definition_passes_the_publication_validator(incident):
    assert validate_definition(incident) == []
    json.dumps(incident, allow_nan=False)


@pytest.mark.parametrize("incident", INCIDENTS, ids=ids)
def test_overview_fields_and_taxonomy(incident):
    assert REQUIRED_KEYS <= set(incident)
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", incident["slug"])
    assert incident["severity"] in {"SEV-1", "SEV-2", "SEV-3", "SEV-4"} and incident["level"] in {1, 2, 3, 4}
    taxonomy = incident["taxonomy"]
    assert taxonomy["bug_categories"][0] == incident["category"] in BUG_CATEGORIES
    assert set(taxonomy["bug_categories"]) <= set(BUG_CATEGORIES)
    assert taxonomy["skills"] and set(taxonomy["skills"]) <= set(DEBUGGING_SKILLS)
    for key in ("affected_services", "impact", "observed_symptoms"):
        assert incident[key] and all(isinstance(item, str) and item.strip() for item in incident[key])
    for key in ("title", "summary", "expected_behavior", "objective"):
        assert isinstance(incident[key], str) and incident[key].strip()
    # Level 2+ incidents include misleading-but-explainable symptoms alongside the real ones.
    assert len(incident["observed_symptoms"]) >= (3 if incident["level"] >= 2 else 2)
    times = [parse_time(entry["at"]) for entry in incident["timeline"]]
    assert times == sorted(times) and len(times) >= 5
    assert {entry["kind"] for entry in incident["timeline"]} <= {"deploy", "alert", "symptom", "action", "note"}
    assert any(entry["kind"] == "deploy" for entry in incident["timeline"])


@pytest.mark.parametrize("incident", INCIDENTS, ids=ids)
def test_artifacts_have_the_documented_shapes(incident):
    artifacts = incident["artifacts"]
    assert len(artifacts) >= 6 and len({a["id"] for a in artifacts}) == len(artifacts)
    assert REQUIRED_ARTIFACTS <= {a["type"] for a in artifacts}
    for artifact in artifacts:
        assert {"id", "type", "title", "description", "data"} <= set(artifact)
        assert artifact["type"] in ARTIFACT_TYPES and artifact["title"].strip() and artifact["description"].strip()
        data = artifact["data"]
        if artifact["type"] == "logs":
            entries = data["entries"]
            assert 15 <= len(entries) <= 40
            assert [entry["ts"] for entry in entries] == sorted(entry["ts"] for entry in entries)
            for entry in entries:
                assert {"ts", "level", "service", "message", "fields"} <= set(entry)
                assert entry["level"] in LOG_LEVELS and isinstance(entry["fields"], dict)
                parse_time(entry["ts"])
            assert any(entry.get("trace_id") for entry in entries)
        elif artifact["type"] == "metrics":
            assert 2 <= len(data["series"]) <= 4 and data["annotations"]
            for row in data["series"]:
                assert row["name"] and row["unit"] and len(row["points"]) >= 6
                for moment, value in row["points"]:
                    parse_time(moment)
                    assert isinstance(value, (int, float)) and not isinstance(value, bool)
            starts = min(parse_time(row["points"][0][0]) for row in data["series"])
            ends = max(parse_time(row["points"][-1][0]) for row in data["series"])
            # The deploy that introduced the defect is visible on the dashboard.
            assert any(starts <= parse_time(note["at"]) <= ends and "deploy" in note["label"].lower()
                       or "rolled out" in note["label"] for note in data["annotations"])
        elif artifact["type"] == "traces":
            assert len(data["traces"]) >= 2
            for trace in data["traces"]:
                spans = trace["spans"]
                span_ids = [item["span_id"] for item in spans]
                assert trace["trace_id"] and len(set(span_ids)) == len(span_ids)
                assert sum(item["parent_id"] is None for item in spans) == 1
                for item in spans:
                    assert item["parent_id"] is None or item["parent_id"] in span_ids
                    assert item["status"] in {"ok", "error"} and item["duration_ms"] >= 0
                    assert isinstance(item["attributes"], dict)
        elif artifact["type"] == "database":
            for table in data["tables"]:
                assert table["name"] and table["columns"]
                assert all(len(row) == len(table["columns"]) for row in table["rows"])
        elif artifact["type"] in TEXT_TYPES:
            assert data["path"] and data["language"] and data["content"].strip()
        elif artifact["type"] == "diff":
            content = data["content"]
            assert data["title"] and data["author"] and content.startswith("--- ")
            assert re.search(r"^\+[^+]", content, re.M) and re.search(r"^-[^-]", content, re.M)
        elif artifact["type"] == "architecture":
            nodes = {node["id"] for node in data["nodes"]}
            assert len(nodes) == len(data["nodes"]) >= 4
            assert {node["kind"] for node in data["nodes"]} <= NODE_KINDS
            assert all(edge["from"] in nodes and edge["to"] in nodes and edge["label"] for edge in data["edges"])


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


@pytest.mark.parametrize("incident", INCIDENTS, ids=ids)
def test_evidence_is_fictional(incident):
    for text in strings(incident):
        for host in re.findall(r"https?://([^/\s:\"']+)", text):
            assert host.endswith("example.com") or host.endswith(".internal"), host
        assert not re.search(r"[A-Za-z0-9._%+-]+@(?!example\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        assert not re.search(r"(?<![\w.])\d{1,3}(\.\d{1,3}){3}(?![\d.])", text)


@pytest.mark.parametrize("incident", INCIDENTS, ids=ids)
def test_scenarios_rubric_and_evaluation_concepts(incident):
    problem = incident["problem"]
    public = [test["name"] for test in problem["tests"] if not test["hidden"]]
    scenarios = incident["scenarios"]
    assert len({scenario["id"] for scenario in scenarios}) == len(scenarios)
    referenced = {name for scenario in scenarios for name in scenario["tests"]}
    assert referenced <= set(public) and referenced == set(public)
    assert all(scenario["name"] and scenario["description"] for scenario in scenarios)
    rubric = incident["rubric"]
    assert rubric["version"] == 1 and rubric["source"] == "authored"
    assert incident["category"] in rubric["defect_categories"]
    assert set(rubric["defect_categories"] + rubric["related_categories"]) <= set(BUG_CATEGORIES)
    assert len(rubric["root_cause"]) >= 4
    for section in RUBRIC_GROUPS:
        assert is_concept_list(rubric[section]), section
    starter = problem["starters"]["python"]
    assert rubric["component"] and all(name in starter for name in rubric["component"])
    for section in CONCEPT_SECTIONS:
        assert is_concept_list(incident["evaluation"][section]), section


@pytest.mark.parametrize("incident", INCIDENTS, ids=ids)
def test_problem_shape(incident):
    problem = incident["problem"]
    assert problem["category"] in {"runtime", "logic", "business", "edge", "system_design"}
    assert problem["difficulty"] in {"easy", "medium", "hard"}
    assert set(problem["starters"]) == set(problem["solutions"]) == {"python"}
    assert problem["starters"]["python"] != problem["solutions"]["python"]
    assert len(problem["hints"]) == 3 and all(hint.strip() for hint in problem["hints"])
    assert problem["requirements"] and problem["explanation"].strip() and 5 <= problem["minutes"] <= 240
    tests = problem["tests"]
    names = [test["name"] for test in tests]
    assert len(set(names)) == len(names)
    assert 2 <= sum(not test["hidden"] for test in tests) <= 3
    assert sum(test["hidden"] for test in tests) >= 4
    for test in tests:
        for assertion in test["assertions"]:
            assert equal(at_path(test["expected"], assertion["path"]), assertion["equals"])


@pytest.mark.parametrize("incident", INCIDENTS, ids=ids)
def test_reference_resolves_and_starter_reproduces_the_incident(incident):
    problem = incident["problem"]
    public_failures = hidden_failures = 0
    for test in problem["tests"]:
        outputs = [run(problem["solutions"]["python"], test["input"]) for _ in range(5)]
        assert all(output == outputs[0] for output in outputs), f"{test['name']} is not deterministic"
        assert equal(outputs[0], test["expected"]), test["name"]
        # The starter must fail by returning a wrong answer, never by crashing.
        actual = run(problem["starters"]["python"], test["input"])
        if not equal(actual, test["expected"]):
            if test["hidden"]:
                hidden_failures += 1
            else:
                public_failures += 1
    assert public_failures >= 1, "a public scenario must reproduce the incident"
    assert hidden_failures >= 1, "hidden regression cases must also catch the defect"


def _partial(slug: str, variant: str, old: str, new: str) -> str:
    source = next(item for item in INCIDENTS if item["slug"] == slug)["problem"][variant]["python"]
    assert old in source
    return source.replace(old, new)


PARTIAL_FIXES = {
    # Re-reading the stock before writing narrows the window but is still a check-then-act race.
    "inventory-reservation-race": _partial("inventory-reservation-race", "starters", '''    remaining = available - quantity
    yield from db.update_available(sku, remaining)
''', '''    available = yield from db.select_available(sku)
    if available < quantity:
        return "rejected"
    remaining = available - quantity
    yield from db.update_available(sku, remaining)
'''),
    # Refusing to retry after any earlier attempt stops duplicates but breaks legitimate retries.
    "duplicate-payment-retries": _partial("duplicate-payment-retries", "starters",
                                          'if record and record["status"] in ("succeeded", "declined"):',
                                          "if record:"),
    # Releasing without rolling back commits the rejected order's rows with the next request.
    "connection-pool-exhaustion": _partial("connection-pool-exhaustion", "starters", '''        connection.begin()
        connection.execute(("insert_order", request["order_id"]))
        for line in request["lines"]:
            if line["sku"] not in self.catalog or line["quantity"] <= 0:
                raise ValidationError(f"invalid line {line['sku']} x {line['quantity']}")
            connection.execute(("insert_line", request["order_id"], line["sku"], line["quantity"]))
        connection.commit()
        self.pool.release(connection)
''', '''        try:
            connection.begin()
            connection.execute(("insert_order", request["order_id"]))
            for line in request["lines"]:
                if line["sku"] not in self.catalog or line["quantity"] <= 0:
                    raise ValidationError(f"invalid line {line['sku']} x {line['quantity']}")
                connection.execute(("insert_line", request["order_id"], line["sku"], line["quantity"]))
            connection.commit()
        finally:
            self.pool.release(connection)
'''),
    # Removing only the gateway retries still retries conflicts inside checkout.
    "retry-amplification-storm": _partial("retry-amplification-storm", "starters", "GATEWAY_ATTEMPTS = 3",
                                          "GATEWAY_ATTEMPTS = 1"),
    # Clearing only the legacy key and the USD key misses the other currencies.
    "stale-price-cache": _partial("stale-price-cache", "starters", '        self.cache.delete(f"price:{sku}")',
                                  '        self.cache.delete(price_cache_key(sku, "USD"))'),
    # Shifting every run by a fixed hour fixes one season and breaks the other.
    "scheduler-dst-shift": _partial("scheduler-dst-shift", "starters",
                                    'offset = timedelta(minutes=subscription["utc_offset_minutes"])',
                                    'offset = timedelta(minutes=subscription["utc_offset_minutes"] + 60)'),
}


@pytest.mark.parametrize("slug", PARTIAL_FIXES)
def test_tests_reject_plausible_partial_fixes(slug):
    problem = next(item for item in INCIDENTS if item["slug"] == slug)["problem"]
    failures = [test["name"] for test in problem["tests"]
                if not equal(run(PARTIAL_FIXES[slug], test["input"]), test["expected"])]
    assert failures, f"no test rejects the partial fix for {slug}"
