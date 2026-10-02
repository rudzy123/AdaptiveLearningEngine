"""Curriculum: topics, concepts (ordered, with prerequisites implied by order) and the problem bank."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ale.engine.config import CURRICULUM_PATH

KINDS = ("numeric", "text", "complexity")
ERROR_TYPES = ("conceptual_error", "calculation_error", "misinterpretation", "incomplete")


@dataclass(frozen=True)
class Signature:
    """A known wrong answer and the error type it indicates."""

    type: str
    note: str
    numbers: tuple[float, ...] | None = None
    pattern: str | None = None
    forms: tuple[str, ...] | None = None
    example: str | None = None


@dataclass(frozen=True)
class Problem:
    id: str
    concept: str
    difficulty: int
    kind: str
    prompt: str
    format: str
    answer: tuple = ()  # numbers (numeric) or canonical forms (complexity)
    ordered: bool = True
    accepted: tuple[str, ...] = ()  # text: accepted exact phrases
    key_points: tuple[tuple[str, ...], ...] = ()  # text: groups of alternatives, all groups required
    reasoning_terms: tuple[str, ...] = ()
    signatures: tuple[Signature, ...] = ()
    hint: str = ""
    explanation: str = ""

    @property
    def correct_answer_text(self) -> str:
        """A human-readable correct answer (used by the research simulator and feedback)."""
        if self.kind == "numeric":
            return ", ".join(_fmt(x) for x in self.answer)
        if self.kind == "complexity":
            return "O(" + str(self.answer[0]) + ")"
        return self.accepted[0] if self.accepted else self.explanation


@dataclass(frozen=True)
class Concept:
    id: str
    title: str
    objective: str
    query: str
    topic: str
    problems: tuple[Problem, ...] = ()


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    aliases: tuple[str, ...]
    concepts: tuple[str, ...]


@dataclass
class Curriculum:
    topics: dict[str, Topic] = field(default_factory=dict)
    concepts: dict[str, Concept] = field(default_factory=dict)

    # lookups -----------------------------------------------------------
    def find_topic(self, text: str) -> Topic | None:
        needle = " ".join(text.lower().replace("_", " ").split())
        for t in self.topics.values():
            if needle in {t.id.replace("_", " "), t.title.lower(), *t.aliases}:
                return t
        for t in self.topics.values():  # loose containment, e.g. "intro to linear algebra"
            if any(a in needle for a in (t.title.lower(), *t.aliases)):
                return t
        return None

    def next_concept(self, concept_id: str) -> str | None:
        topic = self.topics[self.concepts[concept_id].topic]
        i = topic.concepts.index(concept_id)
        return topic.concepts[i + 1] if i + 1 < len(topic.concepts) else None

    def problem(self, bank_id: str) -> Problem:
        for c in self.concepts.values():
            for p in c.problems:
                if p.id == bank_id:
                    return p
        raise KeyError(bank_id)

    def all_problems(self) -> list[Problem]:
        return [p for c in self.concepts.values() for p in c.problems]


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def _signature(raw: dict[str, Any]) -> Signature:
    if raw["type"] not in ERROR_TYPES:
        raise ValueError(f"unknown error type {raw['type']!r}")
    return Signature(
        type=raw["type"],
        note=raw["note"],
        numbers=tuple(raw["numbers"]) if "numbers" in raw else None,
        pattern=raw.get("pattern"),
        forms=tuple(raw["forms"]) if "forms" in raw else None,
        example=raw.get("example"),
    )


def _problem(concept: str, raw: dict[str, Any]) -> Problem:
    if raw["kind"] not in KINDS:
        raise ValueError(f"{raw['id']}: unknown kind {raw['kind']!r}")
    if not 1 <= raw["difficulty"] <= 3:
        raise ValueError(f"{raw['id']}: difficulty must be 1..3")
    return Problem(
        id=raw["id"],
        concept=concept,
        difficulty=raw["difficulty"],
        kind=raw["kind"],
        prompt=raw["prompt"],
        format=raw.get("format", ""),
        answer=tuple(raw.get("answer", ())),
        ordered=raw.get("ordered", True),
        accepted=tuple(raw.get("accepted", ())),
        key_points=tuple(tuple(g) for g in raw.get("key_points", ())),
        reasoning_terms=tuple(raw.get("reasoning_terms", ())),
        signatures=tuple(_signature(s) for s in raw.get("signatures", ())),
        hint=raw.get("hint", ""),
        explanation=raw.get("explanation", ""),
    )


def parse_curriculum(raw: dict[str, Any]) -> Curriculum:
    cur = Curriculum()
    for t in raw["topics"]:
        cur.topics[t["id"]] = Topic(t["id"], t["title"], tuple(t.get("aliases", ())), tuple(t["concepts"]))
    for topic in cur.topics.values():
        for cid in topic.concepts:
            c = raw["concepts"][cid]
            cur.concepts[cid] = Concept(
                id=cid,
                title=c["title"],
                objective=c["objective"],
                query=c["query"],
                topic=topic.id,
                problems=tuple(_problem(cid, p) for p in c["problems"]),
            )
    seen: set[str] = set()
    for p in cur.all_problems():
        if p.id in seen:
            raise ValueError(f"duplicate problem id {p.id}")
        seen.add(p.id)
    return cur


@lru_cache(maxsize=1)
def load_curriculum(path: str | None = None) -> Curriculum:
    p = Path(path) if path else CURRICULUM_PATH
    return parse_curriculum(json.loads(p.read_text(encoding="utf-8")))
