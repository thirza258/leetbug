"""Deterministic, template-based mutation generation (PRD 7.3; MT-001, MT-009, MT-010).

Mutants come only from explicitly supported templates applied at syntactically identified sites,
never from arbitrary text edits:

* Python sites are located with ``ast`` and ``tokenize`` (exact positions; string, comment and
  f-string contents are never touched).
* JavaScript, Java, C++ and Go sites are located with a small tokenizer that skips strings,
  character literals, comments, regular-expression literals, preprocessor lines and
  generic/template angle brackets.

The same source and configuration always produce the same mutants in the same order: critical
mutants (on lines the reference fix changed) first, then a round-robin over operator classes, each
in source order.
"""
import ast
import bisect
import difflib
import hashlib
import io
import re
import tokenize
from collections import OrderedDict
from dataclasses import dataclass, field

MUTATION_VERSION = "mutation-v1"

# Round-robin priority. Concurrency templates (P2) come last; critical-first ordering still
# selects them when they sit on the lines the reference fix changed.
OPERATORS = [
    "comparison", "boundary", "boolean_logic", "arithmetic", "return_value", "null_check", "collection",
    "conditional", "error_handling", "resource_cleanup", "concurrency", "idempotency", "retry_limit",
]
OPERATOR_LABELS = {
    "comparison": "Comparison operator", "boundary": "Boundary condition", "boolean_logic": "Boolean logic",
    "arithmetic": "Arithmetic", "return_value": "Return value", "null_check": "Null handling",
    "collection": "Collection behavior", "conditional": "Conditional branch", "error_handling": "Error handling",
    "resource_cleanup": "Resource handling", "concurrency": "Synchronization / transaction removal",
    "idempotency": "Idempotency validation removal", "retry_limit": "Retry behavior",
}
CONCURRENCY_OPERATORS = {"concurrency", "idempotency", "retry_limit"}
LANGUAGES = ("python", "javascript", "java", "cpp", "go")

RETRY_NAME = re.compile(r"retr|attempt|tries|limit|budget|threshold|capacity|quota"
                        r"|max_?(?:retr|attempt|tr(?:y|ies)|count|calls|requests|failures)", re.IGNORECASE)
LOCK_NAME = re.compile(r"lock|mutex|sem(aphore)?\b|cond(ition)?\b|guard", re.IGNORECASE)
TRANSACTION_NAME = re.compile(r"transaction|atomic|\bconn(ection)?\b|session|\bdb\b|savepoint", re.IGNORECASE)
IDEMPOTENCY_NAME = re.compile(r"seen|processed|dedup|idempot|visited|applied|handled|done|known|cache|key",
                              re.IGNORECASE)
COLLECTION_METHODS = {"append", "add", "extend", "update", "insert", "appendleft", "put", "discard", "remove",
                      "pop", "popleft", "setdefault", "push", "push_back", "emplace_back", "offer", "addLast",
                      "unshift", "splice", "erase", "delete", "set", "putIfAbsent", "merge"}
CLEANUP_METHODS = {"close", "release", "shutdown", "cancel", "rollback", "unlink", "cleanup", "dispose",
                   "disconnect", "free", "terminate", "Close", "Release", "Stop", "Cancel", "Rollback", "Shutdown"}
INDEX_METHODS = {"subList", "substring", "slice", "substr", "charAt", "at", "codePointAt", "copyOfRange",
                 "subarray", "get", "remove", "insert", "erase", "resize", "splice", "Slice", "split", "repeat",
                 "padStart", "padEnd", "toFixed", "SplitN", "Repeat"}
PYTHON_INDEX_METHODS = {"pop", "insert", "split", "rsplit", "index", "find", "rfind", "ljust", "rjust", "zfill"}
CONTROL_KEYWORDS = {"if", "for", "while", "switch", "catch", "synchronized", "return", "foreach", "elif", "else"}
SYNTAX_MARKERS = ("SyntaxError", "IndentationError", "TabError")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_source(source: str) -> str:
    return source.replace("\r\n", "\n").replace("\r", "\n")


def changed_lines(starter: str | None, solution: str) -> set[int]:
    """Reference lines (1-based) that the fix inserted or replaced, plus neighbours of deletions."""
    if not starter:
        return set()
    a, b = normalize_source(starter).split("\n"), normalize_source(solution).split("\n")
    changed: set[int] = set()
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            changed.update(range(j1 + 1, j2 + 1))
        elif tag == "delete":
            changed.update({max(1, j1), j1 + 1})
    return changed


@dataclass
class Candidate:
    operator: str
    description: str
    edits: list  # [(start, end, replacement)] absolute character offsets


@dataclass
class MutantSet:
    mutants: list = field(default_factory=list)
    candidates: int = 0
    by_operator: dict = field(default_factory=dict)
    language: str = ""
    version: str = MUTATION_VERSION


class _Text:
    """Absolute-offset helpers over a normalized source."""

    def __init__(self, source: str):
        self.source = source
        self.lines = source.split("\n")
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line) + 1)

    def line_of(self, offset: int) -> int:
        return max(1, bisect.bisect_right(self.starts, offset))

    def offset(self, line: int, char_col: int) -> int:
        return self.starts[line - 1] + char_col

    def byte_offset(self, line: int, byte_col: int) -> int:
        text = self.lines[line - 1]
        return self.starts[line - 1] + len(text.encode("utf-8")[:byte_col].decode("utf-8", errors="ignore"))


def _apply(source: str, edits: list) -> str:
    code = source
    for start, end, replacement in sorted(edits, key=lambda edit: edit[0], reverse=True):
        code = code[:start] + replacement + code[end:]
    return code


