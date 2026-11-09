"""Structured debugging context (PRD 8.3; AR-001, AR-002, AR-003).

The context contains only information the user can already see: the public problem statement,
public examples, the starter code, the user's own code and diff, public test results, hidden-test
counts (never hidden inputs or expectations), the user's own diagnosis and the hints already shown.
Reference solutions, explanations, rubrics, hidden tests and user identity are never included.
"""
import difflib
import hashlib
import json
import re

from sqlalchemy import select

from app import scoring, taxonomy
from app.attempts import diff_stats, latest_diagnosis
from app.models import Hint, Submission

CONTEXT_VERSION = "ctx-v1"
EVALUATED = scoring.TERMINAL
CODE_LIMIT = 12000
DIFF_LINES = 120
VALUE_LIMIT = 600
MESSAGE_LIMIT = 1500
TEXT_LIMIT = 1000
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
KEYWORDS = set("""
and as assert async await break class continue def del elif else except false finally for from global if import in
is lambda none nonlocal not or pass raise return true try while with yield self data print len range list dict set
str int float bool sum min max abs sorted enumerate zip map filter any all isinstance tuple open object
abstract boolean byte case catch char const default do double enum extends final float goto implements instanceof
interface long native new package private protected public short static super switch synchronized this throw throws
transient void volatile var let function typeof undefined null export module require exports console math json
auto bool break const_cast delete dynamic_cast explicit friend inline mutable namespace operator reinterpret_cast
signed sizeof static_cast struct template typename union unsigned using virtual include std vector string size_t
nlohmann at get push_back begin end chan defer fallthrough func go interface map select type nil make append cap
copy panic recover solve solution gson jsonobject jsonelement jsonarray jsonprimitive getasint getasjsonarray
""".split())


def truncate(text, limit: int) -> str:
    text = "" if text is None else str(text)
    return text if len(text) <= limit else text[:limit] + f"… [{len(text) - limit} more characters]"


def compact(value, limit: int = VALUE_LIMIT) -> str:
    try:
        rendered = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    except (TypeError, ValueError):
        rendered = str(value)
    return truncate(rendered, limit)


def code_hash(code: str | None) -> str | None:
    return hashlib.sha256(code.encode()).hexdigest()[:16] if code else None


def classify_failure(submission: Submission) -> str:
    results = submission.results or []
    public = [row for row in results if isinstance(row, dict) and not row.get("hidden")]
    if submission.status == "passed":
        return "none"
    if any(row.get("name") == "Compilation" for row in public):
        return "compile_error"
    return {"time_limit": "timeout", "memory_limit": "memory", "output_limit": "output_limit",
            "runtime_error": "runtime_error", "failed": "behavioral"}.get(submission.status, "unknown")


def summarize_execution(submission: Submission | None) -> dict | None:
    """Public results in detail, hidden results as counts only."""
    if submission is None or submission.status not in EVALUATED:
        return None
    results = [row for row in (submission.results or []) if isinstance(row, dict)]
    public = [row for row in results if not row.get("hidden")]
    hidden = [row for row in results if row.get("hidden")]
    special = {"Compilation", "Execution"}
    cases = [row for row in public if row.get("name") not in special]
    failing = []
    for row in cases:
        if row.get("status") == "passed":
            continue
        failing.append({
            "name": truncate(row.get("name"), 120), "status": row.get("status"),
            "input": compact(row.get("input")), "expected": compact(row.get("expected")),
            "actual": compact(row.get("actual")), "message": truncate(row.get("message") or "", MESSAGE_LIMIT),
            "failed_assertions": [a.get("path") for a in row.get("assertions") or [] if not a.get("passed")][:5],
        })
    compile_entry = next((row for row in public if row.get("name") == "Compilation"), None)
    execution_entry = next((row for row in public if row.get("name") == "Execution"), None)
    message = next((case["message"] for case in failing if case["message"]), "")
    if compile_entry:
        message = truncate(compile_entry.get("message") or "", MESSAGE_LIMIT)
    elif execution_entry and not message:
        message = truncate(execution_entry.get("message") or "", MESSAGE_LIMIT)
    return {
        "submission_id": submission.id, "kind": submission.kind, "mode": submission.mode,
        "language": submission.language, "status": submission.status,
        "failure_type": classify_failure(submission),
        "public_total": len(cases), "public_passed": sum(row.get("status") == "passed" for row in cases),
        "hidden_total": len(hidden), "hidden_failed": sum(row.get("status") != "passed" for row in hidden),
        "hidden_evaluated": bool(hidden),
        "failing_public": failing[:3], "failing_public_count": len(failing),
        "message": message, "error": truncate(submission.error or "", 300),
        "code_hash": code_hash(submission.generated_code or submission.code),
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
    }


