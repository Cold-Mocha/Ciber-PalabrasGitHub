# Consumidor de Redis que envía palabras y progreso al agregador del visualizer.
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Optional

import redis.asyncio as redis

from .aggregator import WordAggregator
from .config import Settings

logger = logging.getLogger(__name__)


class RedisWordConsumer:
    """Consumes words from Redis and forwards them to the aggregator."""

    def __init__(self, settings: Settings, aggregator: WordAggregator):
        self._settings = settings
        self._aggregator = aggregator
        self._redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="redis-word-consumer")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._redis.close()

    async def _run(self) -> None:
        while self._running:
            try:
                result = await self._redis.blpop(
                    self._settings.redis_queue_name,
                    timeout=self._settings.redis_block_timeout,
                )
                if not result:
                    continue
                _, payload = result
                parsed = self._parse_payload(payload)
                if parsed.get("type") == "progress":
                    await self._aggregator.record_progress(parsed)
                    continue

                language = parsed.get("language")
                word = parsed.get("word")
                repo = parsed.get("repo")
                file_path = parsed.get("file_path")
                function_name = parsed.get("function_name")
                if not word:
                    continue
                await self._aggregator.record_word(
                    language,
                    word,
                    repo=repo,
                    file_path=file_path,
                    function_name=function_name,
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.exception("Redis consumer error: %s", exc)
                await asyncio.sleep(1)

    @staticmethod
    def _parse_payload(payload: str) -> dict:
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            # Backwards compatibility: payload may be solo la palabra.
            return {"language": "unknown", "word": payload}
