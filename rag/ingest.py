"""Build a retrieval index over a per-organ markdown corpus.

Usage:
    python -m rag.ingest --organ cardiac
    python -m rag.ingest --organ all

Each organ has exactly one corpus file, rag/corpus/<organ>_*.md. Chunks are
the `##` sections; the `#` title block is not indexed, but the source URLs
listed in it are stored and cited with every answer.
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
from pathlib import Path

import faiss

from rag.embed import make_embedder

CORPUS_DIR = Path(__file__).parent / "corpus"
INDEX_DIR = Path(__file__).parent / "index"


def chunk_markdown(text: str) -> list[dict]:
    """Split a markdown doc into (heading, body) chunks on '##' boundaries."""
    chunks = []
    for part in re.split(r"\n(?=## )", text):
        part = part.strip()
        if part:
            chunks.append({"heading": part.splitlines()[0].lstrip("# ").strip(), "body": part})
    return chunks


def corpus_path_for(organ: str) -> Path:
    matches = sorted(CORPUS_DIR.glob(f"{organ}_*.md"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one corpus file rag/corpus/{organ}_*.md, found {len(matches)}")
    return matches[0]


def build_index(organ: str) -> None:
    path = corpus_path_for(organ)
    all_chunks = chunk_markdown(path.read_text(encoding="utf-8"))
    title = next((c for c in all_chunks if c["body"].startswith("# ")), None)
    sources = re.findall(r"https?://\S+", title["body"]) if title else []
    # "Limits of this corpus" / "Notes for this agent" sections describe what the
    # corpus does NOT cover. They go into the agent's system prompt, not the
    # index — indexed, they match random off-topic queries.
    is_meta = lambda c: c["heading"].lower().startswith(("limits of", "notes for"))
    limits = "\n".join(c["body"] for c in all_chunks if is_meta(c))
    chunks = [c for c in all_chunks if not c["body"].startswith("# ") and not is_meta(c)]

    # heading repeated so section titles weigh a bit more than body text
    docs = [f"{c['heading']}. {c['heading']}. {c['body']}" for c in chunks]
    embedder = make_embedder().fit(docs)
    vectors = embedder.encode(docs)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_DIR / f"{organ}.faiss"))
    with open(INDEX_DIR / f"{organ}_embedder.pkl", "wb") as f:
        pickle.dump(embedder, f)
    with open(INDEX_DIR / f"{organ}_chunks.json", "w", encoding="utf-8") as f:
        json.dump({"corpus": path.name, "sources": sources, "backend": embedder.name,
                   "limits": limits, "chunks": chunks}, f, indent=2)
    print(f"[{embedder.name}] indexed {len(chunks)} chunks for '{organ}' from {path.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--organ", required=True, help="an organ name (e.g. cardiac) or 'all'")
    args = parser.parse_args()
    if args.organ == "all":
        from agents.registry import ORGANS
        for organ in ORGANS:
            build_index(organ)
    else:
        build_index(args.organ)
