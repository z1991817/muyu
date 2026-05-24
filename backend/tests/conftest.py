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

    async def fetch_cn_market(self) -> object:
        from app.models.cn_market import (
            CnFundFlow,
            CnLimitStock,
            CnMarketAnalysis,
            CnMarketIndex,
            CnMarketResponse,
            CnMarketStock,
        )

        now = _now_iso()
        return CnMarketResponse(
            indices=[
                CnMarketIndex(
                    symbol="000001",
                    name="上证指数",
                    price=3120.5,
                    change=12.3,
                    change_pct=0.39,
                    url="https://quote.eastmoney.com/000001.html",
                    updated_at=now,
                    disclaimer="仅供信息展示，不构成投资建议",
                )
            ],
            stocks=[
                CnMarketStock(
                    symbol="600519",
                    name="贵州茅台",
                    price=1688.0,
                    change=12.5,
                    change_pct=0.75,
                    volume="12.3万",
                    turnover="20.8亿",
                    url="https://quote.eastmoney.com/600519.html",
                    updated_at=now,
                    disclaimer="仅供信息展示，不构成投资建议",
                )
            ],
            analysis=CnMarketAnalysis(
                fund_flows=[
                    CnFundFlow(name="沪深两市", value="128.6亿", change_pct=0.42, direction="in")
                ],
                limit_up=[
                    CnLimitStock(
                        symbol="000001",
                        name="平安银行",
                        price=12.8,
                        change_pct=10.0,
                        reason="金融活跃",
                        url="https://quote.eastmoney.com/000001.html",
                    )
                ],
                limit_down=[],
            ),
            stale=False,
            updated_at=now,
        )

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
                url="https://stock.finance.sina.com.cn/usstock/quotes/.INX.html",
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
                url="https://stock.finance.sina.com.cn/usstock/quotes/.IXIC.html",
                market_status="closed",
                trade_date="2026-05-19",
                updated_at=now,
                disclaimer="仅供信息展示，不构成投资建议",
            ),
        ]


class FakeUmamiClient:
    async def fetch_active_visitors(self) -> int:
        return 12

    async def aclose(self) -> None:
        return None


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
    app.state.umami_client = FakeUmamiClient()
    app.state.default_platforms = list(PLATFORMS.keys())

    yield app


@pytest_asyncio.fixture
async def client(test_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client