def _materialize(text: _Text, candidate: Candidate, changed: set[int]) -> dict | None:
    code = _apply(text.source, candidate.edits)
    if code == text.source:
        return None
    first = min(start for start, _, _ in candidate.edits)
    last = max(max(end - 1, start) for start, end, _ in candidate.edits)
    line, end_line = text.line_of(first), text.line_of(last)
    delta = sum(len(replacement) - (end - start) for start, end, replacement in candidate.edits)
    original_end = text.starts[end_line] - 1 if end_line < len(text.starts) else len(text.source)
    original = text.source[text.starts[line - 1]:original_end]
    mutated = code[text.starts[line - 1]:max(text.starts[line - 1], original_end + delta)]
    lines = set(range(line, end_line + 1))
    return {
        "operator": candidate.operator, "description": candidate.description[:300], "line": line,
        "end_line": end_line, "original_snippet": original.rstrip()[:2000], "mutated_snippet": mutated.rstrip()[:2000],
        "code": code, "critical": bool(lines & changed), "code_hash": sha256(code),
    }


# ── Python ──────────────────────────────────────────────────────────────────────────────────

_COMPARE = {
    ast.Lt: ("<", "<=", "boundary"), ast.Gt: (">", ">=", "boundary"),
    ast.LtE: ("<=", "<", "comparison"), ast.GtE: (">=", ">", "comparison"),
    ast.Eq: ("==", "!=", "comparison"), ast.NotEq: ("!=", "==", "comparison"),
    ast.Is: ("is", "is not", "comparison"), ast.IsNot: ("is not", "is", "comparison"),
    ast.In: ("in", "not in", "comparison"), ast.NotIn: ("not in", "in", "comparison"),
}
_BINOP = {ast.Add: ("+", "-"), ast.Sub: ("-", "+"), ast.Mult: ("*", "/"), ast.Div: ("/", "*"),
          ast.FloorDiv: ("//", "/"), ast.Mod: ("%", "//"), ast.Pow: ("**", "*")}
_AUGOP = {ast.Add: ("+=", "-="), ast.Sub: ("-=", "+="), ast.Mult: ("*=", "/="), ast.Div: ("/=", "*="),
          ast.FloorDiv: ("//=", "/="), ast.Mod: ("%=", "//=")}
_SIMPLE = (ast.Name, ast.Constant, ast.Attribute, ast.Subscript, ast.Call)


class _PythonSites:
    def __init__(self, source: str):
        self.text = _Text(source)
        self.tree = ast.parse(source)
        self.tokens = []
        self.significant = []
        skipped = {tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT,
                   tokenize.ENDMARKER}
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type in skipped:
                continue
            start = self.text.offset(*token.start)
            end = self.text.offset(*token.end)
            self.significant.append(start)
            if token.type in (tokenize.OP, tokenize.NAME):
                self.tokens.append((start, end, token.string))
        self.token_starts = [start for start, _, _ in self.tokens]
        self.fstrings = [self.span(node) for node in ast.walk(self.tree) if isinstance(node, ast.JoinedStr)]

    def span(self, node) -> tuple[int, int]:
        return (self.text.byte_offset(node.lineno, node.col_offset),
                self.text.byte_offset(node.end_lineno, node.end_col_offset))

    def segment(self, node) -> str:
        start, end = self.span(node)
        return self.text.source[start:end]

    def between(self, start: int, end: int) -> list:
        index = bisect.bisect_left(self.token_starts, start)
        found = []
        while index < len(self.tokens) and self.tokens[index][0] < end:
            token = self.tokens[index]
            if token[1] <= end and token[2] not in ("(", ")"):
                found.append(token)
            index += 1
        return found

    def after_token(self, start: int) -> int | None:
        """Start of the token that follows the token beginning at ``start``."""
        index = bisect.bisect_left(self.significant, start)
        if index + 1 >= len(self.significant) or self.significant[index] != start:
            return None
        return self.significant[index + 1]

    def in_fstring(self, start: int, end: int) -> bool:
        return any(start < f_end and end > f_start for f_start, f_end in self.fstrings)

    def operator_span(self, left, right, expected: str) -> tuple[int, int] | None:
        tokens = self.between(self.span(left)[1], self.span(right)[0])
        if not tokens or " ".join(token[2] for token in tokens) != expected:
            return None
        return tokens[0][0], tokens[-1][1]


def _wrap(sites: _PythonSites, node) -> str:
    text = sites.segment(node)
    return text if isinstance(node, _SIMPLE) else f"({text})"


