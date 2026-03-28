from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

logger = logging.getLogger(__name__)


class ChromaMemoryStore:
    def __init__(self, persist_path: Path):
        self.persist_path = persist_path
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self.client = None
        self.collection = None
        try:
            self.client = chromadb.PersistentClient(path=str(self.persist_path))
            self.collection = self.client.get_or_create_collection(
                name="agent1_memory",
                embedding_function=DefaultEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning("Vector memory disabled; failed to initialize Chroma at %s: %s", self.persist_path, exc)

    def add_text(self, user_id: str, text: str, kind: str) -> None:
        text = text.strip()
        if not text or self.collection is None:
            return

        try:
            self.collection.add(
                ids=[str(uuid4())],
                documents=[text],
                metadatas=[
                    {
                        "user_id": str(user_id),
                        "kind": kind,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            )
        except Exception as exc:
            logger.warning("Vector write failed: %s", exc)

    def search(self, user_id: str, query: str, k: int = 4) -> list[str]:
        query = query.strip()
        if not query or self.collection is None:
            return []
        try:
            result = self.collection.query(
                query_texts=[query],
                n_results=k,
                where={"user_id": str(user_id)},
            )
        except Exception as exc:
            logger.warning("Vector search failed: %s", exc)
            return []

        docs = result.get("documents", [])
        if not docs or not docs[0]:
            return []
        return [item for item in docs[0] if isinstance(item, str)]
