from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.cache.policy import as_fresh, as_stale, get_cached_response, market_ttl_seconds
from app.cache.sqlite import SQLiteCache
from app.clients.akshare import AkShareClient, AkShareError
from app.models.market import MarketResponse, StocksResponse

router = APIRouter(tags=["market"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_cache(request: Request) -> SQLiteCache:
    return request.app.state.cache


def get_akshare_client(request: Request) -> AkShareClient:
    return request.app.state.akshare_client


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
