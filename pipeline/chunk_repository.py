"""Load ingested chunks from SQLite or JSON fallbacks."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from config import JSON_OUTPUT_DIR, SQLITE_DB_PATH


@dataclass
class ChunkRecord:
    """A single ingested text chunk with metadata."""

    chunk_id: str
    source_file: str
    topic: str
    subtopic: str
    institution: str
    title: str
    chunk_index: int
    word_count: int
    text: str


@dataclass
class SourceDocument:
    """All chunks belonging to one PDF source."""

    source_file: str
    topic: str
    subtopic: str
    institution: str
    title: str
    chunks: list[ChunkRecord]

    @property
    def stem(self) -> str:
        return Path(self.source_file).stem

    @property
    def total_words(self) -> int:
        return sum(c.word_count for c in self.chunks)


def load_chunks_from_sqlite(db_path: Path | None = None) -> list[ChunkRecord]:
    """Load all chunks from the ingestion SQLite database."""
    path = db_path or SQLITE_DB_PATH
    if not path.exists():
        return []

    records: list[ChunkRecord] = []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT chunk_id, source_file, topic, subtopic, institution,
                   title, chunk_index, word_count, text
            FROM chunks
            ORDER BY source_file, chunk_index
            """
        ).fetchall()
        for row in rows:
            records.append(
                ChunkRecord(
                    chunk_id=row["chunk_id"],
                    source_file=row["source_file"],
                    topic=row["topic"] or "",
                    subtopic=row["subtopic"] or "",
                    institution=row["institution"] or "",
                    title=row["title"] or "",
                    chunk_index=row["chunk_index"],
                    word_count=row["word_count"],
                    text=row["text"] or "",
                )
            )
    return records


def load_chunks_from_json(json_dir: Path | None = None) -> list[ChunkRecord]:
    """Load chunks from per-document JSON files (fallback)."""
    directory = json_dir or JSON_OUTPUT_DIR
    if not directory.exists():
        return []

    records: list[ChunkRecord] = []
    for json_path in sorted(directory.glob("*_chunks.json")):
        with json_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload.get("chunks", []):
            records.append(ChunkRecord(**item))
    return records


def load_all_chunks() -> list[ChunkRecord]:
    """Prefer SQLite; fall back to JSON chunk files."""
    chunks = load_chunks_from_sqlite()
    if chunks:
        return chunks
    return load_chunks_from_json()


def group_by_source(chunks: list[ChunkRecord]) -> list[SourceDocument]:
    """Group chunk records into source documents."""
    by_source: dict[str, list[ChunkRecord]] = {}
    for chunk in chunks:
        by_source.setdefault(chunk.source_file, []).append(chunk)

    documents: list[SourceDocument] = []
    for source_file, doc_chunks in sorted(by_source.items()):
        doc_chunks.sort(key=lambda c: c.chunk_index)
        first = doc_chunks[0]
        documents.append(
            SourceDocument(
                source_file=source_file,
                topic=first.topic,
                subtopic=first.subtopic,
                institution=first.institution,
                title=first.title,
                chunks=doc_chunks,
            )
        )
    return documents
