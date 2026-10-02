"""PDF text extraction using PyMuPDF or pdfplumber."""

from __future__ import annotations

import logging
from pathlib import Path

from config import PDF_EXTRACTOR

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract plain text from a PDF file."""
    if PDF_EXTRACTOR == "pdfplumber":
        return _extract_with_pdfplumber(pdf_path)
    return _extract_with_pymupdf(pdf_path)


def _extract_with_pymupdf(pdf_path: Path) -> str:
    import fitz  # PyMuPDF

    pages: list[str] = []
    with fitz.open(pdf_path) as document:
        for page in document:
            text = page.get_text("text")
            if text.strip():
                pages.append(text)
    return "\n\n".join(pages)


def _extract_with_pdfplumber(pdf_path: Path) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(pdf_path) as document:
        for page in document.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
    return "\n\n".join(pages)
