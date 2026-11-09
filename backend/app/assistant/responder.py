"""Deterministic debugging responses built only from the structured context (PRD 8.6 fallback).

Used when no model is configured, when the provider fails, or to backfill a section the model
answered unusably. It never uses reference solutions, explanations, rubrics or curated hints.
"""
import json
import re

from app import taxonomy
from app.assistant.errors import interpret_error, locate_error
from app.config import settings

TITLES = {
    "what_changed": "What changed",
    "why_not_resolved": "Why it still fails",
    "unsatisfied_requirement": "Requirement to re-check",
    "likely_code_path": "Where to look",
    "failing_tests": "Failing tests",
    "error": "What the error means",
    "reproduction": "How to reproduce it",
    "answer": "Answer",
    "concept": "Concept",
    "hint": "A nudge",
    "diagnosis_review": "Diagnosis review",
    "documentation": "Relevant documentation",
    "next_step": "Next debugging step",
}
INTENT_SECTIONS = {
    "why_fix_failed": ["what_changed", "why_not_resolved", "unsatisfied_requirement", "likely_code_path",
                       "documentation", "next_step"],
    "review_patch": ["what_changed", "why_not_resolved", "unsatisfied_requirement", "likely_code_path",
                     "documentation", "next_step"],
    "identify_failing_test": ["failing_tests", "unsatisfied_requirement", "next_step"],
    "explain_runtime_error": ["error", "likely_code_path", "documentation", "next_step"],
    "reproduction_strategy": ["reproduction", "documentation", "next_step"],
    "explain_problem": ["answer", "next_step"],
    "explain_concept": ["concept", "documentation", "next_step"],
    "find_documentation": ["answer", "documentation", "next_step"],
    "progressive_hint": ["hint", "documentation", "next_step"],
    "review_diagnosis": ["diagnosis_review", "next_step"],
}
STOP = set("""
the and for with that this from into when then than are was were has have had not but all any each its it
return returns value values input inputs output data list lists number numbers case cases test tests should
must can may will would only per one two use using used result results given contains include includes
""".split())
CONSTRAINT = set("""
never must only least most empty negative zero duplicate duplicates ignore unique exactly once invalid missing
null none limit maximum minimum before after repeated retry retries concurrent same order sorted positive
""".split())
REPRODUCTION = {
    "race_condition": "Run several operations concurrently against the same shared state with a tight limit "
                      "(for example two requests for the last unit) and check the invariant after they finish.",
    "deadlock": "Run the smallest workload where two operations wait on each other and add a timeout so the hang shows.",
    "retry_idempotency": "Deliver the same request or event twice, including after a simulated timeout, and check "
                         "that its effect happens only once.",
    "boundary_condition": "Try the smallest inputs: empty collections, zero, a single element, and exact limit values.",
    "numeric_precision": "Use values near the type limits, or fractional amounts that do not divide evenly.",
    "time_handling": "Use timestamps with different UTC offsets or around a daylight-saving change, and compare "
                     "instants rather than strings.",
    "caching": "Write a value, read it through the cache, update it, and read it again; a stale read reproduces the bug.",
    "nullability": "Omit an optional field, or pass null/None/nil where the code assumes a value.",
    "runtime_exception": "Feed the input that crashed into the function directly and read the full error output.",
    "serialization": "Round-trip a value with special characters, very large numbers, or nested data.",
    "resource_leak": "Make several calls fail in a row and check that every acquired resource is released afterwards.",
    "database_transactions": "Make the second step of a multi-step update fail and check that no partial change remains.",
    "validation": "Send invalid or out-of-range values and check that the business rule still holds.",
    "authorization": "Repeat the request as a user who should be refused and check that the action is rejected.",
    "distributed_consistency": "Deliver the same events in a different order, or twice, and compare the final states.",
    "state_corruption": "Call the code twice in a row with the same input and check that the second call is unaffected.",
}
NEXT_STEPS = {
    None: "Run the public tests, compare expected and actual output, then record your diagnosis.",
    "compile_error": "Fix the compile error at the reported line, then run the public tests again.",
    "timeout": "Run one small input and add a bound to the loop, or make sure every lock and wait is released.",
    "memory": "Find the collection that keeps growing and bound it, then rerun one small input.",
    "output_limit": "Remove the extra prints from standard output, then run again.",
}


