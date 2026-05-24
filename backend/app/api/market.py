from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Request

from app.cache.policy import as_fresh, as_stale, get_cached_response, market_ttl_seconds
from app.cache.sqlite import SQLiteCache
from app.clients.akshare import AkShareClient, AkShareError
from app.clients.seesea import SeeSeaClient, SeeSeaError, get_seesea_client
from app.models.cn_market import CnMarketAnalysis, CnMarketResponse
from app.models.market import MarketResponse, StocksResponse

router = APIRouter(tags=["market"])
T = TypeVar("T")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


CN_MARKET_FETCH_TIMEOUT_SECONDS = 10.0


def get_cache(request: Request) -> SQLiteCache:
    return request.app.state.cache


def get_akshare_client(request: Request) -> AkShareClient:
    return request.app.state.akshare_client


def _has_real_market_values(response: MarketResponse) -> bool:
    if not response.items:
        return False
    return any(
        item.price != 0 or item.change != 0 or item.change_pct != 0 for item in response.items
    )


def _has_cn_market_values(response: CnMarketResponse) -> bool:
    return bool(response.indices or response.stocks)


def _consume_task_result(task: asyncio.Task[object]) -> None:
    try:
        task.result()
    except (asyncio.CancelledError, Exception):
        pass


async def _run_with_hard_timeout(awaitable: Coroutine[object, object, T], timeout: float) -> T:
    task = asyncio.create_task(awaitable)
    done, _ = await asyncio.wait({task}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    if task in done:
        return await task
    task.add_done_callback(_consume_task_result)
    task.cancel()
    raise TimeoutError("market fetch timeout")


@router.get("/market/us", response_model=MarketResponse)
async def market_us(
    client: Annotated[AkShareClient, Depends(get_akshare_client)],
    cache: Annotated[SQLiteCache, Depends(get_cache)],
) -> MarketResponse:
    cache_key = "market:us"
    cached = await get_cached_response(cache, cache_key, MarketResponse)
    if cached is not None:
        response, is_expired = cached
        if not is_expired:
            return as_fresh(response)

    try:
        items = await client.fetch_us_indices()
        response = MarketResponse(items=items, stale=False, updated_at=_now_iso())
        if not _has_real_market_values(response):
            raise AkShareError("EMPTY_MARKET", "指数行情接口暂不可用")
        market_status = items[0].market_status if items else "closed"
        await cache.set(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=market_ttl_seconds(market_status),
            source_status="ok",
        )
        return response
    except AkShareError:
        if cached is not None:
            return as_stale(cached[0])
        return MarketResponse(items=[], stale=True, updated_at=_now_iso())


@router.get("/market/us/stocks", response_model=StocksResponse)
async def market_us_stocks(
    client: Annotated[AkShareClient, Depends(get_akshare_client)],
    cache: Annotated[SQLiteCache, Depends(get_cache)],
) -> StocksResponse:
    cache_key = "market:us:stocks"
    cached = await get_cached_response(cache, cache_key, StocksResponse)
    if cached is not None:
        response, is_expired = cached
        if not is_expired:
            return as_fresh(response)

    try:
        items = await client.fetch_us_stocks()
        response = StocksResponse(items=items, stale=False, updated_at=_now_iso())
        market_status = items[0].market_status if items else "closed"
        await cache.set(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=market_ttl_seconds(market_status),
            source_status="ok",
        )
        return response
    except AkShareError:
        if cached is not None:
            return as_stale(cached[0])
        return StocksResponse(items=[], stale=True, updated_at=_now_iso())


@router.get("/market/cn", response_model=CnMarketResponse)
async def market_cn(
    client: Annotated[SeeSeaClient, Depends(get_seesea_client)],
    cache: Annotated[SQLiteCache, Depends(get_cache)],
) -> CnMarketResponse:
    cache_key = "market:cn"
    cached = await get_cached_response(cache, cache_key, CnMarketResponse)
    if cached is not None:
        response, is_expired = cached
        if not is_expired:
            return as_stale(response) if response.stale else as_fresh(response)

    try:
        response = await _run_with_hard_timeout(
            client.fetch_cn_market(),
            CN_MARKET_FETCH_TIMEOUT_SECONDS,
        )
        await cache.set(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=market_ttl_seconds("open"),
            source_status="ok",
        )
        return response
    except (SeeSeaError, TimeoutError):
        try:
            snapshot = await _run_with_hard_timeout(
                client.fetch_cn_market_recent_trade_snapshot(),
                CN_MARKET_FETCH_TIMEOUT_SECONDS,
            )
            await cache.set(
                cache_key,
                snapshot.model_dump(mode="json"),
                ttl_seconds=market_ttl_seconds("closed"),
                source_status="stale",
            )
            return snapshot
        except (SeeSeaError, TimeoutError):
            pass

        if cached is not None:
            return as_stale(cached[0])
        return CnMarketResponse(
            indices=[],
            stocks=[],
            analysis=CnMarketAnalysis(fund_flows=[], limit_up=[], limit_down=[]),
            stale=True,
            updated_at=_now_iso(),
        )