def _python_candidates(source: str) -> list[Candidate]:
    sites = _PythonSites(source)
    found: list[Candidate] = []

    def add(operator, description, edits):
        if any(sites.in_fstring(start, max(end, start + 1)) for start, end, _ in edits):
            return
        found.append(Candidate(operator, description, edits))

    nodes = list(ast.walk(sites.tree))
    nodes.sort(key=lambda node: (getattr(node, "lineno", 0), getattr(node, "col_offset", 0)))
    for node in nodes:
        if isinstance(node, ast.Compare):
            for index, op in enumerate(node.ops):
                old, new, operator = _COMPARE[type(op)]
                left = node.left if index == 0 else node.comparators[index - 1]
                span = sites.operator_span(left, node.comparators[index], old)
                if span:
                    add(operator, f"Replaced `{old}` with `{new}`", [(span[0], span[1], new)])
        elif isinstance(node, ast.BoolOp):
            old = "and" if isinstance(node.op, ast.And) else "or"
            new = "or" if old == "and" else "and"
            for left, right in zip(node.values, node.values[1:], strict=False):
                span = sites.operator_span(left, right, old)
                if span:
                    add("boolean_logic", f"Replaced `{old}` with `{new}`", [(span[0], span[1], new)])
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            start, end = sites.span(node)
            add("boolean_logic", f"Flipped `{node.value}` to `{not node.value}`", [(start, end, str(not node.value))])
        elif isinstance(node, ast.BinOp) and type(node.op) in _BINOP:
            old, new = _BINOP[type(node.op)]
            span = sites.operator_span(node.left, node.right, old)
            if span:
                add("arithmetic", f"Replaced `{old}` with `{new}`", [(span[0], span[1], new)])
        elif isinstance(node, ast.AugAssign) and type(node.op) in _AUGOP:
            old, new = _AUGOP[type(node.op)]
            span = sites.operator_span(node.target, node.value, old)
            if span:
                add("arithmetic", f"Replaced `{old}` with `{new}`", [(span[0], span[1], new)])
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.Not)):
            start = sites.span(node)[0]
            removal_end = sites.after_token(start)
            if removal_end is not None:
                if isinstance(node.op, ast.USub):
                    add("arithmetic", "Removed unary negation", [(start, removal_end, "")])
                else:
                    add("conditional", "Removed `not`", [(start, removal_end, "")])
        if isinstance(node, ast.Return) and node.value is not None:
            value = node.value
            start, end = sites.span(value)
            if isinstance(value, ast.Constant) and isinstance(value.value, bool):
                add("return_value", "Returned the opposite boolean", [(start, end, str(not value.value))])
            elif isinstance(value, ast.Constant) and isinstance(value.value, (int, float)):
                add("return_value", f"Returned {value.value + 1!r} instead of {value.value!r}",
                    [(start, end, repr(value.value + 1))])
            elif not (isinstance(value, ast.Constant) and value.value is None):
                add("return_value", "Returned `None` instead of the computed result", [(start, end, "None")])
        if isinstance(node, ast.If):
            _python_if(sites, node, add)
        if isinstance(node, (ast.If, ast.While, ast.IfExp)):
            test = node.test
            if not (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)):
                start, end = sites.span(test)
                kind = {ast.If: "if", ast.While: "while", ast.IfExp: "conditional expression"}[type(node)]
                add("conditional", f"Inverted the {kind} condition", [(start, end, f"not ({sites.segment(test)})")])
        if isinstance(node, ast.comprehension):
            for test in node.ifs:
                start, end = sites.span(test)
                add("conditional", "Inverted the comprehension filter", [(start, end, f"not ({sites.segment(test)})")])
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and len(node.values) == 2:
            fallback = node.values[1]
            if isinstance(fallback, (ast.Constant, ast.List, ast.Dict, ast.Tuple, ast.Set, ast.Name)) or (
                    isinstance(fallback, ast.Call) and isinstance(fallback.func, ast.Name)
                    and fallback.func.id in {"list", "dict", "set", "tuple", "str", "int", "float"} and not fallback.args):
                start, end = sites.span(node)
                add("null_check", "Removed the default fallback for a missing value",
                    [(start, end, _wrap(sites, node.values[0]))])
        if isinstance(node, ast.Call):
            _python_call(sites, node, add)
        if isinstance(node, ast.Subscript):
            _python_subscript(sites, node, add)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            method = node.value.func.attr
            start, end = sites.span(node)
            if method in COLLECTION_METHODS:
                add("collection", f"Removed the `{method}(...)` call", [(start, end, "pass")])
            elif method in CLEANUP_METHODS:
                add("resource_cleanup", f"Removed the `{method}()` cleanup call", [(start, end, "pass")])
        if isinstance(node, ast.Raise):
            start, end = sites.span(node)
            add("error_handling", "Suppressed the raised exception", [(start, end, "pass")])
        if isinstance(node, ast.Try) and node.finalbody:
            start = sites.span(node.finalbody[0])[0]
            end = sites.span(node.finalbody[-1])[1]
            add("resource_cleanup", "Removed the `finally` cleanup", [(start, end, "pass")])
        if isinstance(node, ast.With) and all(item.optional_vars is None for item in node.items):
            header = " ".join(sites.segment(item.context_expr) for item in node.items)
            colon = next((token for token in sites.between(sites.span(node.items[-1].context_expr)[1],
                                                           sites.span(node.body[0])[0]) if token[2] == ":"), None)
            if colon and (LOCK_NAME.search(header) or TRANSACTION_NAME.search(header)):
                what = "synchronization" if LOCK_NAME.search(header) else "the transaction boundary"
                add("concurrency", f"Removed {what} (`with {header}:`)",
                    [(sites.span(node)[0], colon[1], "if True:")])
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _python_lock_pairs(sites, node, add)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute)
                     else "" for target in targets]
            _python_retry_constant(sites, node.value, any(RETRY_NAME.search(name) for name in names if name), add)
        if isinstance(node, ast.keyword) and node.arg and RETRY_NAME.search(node.arg):
            _python_retry_constant(sites, node.value, True, add)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = node.left, node.comparators[0]
            if _retry_named(left):
                _python_retry_constant(sites, right, True, add)
            elif _retry_named(right):
                _python_retry_constant(sites, left, True, add)
    return found


def _retry_named(node) -> bool:
    if isinstance(node, ast.Name):
        return bool(RETRY_NAME.search(node.id))
    if isinstance(node, ast.Attribute):
        return bool(RETRY_NAME.search(node.attr))
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return bool(RETRY_NAME.search(node.slice.value))
    return False


def _python_retry_constant(sites, value, named: bool, add):
    if named and isinstance(value, ast.Constant) and type(value.value) is int and value.value >= 0:
        start, end = sites.span(value)
        add("retry_limit", f"Changed the limit {value.value} to {value.value + 1}", [(start, end, str(value.value + 1))])


def _mentions_none(test) -> bool:
    return any(isinstance(node, ast.Constant) and node.value is None for node in ast.walk(test)) or any(
        isinstance(node, ast.Compare) and any(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops)
        for node in ast.walk(test))


