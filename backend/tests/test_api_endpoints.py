from __future__ import annotations

from typing import NoReturn

import httpx
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
    assert payload["items"][0]["url"].startswith(
        "https://stock.finance.sina.com.cn/usstock/quotes/"
    )
    assert payload["items"][0]["disclaimer"] == "仅供信息展示，不构成投资建议"


@pytest.mark.asyncio
async def test_market_cn_happy_path(client: AsyncClient, test_app) -> None:
    from app.scheduler import _refresh_cn_market

    await _refresh_cn_market(test_app.state.seesea_client, test_app.state.cache)

    response = await client.get("/api/market/cn")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["stocks"][0]["symbol"] == "600519"
    assert payload["analysis"]["fundFlows"][0]["name"] == "沪深两市"
    assert payload["analysis"]["limitUp"][0]["reason"] == "金融活跃"


@pytest.mark.asyncio
async def test_scheduler_refreshes_cn_market_with_stock_sdk_fallback(
    client: AsyncClient, test_app
) -> None:
    from app.clients.seesea import SeeSeaClient
    from app.scheduler import _refresh_cn_market

    class EmptyLiveTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[], request=request)

    class Result:
        def __init__(self, data: object) -> None:
            self.success = True
            self.data = data

    class RecentTradeStockClient:
        def get_index_list(self) -> Result:
            return Result(
                [
                    {
                        "代码": "000001",
                        "名称": "上证指数",
                        "最新价": 3120.5,
                        "涨跌额": 12.3,
                        "涨跌幅": 0.39,
                    }
                ]
            )

        def get_quotes(self, market: str = "a") -> Result:
            return Result([])

        def get_kline(
            self,
            symbol: str,
            period: str = "daily",
            start_date: str | None = None,
            end_date: str | None = None,
            adjust: str = "qfq",
        ) -> Result:
            return Result(
                [
                    {
                        "日期": start_date,
                        "收盘": 1688.0,
                        "涨跌额": 12.5,
                        "涨跌幅": 0.75,
                        "成交量": "12.3万",
                        "成交额": "20.8亿",
                    }
                ]
            )

        def get_market_fund_flow(self) -> Result:
            return Result([])

        def get_zt_pool(self, date: str | None = None) -> Result:
            return Result(
                [
                    {
                        "代码": "000001",
                        "名称": "平安银行",
                        "最新价": 12.8,
                        "涨跌幅": 10.0,
                        "涨停原因": "金融活跃",
                    }
                ]
            )

        def get_dt_pool(self, date: str | None = None) -> Result:
            return Result([])

    seesea = SeeSeaClient(base_url="http://test-seesea", enable_stock_sdk_fallback=True)
    await seesea._client.aclose()
    seesea._client = httpx.AsyncClient(
        base_url="http://test-seesea",
        transport=EmptyLiveTransport(),
    )
    seesea._stock_sdk_client = RecentTradeStockClient()
    test_app.state.seesea_client = seesea

    await _refresh_cn_market(seesea, test_app.state.cache)
    response = await client.get("/api/market/cn")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["stocks"][0]["symbol"] == "600519"
    assert payload["stocks"][0]["price"] == 1688.0
    assert payload["analysis"]["limitUp"][0]["reason"] == "金融活跃"

    await seesea.aclose()


@pytest.mark.asyncio
async def test_market_cn_stock_sdk_fallback_is_disabled_by_default() -> None:
    from app.clients.seesea import SeeSeaClient, SeeSeaError

    class EmptyLiveTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[], request=request)

    class FailIfCalledStockClient:
        def get_index_list(self) -> object:
            raise AssertionError("stock SDK fallback should be opt-in")

    seesea = SeeSeaClient(base_url="http://test-seesea")
    await seesea._client.aclose()
    seesea._client = httpx.AsyncClient(
        base_url="http://test-seesea",
        transport=EmptyLiveTransport(),
    )
    seesea._stock_sdk_client = FailIfCalledStockClient()

    with pytest.raises(SeeSeaError):
        await seesea.fetch_cn_market()

    await seesea.aclose()


@pytest.mark.asyncio
async def test_hot_sdk_fallback_is_disabled_by_default() -> None:
    from app.clients.seesea import SeeSeaClient, SeeSeaError

    class FailingHotTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"error": "unavailable"}, request=request)

    class FailIfCalledHotClient:
        def fetch_multiple_platforms(self, platforms: list[str]) -> object:
            raise AssertionError("hot SDK fallback should be opt-in")

    seesea = SeeSeaClient(base_url="http://test-seesea")
    await seesea._client.aclose()
    seesea._client = httpx.AsyncClient(
        base_url="http://test-seesea",
        transport=FailingHotTransport(),
    )
    seesea._sdk_client = FailIfCalledHotClient()

    with pytest.raises(SeeSeaError):
        await seesea.fetch_multiple(["weibo"])

    await seesea.aclose()


