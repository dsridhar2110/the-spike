"""Embedding + vector store for the document corpus.

The corpus is deliberately small and deliberately *ours*. `docs/` holds the
hackathon organisers' material and is git-ignored — not ours to republish — so
it is excluded by default and can only be added with an explicit local-only
flag that never reaches a deployment.

Two choices worth defending:

* **Asymmetric task types.** A document is embedded as RETRIEVAL_DOCUMENT and a
  question as RETRIEVAL_QUERY. A question and the passage that answers it are
  not paraphrases of each other — "why do councils decide late?" looks nothing
  like the paragraph that explains it. Task types tell the embedding model which
  side of that asymmetry it is encoding, and it is free accuracy.

* **A relevance floor.** Nearest-neighbour search always returns something: ask
  about the weather and you still get the three least-unrelated chunks. Without
  a floor, the agent would cite them. `MIN_SIMILARITY` is what lets the tool say
  "I found nothing relevant" instead of inventing a grounded-looking answer.
"""

from __future__ import annotations

import os
import time
from collections import deque
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from .chunker import Chunk, chunk_files

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_ROOT = Path(__file__).resolve().parents[2]
PERSIST_DIR = AGENT_ROOT / ".chroma"
COLLECTION = "planning_docs"

load_dotenv(AGENT_ROOT / ".env")

EMBED_MODEL = os.getenv("PLANNING_EMBED_MODEL", "gemini-embedding-001")
# 768 rather than the 3072 default: gemini-embedding-001 is trained so that a
# truncated prefix is still a usable embedding, so this is 4x less storage and
# faster search for no meaningful loss on a corpus this size.
EMBED_DIM = 768

# Cosine similarity below this is treated as "nothing relevant found".
#
# NOT guessed — measured. scripts/build_index.py probes the built index with
# on-topic and off-topic questions and prints both bands. Measured on this
# corpus: on-topic bottoms out at 0.727, off-topic tops out at 0.568 (a weather
# question, of all things), so anything in between separates them. 0.65 is the
# midpoint.
#
# The first guess was 0.55 and it leaked the weather question. That is the whole
# argument for calibrating: an unmeasured threshold silently cites noise.
MIN_SIMILARITY = 0.65

# Our own writing only. The organisers' PDFs and briefs in docs/ are excluded.
OWN_CORPUS = [
    REPO_ROOT / "METHOD.md",
    REPO_ROOT / "BRIEF.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / "PITCH.md",
    REPO_ROOT / "HANDOFF.md",
]

# Local-only, never deployed. Licence: event use only, do not republish.
EVENT_ONLY_CORPUS = [
    REPO_ROOT / "docs" / "policy-briefs.md",
    REPO_ROOT / "docs" / "data-briefs.md",
]

_client: genai.Client | None = None


def _genai() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


class _RateLimiter:
    """Free-tier embedding quota is 100 requests per minute, and the API counts
    each *content item* as a request — a batch of 50 texts costs 50, not 1. So
    indexing 92 chunks and then running a few queries in the same minute trips
    it, which is exactly how this was discovered.

    A sliding window of recent call timestamps; sleeps only when the window is
    full. Cheaper and more predictable than finding the limit via 429s.
    """

    def __init__(self, max_per_minute: int = 90, window_seconds: float = 60.0):
        self.max_per_minute = max_per_minute
        self.window_seconds = window_seconds
        self._calls: deque[float] = deque()

    def acquire(self, n: int = 1) -> None:
        while True:
            now = time.monotonic()
            while self._calls and now - self._calls[0] > self.window_seconds:
                self._calls.popleft()
            if len(self._calls) + n <= self.max_per_minute:
                self._calls.extend([now] * n)
                return
            sleep_for = self.window_seconds - (now - self._calls[0]) + 0.1
            time.sleep(max(sleep_for, 0.1))


_limiter = _RateLimiter()


def embed(texts: list[str], *, is_query: bool, max_retries: int = 4) -> list[list[float]]:
    """Embed texts. Queries and documents use different task types on purpose.

    Rate-limited ahead of time and still retried with backoff: the limiter stops
    us provoking a 429, the retry survives one we failed to predict.
    """
    _limiter.acquire(len(texts))
    for attempt in range(max_retries):
        try:
            response = _genai().models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT",
                    output_dimensionality=EMBED_DIM,
                ),
            )
            return [list(item.values) for item in response.embeddings]
        except ClientError as exc:
            if exc.code != 429 or attempt == max_retries - 1:
                raise
            # 1s, 4s, 16s — comfortably past the ~14s the API asks for
            time.sleep(4**attempt)
    raise RuntimeError("unreachable")


def _collection(create: bool = False):
    client = chromadb.PersistentClient(path=str(PERSIST_DIR))
    if create:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
        # Cosine, not the L2 default: embeddings carry meaning in direction, and
        # cosine ignores magnitude.
        return client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    return client.get_collection(COLLECTION)


def build(include_event_only: bool = False, batch_size: int = 50) -> list[Chunk]:
    """Chunk, embed and store the corpus. Returns the chunks written."""
    paths = list(OWN_CORPUS) + (list(EVENT_ONLY_CORPUS) if include_event_only else [])
    chunks = chunk_files(paths)
    if not chunks:
        raise RuntimeError(f"No chunks produced from {[p.name for p in paths]}")

    collection = _collection(create=True)
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        collection.add(
            ids=[f"{c.id}-{start + i}" for i, c in enumerate(batch)],
            documents=[c.text for c in batch],
            embeddings=embed([c.text for c in batch], is_query=False),
            metadatas=[c.to_metadata() for c in batch],
        )
    return chunks


def search(query: str, top_k: int = 4) -> list[dict]:
    """Return the top_k most similar chunks, each with its similarity score.

    Filtering against MIN_SIMILARITY is the caller's job — the tool needs to see
    the near-misses to explain *why* it found nothing.
    """
    collection = _collection()
    result = collection.query(
        query_embeddings=embed([query], is_query=True),
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for text, meta, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "text": text,
                "citation": meta["heading_path"],
                "source": meta["source"],
                # chroma returns cosine distance; similarity is 1 - distance
                "similarity": round(1.0 - distance, 4),
            }
        )
    return hits


def index_exists() -> bool:
    try:
        _collection()
        return True
    except Exception:
        return False
