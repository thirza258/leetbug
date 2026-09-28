import json
from collections import Counter
from copy import deepcopy

import pytest

from app.catalog import CATALOG
from app.catalog_extra import ADDITIONAL_CATALOG
from app.catalog_extra.wave2 import SECOND_WAVE
from app.catalog_extra.wave3 import THIRD_WAVE
from app.execution import equal

# Other languages run only in the sandbox: python -m app.verify_catalog.
PYTHON_ADDITIONS = [item for item in ADDITIONAL_CATALOG + SECOND_WAVE + THIRD_WAVE if "python" in item["solutions"]]


def test_expansion_is_append_only_and_balanced():
    assert len(CATALOG) == 324
    assert len(ADDITIONAL_CATALOG) == 100
    assert len(SECOND_WAVE) == 50
    assert len(THIRD_WAVE) == 53
    assert CATALOG[120]["slug"] == "circuit-breaker-cooldown"
    assert CATALOG[121:221] == ADDITIONAL_CATALOG
    assert CATALOG[221:271] == SECOND_WAVE
    assert CATALOG[271:] == THIRD_WAVE
    assert Counter(item["category"] for item in ADDITIONAL_CATALOG) == {
        "runtime": 20, "logic": 20, "business": 20, "edge": 20, "system_design": 20,
    }
    assert Counter(item["category"] for item in SECOND_WAVE) == {
        "runtime": 10, "logic": 10, "business": 10, "edge": 10, "system_design": 10,
    }
    assert Counter(language for item in SECOND_WAVE for language in item["solutions"]) == {
        "python": 29, "go": 7, "java": 6, "javascript": 5, "cpp": 3,
    }
    assert Counter(item["category"] for item in THIRD_WAVE) == {
        "runtime": 10, "logic": 10, "business": 10, "edge": 10, "system_design": 13,
    }
    assert Counter(language for item in THIRD_WAVE for language in item["solutions"]) == {
        "python": 27, "java": 7, "javascript": 7, "go": 6, "cpp": 6,
    }
    assert len({item["slug"] for item in CATALOG}) == len(CATALOG)
    assert len({item["title"] for item in CATALOG}) == len(CATALOG)


@pytest.mark.parametrize("item", SECOND_WAVE + THIRD_WAVE, ids=lambda item: item["slug"])
def test_single_language_wave_shape(item):
    (language,) = item["solutions"]
    assert set(item["starters"]) == {language}
    assert item["starters"][language] != item["solutions"][language]
    assert len(item["hints"]) == 3 and item["explanation"] == " ".join(item["hints"][1:])
    assert len(item["tests"]) >= 5
    assert [test["hidden"] for test in item["tests"][:2]] == [False, False]
    assert all(test["hidden"] for test in item["tests"][2:])


@pytest.mark.parametrize("item", PYTHON_ADDITIONS, ids=lambda item: item["slug"])
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
