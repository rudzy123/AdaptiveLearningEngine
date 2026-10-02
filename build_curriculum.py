#!/usr/bin/env python3
"""Analyze ingested content and build a structured learning curriculum."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.curriculum_engine import CurriculumEngine  # noqa: E402
from pipeline.logging_setup import setup_logging  # noqa: E402


def main() -> int:
    logger = setup_logging("build_curriculum")
    logger.info("Starting curriculum engine")

    engine = CurriculumEngine()
    result = engine.run()

    logger.info("--- Curriculum summary ---")
    logger.info("Documents analyzed:  %d", result.documents_analyzed)
    logger.info("Chunks analyzed:     %d", result.chunks_analyzed)
    logger.info("Major topics found:  %d", result.major_topics_found)
    logger.info("Learning path steps: %d", result.path_steps)

    if result.output_path:
        logger.info("Output: %s", result.output_path)
    if result.errors:
        for err in result.errors:
            logger.error("  • %s", err)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
