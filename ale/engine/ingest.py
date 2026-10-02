"""Ingest open educational text (Markdown, plain text, PDF) into the local chunk store.

The bundled fixture corpus is loaded automatically; user PDFs are added with `python -m ale ingest`.
PDF extraction needs the optional `pypdf` package. Nothing here touches the network.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ale.engine.config import CHUNK_WORDS, FIXTURE_CORPUS_DIR
from ale.engine.errors import TutorError
from ale.engine.store import Store
from ale.engine.text import sentences

SUPPORTED = {".md", ".txt", ".pdf"}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "doc"


def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    meta: dict[str, str] = {}
    for line in raw[3:end].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    return meta, raw[end + 4 :].lstrip("\n")


def split_markdown_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading, buf = "Introduction", []
    for line in body.splitlines():
        m = re.match(r"^#{1,3}\s+(.*\S)\s*$", line)
        if m:
            if "".join(buf).strip():
                sections.append((heading, "\n".join(buf).strip()))
            heading, buf = m.group(1), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        sections.append((heading, "\n".join(buf).strip()))
    return sections


def chunk_text(text: str, max_words: int = CHUNK_WORDS) -> list[str]:
    """Pack whole sentences into chunks of at most ~max_words words."""
    text = re.sub(r"\s+", " ", text).strip()
    chunks: list[str] = []
    cur: list[str] = []
    count = 0
    for sent in sentences(text) or [text]:
        n = len(sent.split())
        if cur and count + n > max_words:
            chunks.append(" ".join(cur))
            cur, count = [], 0
        cur.append(sent)
        count += n
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if c]


def read_pdf_pages(path: Path) -> list[tuple[int, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise TutorError(
            "PDF ingestion needs the optional 'pypdf' package: pip install 'adaptive-learning-engine[pdf]'",
            "pdf_support_missing",
            400,
        ) from exc
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((i, text))
    return pages


def _load_sections(path: Path) -> tuple[str, str, list[tuple[str, str]]]:
    """Return (title, license, [(section, text)]) for a file."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = read_pdf_pages(path)
        return path.stem, "", [(f"page {n}", text) for n, text in pages]
    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".md":
        meta, body = parse_front_matter(raw)
        return meta.get("title", path.stem), meta.get("license", ""), split_markdown_sections(body)
    return path.stem, "", [("text", raw)]


def ingest_file(store: Store, path: Path, corpus: str = "user") -> int:
    """Chunk one file and (re)write its chunks. Returns the number of chunks stored."""
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED:
        raise TutorError(f"Unsupported file type: {path.suffix or path.name}", "unsupported_file", 400)
    title, license_, sections = _load_sections(path)
    doc_id = slugify(path.stem) if corpus == "fixture" else f"u_{slugify(path.stem)}"
    rows = []
    for section, text in sections:
        for part in chunk_text(text):
            n = len(rows)
            rows.append(
                {
                    "chunk_id": f"{doc_id}#{n:03d}",
                    "doc_id": doc_id,
                    "source": path.name,
                    "source_title": title,
                    "section": section,
                    "text": part,
                    "corpus": corpus,
                    "license": license_,
                    "position": n,
                }
            )
    store.replace_document(doc_id, rows)
    return len(rows)


def ingest_path(store: Store, path: Path, corpus: str = "user") -> dict[str, int]:
    """Ingest a file, or every supported file under a directory. Returns {filename: chunks}."""
    path = Path(path)
    if not path.exists():
        raise TutorError(f"Path not found: {path}", "path_not_found", 404)
    files = (
        sorted(p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED) if path.is_dir() else [path]
    )
    return {f.name: ingest_file(store, f, corpus) for f in files}


def fixture_fingerprint() -> str:
    h = hashlib.sha256()
    for p in sorted(FIXTURE_CORPUS_DIR.glob("*.md")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def ensure_fixture(store: Store) -> bool:
    """Load the bundled fixture corpus if missing or changed. Returns True if it (re)loaded."""
    fp = fixture_fingerprint()
    if store.get_meta("fixture_fingerprint") == fp and store.chunk_count("fixture") > 0:
        return False
    for p in sorted(FIXTURE_CORPUS_DIR.glob("*.md")):
        ingest_file(store, p, corpus="fixture")
    store.set_meta("fixture_fingerprint", fp)
    return True
