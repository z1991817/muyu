from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest_asyncio
from fastapi import FastAPI


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _fake_cn_market_response() -> object:
    from app.models.cn_market import (
        CnActiveStock,
        CnFundFlow,
        CnMarketAnalysis,
        CnMarketBreadth,
        CnMarketIndex,
        CnMarketResponse,
        CnMarketStock,
        CnRangeStock,
        CnSectorTrend,
    )

    now = _now_iso()
    breadth = [
        CnMarketBreadth(name="上涨家数", value="600", change_pct=50.0, direction="in"),
        CnMarketBreadth(name="下跌家数", value="500", change_pct=41.67, direction="out"),
        CnMarketBreadth(name="平盘家数", value="100", change_pct=8.33, direction="flat"),
    ]
    stocks = [
        CnMarketStock(
            symbol=f"6005{index:02d}",
            name=f"测试股票{index}",
            price=10.0 + index,
            change=0.5 if index % 2 == 0 else -0.2,
            change_pct=1.2 if index % 2 == 0 else -0.8,
            volume="123456",
            turnover="208000000",
            url=f"https://finance.sina.com.cn/realstock/company/sh6005{index:02d}/nc.shtml",
            updated_at=now,
            disclaimer="仅供信息展示，不构成投资建议",
        )
        for index in range(10)
    ]
    return CnMarketResponse(
        indices=[
            CnMarketIndex(
                symbol="000001",
                name="上证指数",
                price=3120.5,
                change=12.3,
                change_pct=0.39,
                url="https://finance.sina.com.cn/realstock/company/sh000001/nc.shtml",
                updated_at=now,
                disclaimer="仅供信息展示，不构成投资建议",
            ),
            CnMarketIndex(
                symbol="000300",
                name="沪深300",
                price=3900.0,
                change=18.0,
                change_pct=0.46,
                url="https://finance.sina.com.cn/realstock/company/sh000300/nc.shtml",
                updated_at=now,
                disclaimer="仅供信息展示，不构成投资建议",
            ),
            CnMarketIndex(
                symbol="000905",
                name="中证500",
                price=5800.0,
                change=-10.0,
                change_pct=-0.17,
                url="https://finance.sina.com.cn/realstock/company/sh000905/nc.shtml",
                updated_at=now,
                disclaimer="仅供信息展示，不构成投资建议",
            ),
        ],
        stocks=stocks,
        analysis=CnMarketAnalysis(
            market_breadth=breadth,
            fund_flows=[
                CnFundFlow(
                    name=item.name,
                    value=item.value,
                    change_pct=item.change_pct,
                    direction=item.direction,
                )
                for item in breadth
            ],
            limit_up=[],
            limit_down=[],
            top_gainers=[
                CnRangeStock(
                    symbol="600500",
                    name="测试股票0",
                    price=10.0,
                    change_pct=1.2,
                    reason="涨幅靠前",
                    url="https://finance.sina.com.cn/realstock/company/sh600500/nc.shtml",
                )
            ],
            top_losers=[
                CnRangeStock(
                    symbol="600501",
                    name="测试股票1",
                    price=11.0,
                    change_pct=-0.8,
                    reason="跌幅靠前",
                    url="https://finance.sina.com.cn/realstock/company/sh600501/nc.shtml",
                )
            ],
            active_stocks=[
                CnActiveStock(
                    symbol="600501",
                    name="测试股票1",
                    price=11.0,
                    change_pct=1.2,
                    volume="123456",
                    turnover="208000000",
                    reason="成交额活跃",
                    url="https://finance.sina.com.cn/realstock/company/sh600501/nc.shtml",
                )
            ],
            sector_trends=[
                CnSectorTrend(
                    name="测试行业",
                    change_pct=2.3,
                    leading_symbol="600501",
                    leading_name="测试股票1",
                    leading_change_pct=1.2,
                    url="https://vip.stock.finance.sina.com.cn/mkt/#new_ljhy",
                )
            ],
        ),
        source="opentdx",
        data_date="2026-05-29",
        market_status="trading",
        stale=False,
        stale_reason=None,
        updated_at=now,
    )


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


class FakeCnMarketClient:
    async def fetch_cn_market(self) -> object:
        return _fake_cn_market_response()

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


class FakeAiNewsFetcher:
    async def fetch_date(self, date: str) -> list[dict[str, object]]:
        return [
            {
                "category": "产品与功能更新",
                "category_key": "product",
                "items": [
                    {
                        "title": "正式发布 stable audio 3 权重。",
                        "summary": "该系列模型已上线最新音频权重合集。",
                        "url": "https://huggingface.co/collections/stabilityai/stable-audio-3",
                        "source": "最新音频权重合集",
                    }
                ],
            }
        ]

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
    app.state.cn_market_client = FakeCnMarketClient()
    app.state.umami_client = FakeUmamiClient()
    app.state.ai_news_fetcher = FakeAiNewsFetcher()
    app.state.default_platforms = list(PLATFORMS.keys())

    yield app


@pytest_asyncio.fixture
async def client(test_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client
