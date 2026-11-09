"""Mutation generation (PRD 7.3; MT-001, MT-009, MT-010): templates, safety and determinism."""
import pytest

from app.catalog import CATALOG
from app.quality.mutation import OPERATORS, changed_lines, generate, generate_mutants, python_syntax_ok


def mutants_for(language, source, **kwargs):
    return generate_mutants(language, source, max_mutants=kwargs.pop("max_mutants", 200), **kwargs)


def lines(mutants, operator):
    return [mutant["mutated_snippet"].strip() for mutant in mutants if mutant["operator"] == operator]


PYTHON = '''import threading

LOCK = threading.Lock()
MAX_RETRIES = 3


def solve(data):
    """Docstring with a < b and x + y that must never change."""
    # comment: if a >= b and c or d
    total = 0
    seen = set()
    label = f"{data['a'] + 1} items"
    for i in range(len(data["items"])):
        item = data["items"][i]
        if item is None:
            continue
        if item["id"] in seen:
            continue
        if item["qty"] >= 0 and not item["skip"]:
            total += item["qty"] * 2 - -1
        seen.add(item["id"])
    with LOCK:
        total = total + data.get("bonus", 0)
    try:
        if total > 100:
            raise ValueError("too large")
    finally:
        data["file"].close()
    return {"total": total, "ok": True, "first": data["items"][0], "label": label, "head": data["items"][1:3]}
'''


def test_python_templates_cover_every_operator_class():
    mutants = mutants_for("python", PYTHON)
    assert {mutant["operator"] for mutant in mutants} == set(OPERATORS)
    assert "if item[\"qty\"] > 0 and not item[\"skip\"]:" in lines(mutants, "comparison")
    assert "if total >= 100:" in lines(mutants, "boundary")
    assert "for i in range(len(data[\"items\"]) - 1):" in lines(mutants, "boundary")
    assert "if item[\"qty\"] >= 0 or not item[\"skip\"]:" in lines(mutants, "boolean_logic")
    assert "total -= item[\"qty\"] * 2 - -1" in lines(mutants, "arithmetic")
    assert "total += item[\"qty\"] * 2 - 1" in lines(mutants, "arithmetic")
    assert "total += item[\"qty\"] / 2 - -1" in lines(mutants, "arithmetic")
    assert "if item is not None:" in lines(mutants, "comparison")
    assert "if False:" in lines(mutants, "null_check")
    assert "total = total + data.get(\"bonus\")" in lines(mutants, "null_check")
    assert "pass" in lines(mutants, "collection")
    assert any("data[\"items\"][1]" in line for line in lines(mutants, "collection"))
    assert any("[1:3 - 1]" in line or "[1 + 1:3]" in line for line in lines(mutants, "collection"))
    assert "if not (total > 100):" in lines(mutants, "conditional")
    assert "if item[\"qty\"] >= 0 and item[\"skip\"]:" in lines(mutants, "conditional")
    assert any(line.startswith("pass") for line in lines(mutants, "error_handling"))
    assert "if True:" in lines(mutants, "concurrency")
    assert "if False:" in lines(mutants, "idempotency")
    assert "MAX_RETRIES = 4" in lines(mutants, "retry_limit")
    assert any("None" in line for line in lines(mutants, "return_value"))
    assert any("\"ok\": False" in line for line in lines(mutants, "boolean_logic"))


def test_python_never_mutates_strings_comments_docstrings_or_fstrings_and_stays_valid():
    mutants = mutants_for("python", PYTHON)
    original_lines = PYTHON.split("\n")
    protected = [index for index, line in enumerate(original_lines) if "Docstring" in line or "# comment" in line
                 or "f\"" in line]
    for mutant in mutants:
        mutated_lines = mutant["code"].split("\n")
        assert python_syntax_ok(mutant["code"]), mutant["description"]
        assert mutant["valid"] is True
        for index in protected:
            assert mutated_lines[index] == original_lines[index], mutant["description"]


def test_generation_is_deterministic_deduplicated_and_capped():
    first = mutants_for("python", PYTHON, max_mutants=10)
    second = mutants_for("python", PYTHON, max_mutants=10)
    assert [m["code"] for m in first] == [m["code"] for m in second]
    assert len(first) == 10 and [m["ordinal"] for m in first] == list(range(1, 11))
    everything = mutants_for("python", PYTHON)
    assert len({m["code_hash"] for m in everything}) == len(everything)
    assert all(m["code"] != PYTHON for m in everything)
    # The first ten rotate across operator classes instead of exhausting one class.
    assert len({m["operator"] for m in first}) >= 8


