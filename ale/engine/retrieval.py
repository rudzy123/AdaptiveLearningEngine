"""Local retrieval: BM25 over stored chunks. No embeddings service, no network."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from ale.engine.config import BM25_B, BM25_K1
from ale.engine.store import Store
from ale.engine.text import stems


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    source_title: str
    section: str
    text: str
    corpus: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float

    def citation(self, n: int | None = None, excerpt: str | None = None) -> dict:
        out = {
            "source": self.chunk.source,
            "source_title": self.chunk.source_title,
            "section": self.chunk.section,
            "chunk_id": self.chunk.chunk_id,
            "score": round(self.score, 3),
            "excerpt": excerpt if excerpt is not None else self.chunk.text,
        }
        if n is not None:
            out = {"n": n, **out}
        return out


class Retriever:
    """BM25 with the section heading indexed alongside the text (headings are weighted by repetition)."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._tf: list[Counter] = []
        self._len: list[int] = []
        df: Counter = Counter()
        for c in chunks:
            toks = stems(c.section) * 2 + stems(c.text)
            tf = Counter(toks)
            self._tf.append(tf)
            self._len.append(len(toks))
            df.update(tf.keys())
        n = len(chunks)
        self._avg = (sum(self._len) / n) if n else 0.0
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    @classmethod
    def from_store(cls, store: Store) -> "Retriever":
        return cls(
            [
                Chunk(r["chunk_id"], r["source"], r["source_title"], r["section"], r["text"], r["corpus"])
                for r in store.all_chunks()
            ]
        )

    def search(self, query: str, k: int = 4, exclude: set[str] | frozenset[str] = frozenset()) -> list[Hit]:
        q = stems(query)
        if not q or not self.chunks:
            return []
        qtf = Counter(q)  # repeated query terms carry proportionally more weight
        hits: list[Hit] = []
        for i, c in enumerate(self.chunks):
            if c.chunk_id in exclude:
                continue
            tf, dl = self._tf[i], self._len[i]
            score = 0.0
            for term, weight in qtf.items():
                f = tf.get(term, 0)
                if not f:
                    continue
                denom = f + BM25_K1 * (1 - BM25_B + BM25_B * dl / (self._avg or 1))
                score += weight * self._idf.get(term, 0.0) * f * (BM25_K1 + 1) / denom
            if score > 0:
                hits.append(Hit(c, score))
        hits.sort(key=lambda h: (-h.score, h.chunk.chunk_id))
        return hits[:k]
