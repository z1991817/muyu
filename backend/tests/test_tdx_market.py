from __future__ import annotations

from enum import Enum
from types import TracebackType
from typing import NoReturn

import pytest
from httpx import AsyncClient

from app.clients.tdx_market import TdxRuntime


class FakeMarket(Enum):
    SZ = 0
    SH = 1
    BJ = 2


class FakeCategory(Enum):
    A = 6


class FakeBoardType(Enum):
    HY = 10001


class FakeSortType(Enum):
    CODE = 0


def _stock_row(
    market: FakeMarket,
    code: str,
    close: float,
    pre_close: float,
    amount: float,
    *,
    vol_ratio: float = 1.0,
    name: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "market": market,
        "code": code,
        "close": close,
        "pre_close": pre_close,
        "vol": 100000 + int(amount / 10000),
        "amount": amount,
        "vol_ratio": vol_ratio,
        "handicap": {
            "bid": [{"price": close, "vol": 1000}],
            "ask": [{"price": close + 0.01, "vol": 1000}],
        },
    }
    if name is not None:
        row["name"] = name
    return row


class FakeTdxClient:
    def __enter__(self) -> FakeTdxClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        return None

    def stock_quotes(self, code_list: list[tuple[object, str]]) -> object:
        if len(code_list) > 1:
            return None
        index_rows = {
            "999999": _stock_row(FakeMarket.SH, "999999", 3120.5, 3108.2, 1_000_000),
            "000300": _stock_row(FakeMarket.SH, "000300", 3900.0, 3882.0, 1_000_000),
            "000905": _stock_row(FakeMarket.SH, "000905", 5800.0, 5810.0, 1_000_000),
            "000688": _stock_row(FakeMarket.SH, "000688", 900.0, 880.0, 1_000_000),
        }
        return [index_rows[code] for _, code in code_list]

    def stock_quotes_list(
        self,
        category: object,
        start: int = 0,
        count: int = 80,
        sort_type: object | None = None,
        reverse: bool = False,
    ) -> list[dict[str, object]]:
        rows = [
            _stock_row(FakeMarket.SH, "600000", 11.0, 10.0, 900_000_000, vol_ratio=4.2),
            _stock_row(FakeMarket.SZ, "000002", 9.0, 10.0, 800_000_000, vol_ratio=3.1),
            _stock_row(FakeMarket.SZ, "300001", 12.0, 10.0, 700_000_000, vol_ratio=2.8),
            _stock_row(FakeMarket.SH, "688001", 8.0, 10.0, 600_000_000, vol_ratio=2.4),
            _stock_row(FakeMarket.BJ, "920575", 13.0, 10.0, 500_000_000, vol_ratio=2.2),
            _stock_row(FakeMarket.SH, "600001", 10.5, 10.0, 490_000_000),
            _stock_row(FakeMarket.SH, "600002", 9.8, 10.0, 480_000_000),
            _stock_row(FakeMarket.SZ, "000003", 10.1, 10.0, 470_000_000),
            _stock_row(FakeMarket.SZ, "000004", 10.0, 10.0, 460_000_000),
            _stock_row(FakeMarket.SH, "600003", 10.2, 10.0, 450_000_000),
            _stock_row(FakeMarket.SH, "600004", 9.9, 10.0, 440_000_000),
            _stock_row(FakeMarket.SZ, "000005", 10.3, 10.0, 430_000_000),
            _stock_row(
                FakeMarket.BJ,
                "920218",
                51.77,
                12.19,
                420_000_000,
                name="N新天力",
            ),
            _stock_row(FakeMarket.SH, "600006", 11.05, 10.03, 410_000_000),
        ]
        rows.extend(
            _stock_row(
                FakeMarket.SH,
                f"60{index + 1000:04d}",
                10.01 if index % 3 == 0 else 9.99 if index % 3 == 1 else 10.0,
                10.0,
                10_000_000 + index,
            )
            for index in range(1200)
        )
        return rows[start:] if count == 0 else rows[start : start + count]

    def stock_board_members(self, board_symbol: object, count: int = 100000) -> object:
        return self.stock_quotes_list(board_symbol, count=count)

    def stock_list(
        self,
        market: object,
        start: int = 0,
        count: int = 0,
    ) -> list[dict[str, object]]:
        names = {
            "600000": "浦发银行",
            "000002": "万科A",
            "300001": "特锐德",
            "688001": "华兴源创",
            "920575": "惠丰钻石",
            "600001": "测试沪一",
            "600002": "测试沪二",
            "000003": "测试深三",
            "000004": "测试深四",
            "600003": "测试沪三",
            "600004": "测试沪四",
            "000005": "测试深五",
        }
        return [{"code": code, "name": name} for code, name in names.items()]

    def stock_board_list(self, market: object, count: int = 10000) -> object:
        return [
            {
                "code": "880491",
                "name": "酿酒",
                "price": 1020.0,
                "pre_close": 1000.0,
                "symbol_code": "688001",
                "symbol_name": "华兴源创",
                "symbol_price": 8.0,
                "symbol_pre_close": 10.0,
            }
        ]