def _python_if(sites: _PythonSites, node: ast.If, add):
    test = node.test
    start, end = sites.span(test)
    negated = isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and isinstance(test.operand, _SIMPLE)
    if _mentions_none(test) or negated:
        present = isinstance(test, ast.Compare) and all(isinstance(op, (ast.IsNot, ast.NotEq)) for op in test.ops)
        add("null_check", "Removed the null/empty check", [(start, end, "True" if present else "False")])
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], (ast.In, ast.NotIn)):
        skip_when_member = isinstance(test.ops[0], ast.In)
        add("idempotency", "Removed the membership (idempotency/deduplication) check",
            [(start, end, "False" if skip_when_member else "True")])


def _python_call(sites: _PythonSites, node: ast.Call, add):
    if isinstance(node.func, ast.Name) and node.func.id == "range" and 1 <= len(node.args) <= 3 and not node.keywords:
        stop = node.args[0] if len(node.args) == 1 else node.args[1]
        start, end = sites.span(stop)
        add("boundary", "Shortened the `range(...)` stop by one", [(start, end, f"{_wrap(sites, stop)} - 1")])
    if isinstance(node.func, ast.Attribute) and node.func.attr in PYTHON_INDEX_METHODS:
        for argument in node.args:
            if isinstance(argument, ast.Constant) and type(argument.value) is int:
                start, end = sites.span(argument)
                add("collection", f"Changed the `{node.func.attr}` argument {argument.value} to {argument.value + 1}",
                    [(start, end, str(argument.value + 1))])
    if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and len(node.args) == 2 and not node.keywords:
        start, end = sites.span(node)
        add("null_check", "Removed the `get(...)` default value",
            [(start, end, f"{sites.segment(node.func)}({sites.segment(node.args[0])})")])


def _python_subscript(sites: _PythonSites, node: ast.Subscript, add):
    index = node.slice
    if isinstance(index, ast.Constant) and type(index.value) is int:
        start, end = sites.span(index)
        add("collection", f"Changed index {index.value} to {index.value + 1}", [(start, end, str(index.value + 1))])
    elif (isinstance(index, ast.UnaryOp) and isinstance(index.op, ast.USub) and isinstance(index.operand, ast.Constant)
          and type(index.operand.value) is int):
        start, end = sites.span(index)
        add("collection", f"Changed index -{index.operand.value} to -{index.operand.value + 1}",
            [(start, end, f"-{index.operand.value + 1}")])
    elif isinstance(index, ast.Slice):
        if index.lower is not None:
            start, end = sites.span(index.lower)
            add("collection", "Moved the slice start forward by one", [(start, end, f"{_wrap(sites, index.lower)} + 1")])
        if index.upper is not None:
            start, end = sites.span(index.upper)
            add("collection", "Moved the slice end back by one", [(start, end, f"{_wrap(sites, index.upper)} - 1")])


def _python_lock_pairs(sites: _PythonSites, function, add):
    calls: dict[str, dict[str, list]] = OrderedDict()
    for node in ast.walk(function):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr in ("acquire", "release") and not node.value.args):
            receiver = sites.segment(node.value.func.value)
            calls.setdefault(receiver, {"acquire": [], "release": []})[node.value.func.attr].append(node)
    for receiver, found in calls.items():
        if found["acquire"] and found["release"]:
            edits = [(*sites.span(node), "pass") for node in found["acquire"] + found["release"]]
            add("concurrency", f"Removed `{receiver}.acquire()`/`release()` locking", edits)


# ── JavaScript, Java, C++ and Go ────────────────────────────────────────────────────────────

@dataclass
class _Tok:
    kind: str  # id | num | str | op
    text: str
    start: int
    end: int
    nl: bool  # a newline precedes this token (Go statement boundaries)


_COMMON_OPS = ["...", "<<=", ">>=", "==", "!=", "<=", ">=", "&&", "||", "++", "--", "+=", "-=", "*=", "/=",
               "%=", "&=", "|=", "^=", "<<", ">>", "->", "::"]
_LANG_OPS = {
    "javascript": [">>>=", "===", "!==", ">>>", "**=", "&&=", "||=", "??=", "**", "=>", "?.", "??"],
    "java": [">>>=", ">>>"],
    "cpp": ["->*", "<=>"],
    "go": ["&^=", ":=", "<-", "&^"],
}
_NUMBER = re.compile(r"0[xX][0-9a-fA-F_']+[a-zA-Z]*|0[bB][01_']+[a-zA-Z]*|(?:\d[\d_']*(?:\.\d*)?|\.\d+)"
                     r"(?:[eE][+-]?\d+)?[a-zA-Z]*")
_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_KEYWORDS = {"return", "case", "typeof", "in", "of", "new", "delete", "throw", "else", "do", "void", "instanceof",
             "yield", "await", "go", "defer", "var", "let", "const", "if", "for", "while", "switch", "func",
             "chan", "range", "sizeof", "and", "or", "not"}
_TYPE_WORDS = {"int", "long", "short", "char", "double", "float", "bool", "void", "auto", "const", "unsigned",
               "signed", "size_t", "string", "byte", "rune", "int64", "int32", "uint", "uint64", "uint32",
               "float64", "float32", "struct", "class", "typename", "volatile", "std"}
_GENERIC_INNER = {"::", ".", ",", "?", "[", "]", "*", "&", "<", ">", ">>", ">>>"}


