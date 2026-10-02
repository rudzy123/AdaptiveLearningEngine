"""PDF ingestion orchestration: discover, extract, chunk, store."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from config import DATA_ROOT, SOURCE_DIRS
from pipeline.chunker import split_into_chunks
from pipeline.pdf_extractor import extract_text_from_pdf
from pipeline.storage import ChunkStorage

logger = logging.getLogger(__name__)

# Map folder names to default subtopics when not inferable from filename
SUBTOPIC_HINTS: dict[str, list[tuple[str, str]]] = {
    "physics": [
        ("thermodynamics", "thermodynamics"),
        ("mechanics", "mechanics"),
        ("chapter", "mechanics"),
    ],
    "math": [("linear_algebra", "linear_algebra"), ("algebra", "linear_algebra")],
    "cs": [("algorithms", "algorithms"), ("cs161", "algorithms")],
    "problems": [],
}


@dataclass
class IngestionStats:
    """Summary statistics for an ingestion run."""

    documents_processed: int = 0
    documents_failed: int = 0
    chunks_created: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def infer_topic(pdf_path: Path) -> str:
    """Derive topic label from parent folder name."""
    for topic, directory in SOURCE_DIRS.items():
        try:
            pdf_path.relative_to(directory)
            return topic
        except ValueError:
            continue
    # Fallback: first parent under data root
    rel = pdf_path.relative_to(DATA_ROOT)
    return rel.parts[0] if rel.parts else "unknown"


def infer_subtopic(pdf_path: Path, topic: str) -> str:
    """Guess subtopic from filename keywords."""
    name = pdf_path.stem.lower()
    for keyword, subtopic in SUBTOPIC_HINTS.get(topic, []):
        if keyword in name:
            return subtopic
    return ""


def discover_pdfs() -> list[Path]:
    """Find all PDF files under source topic directories."""
    pdfs: list[Path] = []
    for directory in SOURCE_DIRS.values():
        if directory.exists():
            pdfs.extend(sorted(directory.rglob("*.pdf")))
    return pdfs


class PdfIngestionPipeline:
    """End-to-end ingestion from PDFs to chunked storage."""

    def __init__(self) -> None:
        self.storage = ChunkStorage()
        self.stats = IngestionStats()

    def run(self) -> IngestionStats:
        """Process all discovered PDFs."""
        pdf_files = discover_pdfs()
        if not pdf_files:
            logger.warning(
                "No PDFs found under %s. Run download_materials.py first.",
                DATA_ROOT,
            )
            return self.stats

        for pdf_path in pdf_files:
            try:
                self._process_pdf(pdf_path)
                self.stats.documents_processed += 1
            except Exception as exc:  # noqa: BLE001
                self.stats.documents_failed += 1
                message = f"{pdf_path.name}: {exc}"
                self.stats.errors.append(message)
                logger.error("Ingestion error: %s", message)

        return self.stats

    def _process_pdf(self, pdf_path: Path) -> None:
        logger.info("Processing: %s", pdf_path)
        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            raise ValueError("No extractable text in PDF")

        topic = infer_topic(pdf_path)
        subtopic = infer_subtopic(pdf_path, topic)
        title = pdf_path.stem.replace("_", " ").title()

        chunks = split_into_chunks(
            text,
            source_file=str(pdf_path.relative_to(DATA_ROOT.parent)),
            topic=topic,
            subtopic=subtopic,
            institution=_infer_institution(pdf_path),
            title=title,
        )

        if not chunks:
            raise ValueError("Chunking produced zero chunks")

        self.storage.save_document_chunks(pdf_path.stem, chunks)
        self.stats.chunks_created += len(chunks)
        logger.info(
            "Created %d chunks from %s (topic=%s)",
            len(chunks),
            pdf_path.name,
            topic,
        )


def _infer_institution(pdf_path: Path) -> str:
    name = pdf_path.stem.lower()
    if "stanford" in name or "cs161" in name:
        return "Stanford CS161"
    if "mit" in name:
        return "MIT OpenCourseWare"
    return "Open Educational Resource"
