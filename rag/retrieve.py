"""Query-time retrieval over a per-organ index built by rag/ingest.py."""
from __future__ import annotations

import json
import pickle
from functools import lru_cache
from pathlib import Path

import faiss

INDEX_DIR = Path(__file__).parent / "index"


@lru_cache(maxsize=16)
def _load(organ: str):
    if not (INDEX_DIR / f"{organ}.faiss").exists():
        raise FileNotFoundError(f"No index for '{organ}'. Run: python -m rag.ingest --organ {organ}")
    index = faiss.read_index(str(INDEX_DIR / f"{organ}.faiss"))
    with open(INDEX_DIR / f"{organ}_embedder.pkl", "rb") as f:
        embedder = pickle.load(f)
    with open(INDEX_DIR / f"{organ}_chunks.json", encoding="utf-8") as f:
        meta = json.load(f)
    return index, embedder, meta


def corpus_limits(organ: str) -> str:
    """The corpus's own statement of what it does not cover."""
    return _load(organ)[2].get("limits", "")


def retrieve(organ: str, query: str, top_k: int = 3) -> list[dict]:
    """Top_k chunks for `query` from `organ`'s corpus.

    Each result: {"heading", "body", "score", "sources", "backend"}. `score`
    is cosine similarity; the guardrail compares the best score against the
    backend's MIN_SCORE (rag/embed.py).
    """
    index, embedder, meta = _load(organ)
    chunks = meta["chunks"]
    scores, idxs = index.search(embedder.encode([query]), min(top_k, len(chunks)))
    return [
        {
            "heading": chunks[i]["heading"],
            "body": chunks[i]["body"],
            "score": float(s),
            "sources": meta["sources"],
            "backend": meta["backend"],
        }
        for s, i in zip(scores[0], idxs[0]) if i != -1
    ]
