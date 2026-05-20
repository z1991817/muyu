from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_home_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/home")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert payload["calendar"]["date"]
    assert isinstance(payload["calendar"]["isRestDay"], bool)
    assert payload["calendar"]["kind"] in {"holiday", "weekend", "workday"}
    assert len(payload["trends"]) > 0
    assert len(payload["sources"]) > 0
    assert len(payload["markets"]) > 0
    assert payload["markets"][0]["disclaimer"] == "仅供信息展示，不构成投资建议"


@pytest.mark.asyncio
async def test_home_uses_fresh_cache(client: AsyncClient, test_app) -> None:
    response = await client.get("/api/home")
    assert response.status_code == 200

    class FailSeeSeaClient:
        async def fetch_multiple(self, platforms: list[str]) -> list[object]:
            raise AssertionError("fresh home cache should avoid SeeSea")

        async def fetch_platforms(self) -> list[object]:
            raise AssertionError("fresh home cache should avoid SeeSea")

    class FailAkShareClient:
        async def fetch_us_indices(self) -> list[object]:
            raise AssertionError("fresh home cache should avoid AkShare")

    test_app.state.seesea_client = FailSeeSeaClient()
    test_app.state.akshare_client = FailAkShareClient()

    cached_response = await client.get("/api/home")
    assert cached_response.status_code == 200
    assert cached_response.json()["stale"] is False


@pytest.mark.asyncio
async def test_trends_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/trends")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert len(payload["items"]) > 0
    assert payload["items"][0]["platform"]
    assert payload["items"][0]["platformName"]
    assert payload["items"][0]["updatedAt"]


@pytest.mark.asyncio
async def test_sources_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/sources")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert len(payload["items"]) > 0
    assert payload["items"][0]["platform"]
    assert payload["items"][0]["platformName"]
    assert payload["items"][0]["updatedAt"]


@pytest.mark.asyncio
async def test_market_us_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/market/us")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert len(payload["items"]) > 0
    assert payload["items"][0]["symbol"]
    assert payload["items"][0]["disclaimer"] == "仅供信息展示，不构成投资建议"


@pytest.mark.asyncio
async def test_market_us_has_items_when_upstream_fails(client: AsyncClient, test_app) -> None:
    from app.clients.akshare import AkShareError

    class FailAkShareClient:
        async def fetch_us_indices(self) -> list[object]:
            raise AkShareError("AKSHARE_UPSTREAM", "mock fail")

    test_app.state.akshare_client = FailAkShareClient()

    response = await client.get("/api/market/us")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is True
    assert payload["items"] == []


@pytest.mark.asyncio
async def test_akshare_client_fallback_returns_items() -> None:
    from app.clients.akshare import AkShareClient

    client = AkShareClient()
    items = client._fallback_indices(status="closed")

    assert len(items) == 5
    assert items[0].symbol
    assert items[0].disclaimer == "仅供信息展示，不构成投资建议"


@pytest.mark.asyncio
async def test_akshare_client_fetch_returns_fallback_when_api_unavailable() -> None:
    from app.clients.akshare import AkShareClient

    client = AkShareClient()
    items = await client.fetch_us_indices()

    assert len(items) == 5
    assert {item.symbol for item in items} >= {"SPX", "DJI", "IXIC"}
