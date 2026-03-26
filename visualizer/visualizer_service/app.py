# Servicio FastAPI que expone el API y websockets del visualizador.
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .aggregator import WordAggregator
from .config import Settings
from .consumer import RedisWordConsumer

logger = logging.getLogger("visualizer")
logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).parent
STATIC_DIR = ROOT_DIR / "static"
SUPPORTED_LANGUAGES = ("python", "java")

settings = Settings()
aggregator = WordAggregator(default_top_n=settings.default_top_n)
consumer = RedisWordConsumer(settings, aggregator)

app = FastAPI(title="Word Frequency Visualizer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_aggregator() -> WordAggregator:
    return aggregator


def _normalize_language(language: str) -> str:
    normalized = (language or "").strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{language}'.")
    return normalized


@app.on_event("startup")
async def on_startup() -> None:
    await aggregator.reset()
    await consumer.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await consumer.stop()


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/top-words")
async def top_words(
    language: Annotated[str, Query(description="Programming language", examples=["python", "java"])] = "python",
    limit: Annotated[int, Query(gt=0, le=100, description="Max words to return")] = settings.default_top_n,
    agg: WordAggregator = Depends(get_aggregator),
) -> dict:
    normalized_language = _normalize_language(language)
    result = await agg.get_top_words(normalized_language, limit)
    return {"language": normalized_language, "top_words": result}


@app.get("/dashboard")
async def dashboard(
    language: Annotated[str, Query(description="Programming language", examples=["python", "java"])] = "python",
    limit: Annotated[int, Query(gt=0, le=100)] = settings.default_top_n,
    combined_limit: Annotated[int, Query(gt=0, le=100)] | None = None,
    repo_limit: Annotated[int, Query(gt=1, le=25)] = settings.dashboard_repo_limit,
    activity_limit: Annotated[int, Query(gt=1, le=50)] = settings.dashboard_activity_limit,
    repo_top_words: Annotated[int, Query(gt=1, le=10)] = settings.dashboard_repo_top_words,
    agg: WordAggregator = Depends(get_aggregator),
) -> dict:
    normalized_language = _normalize_language(language)
    payload = await agg.get_dashboard_payload(
        normalized_language,
        limit,
        combined_limit=combined_limit,
        repo_limit=repo_limit,
        activity_limit=activity_limit,
        repo_top_words=repo_top_words,
    )
    return payload


@app.websocket("/ws/top-words")
async def ws_top_words(
    websocket: WebSocket,
    language: str = "python",
    limit: int = settings.default_top_n,
    agg: WordAggregator = Depends(get_aggregator),
) -> None:
    normalized_language = _normalize_language(language)
    safe_limit = max(1, min(limit, 100))
    await websocket.accept()
    version = -1
    min_interval = 1 / max(1, settings.websocket_max_updates_per_second)

    try:
        await websocket.send_json(
            {"language": normalized_language, "top_words": await agg.get_top_words(normalized_language, safe_limit)}
        )
        while True:
            version = await agg.wait_for_update(version)
            payload = await agg.get_top_words(normalized_language, safe_limit)
            await websocket.send_json({"language": normalized_language, "top_words": payload})
            if min_interval > 0:
                await asyncio.sleep(min_interval)
    except WebSocketDisconnect:
        logger.info("Client disconnected from /ws/top-words")


@app.websocket("/ws/dashboard")
async def ws_dashboard(
    websocket: WebSocket,
    language: str = "python",
    limit: int = settings.default_top_n,
    combined_limit: int | None = None,
    repo_limit: int = settings.dashboard_repo_limit,
    activity_limit: int = settings.dashboard_activity_limit,
    repo_top_words: int = settings.dashboard_repo_top_words,
    agg: WordAggregator = Depends(get_aggregator),
) -> None:
    normalized_language = _normalize_language(language)
    safe_limit = max(1, min(limit, 100))
    safe_combined_limit = None if combined_limit is None else max(1, min(combined_limit, 100))
    await websocket.accept()
    version = -1
    min_interval = 1 / max(1, settings.websocket_max_updates_per_second)

    async def _snapshot() -> dict:
        return await agg.get_dashboard_payload(
            normalized_language,
            safe_limit,
            combined_limit=safe_combined_limit,
            repo_limit=repo_limit,
            activity_limit=activity_limit,
            repo_top_words=repo_top_words,
        )

    try:
        await websocket.send_json(await _snapshot())
        while True:
            version = await agg.wait_for_update(version)
            await websocket.send_json(await _snapshot())
            if min_interval > 0:
                await asyncio.sleep(min_interval)
    except WebSocketDisconnect:
        logger.info("Client disconnected from /ws/dashboard")


__all__ = ["app", "aggregator", "consumer", "settings", "get_aggregator"]
