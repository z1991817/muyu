from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.cache.policy import as_fresh, as_stale, get_cached_response
from app.cache.sqlite import SQLiteCache
from app.clients.umami import UmamiClient, UmamiError, get_umami_client
from app.config import settings
from app.models.online import OnlineResponse

router = APIRouter(tags=["online"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_cache(request: Request) -> SQLiteCache:
    return request.app.state.cache


@router.get("/online", response_model=OnlineResponse)
async def get_online_visitors(
    client: Annotated[UmamiClient, Depends(get_umami_client)],
    cache: Annotated[SQLiteCache, Depends(get_cache)],
) -> OnlineResponse:
    cache_key = "online:umami"
    cached = await get_cached_response(cache, cache_key, OnlineResponse)
    if cached is not None:
        response, is_expired = cached
        if not is_expired:
            return as_fresh(response)

    try:
        response = OnlineResponse(
            visitors=await client.fetch_active_visitors(),
            stale=False,
            updated_at=_now_iso(),
        )
        await cache.set(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=settings.online_cache_ttl_seconds,
            source_status="ok",
        )
        return response
    except UmamiError:
        if cached is not None:
            return as_stale(cached[0])
        return OnlineResponse(visitors=None, stale=True, updated_at=_now_iso())
