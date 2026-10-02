"""Curriculum loading and concept sequencing for a topic."""

from __future__ import annotations

import json
from pathlib import Path

from config import CURRICULUM_JSON_PATH
from engine.concepts import ConceptRegistry


class CurriculumService:
    """
    Provides ordered concept lists for a topic.

    Uses ConceptRegistry first; merges with saved learning_path.json when present.
    """

    def __init__(self, concepts: ConceptRegistry | None = None) -> None:
        self.concepts = concepts or ConceptRegistry()

    def get_concepts_for_topic(self, topic: str) -> list[str]:
        """Return ordered concepts to study for this topic."""
        from_curriculum = self._load_from_json(topic)
        if from_curriculum:
            return from_curriculum
        return self.concepts.get_concepts_for_topic(topic)

    def _load_from_json(self, topic: str) -> list[str]:
        path = CURRICULUM_JSON_PATH
        if not path.exists():
            return []
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return []

        topic_key = self._normalize_topic(topic)
        concepts: list[str] = []
        for step in data.get("learning_path", []):
            if self._step_matches_topic(step, topic_key):
                c = step.get("subtopic") or step.get("domain", "")
                if c and c not in concepts:
                    concepts.append(c.replace(" ", "_"))
        if concepts:
            return concepts

        for block in data.get("major_topics", []):
            if self._block_matches_topic(block, topic_key):
                for unit in block.get("units", []):
                    for kw in unit.get("keywords", [])[:1]:
                        if kw not in concepts:
                            concepts.append(kw)
        return concepts

    @staticmethod
    def _normalize_topic(topic: str) -> str:
        t = topic.lower().strip()
        aliases = {
            "linear algebra": "math",
            "linear_algebra": "math",
            "algorithms": "cs",
            "computer science": "cs",
            "mechanics": "physics",
        }
        return aliases.get(t, t)

    @staticmethod
    def _step_matches_topic(step: dict, topic_key: str) -> bool:
        domain = step.get("domain", "")
        sub = step.get("subtopic", "")
        return topic_key in (domain, sub, f"{domain}_{sub}")

    @staticmethod
    def _block_matches_topic(block: dict, topic_key: str) -> bool:
        return topic_key in (block.get("domain", ""), block.get("subtopic", ""))

    def build_or_refresh(self) -> Path | None:
        """Run curriculum engine to generate learning_path.json."""
        from pipeline.curriculum_engine import CurriculumEngine

        engine = CurriculumEngine()
        result = engine.run()
        if result.output_path:
            return Path(result.output_path)
        return None
