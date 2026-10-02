"""Curriculum engine: analyze ingested content and build a learning path."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from config import CURRICULUM_JSON_PATH, CURRICULUM_OUTPUT_DIR, TOP_KEYWORDS_PER_MODULE
from pipeline.chunk_repository import group_by_source, load_all_chunks
from pipeline.content_analyzer import analyze_corpus
from pipeline.learning_path import build_learning_path, learning_path_to_dict
from pipeline.topic_extractor import extract_topics

logger = logging.getLogger(__name__)


@dataclass
class CurriculumResult:
    """Output of a full curriculum build run."""

    documents_analyzed: int = 0
    chunks_analyzed: int = 0
    major_topics_found: int = 0
    path_steps: int = 0
    output_path: str = ""
    errors: list[str] = field(default_factory=list)


class CurriculumEngine:
    """Orchestrates content analysis, topic extraction, and path building."""

    def __init__(self, output_path: str | None = None) -> None:
        self.output_path = output_path or str(CURRICULUM_JSON_PATH)

    def run(self) -> CurriculumResult:
        """Execute the full curriculum pipeline."""
        result = CurriculumResult()

        try:
            chunks = load_all_chunks()
            if not chunks:
                raise FileNotFoundError(
                    "No ingested chunks found. Run ingest_pdfs.py first."
                )

            documents = group_by_source(chunks)
            result.documents_analyzed = len(documents)
            result.chunks_analyzed = len(chunks)

            logger.info(
                "Analyzing %d documents (%d chunks)",
                result.documents_analyzed,
                result.chunks_analyzed,
            )
            corpus = analyze_corpus(documents, keywords_per_doc=TOP_KEYWORDS_PER_MODULE)

            logger.info("Extracting major topics and learning units")
            catalog = extract_topics(documents, corpus)

            result.major_topics_found = len(catalog.major_topics)
            for topic in catalog.major_topics:
                logger.info(
                    "  Topic: %s (%d units, %d chunks)",
                    topic.name,
                    topic.unit_count,
                    topic.total_chunks,
                )

            logger.info("Building ordered learning path")
            path = build_learning_path(catalog)
            result.path_steps = len(path.steps)

            payload = learning_path_to_dict(path)
            payload["analysis"] = {
                "corpus": {
                    "document_count": corpus.document_count,
                    "chunk_count": corpus.chunk_count,
                    "total_words": corpus.total_words,
                    "domain_keywords": corpus.domain_keywords,
                },
            }

            self._write_output(payload)
            result.output_path = self.output_path

            logger.info(
                "Curriculum written: %d steps across %d major topics → %s",
                result.path_steps,
                result.major_topics_found,
                self.output_path,
            )

        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            result.errors.append(message)
            logger.error("Curriculum build failed: %s", message)

        return result

    def _write_output(self, payload: dict) -> None:
        CURRICULUM_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
