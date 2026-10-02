"""Persist concept tags and chunk groups to SQLite for retrieval."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from config import CONCEPT_GROUPS_JSON, KNOWLEDGE_INDEX_DIR, SQLITE_DB_PATH
from pipeline.chunk_grouper import ChunkGroup
from pipeline.concept_tagger import ConceptTag, TaggedChunk
from pipeline.chunk_repository import ChunkRecord, load_all_chunks

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chunk_concepts (
    chunk_id TEXT NOT NULL,
    concept TEXT NOT NULL,
    score REAL NOT NULL,
    match_type TEXT NOT NULL,
    PRIMARY KEY (chunk_id, concept),
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_chunk_concepts_concept
    ON chunk_concepts(concept);

CREATE TABLE IF NOT EXISTS chunk_groups (
    group_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    primary_concept TEXT NOT NULL,
    topic TEXT NOT NULL,
    subtopic TEXT,
    group_type TEXT NOT NULL DEFAULT 'concept',
    concepts_json TEXT NOT NULL,
    source_files_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunk_group_members (
    group_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, chunk_id),
    FOREIGN KEY (group_id) REFERENCES chunk_groups(group_id),
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_group_members_chunk
    ON chunk_group_members(chunk_id);
"""


@dataclass
class IndexingStats:
    """Statistics from a knowledge indexing run."""

    chunks_tagged: int = 0
    concept_tags_written: int = 0
    groups_created: int = 0
    unique_concepts: int = 0
    errors: list[str] = field(default_factory=list)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(chunk_groups)").fetchall()
    }
    if columns and "group_type" not in columns:
        conn.execute(
            "ALTER TABLE chunk_groups ADD COLUMN group_type TEXT NOT NULL DEFAULT 'concept'"
        )
    conn.commit()


def clear_knowledge_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM chunk_group_members")
    conn.execute("DELETE FROM chunk_groups")
    conn.execute("DELETE FROM chunk_concepts")
    conn.commit()


def save_tags(conn: sqlite3.Connection, tagged_chunks: list[TaggedChunk]) -> int:
    """Write concept tags; returns number of tag rows."""
    count = 0
    for tagged in tagged_chunks:
        for tag in tagged.concepts:
            conn.execute(
                """
                INSERT OR REPLACE INTO chunk_concepts
                (chunk_id, concept, score, match_type)
                VALUES (?, ?, ?, ?)
                """,
                (tagged.chunk.chunk_id, tag.concept, tag.score, tag.match_type),
            )
            count += 1
    conn.commit()
    return count


def save_groups(conn: sqlite3.Connection, groups: list[ChunkGroup]) -> None:
    for group in groups:
        conn.execute(
            """
            INSERT OR REPLACE INTO chunk_groups
            (group_id, name, primary_concept, topic, subtopic, group_type,
             concepts_json, source_files_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group.group_id,
                group.name,
                group.primary_concept,
                group.topic,
                group.subtopic,
                group.group_type,
                json.dumps(group.concepts),
                json.dumps(group.source_files),
            ),
        )
        for position, chunk_id in enumerate(group.chunk_ids):
            conn.execute(
                """
                INSERT OR REPLACE INTO chunk_group_members
                (group_id, chunk_id, position)
                VALUES (?, ?, ?)
                """,
                (group.group_id, chunk_id, position),
            )
    conn.commit()


def export_groups_json(groups: list[ChunkGroup], path: Path | None = None) -> Path:
    out = path or CONCEPT_GROUPS_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "group_count": len(groups),
        "groups": [
            {
                "group_id": g.group_id,
                "name": g.name,
                "primary_concept": g.primary_concept,
                "topic": g.topic,
                "subtopic": g.subtopic,
                "concepts": g.concepts,
                "chunk_ids": g.chunk_ids,
                "source_files": g.source_files,
                "group_type": g.group_type,
            }
            for g in groups
        ],
    }
    with out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return out


@dataclass
class ChunkWithConcepts:
    """Chunk row enriched with concept tags."""

    chunk_id: str
    source_file: str
    topic: str
    subtopic: str
    institution: str
    title: str
    chunk_index: int
    word_count: int
    text: str
    concepts: list[ConceptTag] = field(default_factory=list)
    group_ids: list[str] = field(default_factory=list)


def load_tagged_chunks(db_path: Path | None = None) -> list[ChunkWithConcepts]:
    """Load all chunks with their concept tags and group memberships."""
    path = db_path or SQLITE_DB_PATH
    if not path.exists():
        return []

    results: list[ChunkWithConcepts] = []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT c.chunk_id, c.source_file, c.topic, c.subtopic,
                   c.institution, c.title, c.chunk_index, c.word_count, c.text
            FROM chunks c
            ORDER BY c.source_file, c.chunk_index
            """
        ).fetchall()

        for row in rows:
            tags = conn.execute(
                """
                SELECT concept, score, match_type
                FROM chunk_concepts
                WHERE chunk_id = ?
                ORDER BY score DESC
                """,
                (row["chunk_id"],),
            ).fetchall()
            groups = conn.execute(
                """
                SELECT group_id FROM chunk_group_members
                WHERE chunk_id = ?
                """,
                (row["chunk_id"],),
            ).fetchall()

            results.append(
                ChunkWithConcepts(
                    chunk_id=row["chunk_id"],
                    source_file=row["source_file"],
                    topic=row["topic"] or "",
                    subtopic=row["subtopic"] or "",
                    institution=row["institution"] or "",
                    title=row["title"] or "",
                    chunk_index=row["chunk_index"],
                    word_count=row["word_count"],
                    text=row["text"] or "",
                    concepts=[
                        ConceptTag(
                            concept=t["concept"],
                            score=t["score"],
                            match_type=t["match_type"],
                        )
                        for t in tags
                    ],
                    group_ids=[g["group_id"] for g in groups],
                )
            )
    return results


def load_concept_index(db_path: Path | None = None) -> dict[str, list[str]]:
    """Inverted index: concept → chunk_ids."""
    path = db_path or SQLITE_DB_PATH
    index: dict[str, list[str]] = {}
    if not path.exists():
        return index

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT concept, chunk_id, score
            FROM chunk_concepts
            ORDER BY concept, score DESC
            """
        ).fetchall()
        for row in rows:
            index.setdefault(row["concept"], []).append(row["chunk_id"])
    return index
