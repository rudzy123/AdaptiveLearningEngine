"""Five-layer answer evaluation. Deterministic, local, no model calls.

Layers (each is a separate function with its own output so it can be tested and shown):

1. exact_match         exact / numeric match against the problem's answer key
2. partial_credit      fraction of required values or key points present
3. reasoning_alignment overlap between the learner's answer + reasoning and the concept's reasoning terms
4. error_typing        conceptual_error | calculation_error | misinterpretation | incomplete | none
5. confidence_delta    how this attempt moves the learner's confidence in the concept

The composite score is  0.85 * max(exact, 0.9 * partial) + 0.15 * reasoning  and an answer passes at >= 0.7.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from ale.engine.config import (
    EARLY_ATTEMPTS,
    EXACT_WEIGHT,
    LEARNING_RATE_EARLY,
    LEARNING_RATE_LATE,
    PARTIAL_CAP,
    PASS_SCORE,
    REASONING_WEIGHT,
)
from ale.engine.curriculum import Problem, Signature
from ale.engine.text import contains_phrase, normalize, numbers, stem, stems, words

NUMBER_TOLERANCE = 0.01
NEGATIONS = frozenset(
    {"not", "no", "never", "cannot", "without", "isn", "don", "doesn", "aren", "wasn", "won", "isnt", "dont", "cant"}
)
_IDK = re.compile(r"^\W*(i\s+)?(don'?t|do not|dont)\s+know\W*$|^\W*(idk|no idea|not sure|skip|\?+)\W*$", re.I)

_WORD_FORMS = {
    "constant": "1", "logarithmic": "logn", "linear": "n", "linearithmic": "nlogn",
    "quadratic": "n2", "cubic": "n3",
}
_FORM_SHAPE = re.compile(r"(?:\d*n\d*)?(?:logn)?|\d+")


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

@dataclass
class Parsed:
    raw: str
    numbers: list[float] = field(default_factory=list)
    forms: set[str] = field(default_factory=set)
    stems: list[str] = field(default_factory=list)


def _balanced_o_contents(t: str) -> list[str]:
    out = []
    for m in re.finditer(r"\bo\s*\(", t):
        depth, i = 1, m.end()
        while i < len(t) and depth:
            depth += {"(": 1, ")": -1}.get(t[i], 0)
            i += 1
        if depth == 0:
            out.append(t[m.end() : i - 1])
    return out


def canonical_form(expr: str) -> str:
    s = normalize(expr)
    s = re.sub(r"\bsquared\b", "2", s)
    s = re.sub(r"\bcubed\b", "3", s)
    s = re.sub(r"log_?2|\blg\b|\bln\b", "log", s)
    s = re.sub(r"[\s*^()]", "", s)
    return {"nn": "n2", "nnn": "n3"}.get(s, s)


def parse_complexity(text: str) -> set[str]:
    t = normalize(text)
    forms = {canonical_form(c) for c in _balanced_o_contents(t)}
    forms |= {_WORD_FORMS[w] for w in words(t) if w in _WORD_FORMS}
    whole = canonical_form(t.strip().rstrip("."))
    if whole and _FORM_SHAPE.fullmatch(whole):
        forms.add(whole)
    forms.discard("")
    return forms


def parse(problem: Problem, answer: str, reasoning: str = "") -> Parsed:
    p = Parsed(raw=answer, stems=stems(answer))
    if problem.kind == "numeric":
        p.numbers = numbers(answer)
    elif problem.kind == "complexity":
        p.forms = parse_complexity(answer)
    return p


# --------------------------------------------------------------------------
# Matching helpers
# --------------------------------------------------------------------------

def match_numbers(given: list[float], expected: list[float], ordered: bool) -> int:
    """Number of expected values matched (positionally if ordered, else as a multiset)."""
    if ordered:
        return sum(1 for g, e in zip(given, expected) if abs(g - e) <= NUMBER_TOLERANCE)
    pool = list(given)
    hits = 0
    for e in expected:
        for i, g in enumerate(pool):
            if abs(g - e) <= NUMBER_TOLERANCE:
                hits += 1
                pool.pop(i)
                break
    return hits


def _negated(tokens: list[str], index: int) -> bool:
    return any(t in NEGATIONS for t in tokens[max(0, index - 2) : index])


def _phrase_stems(phrase: str) -> list[str]:
    return stems(phrase)


def text_exact(problem: Problem, parsed: Parsed) -> bool:
    for phrase in problem.accepted:
        ps = _phrase_stems(phrase)
        i = contains_phrase(parsed.stems, ps)
        if i >= 0 and not _negated(parsed.stems, i):
            return True
    return False


def key_points_hit(problem: Problem, parsed: Parsed) -> list[bool]:
    return [
        any(contains_phrase(parsed.stems, _phrase_stems(alt)) >= 0 for alt in group)
        for group in problem.key_points
    ]


def _numeric_match(problem: Problem, parsed: Parsed) -> tuple[int, int, int]:
    expected = list(problem.answer)
    matched = match_numbers(parsed.numbers, expected, problem.ordered)
    return matched, len(expected), len(parsed.numbers)


# --------------------------------------------------------------------------
# Layer 1: exact / numeric match
# --------------------------------------------------------------------------

def layer_exact(problem: Problem, parsed: Parsed) -> dict[str, Any]:
    if problem.kind == "numeric":
        matched, n_exp, n_given = _numeric_match(problem, parsed)
        ok = matched == n_exp == n_given
        detail = (
            f"numeric match within {NUMBER_TOLERANCE}: {matched}/{n_exp} values equal"
            + (f", {n_given - matched} extra" if n_given > matched and n_given != n_exp else "")
        )
    elif problem.kind == "complexity":
        ok = bool(parsed.forms) and parsed.forms <= {str(a) for a in problem.answer}
        detail = "parsed complexity: " + (", ".join(sorted(parsed.forms)) or "none recognised")
    else:
        ok = text_exact(problem, parsed)
        detail = "matched an accepted phrase" if ok else "no accepted phrase found"
    return {"layer": 1, "name": "exact_match", "score": 1.0 if ok else 0.0, "passed": ok, "detail": detail}


# --------------------------------------------------------------------------
# Layer 2: partial credit
# --------------------------------------------------------------------------

def layer_partial(problem: Problem, parsed: Parsed, exact: bool) -> dict[str, Any]:
    if exact:
        return {"layer": 2, "name": "partial_credit", "score": 1.0, "passed": True, "detail": "all required parts present"}
    if problem.kind == "numeric":
        matched, n_exp, n_given = _numeric_match(problem, parsed)
        score = matched / max(n_exp, n_given) if max(n_exp, n_given) else 0.0
        detail = f"{matched} of {n_exp} required values correct"
    elif problem.kind == "complexity":
        score, detail = 0.0, "complexity class does not match"
    elif problem.key_points:
        hits = key_points_hit(problem, parsed)
        score = sum(hits) / len(hits)
        detail = f"{sum(hits)} of {len(hits)} key points present"
    else:
        score, detail = 0.0, "no required key point present"
    return {"layer": 2, "name": "partial_credit", "score": round(score, 3), "passed": score >= 1.0, "detail": detail}


# --------------------------------------------------------------------------
# Layer 3: reasoning alignment
# --------------------------------------------------------------------------

def layer_reasoning(problem: Problem, answer: str, reasoning: str = "") -> dict[str, Any]:
    terms = problem.reasoning_terms
    if not terms:
        return {"layer": 3, "name": "reasoning_alignment", "score": 0.0, "passed": False,
                "detail": "no reasoning terms defined", "matched_terms": []}
    have = set(stems(f"{answer} {reasoning}"))
    matched = [t for t in terms if stem(normalize(t)) in have]
    needed = math.ceil(len(terms) / 2)
    score = min(1.0, len(matched) / needed)
    return {
        "layer": 3, "name": "reasoning_alignment", "score": round(score, 3), "passed": score >= 1.0,
        "detail": f"{len(matched)} of {len(terms)} concept terms used (needs {needed} for full alignment)",
        "matched_terms": matched,
    }


# --------------------------------------------------------------------------
# Layer 4: error typing
# --------------------------------------------------------------------------

def _near(g: float, e: float) -> bool:
    if abs(g - e) <= 1 or g == -e:
        return True
    if e != 0 and abs(g - e) / abs(e) <= 0.25:
        return True
    if float(g).is_integer() and float(e).is_integer():
        return sorted(str(abs(int(g)))) == sorted(str(abs(int(e)))) and g != e
    return False


def _signature_matches(problem: Problem, sig: Signature, parsed: Parsed) -> bool:
    if sig.numbers is not None and problem.kind == "numeric":
        g = parsed.numbers
        s = list(sig.numbers)
        return len(g) == len(s) and match_numbers(g, s, problem.ordered) == len(s)
    if sig.forms is not None:
        return any(f in parsed.forms for f in sig.forms)
    if sig.pattern is not None:
        return re.search(sig.pattern, normalize(parsed.raw)) is not None
    return False


def layer_error_type(problem: Problem, parsed: Parsed, exact: bool, partial: float, passed: bool) -> dict[str, Any]:
    def out(kind: str, evidence: str) -> dict[str, Any]:
        return {"layer": 4, "name": "error_typing", "error_type": kind, "score": None, "passed": kind == "none",
                "detail": evidence}

    if passed:
        return out("none", "no error")
    text = parsed.raw.strip()
    if not text or _IDK.match(text):
        return out("incomplete", "no attempt was made")
    for sig in problem.signatures:
        if _signature_matches(problem, sig, parsed):
            return out(sig.type, sig.note)

    if problem.kind == "numeric":
        given, expected = parsed.numbers, list(problem.answer)
        if not given:
            return out("misinterpretation", "no number found where a numeric answer was requested")
        if 0 < partial < 1:
            if len(given) < len(expected):
                return out("incomplete", f"gave {len(given)} of the {len(expected)} values requested")
            if len(given) == len(expected):
                good = round(partial * len(expected))
                return out("calculation_error", f"{good} of {len(expected)} entries are right; recheck the arithmetic on the rest")
            return out("misinterpretation", f"gave {len(given)} values but only {len(expected)} were requested")
        prompt_numbers = set(numbers(problem.prompt))
        if all(g in prompt_numbers for g in given):
            return out("misinterpretation", "restated numbers from the problem instead of computing a result")
        if len(given) != len(expected):
            return out("misinterpretation", f"answer has {len(given)} value(s); the question asks for {len(expected)}")
        if all(_near(g, e) for g, e in zip(given, expected)):
            return out("calculation_error", "the method looks right but the result is slightly off")
        return out("conceptual_error", "the result differs from the expected value by more than an arithmetic slip")

    if problem.kind == "complexity":
        if not parsed.forms:
            return out("misinterpretation", "no complexity class (such as O(n)) was recognised in the answer")
        return out("conceptual_error", "that growth rate does not match the algorithm described")

    # text
    if 0 < partial < 1:
        hits = round(partial * len(problem.key_points))
        return out("incomplete", f"covers {hits} of {len(problem.key_points)} required points")
    vocabulary = set(stems(problem.prompt)) | {stem(normalize(t)) for t in problem.reasoning_terms}
    if not vocabulary & set(parsed.stems):
        return out("misinterpretation", "the answer does not engage with what the question asked")
    return out("conceptual_error", "the answer uses the right vocabulary but states something incorrect")


# --------------------------------------------------------------------------
# Layer 5: confidence delta
# --------------------------------------------------------------------------

def update_confidence(before: float, score: float, attempts: int) -> tuple[float, float, float]:
    """Move confidence toward the attempt score. Returns (after, delta, learning_rate)."""
    lr = LEARNING_RATE_EARLY if attempts < EARLY_ATTEMPTS else LEARNING_RATE_LATE
    after = min(1.0, max(0.0, before + lr * (score - before)))
    return round(after, 3), round(after - before, 3), lr


def layer_confidence(before: float, score: float, attempts: int) -> dict[str, Any]:
    after, delta, lr = update_confidence(before, score, attempts)
    return {
        "layer": 5, "name": "confidence_delta", "score": None, "passed": delta >= 0,
        "before": round(before, 3), "after": after, "delta": delta, "learning_rate": lr,
        "detail": f"learning rate {lr}; new confidence written to concept memory",
    }


# --------------------------------------------------------------------------
# Composite
# --------------------------------------------------------------------------

def composite_score(exact: float, partial: float, reasoning: float) -> float:
    base = max(exact, PARTIAL_CAP * partial)
    return round(EXACT_WEIGHT * base + REASONING_WEIGHT * reasoning, 3)


@dataclass
class Evaluation:
    score: float
    passed: bool
    error_type: str
    layers: list[dict[str, Any]]
    feedback: str
    hint: str
    explanation: str
    confidence_before: float
    confidence_after: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "error_type": self.error_type,
            "layers": self.layers,
            "feedback": self.feedback,
            "hint": self.hint,
            "explanation": self.explanation,
        }


def evaluate(
    problem: Problem,
    answer: str,
    reasoning: str = "",
    *,
    confidence_before: float,
    attempts: int,
) -> Evaluation:
    parsed = parse(problem, answer, reasoning)
    l1 = layer_exact(problem, parsed)
    l2 = layer_partial(problem, parsed, l1["passed"])
    l3 = layer_reasoning(problem, answer, reasoning)
    score = composite_score(l1["score"], l2["score"], l3["score"])
    passed = score >= PASS_SCORE
    l4 = layer_error_type(problem, parsed, l1["passed"], l2["score"], passed)
    l5 = layer_confidence(confidence_before, score, attempts)

    if passed:
        feedback = "Correct. " + problem.explanation
    else:
        feedback = f"Not yet ({l4['error_type'].replace('_', ' ')}): {l4['detail']}."
    return Evaluation(
        score=score,
        passed=passed,
        error_type=l4["error_type"],
        layers=[l1, l2, l3, l4, l5],
        feedback=feedback,
        hint=problem.hint,
        explanation=problem.explanation,
        confidence_before=l5["before"],
        confidence_after=l5["after"],
    )


def learning_signal(concept: str, ev: Evaluation) -> dict[str, Any]:
    """What the rest of the system should believe about the learner after this attempt."""
    weak = ev.confidence_after < 0.5 or ev.error_type in ("conceptual_error", "misinterpretation")
    reasons = []
    if ev.confidence_after < 0.5:
        reasons.append(f"confidence {ev.confidence_after:.2f} is below 0.5")
    if ev.error_type in ("conceptual_error", "misinterpretation"):
        reasons.append(f"last error was {ev.error_type}")
    return {
        "weak_concept": weak,
        "concept": concept,
        "retry_recommended": not ev.passed,
        "reason": "; ".join(reasons) if reasons else "no weakness signal",
    }
