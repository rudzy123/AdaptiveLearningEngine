"""Build an ordered learning path with prerequisites from extracted topics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import DOMAIN_SEQUENCE, SUBTOPIC_SEQUENCE
from pipeline.topic_extractor import LearningUnit, MajorTopic, TopicCatalog

# Pedagogical prerequisites between major topics (topic_id → required topic_ids)
TOPIC_PREREQUISITES: dict[str, list[str]] = {
    "physics_mechanics": ["math_linear_algebra"],
    "physics_thermodynamics": ["physics_mechanics"],
    "cs_algorithms": ["math_linear_algebra"],
    "problems_general": ["math_linear_algebra", "cs_algorithms"],
}

# Fine-grained unit ordering overrides (unit_id suffix patterns → must come after)
UNIT_ORDER_OVERRIDES: list[tuple[str, str]] = [
    ("chapter07", "chapter01"),
    ("chapter10", "chapter07"),
    ("chapter13", "chapter10"),
    ("thermodynamics_lecture07", "thermodynamics_lecture01"),
    ("thermodynamics_lecture15", "thermodynamics_lecture07"),
    ("thermodynamics_lecture19", "thermodynamics_lecture15"),
    ("algorithms_lecture02", "algorithms_lecture01"),
    ("algorithms_lecture03", "algorithms_lecture02"),
    ("algorithms_lecture04", "algorithms_lecture03"),
    ("algorithms_lecture06", "algorithms_lecture04"),
    ("algorithms_lecture07", "algorithms_lecture06"),
    ("problem_set_1_2", "problem_set_1_1"),
    ("problem_set_1_3", "problem_set_1_2"),
    ("problem_set_2", "problem_set_1"),
]


@dataclass
class PathStep:
    """One step in the global learning path."""

    step: int
    unit_id: str
    title: str
    domain: str
    subtopic: str
    major_topic_id: str
    major_topic_name: str
    prerequisites: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    estimated_chunks: int = 0


@dataclass
class LearningPath:
    """Complete ordered curriculum path."""

    generated_at: str
    version: str
    summary: dict
    major_topics: list[dict]
    steps: list[PathStep] = field(default_factory=list)


def _domain_sort_key(topic: MajorTopic) -> tuple[int, int, str]:
    domain_rank = DOMAIN_SEQUENCE.index(topic.domain) if topic.domain in DOMAIN_SEQUENCE else 99
    sub_seq = SUBTOPIC_SEQUENCE.get(topic.domain, [])
    sub_rank = sub_seq.index(topic.subtopic) if topic.subtopic in sub_seq else 0
    return (domain_rank, sub_rank, topic.topic_id)


def _unit_sort_key(unit: LearningUnit) -> tuple[int, int, str]:
    domain_rank = DOMAIN_SEQUENCE.index(unit.domain) if unit.domain in DOMAIN_SEQUENCE else 99
    sub_seq = SUBTOPIC_SEQUENCE.get(unit.domain, [])
    sub_rank = sub_seq.index(unit.subtopic) if unit.subtopic in sub_seq else 0
    return (domain_rank, sub_rank, unit.sequence_hint, unit.unit_id)


def _prerequisites_for_unit(unit: LearningUnit, prior_units: list[LearningUnit]) -> list[str]:
    """Determine prerequisite unit IDs based on rules and ordering."""
    prereqs: list[str] = []
    unit_key = unit.unit_id.lower()

    for after, before in UNIT_ORDER_OVERRIDES:
        if after in unit_key:
            for prior in prior_units:
                if before in prior.unit_id.lower():
                    prereqs.append(prior.unit_id)

    # Same-domain prior unit in sequence
    same_domain = [
        u for u in prior_units
        if u.domain == unit.domain and u.subtopic == unit.subtopic
    ]
    if same_domain and not prereqs:
        prereqs.append(same_domain[-1].unit_id)

    # Cross-domain: first unit in a topic may require last unit of prereq topics
    if unit.domain == "physics" and unit.subtopic == "mechanics":
        math_units = [u for u in prior_units if u.domain == "math"]
        if math_units and not prereqs:
            prereqs.append(math_units[-1].unit_id)

    if unit.domain == "physics" and unit.subtopic == "thermodynamics":
        mech_units = [
            u for u in prior_units
            if u.domain == "physics" and u.subtopic == "mechanics"
        ]
        if mech_units and not prereqs:
            prereqs.append(mech_units[-1].unit_id)

    if unit.domain == "cs":
        math_units = [u for u in prior_units if u.domain == "math"]
        if math_units and not prereqs:
            prereqs.append(math_units[-1].unit_id)

    if unit.domain == "problems":
        if "18_06" in unit_key or "linear" in unit_key:
            math_units = [u for u in prior_units if u.domain == "math"]
            if math_units:
                prereqs.append(math_units[-1].unit_id)
        if "6_006" in unit_key or "algorithm" in unit_key:
            cs_units = [u for u in prior_units if u.domain == "cs"]
            if cs_units:
                prereqs.append(cs_units[-1].unit_id)

    return list(dict.fromkeys(prereqs))


def build_learning_path(catalog: TopicCatalog) -> LearningPath:
    """Produce a globally ordered learning path from the topic catalog."""
    sorted_topics = sorted(catalog.major_topics, key=_domain_sort_key)

    all_units: list[LearningUnit] = []
    for topic in sorted_topics:
        topic.units.sort(key=_unit_sort_key)
        all_units.extend(topic.units)

    # Stable global order
    all_units.sort(key=_unit_sort_key)

    steps: list[PathStep] = []
    prior: list[LearningUnit] = []
    topic_by_id = {t.topic_id: t for t in catalog.major_topics}

    for idx, unit in enumerate(all_units, start=1):
        major = next(
            (t for t in catalog.major_topics if unit in t.units),
            None,
        )
        prereqs = _prerequisites_for_unit(unit, prior)

        steps.append(
            PathStep(
                step=idx,
                unit_id=unit.unit_id,
                title=unit.title,
                domain=unit.domain,
                subtopic=unit.subtopic,
                major_topic_id=major.topic_id if major else "",
                major_topic_name=major.name if major else "",
                prerequisites=prereqs,
                source_files=unit.source_files,
                chunk_ids=unit.chunk_ids,
                concepts=unit.concepts,
                estimated_chunks=unit.chunk_count,
            )
        )
        prior.append(unit)

    summary = {
        "total_steps": len(steps),
        "major_topic_count": len(catalog.major_topics),
        "domains": list(dict.fromkeys(s.domain for s in steps)),
        "total_chunks": sum(s.estimated_chunks for s in steps),
    }

    major_topics_payload = []
    for topic in sorted_topics:
        major_topics_payload.append(
            {
                "topic_id": topic.topic_id,
                "name": topic.name,
                "domain": topic.domain,
                "subtopic": topic.subtopic,
                "description": topic.description,
                "concepts": topic.concepts,
                "unit_count": topic.unit_count,
                "total_chunks": topic.total_chunks,
                "prerequisites": TOPIC_PREREQUISITES.get(topic.topic_id, []),
                "units": [
                    {
                        "unit_id": u.unit_id,
                        "title": u.title,
                        "source_files": u.source_files,
                        "keywords": u.keywords,
                        "chunk_count": u.chunk_count,
                        "sequence_hint": u.sequence_hint,
                    }
                    for u in topic.units
                ],
            }
        )

    return LearningPath(
        generated_at=datetime.now(timezone.utc).isoformat(),
        version="1.0",
        summary=summary,
        major_topics=major_topics_payload,
        steps=steps,
    )


def learning_path_to_dict(path: LearningPath) -> dict:
    """Serialize learning path for JSON export."""
    return {
        "generated_at": path.generated_at,
        "version": path.version,
        "summary": path.summary,
        "major_topics": path.major_topics,
        "learning_path": [
            {
                "step": s.step,
                "unit_id": s.unit_id,
                "title": s.title,
                "domain": s.domain,
                "subtopic": s.subtopic,
                "major_topic_id": s.major_topic_id,
                "major_topic_name": s.major_topic_name,
                "prerequisites": s.prerequisites,
                "source_files": s.source_files,
                "chunk_count": s.estimated_chunks,
                "concepts": s.concepts,
            }
            for s in path.steps
        ],
    }
