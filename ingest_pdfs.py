#!/usr/bin/env python3
"""Ingest PDFs: extract text, chunk, and store with metadata."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import JSON_OUTPUT_DIR, PROCESSED_DIR, SQLITE_DB_PATH  # noqa: E402
from pipeline.ingestion import PdfIngestionPipeline  # noqa: E402
from pipeline.logging_setup import setup_logging  # noqa: E402


def main() -> int:
    logger = setup_logging("ingest_pdfs")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Starting PDF ingestion pipeline")
    pipeline = PdfIngestionPipeline()
    stats = pipeline.run()

    logger.info("--- Ingestion summary ---")
    logger.info("Documents processed: %d", stats.documents_processed)
    logger.info("Documents failed:    %d", stats.documents_failed)
    logger.info("Chunks created:      %d", stats.chunks_created)
    if stats.errors:
        logger.info("Errors encountered:  %d", len(stats.errors))
        for err in stats.errors:
            logger.error("  • %s", err)

    if SQLITE_DB_PATH.exists():
        logger.info("SQLite database: %s", SQLITE_DB_PATH)
    logger.info("JSON chunks dir:   %s", JSON_OUTPUT_DIR)

    return 1 if stats.documents_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