def _scan(source: str, language: str) -> list[_Tok]:
    ops = sorted(_COMMON_OPS + _LANG_OPS.get(language, []), key=len, reverse=True)
    tokens: list[_Tok] = []
    i, n, newline = 0, len(source), True
    line_start = True

    def quoted(start: int, quote: str) -> int:
        j = start + 1
        while j < n:
            if source[j] == "\\":
                j += 2
                continue
            if source[j] == quote or (source[j] == "\n" and quote != "`"):
                return j + 1
            j += 1
        return n

    def template(start: int) -> int:
        j, depth = start + 1, 0
        while j < n:
            char = source[j]
            if char == "\\":
                j += 2
                continue
            if language == "javascript" and source.startswith("${", j):
                depth += 1
                j += 2
                continue
            if depth and char == "}":
                depth -= 1
            elif char == "`" and not depth:
                return j + 1
            j += 1
        return n

    while i < n:
        char = source[i]
        if char == "\n":
            newline = line_start = True
            i += 1
            continue
        if char in " \t\f\v":
            i += 1
            continue
        if source.startswith("//", i):
            j = source.find("\n", i)
            i = n if j < 0 else j
            continue
        if source.startswith("/*", i):
            j = source.find("*/", i + 2)
            end = n if j < 0 else j + 2
            if "\n" in source[i:end]:
                newline = line_start = True
            i = end
            continue
        if char == "#" and language == "cpp" and line_start:
            while i < n and source[i] != "\n":
                i = i + 2 if source[i] == "\\" else i + 1
            continue
        line_start = False
        previous = tokens[-1] if tokens else None
        if char in "\"'":
            end = quoted(i, char)
            tokens.append(_Tok("str", source[i:end], i, end, newline))
        elif char == "`":
            end = template(i)
            tokens.append(_Tok("str", source[i:end], i, end, newline))
        elif char.isdigit() or (char == "." and i + 1 < n and source[i + 1].isdigit()):
            match = _NUMBER.match(source, i)
            end = match.end() if match else i + 1
            tokens.append(_Tok("num", source[i:end], i, end, newline))
        elif char.isalpha() or char in "_$":
            match = _IDENT.match(source, i)
            end = match.end()
            word = source[i:end]
            if language == "cpp" and word in {"R", "u8R", "uR", "UR", "LR"} and end < n and source[end] == '"':
                close = source.find("(", end)
                delimiter = source[end + 1:close] if close > 0 else ""
                finish = source.find(")" + delimiter + '"', close)
                end = n if finish < 0 else finish + len(delimiter) + 2
                tokens.append(_Tok("str", source[i:end], i, end, newline))
            else:
                tokens.append(_Tok("id", word, i, end, newline))
        elif char == "/" and language == "javascript" and _regex_allowed(previous):
            j, in_class = i + 1, False
            while j < n and source[j] != "\n":
                if source[j] == "\\":
                    j += 2
                    continue
                if source[j] == "[":
                    in_class = True
                elif source[j] == "]":
                    in_class = False
                elif source[j] == "/" and not in_class:
                    break
                j += 1
            j += 1
            while j < n and source[j].isalpha():
                j += 1
            tokens.append(_Tok("str", source[i:j], i, j, newline))
            end = j
        else:
            text = next((op for op in ops if source.startswith(op, i)), char)
            end = i + len(text)
            tokens.append(_Tok("op", text, i, end, newline))
        newline = False
        i = end
    return tokens


def _regex_allowed(previous: _Tok | None) -> bool:
    if previous is None:
        return True
    if previous.kind == "op":
        return previous.text not in (")", "]", "}", "++", "--")
    return previous.kind == "id" and previous.text in _KEYWORDS


def _operand_end(token: _Tok | None) -> bool:
    if token is None:
        return False
    if token.kind in ("num", "str"):
        return True
    if token.kind == "id":
        return token.text not in _KEYWORDS
    return token.text in (")", "]")


def _generic_brackets(tokens: list[_Tok], language: str) -> set[int]:
    """Indices of ``<``/``>`` tokens that are generic or template brackets (Java and C++ only)."""
    marked: set[int] = set()
    if language not in ("java", "cpp"):
        return marked
    for index, token in enumerate(tokens):
        if token.text != "<" or index in marked or index == 0 or tokens[index - 1].kind != "id":
            continue
        depth, j, inner = 1, index + 1, [index]
        while j < len(tokens) and depth > 0:
            current = tokens[j]
            if current.text == "<":
                depth += 1
                inner.append(j)
            elif current.text in (">", ">>", ">>>"):
                depth -= len(current.text)
                inner.append(j)
            elif not (current.kind in ("id", "num") or current.text in _GENERIC_INNER):
                break
            j += 1
        if depth <= 0:
            marked.update(inner)
    return marked


def _match(tokens: list[_Tok], index: int, opener: str, closer: str) -> int | None:
    depth = 0
    for j in range(index, len(tokens)):
        if tokens[j].text == opener:
            depth += 1
        elif tokens[j].text == closer:
            depth -= 1
            if depth == 0:
                return j
    return None


def _statement_end(tokens: list[_Tok], start: int, language: str) -> int | None:
    """Index of the last token of the simple statement starting at ``start``."""
    depth = 0
    for j in range(start, len(tokens)):
        token = tokens[j]
        if language == "go" and j > start and token.nl and depth == 0:
            return j - 1
        if token.text in ("(", "[", "{"):
            depth += 1
        elif token.text in (")", "]", "}"):
            if depth == 0:
                return j - 1 if language == "go" else None
            depth -= 1
        elif token.text == ";" and depth == 0:
            return j
    return len(tokens) - 1 if language == "go" else None


def _call_statement(tokens: list[_Tok], start: int, end: int) -> tuple[str, str] | None:
    """(receiver, method) when tokens[start..end] is ``[defer|go] a.b.method(...)[;]``."""
    j = start
    if tokens[j].text in ("defer", "go"):
        j += 1
    if j > end or tokens[j].kind != "id":
        return None
    names, last_call = [tokens[j].text], None
    j += 1
    while j <= end:
        text = tokens[j].text
        if text in (".", "->", "::") and j + 1 <= end and tokens[j + 1].kind == "id":
            names.append(tokens[j + 1].text)
            j += 2
        elif text == "(":
            close = _match(tokens, j, "(", ")")
            if close is None or close > end:
                return None
            last_call = names[-1]
            j = close + 1
        elif text == ";" and j == end:
            j += 1
        else:
            return None
    if last_call is None:
        return None
    receiver = ".".join(names[:-1]) if names[-1] == last_call else ".".join(names)
    return receiver, last_call


