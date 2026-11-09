"""Engineering Quality Score for accepted patches (PRD 10.2).

Correctness is a hard gate: only a full submission that passed every public and hidden test is
scored. The dimensions are deterministic, explainable heuristics over the user's diff against the
buggy starter, compared with the reference fix's diff. They never return reference code.
"""
import difflib
import re
import statistics

from sqlalchemy import select

from app import scoring, taxonomy
from app.models import Submission

VERSION = "quality-v1"
LONG_LINE = 120
COMMENT_PREFIX = re.compile(r"^\s*(#|//|/\*|\*)")
CODE_IN_COMMENT = re.compile(r"[;(){}=\[\]]")
DEBUG_OUTPUT = re.compile(
    r"print\(.*file\s*=\s*sys\.stderr|console\.(log|error|debug|warn)\(|System\.(err|out)\.print|"
    r"fmt\.(Fprint|Print)|std::(cerr|cout)|log\.Print|eprintln|traceback\.print_exc")
TODO = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
SWALLOW_PATTERNS = (
    (re.compile(r"^\s*except\s*:\s*(pass)?\s*$"), 0.5, "a bare except"),
    (re.compile(r"^\s*except\s+(Exception|BaseException)(\s+as\s+\w+)?\s*:\s*(pass|return\b.*|continue)?\s*$"), 0.35,
     "a broad exception handler"),
    (re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"), 0.5, "an empty catch block"),
    (re.compile(r"catch\s*\(\s*(Exception|Throwable|\.\.\.)"), 0.3, "a catch-all handler"),
    (re.compile(r"_\s*=\s*err\b|if\s+err\s*!=\s*nil\s*\{\s*\}"), 0.35, "an ignored error"),
    (re.compile(r"\brecover\(\)"), 0.3, "a recovered panic"),
)
SYNCHRONIZATION = re.compile(
    r"\bLock\(|\bRLock\(|\bSemaphore\(|\bCondition\(|\bwith\s+\w*lock\w*\s*:|synchronized|ReentrantLock|"
    r"\bAtomic\w+|ConcurrentHashMap|sync\.Mutex|sync\.RWMutex|\.Lock\(\)|atomic\.|std::mutex|lock_guard|"
    r"unique_lock|std::atomic|Atomics\.|\bchan\b", re.I)


def _lines(source: str) -> list[str]:
    return (source or "").splitlines()


def _changes(original: list[str], current: list[str]):
    matcher = difflib.SequenceMatcher(a=original, b=current, autojunk=False)
    return [op for op in matcher.get_opcodes() if op[0] != "equal"]


def _changed_count(original: list[str], current: list[str]) -> int:
    return sum((i2 - i1) + (j2 - j1) for _, i1, i2, j1, j2 in _changes(original, current))


def _changed_original_lines(original: list[str], current: list[str]) -> set[int]:
    lines: set[int] = set()
    for _, i1, i2, _j1, _j2 in _changes(original, current):
        lines.update(range(i1, max(i2, i1 + 1)))
    return lines


def _added_lines(original: list[str], current: list[str]) -> list[str]:
    return [line for _, _i1, _i2, j1, j2 in _changes(original, current) for line in current[j1:j2]]


def _indent(line: str) -> int:
    expanded = line.replace("\t", "    ")
    return len(expanded) - len(expanded.lstrip(" "))


def _minimality(starter, code, reference) -> dict:
    mine, theirs = _changed_count(starter, code), _changed_count(starter, reference)
    ratio = mine / max(1, theirs)
    if ratio <= 1.5:
        score = 1.0
    else:
        score = max(0.3, 1 - (ratio - 1.5) / 4.5 * 0.7)
    return {"score": round(score, 3),
            "detail": f"{mine} changed lines; about {ratio:.1f}x the size of a focused fix."}


def _maintainability(starter, code) -> dict:
    added = _added_lines(starter, code)
    penalty, findings = 0.0, []
    long_lines = sum(1 for line in added if len(line) > LONG_LINE)
    if long_lines:
        penalty += min(0.4, 0.1 * long_lines)
        findings.append(f"{long_lines} line(s) over {LONG_LINE} characters")
    if any(TODO.search(line) for line in added):
        penalty += 0.15
        findings.append("TODO/FIXME markers")
    commented = sum(1 for line in added if COMMENT_PREFIX.match(line) and CODE_IN_COMMENT.search(line))
    if commented:
        penalty += min(0.3, 0.1 * commented)
        findings.append("commented-out code")
    if any(DEBUG_OUTPUT.search(line) for line in added):
        penalty += 0.2
        findings.append("leftover debug output")
    base_depth = max((_indent(line) for line in starter if line.strip()), default=0)
    new_depth = max((_indent(line) for line in added if line.strip()), default=0)
    if new_depth - base_depth >= 8:
        penalty += 0.15
        findings.append("deeper nesting than the original")
    score = max(0.0, 1 - penalty)
    return {"score": round(score, 3), "detail": "No maintainability concerns in the changed lines."
            if not findings else "Changed lines include " + ", ".join(findings) + "."}


def _error_handling(starter, code) -> dict:
    added = _added_lines(starter, code)
    joined = "\n".join(added)
    penalty, findings = 0.0, []
    for pattern, cost, label in SWALLOW_PATTERNS:
        if any(pattern.search(line) for line in added) or (label == "an empty catch block" and pattern.search(joined)):
            penalty += cost
            findings.append(label)
    score = max(0.0, 1 - penalty)
    return {"score": round(score, 3), "detail": "No swallowed or catch-all error handling was added."
            if not findings else "The fix adds " + ", ".join(dict.fromkeys(findings)) + ", which can hide failures."}


def _performance(db, problem, submission) -> dict:
    if submission.runtime_ms is None:
        return {"score": None, "detail": "No runtime was recorded.", "flag": "insufficient_data"}
    peers = [value for value in db.scalars(select(Submission.runtime_ms).where(
        Submission.problem_id == problem.id, Submission.language == submission.language,
        Submission.kind == "submit", Submission.status == "passed", Submission.id != submission.id,
        Submission.runtime_ms.is_not(None)).limit(500)) if value is not None]
    if len(peers) < 5:
        return {"score": None, "detail": "Fewer than five accepted runs to compare with.", "flag": "insufficient_data"}
    median = statistics.median(peers) or 1.0
    ratio = submission.runtime_ms / median
    score = 1.0 if ratio <= 1.25 else max(0.3, 1 - (ratio - 1.25) * 0.4)
    return {"score": round(score, 3), "detail": f"Runtime is {ratio:.2f}x the median accepted run in this language."}


def _concurrency(problem, code, reference) -> dict | None:
    categories = set(taxonomy.classify_problem(problem)["bug_categories"])
    if not categories & {"race_condition", "deadlock"}:
        return None
    ours = bool(SYNCHRONIZATION.search("\n".join(code)))
    expected = bool(SYNCHRONIZATION.search("\n".join(reference)))
    if ours:
        return {"score": 1.0, "detail": "Shared state is protected by an explicit synchronization primitive."}
    if not expected:
        return {"score": 1.0, "detail": "The fix avoids shared mutable state."}
    return {"score": 0.6, "detail": "The tests pass, but no synchronization primitive protects the shared state."}


def _regression_risk(starter, code, reference) -> dict:
    mine = _changed_original_lines(starter, code)
    if not mine:
        return {"score": 1.0, "detail": "The fix changes no original lines."}
    region = _changed_original_lines(starter, reference)
    if not region:
        return {"score": None, "detail": "No reference region to compare with.", "flag": "insufficient_data"}
    near = sum(1 for line in mine if any(abs(line - target) <= 3 for target in region))
    fraction = near / len(mine)
    return {"score": round(0.4 + 0.6 * fraction, 3),
            "detail": f"{round(fraction * 100)}% of the changed lines are close to where the defect is."}


def score_patch(db, problem, submission) -> dict | None:
    """Quality of an accepted full submission; None when quality does not apply (correctness gate)."""
    if submission is None or submission.status != "passed" or submission.kind != "submit":
        return None
    language = submission.language
    starter = _lines(problem.starters.get(language, ""))
    reference = _lines(problem.solutions.get(language, ""))
    code = _lines(submission.generated_code or submission.code)
    if not starter or not code:
        return None
    dimensions = {
        "minimality": _minimality(starter, code, reference),
        "maintainability": _maintainability(starter, code),
        "error_handling": _error_handling(starter, code),
        "performance": _performance(db, problem, submission),
        "concurrency_safety": _concurrency(problem, code, reference),
        "regression_risk": _regression_risk(starter, code, reference),
    }
    dimensions = {name: value for name, value in dimensions.items() if value is not None}
    score = scoring.weighted({name: None if value["score"] is None else value["score"] * 100
                              for name, value in dimensions.items()}, scoring.QUALITY_WEIGHTS)
    return {"score": score, "version": VERSION, "dimensions": dimensions}