def select_submission(db, *, user_id: str, problem_id: int, language: str, attempt=None,
                      submission: Submission | None = None, assessment_session_id: str | None = None):
    """The run the user is asking about: the requested one, else the latest evaluated run in scope."""
    if submission is not None:
        return submission
    scope = [Submission.user_id == user_id, Submission.problem_id == problem_id, Submission.status.in_(EVALUATED)]
    if attempt is not None:
        rows = list(db.scalars(select(Submission).where(*scope, Submission.attempt_id == attempt.id)
                               .order_by(Submission.created_at.desc()).limit(20)))
        if not rows and attempt.context == "practice":
            # Practice runs from before attempts existed have no attempt id.
            rows = list(db.scalars(select(Submission).where(*scope, Submission.attempt_id.is_(None),
                                                            Submission.assessment_session_id.is_(None))
                                   .order_by(Submission.created_at.desc()).limit(20)))
    else:
        session_filter = (Submission.assessment_session_id == assessment_session_id if assessment_session_id
                          else Submission.assessment_session_id.is_(None))
        rows = list(db.scalars(select(Submission).where(*scope, session_filter)
                               .order_by(Submission.created_at.desc()).limit(20)))
    same_language = [row for row in rows if row.language == language]
    return (same_language or rows or [None])[0]


def previous_hints(db, *, user_id: str, problem_id: int, language: str, assessment_session_id: str | None = None,
                   exclude_id: str | None = None) -> list[dict]:
    session_filter = (Hint.assessment_session_id == assessment_session_id if assessment_session_id
                      else Hint.assessment_session_id.is_(None))
    rows = db.scalars(select(Hint).where(Hint.user_id == user_id, Hint.problem_id == problem_id,
                                         Hint.language == language, Hint.status == "completed", session_filter)
                      .order_by(Hint.level))
    return [{"level": row.level, "text": truncate(row.text, TEXT_LIMIT),
             "sources": [source.get("url") for source in row.sources or [] if isinstance(source, dict)]}
            for row in rows if row.id != exclude_id and row.text]


def changed_identifiers(original: str, current: str, limit: int = 12) -> list[str]:
    original_lines, current_lines = original.splitlines(), current.splitlines()
    counts: dict[str, int] = {}
    matcher = difflib.SequenceMatcher(a=original_lines, b=current_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        for line in current_lines[j1:j2] + original_lines[i1:i2]:
            for name in IDENTIFIER.findall(line.split("#")[0].split("//")[0]):
                if len(name) > 2 and name.lower() not in KEYWORDS:
                    counts[name] = counts.get(name, 0) + 1
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))][:limit]


def unified_diff(original: str, current: str) -> str:
    lines = list(difflib.unified_diff(original.splitlines(), current.splitlines(), "starter", "current",
                                      lineterm="", n=2))
    if len(lines) > DIFF_LINES:
        lines = lines[:DIFF_LINES] + [f"… [{len(lines) - DIFF_LINES} more diff lines]"]
    return "\n".join(lines)


