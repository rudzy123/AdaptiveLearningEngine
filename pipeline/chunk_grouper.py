"""Group related chunks by shared concepts and within-document continuity."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from config import CHUNK_GROUP_MIN_JACCARD, CHUNK_GROUP_MIN_SHARED_CONCEPTS
from pipeline.concept_tagger import TaggedChunk


@dataclass
class ChunkGroup:
    """A cluster of related chunks for lesson planning or retrieval."""

    group_id: str
    name: str
    primary_concept: str
    topic: str
    subtopic: str
    chunk_ids: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    group_type: str = "concept"  # concept | sequence | similarity


def _concept_set(tagged: TaggedChunk) -> set[str]:
    return {t.concept for t in tagged.concepts}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union)


def _build_concept_groups(tagged_chunks: list[TaggedChunk]) -> list[ChunkGroup]:
    """One group per concept that appears in 2+ chunks (same topic)."""
    concept_to_chunks: dict[tuple[str, str], list[TaggedChunk]] = defaultdict(list)

    for tagged in tagged_chunks:
        for tag in tagged.concepts:
            key = (tagged.chunk.topic, tag.concept)
            concept_to_chunks[key].append(tagged)

    groups: list[ChunkGroup] = []
    for (topic, concept), members in concept_to_chunks.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda t: (t.chunk.source_file, t.chunk.chunk_index))
        subtopic = members[0].chunk.subtopic
        groups.append(
            ChunkGroup(
                group_id=str(uuid.uuid4()),
                name=f"{concept.replace('_', ' ').title()} ({len(members)} chunks)",
                primary_concept=concept,
                topic=topic,
                subtopic=subtopic,
                chunk_ids=[m.chunk.chunk_id for m in members],
                concepts=[concept],
                source_files=list(dict.fromkeys(m.chunk.source_file for m in members)),
                group_type="concept",
            )
        )
    return groups


def _build_sequence_groups(tagged_chunks: list[TaggedChunk]) -> list[ChunkGroup]:
    """Group consecutive chunks within the same PDF that share at least one concept."""
    by_source: dict[str, list[TaggedChunk]] = defaultdict(list)
    for tagged in tagged_chunks:
        by_source[tagged.chunk.source_file].append(tagged)

    groups: list[ChunkGroup] = []
    for source_file, members in by_source.items():
        members.sort(key=lambda t: t.chunk.chunk_index)
        if len(members) < 2:
            continue

        run: list[TaggedChunk] = [members[0]]
        for tagged in members[1:]:
            prev_concepts = _concept_set(run[-1])
            curr_concepts = _concept_set(tagged)
            if prev_concepts & curr_concepts or not prev_concepts or not curr_concepts:
                run.append(tagged)
            else:
                if len(run) >= 2:
                    groups.append(_sequence_group_from_run(run, source_file))
                run = [tagged]
        if len(run) >= 2:
            groups.append(_sequence_group_from_run(run, source_file))

    return groups


def _sequence_group_from_run(run: list[TaggedChunk], source_file: str) -> ChunkGroup:
    concept_counts: dict[str, int] = defaultdict(int)
    for member in run:
        for tag in member.concepts:
            concept_counts[tag.concept] += 1
    primary = max(concept_counts, key=concept_counts.get) if concept_counts else "sequence"
    first = run[0].chunk
    stem = source_file.split("/")[-1].replace(".pdf", "").replace("_", " ")
    return ChunkGroup(
        group_id=str(uuid.uuid4()),
        name=f"Sequence: {stem} ({len(run)} chunks)",
        primary_concept=primary,
        topic=first.topic,
        subtopic=first.subtopic,
        chunk_ids=[m.chunk.chunk_id for m in run],
        concepts=list(concept_counts.keys())[:5],
        source_files=[source_file],
        group_type="sequence",
    )


def _build_similarity_groups(
    tagged_chunks: list[TaggedChunk],
    existing_chunk_ids: set[str],
) -> list[ChunkGroup]:
    """Pairwise clusters for high concept overlap within the same subtopic."""
    groups: list[ChunkGroup] = []
    used_pairs: set[tuple[str, str]] = set()

    by_subtopic: dict[tuple[str, str], list[TaggedChunk]] = defaultdict(list)
    for tagged in tagged_chunks:
        if tagged.concepts:
            by_subtopic[(tagged.chunk.topic, tagged.chunk.subtopic)].append(tagged)

    for (_topic, _subtopic), members in by_subtopic.items():
        for i, a in enumerate(members):
            set_a = _concept_set(a)
            if not set_a:
                continue
            cluster = [a]
            for b in members[i + 1 :]:
                set_b = _concept_set(b)
                shared = len(set_a & set_b)
                if shared >= CHUNK_GROUP_MIN_SHARED_CONCEPTS or _jaccard(set_a, set_b) >= CHUNK_GROUP_MIN_JACCARD:
                    pair = tuple(sorted((a.chunk.chunk_id, b.chunk.chunk_id)))
                    if pair in used_pairs:
                        continue
                    used_pairs.add(pair)
                    if b not in cluster:
                        cluster.append(b)

            if len(cluster) >= 2:
                ids = {m.chunk.chunk_id for m in cluster}
                if ids & existing_chunk_ids and len(ids) <= 2:
                    continue
                concept_counts: dict[str, int] = defaultdict(int)
                for member in cluster:
                    for tag in member.concepts:
                        concept_counts[tag.concept] += 1
                ranked = sorted(concept_counts.items(), key=lambda x: -x[1])
                primary = ranked[0][0]
                first = cluster[0].chunk
                groups.append(
                    ChunkGroup(
                        group_id=str(uuid.uuid4()),
                        name=f"Related: {primary.replace('_', ' ')} ({len(cluster)} chunks)",
                        primary_concept=primary,
                        topic=first.topic,
                        subtopic=first.subtopic,
                        chunk_ids=[m.chunk.chunk_id for m in cluster],
                        concepts=[c for c, _ in ranked[:4]],
                        source_files=list(
                            dict.fromkeys(m.chunk.source_file for m in cluster)
                        ),
                        group_type="similarity",
                    )
                )
                existing_chunk_ids.update(ids)

    return groups


def build_chunk_groups(tagged_chunks: list[TaggedChunk]) -> list[ChunkGroup]:
    """Build concept, sequence, and similarity chunk groups."""
    if not tagged_chunks:
        return []

    concept_groups = _build_concept_groups(tagged_chunks)
    sequence_groups = _build_sequence_groups(tagged_chunks)

    existing_ids: set[str] = set()
    for group in concept_groups + sequence_groups:
        existing_ids.update(group.chunk_ids)

    similarity_groups = _build_similarity_groups(tagged_chunks, existing_ids)

    all_groups = concept_groups + sequence_groups + similarity_groups
    all_groups.sort(
        key=lambda g: (g.topic, g.primary_concept, g.group_type, -len(g.chunk_ids))
    )
    return all_groups
