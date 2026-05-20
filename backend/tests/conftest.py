from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest_asyncio
from fastapi import FastAPI


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class FakeSeeSeaClient:
    async def fetch_multiple(self, platforms: list[str]) -> list[object]:
        from app.models.trend import Trend
        from app.platforms import PLATFORMS

        now = _now_iso()
        return [
            Trend(
                platform=platform,
                platform_name=PLATFORMS.get(platform, PLATFORMS["weibo"]).platform_name,
                title=f"{platform} 热点测试",
                url=f"https://example.com/{platform}",
                rank=1,
                heat="1000",
                source=platform,
                updated_at=now,
            )
            for platform in platforms
        ]

    async def fetch_single(self, platform: str) -> list[object]:
        return await self.fetch_multiple([platform])

    async def fetch_platforms(self) -> list[object]:
        from app.models.source import Source
        from app.platforms import PLATFORMS

        now = _now_iso()
        return [
            Source(
                platform=meta.platform,
                platform_name=meta.platform_name,
                status="ok",
                updated_at=now,
            )
            for meta in PLATFORMS.values()
        ]

    async def aclose(self) -> None:
        return None


class FakeAkShareClient:
    async def fetch_us_indices(self) -> list[object]:
        from app.models.market import MarketIndex

        now = _now_iso()
        return [
            MarketIndex(
                symbol="SPX",
                name="S&P 500",
                price=5000.0,
                change=10.2,
                change_pct=0.2,
                url="https://finance.yahoo.com/quote/%5EGSPC",
                market_status="closed",
                trade_date="2026-05-19",
                updated_at=now,
                disclaimer="仅供信息展示，不构成投资建议",
            ),
            MarketIndex(
                symbol="IXIC",
                name="Nasdaq Composite",
                price=17000.0,
                change=-20.3,
                change_pct=-0.12,
                url="https://finance.yahoo.com/quote/%5EIXIC",
                market_status="closed",
                trade_date="2026-05-19",
                updated_at=now,
                disclaimer="仅供信息展示，不构成投资建议",
            ),
        ]


@pytest_asyncio.fixture
async def test_app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    import sys

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from app.cache.sqlite import SQLiteCache
    from app.main import app
    from app.platforms import PLATFORMS

    cache = SQLiteCache((tmp_path / "cache.db").as_posix())
    await cache.init()

    app.state.cache = cache
    app.state.seesea_client = FakeSeeSeaClient()
    app.state.akshare_client = FakeAkShareClient()
    app.state.default_platforms = list(PLATFORMS.keys())

    yield app


@pytest_asyncio.fixture
async def client(test_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client
