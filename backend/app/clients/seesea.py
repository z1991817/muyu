from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast, runtime_checkable

import httpx
from fastapi import Request
from pydantic import ValidationError

from app.config import settings
from app.models.cn_market import (
    CnFundFlow,
    CnLimitStock,
    CnMarketAnalysis,
    CnMarketIndex,
    CnMarketResponse,
    CnMarketStock,
)
from app.models.source import Source
from app.models.trend import Trend
from app.platforms import get_platform_name

_CN_INDEX_NAMES = {"上证指数", "沪深300", "中证500", "科创50"}
_CN_INDEX_SYMBOLS = {"000001", "000300", "000905", "000688"}
_CN_MARKET_STOCK_LIMIT = 20
_CN_LIMIT_LIST_LIMIT = 20
_CN_HISTORY_SYMBOLS = (
    ("600519", "贵州茅台"),
    ("300750", "宁德时代"),
    ("601318", "中国平安"),
    ("600036", "招商银行"),
    ("000333", "美的集团"),
    ("002594", "比亚迪"),
    ("000858", "五粮液"),
    ("600900", "长江电力"),
    ("601899", "紫金矿业"),
    ("000651", "格力电器"),
    ("600030", "中信证券"),
    ("600276", "恒瑞医药"),
    ("601988", "中国银行"),
    ("600309", "万华化学"),
    ("300760", "迈瑞医疗"),
    ("601668", "中国建筑"),
    ("601088", "中国神华"),
    ("600887", "伊利股份"),
    ("601398", "工商银行"),
    ("600941", "中国移动"),
    ("601288", "农业银行"),
    ("601857", "中国石油"),
    ("600028", "中国石化"),
    ("601012", "隆基绿能"),
    ("300059", "东方财富"),
    ("002415", "海康威视"),
    ("000001", "平安银行"),
    ("600050", "中国联通"),
    ("601688", "华泰证券"),
)


