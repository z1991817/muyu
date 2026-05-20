from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health_router, home_router, market_router, sources_router, trends_router
from app.cache.sqlite import SQLiteCache
from app.clients.akshare import AkShareClient
from app.clients.seesea import SeeSeaClient
from app.config import settings
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = SQLiteCache(settings.cache_db_path)
    await cache.init()

    app.state.cache = cache
    app.state.seesea_client = SeeSeaClient()
    app.state.akshare_client = AkShareClient()
    app.state.default_platforms = settings.seesea_default_platforms

    scheduler_task = start_scheduler(app)
    try:
        yield
    finally:
        await stop_scheduler(scheduler_task)
        await app.state.seesea_client.aclose()
        await app.state.akshare_client.aclose()


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
app.include_router(health_router)