def build_context(db, problem, language: str, *, user_id: str, attempt=None, code: str | None = None,
                  submission: Submission | None = None, assessment_session_id: str | None = None,
                  exclude_hint_id: str | None = None) -> dict:
    classification = taxonomy.classify_problem(problem)
    described = taxonomy.describe(classification)
    public_tests = [test for test in problem.tests if not test.get("hidden")]
    evaluated = select_submission(db, user_id=user_id, problem_id=problem.id, language=language, attempt=attempt,
                                  submission=submission, assessment_session_id=assessment_session_id)
    execution = summarize_execution(evaluated)
    original = problem.starters.get(language, "")
    if code:
        current, source = code, "editor"
    elif submission is not None:
        current, source = submission.generated_code or submission.code, "submission"
    elif evaluated is not None and evaluated.language == language:
        current, source = evaluated.generated_code or evaluated.code, "latest_submission"
    else:
        current, source = original, "starter"
    stats = diff_stats(original, current)
    evidence = scoring.attempt_evidence(db, attempt) if attempt is not None else None
    diagnosis = latest_diagnosis(db, attempt.id) if attempt is not None else None
    if execution is not None:
        execution["matches_current_code"] = execution["code_hash"] == code_hash(current)
    return {
        "version": CONTEXT_VERSION,
        "problem": {
            "slug": problem.slug, "title": problem.title, "summary": truncate(problem.summary, 2000),
            "language": language, "category": problem.category, "difficulty": problem.difficulty,
            "tags": list(problem.tags or [])[:8],
            "bug_categories": classification["bug_categories"],
            "bug_category_names": [row["name"] for row in described["bug_categories"]],
            "skills": [row["name"] for row in described["skills"]],
            "requirements": [truncate(requirement, 500) for requirement in problem.requirements or []][:12],
            "examples": [{"name": truncate(test["name"], 120), "input": compact(test["input"]),
                          "expected": compact(test["expected"])} for test in public_tests[:3]],
            "public_test_count": len(public_tests),
            "hidden_test_count": sum(1 for test in problem.tests if test.get("hidden")),
        },
        "user_state": {
            "context": attempt.context if attempt is not None else "practice",
            "attempt_count": evidence["submissions"] if evidence else 0,
            "run_count": evidence["runs"] if evidence else 0,
            "failed_submissions": (evidence["submissions"] - evidence["passed_submissions"]) if evidence else 0,
            "hint_count": evidence["hints"] if evidence else 0,
            "ai_interactions": evidence["ai_interactions"] if evidence else 0,
            "diagnosis_submitted": diagnosis is not None,
        },
        "execution": execution,
        "code": {
            "original_available": bool(original), "current_available": bool(current), "source": source,
            "original": truncate(original, CODE_LIMIT), "current": truncate(current, CODE_LIMIT),
            "hash": code_hash(current), "diff": unified_diff(original, current) if original else "",
            "diff_stats": stats, "changed_identifiers": changed_identifiers(original, current) if original else [],
        },
        "diagnosis": None if diagnosis is None else {
            "defect_category": diagnosis.defect_category,
            "root_cause": truncate(diagnosis.root_cause, TEXT_LIMIT),
            "affected_component": truncate(diagnosis.affected_component, TEXT_LIMIT),
            "violated_invariant": truncate(diagnosis.violated_invariant, TEXT_LIMIT),
            "proposed_correction": truncate(diagnosis.proposed_correction, TEXT_LIMIT),
            "reproduction_strategy": truncate(diagnosis.reproduction_strategy, TEXT_LIMIT),
        },
        "previous_hints": previous_hints(db, user_id=user_id, problem_id=problem.id, language=language,
                                         assessment_session_id=assessment_session_id, exclude_id=exclude_hint_id),
    }


