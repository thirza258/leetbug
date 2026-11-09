"""Response validation and grounding evaluation (PRD 8.8, 13.3; AR-010).

Every assistant answer — model-generated or deterministic — passes through these checks before it is
stored: hidden test data is redacted, reference-solution-like code is removed, citations and URLs
that are not among the retrieved sources are stripped, a limitation note is added when no evaluated
run exists, and a grounding score is computed.
"""
import json
import re

LIMITATION_NOTE = "No evaluated run is available yet, so this answer is based on the code and requirements only."
HIDDEN_PLACEHOLDER = "[hidden test data removed]"
CODE_PLACEHOLDER = "[Code removed: the assistant explains the defect instead of writing the fix.]"
MAX_CODE_LINES = 12
SHINGLE = 10
FENCE = re.compile(r"```[^\n]*\n.*?(?:```|\Z)", re.DOTALL)
SIGNATURE = re.compile(
    r"\bdef\s+solve\s*\(|\bfunction\s+solve\s*\(|\bfunc\s+Solve\s*\(|\bstatic\b[^\n(]*\bsolve\s*\(|"
    r"\bjson\s+solve\s*\(|\b(?:const|let|var)\s+solve\s*=|\bsolve\s*=\s*(?:async\s*)?\(")
CITATION = re.compile(r"(?<![\w\])])\[(\d{1,3})\]")
URL = re.compile(r"https?://[^\s)\]>\"'`]+")
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|!=|<=|>=|&&|\|\||=>|->|[^\sA-Za-z0-9_]")
LIMITATION_CUES = re.compile(r"\b(no (evaluated )?run|not (been )?run|haven'?t run|without (an? )?(evaluated )?run|"
                             r"based on the code|cannot see|not available|no test results)\b", re.IGNORECASE)
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
GENERIC_WORDS = set("""
the and for with that this from your you code line lines value values input inputs output test tests case
cases return returns function error run runs check data result results when then than should must
""".split())


def _shingles(text: str, size: int = SHINGLE) -> set[tuple]:
    tokens = TOKEN.findall(text or "")
    return {tuple(tokens[index:index + size]) for index in range(0, max(0, len(tokens) - size + 1))}


def _leaves(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item)
    else:
        yield value


def hidden_fragments(problem, public_text: str) -> list[str]:
    """Serialized hidden inputs/expectations (and distinctive leaves) that do not appear publicly."""
    fragments = set()
    for test in problem.tests:
        if not test.get("hidden"):
            continue
        for value in (test.get("input"), test.get("expected")):
            for rendered in {json.dumps(value), json.dumps(value, separators=(",", ":")),
                             json.dumps(value, ensure_ascii=False)}:
                if len(rendered) >= 8 and rendered not in public_text:
                    fragments.add(rendered)
            for leaf in _leaves(value):
                if isinstance(leaf, bool) or leaf is None:
                    continue
                rendered = leaf if isinstance(leaf, str) else str(leaf)
                distinctive = len(rendered) >= 8 if isinstance(leaf, str) else len(rendered.lstrip("-")) >= 5
                if distinctive and rendered not in public_text:
                    fragments.add(rendered)
    # Longest first, so a whole serialized input is replaced before its parts.
    return sorted(fragments, key=len, reverse=True)


def public_material(problem, context: dict) -> str:
    public_tests = [test for test in problem.tests if not test.get("hidden")]
    return "\n".join([json.dumps(public_tests), json.dumps(public_tests, separators=(",", ":")),
                      problem.summary or "", problem.description or "", "\n".join(problem.requirements or []),
                      "\n".join((problem.starters or {}).values()), context["code"]["current"] or ""])


def reference_only_shingles(problem, context: dict) -> set[tuple]:
    """Token shingles of the reference solutions that are not in public or user-authored code."""
    allowed = set()
    for source in list((problem.starters or {}).values()) + [context["code"]["current"], context["code"]["original"]]:
        allowed |= _shingles(source)
    reference = set()
    for source in (problem.solutions or {}).values():
        reference |= _shingles(source)
    return reference - allowed


def _strip_code(text: str, reference_only: set, flags: dict) -> str:
    def replace_block(match):
        block = match.group(0)
        if SIGNATURE.search(block):
            flags["solution_like"] += 1
            return CODE_PLACEHOLDER
        if reference_only and _shingles(block) & reference_only:
            flags["reference_overlap"] += 1
            return CODE_PLACEHOLDER
        if block.count("\n") - 1 > MAX_CODE_LINES:
            flags["long_code_blocks"] += 1
            return CODE_PLACEHOLDER
        return block

    text = FENCE.sub(replace_block, text)
    # Unfenced code: drop a solve() definition and the code-like lines that follow it.
    lines, kept, skipping = text.split("\n"), [], False
    for line in lines:
        if not skipping and SIGNATURE.search(line) and "`" not in line:
            flags["solution_like"] += 1
            kept.append(CODE_PLACEHOLDER)
            skipping = True
            continue
        if skipping:
            if not line.strip():
                skipping = False
                kept.append(line)
            continue
        if reference_only and _shingles(line) & reference_only:
            flags["reference_overlap"] += 1
            kept.append(CODE_PLACEHOLDER)
            continue
        kept.append(line)
    return "\n".join(kept)