def _words(text: str) -> set[str]:
    words = set()
    for word in re.findall(r"[a-z][a-z0-9_]+", (text or "").lower()):
        if len(word) < 3 or word in STOP:
            continue
        for suffix in ("ing", "es", "ed", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[: -len(suffix)]
                break
        words.add(word)
    return words


def _code(text: str) -> str:
    return "`" + text.replace("`", "'") + "`"


def _difference_signals(expected_text: str, actual_text: str) -> set[str]:
    """Words describing how an actual result differs from the expected one (for example a negative total)."""
    try:
        expected, actual = json.loads(expected_text), json.loads(actual_text)
    except (TypeError, ValueError):
        return set()
    signals: set[str] = set()

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def walk(want, got, key=""):
        if isinstance(want, dict) and isinstance(got, dict):
            for name, value in want.items():
                if name not in got:
                    signals.update({"missing", name})
                else:
                    walk(value, got[name], name)
        elif isinstance(want, list) and isinstance(got, list):
            if len(got) > len(want):
                signals.update({"duplicate", "once", "unique", "ignore", "only", key})
            elif len(got) < len(want):
                signals.update({"missing", "every", "include", key})
            else:
                for left, right in zip(want, got, strict=True):
                    walk(left, right, key)
        elif number(want) and number(got):
            if got < 0 <= want:
                signals.update({"negative", "never", "zero", key})
            elif got > want:
                signals.update({"exceed", "most", "maximum", "limit", key})
            elif got < want:
                signals.update({"least", "minimum", key})
        elif got is None and want is not None:
            signals.update({"missing", "null", "none", key})
        elif want != got and key:
            signals.add(key)

    walk(expected, actual)
    return _words(" ".join(signal for signal in signals if signal))


def match_requirement(context: dict) -> tuple[str, str] | None:
    """The requirement most related to the observed failure, and why it was chosen."""
    requirements = context["problem"]["requirements"]
    execution = context.get("execution")
    if not requirements or not execution or execution["failure_type"] == "none":
        return None
    difference, output, names, inputs = set(), set(), set(), set()
    for case in execution["failing_public"]:
        difference |= _difference_signals(case["expected"], case["actual"])
        output |= _words(case["expected"]) | _words(" ".join(case["failed_assertions"]))
        names |= _words(case["name"])
        inputs |= _words(case["input"])
    if execution["message"]:
        lines = execution["message"].splitlines()
        names |= _words(lines[-1] if lines else "")
    hidden_only = not execution["failing_public"] and execution["hidden_failed"] > 0
    best, best_score = None, 0.0
    for requirement in requirements:
        words = _words(requirement)
        score = (2.0 * len(words & difference) + 1.5 * len(words & output) + 1.0 * len(words & names)
                 + 0.5 * len(words & inputs) + (0.5 * len(words & CONSTRAINT) if hidden_only else 0))
        if score > best_score:
            best, best_score = requirement, score
    if best is None:
        return None
    reason = ("hidden checks fail, and this requirement states a condition the visible examples may not cover"
              if hidden_only else "the failing case's result differs from what it requires")
    return best, reason


def what_changed(context: dict) -> str:
    code = context["code"]
    stats = code["diff_stats"]
    if stats["unchanged"]:
        return "Your current code is identical to the starter, so the original defect is still present."
    text = f"Compared with the starter you added {stats['added']} line(s) and removed {stats['removed']}"
    lines = stats.get("changed_original_lines") or []
    if lines:
        text += f", around starter line {lines[0]}" + (f"–{lines[-1]}" if lines[-1] != lines[0] else "")
    if code["changed_identifiers"]:
        text += ", touching " + ", ".join(_code(name) for name in code["changed_identifiers"][:5])
    text += "."
    execution = context.get("execution")
    if execution is not None and not execution.get("matches_current_code", True):
        text += " The latest evaluated run used different code than your editor, so run again to test these edits."
    return text


def why_not_resolved(context: dict) -> str:
    execution = context.get("execution")
    language = context["problem"]["language"]
    if execution is None:
        return "There is no evaluated run yet. Run the public tests to see how your change behaves."
    kind = execution["failure_type"]
    if kind == "none":
        if execution["kind"] == "run":
            return "Your latest public run passed. Submit the fix to check the hidden cases."
        return "Your latest full submission passed every public and hidden case."
    if kind == "behavioral":
        parts = []
        for case in execution["failing_public"][:2]:
            sentence = f"\"{case['name']}\" expected {case['expected']} but your code returned {case['actual']}."
            if case["failed_assertions"]:
                sentence += " Failed state checks: " + ", ".join(_code(path) for path in case["failed_assertions"]) + "."
            parts.append(sentence)
        if execution["hidden_failed"] and execution["failing_public"]:
            parts.append(f"{execution['hidden_failed']} of {execution['hidden_total']} hidden cases also fail.")
        elif execution["hidden_failed"]:
            parts.append(f"All visible examples pass, but {execution['hidden_failed']} of {execution['hidden_total']} "
                         "hidden cases fail. Hidden inputs stay private, so compare your logic with each requirement, "
                         "especially edge conditions.")
        return " ".join(parts) or "The returned values do not match the expected results."
    if kind in {"runtime_error", "compile_error"}:
        interpreted = interpret_error(execution["message"], language)
        located = locate_error(execution["message"], language, context["code"]["current"])
        if interpreted is None:
            if execution["failing_public_count"] == 0 and execution["hidden_failed"]:
                return ("A hidden case crashed while every visible example ran. Its input stays private, so look for "
                        "inputs the examples do not cover: empty collections, zero, missing or null fields.")
            return execution["error"] or "The program stopped with an error before returning a result."
        prefix = "The code does not compile" if kind == "compile_error" else "The program stopped with"
        text = f"{prefix} {interpreted['type']}: {interpreted['meaning']}."
        if located:
            text += f" It is raised at line {located['line']}: {_code(located['text'])}."
        return text
    return {
        "timeout": "Execution exceeded the time limit. Look for a loop whose exit condition never becomes true, a "
                   "lock or wait that is never released, or work that grows much faster than the input.",
        "memory": "Execution exceeded the memory limit. Look for a collection that grows without bound.",
        "output_limit": "The program printed too much output. Only the JSON result belongs on standard output.",
    }.get(kind, execution["error"] or "The evaluation did not pass.")


def _input_keys(execution: dict) -> list[str]:
    keys = []
    for case in execution.get("failing_public", []):
        keys += re.findall(r"\"([A-Za-z_][A-Za-z0-9_]*)\":", case["input"])
    return list(dict.fromkeys(keys))


def likely_code_path(context: dict) -> str:
    code = context["code"]["current"]
    lines = code.splitlines()
    execution = context.get("execution") or {}
    language = context["problem"]["language"]
    located = locate_error(execution.get("message") or "", language, code)
    if located:
        return (f"Line {located['line']}: {_code(located['text'])} is where the error is raised. "
                "Trace where each value on that line comes from.")
    parts = []
    keys = _input_keys(execution)
    hits = [(number, line.strip()) for number, line in enumerate(lines, 1)
            if keys and any(re.search(rf"\b{re.escape(key)}\b", line) for key in keys)][:3]
    if hits:
        parts.append("Lines that read the fields of the failing case: " +
                     "; ".join(f"line {number} {_code(text)}" for number, text in hits) + ".")
    returns = [(number, line.strip()) for number, line in enumerate(lines, 1) if re.search(r"\breturn\b", line)][:2]
    if returns:
        parts.append("The result is produced at " +
                     "; ".join(f"line {number} {_code(text)}" for number, text in returns) +
                     ", so trace each returned field back to its inputs.")
    stats = context["code"]["diff_stats"]
    if stats["unchanged"]:
        parts.append("You have not edited the starter yet; the defect is still somewhere in its logic.")
    return " ".join(parts) or "Start from the function that builds the returned value and trace it back to the inputs."


def failing_tests(context: dict) -> str:
    execution = context.get("execution")
    if execution is None:
        return "No evaluated run yet, so no failing test is known. Run the public tests first."
    if execution["failure_type"] == "none":
        return "No test failed in your latest evaluated run."
    names = [f"\"{case['name']}\" ({case['status'].replace('_', ' ')})" for case in execution["failing_public"]]
    text = ("Failing public cases: " + ", ".join(names) + "." if names else "Every public case passed.")
    if execution["hidden_evaluated"]:
        text += f" Hidden cases: {execution['hidden_failed']} of {execution['hidden_total']} failed; their inputs stay private."
    elif execution["kind"] == "run":
        text += " This was a public run, so hidden cases were not evaluated."
    return text


def error_section(context: dict) -> str:
    execution = context.get("execution")
    if execution is None:
        return "There is no evaluated run yet, so there is no error output to explain."
    interpreted = interpret_error(execution["message"], context["problem"]["language"])
    if interpreted is None:
        if execution["failure_type"] in {"behavioral", "none"}:
            return ("Your latest run did not raise an error: it returned a result. " + why_not_resolved(context))
        return why_not_resolved(context)
    return f"{interpreted['type']}: {interpreted['meaning']}. {interpreted['check']}"


def reproduction(context: dict) -> str:
    problem = context["problem"]
    execution = context.get("execution") or {}
    steps = []
    if execution.get("failing_public"):
        case = execution["failing_public"][0]
        steps.append(f"Start from the public case \"{case['name']}\": input {case['input']}. It returns "
                     f"{case['actual']} instead of {case['expected']}.")
    elif problem["examples"]:
        steps.append(f"Start from the public example \"{problem['examples'][0]['name']}\" and change one field at a time.")
    for category in problem["bug_categories"]:
        if category in REPRODUCTION:
            steps.append(REPRODUCTION[category])
            break
    else:
        steps.append("Find the smallest input that still breaks one requirement.")
    steps.append("State the expected result before running it, then run the public tests to confirm that the "
                 "failure is reproducible.")
    return " ".join(f"{index}. {step}" for index, step in enumerate(steps, 1))


def explain_problem(context: dict) -> str:
    problem = context["problem"]
    text = f"{problem['summary']} The fix must satisfy {len(problem['requirements'])} requirement(s): " + " ".join(
        f"({index}) {line}" for index, line in enumerate(problem["requirements"], 1))
    text += (f" {problem['public_test_count']} public example(s) show the expected output; "
             f"{problem['hidden_test_count']} hidden case(s) check that the fix generalizes.")
    return text


def concept(context: dict) -> str:
    names = []
    for category in context["problem"]["bug_categories"][:2]:
        info = taxonomy.BUG_CATEGORIES.get(category)
        if info:
            names.append(f"{info['name']}: {info['description']}")
    concepts = [taxonomy.CONCEPT_GRAPH[key]["name"] for key in taxonomy.concepts_for(context["problem"]["bug_categories"])]
    text = " ".join(names) or "This challenge exercises careful reasoning about the stated requirements."
    if concepts:
        text += " Related concepts: " + ", ".join(dict.fromkeys(concepts[:4])) + "."
    return text


def hint(context: dict) -> str:
    problem = context["problem"]
    category = next((taxonomy.BUG_CATEGORIES[c] for c in problem["bug_categories"] if c in taxonomy.BUG_CATEGORIES), None)
    text = (f"This challenge is about {category['name'].lower()}: {category['description'].lower()}"
            if category else "Compare each requirement with what the code actually does.")
    if problem["skills"]:
        text += f" A useful technique here is {problem['skills'][0].lower()}."
    text += (f" Progressive, documentation-backed hints unlock from the Hint button after "
             f"{settings.hint_failure_threshold} unsuccessful evaluations.")
    return text


def diagnosis_review(context: dict) -> str:
    diagnosis = context.get("diagnosis")
    if not diagnosis:
        return ("You have not submitted a diagnosis yet. Describe the defect category, the root cause, the affected "
                "component, the violated invariant, your proposed correction, and how you would reproduce the failure.")
    identifiers = {name.lower() for name in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", context["code"]["current"])}
    notes = []
    root = diagnosis["root_cause"] or ""
    if len(root) < 40 or not re.search(r"\b(because|when|since|so|before|after|without|instead)\b", root, re.I):
        notes.append("Root cause: explain the mechanism (what happens, and when), not only the symptom.")
    else:
        notes.append("Root cause: it describes a mechanism, which is what a diagnosis needs.")
    component = (diagnosis["affected_component"] or "").lower()
    if not any(name in component for name in identifiers):
        notes.append("Affected component: name the function, variable or step in the code that is wrong.")
    if not re.search(r"\b(must|never|always|at most|at least|exactly|only|should|cannot|can't)\b",
                     diagnosis["violated_invariant"] or "", re.I):
        notes.append("Invariant: state it as a rule that must always hold (for example \"X must never ...\").")
    if not re.search(r"\b(check|validate|lock|move|handle|guard|use|replace|add|remove|clamp|reject|make)\b",
                     diagnosis["proposed_correction"] or "", re.I):
        notes.append("Correction: describe the change you intend to make, not only the goal.")
    if not re.search(r"\d|\"|'|\b(input|case|test|empty|twice|concurrent|null|none|zero)\b",
                     diagnosis["reproduction_strategy"] or "", re.I):
        notes.append("Reproduction: give a concrete input or sequence that triggers the failure.")
    execution = context.get("execution") or {}
    interpreted = interpret_error(execution.get("message") or "", context["problem"]["language"])
    if interpreted:
        error_words = {word for word in re.findall(r"[a-z]{3,}", interpreted["type"].lower())
                       if word not in {"panic", "error", "fatal", "exception"}} or {interpreted["type"].lower()}
        if not any(word in (root + " " + component).lower() for word in error_words):
            notes.append(f"Your latest run raises {interpreted['type']}; check that your root cause explains that error.")
    return " ".join(notes)


def documentation(docs: list[dict]) -> str:
    if not docs:
        return "No matching official documentation was found for this question."
    lines = []
    for index, doc in enumerate(docs, 1):
        sentence = re.split(r"(?<=[.!?])\s", doc["text"].strip(), maxsplit=1)[0]
        lines.append(f"[{index}] {doc['title']}: {sentence}")
    return " ".join(lines)


def next_step(context: dict, intent: str) -> str:
    execution = context.get("execution")
    if intent == "review_diagnosis":
        return "Revise the weakest field, then test your hypothesis with a run that should fail for exactly that reason."
    if intent in {"explain_concept", "find_documentation"} and context.get("execution") is None:
        return "Read [1], then find the place in your code where that concept applies and run the public tests."
    if execution is None:
        return NEXT_STEPS[None]
    kind = execution["failure_type"]
    if kind in NEXT_STEPS:
        return NEXT_STEPS[kind]
    if kind == "none":
        if execution["kind"] == "run":
            return "Submit the fix to run the hidden cases."
        return "Explain your fix: why the original failed, which invariant now holds, and which regression tests matter."
    if kind == "runtime_error":
        located = locate_error(execution["message"], context["problem"]["language"], context["code"]["current"])
        where = f" at line {located['line']}" if located else ""
        return f"Reproduce the crash with the failing input, then guard or validate the value{where} before it is used."
    if execution["failing_public"]:
        case = execution["failing_public"][0]
        return (f"Trace \"{case['name']}\" by hand: follow each line that computes the returned fields and find the "
                f"first step where a value differs from {case['expected']}.")
    return ("Write one extra case for an edge condition from the requirements (empty input, zero, negative values, "
            "duplicates or limits), predict its output, and check your code against it.")


def deterministic_response(context: dict, intent: str, docs: list[dict]) -> list[dict]:
    builders = {
        "what_changed": lambda: what_changed(context),
        "why_not_resolved": lambda: why_not_resolved(context),
        "unsatisfied_requirement": lambda: (lambda match: f"\"{match[0]}\" — {match[1]}." if match else "")(
            match_requirement(context)),
        "likely_code_path": lambda: likely_code_path(context),
        "failing_tests": lambda: failing_tests(context),
        "error": lambda: error_section(context),
        "reproduction": lambda: reproduction(context),
        "answer": lambda: (explain_problem(context) if intent == "explain_problem"
                           else "These official references match this challenge and your latest result."),
        "concept": lambda: concept(context),
        "hint": lambda: hint(context),
        "diagnosis_review": lambda: diagnosis_review(context),
        "documentation": lambda: documentation(docs),
        "next_step": lambda: next_step(context, intent),
    }
    sections = []
    for key in INTENT_SECTIONS.get(intent, INTENT_SECTIONS["why_fix_failed"]):
        body = builders[key]()
        if body:
            sections.append({"key": key, "title": TITLES[key], "body": body})
    return sections
