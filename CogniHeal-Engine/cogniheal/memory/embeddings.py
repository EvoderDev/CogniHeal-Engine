"""Embedding generation utilities.

Provides a thin wrapper around the OpenAI embeddings API with an
offline fallback that uses a deterministic hash-based pseudo-embedding
for environments where no API key is configured.
"""

from __future__ import annotations

import hashlib
import struct
from typing import TYPE_CHECKING

import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

if TYPE_CHECKING:
    from openai import OpenAI

from cogniheal.config import settings

_EMBEDDING_DIM = 1536  # text-embedding-3-small dimension


def _get_openai_client() -> "OpenAI":
    """Lazily construct a shared OpenAI client."""
    from openai import OpenAI as _OpenAI

    return _OpenAI(api_key=settings.openai_api_key)


def _deterministic_pseudo_embedding(text: str, dim: int = _EMBEDDING_DIM) -> list[float]:
    """Generate a deterministic pseudo-embedding from a SHA-256 digest.

    This is **not** a real semantic embedding — it is used solely as a
    fallback so the pipeline can run end-to-end without an API key
    during development and testing.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(seed=int.from_bytes(digest[:8], "little"))
    vec = rng.standard_normal(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _call_openai_embedding(text: str) -> list[float]:
    """Call the OpenAI embeddings endpoint with automatic retry."""
    client = _get_openai_client()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding


def generate_embedding(text: str) -> list[float]:
    """Return a normalised embedding vector for *text*.

    Uses the OpenAI API when an API key is configured; otherwise falls
    back to a deterministic pseudo-embedding.

    Args:
        text: The text to embed.

    Returns:
        A list of floats representing the embedding vector.
    """
    if settings.openai_api_key:
        try:
            return _call_openai_embedding(text)
        except Exception:
            return _deterministic_pseudo_embedding(text)
    return _deterministic_pseudo_embedding(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Cosine similarity in the range [-1, 1].
    """
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    dot = float(np.dot(va, vb))
    norm_a = float(np.linalg.norm(va))
    norm_b = float(np.linalg.norm(vb))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
