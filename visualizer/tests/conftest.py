import asyncio
import pytest
import pytest_asyncio
import httpx

from visualizer.visualizer_service import app as app_module
from visualizer.visualizer_service.app import app, aggregator


class _DummyConsumer:
    async def start(self) -> None:  # pragma: no cover - trivial
        return None

    async def stop(self) -> None:  # pragma: no cover - trivial
        return None


@pytest.fixture(autouse=True)
def patch_consumer(monkeypatch):
    dummy = _DummyConsumer()
    monkeypatch.setattr(app_module, "consumer", dummy)
    return dummy


@pytest_asyncio.fixture(autouse=True)
async def reset_aggregator():
    await aggregator.reset()
    yield
    await aggregator.reset()


@pytest_asyncio.fixture
async def async_client(patch_consumer):
    await app.router.startup()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await app.router.shutdown()