class StockKlineClient(Protocol):
    def get_kline(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> object: ...


@runtime_checkable
class TabularPayload(Protocol):
    def to_dict(self, orient: str) -> object: ...


class SeeSeaError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SeeSeaClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        enable_hot_sdk_fallback: bool = False,
        enable_stock_sdk_fallback: bool = False,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=(base_url or settings.seesea_base_url).rstrip("/"),
            timeout=httpx.Timeout(8.0, connect=3.0),
            headers={"User-Agent": "moyu-aggregator/0.1"},
        )
        self._sdk_client: object | None = None
        self._stock_sdk_client: object | None = None
        self._stock_sdk_lock = asyncio.Lock()
        self._enable_hot_sdk_fallback = enable_hot_sdk_fallback
        self._enable_stock_sdk_fallback = enable_stock_sdk_fallback

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_multiple(self, platforms: list[str]) -> list[Trend]:
        try:
            payload = await self._get_json(
                "/api/hot/multiple", {"platforms": ",".join(platforms), "latest": "true"}
            )
        except SeeSeaError:
            if not self._enable_hot_sdk_fallback:
                raise
            payload = await self._run_sdk("fetch_multiple_platforms", platforms)
        return self._parse_multi_payload(payload)

    async def fetch_single(self, platform: str) -> list[Trend]:
        try:
            payload = await self._get_json(f"/api/hot/{platform}", {"latest": "true"})
        except SeeSeaError:
            if not self._enable_hot_sdk_fallback:
                raise
            payload = await self._run_sdk("fetch_platform", platform)
        return self._parse_single_payload(payload, platform)

    async def fetch_platforms(self) -> list[Source]:
        try:
            payload = await self._get_json("/api/hot/platforms", None)
        except SeeSeaError:
            if not self._enable_hot_sdk_fallback:
                raise
            payload = await self._run_sdk("list_platforms")
        now = _now_iso()
        if isinstance(payload, list):
            return [
                Source(
                    platform=str(item.get("id") or item.get("platform_id") or ""),
                    platform_name=str(item.get("name") or item.get("platform_name") or ""),
                    status="ok",
                    updated_at=now,
                )
                for item in payload
                if isinstance(item, dict)
            ]
        if isinstance(payload, dict):
            return [
                Source(
                    platform=str(platform),
                    platform_name=str(platform_name),
                    status="ok",
                    updated_at=now,
                )
                for platform, platform_name in payload.items()
            ]
        return []

    async def fetch_cn_market(self) -> CnMarketResponse:
        now = _now_iso()
        last_trade_date = _recent_trade_date()
        indices_raw, quotes_raw, fund_flow_raw, limit_up_raw, limit_down_raw = await asyncio.gather(
            self._fetch_stock_data(
                "/api/stock/market/indices",
                None,
                "get_index_list",
                fallback_sdk_method="get_index_list",
            ),
            self._fetch_stock_data(
                "/api/stock/list/a",
                None,
                "_fetch_recent_cn_stock_history",
                last_trade_date,
            ),
            self._fetch_stock_data("/api/stock/fund_flow", None, "get_market_fund_flow"),
            self._fetch_stock_data(
                "/api/stock/ranking",
                {"type": "zt"},
                "get_zt_pool",
                fallback_params={"type": "zt", "date": last_trade_date},
                fallback_sdk_method="get_zt_pool",
                fallback_sdk_args=(last_trade_date,),
                akshare_fallback="stock_zt_pool_em",
                akshare_args=(last_trade_date,),
            ),
            self._fetch_stock_data(
                "/api/stock/ranking",
                {"type": "dt"},
                "get_dt_pool",
                fallback_params={"type": "dt", "date": last_trade_date},
                fallback_sdk_method="get_dt_pool",
                fallback_sdk_args=(last_trade_date,),
                akshare_fallback="stock_zt_pool_dtgc_em",
                akshare_args=(last_trade_date,),
            ),
        )

        indices = _map_primary_cn_indices(_iter_dict_items(indices_raw), now)
        stocks = [_map_cn_stock(item, now) for item in _iter_dict_items(quotes_raw)]
        stocks = [item for item in stocks if item is not None]
        stocks.sort(key=lambda item: abs(item.change_pct), reverse=True)
        limit_up_all = [
            item
            for item in (_map_cn_limit_stock(raw) for raw in _iter_dict_items(limit_up_raw))
            if item is not None
        ]
        limit_down_all = [
            item
            for item in (_map_cn_limit_stock(raw) for raw in _iter_dict_items(limit_down_raw))
            if item is not None
        ]
        if len(stocks) < _CN_MARKET_STOCK_LIMIT:
            stocks = _supplement_market_stocks_from_limit_stocks(
                stocks,
                limit_up_all + limit_down_all,
                now,
            )

        response = CnMarketResponse(
            indices=indices[:3],
            stocks=stocks[:_CN_MARKET_STOCK_LIMIT],
            analysis=CnMarketAnalysis(
                fund_flows=_map_cn_fund_flows(_iter_dict_items(fund_flow_raw))[:6],
                limit_up=limit_up_all[:_CN_LIMIT_LIST_LIMIT],
                limit_down=limit_down_all[:_CN_LIMIT_LIST_LIMIT],
            ),
            stale=False,
            updated_at=now,
        )
        if not response.indices and not response.stocks:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用")
        return response

    async def fetch_cn_market_recent_trade_snapshot(self) -> CnMarketResponse:
        if not self._enable_stock_sdk_fallback:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用")

        now = _now_iso()
        trade_date = _recent_trade_date()

        indices_raw = await self._run_stock_sdk("get_index_list")
        quotes_raw = await self._run_stock_sdk("_fetch_recent_cn_stock_history", trade_date)
        limit_up_raw = await self._fetch_limit_pool_snapshot(
            "get_zt_pool",
            "stock_zt_pool_em",
            trade_date,
        )
        limit_down_raw = await self._fetch_limit_pool_snapshot(
            "get_dt_pool",
            "stock_zt_pool_dtgc_em",
            trade_date,
        )

        indices = _map_primary_cn_indices(_iter_dict_items(indices_raw), now)
        stocks = [_map_cn_stock(item, now) for item in _iter_dict_items(quotes_raw)]
        stocks = [item for item in stocks if item is not None]
        stocks.sort(key=lambda item: abs(item.change_pct), reverse=True)
        limit_up_all = [
            item
            for item in (_map_cn_limit_stock(raw) for raw in _iter_dict_items(limit_up_raw))
            if item is not None
        ]
        limit_down_all = [
            item
            for item in (_map_cn_limit_stock(raw) for raw in _iter_dict_items(limit_down_raw))
            if item is not None
        ]
        if len(stocks) < _CN_MARKET_STOCK_LIMIT:
            stocks = _supplement_market_stocks_from_limit_stocks(
                stocks,
                limit_up_all + limit_down_all,
                now,
            )

        response = CnMarketResponse(
            indices=indices[:3],
            stocks=stocks[:_CN_MARKET_STOCK_LIMIT],
            analysis=CnMarketAnalysis(
                fund_flows=[],
                limit_up=limit_up_all[:_CN_LIMIT_LIST_LIMIT],
                limit_down=limit_down_all[:_CN_LIMIT_LIST_LIMIT],
            ),
            stale=True,
            updated_at=now,
        )
        if not response.indices and not response.stocks:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用")
        return response

    async def _get_json(self, path: str, params: dict[str, str] | None) -> object:
        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用") from exc

    async def _fetch_stock_data(
        self,
        path: str,
        params: dict[str, str] | None,
        sdk_method: str,
        *sdk_args: object,
        fallback_params: dict[str, str] | None = None,
        fallback_sdk_method: str | None = None,
        fallback_sdk_args: tuple[object, ...] = (),
        akshare_fallback: str | None = None,
        akshare_args: tuple[object, ...] = (),
    ) -> object:
        try:
            payload = await self._get_json(path, params)
            if _iter_dict_items(payload):
                return payload
        except SeeSeaError:
            pass

        if self._enable_stock_sdk_fallback:
            try:
                payload = await self._run_stock_sdk(sdk_method, *sdk_args)
                if _iter_dict_items(payload):
                    return payload
            except SeeSeaError:
                pass

        if fallback_params is not None:
            try:
                payload = await self._get_json(path, fallback_params)
                if _iter_dict_items(payload):
                    return payload
            except SeeSeaError:
                pass

        if self._enable_stock_sdk_fallback and fallback_sdk_method is not None:
            try:
                payload = await self._run_stock_sdk(fallback_sdk_method, *fallback_sdk_args)
                if _iter_dict_items(payload):
                    return payload
            except SeeSeaError:
                pass

        if self._enable_stock_sdk_fallback and akshare_fallback is not None:
            try:
                return await self._run_akshare_stock(akshare_fallback, *akshare_args)
            except SeeSeaError:
                return []

        return []

    async def _fetch_limit_pool_snapshot(
        self,
        sdk_method: str,
        akshare_method: str,
        trade_date: str,
    ) -> object:
        try:
            payload = await self._run_stock_sdk(sdk_method, trade_date)
            if _iter_dict_items(payload):
                return payload
        except SeeSeaError:
            pass

        try:
            return await self._run_akshare_stock(akshare_method, trade_date)
        except SeeSeaError:
            return []

    async def _run_sdk(self, method: str, *args: object) -> object:
        try:
            return await asyncio.to_thread(self._run_sdk_sync, method, *args)
        except Exception as exc:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用") from exc

    def _run_sdk_sync(self, method: str, *args: object) -> object:
        if self._sdk_client is None:
            self._sdk_client = _create_sdk_client()

        sdk_method = getattr(self._sdk_client, method)
        result = sdk_method(*args)
        if not getattr(result, "success", False):
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用")
        data = getattr(result, "data", None)
        if data is None:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用")
        return data

    async def _run_stock_sdk(self, method: str, *args: object) -> object:
        try:
            async with self._stock_sdk_lock:
                return await asyncio.to_thread(self._run_stock_sdk_sync, method, *args)
        except Exception as exc:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用") from exc

    def _run_stock_sdk_sync(self, method: str, *args: object) -> object:
        if self._stock_sdk_client is None:
            self._stock_sdk_client = _create_stock_sdk_client()

        if method == "_fetch_recent_cn_stock_history":
            trade_date = str(args[0]) if args else _recent_trade_date()
            return _fetch_recent_cn_stock_history(self._stock_sdk_client, trade_date)

        sdk_method: Callable[..., object] = getattr(self._stock_sdk_client, method)
        result = _call_stock_sdk_method(sdk_method, *args)
        if not getattr(result, "success", False):
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用")
        data = getattr(result, "data", None)
        if data is None:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用")
        return data

    async def _run_akshare_stock(self, method: str, *args: object) -> object:
        try:
            return await asyncio.to_thread(_run_akshare_stock_sync, method, *args)
        except Exception as exc:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用") from exc

    def _parse_multi_payload(self, payload: object) -> list[Trend]:
        groups = []
        if isinstance(payload, list):
            groups = payload
        elif isinstance(payload, dict):
            results = payload.get("results")
            if isinstance(results, list):
                groups = results
            elif all(isinstance(v, dict) for v in payload.values()):
                groups = list(payload.values())

        trends: list[Trend] = []
        now = _now_iso()
        for group in groups:
            if not isinstance(group, dict):
                continue
            platform = str(group.get("platform_id") or group.get("platform") or "")
            platform_name = str(group.get("platform_name") or get_platform_name(platform))
            items = group.get("items")
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                trend = _map_item(item, platform, platform_name, idx, now)
                if trend is not None:
                    trends.append(trend)
        return trends

    def _parse_single_payload(self, payload: object, platform: str) -> list[Trend]:
        if not isinstance(payload, dict):
            return []
        platform_name = str(payload.get("platform_name") or get_platform_name(platform))
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        now = _now_iso()
        trends: list[Trend] = []
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            trend = _map_item(item, platform, platform_name, idx, now)
            if trend is not None:
                trends.append(trend)
        return trends


