"""
Nexearch — Embedding Router
Supports local (sentence-transformers) and OpenAI embeddings.
Used for vector store operations (ChromaDB / JSON fallback).
"""

import numpy as np
from typing import List, Optional
from loguru import logger

from nexearch.config import get_nexearch_settings


class EmbeddingRouter:
    """
    Generates text embeddings using either local sentence-transformers
    (all-MiniLM-L6-v2, free, CPU) or OpenAI (text-embedding-3-small).
    """

    def __init__(self, provider: Optional[str] = None):
        settings = get_nexearch_settings()
        self._provider = provider or settings.EMBEDDING_PROVIDER
        self._model = None
        self._dimension = 384  # Default for MiniLM

        if self._provider == "local":
            self._init_local()
        elif self._provider == "openai":
            self._init_openai()
        else:
            logger.warning(f"Unknown embedding provider '{self._provider}', falling back to local")
            self._provider = "local"
            self._init_local()

    def _init_local(self):
        """Initialize sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._dimension = 384
            logger.info("EmbeddingRouter: local model (all-MiniLM-L6-v2) loaded")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            # Fallback: use a simple hash-based embedding for dev
            self._model = None
            self._dimension = 384

    def _init_openai(self):
        """Initialize OpenAI embedding client."""
        settings = get_nexearch_settings()
        if not settings.has_openai:
            logger.warning("OpenAI API key not set. Falling back to local embeddings.")
            self._provider = "local"
            self._init_local()
            return
        self._dimension = 1536  # text-embedding-3-small dimension
        logger.info("EmbeddingRouter: OpenAI (text-embedding-3-small) configured")

    @property
    def dimension(self) -> int:
        """Return the embedding dimension for the current model."""
        return self._dimension

    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text string."""
        if self._provider == "local":
            return self._embed_local(text)
        elif self._provider == "openai":
            return self._embed_openai(text)
        return self._embed_fallback(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of text strings."""
        if self._provider == "local":
            return self._embed_local_batch(texts)
        elif self._provider == "openai":
            return self._embed_openai_batch(texts)
        return [self._embed_fallback(t) for t in texts]

    def _embed_local(self, text: str) -> List[float]:
        """Generate embedding using sentence-transformers."""
        if self._model is None:
            return self._embed_fallback(text)
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def _embed_local_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding with sentence-transformers."""
        if self._model is None:
            return [self._embed_fallback(t) for t in texts]
        embeddings = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return [e.tolist() for e in embeddings]

    def _embed_openai(self, text: str) -> List[float]:
        """Generate embedding via OpenAI API."""
        import openai
        settings = get_nexearch_settings()
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def _embed_openai_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding via OpenAI API."""
        import openai
        settings = get_nexearch_settings()
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]

    def _embed_fallback(self, text: str) -> List[float]:
        """
        Fallback embedding using deterministic hashing.
        NOT suitable for production — only for dev when no models available.
        """
        import hashlib
        hash_bytes = hashlib.sha384(text.encode()).digest()
        # Convert bytes to floats in [-1, 1] range
        values = []
        for b in hash_bytes:
            values.append((b / 127.5) - 1.0)
        # Pad/trim to dimension
        while len(values) < self._dimension:
            values.append(0.0)
        values = values[:self._dimension]
        # Normalize
        norm = sum(v * v for v in values) ** 0.5
        if norm > 0:
            values = [v / norm for v in values]
        return values

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two embedding vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))


# ── Singleton ────────────────────────────────────────────────

_embedding_instance: Optional[EmbeddingRouter] = None


def get_embedding_router() -> EmbeddingRouter:
    """Factory — returns the embedding router singleton."""
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = EmbeddingRouter()
    return _embedding_instance
