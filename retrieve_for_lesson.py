#!/usr/bin/env python3
"""Retrieve tagged chunks for lesson generation (CLI)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import KNOWLEDGE_INDEX_DIR  # noqa: E402
from pipeline.logging_setup import setup_logging  # noqa: E402
from pipeline.retrieval import ChunkRetriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve concept-tagged chunks for lesson generation.",
    )
    parser.add_argument(
        "--concepts",
        "-c",
        required=True,
        help="Comma-separated concepts (e.g. eigenvalues,entropy)",
    )
    parser.add_argument(
        "--query",
        "-q",
        default="",
        help="Optional free-text query to boost relevance",
    )
    parser.add_argument("--topic", help="Filter by domain folder: math, physics, cs")
    parser.add_argument("--subtopic", help="Filter by subtopic: linear_algebra, mechanics")
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=12,
        help="Maximum total chunks in lesson context",
    )
    parser.add_argument(
        "--per-concept",
        type=int,
        default=4,
        help="Max chunks per concept section",
    )
    parser.add_argument(
        "--mode",
        choices=["lesson", "search", "related"],
        default="lesson",
        help="lesson=grouped context; search=flat ranked list; related=from chunk id",
    )
    parser.add_argument(
        "--chunk-id",
        help="Chunk ID for related mode",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write JSON output to file",
    )
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Print LLM-ready prompt context to stdout",
    )
    return parser.parse_args()


def main() -> int:
    logger = setup_logging("retrieve_for_lesson")
    args = parse_args()
    concepts = [c.strip() for c in args.concepts.split(",") if c.strip()]

    retriever = ChunkRetriever()
    try:
        retriever.load()
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        logger.error("Run: python tag_chunks.py")
        return 1

    if args.mode == "related":
        if not args.chunk_id:
            logger.error("--chunk-id required for related mode")
            return 1
        results = retriever.retrieve_related(args.chunk_id, top_k=args.max_chunks)
        payload = {
            "mode": "related",
            "chunk_id": args.chunk_id,
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "score": c.score,
                    "concepts": c.concepts,
                    "source_file": c.source_file,
                    "text_preview": c.text[:400],
                }
                for c in results
            ],
        }
    elif args.mode == "search":
        results = retriever.retrieve(
            concepts=concepts,
            query=args.query,
            topic=args.topic,
            subtopic=args.subtopic,
            top_k=args.max_chunks,
        )
        payload = {
            "mode": "search",
            "query_concepts": concepts,
            "query": args.query,
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "score": c.score,
                    "concepts": c.concepts,
                    "source_file": c.source_file,
                    "text": c.text,
                }
                for c in results
            ],
        }
    else:
        lesson = retriever.retrieve_for_lesson(
            concepts=concepts,
            query=args.query,
            topic=args.topic,
            subtopic=args.subtopic,
            max_chunks=args.max_chunks,
            chunks_per_concept=args.per_concept,
        )
        payload = lesson.to_dict()
        if args.prompt:
            print(lesson.to_prompt_context())
            return 0

    out_path = args.output or (
        KNOWLEDGE_INDEX_DIR / f"lesson_{'_'.join(concepts[:2])}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    count = len(payload.get("all_chunk_ids", [])) or len(payload.get("chunks", []))
    logger.info("Retrieved %d chunk(s)", count)
    logger.info("Written to %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
