"""
Nexearch — Vector Store
Dual backend: ChromaDB (primary) with JSON file fallback.
Handles per-client collections and global signal storage.
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from nexearch.config import get_nexearch_settings


class VectorStoreResult:
    """A single result from a vector store query."""
    def __init__(self, id: str, document: str, metadata: Dict[str, Any], distance: float):
        self.id = id
        self.document = document
        self.metadata = metadata
        self.distance = distance  # Lower = more similar
        self.similarity = 1.0 - distance  # Higher = more similar

    def __repr__(self):
        return f"VectorStoreResult(id={self.id}, similarity={self.similarity:.3f})"


class VectorStore:
    """
    Abstraction over ChromaDB and JSON file storage.
    Auto-detects ChromaDB availability and falls back to JSON.
    """

    def __init__(self):
        self._settings = get_nexearch_settings()
        self._backend = "json"  # Default
        self._chroma_client = None
        self._json_dir = Path(self._settings.CHROMA_PERSIST_DIRECTORY) / "json_fallback"

        # Try to initialize ChromaDB
        try:
            import chromadb
            persist_dir = str(self._settings.chroma_persist_path)
            os.makedirs(persist_dir, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=persist_dir)
            self._backend = "chromadb"
            logger.info(f"VectorStore: ChromaDB initialized at {persist_dir}")
        except (ImportError, Exception) as e:
            logger.warning(f"ChromaDB not available ({e}). Using JSON fallback.")
            self._json_dir.mkdir(parents=True, exist_ok=True)

    @property
    def backend(self) -> str:
        """Return the active backend name."""
        return self._backend

    def upsert(
        self,
        collection: str,
        id: str,
        document: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> bool:
        """Insert or update a document in the vector store."""
        try:
            if self._backend == "chromadb":
                return self._chroma_upsert(collection, id, document, embedding, metadata)
            else:
                return self._json_upsert(collection, id, document, embedding, metadata)
        except Exception as e:
            logger.error(f"VectorStore upsert failed: {e}")
            return False

    def query(
        self,
        collection: str,
        embedding: List[float],
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorStoreResult]:
        """Query for similar documents by embedding vector."""
        try:
            if self._backend == "chromadb":
                return self._chroma_query(collection, embedding, n_results, filters)
            else:
                return self._json_query(collection, embedding, n_results, filters)
        except Exception as e:
            logger.error(f"VectorStore query failed: {e}")
            return []

    def delete(self, collection: str, id: str) -> bool:
        """Delete a document from the vector store."""
        try:
            if self._backend == "chromadb":
                return self._chroma_delete(collection, id)
            else:
                return self._json_delete(collection, id)
        except Exception as e:
            logger.error(f"VectorStore delete failed: {e}")
            return False

    def collection_stats(self, collection: str) -> Dict[str, Any]:
        """Get stats for a collection."""
        try:
            if self._backend == "chromadb":
                return self._chroma_stats(collection)
            else:
                return self._json_stats(collection)
        except Exception as e:
            logger.error(f"VectorStore stats failed: {e}")
            return {"error": str(e)}

    def list_collections(self) -> List[str]:
        """List all collections."""
        if self._backend == "chromadb":
            cols = self._chroma_client.list_collections()
            return [c.name for c in cols]
        else:
            return [f.stem for f in self._json_dir.glob("*.json")]

    # ── ChromaDB Backend ──────────────────────────────────────

    def _chroma_upsert(self, collection, id, document, embedding, metadata):
        col = self._chroma_client.get_or_create_collection(name=collection)
        # ChromaDB metadata must be flat (no nested dicts/lists)
        flat_metadata = self._flatten_metadata(metadata)
        col.upsert(ids=[id], documents=[document], embeddings=[embedding], metadatas=[flat_metadata])
        return True

    def _chroma_query(self, collection, embedding, n_results, filters):
        try:
            col = self._chroma_client.get_collection(name=collection)
        except Exception:
            return []
        where = self._build_chroma_where(filters) if filters else None
        kwargs = {"query_embeddings": [embedding], "n_results": n_results}
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)
        output = []
        if results and results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                output.append(VectorStoreResult(
                    id=doc_id,
                    document=results["documents"][0][i] if results.get("documents") else "",
                    metadata=results["metadatas"][0][i] if results.get("metadatas") else {},
                    distance=results["distances"][0][i] if results.get("distances") else 0.0,
                ))
        return output

    def _chroma_delete(self, collection, id):
        try:
            col = self._chroma_client.get_collection(name=collection)
            col.delete(ids=[id])
            return True
        except Exception:
            return False

    def _chroma_stats(self, collection):
        try:
            col = self._chroma_client.get_collection(name=collection)
            return {"collection": collection, "count": col.count(), "backend": "chromadb"}
        except Exception:
            return {"collection": collection, "count": 0, "backend": "chromadb"}

    # ── JSON Fallback Backend ─────────────────────────────────

    def _json_path(self, collection: str) -> Path:
        return self._json_dir / f"{collection}.json"

    def _json_load(self, collection: str) -> Dict[str, Any]:
        path = self._json_path(collection)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"documents": {}}

    def _json_save(self, collection: str, data: Dict[str, Any]):
        path = self._json_path(collection)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)

    def _json_upsert(self, collection, id, document, embedding, metadata):
        data = self._json_load(collection)
        data["documents"][id] = {
            "document": document,
            "embedding": embedding,
            "metadata": metadata,
            "updated_at": time.time(),
        }
        self._json_save(collection, data)
        return True

    def _json_query(self, collection, embedding, n_results, filters):
        data = self._json_load(collection)
        if not data.get("documents"):
            return []

        scored = []
        for doc_id, doc_data in data["documents"].items():
            # Apply filters
            if filters and not self._matches_filters(doc_data.get("metadata", {}), filters):
                continue
            # Compute cosine similarity
            doc_emb = doc_data.get("embedding", [])
            if doc_emb:
                similarity = self._cosine_sim(embedding, doc_emb)
                distance = 1.0 - similarity
            else:
                distance = 1.0
            scored.append(VectorStoreResult(
                id=doc_id,
                document=doc_data.get("document", ""),
                metadata=doc_data.get("metadata", {}),
                distance=distance,
            ))

        # Sort by distance (ascending = most similar first)
        scored.sort(key=lambda x: x.distance)
        return scored[:n_results]

    def _json_delete(self, collection, id):
        data = self._json_load(collection)
        if id in data.get("documents", {}):
            del data["documents"][id]
            self._json_save(collection, data)
            return True
        return False

    def _json_stats(self, collection):
        data = self._json_load(collection)
        return {
            "collection": collection,
            "count": len(data.get("documents", {})),
            "backend": "json",
        }

    # ── Utilities ─────────────────────────────────────────────

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _flatten_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten metadata for ChromaDB (no nested dicts/lists)."""
        flat = {}
        for k, v in metadata.items():
            if isinstance(v, (dict, list)):
                flat[k] = json.dumps(v, default=str)
            elif v is None:
                flat[k] = ""
            else:
                flat[k] = v
        return flat

    @staticmethod
    def _matches_filters(metadata: Dict, filters: Dict) -> bool:
        """Check if metadata matches filter criteria."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        return True

    @staticmethod
    def _build_chroma_where(filters: Dict) -> Optional[Dict]:
        """Build ChromaDB where clause from simple filters."""
        if not filters:
            return None
        if len(filters) == 1:
            key, value = list(filters.items())[0]
            return {key: {"$eq": value}}
        conditions = [{k: {"$eq": v}} for k, v in filters.items()]
        return {"$and": conditions}


# ── Singleton ────────────────────────────────────────────────

_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Factory — returns the vector store singleton."""
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorStore()
    return _store_instance