def _clike_candidates(source: str, language: str) -> list[Candidate]:
    tokens = _scan(source, language)
    generic = _generic_brackets(tokens, language)
    found: list[Candidate] = []
    empty_statement = "" if language == "go" else ";"

    def add(operator, description, edits):
        found.append(Candidate(operator, description, edits))

    compare = {"<": ("<=", "boundary"), ">": (">=", "boundary"), "<=": ("<", "comparison"),
               ">=": (">", "comparison"), "==": ("!=", "comparison"), "!=": ("==", "comparison"),
               "===": ("!==", "comparison"), "!==": ("===", "comparison")}
    arithmetic = {"+": "-", "-": "+", "*": "/", "/": "*", "%": "/", "++": "--", "--": "++",
                  "+=": "-=", "-=": "+=", "*=": "/=", "/=": "*="}
    lock_pairs: dict[tuple[str, str], list[tuple[int, int]]] = OrderedDict()
    for index, token in enumerate(tokens):
        previous = tokens[index - 1] if index else None
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        text = token.text
        if token.kind == "op" and text in compare and index not in generic:
            new, operator = compare[text]
            add(operator, f"Replaced `{text}` with `{new}`", [(token.start, token.end, new)])
        elif token.kind == "op" and text in ("&&", "||"):
            new = "||" if text == "&&" else "&&"
            add("boolean_logic", f"Replaced `{text}` with `{new}`", [(token.start, token.end, new)])
        elif token.kind == "id" and text in ("true", "false"):
            new = "false" if text == "true" else "true"
            add("boolean_logic", f"Flipped `{text}` to `{new}`", [(token.start, token.end, new)])
        elif token.kind == "op" and text in arithmetic:
            if text in ("+", "-", "*", "/", "%") and not (_operand_end(previous) and following is not None
                                                          and following.text not in (")", ",", ";", "]", "}")):
                pass
            elif text in ("*", "/") and language in ("cpp", "go") and previous is not None and (
                    previous.text in _TYPE_WORDS or previous.text[:1].isupper()
                    or (following is not None and (following.text in (">", "&", "*", "=")
                                                   or (language == "go" and following.text[:1].isupper())))):
                pass
            else:
                new = arithmetic[text]
                add("arithmetic", f"Replaced `{text}` with `{new}`", [(token.start, token.end, new)])
        elif token.kind == "op" and text == "!" and following is not None and not _operand_end(previous):
            add("conditional", "Removed `!` negation", [(token.start, following.start, "")])
        if token.kind == "op" and text == "-" and following is not None and not _operand_end(previous) \
                and (following.kind in ("num", "id") or following.text == "(") and following.text not in _KEYWORDS:
            add("arithmetic", "Removed unary negation", [(token.start, following.start, "")])
        if token.kind == "num" and token.text.isdigit() and previous is not None and previous.text in ("(", ","):
            method = _call_name(tokens, index)
            if method in INDEX_METHODS:
                add("collection", f"Changed the `{method}` argument {token.text} to {int(token.text) + 1}",
                    [(token.start, token.end, str(int(token.text) + 1))])
        if token.kind == "op" and text == "[" and following is not None and following.kind == "num" \
                and language != "cpp" and _operand_end(previous) and previous.text not in _TYPE_WORDS \
                and index + 2 < len(tokens) and tokens[index + 2].text == "]" and following.text.isdigit():
            add("collection", f"Changed index {following.text} to {int(following.text) + 1}",
                [(following.start, following.end, str(int(following.text) + 1))])
        if token.kind == "num" and token.text.isdigit():
            context = [tokens[j] for j in range(max(0, index - 3), index)]
            if any(item.kind == "id" and RETRY_NAME.search(item.text) for item in context) or any(
                    item.kind == "str" and RETRY_NAME.search(item.text) for item in context):
                add("retry_limit", f"Changed the limit {token.text} to {int(token.text) + 1}",
                    [(token.start, token.end, str(int(token.text) + 1))])
        if token.kind == "id" and text in ("if", "while") and (text == "if" or language != "go"):
            _clike_condition(source, tokens, index, language, add)
        if token.kind == "id" and text == "return":
            close = _statement_end(tokens, index, language)
            if close is not None:
                last = close - 1 if tokens[close].text == ";" else close
                value = tokens[last] if last == index + 1 else None
                if value is not None and value.kind == "num" and value.text.isdigit():
                    add("return_value", f"Returned {int(value.text) + 1} instead of {value.text}",
                        [(value.start, value.end, str(int(value.text) + 1))])
                elif last > index:
                    replacement = "null" if language == "javascript" else _typed_default(tokens, index, language)
                    expression = source[tokens[index + 1].start:tokens[last].end].strip()
                    if replacement and expression != replacement and tokens[index + 1].text not in ("true", "false"):
                        add("return_value", f"Returned `{replacement}` instead of the computed result",
                            [(tokens[index + 1].start, tokens[last].end, replacement)])
        if token.kind == "id" and text == "throw" and language != "go":
            close = _statement_end(tokens, index, language)
            if close is not None:
                add("error_handling", "Suppressed the thrown exception", [(token.start, tokens[close].end, ";")])
        if token.kind == "id" and text == "finally" and following is not None and following.text == "{":
            close = _match(tokens, index + 1, "{", "}")
            if close is not None and close > index + 2:
                add("resource_cleanup", "Removed the `finally` cleanup",
                    [(following.end, tokens[close].start, " ")])
        if token.kind == "id" and text == "synchronized" and language == "java":
            if following is not None and following.text == "(":
                close = _match(tokens, index + 1, "(", ")")
                if close is not None:
                    add("concurrency", "Removed the `synchronized` block lock",
                        [(token.start, tokens[close].end, "")])
            else:
                end = following.start if following is not None else token.end
                add("concurrency", "Removed the `synchronized` modifier", [(token.start, end, "")])
        boundary = index == 0 or (tokens[index - 1].text in (";", "{", "}", "else")) or (language == "go" and token.nl) \
            or (tokens[index - 1].text == ")" and _closes_control_header(tokens, index - 1))
        if boundary and token.kind == "id":
            close = _statement_end(tokens, index, language)
            if close is None:
                continue
            call = _call_statement(tokens, index, close)
            span = (token.start, tokens[close].end)
            if language == "cpp" and text in ("std", "lock_guard", "unique_lock", "scoped_lock"):
                words = {tokens[j].text for j in range(index, min(close + 1, index + 4))}
                if words & {"lock_guard", "unique_lock", "scoped_lock"}:
                    add("concurrency", "Removed the scoped lock guard", [(span[0], span[1], empty_statement)])
                    continue
            if language == "go" and text == "panic" and call:
                add("error_handling", "Removed the `panic(...)` call", [(span[0], span[1], empty_statement)])
                continue
            if language == "go" and close >= index + 3 and tokens[index + 1].text == "=" \
                    and tokens[index + 2].text == "append":
                add("collection", f"Removed the append to `{text}`", [(span[0], span[1], empty_statement)])
                continue
            if not call:
                continue
            receiver, method = call
            if method in ("Lock", "Unlock", "RLock", "RUnlock", "lock", "unlock") and receiver:
                kind = "read" if method.startswith("R") else "write"
                lock_pairs.setdefault((receiver, kind), []).append(span)
            elif method in COLLECTION_METHODS:
                add("collection", f"Removed the `{method}(...)` call", [(span[0], span[1], empty_statement)])
            elif method in CLEANUP_METHODS:
                add("resource_cleanup", f"Removed the `{method}()` cleanup call", [(span[0], span[1], empty_statement)])
    for (receiver, _kind), spans in lock_pairs.items():
        if len(spans) >= 2:
            add("concurrency", f"Removed `{receiver}` lock/unlock synchronization",
                [(start, end, empty_statement) for start, end in spans])
    return found


