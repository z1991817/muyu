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

    await _refresh_cn_market(test_app.state.cn_market_client, test_app.state.cache)

    response = await client.get("/api/market/cn")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["stocks"][0]["symbol"] == "600519"
    assert payload["analysis"]["fundFlows"][0]["name"] == "上涨家数"
    assert payload["analysis"]["limitUp"][0]["reason"] == "金融活跃"


@pytest.mark.asyncio
async def test_cn_market_client_parses_primary_sources() -> None:
    from app.clients.cn_market import CnMarketClient

    def tencent_quote(symbol: str, name: str, price: str, change: str, pct: str) -> str:
        fields = ["0"] * 33
        fields[1] = name
        fields[2] = symbol
        fields[3] = price
        fields[31] = change
        fields[32] = pct
        return f'v_sh{symbol}="' + "~".join(fields) + '";'

    class MarketTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            if request.url.host == "qt.gtimg.cn":
                return httpx.Response(
                    200,
                    text=(
                        tencent_quote("000001", "上证指数", "4145.37", "-7.20", "-0.17")
                        + tencent_quote("000300", "沪深300", "4947.85", "26.25", "0.53")
                        + tencent_quote("000905", "中证500", "8600.00", "10.00", "0.12")
                    ),
                    request=request,
                )
            if request.url.host == "push2his.eastmoney.com":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "klines": [
                                (
                                    "2026-05-26,100.0,-20.0,30.0,40.0,60.0,"
                                    "1.2,-0.2,0.3,0.4,0.6,4145.37,-0.17,12000,0.12"
                                )
                            ]
                        }
                    },
                    request=request,
                )
            return httpx.Response(404, request=request)

    async def fake_run_akshare(self: object, method: str, *args: object) -> object:
        if method == "stock_zh_a_spot":
            return [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": 1688.0,
                    "涨跌额": 12.5,
                    "涨跌幅": 0.75,
                    "成交量": "12.3万",
                    "成交额": "20.8亿",
                }
            ]
        if method == "stock_hot_follow_xq":
            return [
                {
                    "股票代码": "SH600519",
                    "股票简称": "贵州茅台",
                    "关注": 3635107,
                    "最新价": 1688.0,
                }
            ]
        if method == "stock_zt_pool_em":
            return [
                {
                    "代码": "000001",
                    "名称": "平安银行",
                    "最新价": 12.8,
                    "涨跌幅": 10.0,
                    "所属行业": "银行",
                    "连板数": 1,
                }
            ]
        return []

    client = CnMarketClient()
    await client._http.aclose()
    client._http = httpx.AsyncClient(transport=MarketTransport())
    client._run_akshare = fake_run_akshare.__get__(client, CnMarketClient)
    try:
        response = await client.fetch_cn_market()
    finally:
        await client.aclose()

    assert response.stale is False
    assert response.indices[0].name == "上证指数"
    assert response.indices[0].price == 4145.37
    assert response.stocks[0].symbol == "600519"
    assert response.stocks[0].turnover == "20.8亿"
    assert response.analysis.fund_flows[0].name == "上涨家数"
    assert response.analysis.fund_flows[0].direction == "in"
    assert response.analysis.limit_up[0].reason == "银行 · 1连板"


