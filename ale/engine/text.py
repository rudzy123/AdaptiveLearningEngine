"""Tokenizing, light stemming and number parsing shared by retrieval and evaluation."""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    """a an the is are was were be been of to in and or it for on that this as by with at from its
    i you we they he she do does did can could would should will what which who how when where why
    one two please then than so if but also into about""".split()
)

_WORD = re.compile(r"\w+", re.UNICODE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def normalize(text: str) -> str:
    """Lowercase and fold typographic variants so '−3' and 'λ' behave."""
    text = text.lower()
    for src, dst in (("\u2212", "-"), ("\u2013", "-"), ("\u2014", "-"), ("\u00d7", " by "), ("\u00b7", "*")):
        text = text.replace(src, dst)
    text = text.replace("\u03bb", " lambda ").replace("\u00b2", "^2").replace("\u00b3", "^3")
    return text


def stem(word: str) -> str:
    """A deliberately small suffix stripper; consistency matters more than linguistics."""
    if len(word) <= 3 or word.isdigit():
        return word
    for suffix, repl in (("ies", "y"), ("sses", "ss")):
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            word = word[: -len(suffix)] + repl
            break
    else:
        for suffix in ("ing", "ed", "es", "ly"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word = word[: -len(suffix)]
                break
        else:
            if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
                word = word[:-1]
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def words(text: str) -> list[str]:
    return _WORD.findall(normalize(text))


def stems(text: str, *, drop_stopwords: bool = True) -> list[str]:
    out = []
    for w in words(text):
        if drop_stopwords and w in STOPWORDS:
            continue
        out.append(stem(w))
    return out


def sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(text.strip())]
    return [s for s in parts if s]


def contains_phrase(haystack: list[str], phrase: list[str]) -> int:
    """Index of the first contiguous occurrence of phrase in haystack, or -1."""
    n = len(phrase)
    if n == 0:
        return -1
    for i in range(len(haystack) - n + 1):
        if haystack[i : i + n] == phrase:
            return i
    return -1


# Numbers -------------------------------------------------------------------

_NUMBER = re.compile(
    r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:/\d+)?"
)
_NUMBER_WORDS = {
    w: i
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
    )
}


def numbers(text: str) -> list[float]:
    """Extract numbers in order. Handles negatives, decimals, a/b fractions, 1,000 style groups."""
    t = normalize(text)
    t = re.sub(r"(?<=[a-z_])\d+", "", t)  # drop subscripts glued to names: lambda1, x2
    found: list[float] = []
    for m in _NUMBER.finditer(t):
        tok = m.group(0).replace(",", "")
        if "/" in tok:
            top, bottom = tok.split("/", 1)
            if float(bottom) == 0:
                continue
            found.append(float(top) / float(bottom))
        else:
            found.append(float(tok))
    if found:
        return found
    return [float(_NUMBER_WORDS[w]) for w in _WORD.findall(t) if w in _NUMBER_WORDS]