def test_critical_mutants_on_changed_lines_come_first():
    starter = "def solve(data):\n    total = 0\n    for n in data['nums'][:-1]:\n        total += n\n    return total\n"
    solution = "def solve(data):\n    total = 0\n    for n in data['nums']:\n        total += n\n    return total\n"
    assert changed_lines(starter, solution) == {3}
    mutants = mutants_for("python", solution, starter=starter)
    flags = [m["critical"] for m in mutants]
    assert flags == sorted(flags, reverse=True)
    assert all(m["line"] == 3 for m in mutants if m["critical"])
    assert not changed_lines(None, solution)


def test_operator_selection_and_unknown_operators():
    only = mutants_for("python", PYTHON, operators=["boundary"])
    assert only and {m["operator"] for m in only} == {"boundary"}
    with pytest.raises(ValueError):
        generate("python", PYTHON, operators=["shuffle"])
    with pytest.raises(ValueError):
        generate("ruby", "puts 1")


JAVA = '''import com.google.gson.*;
import java.util.*;
public class Solution {
  private static final int MAX_RETRIES = 3;
  public static synchronized JsonElement solve(JsonObject data) {
    Map<String, List<Integer>> groups = new HashMap<>();
    List<String> names = new ArrayList<>();
    String text = "a < b && c > d"; // i < n
    /* if (x == null) */
    for (int i = 0; i < data.get("n").getAsInt(); i++) names.add("x" + i);
    if (data.get("key") == null) return null;
    if (seen.contains(key)) return new JsonPrimitive(0);
    try { work(); } finally { close(); }
    return new JsonPrimitive(names.size() >= 2 && !names.isEmpty() ? names.get(0).length() : -1);
  }
}
'''


def test_java_tokenizer_skips_generics_strings_comments():
    mutants = mutants_for("java", JAVA)
    for mutant in mutants:
        assert 'String text = "a < b && c > d"; // i < n' in mutant["code"]
        assert "/* if (x == null) */" in mutant["code"]
        assert "Map<String, List<Integer>> groups = new HashMap<>();" in mutant["code"] or mutant["operator"] in (
            "collection", "concurrency")
    assert "for (int i = 0; i <= data.get(\"n\").getAsInt(); i++) names.add(\"x\" + i);" in lines(mutants, "boundary")
    assert "for (int i = 0; i < data.get(\"n\").getAsInt(); i--) names.add(\"x\" + i);" in lines(mutants, "arithmetic")
    assert any("names.size() > 2" in line for line in lines(mutants, "comparison"))
    assert any("|| !names.isEmpty()" in line for line in lines(mutants, "boolean_logic"))
    assert any("names.size() >= 2 && names.isEmpty()" in line for line in lines(mutants, "conditional"))
    assert any("false && (data.get(\"key\") == null)" in line for line in lines(mutants, "null_check"))
    assert any("false && (seen.contains(key))" in line for line in lines(mutants, "idempotency"))
    assert any("finally { }" in line for line in lines(mutants, "resource_cleanup"))
    assert any("public static JsonElement solve" in line for line in lines(mutants, "concurrency"))
    assert "private static final int MAX_RETRIES = 4;" in lines(mutants, "retry_limit")
    assert any("names.get(1)" in line for line in lines(mutants, "collection"))
    assert any(": 1);" in line for line in lines(mutants, "arithmetic"))
    # Generic brackets are never treated as comparisons.
    assert not any("Map<=" in m["code"] or "List<=" in m["code"] or "HashMap<=" in m["code"] for m in mutants)


CPP = '''#include <nlohmann/json.hpp>
#include <vector>
#include <mutex>
using nlohmann::json;
std::mutex m;
json solve(const json& data) {
    std::lock_guard<std::mutex> guard(m);
    auto values = data.at("values").get<std::vector<int>>();
    std::vector<int> out;
    for (size_t i = 0; i < values.size(); i++) if (values[i] > 0) out.push_back(values[i] * 2);
    return static_cast<int>(out.size()) >> 1 << 1 == 0 ? json(out) : json(values);
}
'''