@pytest.mark.asyncio
async def test_market_cn_reads_expired_cache_as_stale(client: AsyncClient, test_app) -> None:
    import sqlite3
    from datetime import UTC, datetime, timedelta

    from app.cache.policy import market_ttl_seconds
    from app.models.cn_market import CnMarketAnalysis, CnMarketResponse

    cached_payload = CnMarketResponse(
        indices=[],
        stocks=[],
        analysis=CnMarketAnalysis(fund_flows=[], limit_up=[], limit_down=[]),
        stale=False,
        updated_at="2026-05-24T00:00:00+00:00",
    )
    await test_app.state.cache.set(
        "market:cn",
        cached_payload.model_dump(mode="json"),
        ttl_seconds=market_ttl_seconds("open"),
        source_status="ok",
    )
    conn = sqlite3.connect(test_app.state.cache._db_path.as_posix())
    conn.execute(
        "UPDATE cache_entries SET expires_at = ? WHERE key = ?",
        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), "market:cn"),
    )
    conn.commit()
    conn.close()

    class FailIfCalledSeeSeaClient:
        async def fetch_cn_market(self) -> object:
            raise AssertionError("market cn route should only read cache")

        async def fetch_cn_market_recent_trade_snapshot(self) -> object:
            raise AssertionError("market cn route should only read cache")

        async def aclose(self) -> None:
            return None

    test_app.state.seesea_client = FailIfCalledSeeSeaClient()

    response = await client.get("/api/market/cn")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale"] is True
    assert payload["updatedAt"] == "2026-05-24T00:00:00+00:00"
    assert payload["indices"] == []
    assert payload["stocks"] == []


@pytest.mark.asyncio
async def test_market_cn_returns_empty_stale_payload_without_cache(
    client: AsyncClient, test_app
) -> None:
    class FailIfCalledSeeSeaClient:
        async def fetch_cn_market(self) -> object:
            raise AssertionError("market cn route should only read cache")

        async def fetch_cn_market_recent_trade_snapshot(self) -> object:
            raise AssertionError("market cn route should only read cache")

        async def aclose(self) -> None:
            return None

    test_app.state.seesea_client = FailIfCalledSeeSeaClient()

    response = await client.get("/api/market/cn")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale"] is True
    assert payload["indices"] == []
    assert payload["stocks"] == []
    assert payload["analysis"]["fundFlows"] == []
    assert payload["analysis"]["limitUp"] == []
    assert payload["analysis"]["limitDown"] == []


@pytest.mark.asyncio
async def test_scheduler_falls_back_to_recent_trade_snapshot(client: AsyncClient, test_app) -> None:
    from app.clients.seesea import SeeSeaError
    from app.models.cn_market import (
        CnMarketAnalysis,
        CnMarketIndex,
        CnMarketResponse,
        CnMarketStock,
    )
    from app.scheduler import _refresh_cn_market

    class SnapshotSeeSeaClient:
        async def fetch_cn_market(self) -> NoReturn:
            raise SeeSeaError("SEESEA_UPSTREAM", "mock fail")

        async def fetch_cn_market_recent_trade_snapshot(self) -> CnMarketResponse:
            return CnMarketResponse(
                indices=[
                    CnMarketIndex(
                        symbol="000001",
                        name="上证指数",
                        price=3120.5,
                        change=12.3,
                        change_pct=0.39,
                        url="https://quote.eastmoney.com/000001.html",
                        updated_at="2026-05-24T00:00:00+00:00",
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
                        updated_at="2026-05-24T00:00:00+00:00",
                        disclaimer="仅供信息展示，不构成投资建议",
                    )
                ],
                analysis=CnMarketAnalysis(fund_flows=[], limit_up=[], limit_down=[]),
                stale=True,
                updated_at="2026-05-24T00:00:00+00:00",
            )

        async def aclose(self) -> None:
            return None

    test_app.state.seesea_client = SnapshotSeeSeaClient()
    await _refresh_cn_market(test_app.state.seesea_client, test_app.state.cache)
    response = await client.get("/api/market/cn")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale"] is True
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["stocks"][0]["symbol"] == "600519"


@pytest.mark.asyncio
async def test_online_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/online")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert payload["visitors"] == 12


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
async def test_market_us_does_not_cache_zero_fallback(client: AsyncClient, test_app) -> None:
    from app.models.market import MarketIndex

    class ZeroFallbackAkShareClient:
        async def fetch_us_indices(self) -> list[object]:
            return [
                MarketIndex(
                    symbol="SPX",
                    name="S&P 500",
                    price=0.0,
                    change=0.0,
                    change_pct=0.0,
                    url="https://stock.finance.sina.com.cn/usstock/quotes/.INX.html",
                    market_status="closed",
                    trade_date="2026-05-24",
                    updated_at="2026-05-24T00:00:00+00:00",
                    disclaimer="仅供信息展示，不构成投资建议",
                )
            ]

    test_app.state.akshare_client = ZeroFallbackAkShareClient()

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
    assert all(
        item.url.startswith("https://stock.finance.sina.com.cn/usstock/quotes/") for item in items
    )
    assert items[0].disclaimer == "仅供信息展示，不构成投资建议"


@pytest.mark.asyncio
async def test_akshare_client_parses_us_indices_payload() -> None:
    from app.clients.akshare import _parse_sina

    payload = (
        'var hq_str_gb_$inx="标普500指数,7473.4702,0.37,2026-05-23 04:45:23,'
        '27.7500";\n'
        'var hq_str_gb_$dji="道琼斯,50579.6992,0.58,2026-05-23 04:45:23,'
        '294.0400";\n'
        'var hq_str_gb_$ixic="纳斯达克,26343.9700,0.19,2026-05-23 04:45:23,'
        '50.8700";'
    )
    items = _parse_sina(payload, "closed")

    assert len(items) == 3
    assert [(item.symbol, item.price) for item in items] == [
        ("SPX", 7473.47),
        ("DJI", 50579.7),
        ("IXIC", 26343.97),
    ]
