import logging

from ..config import settings

logger = logging.getLogger("quantumbio_moe.storage")


class RedisStore:
    def __init__(self, host: str = "", port: int = 6379, ttl: int = 3600):
        self.host = host or settings.REDIS_HOST
        self.port = port or settings.REDIS_PORT
        self.ttl = ttl
        self._client = None
        self._fallback: dict[str, str] = {}

    async def start(self) -> None:
        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                f"redis://{self.host}:{self.port}",
                decode_responses=True,
                socket_connect_timeout=settings.INFRA_CONNECT_TIMEOUT,
                socket_timeout=settings.INFRA_CONNECT_TIMEOUT,
            )
            await self._client.ping()
        except Exception as exc:  # pragma: no cover - redis optional
            logger.warning("Redis unavailable at %s:%s (%s); using in-memory cache.", self.host, self.port, exc)
            self._client = None

    async def get(self, key: str) -> str | None:
        if self._client:
            try:
                return await self._client.get(key)
            except Exception:  # pragma: no cover
                return None
        return self._fallback.get(key)

    async def set(self, key: str, value: str) -> None:
        if self._client:
            try:
                await self._client.set(key, value, ex=self.ttl)
                return
            except Exception:  # pragma: no cover
                pass
        self._fallback[key] = value

    async def close(self) -> None:
        if self._client:
            try:
                await self._client.aclose()
            except Exception:  # pragma: no cover
                pass


class Database:
    def __init__(self, url: str = ""):
        self.url = url or settings.DATABASE_URL
        self._pool = None

    async def start(self) -> None:
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self.url.replace("postgresql+asyncpg://", "postgresql://"),
                timeout=settings.INFRA_CONNECT_TIMEOUT,
            )
            logger.info("Postgres connection pool ready.")
        except Exception as exc:  # pragma: no cover - postgres optional
            logger.warning("Postgres unavailable (%s); SQL persistence disabled.", exc)
            self._pool = None

    async def log_request(self, *, request_id: str, model: str, prompt_tokens: int,
                          completion_tokens: int, expert: str, latency_ms: int) -> None:
        if self._pool is None:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS request_log (
                        id TEXT PRIMARY KEY,
                        model TEXT, expert TEXT,
                        prompt_tokens INT, completion_tokens INT,
                        latency_ms INT, created_at TIMESTAMPTZ DEFAULT now()
                    )
                    """
                )
                await conn.execute(
                    """
                    INSERT INTO request_log(id, model, expert, prompt_tokens, completion_tokens, latency_ms)
                    VALUES($1, $2, $3, $4, $5, $6)
                    """,
                    request_id, model, expert, prompt_tokens, completion_tokens, latency_ms,
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not persist request log: %s", exc)

    async def close(self) -> None:
        if self._pool:
            try:
                await self._pool.close()
            except Exception:  # pragma: no cover
                pass