@pytest.mark.asyncio
async def test_cn_market_client_uses_hot_follow_rank_for_stock_order() -> None:
    from app.clients.cn_market import CnMarketClient

    class MarketTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            if request.url.host == "qt.gtimg.cn":
                fields = ["0"] * 33
                fields[1] = "上证指数"
                fields[2] = "000001"
                fields[3] = "4145.37"
                fields[31] = "-7.20"
                fields[32] = "-0.17"
                return httpx.Response(
                    200,
                    text='v_sh000001="' + "~".join(fields) + '";',
                    request=request,
                )
            return httpx.Response(404, request=request)

    async def fake_run_akshare(self: object, method: str, *args: object) -> object:
        if method == "stock_zh_a_spot":
            return [
                {
                    "代码": "SH600519",
                    "名称": "贵州茅台",
                    "最新价": 1688.0,
                    "涨跌额": 12.5,
                    "涨跌幅": 0.75,
                    "成交量": "12.3万",
                    "成交额": "20.8亿",
                },
                {
                    "代码": "SZ002594",
                    "名称": "比亚迪",
                    "最新价": 96.55,
                    "涨跌额": -1.5,
                    "涨跌幅": -1.53,
                    "成交量": "98.2万",
                    "成交额": "95.1亿",
                },
            ]
        if method == "stock_hot_follow_xq":
            return [
                {"股票代码": "SZ002594", "股票简称": "比亚迪", "关注": 2344997, "最新价": 96.55},
                {"股票代码": "SH600519", "股票简称": "贵州茅台", "关注": 3635107, "最新价": 1688.0},
            ]
        return []

    client = CnMarketClient()
    await client._http.aclose()
    client._http = httpx.AsyncClient(transport=MarketTransport())
    client._run_akshare = fake_run_akshare.__get__(client, CnMarketClient)
    try:
        response = await client.fetch_cn_market()
    finally:
        await client.aclose()

    assert [item.symbol for item in response.stocks[:2]] == ["002594", "600519"]
    assert response.stocks[0].turnover == "95.1亿"
    assert response.stocks[0].volume == "98.2万"


