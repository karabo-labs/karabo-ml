"""HTTP client for the RAG DevOps Assistant API."""

from __future__ import annotations

from typing import Any

import httpx
from kb.logger import get_logger

logger = get_logger()


class RagClient:
    """Client for the RAG DevOps Assistant API."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def health(self) -> dict[str, Any]:
        """Check the API health endpoint."""
        try:
            resp = self._client.get("/health")
            resp.raise_for_status()
            return resp.json() | {"reachable": True}
        except httpx.HTTPError as e:
            logger.warning(f"Health check failed: {e}")
            return {"status": "unreachable", "reachable": False, "error": str(e)}

    def query(
        self,
        question: str,
        top_k: int = 5,
        include_sources: bool = True,
    ) -> dict[str, Any]:
        """Send a RAG query to the API."""
        payload = {
            "question": question,
            "top_k": top_k,
            "include_sources": include_sources,
        }
        try:
            resp = self._client.post("/query", json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Query failed: {e}")
            return {"error": str(e), "question": question, "answer": ""}

    def qdrant_info(self) -> dict[str, Any]:
        """Get Qdrant health info from the API health endpoint."""
        return self.health()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
