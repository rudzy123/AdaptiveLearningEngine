"""Generate practice problems adapted to user state."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from engine.concepts import ConceptRegistry
from engine.user_state import UserState
from pipeline.retrieval import ChunkRetriever

logger = logging.getLogger(__name__)

# Template banks keyed by concept (local, no API)
PROBLEM_TEMPLATES: dict[str, list[dict]] = {
    "eigenvalues": [
        {
            "question": "What is an eigenvalue λ of matrix A if Av = λv for non-zero v?",
            "answer": "scalar lambda such that Av equals lambda v",
            "difficulty": "beginner",
        },
        {
            "question": "For A = [[2,0],[0,3]], what are the eigenvalues?",
            "answer": "2 and 3",
            "difficulty": "intermediate",
        },
    ],
    "vectors": [
        {
            "question": "Compute the dot product of [1,2] and [3,4].",
            "answer": "11",
            "difficulty": "beginner",
        },
    ],
    "entropy": [
        {
            "question": "Does entropy of an isolated system tend to increase, decrease, or stay fixed?",
            "answer": "increase",
            "difficulty": "beginner",
        },
    ],
    "sorting": [
        {
            "question": "What is the worst-case time complexity of merge sort?",
            "answer": "n log n",
            "difficulty": "intermediate",
        },
    ],
    "dynamic_programming": [
        {
            "question": "Name two properties a problem needs for dynamic programming.",
            "answer": "optimal substructure overlapping subproblems",
            "difficulty": "intermediate",
        },
    ],
    "matrices": [
        {
            "question": "If A is 2×3 and B is 3×4, what size is AB?",
            "answer": "2 by 4",
            "difficulty": "beginner",
        },
    ],
    "determinants": [
        {
            "question": "What is det([[1,2],[3,4]])?",
            "answer": "-2",
            "difficulty": "beginner",
        },
    ],
    "graphs": [
        {
            "question": "Which traversal uses a queue: BFS or DFS?",
            "answer": "bfs",
            "difficulty": "beginner",
        },
    ],
    "general": [
        {
            "question": "In one sentence, state the main idea of this lesson.",
            "answer": "main idea",
            "difficulty": "beginner",
        },
    ],
}


@dataclass
class GeneratedProblem:
    """A practice problem with expected answer for evaluation."""

    problem_id: str
    concept: str
    question: str
    expected_answer: str
    difficulty: str
    hint: str = ""
    source_excerpt: str = ""
    metadata: dict = field(default_factory=dict)


class ProblemGenerator:
    """
    Creates problems prioritizing weak concepts and current difficulty.

    Pulls context from chunks when templates are insufficient.
    """

    def __init__(
        self,
        retriever: ChunkRetriever | None = None,
        concepts: ConceptRegistry | None = None,
    ) -> None:
        self.concepts = concepts or ConceptRegistry()
        self._retriever = retriever
        self._retriever_loaded = False
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"prob_{self._counter}"

    def _get_retriever(self) -> ChunkRetriever:
        if self._retriever is None:
            self._retriever = ChunkRetriever()
        if not self._retriever_loaded:
            try:
                self._retriever.load()
                self._retriever_loaded = True
            except FileNotFoundError:
                logger.warning("Retriever not loaded; using templates only")
        return self._retriever

    def generate_problem(
        self,
        user_state: UserState,
        concept: str | None = None,
    ) -> GeneratedProblem:
        """Generate one problem adapted to user_state."""
        concept = self.concepts.normalize_concept(
            concept or user_state.primary_focus()
        )
        difficulty = user_state.difficulty

        # Prioritize weak concepts when picking
        if not concept or concept == "general":
            if user_state.weak_concepts:
                concept = user_state.weak_concepts[0]
            else:
                concept = user_state.current_concept or self.concepts.get_first_concept(
                    user_state.topic
                )

        templates = PROBLEM_TEMPLATES.get(concept, [])
        candidates = [t for t in templates if t["difficulty"] == difficulty]
        if not candidates:
            candidates = templates or PROBLEM_TEMPLATES["general"]

        template = random.choice(candidates) if candidates else PROBLEM_TEMPLATES["general"][0]

        excerpt = ""
        if self._retriever_loaded or self._retriever:
            try:
                retriever = self._get_retriever()
                hits = retriever.retrieve(
                    concepts=[concept],
                    top_k=1,
                )
                if hits:
                    excerpt = hits[0].text[:300]
            except FileNotFoundError:
                pass

        question = template["question"]
        if difficulty == "advanced" and excerpt:
            question += f"\n\n(Context: {excerpt[:200]}...)"

        return GeneratedProblem(
            problem_id=self._next_id(),
            concept=concept,
            question=question,
            expected_answer=template["answer"],
            difficulty=difficulty,
            hint=self._hint_for_concept(concept, difficulty),
            source_excerpt=excerpt,
            metadata={
                "weak_focus": concept in user_state.weak_concepts,
                "user_id": user_state.user_id,
            },
        )

    def generate_problem_set(
        self,
        user_state: UserState,
        count: int = 3,
    ) -> list[GeneratedProblem]:
        """
        Generate multiple problems, overweighting weak areas.

        If user is strong on current concept, include next concept once.
        """
        problems: list[GeneratedProblem] = []
        concepts_queue: list[str] = []

        if user_state.weak_concepts:
            concepts_queue.extend(user_state.weak_concepts[:2])
        if user_state.current_concept:
            concepts_queue.append(user_state.current_concept)
        if not concepts_queue:
            concepts_queue = self.concepts.get_concepts_for_topic(user_state.topic)[:3]

        concepts_queue = list(dict.fromkeys(concepts_queue))
        while len(problems) < count:
            concept = concepts_queue[len(problems) % len(concepts_queue)]
            problems.append(self.generate_problem(user_state, concept))
        return problems

    @staticmethod
    def _hint_for_concept(concept: str, difficulty: str) -> str:
        hints = {
            "eigenvalues": "Think: Av = λv. Solve det(A - λI) = 0.",
            "entropy": "Second law: isolated system entropy tends to increase.",
            "sorting": "Merge sort divides, sorts halves, merges.",
            "dynamic_programming": "Look for overlapping subproblems.",
        }
        base = hints.get(concept, "Review the lesson section for this topic.")
        if difficulty == "beginner":
            return f"Hint: {base}"
        return ""