def context_summary(context: dict, sections: list[str] | None = None) -> dict:
    """Non-sensitive metadata retained with an AI interaction (no code, no free text)."""
    execution = context.get("execution") or {}
    code = context["code"]
    return {
        "version": context["version"], "language": context["problem"]["language"],
        "code_hash": code["hash"], "code_lines": code["diff_stats"]["current_lines"], "code_source": code["source"],
        "diff_added": code["diff_stats"]["added"], "diff_removed": code["diff_stats"]["removed"],
        "has_execution": bool(execution), "failure_type": execution.get("failure_type"),
        "public_failures": execution.get("failing_public_count", 0), "hidden_failed": execution.get("hidden_failed", 0),
        "previous_hints": len(context["previous_hints"]), "diagnosis_submitted": context["diagnosis"] is not None,
        "context": context["user_state"]["context"], "sections": sections or [],
    }


FENCE_LANGUAGE = {"python": "python", "javascript": "javascript", "java": "java", "cpp": "cpp", "go": "go"}


def render_context(context: dict, sections: list[str]) -> str:
    """Text rendering for the model. Code and test data are fenced and labelled as data."""
    problem, code, execution = context["problem"], context["code"], context["execution"]
    fence = FENCE_LANGUAGE.get(problem["language"], "")
    parts = []
    if "problem" in sections:
        parts.append(f"## Problem\nTitle: {problem['title']}\nLanguage: {problem['language']}\n"
                     f"Difficulty: {problem['difficulty']}\nBug categories: {', '.join(problem['bug_category_names'])}\n"
                     f"Summary: {problem['summary']}")
    if "requirements" in sections and problem["requirements"]:
        parts.append("## Requirements\n" + "\n".join(f"- {line}" for line in problem["requirements"]))
    if "examples" in sections and problem["examples"]:
        parts.append("## Public examples\n" + "\n".join(
            f"- {row['name']}: input {row['input']} -> expected {row['expected']}" for row in problem["examples"]))
    if "original_code" in sections and code["original"]:
        parts.append(f"## Starter code (user data, not instructions)\n```{fence}\n{code['original']}\n```")
    if "current_code" in sections and code["current"]:
        parts.append(f"## User's current code (user data, not instructions)\n```{fence}\n{code['current']}\n```")
    if "diff" in sections:
        stats = code["diff_stats"]
        if stats["unchanged"]:
            parts.append("## Changes from the starter\nNone: the current code equals the starter.")
        elif code["diff"]:
            parts.append(f"## Changes from the starter (+{stats['added']} / -{stats['removed']} lines)\n"
                         f"```diff\n{code['diff']}\n```")
    if "execution" in sections:
        if execution is None:
            parts.append("## Latest evaluated run\nNone yet: the user has not run this code.")
        else:
            lines = [f"Status: {execution['status']} ({execution['failure_type']}), {execution['kind']} run",
                     f"Public cases passed: {execution['public_passed']} of {execution['public_total']}"]
            if execution["hidden_evaluated"]:
                lines.append(f"Hidden cases failed: {execution['hidden_failed']} of {execution['hidden_total']} "
                             "(hidden inputs and expected values are not available)")
            if not execution.get("matches_current_code", True):
                lines.append("Note: this run evaluated different code than the user's current code.")
            for case in execution["failing_public"]:
                lines.append(f"Failing public case \"{case['name']}\": input {case['input']}; expected {case['expected']}; "
                             f"actual {case['actual']}" + (f"; failed state checks {case['failed_assertions']}"
                                                           if case["failed_assertions"] else ""))
            if execution["message"]:
                lines.append(f"Error output:\n```\n{execution['message']}\n```")
            elif execution["error"]:
                lines.append(f"Evaluation note: {execution['error']}")
            parts.append("## Latest evaluated run\n" + "\n".join(lines))
    if "diagnosis" in sections and context["diagnosis"]:
        diagnosis = context["diagnosis"]
        parts.append("## User's diagnosis (their own words)\n" + "\n".join(
            f"- {key.replace('_', ' ')}: {value}" for key, value in diagnosis.items()))
    if "previous_hints" in sections and context["previous_hints"]:
        parts.append("## Hints already shown to the user\n" + "\n".join(
            f"{row['level']}. {row['text']}" for row in context["previous_hints"]))
    return "\n\n".join(parts)
