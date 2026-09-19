import json
from collections import Counter
from copy import deepcopy

import pytest

from app.catalog import CATALOG
from app.catalog_extra import ADDITIONAL_CATALOG
from app.execution import equal


def test_expansion_is_append_only_and_balanced():
    assert len(CATALOG) == 221
    assert len(ADDITIONAL_CATALOG) == 100
    assert CATALOG[120]["slug"] == "circuit-breaker-cooldown"
    assert CATALOG[121:] == ADDITIONAL_CATALOG
    assert Counter(item["category"] for item in ADDITIONAL_CATALOG) == {
        "runtime": 20, "logic": 20, "business": 20, "edge": 20, "system_design": 20,
    }
    assert len({item["slug"] for item in CATALOG}) == len(CATALOG)
    assert len({item["title"] for item in CATALOG}) == len(CATALOG)


@pytest.mark.parametrize("item", ADDITIONAL_CATALOG, ids=lambda item: item["slug"])
def test_expansion_reference_and_public_reproducer(item):
    assert len(item["hints"]) == 3
    assert len(item["tests"]) >= 5
    assert any(test["hidden"] for test in item["tests"])
    public_failures = 0
    for variant in ("solutions", "starters"):
        source = compile(item[variant]["python"], item["slug"], "exec")
        for case in item["tests"]:
            # These are repository-authored reference programs, not submitted user code.
            namespace = {}
            exec(source, namespace)
            try:
                actual = namespace["solve"](deepcopy(case["input"]))
                actual = json.loads(json.dumps(actual, allow_nan=False))
            except Exception:
                if variant == "solutions":
                    raise
                if not case["hidden"]:
                    public_failures += 1
            else:
                if variant == "solutions":
                    assert equal(actual, case["expected"]), case["name"]
                elif not case["hidden"] and not equal(actual, case["expected"]):
                    public_failures += 1
    assert public_failures > 0, "An intentional defect must be exposed by a public example"
