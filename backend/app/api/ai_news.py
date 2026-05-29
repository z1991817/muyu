from __future__ import annotations

import re
from datetime import UTC, datetime
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.cache.policy import as_fresh, as_stale, get_cached_response
from app.cache.sqlite import SQLiteCache
from app.clients.ai_news_fetcher import AiNewsFetcher, AiNewsFetchError
from app.models.ai_news import AiNewsGroup, AiNewsItem, AiNewsResponse

router = APIRouter(tags=["ai-news"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Past dates don't change; today may be updated during the day
_TTL_PAST = 7 * 24 * 3600  # 7 days
_TTL_TODAY = 6 * 3600  # 6 hours


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ttl(date_str: str) -> int:
    today = date_type.today().isoformat()
    return _TTL_TODAY if date_str >= today else _TTL_PAST


def get_cache(request: Request) -> SQLiteCache:
    return request.app.state.cache


def get_fetcher(request: Request) -> AiNewsFetcher:
    return request.app.state.ai_news_fetcher


def _build_response(date_str: str, raw_groups: list[dict], stale: bool) -> AiNewsResponse:
    groups = [
        AiNewsGroup(
            category=g["category"],
            category_key=g["category_key"],
            items=[AiNewsItem(**item) for item in g["items"]],
        )
        for g in raw_groups
    ]
    return AiNewsResponse(
        date=date_str,
        groups=groups,
        stale=stale,
        updated_at=_now_iso(),
    )


@router.get("/ai-news", response_model=AiNewsResponse)
async def get_ai_news(
    cache: Annotated[SQLiteCache, Depends(get_cache)],
    fetcher: Annotated[AiNewsFetcher, Depends(get_fetcher)],
    date: str = Query(default="", description="YYYY-MM-DD"),
) -> AiNewsResponse:
    if not date:
        date = date_type.today().isoformat()

    if not _DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    cache_key = f"ai-news:v2:{date}"
    cached = await get_cached_response(cache, cache_key, AiNewsResponse)
    if cached is not None:
        response, is_expired = cached
        if not is_expired:
            return as_fresh(response)

    try:
        raw_groups = await fetcher.fetch_date(date)
        response = _build_response(date, raw_groups, stale=False)
        if raw_groups:
            await cache.set(
                cache_key,
                response.model_dump(mode="json"),
                ttl_seconds=_ttl(date),
                source_status="ok",
            )
        return response
    except AiNewsFetchError:
        if cached is not None:
            return as_stale(cached[0])
        return _build_response(date, [], stale=True)