@pytest.mark.asyncio
async def test_cn_market_refresh_does_not_restore_legacy_fund_flow(
    client: AsyncClient, test_app
) -> None:
    from app.models.cn_market import (
        CnFundFlow,
        CnLimitStock,
        CnMarketAnalysis,
        CnMarketIndex,
        CnMarketResponse,
        CnMarketStock,
    )
    from app.scheduler import _refresh_cn_market

    cached = CnMarketResponse(
        indices=[],
        stocks=[],
        analysis=CnMarketAnalysis(
            fund_flows=[
                CnFundFlow(name="主力资金", value="-100.0", change_pct=-1.2, direction="out")
            ],
            limit_up=[],
            limit_down=[],
        ),
        stale=False,
        updated_at="2026-05-26T00:00:00+00:00",
    )
    await test_app.state.cache.set(
        "market:cn",
        cached.model_dump(mode="json"),
        ttl_seconds=60,
        source_status="ok",
    )

    class EmptyFundFlowCnMarketClient:
        async def fetch_cn_market(self) -> CnMarketResponse:
            return CnMarketResponse(
                indices=[
                    CnMarketIndex(
                        symbol="000001",
                        name="上证指数",
                        price=4145.37,
                        change=-7.2,
                        change_pct=-0.17,
                        url="https://quote.eastmoney.com/000001.html",
                        updated_at="2026-05-26T11:00:00+00:00",
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
                        updated_at="2026-05-26T11:00:00+00:00",
                        disclaimer="仅供信息展示，不构成投资建议",
                    )
                ],
                analysis=CnMarketAnalysis(
                    fund_flows=[],
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
                updated_at="2026-05-26T11:00:00+00:00",
            )

        async def fetch_cn_market_recent_trade_snapshot(self) -> CnMarketResponse:
            return await self.fetch_cn_market()

    await _refresh_cn_market(EmptyFundFlowCnMarketClient(), test_app.state.cache)
    response = await client.get("/api/market/cn")
    payload = response.json()

    assert payload["stale"] is False
    assert payload["indices"][0]["price"] == 4145.37
    assert payload["analysis"]["fundFlows"] == []


@pytest.mark.asyncio
async def test_cn_market_refresh_keeps_cached_stock_metrics_when_new_stocks_incomplete(
    client: AsyncClient, test_app
) -> None:
    from app.models.cn_market import (
        CnLimitStock,
        CnMarketAnalysis,
        CnMarketIndex,
        CnMarketResponse,
        CnMarketStock,
    )
    from app.scheduler import _refresh_cn_market

    cached = CnMarketResponse(
        indices=[],
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
                updated_at="2026-05-26T10:00:00+00:00",
                disclaimer="仅供信息展示，不构成投资建议",
            )
        ],
        analysis=CnMarketAnalysis(fund_flows=[], limit_up=[], limit_down=[]),
        stale=False,
        updated_at="2026-05-26T10:00:00+00:00",
    )
    await test_app.state.cache.set(
        "market:cn",
        cached.model_dump(mode="json"),
        ttl_seconds=60,
        source_status="ok",
    )

    class IncompleteStocksCnMarketClient:
        async def fetch_cn_market(self) -> CnMarketResponse:
            return CnMarketResponse(
                indices=[
                    CnMarketIndex(
                        symbol="000001",
                        name="上证指数",
                        price=4145.37,
                        change=-7.2,
                        change_pct=-0.17,
                        url="https://quote.eastmoney.com/000001.html",
                        updated_at="2026-05-26T11:00:00+00:00",
                        disclaimer="仅供信息展示，不构成投资建议",
                    )
                ],
                stocks=[
                    CnMarketStock(
                        symbol="920575",
                        name="*ST康乐",
                        price=4.26,
                        change=0,
                        change_pct=21.714,
                        volume="-",
                        turnover="-",
                        url="https://quote.eastmoney.com/bj/920575.html",
                        updated_at="2026-05-26T11:00:00+00:00",
                        disclaimer="仅供信息展示，不构成投资建议",
                    )
                ],
                analysis=CnMarketAnalysis(
                    fund_flows=[],
                    limit_up=[
                        CnLimitStock(
                            symbol="920575",
                            name="*ST康乐",
                            price=4.26,
                            change_pct=21.714,
                            reason="市场异动",
                            url="https://quote.eastmoney.com/bj/920575.html",
                        )
                    ],
                    limit_down=[],
                ),
                stale=False,
                updated_at="2026-05-26T11:00:00+00:00",
            )

        async def fetch_cn_market_recent_trade_snapshot(self) -> CnMarketResponse:
            return await self.fetch_cn_market()

    await _refresh_cn_market(IncompleteStocksCnMarketClient(), test_app.state.cache)
    response = await client.get("/api/market/cn")
    payload = response.json()

    assert payload["stale"] is True
    assert payload["stocks"][0]["symbol"] == "600519"
    assert payload["stocks"][0]["volume"] == "12.3万"
    assert payload["stocks"][0]["turnover"] == "20.8亿"


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
            return Result(
                [
                    {
                        "日期": "2026-05-22",
                        "主力净流入-净额": -59244441600.0,
                        "主力净流入-净占比": -3.47,
                        "超大单净流入-净额": -28084895744.0,
                        "超大单净流入-净占比": -1.64,
                        "大单净流入-净额": -31159545856.0,
                        "大单净流入-净占比": -1.82,
                        "中单净流入-净额": 5589135360.0,
                        "中单净流入-净占比": 0.33,
                        "小单净流入-净额": 53655302144.0,
                        "小单净流入-净占比": 3.14,
                    }
                ]
            )

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
    assert len(payload["stocks"]) == 20
    assert payload["stocks"][0]["symbol"] == "600519"
    assert payload["stocks"][0]["price"] == 1688.0
    assert payload["analysis"]["fundFlows"][0]["name"] == "主力资金"
    assert payload["analysis"]["fundFlows"][0]["direction"] == "out"
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
async def test_market_cn_maps_north_exchange_urls(client: AsyncClient, test_app) -> None:
    from app.models.cn_market import CnMarketResponse
    from app.scheduler import _refresh_cn_market

    class NorthExchangeCnMarketClient:
        async def fetch_cn_market(self) -> CnMarketResponse:
            from app.models.cn_market import (
                CnLimitStock,
                CnMarketAnalysis,
                CnMarketIndex,
                CnMarketResponse,
                CnMarketStock,
            )

            return CnMarketResponse(
                indices=[
                    CnMarketIndex(
                        symbol="000001",
                        name="上证指数",
                        price=3120.5,
                        change=12.3,
                        change_pct=0.39,
                        url="https://quote.eastmoney.com/000001.html",
                        updated_at="2026-05-26T00:00:00+00:00",
                        disclaimer="仅供信息展示，不构成投资建议",
                    )
                ],
                stocks=[
                    CnMarketStock(
                        symbol="920575",
                        name="*ST康乐",
                        price=4.26,
                        change=0,
                        change_pct=21.714,
                        volume="-",
                        turnover="-",
                        url="https://quote.eastmoney.com/bj/920575.html",
                        updated_at="2026-05-26T00:00:00+00:00",
                        disclaimer="仅供信息展示，不构成投资建议",
                    )
                ],
                analysis=CnMarketAnalysis(
                    fund_flows=[],
                    limit_up=[
                        CnLimitStock(
                            symbol="920575",
                            name="*ST康乐",
                            price=4.26,
                            change_pct=21.714,
                            reason="市场异动",
                            url="https://quote.eastmoney.com/bj/920575.html",
                        )
                    ],
                    limit_down=[],
                ),
                stale=False,
                updated_at="2026-05-26T00:00:00+00:00",
            )

        async def fetch_cn_market_recent_trade_snapshot(self) -> CnMarketResponse:
            return await self.fetch_cn_market()

    await _refresh_cn_market(NorthExchangeCnMarketClient(), test_app.state.cache)
    response = await client.get("/api/market/cn")
    assert response.status_code == 200

    payload = response.json()
    north_stock = next(item for item in payload["stocks"] if item["symbol"] == "920575")
    assert north_stock["url"] == "https://quote.eastmoney.com/bj/920575.html"
    assert payload["analysis"]["limitUp"][0]["url"] == "https://quote.eastmoney.com/bj/920575.html"