def _match_back(tokens: list[_Tok], index: int, opener: str, closer: str) -> int | None:
    depth = 0
    for j in range(index, -1, -1):
        if tokens[j].text == closer:
            depth += 1
        elif tokens[j].text == opener:
            depth -= 1
            if depth == 0:
                return j
    return None


def _closes_control_header(tokens: list[_Tok], close: int) -> bool:
    opener = _match_back(tokens, close, "(", ")")
    return opener is not None and opener > 0 and tokens[opener - 1].text in ("if", "for", "while")


def _call_name(tokens: list[_Tok], index: int) -> str | None:
    """Name of the call whose argument list contains ``tokens[index]``."""
    depth = 0
    for j in range(index - 1, -1, -1):
        text = tokens[j].text
        if text in (")", "]"):
            depth += 1
        elif text in ("(", "["):
            if depth == 0:
                return tokens[j - 1].text if text == "(" and j > 0 and tokens[j - 1].kind == "id" else None
            depth -= 1
        elif text in (";", "{", "}") and depth == 0:
            return None
    return None


_GO_ZERO = {"int": "0", "int64": "0", "int32": "0", "uint": "0", "uint64": "0", "float64": "0", "float32": "0",
            "byte": "0", "rune": "0", "string": '""'}
_JAVA_ZERO = {"int": "0", "long": "0", "short": "0", "byte": "0", "double": "0", "float": "0"}


def _typed_default(tokens: list[_Tok], index: int, language: str) -> str | None:
    """A type-correct wrong return value for the function enclosing ``tokens[index]``, if known."""
    depth = 0
    for j in range(index - 1, -1, -1):
        text = tokens[j].text
        if text == "}":
            depth += 1
            continue
        if text != "{":
            continue
        if depth:
            depth -= 1
            continue
        header = _function_header(tokens, j, language)
        if header == "block":
            continue
        return header
    return None


def _function_header(tokens: list[_Tok], brace: int, language: str) -> str | None:
    """For the block opened at ``brace``: "block" for if/for/while bodies, else a default value or None."""
    if language == "go":
        func = next((k for k in range(brace - 1, max(-1, brace - 60), -1) if tokens[k].text == "func"), None)
        if func is None or any(tokens[k].text in (";",) for k in range(func, brace)):
            return "block"
        k = func + 1
        if k < brace and tokens[k].text == "(" and k + 1 < brace and tokens[k + 1].kind == "id" \
                and tokens[k + 1].text != ")" and tokens[func + 1].text == "(" and tokens[k - 1].text == "func":
            # A method receiver or an anonymous function's parameter list.
            close = _match(tokens, k, "(", ")")
            k = close + 1 if close is not None else brace
        if k < brace and tokens[k].kind == "id":
            k += 1
        if k < brace and tokens[k].text == "(":
            close = _match(tokens, k, "(", ")")
            k = close + 1 if close is not None else brace
        result = "".join(tokens[m].text for m in range(k, brace))
        if not result:
            return None
        if result in _GO_ZERO:
            return _GO_ZERO[result]
        if result.startswith(("[", "*", "map", "interface", "func", "chan")) or result in ("error", "any"):
            return "nil"
        return None
    end = brace - 1
    if end >= 0 and tokens[end].kind == "id" and language == "java":
        throws = next((k for k in range(end, max(-1, end - 12), -1) if tokens[k].text == "throws"), None)
        if throws is not None:
            end = throws - 1
    if end < 0 or tokens[end].text != ")":
        return "block" if end >= 0 and tokens[end].text in ("else", "try", "do", "finally") else None
    opener = _match_back(tokens, end, "(", ")")
    if opener is None or opener < 2:
        return None
    name = tokens[opener - 1]
    if name.kind != "id" or name.text in CONTROL_KEYWORDS:
        return "block" if name.text in CONTROL_KEYWORDS else None
    return_type = tokens[opener - 2]
    if language == "cpp":
        return None if return_type.text == "void" else "{}"
    if return_type.text == "void" or return_type.text == "boolean":
        return None
    if return_type.text in _JAVA_ZERO:
        return _JAVA_ZERO[return_type.text]
    if return_type.text in (">", "]") or return_type.text[:1].isupper():
        return "null"
    return None


