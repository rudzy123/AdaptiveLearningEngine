#!/usr/bin/env python3
"""Download open educational PDFs into the learning_engine_data folders."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DATA_ROOT, SOURCE_DIRS  # noqa: E402
from pipeline.downloader import MaterialDownloader  # noqa: E402
from pipeline.logging_setup import setup_logging  # noqa: E402


def ensure_directories() -> None:
    """Create data directory tree if missing."""
    for path in [DATA_ROOT, *SOURCE_DIRS.values()]:
        path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    logger = setup_logging("download_materials")
    ensure_directories()
    logger.info("Starting educational material download")
    logger.info("Data root: %s", DATA_ROOT)

    downloader = MaterialDownloader()
    stats = downloader.run()

    logger.info("--- Download summary ---")
    logger.info("Attempted:          %d", stats["attempted"])
    logger.info("Downloaded:         %d", stats["downloaded"])
    logger.info("Skipped (duplicate): %d", stats["skipped_duplicate"])
    logger.info("Failed:             %d", stats["failed"])

    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
