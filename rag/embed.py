"""Embedding backends for retrieval. Pick with EMBED_BACKEND in .env.

tfidf  (default) — word + character n-gram TF-IDF. Fully offline, no model
        download. Character n-grams handle word forms ("transmitted" vs
        "transmission") that plain word TF-IDF misses. Good enough for small
        curated corpora; similarity scores are low and noisy, so the
        guardrail threshold is conservative.
nebius — a neural embedding model served on Nebius Token Factory
        (OpenAI-compatible embeddings endpoint). Better semantic matching,
        and keeps another part of the pipeline on Nebius. Set
        NEBIUS_EMBED_MODEL to an embedding model ID from the Nebius console.
        Not tested from this build environment (no network access to
        Nebius) — run tests locally after switching.

Each backend has its own MIN_SCORE for the retrieval-confidence guardrail,
because similarity scales differ a lot between them. Re-calibrate after
switching: run `python -m rag.calibrate`.
"""
from __future__ import annotations

import os

import numpy as np
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.preprocessing import normalize

load_dotenv()
BACKEND = os.environ.get("EMBED_BACKEND", "tfidf").lower()

MIN_SCORE = {
    # tfidf: on this corpus, correctly-routed on-topic queries mostly score
    # 0.2-0.45; off-topic text scores up to ~0.2. Off-topic queries are
    # mostly stopped earlier by routing, so this threshold is a backstop.
    "tfidf": 0.12,
    # nebius: placeholder until calibrated against real scores.
    "nebius": 0.30,
}


class TfidfEmbedder:
    name = "tfidf"

    def __init__(self):
        self.vec = FeatureUnion([
            ("word", TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ])

    def fit(self, texts: list[str]) -> "TfidfEmbedder":
        self.vec.fit(texts)
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        return normalize(self.vec.transform(texts)).toarray().astype("float32")


class NebiusEmbedder:
    name = "nebius"

    def __init__(self):
        self.model = os.environ.get("NEBIUS_EMBED_MODEL")
        if not self.model:
            raise RuntimeError("EMBED_BACKEND=nebius needs NEBIUS_EMBED_MODEL set in .env")

    def fit(self, texts: list[str]) -> "NebiusEmbedder":
        return self  # nothing to fit

    def encode(self, texts: list[str]) -> np.ndarray:
        from orchestrator.client import _client
        resp = _client().embeddings.create(model=self.model, input=texts)
        arr = np.array([d.embedding for d in resp.data], dtype="float32")
        return normalize(arr).astype("float32")

    # the OpenAI client isn't picklable; drop it and rebuild on load
    def __getstate__(self):
        return {"model": self.model}

    def __setstate__(self, state):
        self.model = state["model"]


def make_embedder():
    if BACKEND == "tfidf":
        return TfidfEmbedder()
    if BACKEND == "nebius":
        return NebiusEmbedder()
    raise ValueError(f"Unknown EMBED_BACKEND '{BACKEND}' (use tfidf or nebius)")