def _map_item(
    item: dict[str, object], platform: str, platform_name: str, rank: int, fallback_time: str
) -> Trend | None:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or item.get("mobileUrl") or item.get("mobile_url") or "").strip()
    if not title or not url:
        return None

    raw_rank = item.get("rank")
    if isinstance(raw_rank, int):
        rank = raw_rank

    heat_value = item.get("hotValue") or item.get("hot_value")
    heat = str(heat_value) if heat_value is not None else str(item.get("hotIndex") or "")
    updated_at = str(item.get("publishTime") or fallback_time)

    try:
        return Trend(
            platform=platform,
            platform_name=platform_name,
            title=title,
            url=url,
            rank=rank,
            heat=heat,
            source=str(item.get("source") or platform),
            updated_at=updated_at,
        )
    except ValidationError:
        return None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _recent_trade_date(today: date | None = None) -> str:
    current = today or datetime.now(UTC).date()
    current -= timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current.strftime("%Y%m%d")


def _iter_dict_items(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        result = payload.get("result")
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
    return []


def _text(raw: dict[str, object], *keys: str, default: str = "") -> str:
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _number(raw: dict[str, object], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = raw.get(key)
        if value is None or value == "":
            continue
        try:
            return float(Decimal(str(value).replace(",", "").replace("%", "")))
        except (InvalidOperation, ValueError):
            continue
    return default


def _is_primary_cn_index(raw: dict[str, object]) -> bool:
    symbol = _text(raw, "代码", "code", "symbol", "指数代码")
    name = _text(raw, "名称", "name", "指数名称")
    return name in _CN_INDEX_NAMES or symbol in _CN_INDEX_SYMBOLS


def _map_primary_cn_indices(items: list[dict[str, object]], updated_at: str) -> list[CnMarketIndex]:
    mapped: list[CnMarketIndex] = []
    seen: set[str] = set()
    preferred_symbols = ("000001", "000300", "000905", "000688")

    for symbol in preferred_symbols:
        item = next(
            (raw for raw in items if _text(raw, "代码", "code", "symbol", "指数代码") == symbol),
            None,
        )
        if item is None:
            continue
        index = _map_cn_index(item, updated_at)
        if index is not None and index.symbol not in seen:
            mapped.append(index)
            seen.add(index.symbol)

    for item in items:
        if not _is_primary_cn_index(item):
            continue
        index = _map_cn_index(item, updated_at)
        if index is not None and index.symbol not in seen:
            mapped.append(index)
            seen.add(index.symbol)

    return mapped


def _stock_url(symbol: str) -> str:
    return (
        f"https://quote.eastmoney.com/{symbol}.html" if symbol else "https://quote.eastmoney.com/"
    )


def _map_cn_index(raw: dict[str, object], updated_at: str) -> CnMarketIndex | None:
    symbol = _text(raw, "代码", "code", "symbol", "指数代码")
    name = _text(raw, "名称", "name", "指数名称")
    if not name:
        return None
    return CnMarketIndex(
        symbol=symbol or name,
        name=name,
        price=_number(raw, "最新价", "price", "current_price", "最新"),
        change=_number(raw, "涨跌额", "change", "change_amount"),
        change_pct=_number(raw, "涨跌幅", "change_pct", "change_percent", "涨跌幅"),
        url=_stock_url(symbol),
        updated_at=updated_at,
        disclaimer=settings.market_disclaimer,
    )


def _map_cn_stock(raw: dict[str, object], updated_at: str) -> CnMarketStock | None:
    symbol = _text(raw, "代码", "code", "symbol")
    name = _text(raw, "名称", "name")
    if not symbol or not name:
        return None
    return CnMarketStock(
        symbol=symbol,
        name=name,
        price=_number(raw, "最新价", "收盘", "price", "current_price", "close", "最新"),
        change=_number(raw, "涨跌额", "change", "change_amount"),
        change_pct=_number(raw, "涨跌幅", "change_pct", "change_percent"),
        volume=_text(raw, "成交量", "volume", default="-"),
        turnover=_text(raw, "成交额", "turnover", "amount", default="-"),
        url=_stock_url(symbol),
        updated_at=updated_at,
        disclaimer=settings.market_disclaimer,
    )


def _map_cn_stock_history(
    raw: dict[str, object], symbol: str, name: str, updated_at: str
) -> dict[str, object] | None:
    price = _number(raw, "收盘", "close", "最新价", "price")
    if price == 0:
        return None
    return {
        "代码": symbol,
        "名称": name,
        "最新价": price,
        "涨跌额": _number(raw, "涨跌额", "change", "change_amount"),
        "涨跌幅": _number(raw, "涨跌幅", "change_pct", "change_percent"),
        "成交量": _text(raw, "成交量", "volume", default="-"),
        "成交额": _text(raw, "成交额", "turnover", "amount", default="-"),
        "日期": _text(raw, "日期", "date", "trade_date", default=updated_at),
    }


def _fetch_recent_cn_stock_history(
    stock_client: object, trade_date: str
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    method = cast(StockKlineClient, stock_client).get_kline
    for symbol, name in _CN_HISTORY_SYMBOLS:
        result = _call_stock_sdk_method(method, symbol, "daily", trade_date, trade_date, "qfq")
        if not getattr(result, "success", False):
            continue
        rows = _iter_dict_items(getattr(result, "data", None))
        if not rows:
            continue
        item = _map_cn_stock_history(rows[-1], symbol, name, trade_date)
        if item is not None:
            items.append(item)
    return items


def _call_stock_sdk_method(method: Callable[..., object], *args: object) -> object:
    result: object | None = None
    for _attempt in range(3):
        result = method(*args)
        if getattr(result, "success", False):
            return result
    return result


def _run_akshare_stock_sync(method: str, *args: object) -> object:
    import importlib

    akshare = importlib.import_module("akshare")
    akshare_method = cast(Callable[..., object], getattr(akshare, method))
    payload = akshare_method(*args)
    if isinstance(payload, TabularPayload):
        return payload.to_dict("records")
    return payload


def _map_cn_fund_flows(items: list[dict[str, object]]) -> list[CnFundFlow]:
    if not items:
        return []

    latest = items[-1]
    if latest.get("主力净流入-净额") is None:
        flows = [_map_cn_fund_flow(item) for item in items]
        return [item for item in flows if item is not None]

    return [
        item
        for item in (
            _map_cn_fund_flow_metric(latest, "主力资金", "主力净流入-净额", "主力净流入-净占比"),
            _map_cn_fund_flow_metric(latest, "超大单", "超大单净流入-净额", "超大单净流入-净占比"),
            _map_cn_fund_flow_metric(latest, "大单", "大单净流入-净额", "大单净流入-净占比"),
            _map_cn_fund_flow_metric(latest, "中单", "中单净流入-净额", "中单净流入-净占比"),
            _map_cn_fund_flow_metric(latest, "小单", "小单净流入-净额", "小单净流入-净占比"),
        )
        if item is not None
    ]


def _map_cn_fund_flow_metric(
    raw: dict[str, object], name: str, value_key: str, pct_key: str
) -> CnFundFlow | None:
    if raw.get(value_key) is None:
        return None
    value = _text(raw, value_key, default="-")
    direction = "in" if not str(value).startswith("-") else "out"
    return CnFundFlow(
        name=name,
        value=value,
        change_pct=_number(raw, pct_key),
        direction=direction,
    )


def _map_cn_fund_flow(raw: dict[str, object]) -> CnFundFlow | None:
    name = _text(raw, "名称", "name", "板块", "行业", "item")
    if not name and raw.get("日期") is not None:
        name = "主力资金"
    if not name:
        return None
    value = _text(raw, "净流入", "主力净流入", "主力净流入-净额", "value", "amount", default="-")
    change_pct = _number(
        raw,
        "涨跌幅",
        "上证-涨跌幅",
        "深证-涨跌幅",
        "主力净流入-净占比",
        "change_pct",
        "change_percent",
    )
    direction = "in" if not str(value).startswith("-") else "out"
    return CnFundFlow(name=name, value=value, change_pct=change_pct, direction=direction)


def _map_cn_limit_stock(raw: dict[str, object]) -> CnLimitStock | None:
    symbol = _text(raw, "代码", "code", "symbol")
    name = _text(raw, "名称", "name")
    if not symbol or not name:
        return None
    return CnLimitStock(
        symbol=symbol,
        name=name,
        price=_number(raw, "最新价", "price", "current_price"),
        change_pct=_number(raw, "涨跌幅", "change_pct", "change_percent"),
        reason=_text(raw, "涨停原因", "跌停原因", "原因", "reason", default="市场异动"),
        url=_stock_url(symbol),
    )


def _supplement_market_stocks_from_limit_stocks(
    stocks: list[CnMarketStock],
    limit_stocks: list[CnLimitStock],
    updated_at: str,
) -> list[CnMarketStock]:
    merged = list(stocks)
    seen = {item.symbol for item in merged}
    for item in limit_stocks:
        if item.symbol in seen:
            continue
        merged.append(
            CnMarketStock(
                symbol=item.symbol,
                name=item.name,
                price=item.price,
                change=0,
                change_pct=item.change_pct,
                volume="-",
                turnover="-",
                url=item.url,
                updated_at=updated_at,
                disclaimer=settings.market_disclaimer,
            )
        )
        seen.add(item.symbol)
        if len(merged) >= _CN_MARKET_STOCK_LIMIT:
            break
    return merged


def _create_sdk_client() -> object:
    try:
        from seesea.sdk.feed.hot_client import HotTrendClient  # type: ignore[reportMissingImports]
    except ImportError as exc:
        raise SeeSeaError("SEESEA_SDK_UNAVAILABLE", "上游数据源暂不可用") from exc

    client = HotTrendClient(max_concurrency=10)
    result = client.connect()
    if not getattr(result, "success", False):
        raise SeeSeaError("SEESEA_SDK_UNAVAILABLE", "上游数据源暂不可用")
    return client


def _create_stock_sdk_client() -> object:
    try:
        from seesea.sdk.stock.client import StockClient  # type: ignore[reportMissingImports]
    except ImportError as exc:
        raise SeeSeaError("SEESEA_SDK_UNAVAILABLE", "上游数据源暂不可用") from exc

    client = StockClient()
    result = client.connect()
    if not getattr(result, "success", False):
        raise SeeSeaError("SEESEA_SDK_UNAVAILABLE", "上游数据源暂不可用")
    return client


def get_seesea_client(request: Request) -> SeeSeaClient:
    return request.app.state.seesea_client