def test_cpp_tokenizer_skips_templates_includes_and_shifts():
    mutants = mutants_for("cpp", CPP)
    assert mutants
    for mutant in mutants:
        assert "#include <nlohmann/json.hpp>" in mutant["code"]
        assert "get<std::vector<int>>()" in mutant["code"] or mutant["operator"] == "concurrency"
        if mutant["operator"] != "return_value":
            assert "static_cast<int>(" in mutant["code"]
            assert ">> 1 << 1" in mutant["code"]
    assert any("i <= values.size()" in line for line in lines(mutants, "boundary"))
    assert any("values[i] >= 0" in line for line in lines(mutants, "boundary"))
    assert any(";" == line.strip() or line.strip().startswith("for") for line in lines(mutants, "collection"))
    assert any("return {};" in line for line in lines(mutants, "return_value"))
    assert lines(mutants, "concurrency")


GO = '''package main
import ("strings"; "sync")
var mu sync.Mutex
var maxRetries = 3
func Solve(data map[string]interface{}) interface{} {
    mu.Lock()
    defer mu.Unlock()
    ch := make(chan int, 1)
    ch <- 1
    x := <-ch
    s := "a < b"
    seen := map[string]bool{}
    if seen["k"] { return nil }
    if v, ok := data["v"]; ok && v != nil { x += len(strings.Repeat("a", 2)) }
    total := 0
    for i := 0; i < x; i++ { total = total + i }
    return total
}
'''


def test_go_tokenizer_handles_channels_short_declarations_and_locks():
    mutants = mutants_for("go", GO)
    for mutant in mutants:
        assert 's := "a < b"' in mutant["code"]
        assert "<=-" not in mutant["code"] and "x := <-ch" in mutant["code"]
        assert "ch <- 1" in mutant["code"]
    assert any("i <= x" in line for line in lines(mutants, "boundary"))
    assert any("total = total - i" in line for line in lines(mutants, "arithmetic"))
    pair = [m for m in mutants if m["operator"] == "concurrency"]
    assert len(pair) == 1 and "mu.Lock()" not in pair[0]["code"] and "mu.Unlock()" not in pair[0]["code"]
    assert any("false && (seen[\"k\"])" in line for line in lines(mutants, "idempotency"))
    assert any("true || (ok && v != nil)" in line for line in lines(mutants, "null_check"))
    assert "var maxRetries = 4" in lines(mutants, "retry_limit")
    assert any("Repeat(\"a\", 3)" in line for line in lines(mutants, "collection"))


JS = '''const LIMIT = 2;
function solve(data) {
  const re = /a<b|c>d/g;
  const msg = `total ${data.a < 1 ? "small" : "big"}`;
  if (data.items === undefined) return [];
  const seen = new Set();
  const out = [];
  for (const item of data.items) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    out.push(item.value !== null ? item.value * 2 : 0);
  }
  return out.slice(0, LIMIT);
}
module.exports = { solve };
'''


def test_javascript_tokenizer_skips_regex_and_template_literals():
    mutants = mutants_for("javascript", JS)
    for mutant in mutants:
        assert "/a<b|c>d/g" in mutant["code"]
        assert 'total ${data.a < 1 ? "small" : "big"}' in mutant["code"]
    assert any("data.items !== undefined" in line for line in lines(mutants, "comparison"))
    assert any("item.value === null" in line for line in lines(mutants, "comparison"))
    assert any("false && (seen.has(item.id))" in line for line in lines(mutants, "idempotency"))
    assert any(line.strip() == ";" for line in lines(mutants, "collection"))
    assert any("return null;" in line for line in lines(mutants, "return_value"))
    assert any("out.slice(1, LIMIT)" in line for line in lines(mutants, "collection"))


@pytest.mark.parametrize("item", CATALOG, ids=lambda item: item["slug"])
def test_every_catalog_variant_generates_valid_deterministic_mutants(item):
    for language, solution in item["solutions"].items():
        first = generate(language, solution, starter=item["starters"].get(language), max_mutants=24)
        second = generate(language, solution, starter=item["starters"].get(language), max_mutants=24)
        assert [m["code"] for m in first.mutants] == [m["code"] for m in second.mutants]
        assert first.mutants, f"{item['slug']} {language} produced no mutants"
        assert len(first.mutants) <= 24
        for mutant in first.mutants:
            assert mutant["code"] != solution
            assert mutant["operator"] in OPERATORS
            if language == "python":
                assert mutant["valid"] is True, (item["slug"], mutant["description"])
