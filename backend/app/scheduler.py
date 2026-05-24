from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, time
from typing import Protocol

from app.cache.policy import market_ttl_seconds
from app.cache.sqlite import SQLiteCache
from app.clients.akshare import AkShareClient, AkShareError
from app.clients.seesea import SeeSeaClient, SeeSeaError
from app.config import settings
from app.lib.china_holidays import get_china_rest_day_info
from app.models.cn_market import CnMarketResponse
from app.models.home import HomeResponse
from app.models.market import MarketResponse, StocksResponse
from app.models.source import Source, SourcesResponse
from app.models.trend import TrendsResponse
from app.platforms import PLATFORMS

logger = logging.getLogger(__name__)

INITIAL_REFRESH_DELAY_SECONDS = 10
CN_MARKET_REFRESH_TIMEOUT_SECONDS = 25


class CnMarketFetcher(Protocol):
    async def fetch_cn_market(self) -> CnMarketResponse: ...

    async def fetch_cn_market_recent_trade_snapshot(self) -> CnMarketResponse: ...


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _market_open() -> bool:
    """美东夏令时 UTC-4: 开盘 13:30，收盘 20:00。"""
    t = datetime.now(UTC).time()
    return time(13, 30) <= t <= time(20, 0)


def _refresh_interval() -> int:
    """交易时段 3 分钟，非交易时段 30 分钟。"""
    return 180 if _market_open() else 1800


async def _refresh_trends(
    seesea: SeeSeaClient,
    cache: SQLiteCache,
    default_platforms: list[str],
) -> TrendsResponse | None:
    cache_key = f"trends:multi:{','.join(default_platforms)}"
    try:
        items = await seesea.fetch_multiple(default_platforms)
        response = TrendsResponse(items=items, stale=False, updated_at=_now_iso())
        await cache.set(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=settings.trends_cache_ttl_seconds,
            source_status="ok",
        )
        logger.info("scheduler: trends refreshed (%d items)", len(items))
        return response
    except SeeSeaError as e:
        logger.warning("scheduler: trends refresh failed: %s", e)
        return None


async def _refresh_sources(
    seesea: SeeSeaClient,
    cache: SQLiteCache,
) -> SourcesResponse | None:
    try:
        items = await seesea.fetch_platforms()
        if not items:
            items = [
                Source(
                    platform=meta.platform,
                    platform_name=meta.platform_name,
                    status="ok",
                    updated_at=_now_iso(),
                )
                for meta in PLATFORMS.values()
            ]
        response = SourcesResponse(items=items, stale=False, updated_at=_now_iso())
        await cache.set(
            "sources:list",
            response.model_dump(mode="json"),
            ttl_seconds=settings.sources_cache_ttl_seconds,
            source_status="ok",
        )
        logger.info("scheduler: sources refreshed (%d items)", len(items))
        return response
    except SeeSeaError as e:
        logger.warning("scheduler: sources refresh failed: %s", e)
        return None


async def _refresh_market(
    akshare: AkShareClient,
    cache: SQLiteCache,
) -> MarketResponse | None:
    try:
        items = await akshare.fetch_us_indices()
        response = MarketResponse(items=items, stale=False, updated_at=_now_iso())
        market_status = items[0].market_status if items else "closed"
        await cache.set(
            "market:us",
            response.model_dump(mode="json"),
            ttl_seconds=market_ttl_seconds(market_status),
            source_status="ok",
        )
        logger.info("scheduler: market indices refreshed (%d items)", len(items))
        return response
    except AkShareError as e:
        logger.warning("scheduler: market refresh failed: %s", e)
        return None


async def _refresh_stocks(
    akshare: AkShareClient,
    cache: SQLiteCache,
) -> StocksResponse | None:
    try:
        items = await akshare.fetch_us_stocks()
        response = StocksResponse(items=items, stale=False, updated_at=_now_iso())
        market_status = items[0].market_status if items else "closed"
        await cache.set(
            "market:us:stocks",
            response.model_dump(mode="json"),
            ttl_seconds=market_ttl_seconds(market_status),
            source_status="ok",
        )
        logger.info("scheduler: hot stocks refreshed (%d items)", len(items))
        return response
    except AkShareError as e:
        logger.warning("scheduler: stocks refresh failed: %s", e)
        return None