def _runtime() -> TdxRuntime:
    return TdxRuntime(
        client_factory=FakeTdxClient,
        market_sz=FakeMarket.SZ,
        market_sh=FakeMarket.SH,
        market_bj=FakeMarket.BJ,
        category_a=FakeCategory.A,
        board_type_hy=FakeBoardType.HY,
        sort_code=FakeSortType.CODE,
    )


@pytest.mark.asyncio
async def test_tdx_market_client_builds_complete_snapshot() -> None:
    from app.clients.tdx_market import TdxMarketClient

    response = await TdxMarketClient(runtime=_runtime()).fetch_cn_market()

    assert response.source == "opentdx"
    assert response.stale is False
    assert response.stale_reason is None
    assert len(response.indices) == 4
    assert len(response.stocks) == 20
    assert response.indices[0].symbol == "000001"
    assert response.stocks[0].symbol == "600000"
    assert response.analysis.market_breadth[0].name == "上涨家数"
    assert response.analysis.fund_flows[0].name == response.analysis.market_breadth[0].name
    assert response.analysis.limit_up == []
    assert response.analysis.limit_down == []
    assert [item.symbol for item in response.analysis.top_gainers[:3]] == [
        "920218",
        "920575",
        "300001",
    ]
    assert [item.symbol for item in response.analysis.top_losers[:2]] == ["688001", "000002"]
    assert response.analysis.top_gainers[0].reason == "涨幅靠前"
    assert response.analysis.top_losers[0].reason == "跌幅靠前"
    assert response.analysis.active_stocks[0].reason == "量比 4.20"
    assert response.analysis.sector_trends[0].name == "酿酒"
    assert (
        response.analysis.sector_trends[0].url
        == "https://vip.stock.finance.sina.com.cn/mkt/#new_ljhy"
    )


def test_sina_sector_url_falls_back_to_all_sector_page() -> None:
    from app.clients.tdx_market import _sina_sector_url

    assert _sina_sector_url("医疗美容") == "https://finance.sina.com.cn/stock/sl/#sinaindustry_1"


@pytest.mark.asyncio
async def test_cn_market_route_returns_empty_new_structure_without_snapshot(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/market/cn")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "opentdx"
    assert payload["stale"] is True
    assert payload["staleReason"] == "NO_CN_MARKET_SNAPSHOT"
    assert payload["analysis"]["marketBreadth"] == []
    assert payload["analysis"]["topGainers"] == []
    assert payload["analysis"]["topLosers"] == []
    assert payload["analysis"]["activeStocks"] == []
    assert payload["analysis"]["sectorTrends"] == []


@pytest.mark.asyncio
async def test_cn_market_refresh_failure_keeps_previous_complete_snapshot(
    client: AsyncClient,
    test_app,
) -> None:
    from app.clients.tdx_market import CnMarketError, TdxMarketClient
    from app.scheduler import _refresh_cn_market

    complete = await TdxMarketClient(runtime=_runtime()).fetch_cn_market()
    await test_app.state.cache.set(
        "market:cn",
        complete.model_dump(mode="json"),
        ttl_seconds=60,
        source_status="ok",
    )

    class IncompleteFetcher:
        async def fetch_cn_market(self):
            return complete.model_copy(update={"indices": []})

    result = await _refresh_cn_market(IncompleteFetcher(), test_app.state.cache)
    response = await client.get("/api/market/cn")

    assert result is not None
    assert result.stale is True
    assert result.stale_reason == "CN_MARKET_INCOMPLETE_SNAPSHOT"
    payload = response.json()
    assert payload["stale"] is True
    assert payload["staleReason"] == "CN_MARKET_INCOMPLETE_SNAPSHOT"
    assert payload["indices"][0]["symbol"] == "000001"
    assert payload["stocks"][0]["symbol"] == "600000"

    class FailingFetcher:
        async def fetch_cn_market(self) -> NoReturn:
            raise CnMarketError("CN_MARKET_REFRESH_FAILED", "mock fail")

    failed = await _refresh_cn_market(FailingFetcher(), test_app.state.cache)
    assert failed is not None
    assert failed.stale_reason == "CN_MARKET_REFRESH_FAILED"


@pytest.mark.asyncio
async def test_cn_market_job_writes_tdx_snapshot(
    client: AsyncClient,
    test_app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.clients.tdx_market import TdxMarketClient
    from app.jobs import refresh_cn_market

    class StaticTdxMarketClient:
        async def fetch_cn_market(self):
            return await TdxMarketClient(runtime=_runtime()).fetch_cn_market()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        refresh_cn_market.settings, "cache_db_path", test_app.state.cache._db_path.as_posix()
    )
    monkeypatch.setattr(refresh_cn_market, "TdxMarketClient", StaticTdxMarketClient)

    exit_code = await refresh_cn_market.refresh_once()
    response = await client.get("/api/market/cn")

    assert exit_code == 0
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "opentdx"
    assert payload["stale"] is False
    assert payload["analysis"]["marketBreadth"][0]["name"] == "上涨家数"
    assert payload["analysis"]["limitUp"] == []
    assert payload["analysis"]["limitDown"] == []
    assert payload["analysis"]["topGainers"][0]["reason"] == "涨幅靠前"
