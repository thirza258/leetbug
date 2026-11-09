"""Deterministic text analysis for diagnosis and explanation scoring.

Matching is lexical: lowercase words split from identifiers (snake_case and camelCase), a light
suffix stemmer, and prefix tolerance for longer words. It is deliberately simple, stable across
Python versions, and explainable; semantic judgement is the optional AI layer's job.
"""
import math
import re
from difflib import SequenceMatcher

WORD = re.compile(r"[A-Za-z0-9_]+")
CAMEL = re.compile(r"([a-z0-9])([A-Z])")

STOP_WORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being below between
both but by can cannot could did do does doing down during each either else even ever every few for from further
had has have having he her here hers him his how however i if in into is it its itself just least less let like
make makes many may me might more most much must my need needs no nor not now of off often on once one only or
other our out over own per rather same should since so some such than that the their them then there these they
this those though through thus to too under until up upon us very via was we were what when where whether which
while who whom whose why will with within without would yet you your
""".split())

# Words that appear in nearly every problem statement and say nothing about a specific defect.
GENERIC_WORDS = frozenset("""
solve data return returns returned value values result results input inputs output outputs function functions
code program programs time space extra case cases test tests example examples problem problems bug bugs fix fixed
fixes work works working correct correctly incorrect wrong right way thing things also first second third keep
make makes made use uses using used get gets got set sets new old current given give gives true false null none
behave behaves behaving calculate calculates calculating calculation determine determines read reads final
directly equal handle handles handling instead happen happens change changes changing ensure ensures still actual
expected whether once another already simply just really part parts step steps look looks looking point points
""".split())

INVARIANT_SHAPE = ("must", "never", "always", "only", "at most", "at least", "exactly", "should", "cannot",
                   "can't", "must not", "no more than", "no less than", "every", "invariant", "guarantee",
                   "remain", "remains", "stay", "stays", "hold", "holds")

_RULES = (
    ("ational", "ate"), ("ization", "ize"), ("isation", "ize"), ("ically", "ic"), ("ations", "ate"),
    ("ation", "ate"), ("ingly", ""), ("edly", ""), ("ency", "ent"), ("ancy", "ant"), ("ence", "ent"),
    ("ance", "ant"), ("ings", ""), ("ing", ""), ("ally", "al"), ("ness", ""), ("ment", ""), ("ies", "y"),
    ("ied", "y"), ("sses", "ss"), ("ches", "ch"), ("shes", "sh"), ("xes", "x"), ("ed", ""), ("ly", ""),
    ("ers", "er"), ("s", ""),
)


def split_identifier(raw: str) -> list[str]:
    return CAMEL.sub(r"\1 \2", raw).replace("_", " ").lower().split()


def words(text: str) -> list[str]:
    """Lowercase word pieces in reading order; identifiers are split into their parts."""
    pieces: list[str] = []
    for raw in WORD.findall(text or ""):
        pieces.extend(split_identifier(raw))
    return pieces


def identifiers(text: str) -> set[str]:
    """Whole identifiers as written (lowercased), plus their pieces."""
    found = set()
    for raw in WORD.findall(text or ""):
        found.add(raw.lower())
        found.update(split_identifier(raw))
    return found


def _stem_once(word: str) -> str:
    if len(word) <= 3 or word.isdigit():
        return word
    for suffix, replacement in _RULES:
        if not word.endswith(suffix):
            continue
        if suffix == "s" and word.endswith(("ss", "us", "is")):
            return word
        base = word[: -len(suffix)] + replacement
        if len(base) >= 3:
            return base
    return word


def stem(word: str) -> str:
    first = _stem_once(word.lower())
    return _stem_once(first) if first != word.lower() else first


def word_match(a: str, b: str) -> bool:
    """Equality of stems, with prefix tolerance between longer words (validate/validation)."""
    if a == b:
        return True
    if min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a)):
        return True
    return False


class Text:
    """A pre-processed text for repeated concept matching."""

    def __init__(self, raw: str):
        self.raw = raw or ""
        self.words = words(self.raw)
        self.stems = [stem(word) for word in self.words]
        self.identifiers = identifiers(self.raw)
        self._stem_set = set(self.stems)

    def has_phrase(self, phrase: str) -> bool:
        target = [stem(word) for word in words(phrase)]
        if not target:
            return False
        if len(target) == 1:
            needle = target[0]
            return needle in self._stem_set or any(word_match(needle, item) for item in self._stem_set)
        span = len(target)
        for start in range(len(self.stems) - span + 1):
            if all(word_match(self.stems[start + offset], target[offset]) for offset in range(span)):
                return True
        return False

    def matches_group(self, group: list[str]) -> bool:
        return any(self.has_phrase(phrase) for phrase in group)

    def content_stems(self) -> set[str]:
        return {stem for stem, word in zip(self.stems, self.words, strict=True)
                if word not in STOP_WORDS and word not in GENERIC_WORDS and len(word) >= 3 and not word.isdigit()}


def coverage(text: Text, groups: list[list[str]], ratio: float) -> tuple[float, list[int]]:
    """Share of the needed concept groups that the text mentions, saturating at 1.

    ``ratio`` sets how many groups are needed for full credit (e.g. 0.4 of all groups), so a
    focused answer does not have to repeat every phrasing in the rubric.
    """
    if not groups:
        return 0.0, []
    matched = [index for index, group in enumerate(groups) if text.matches_group(group)]
    needed = max(1, math.floor(ratio * len(groups) + 0.5))
    return min(1.0, len(matched) / needed), matched


def has_invariant_shape(text: Text) -> bool:
    lowered = " " + " ".join(text.words) + " "
    return any(f" {phrase} " in lowered for phrase in INVARIANT_SHAPE)


def looks_like_gibberish(raw: str) -> bool:
    stripped = (raw or "").strip()
    if not stripped:
        return True
    if re.search(r"(.)\1{5,}", stripped):
        return True
    tokens = [word for word in words(stripped) if not word.isdigit()]
    if not tokens:
        return True
    if len(tokens) >= 6 and len(set(tokens)) / len(tokens) < 0.3:
        return True
    alphabetic = [word for word in tokens if word.isalpha() and len(word) > 3]
    if len(alphabetic) >= 3:
        vowelless = sum(1 for word in alphabetic if not re.search(r"[aeiouy]", word))
        if vowelless / len(alphabetic) > 0.5:
            return True
    return False


def too_short(raw: str, *, min_chars: int = 12, min_words: int = 3) -> bool:
    stripped = (raw or "").strip()
    return len(stripped) < min_chars or len(words(stripped)) < min_words


def similarity(a: str, b: str) -> float:
    left, right = " ".join(words(a)), " ".join(words(b))
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=left, b=right, autojunk=False).ratio()


def overlap_ratio(text: Text, reference: Text) -> float:
    """Share of the text's content words that also occur in the reference."""
    own = text.content_stems()
    if not own:
        return 0.0
    other = reference.content_stems()
    return sum(1 for item in own if item in other) / len(own)


def shingles(raw: str, size: int = 4) -> set[tuple[str, ...]]:
    tokens = [word for word in words(raw) if word not in STOP_WORDS]
    return {tuple(tokens[index:index + size]) for index in range(len(tokens) - size + 1)}
