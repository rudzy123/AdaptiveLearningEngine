"""Ordered concept curricula per topic and problem-to-concept mapping."""

from __future__ import annotations

import json
import re
from pathlib import Path

from config import CURRICULUM_JSON_PATH

# Ordered learning sequences per topic (canonical concept ids)
TOPIC_CONCEPT_ORDER: dict[str, list[str]] = {
    "math": [
        "vectors",
        "matrices",
        "gaussian_elimination",
        "determinants",
        "rank",
        "subspaces",
        "orthogonality",
        "linear_transformations",
        "matrix_decomposition",
        "eigenvalues",
        "eigenvectors",
    ],
    "linear_algebra": [
        "vectors",
        "matrices",
        "gaussian_elimination",
        "determinants",
        "rank",
        "subspaces",
        "orthogonality",
        "linear_transformations",
        "matrix_decomposition",
        "eigenvalues",
        "eigenvectors",
    ],
    "physics": [
        "kinematics",
        "forces",
        "newtons_laws",
        "energy",
        "momentum",
        "rotation",
        "equilibrium",
        "thermodynamics",
        "temperature",
        "heat",
        "entropy",
        "ideal_gas",
        "chemical_equilibrium",
        "phase_transitions",
    ],
    "mechanics": [
        "kinematics",
        "forces",
        "newtons_laws",
        "energy",
        "momentum",
        "rotation",
        "equilibrium",
    ],
    "thermodynamics": [
        "thermodynamics",
        "temperature",
        "heat",
        "entropy",
        "ideal_gas",
        "chemical_equilibrium",
        "phase_transitions",
    ],
    "cs": [
        "algorithms",
        "complexity_analysis",
        "data_structures",
        "sorting",
        "divide_and_conquer",
        "recurrence_relations",
        "hashing",
        "trees",
        "heaps",
        "graphs",
        "breadth_first_search",
        "depth_first_search",
        "shortest_paths",
        "dynamic_programming",
    ],
    "algorithms": [
        "algorithms",
        "complexity_analysis",
        "data_structures",
        "sorting",
        "divide_and_conquer",
        "recurrence_relations",
        "hashing",
        "trees",
        "heaps",
        "graphs",
        "breadth_first_search",
        "depth_first_search",
        "shortest_paths",
        "dynamic_programming",
    ],
}

# Human-readable labels for display
CONCEPT_LABELS: dict[str, str] = {
    "vectors": "Vectors",
    "matrices": "Matrix Multiplication",
    "gaussian_elimination": "Gaussian Elimination",
    "determinants": "Determinants",
    "eigenvalues": "Eigenvalues",
    "eigenvectors": "Eigenvectors",
    "entropy": "Entropy",
    "thermodynamics": "Thermodynamics",
    "dynamic_programming": "Dynamic Programming",
    "sorting": "Sorting Algorithms",
}

# Keywords in problem text → concept
PROBLEM_CONCEPT_KEYWORDS: dict[str, list[str]] = {
    "eigenvalues": ["eigenvalue", "eigenvalues", "characteristic polynomial"],
    "eigenvectors": ["eigenvector", "eigenvectors"],
    "determinants": ["determinant", "det("],
    "matrices": ["matrix", "matrices", "multiply"],
    "vectors": ["vector", "dot product", "cross product"],
    "entropy": ["entropy", "second law"],
    "thermodynamics": ["thermodynamic", "heat engine"],
    "sorting": ["sort", "sorted", "permutation"],
    "dynamic_programming": ["dynamic programming", "memoization", "optimal substructure"],
    "graphs": ["graph", "vertex", "edge", "adjacency"],
    "breadth_first_search": ["bfs", "breadth-first"],
    "depth_first_search": ["dfs", "depth-first"],
}


class ConceptRegistry:
    """
    Maintains ordered concept lists per topic and maps content to concepts.

    Can merge curriculum JSON from build_curriculum when available.
    """

    def __init__(self) -> None:
        self._order = dict(TOPIC_CONCEPT_ORDER)
        self._load_curriculum_concepts()

    def _load_curriculum_concepts(self) -> None:
        """Augment order from generated curriculum if present."""
        path = CURRICULUM_JSON_PATH
        if not path.exists():
            return
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            for topic_info in data.get("major_topics", []):
                domain = topic_info.get("domain", "")
                subtopic = topic_info.get("subtopic", "")
                concepts = topic_info.get("concepts", [])
                if domain and concepts:
                    key = subtopic or domain
                    existing = self._order.get(key, [])
                    merged = list(dict.fromkeys(existing + concepts))
                    self._order[key] = merged
        except (json.JSONDecodeError, OSError):
            pass

    def get_concepts_for_topic(self, topic: str) -> list[str]:
        """Return ordered concept list for a topic key."""
        topic_key = topic.lower().replace(" ", "_")
        if topic_key in self._order:
            return list(self._order[topic_key])
        # Alias: linear algebra → math sequence
        if "algebra" in topic_key:
            return list(self._order.get("linear_algebra", self._order["math"]))
        if "algorithm" in topic_key:
            return list(self._order.get("algorithms", self._order["cs"]))
        if "mechanic" in topic_key:
            return list(self._order.get("mechanics", self._order["physics"]))
        return list(self._order.get(topic_key, []))

    def get_next_concept(self, topic: str, current_concept: str) -> str | None:
        """Return the next concept in the topic sequence, or None at end."""
        concepts = self.get_concepts_for_topic(topic)
        if not concepts:
            return None
        if not current_concept:
            return concepts[0]
        try:
            idx = concepts.index(current_concept)
            if idx + 1 < len(concepts):
                return concepts[idx + 1]
        except ValueError:
            pass
        return None

    def get_first_concept(self, topic: str) -> str:
        concepts = self.get_concepts_for_topic(topic)
        return concepts[0] if concepts else "general"

    def label(self, concept: str) -> str:
        return CONCEPT_LABELS.get(concept, concept.replace("_", " ").title())

    def map_problem_to_concept(
        self, problem_text: str, topic: str | None = None
    ) -> str:
        """
        Infer the primary concept tested by a problem from its text.

        Falls back to topic's first concept or 'general'.
        """
        text = problem_text.lower()
        best_concept = ""
        best_hits = 0

        candidates = list(PROBLEM_CONCEPT_KEYWORDS.keys())
        if topic:
            candidates = self.get_concepts_for_topic(topic) + candidates

        for concept in dict.fromkeys(candidates):
            keywords = PROBLEM_CONCEPT_KEYWORDS.get(concept, [concept.replace("_", " ")])
            hits = sum(1 for kw in keywords if kw in text)
            if hits > best_hits:
                best_hits = hits
                best_concept = concept

        if best_concept:
            return best_concept
        if topic:
            return self.get_first_concept(topic)
        return "general"

    def normalize_concept(self, concept: str) -> str:
        """Normalize user-facing concept strings to canonical ids."""
        c = concept.strip().lower().replace(" ", "_").replace("-", "_")
        for canonical in self.get_concepts_for_topic("math") + self.get_concepts_for_topic("cs"):
            if c == canonical or c in canonical or canonical in c:
                return canonical
        return c
