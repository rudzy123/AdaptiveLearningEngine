"""Extract major topics and learning units from analyzed corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from config import TOP_CONCEPTS_PER_DOMAIN, TOP_KEYWORDS_PER_MODULE
from pipeline.chunk_repository import SourceDocument
from pipeline.content_analyzer import CorpusAnalysis, DocumentAnalysis

DOMAIN_DISPLAY_NAMES = {
    "math": "Mathematics",
    "physics": "Physics",
    "cs": "Computer Science",
    "problems": "Practice & Assessment",
}

SUBTOPIC_DISPLAY_NAMES = {
    "linear_algebra": "Linear Algebra",
    "mechanics": "Classical Mechanics",
    "thermodynamics": "Thermodynamics",
    "algorithms": "Algorithms & Data Structures",
    "": "General",
}


@dataclass
class LearningUnit:
    """One teachable unit mapped to source material."""

    unit_id: str
    title: str
    domain: str
    subtopic: str
    source_files: list[str]
    chunk_ids: list[str]
    concepts: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    sequence_hint: int = 0
    chunk_count: int = 0
    word_count: int = 0
    institution: str = ""


@dataclass
class MajorTopic:
    """A cluster of related learning units within a domain."""

    topic_id: str
    name: str
    domain: str
    subtopic: str
    description: str
    concepts: list[str]
    units: list[LearningUnit] = field(default_factory=list)
    unit_count: int = 0
    total_chunks: int = 0


@dataclass
class TopicCatalog:
    """All major topics extracted from the corpus."""

    major_topics: list[MajorTopic] = field(default_factory=list)
    orphan_units: list[LearningUnit] = field(default_factory=list)


def _sequence_from_filename(source_file: str) -> int:
    """Parse lecture/chapter/problem numbers from filenames for ordering."""
    name = source_file.lower()
    patterns = [
        r"lecture0*(\d+)",
        r"chapter0*(\d+)",
        r"problem_set_(\d+)_(\d+)",
        r"problem_set_(\d+)",
        r"pset(\d+)",
        r"_(\d+)_",
    ]
    for pattern in patterns:
        match = re.search(pattern, name)
        if match:
            groups = [int(g) for g in match.groups()]
            # problem_set_1_2 → 102-style ordering
            if len(groups) == 2:
                return groups[0] * 100 + groups[1]
            return groups[0]
    return 9999


def _human_title(doc: SourceDocument, analysis: DocumentAnalysis | None) -> str:
    """Build a readable unit title from metadata and headings."""
    if analysis and analysis.heading_phrases:
        return analysis.heading_phrases[0]
    stem = doc.stem.replace("_", " ")
    # Prefer institution prefix stripped
    for prefix in ("mit ", "stanford "):
        if stem.lower().startswith(prefix):
            stem = stem[len(prefix) :]
    return stem.title()


# Known duplicate editions of the same material (stems without domain prefix)
DUPLICATE_STEM_GROUPS: list[frozenset[str]] = [
    frozenset(
        {
            "mit_18_06_linear_algebra_zoom_notes",
            "mit_18_06_spring2010_zoom_notes",
        }
    ),
]


def _stem_from_unit_id(unit_id: str) -> str:
    """Extract source stem from unit_id (format: domain__stem)."""
    return unit_id.split("__", 1)[-1] if "__" in unit_id else unit_id


def _merge_duplicate_units(units: list[LearningUnit]) -> list[LearningUnit]:
    """Merge only explicitly catalogued duplicate editions (same course, different year)."""
    stem_to_group: dict[str, int] = {}
    for idx, group in enumerate(DUPLICATE_STEM_GROUPS):
        for stem in group:
            stem_to_group[stem] = idx

    groups: dict[int, list[LearningUnit]] = {}
    standalone: list[LearningUnit] = []

    for unit in units:
        stem = _stem_from_unit_id(unit.unit_id)
        group_id = stem_to_group.get(stem)
        if group_id is None:
            standalone.append(unit)
        else:
            groups.setdefault(group_id, []).append(unit)

    merged: list[LearningUnit] = list(standalone)
    for group_units in groups.values():
        if len(group_units) == 1:
            merged.append(group_units[0])
            continue
        group_units.sort(key=lambda u: u.sequence_hint)
        primary = group_units[0]
        for other in group_units[1:]:
            primary.source_files.extend(other.source_files)
            primary.chunk_ids.extend(other.chunk_ids)
            primary.keywords = list(
                dict.fromkeys(primary.keywords + other.keywords)
            )[:TOP_KEYWORDS_PER_MODULE]
            primary.chunk_count += other.chunk_count
            primary.word_count += other.word_count
        primary.title = "Linear Algebra (MIT 18.06 Zoom Notes)"
        merged.append(primary)

    return merged


def _build_unit(
    doc: SourceDocument,
    analysis: DocumentAnalysis | None,
) -> LearningUnit:
    keywords = analysis.top_keywords if analysis else []
    concepts = list(
        dict.fromkeys(keywords + (analysis.heading_phrases[:3] if analysis else []))
    )[:TOP_KEYWORDS_PER_MODULE]

    return LearningUnit(
        unit_id=f"{doc.topic}__{doc.stem}",
        title=_human_title(doc, analysis),
        domain=doc.topic,
        subtopic=doc.subtopic or _infer_subtopic_from_stem(doc.stem),
        source_files=[doc.source_file],
        chunk_ids=[c.chunk_id for c in doc.chunks],
        concepts=concepts,
        keywords=keywords,
        sequence_hint=_sequence_from_filename(doc.source_file),
        chunk_count=len(doc.chunks),
        word_count=doc.total_words,
        institution=doc.institution,
    )


def _infer_subtopic_from_stem(stem: str) -> str:
    stem_l = stem.lower()
    if "thermodynamics" in stem_l or "5_60" in stem_l:
        return "thermodynamics"
    if "mechanics" in stem_l or "8_01" in stem_l:
        return "mechanics"
    if "linear_algebra" in stem_l or "18_06" in stem_l:
        return "linear_algebra"
    if "algorithm" in stem_l or "6_006" in stem_l or "cs161" in stem_l:
        return "algorithms"
    return ""


def extract_topics(
    documents: list[SourceDocument],
    corpus: CorpusAnalysis,
) -> TopicCatalog:
    """Cluster documents into major topics and learning units."""
    analysis_by_source = {d.source_file: d for d in corpus.documents}

    units: list[LearningUnit] = []
    for doc in documents:
        analysis = analysis_by_source.get(doc.source_file)
        units.append(_build_unit(doc, analysis))

    units = _merge_duplicate_units(units)

    # Group units into major topics by (domain, subtopic)
    clusters: dict[tuple[str, str], list[LearningUnit]] = {}
    for unit in units:
        clusters.setdefault((unit.domain, unit.subtopic), []).append(unit)

    major_topics: list[MajorTopic] = []
    for (domain, subtopic), cluster_units in sorted(clusters.items()):
        cluster_units.sort(key=lambda u: u.sequence_hint)
        domain_concepts = corpus.domain_keywords.get(domain, [])[:TOP_CONCEPTS_PER_DOMAIN]
        subtopic_name = SUBTOPIC_DISPLAY_NAMES.get(subtopic, subtopic.replace("_", " ").title())
        domain_name = DOMAIN_DISPLAY_NAMES.get(domain, domain.title())

        topic_id = f"{domain}_{subtopic or 'general'}"
        major_topics.append(
            MajorTopic(
                topic_id=topic_id,
                name=f"{domain_name}: {subtopic_name}",
                domain=domain,
                subtopic=subtopic,
                description=(
                    f"Covers {len(cluster_units)} unit(s) with "
                    f"{sum(u.chunk_count for u in cluster_units)} chunks "
                    f"from {domain_name.lower()} materials."
                ),
                concepts=domain_concepts,
                units=cluster_units,
                unit_count=len(cluster_units),
                total_chunks=sum(u.chunk_count for u in cluster_units),
            )
        )

    major_topics.sort(key=lambda t: (t.domain, t.subtopic))
    return TopicCatalog(major_topics=major_topics)
