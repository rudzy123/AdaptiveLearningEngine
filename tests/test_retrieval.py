"""Local RAG: ingestion, BM25 retrieval and citation shape. No network involved."""

import pytest

from ale.engine import Tutor
from ale.engine.ingest import chunk_text, ensure_fixture, ingest_path, parse_front_matter
from ale.engine.lesson import build_query

CITATION_KEYS = {"n", "source", "source_title", "section", "chunk_id", "score", "excerpt"}


def test_fixture_corpus_loads_offline_and_is_idempotent(tutor):
    n = tutor.store.chunk_count("fixture")
    assert n == 28
    assert ensure_fixture(tutor.store) is False  # unchanged -> no reload
    assert tutor.store.chunk_count("fixture") == n


def test_every_concept_retrieves_its_own_sections_first(tutor):
    for cid, concept in tutor.curriculum.concepts.items():
        hits = tutor.retriever().search(build_query(concept), k=4)
        assert len(hits) == 4
        assert all(h.chunk.section.lower().startswith(concept.title.lower().split()[0]) for h in hits), (
            cid, [h.chunk.section for h in hits])


def test_search_returns_scored_cited_hits(tutor):
    results = tutor.search("orthogonal vectors have dot product zero", k=3)
    assert results[0]["section"].startswith("Dot product")
    assert [r["score"] for r in results] == sorted((r["score"] for r in results), reverse=True)
    for r in results:
        assert CITATION_KEYS <= set(r)
        assert isinstance(r["score"], float) and r["score"] > 0


def test_lesson_citations_are_grounded_in_stored_chunks(tutor):
    tutor.start_topic("ada", "linear algebra")
    lesson = tutor.get_lesson("ada")
    assert 1 <= len(lesson["citations"]) <= 3
    chunks = {c["chunk_id"]: c for c in tutor.store.all_chunks()}
    for i, c in enumerate(lesson["citations"], start=1):
        assert CITATION_KEYS <= set(c)
        assert c["n"] == i and c["score"] > 0
        stored = chunks[c["chunk_id"]]
        assert c["source"] == stored["source"] and c["section"] == stored["section"]
        assert c["excerpt"] in stored["text"]  # extractive: nothing invented
        assert f"[{i}]" in lesson["body"]
    assert lesson["generator"].startswith("extractive")


def test_markdown_front_matter_and_chunking():
    meta, body = parse_front_matter("---\ntitle: T\nlicense: CC0\n---\n\n## A\nx")
    assert meta == {"title": "T", "license": "CC0"} and body.startswith("## A")
    parts = chunk_text(" ".join(f"Sentence number {i} has several words in it." for i in range(60)), max_words=40)
    assert len(parts) > 3 and all(len(p.split()) <= 48 for p in parts)


def test_user_documents_join_the_index(tutor, tmp_path):
    doc = tmp_path / "notes.md"
    doc.write_text("# Quaternions\n\nQuaternions extend complex numbers and encode three dimensional rotation "
                   "without gimbal lock. A unit quaternion represents a rotation.\n")
    assert ingest_path(tutor.store, doc) == {"notes.md": 1}
    hits = tutor.search("quaternion rotation gimbal", k=2)
    assert hits[0]["source"] == "notes.md" and hits[0]["chunk_id"].startswith("u_notes#")
    ingest_path(tutor.store, doc)  # re-ingest replaces rather than duplicates
    assert tutor.store.chunk_count() == 29


def test_pdf_ingestion(tutor, tmp_path):
    pytest.importorskip("pypdf")
    text = ("Fourier series decompose a periodic signal into sine and cosine components. "
            "Each coefficient measures how much of one frequency the signal contains.")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    pdf = tmp_path / "signals.pdf"
    pdf.write_bytes(out)

    assert ingest_path(tutor.store, pdf)["signals.pdf"] >= 1
    hits = tutor.search("fourier frequency coefficient", k=1)
    assert hits[0]["source"] == "signals.pdf" and hits[0]["section"] == "page 1"
