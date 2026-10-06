import logging
import time
import uuid

from ..config import settings
from ..utils.embeddings import cosine_similarity, local_hash_embedding

logger = logging.getLogger("quantumbio_moe.storage")


class VectorCache:
    def __init__(self, host: str = "", port: int = 6333, dimension: int = 384):
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.dimension = dimension
        self._client = None
        self._ready = False
        self._memory: dict[str, dict] = {}

    async def start(self) -> None:
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import Distance, PointStruct, VectorParams

            self._client = AsyncQdrantClient(
                url=f"http://{self.host}:{self.port}",
                check_compatibility=False,
                timeout=settings.INFRA_CONNECT_TIMEOUT,
            )
            response = await self._client.get_collections()
            collections = [c.name for c in response.collections]
            if "quantumbio_moe" not in collections:
                await self._client.create_collection(
                    collection_name="quantumbio_moe",
                    vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
                )
            self._vector_params = VectorParams(size=self.dimension, distance=Distance.COSINE)
            self._point_struct = PointStruct
            self._ready = True
            logger.info("Vector cache connected to Qdrant at %s:%s.", self.host, self.port)
        except Exception as exc:  # pragma: no cover - qdrant optional
            logger.warning("Qdrant unavailable at %s:%s (%s); using in-memory vector cache.", self.host, self.port, exc)
            self._ready = False
            self._client = None

    async def upsert(self, key: str, text: str, metadata: dict | None = None) -> str:
        vector = local_hash_embedding(text, self.dimension)
        if self._ready and self._client is not None:
            try:
                point_id = uuid.uuid5(uuid.NAMESPACE_URL, key).hex
                await self._client.upsert(
                    collection_name="quantumbio_moe",
                    points=[self._point_struct(id=point_id, vector=vector, payload={
                        "key": key, "text": text, "metadata": metadata or {},
                    })],
                )
                return point_id
            except Exception as exc:  # pragma: no cover
                logger.warning("Qdrant upsert failed: %s", exc)
        self._memory[key] = {"vector": vector, "text": text, "metadata": metadata or {}, "ts": time.time()}
        return key

    async def search(self, text: str, top_k: int = 5) -> list[dict]:
        query = local_hash_embedding(text, self.dimension)
        results: list[dict] = []
        if self._ready and self._client is not None:
            try:
                hits = await self._client.query_points(
                    collection_name="quantumbio_moe",
                    query=query,
                    limit=top_k,
                    with_payload=True,
                )
                for hit in hits.points:
                    results.append({"text": hit.payload.get("text"), "score": hit.score})
                return results
            except Exception as exc:  # pragma: no cover
                logger.warning("Qdrant search failed: %s", exc)
        scored = []
        for key, entry in self._memory.items():
            scored.append((cosine_similarity(query, entry["vector"]), entry, key))
        scored.sort(key=lambda item: item[0], reverse=True)
        for _score, entry, _key in scored[:top_k]:
            results.append({"text": entry["text"], "score": _score})
        return results

    async def clear(self) -> None:
        if self._ready and self._client is not None:
            try:
                await self._client.delete_collection(collection_name="quantumbio_moe")
            except Exception:  # pragma: no cover
                pass
        self._memory = {}

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:  # pragma: no cover
                pass