def _strip_links(text: str, sources: list[dict], flags: dict) -> str:
    allowed = {source.get("url", "") for source in sources} | {source.get("url", "").split("#")[0] for source in sources}
    allowed.discard("")

    def link(match):
        if match.group(2) in allowed:
            return match.group(0)
        flags["unverified_urls"] += 1
        return match.group(1)

    text = MARKDOWN_LINK.sub(link, text)

    def bare(match):
        url = match.group(0).rstrip(".,;:")
        if url in allowed or url.split("#")[0] in allowed:
            return match.group(0)
        flags["unverified_urls"] += 1
        return ""

    text = URL.sub(bare, text)

    def citation(match):
        if 1 <= int(match.group(1)) <= len(sources):
            return match.group(0)
        flags["invalid_citations"] += 1
        return ""

    return CITATION.sub(citation, text)


def _clean(text: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", re.sub(r"\s+([.,;:])", r"\1", text)).strip()


def new_flags() -> dict:
    return {"redacted_hidden": 0, "solution_like": 0, "reference_overlap": 0, "long_code_blocks": 0,
            "invalid_citations": 0, "unverified_urls": 0, "limitation_added": False}


def sanitize(text: str, *, fragments: list[str], reference_only: set, sources: list[dict], flags: dict) -> str:
    text = text or ""
    for fragment in fragments:
        if fragment in text:
            flags["redacted_hidden"] += text.count(fragment)
            text = text.replace(fragment, HIDDEN_PLACEHOLDER)
    text = _strip_code(text, reference_only, flags)
    return _clean(_strip_links(text, sources, flags))


def grounding_entities(context: dict) -> set[str]:
    entities = set()
    execution = context.get("execution") or {}
    for case in execution.get("failing_public", []):
        entities.add(case["name"].lower())
    for example in context["problem"]["examples"]:
        entities.add(example["name"].lower())
    for name in WORD.findall(context["code"]["current"] or ""):
        if name.lower() not in GENERIC_WORDS and len(name) > 3:
            entities.add(name.lower())
    for requirement in context["problem"]["requirements"]:
        entities.update(word.lower() for word in WORD.findall(requirement)
                        if len(word) > 5 and word.lower() not in GENERIC_WORDS)
    entities.update(name.lower() for name in context["problem"]["bug_category_names"])
    return entities


def grounding(sections: list[dict], context: dict) -> dict:
    """Share of sentences that cite a source or mention a concrete element of the user's context."""
    entities = grounding_entities(context)
    sentences = []
    for section in sections:
        sentences += [part for part in re.split(r"(?<=[.!?])\s+|\n+", section["body"]) if len(part.strip()) > 12]
    grounded = 0
    for sentence in sentences:
        lowered = sentence.lower()
        if CITATION.search(sentence) or re.search(r"\bline \d+\b", lowered) or "`" in sentence or any(
                entity in lowered for entity in entities):
            grounded += 1
    total = len(sentences)
    return {"grounding_score": round(grounded / total, 2) if total else 0.0, "grounded_sentences": grounded,
            "total_sentences": total}


def validate_sections(sections: list[dict], *, problem, context: dict, sources: list[dict]) -> tuple[list[dict], dict]:
    flags = new_flags()
    fragments = hidden_fragments(problem, public_material(problem, context))
    reference_only = reference_only_shingles(problem, context)
    cleaned = []
    for section in sections:
        body = sanitize(section.get("body", ""), fragments=fragments, reference_only=reference_only,
                        sources=sources, flags=flags)
        if body and body != CODE_PLACEHOLDER:
            cleaned.append({**section, "body": body})
    if context.get("execution") is None and cleaned and not any(
            LIMITATION_CUES.search(section["body"]) for section in cleaned):
        cleaned[0] = {**cleaned[0], "body": f"{LIMITATION_NOTE} {cleaned[0]['body']}"}
        flags["limitation_added"] = True
    flags.update(grounding(cleaned, context))
    flags["blocked"] = bool(flags["redacted_hidden"] or flags["solution_like"] or flags["reference_overlap"])
    flags["low_grounding"] = flags["total_sentences"] > 0 and flags["grounding_score"] < 0.3
    return cleaned, flags


def validate_text(text: str, *, problem, context: dict, sources: list[dict]) -> tuple[str, dict]:
    """Single-text variant used for adaptive hints."""
    flags = new_flags()
    body = sanitize(text, fragments=hidden_fragments(problem, public_material(problem, context)),
                    reference_only=reference_only_shingles(problem, context), sources=sources, flags=flags)
    flags["blocked"] = bool(flags["redacted_hidden"] or flags["solution_like"] or flags["reference_overlap"])
    return body, flags