async def _refresh_cn_market(
    seesea: CnMarketFetcher,
    cache: SQLiteCache,
) -> CnMarketResponse | None:
    try:
        response = await asyncio.wait_for(
            seesea.fetch_cn_market(),
            timeout=CN_MARKET_REFRESH_TIMEOUT_SECONDS,
        )
        await cache.set(
            "market:cn",
            response.model_dump(mode="json"),
            ttl_seconds=market_ttl_seconds("open"),
            source_status="ok",
        )
        logger.info(
            "scheduler: cn market refreshed (%d indices, %d stocks)",
            len(response.indices),
            len(response.stocks),
        )
        return response
    except SeeSeaError as e:
        logger.warning("scheduler: cn market refresh failed: %s", e)
    except TimeoutError:
        logger.warning("scheduler: cn market refresh timed out")

    try:
        snapshot = await asyncio.wait_for(
            seesea.fetch_cn_market_recent_trade_snapshot(),
            timeout=CN_MARKET_REFRESH_TIMEOUT_SECONDS,
        )
        await cache.set(
            "market:cn",
            snapshot.model_dump(mode="json"),
            ttl_seconds=market_ttl_seconds("closed"),
            source_status="stale",
        )
        logger.info(
            "scheduler: cn market snapshot refreshed (%d indices, %d stocks)",
            len(snapshot.indices),
            len(snapshot.stocks),
        )
        return snapshot
    except SeeSeaError as e:
        logger.warning("scheduler: cn market snapshot refresh failed: %s", e)
        return None
    except TimeoutError:
        logger.warning("scheduler: cn market snapshot refresh timed out")
        return None


async def _refresh_all(
    seesea: SeeSeaClient,
    akshare: AkShareClient,
    cache: SQLiteCache,
    default_platforms: list[str],
) -> None:
    (
        trends_result,
        sources_result,
        market_result,
        _stocks_result,
        _cn_market_result,
    ) = await asyncio.gather(
        _refresh_trends(seesea, cache, default_platforms),
        _refresh_sources(seesea, cache),
        _refresh_market(akshare, cache),
        _refresh_stocks(akshare, cache),
        _refresh_cn_market(seesea, cache),
        return_exceptions=True,
    )

    if (
        isinstance(trends_result, TrendsResponse)
        and isinstance(sources_result, SourcesResponse)
        and isinstance(market_result, MarketResponse)
    ):
        response = HomeResponse(
            trends=trends_result.items,
            sources=sources_result.items,
            markets=market_result.items,
            calendar=get_china_rest_day_info(),
            stale=False,
            updated_at=_now_iso(),
        )
        await cache.set(
            "home",
            response.model_dump(mode="json"),
            ttl_seconds=settings.home_cache_ttl_seconds,
            source_status="ok",
        )
        logger.info("scheduler: home refreshed")


async def run_refresh_loop(app) -> None:  # type: ignore[no-untyped-def]
    cache: SQLiteCache = app.state.cache
    seesea: SeeSeaClient = app.state.seesea_client
    akshare: AkShareClient = app.state.akshare_client
    default_platforms: list[str] = app.state.default_platforms

    await asyncio.sleep(INITIAL_REFRESH_DELAY_SECONDS)
    await _refresh_all(seesea, akshare, cache, default_platforms)

    while True:
        interval = _refresh_interval()
        logger.info(
            "scheduler: next refresh in %ds (market %s)",
            interval,
            "open" if _market_open() else "closed",
        )
        await asyncio.sleep(interval)

        await _refresh_all(seesea, akshare, cache, default_platforms)


def start_scheduler(app) -> asyncio.Task[None]:  # type: ignore[no-untyped-def]
    return asyncio.create_task(run_refresh_loop(app))


async def stop_scheduler(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