@pytest.mark.asyncio
async def test_market_cn_limit_pools_use_akshare_fallback(
    client: AsyncClient, test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.clients.seesea import SeeSeaClient
    from app.scheduler import _refresh_cn_market

    class EmptyLiveTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[], request=request)

    class Result:
        def __init__(self, data: object, *, success: bool = True) -> None:
            self.success = success
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
            return Result(
                [
                    {
                        "日期": "2026-05-22",
                        "主力净流入-净额": 100.0,
                        "主力净流入-净占比": 1.2,
                    }
                ]
            )

        def get_zt_pool(self, date: str | None = None) -> Result:
            return Result([], success=False)

        def get_dt_pool(self, date: str | None = None) -> Result:
            return Result([], success=False)

    def fake_run_akshare_stock_sync(method: str, *args: object) -> object:
        if method == "stock_zt_pool_em":
            return [
                {
                    "代码": f"60{index:04d}",
                    "名称": f"涨停{index}",
                    "最新价": 10 + index,
                    "涨跌幅": 10.0,
                    "所属行业": "元件",
                    "连板数": 2,
                }
                for index in range(25)
            ]
        if method == "stock_zt_pool_dtgc_em":
            return [
                {
                    "代码": f"00{index:04d}",
                    "名称": f"跌停{index}",
                    "最新价": 8 + index,
                    "涨跌幅": -10.0,
                    "所属行业": "家居用品",
                    "连续跌停": 1,
                }
                for index in range(5)
            ]
        raise AssertionError(f"unexpected AkShare method: {method}")

    monkeypatch.setattr(
        "app.clients.seesea._run_akshare_stock_sync",
        fake_run_akshare_stock_sync,
    )

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
    assert len(payload["analysis"]["limitUp"]) == 20
    assert len(payload["analysis"]["limitDown"]) == 5
    assert payload["analysis"]["limitUp"][0]["reason"] == "元件 · 2连板"
    assert payload["analysis"]["limitDown"][0]["reason"] == "家居用品 · 1连跌"
    assert payload["analysis"]["limitDown"][0]["changePct"] == -10.0

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
async def test_market_cn_indices_use_akshare_fallback(
    client: AsyncClient, test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.clients.seesea import SeeSeaClient
    from app.scheduler import _refresh_cn_market

    class NotFoundTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "not found"}, request=request)

    class Result:
        def __init__(self, data: object, *, success: bool = True) -> None:
            self.success = success
            self.data = data

    class RecentTradeStockClient:
        def get_index_list(self) -> Result:
            return Result([], success=False)

        def get_kline(
            self,
            symbol: str,
            period: str = "daily",
            start_date: str | None = None,
            end_date: str | None = None,
            adjust: str = "qfq",
        ) -> Result:
            return Result([], success=False)

        def get_market_fund_flow(self) -> Result:
            return Result([])

        def get_zt_pool(self, date: str | None = None) -> Result:
            return Result([])

        def get_dt_pool(self, date: str | None = None) -> Result:
            return Result([])

    def fake_run_akshare_stock_sync(method: str, *args: object) -> object:
        if method == "stock_zh_index_spot_em":
            return [
                {
                    "代码": "sh000001",
                    "名称": "上证指数",
                    "最新价": 3120.5,
                    "涨跌额": 12.3,
                    "涨跌幅": 0.39,
                },
                {
                    "代码": "000300.SH",
                    "名称": "沪深300",
                    "最新价": 3888.8,
                    "涨跌额": -8.1,
                    "涨跌幅": -0.21,
                },
            ]
        if method == "stock_zh_a_spot":
            return [
                {
                    "代码": "sh600519",
                    "名称": "贵州茅台",
                    "最新价": 1688.0,
                    "涨跌额": 12.5,
                    "涨跌幅": 0.75,
                    "成交量": 123456,
                    "成交额": 208000000,
                },
                {
                    "代码": "sz300750",
                    "名称": "宁德时代",
                    "最新价": 380.2,
                    "涨跌额": -3.1,
                    "涨跌幅": -0.81,
                    "成交量": 234567,
                    "成交额": 91800000,
                },
            ]
        if method in {"stock_zt_pool_em", "stock_zt_pool_dtgc_em"}:
            return []
        raise AssertionError(f"unexpected AkShare method: {method}")

    monkeypatch.setattr(
        "app.clients.seesea._run_akshare_stock_sync",
        fake_run_akshare_stock_sync,
    )

    seesea = SeeSeaClient(base_url="http://test-seesea", enable_stock_sdk_fallback=True)
    await seesea._client.aclose()
    seesea._client = httpx.AsyncClient(
        base_url="http://test-seesea",
        transport=NotFoundTransport(),
    )
    seesea._stock_sdk_client = RecentTradeStockClient()
    test_app.state.seesea_client = seesea

    await _refresh_cn_market(seesea, test_app.state.cache)
    response = await client.get("/api/market/cn")
    assert response.status_code == 200

    payload = response.json()
    assert payload["indices"][0]["symbol"] == "000001"
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["indices"][1]["symbol"] == "000300"
    maotai = next(item for item in payload["stocks"] if item["symbol"] == "600519")
    assert maotai["volume"] == "123456"
    assert maotai["turnover"] == "208000000"

    await seesea.aclose()


