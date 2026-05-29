from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai_news_router,
    health_router,
    home_router,
    market_router,
    online_router,
    sources_router,
    trends_router,
)
from app.cache.sqlite import SQLiteCache
from app.clients.ai_news_fetcher import AiNewsFetcher
from app.clients.akshare import AkShareClient
from app.clients.cn_market import CnMarketClient
from app.clients.seesea import SeeSeaClient
from app.clients.umami import UmamiClient
from app.config import settings
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = SQLiteCache(settings.cache_db_path)
    await cache.init()

    app.state.cache = cache
    app.state.seesea_client = SeeSeaClient(
        enable_stock_sdk_fallback=settings.seesea_stock_sdk_fallback_enabled
    )
    app.state.akshare_client = AkShareClient()
    app.state.cn_market_client = CnMarketClient()
    app.state.umami_client = UmamiClient()
    app.state.ai_news_fetcher = AiNewsFetcher()
    app.state.default_platforms = settings.seesea_default_platforms

    scheduler_task = start_scheduler(app)
    try:
        yield
    finally:
        await stop_scheduler(scheduler_task)
        await app.state.seesea_client.aclose()
        await app.state.akshare_client.aclose()
        await app.state.cn_market_client.aclose()
        await app.state.umami_client.aclose()
        await app.state.ai_news_fetcher.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(home_router, prefix=settings.api_prefix)
app.include_router(trends_router, prefix=settings.api_prefix)
app.include_router(sources_router, prefix=settings.api_prefix)
app.include_router(market_router, prefix=settings.api_prefix)
app.include_router(online_router, prefix=settings.api_prefix)
app.include_router(ai_news_router, prefix=settings.api_prefix)
app.include_router(health_router)
