"""Persist ingested chunks to JSON files and/or SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path

from config import JSON_OUTPUT_DIR, OUTPUT_FORMAT, SQLITE_DB_PATH
from pipeline.chunker import TextChunk

logger = logging.getLogger(__name__)


class ChunkStorage:
    """Write chunks to JSON and SQLite backends."""

    def __init__(self) -> None:
        self.json_dir = JSON_OUTPUT_DIR
        self.db_path = SQLITE_DB_PATH

    def save_document_chunks(
        self, source_stem: str, chunks: list[TextChunk]
    ) -> None:
        """Persist all chunks for one source document."""
        if not chunks:
            return

        if OUTPUT_FORMAT in ("json", "both"):
            self._save_json(source_stem, chunks)
        if OUTPUT_FORMAT in ("sqlite", "both"):
            self._save_sqlite(chunks)

    def _save_json(self, source_stem: str, chunks: list[TextChunk]) -> None:
        self.json_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.json_dir / f"{source_stem}_chunks.json"
        payload = {
            "source": chunks[0].source_file,
            "topic": chunks[0].topic,
            "chunk_count": len(chunks),
            "chunks": [asdict(c) for c in chunks],
        }
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        logger.debug("Wrote JSON: %s", out_path)

    def _save_sqlite(self, chunks: list[TextChunk]) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    subtopic TEXT,
                    institution TEXT,
                    title TEXT,
                    chunk_index INTEGER NOT NULL,
                    word_count INTEGER NOT NULL,
                    text TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_topic ON chunks(topic)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_file)"
            )
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chunks
                    (chunk_id, source_file, topic, subtopic, institution,
                     title, chunk_index, word_count, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.source_file,
                        chunk.topic,
                        chunk.subtopic,
                        chunk.institution,
                        chunk.title,
                        chunk.chunk_index,
                        chunk.word_count,
                        chunk.text,
                    ),
                )
            conn.commit()