@pytest.mark.asyncio
async def test_market_cn_indices_use_eastmoney_fallback_when_akshare_index_fails(
    client: AsyncClient, test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.clients.seesea import SeeSeaClient
    from app.scheduler import _refresh_cn_market

    class MarketTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            if request.url.host == "qt.gtimg.cn":
                return httpx.Response(
                    200,
                    text=(
                        'v_sh000001="1~上证指数~000001~4145.37~4152.57~4137.32'
                        "~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0"
                        '~~20260526161415~-7.20~-0.17";'
                        'v_sh000300="1~沪深300~000300~4947.85~4921.60~4900.12'
                        "~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0"
                        '~~20260526161403~26.25~0.53";'
                        'v_sh000905="1~中证500~000905~8658.62~8703.89~8665.44'
                        "~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0"
                        '~~20260526161409~-45.27~-0.52";'
                    ),
                    request=request,
                )
            if request.url.host == "push2.eastmoney.com":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "diff": [
                                {
                                    "f12": "000001",
                                    "f14": "上证指数",
                                    "f2": 4145.37,
                                    "f4": -7.2,
                                    "f3": -0.17,
                                },
                                {
                                    "f12": "000300",
                                    "f14": "沪深300",
                                    "f2": 4947.85,
                                    "f4": 26.25,
                                    "f3": 0.53,
                                },
                                {
                                    "f12": "000905",
                                    "f14": "中证500",
                                    "f2": 8658.62,
                                    "f4": -45.27,
                                    "f3": -0.52,
                                },
                            ]
                        }
                    },
                    request=request,
                )
            return httpx.Response(404, json={"error": "not found"}, request=request)

    class Result:
        def __init__(self, data: object, *, success: bool = True) -> None:
            self.success = success
            self.data = data

    class EmptyStockClient:
        def get_index_list(self) -> Result:
            return Result([], success=False)

        def get_kline(
            self,
            symbol: str,
            period: str = "daily",
            start_date: str | None = None,
            end_date: str | None = None,
            adjust: str = "qfq",
        ) -> Result:
            return Result([], success=False)

        def get_market_fund_flow(self) -> Result:
            return Result([])

        def get_zt_pool(self, date: str | None = None) -> Result:
            return Result([])

        def get_dt_pool(self, date: str | None = None) -> Result:
            return Result([])

    def fake_run_akshare_stock_sync(method: str, *args: object) -> object:
        if method == "stock_zh_index_spot_em":
            raise ConnectionError("remote closed")
        if method == "stock_zh_a_spot":
            return [
                {
                    "代码": "sh600519",
                    "名称": "贵州茅台",
                    "最新价": 1688.0,
                    "涨跌额": 12.5,
                    "涨跌幅": 0.75,
                    "成交量": 123456,
                    "成交额": 208000000,
                }
            ]
        if method in {"stock_zt_pool_em", "stock_zt_pool_dtgc_em"}:
            return []
        raise AssertionError(f"unexpected AkShare method: {method}")

    monkeypatch.setattr(
        "app.clients.seesea._run_akshare_stock_sync",
        fake_run_akshare_stock_sync,
    )

    seesea = SeeSeaClient(base_url="http://test-seesea", enable_stock_sdk_fallback=True)
    await seesea._client.aclose()
    seesea._client = httpx.AsyncClient(
        base_url="http://test-seesea",
        transport=MarketTransport(),
    )
    seesea._stock_sdk_client = EmptyStockClient()
    test_app.state.seesea_client = seesea

    await _refresh_cn_market(seesea, test_app.state.cache)
    response = await client.get("/api/market/cn")
    assert response.status_code == 200

    payload = response.json()
    assert payload["indices"][0]["symbol"] == "000001"
    assert payload["indices"][0]["price"] == 4145.37
    assert payload["indices"][1]["price"] == 4947.85
    assert payload["indices"][2]["price"] == 8658.62

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
async def test_refresh_all_skips_cn_market_by_default(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import scheduler
    from app.config import settings

    async def fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("cn market should be refreshed by the standalone job")

    monkeypatch.setattr(settings, "cn_market_scheduler_enabled", False)
    monkeypatch.setattr(scheduler, "_refresh_cn_market", fail_if_called)

    await scheduler._refresh_all(
        test_app.state.seesea_client,
        test_app.state.akshare_client,
        test_app.state.cn_market_client,
        test_app.state.cache,
        test_app.state.default_platforms,
    )

    assert await test_app.state.cache.get("market:cn") is None


def test_cn_market_refresh_interval_tracks_trading_hours() -> None:
    from datetime import UTC, datetime

    from app.scheduler import cn_market_refresh_interval_seconds

    assert cn_market_refresh_interval_seconds(datetime(2026, 5, 26, 2, 0, tzinfo=UTC)) == 180
    assert cn_market_refresh_interval_seconds(datetime(2026, 5, 26, 4, 0, tzinfo=UTC)) == 1800
    assert cn_market_refresh_interval_seconds(datetime(2026, 5, 26, 6, 0, tzinfo=UTC)) == 180
    assert cn_market_refresh_interval_seconds(datetime(2026, 5, 30, 2, 0, tzinfo=UTC)) == 1800


@pytest.mark.asyncio
async def test_cn_market_job_writes_cache(
    client: AsyncClient, test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.jobs import refresh_cn_market

    monkeypatch.setattr(
        refresh_cn_market.settings, "cache_db_path", test_app.state.cache._db_path.as_posix()
    )
    monkeypatch.setattr(
        "app.jobs.refresh_cn_market.CnMarketClient",
        lambda: test_app.state.cn_market_client,
    )

    exit_code = await refresh_cn_market.refresh_once()

    assert exit_code == 0
    response = await client.get("/api/market/cn")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale"] is False
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["stocks"][0]["symbol"] == "600519"
    assert payload["analysis"]["fundFlows"][0]["name"] == "上涨家数"


@pytest.mark.asyncio
async def test_online_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/online")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert payload["visitors"] == 12


@pytest.mark.asyncio
async def test_ai_news_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/ai-news?date=2026-05-27")
    assert response.status_code == 200

    payload = response.json()
    assert payload["date"] == "2026-05-27"
    assert payload["stale"] is False
    assert payload["groups"][0]["category"] == "产品与功能更新"
    assert payload["groups"][0]["categoryKey"] == "product"
    assert payload["groups"][0]["items"][0]["url"].startswith("https://huggingface.co/")


def test_ai_news_parser_reads_hex2077_daily_sections() -> None:
    from app.clients.ai_news_fetcher import parse_markdown

    markdown = "\n".join(
        [
            "## **今日摘要**",
            "```",
            "今天的摘要不应该作为资讯卡片展示。",
            "```",
            "### 产品与功能更新",
            (
                "1. **正式发布 stable audio 3 权重。** "
                "该系列模型已上线 [最新音频权重合集(ai资讯)]"
                "(https://huggingface.co/collections/stabilityai/stable-audio-3) 中。"
                "![配图](https://source.hex2077.dev/images/demo.avif)"
            ),
            "### 前沿研究",
            (
                "1. **surgicalmamba 系统大幅提升手术安全。** "
                "详见 [手术智能识别模型(ai资讯)](https://arxiv.org/abs/2605.14889) 报告。"
            ),
        ]
    )

    groups = parse_markdown(markdown)

    assert groups[0]["category"] == "产品与功能更新"
    assert groups[0]["category_key"] == "product"
    assert groups[0]["items"][0]["title"] == "正式发布 stable audio 3 权重。"
    assert (
        groups[0]["items"][0]["url"]
        == "https://huggingface.co/collections/stabilityai/stable-audio-3"
    )
    assert groups[0]["items"][0]["source"] == "最新音频权重合集"
    assert groups[1]["category"] == "前沿研究"


@pytest.mark.asyncio
async def test_ai_news_fetcher_force_refreshes_future_date_when_cache_misses() -> None:
    from app.clients.ai_news_fetcher import AiNewsFetcher

    calls = 0

    class SearchIndexTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            payload = [
                {
                    "slug": "2999-01/2999-01-01",
                    "title": "2999-01-01 AI 日报",
                    "type": "docs",
                    "content": (
                        "### 产品与功能更新\n"
                        "1. **未来日报已更新。** "
                        "[未来来源(ai资讯)](https://example.com/future)"
                    ),
                }
            ]
            if calls == 1:
                payload = []
            return httpx.Response(200, json=payload, request=request)

    fetcher = AiNewsFetcher()
    await fetcher._client.aclose()
    fetcher._client = httpx.AsyncClient(transport=SearchIndexTransport())
    try:
        groups = await fetcher.fetch_date("2999-01-01")
    finally:
        await fetcher.aclose()

    assert calls == 2
    assert groups[0]["category"] == "产品与功能更新"
    assert groups[0]["items"][0]["title"] == "未来日报已更新。"


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
