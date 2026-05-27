from __future__ import annotations

import asyncio
import importlib
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast, runtime_checkable

import httpx

from app.config import settings
from app.models.cn_market import (
    CnFundFlow,
    CnLimitStock,
    CnMarketAnalysis,
    CnMarketIndex,
    CnMarketResponse,
    CnMarketStock,
)

_CN_MARKET_STOCK_LIMIT = 20
_CN_LIMIT_LIST_LIMIT = 20
_CN_INDEX_NAMES = {"上证指数", "沪深300", "中证500", "科创50"}
_CN_INDEX_SYMBOLS = {"000001", "000300", "000905", "000688"}
_TENCENT_INDEX_URL = "https://qt.gtimg.cn/q=sh000001,sh000300,sh000905"
_SINA_INDEX_URL = "https://hq.sinajs.cn/list=s_sh000001,s_sh000300,s_sh000905"
_EASTMONEY_FUND_FLOW_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"


class CnMarketError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@runtime_checkable
class TabularPayload(Protocol):
    def to_dict(self, orient: str) -> object: ...


class CnMarketClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(12.0, connect=5.0),
            headers={"User-Agent": "Mozilla/5.0"},
            trust_env=False,
        )
        self._akshare_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def fetch_cn_market(self) -> CnMarketResponse:
        now = _now_iso()
        trade_date = _recent_trade_date()
        (
            indices_raw,
            stocks_raw,
            hot_stocks_raw,
            fund_flow_raw,
            limit_up_raw,
            limit_down_raw,
        ) = await asyncio.gather(
            self._fetch_indices(),
            self._run_akshare("stock_zh_a_spot"),
            self._run_akshare("stock_hot_follow_xq"),
            self._fetch_fund_flow(),
            self._run_akshare("stock_zt_pool_em", trade_date),
            self._run_akshare("stock_zt_pool_dtgc_em", trade_date),
            return_exceptions=True,
        )

        indices = _map_primary_cn_indices(_items_or_empty(indices_raw), now)[:3]
        stock_rows = _items_or_empty(stocks_raw)
        all_stocks = [
            item for item in (_map_cn_stock(raw, now) for raw in stock_rows) if item is not None
        ]
        hot_rows = _items_or_empty(hot_stocks_raw)
        stocks = _map_hot_cn_stocks(hot_rows, all_stocks)
        if not stocks and hot_rows:
            hot_quotes_raw = await self._fetch_tencent_hot_stock_quotes(hot_rows)
            stocks = [
                item
                for item in (_map_cn_stock(raw, now) for raw in _iter_dict_items(hot_quotes_raw))
                if item is not None
            ]
        if not stocks:
            stocks = list(all_stocks)
            stocks.sort(key=lambda item: abs(item.change_pct), reverse=True)
        limit_up_all = [
            item
            for item in (_map_cn_limit_stock(raw) for raw in _items_or_empty(limit_up_raw))
            if item is not None
        ]
        limit_down_all = [
            item
            for item in (_map_cn_limit_stock(raw) for raw in _items_or_empty(limit_down_raw))
            if item is not None
        ]
        response = CnMarketResponse(
            indices=indices,
            stocks=stocks[:_CN_MARKET_STOCK_LIMIT],
            analysis=CnMarketAnalysis(
                fund_flows=_map_cn_market_breadth(
                    stock_rows,
                    limit_up_all,
                    limit_down_all,
                    _items_or_empty(fund_flow_raw),
                )[:6],
                limit_up=limit_up_all[:_CN_LIMIT_LIST_LIMIT],
                limit_down=limit_down_all[:_CN_LIMIT_LIST_LIMIT],
            ),
            stale=False,
            updated_at=now,
        )
        if not response.indices and not response.stocks:
            raise CnMarketError("CN_MARKET_UPSTREAM", "A 股行情接口暂不可用")
        return response

    async def fetch_cn_market_recent_trade_snapshot(self) -> CnMarketResponse:
        return (await self.fetch_cn_market()).model_copy(update={"stale": True})

    async def _fetch_indices(self) -> object:
        tencent = await self._fetch_tencent_indices()
        if tencent:
            return tencent

        sina = await self._fetch_sina_indices()
        if sina:
            return sina

        return await self._run_akshare("stock_zh_index_spot_em")

    async def _fetch_tencent_indices(self) -> list[dict[str, object]]:
        try:
            response = await self._http.get(_TENCENT_INDEX_URL)
            response.raise_for_status()
            return _parse_tencent_cn_index_text(response.text)
        except httpx.HTTPError:
            return []

    async def _fetch_sina_indices(self) -> list[dict[str, object]]:
        try:
            response = await self._http.get(
                _SINA_INDEX_URL,
                headers={"Referer": "https://finance.sina.com.cn/"},
            )
            response.raise_for_status()
            return _parse_sina_cn_index_text(response.text)
        except httpx.HTTPError:
            return []

    async def _fetch_fund_flow(self) -> object:
        params = {
            "lmt": "0",
            "klt": "101",
            "secid": "1.000001",
            "secid2": "0.399001",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
        }
        payload: object | None = None
        for _attempt in range(2):
            try:
                response = await self._http.get(
                    _EASTMONEY_FUND_FLOW_URL,
                    params=params,
                    headers={"Referer": "https://quote.eastmoney.com/"},
                )
                response.raise_for_status()
                payload = response.json()
                break
            except (httpx.HTTPError, ValueError):
                payload = None
        if payload is None:
            return []

        data = payload.get("data") if isinstance(payload, dict) else None
        klines = data.get("klines") if isinstance(data, dict) else None
        if not isinstance(klines, list) or not klines:
            return []
        latest = str(klines[-1]).split(",")
        if len(latest) < 15:
            return []
        return [
            {
                "日期": latest[0],
                "主力净流入-净额": latest[1],
                "小单净流入-净额": latest[2],
                "中单净流入-净额": latest[3],
                "大单净流入-净额": latest[4],
                "超大单净流入-净额": latest[5],
                "主力净流入-净占比": latest[6],
                "小单净流入-净占比": latest[7],
                "中单净流入-净占比": latest[8],
                "大单净流入-净占比": latest[9],
                "超大单净流入-净占比": latest[10],
                "上证-涨跌幅": latest[12],
                "深证-涨跌幅": latest[14],
            }
        ]

    async def _fetch_tencent_hot_stock_quotes(
        self,
        hot_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        quote_symbols: list[str] = []
        for raw in hot_rows:
            symbol = _normalize_cn_symbol(_text(raw, "股票代码", "代码", "code", "symbol"))
            if not symbol:
                continue
            quote_symbols.append(_tencent_quote_symbol(symbol))
            if len(quote_symbols) >= _CN_MARKET_STOCK_LIMIT:
                break
        if not quote_symbols:
            return []

        try:
            response = await self._http.get(f"https://qt.gtimg.cn/q={','.join(quote_symbols)}")
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        return _parse_tencent_cn_stock_text(response.text)

    async def _run_akshare(self, method: str, *args: object) -> object:
        try:
            async with self._akshare_lock:
                return await asyncio.to_thread(_run_akshare_sync, method, *args)
        except Exception as exc:
            raise CnMarketError("CN_MARKET_UPSTREAM", "A 股行情接口暂不可用") from exc


def _run_akshare_sync(method: str, *args: object) -> object:
    akshare = importlib.import_module("akshare")
    akshare_method = cast(Callable[..., object], getattr(akshare, method))
    payload = akshare_method(*args)
    if isinstance(payload, TabularPayload):
        return payload.to_dict("records")
    return payload


def _items_or_empty(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, BaseException):
        return []
    return _iter_dict_items(payload)


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
        diff = payload.get("diff")
        if isinstance(diff, list):
            return [item for item in diff if isinstance(item, dict)]
        nested_data = data.get("diff") if isinstance(data, dict) else None
        if isinstance(nested_data, list):
            return [item for item in nested_data if isinstance(item, dict)]
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
    symbol = _normalize_cn_symbol(_text(raw, "代码", "code", "symbol", "指数代码", "f12"))
    name = _text(raw, "名称", "name", "指数名称", "f14")
    return name in _CN_INDEX_NAMES or symbol in _CN_INDEX_SYMBOLS


def _map_primary_cn_indices(items: list[dict[str, object]], updated_at: str) -> list[CnMarketIndex]:
    mapped: list[CnMarketIndex] = []
    seen: set[str] = set()
    preferred_symbols = ("000001", "000300", "000905", "000688")

    for symbol in preferred_symbols:
        item = next(
            (
                raw
                for raw in items
                if _normalize_cn_symbol(_text(raw, "代码", "code", "symbol", "指数代码", "f12"))
                == symbol
            ),
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


def _map_cn_index(raw: dict[str, object], updated_at: str) -> CnMarketIndex | None:
    symbol = _normalize_cn_symbol(_text(raw, "代码", "code", "symbol", "指数代码", "f12"))
    name = _text(raw, "名称", "name", "指数名称", "f14")
    if not name:
        return None
    return CnMarketIndex(
        symbol=symbol or name,
        name=name,
        price=_number(raw, "最新价", "price", "current_price", "最新", "f2"),
        change=_number(raw, "涨跌额", "change", "change_amount", "f4"),
        change_pct=_number(raw, "涨跌幅", "change_pct", "change_percent", "f3"),
        url=_stock_url(symbol),
        updated_at=updated_at,
        disclaimer=settings.market_disclaimer,
    )


def _parse_tencent_cn_index_text(text: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for match in re.finditer(r'v_(?:sh|sz)\d+="([^"]*)"', text):
        parts = match.group(1).split("~")
        if len(parts) <= 32:
            continue
        items.append(
            {
                "代码": parts[2],
                "名称": parts[1],
                "最新价": parts[3],
                "涨跌额": parts[31],
                "涨跌幅": parts[32],
            }
        )
    return items


def _parse_sina_cn_index_text(text: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for match in re.finditer(r'var hq_str_s_(?:sh|sz)(\d+)="([^"]*)"', text):
        parts = match.group(2).split(",")
        if len(parts) < 4:
            continue
        items.append(
            {
                "代码": match.group(1),
                "名称": parts[0],
                "最新价": parts[1],
                "涨跌额": parts[2],
                "涨跌幅": parts[3],
            }
        )
    return items


def _parse_tencent_cn_stock_text(text: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for match in re.finditer(r'v_(?:sh|sz|bj)\d+="([^"]*)"', text):
        parts = match.group(1).split("~")
        if len(parts) <= 37:
            continue
        items.append(
            {
                "代码": parts[2],
                "名称": parts[1],
                "最新价": parts[3],
                "涨跌额": parts[31],
                "涨跌幅": parts[32],
                "成交量": parts[36],
                "成交额": parts[37],
            }
        )
    return items


def _map_cn_stock(raw: dict[str, object], updated_at: str) -> CnMarketStock | None:
    symbol = _normalize_cn_symbol(_text(raw, "代码", "code", "symbol"))
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


def _map_hot_cn_stocks(
    hot_rows: list[dict[str, object]],
    quote_stocks: list[CnMarketStock],
) -> list[CnMarketStock]:
    if not hot_rows or not quote_stocks:
        return []

    quote_by_symbol = {item.symbol: item for item in quote_stocks}
    result: list[CnMarketStock] = []
    seen: set[str] = set()
    for raw in hot_rows:
        symbol = _normalize_cn_symbol(_text(raw, "股票代码", "代码", "code", "symbol"))
        if not symbol or symbol in seen:
            continue
        quote = quote_by_symbol.get(symbol)
        if quote is None:
            continue
        result.append(quote)
        seen.add(symbol)
        if len(result) >= _CN_MARKET_STOCK_LIMIT:
            break
    return result


def _map_cn_fund_flows(items: list[dict[str, object]]) -> list[CnFundFlow]:
    if not items:
        return []

    latest = items[-1]
    if latest.get("主力净流入-净额") is None:
        flows = [_map_cn_fund_flow(item) for item in items]
        return [item for item in flows if item is not None]

    rows = [
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
    if rows:
        return rows

    flows = [_map_cn_fund_flow(item) for item in items]
    return [item for item in flows if item is not None]


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
    if not name:
        name = _text(raw, "板块", default="")
    value = _text(
        raw,
        "净流入",
        "主力净流入",
        "主力净流入-净额",
        "资金净流入",
        "成交净买额",
        "value",
        "amount",
        default="-",
    )
    if not name or value == "-":
        return None
    change_pct = _number(
        raw,
        "涨跌幅",
        "指数涨跌幅",
        "上证-涨跌幅",
        "深证-涨跌幅",
        "主力净流入-净占比",
        "change_pct",
        "change_percent",
    )
    direction = "in" if not str(value).startswith("-") else "out"
    return CnFundFlow(name=name, value=value, change_pct=change_pct, direction=direction)


def _map_cn_market_breadth(
    stock_rows: list[dict[str, object]],
    limit_up: list[CnLimitStock],
    limit_down: list[CnLimitStock],
    fallback_fund_flow_items: list[dict[str, object]],
) -> list[CnFundFlow]:
    if not stock_rows:
        if limit_up or limit_down:
            diff = len(limit_up) - len(limit_down)
            return [
                CnFundFlow(
                    name="涨停家数",
                    value=str(len(limit_up)),
                    change_pct=0.0,
                    direction="in",
                ),
                CnFundFlow(
                    name="跌停家数",
                    value=str(len(limit_down)),
                    change_pct=0.0,
                    direction="out",
                ),
                CnFundFlow(
                    name="涨跌停差",
                    value=str(diff),
                    change_pct=0.0,
                    direction="in" if diff >= 0 else "out",
                ),
            ]
        return _map_cn_fund_flows(fallback_fund_flow_items)

    changes = [_number(raw, "涨跌幅", "change_pct", "change_percent") for raw in stock_rows]
    total = len(changes)
    up_count = sum(1 for value in changes if value > 0)
    down_count = sum(1 for value in changes if value < 0)
    flat_count = total - up_count - down_count
    return [
        _market_breadth_item("上涨家数", up_count, total, "in"),
        _market_breadth_item("下跌家数", down_count, total, "out"),
        _market_breadth_item("平盘家数", flat_count, total, "flat"),
        _market_breadth_item("涨停家数", len(limit_up), total, "in"),
        _market_breadth_item("跌停家数", len(limit_down), total, "out"),
    ]


def _market_breadth_item(name: str, count: int, total: int, direction: str) -> CnFundFlow:
    pct = round(count / total * 100, 2) if total else 0.0
    return CnFundFlow(name=name, value=str(count), change_pct=pct, direction=direction)


def _map_cn_limit_stock(raw: dict[str, object]) -> CnLimitStock | None:
    symbol = _normalize_cn_symbol(_text(raw, "代码", "code", "symbol"))
    name = _text(raw, "名称", "name")
    if not symbol or not name:
        return None
    return CnLimitStock(
        symbol=symbol,
        name=name,
        price=_number(raw, "最新价", "price", "current_price"),
        change_pct=_number(raw, "涨跌幅", "change_pct", "change_percent"),
        reason=_limit_reason(raw),
        url=_stock_url(symbol),
    )


def _limit_reason(raw: dict[str, object]) -> str:
    explicit_reason = _text(raw, "涨停原因", "跌停原因", "原因", "reason")
    if explicit_reason:
        return explicit_reason

    industry = _text(raw, "所属行业", "行业")
    consecutive = _text(raw, "连板数", "连续跌停")
    if industry and consecutive and consecutive not in {"0", "0.0"}:
        suffix = "连板" if _number(raw, "涨跌幅") >= 0 else "连跌"
        return f"{industry} · {consecutive}{suffix}"
    if industry:
        return industry
    return "市场异动"


def _normalize_cn_symbol(symbol: str) -> str:
    value = symbol.strip()
    if "." in value:
        value = value.split(".", 1)[0]
    lower = value.lower()
    if lower.startswith(("sh", "sz", "bj")) and len(value) > 2:
        value = value[2:]
    return value


def _tencent_quote_symbol(symbol: str) -> str:
    if symbol.startswith(("8", "4", "9")):
        return f"bj{symbol}"
    if symbol.startswith(("6", "5", "7")):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _stock_url(symbol: str) -> str:
    if not symbol:
        return "https://quote.eastmoney.com/"
    if symbol.startswith(("8", "4", "9")):
        return f"https://quote.eastmoney.com/bj/{symbol}.html"
    return f"https://quote.eastmoney.com/{symbol}.html"