def _clike_condition(source: str, tokens: list[_Tok], index: int, language: str, add):
    if language == "go":
        j, depth, start = index + 1, 0, index + 1
        while j < len(tokens):
            text = tokens[j].text
            if text in ("(", "["):
                depth += 1
            elif text in (")", "]"):
                depth -= 1
            elif text == ";" and depth == 0:
                start = j + 1
            elif text == "{" and depth == 0:
                break
            j += 1
        if j >= len(tokens) or start >= j:
            return
        first, last = start, j - 1
    else:
        if index + 1 >= len(tokens) or tokens[index + 1].text != "(":
            return
        close = _match(tokens, index + 1, "(", ")")
        if close is None or close <= index + 2:
            return
        first, last = index + 2, close - 1
    span_start, span_end = tokens[first].start, tokens[last].end
    condition = [tokens[j] for j in range(first, last + 1)]
    source_text = source[span_start:span_end]
    keyword = tokens[index].text
    add("conditional", f"Inverted the {keyword} condition", [(span_start, span_end, f"!({source_text})")])
    if keyword != "if":
        return
    words = {token.text for token in condition}
    if words & {"null", "nil", "nullptr", "undefined", "NULL"}:
        present = bool(words & {"!=", "!=="})
        replacement = f"true || ({source_text})" if present else f"false && ({source_text})"
        add("null_check", "Removed the null check", [(span_start, span_end, replacement)])
    methods = {token.text for token in condition if token.kind == "id"}
    membership = methods & {"has", "contains", "containsKey", "includes", "count", "find", "exists", "Contains"} \
        or any(token.text == "[" for token in condition)
    if membership and any(token.kind == "id" and IDEMPOTENCY_NAME.search(token.text) for token in condition):
        add("idempotency", "Removed the duplicate/membership check",
            [(span_start, span_end, f"false && ({source_text})")])


# ── Public API ──────────────────────────────────────────────────────────────────────────────

def candidates_for(language: str, source: str) -> list[Candidate]:
    source = normalize_source(source)
    if language == "python":
        try:
            return _python_candidates(source)
        except (SyntaxError, tokenize.TokenError, ValueError):
            return []
    if language in ("javascript", "java", "cpp", "go"):
        return _clike_candidates(source, language)
    raise ValueError(f"Unsupported language: {language}")


def python_syntax_ok(code: str) -> bool:
    try:
        compile(code, "<mutant>", "exec")
    except (SyntaxError, ValueError):
        return False
    return True


def _round_robin(items: list[dict]) -> list[dict]:
    buckets = OrderedDict((operator, [item for item in items if item["operator"] == operator]) for operator in OPERATORS)
    ordered = []
    while any(buckets.values()):
        for operator in OPERATORS:
            if buckets[operator]:
                ordered.append(buckets[operator].pop(0))
    return ordered


def generate(language: str, source: str, *, starter: str | None = None, max_mutants: int = 24,
             operators: list[str] | None = None) -> MutantSet:
    """All mutants for ``source`` (the reference solution), ordered and capped deterministically."""
    selected = set(operators or OPERATORS)
    unknown = selected - set(OPERATORS)
    if unknown:
        raise ValueError(f"Unknown mutation operators: {', '.join(sorted(unknown))}")
    source = normalize_source(source)
    text = _Text(source)
    changed = changed_lines(starter, source)
    original_hash = sha256(source)
    by_code: OrderedDict[str, dict] = OrderedDict()
    counts: dict[str, int] = {operator: 0 for operator in OPERATORS}
    candidates = [candidate for candidate in candidates_for(language, source) if candidate.operator in selected]
    candidates.sort(key=lambda candidate: (OPERATORS.index(candidate.operator), min(e[0] for e in candidate.edits)))
    for candidate in candidates:
        mutant = _materialize(text, candidate, changed)
        if mutant is None or mutant["code_hash"] in by_code:
            continue
        counts[candidate.operator] += 1
        mutant["original_hash"] = original_hash
        mutant["valid"] = python_syntax_ok(mutant["code"]) if language == "python" else None
        by_code[mutant["code_hash"]] = mutant
    unique = list(by_code.values())
    unique.sort(key=lambda mutant: (OPERATORS.index(mutant["operator"]), mutant["line"], mutant["code_hash"]))
    for mutant in unique:
        mutant.pop("end_line", None)
    ordered = _round_robin([m for m in unique if m["critical"]]) + _round_robin([m for m in unique if not m["critical"]])
    limited = ordered[:max(0, int(max_mutants))]
    for ordinal, mutant in enumerate(limited, 1):
        mutant["ordinal"] = ordinal
        mutant["language"] = language
    return MutantSet(mutants=limited, candidates=len(unique), language=language,
                     by_operator={key: value for key, value in counts.items() if value})


def generate_mutants(language: str, source: str, *, starter: str | None = None, max_mutants: int = 24,
                     operators: list[str] | None = None) -> list[dict]:
    return generate(language, source, starter=starter, max_mutants=max_mutants, operators=operators).mutants
