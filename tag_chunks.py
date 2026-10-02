#!/usr/bin/env python3
"""Tag chunks with concepts, group related chunks, and index for retrieval."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import CONCEPT_GROUPS_JSON, SQLITE_DB_PATH  # noqa: E402
from pipeline.chunk_grouper import build_chunk_groups  # noqa: E402
from pipeline.chunk_repository import load_all_chunks  # noqa: E402
from pipeline.concept_tagger import tag_chunks  # noqa: E402
from pipeline.knowledge_index import (  # noqa: E402
    clear_knowledge_tables,
    ensure_schema,
    export_groups_json,
    save_groups,
    save_tags,
)
from pipeline.logging_setup import setup_logging  # noqa: E402
import sqlite3  # noqa: E402


def main() -> int:
    logger = setup_logging("tag_chunks")
    logger.info("Starting concept tagging and chunk grouping")

    chunks = load_all_chunks()
    if not chunks:
        logger.error("No chunks found. Run ingest_pdfs.py first.")
        return 1

    if not SQLITE_DB_PATH.exists():
        logger.error("SQLite database missing at %s", SQLITE_DB_PATH)
        return 1

    tagged = tag_chunks(chunks)
    groups = build_chunk_groups(tagged)

    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        ensure_schema(conn)
        clear_knowledge_tables(conn)
        tag_count = save_tags(conn, tagged)
        save_groups(conn, groups)

    groups_path = export_groups_json(groups)
    unique_concepts = len({t.concept for tc in tagged for t in tc.concepts})

    logger.info("--- Tagging summary ---")
    logger.info("Chunks tagged:       %d", len(tagged))
    logger.info("Concept tags written: %d", tag_count)
    logger.info("Unique concepts:     %d", unique_concepts)
    logger.info("Chunk groups created: %d", len(groups))
    logger.info("Groups export:       %s", groups_path)
    logger.info("Index tables in:     %s", SQLITE_DB_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
