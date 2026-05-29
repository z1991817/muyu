from app.api.ai_news import router as ai_news_router
from app.api.health import router as health_router
from app.api.home import router as home_router
from app.api.market import router as market_router
from app.api.online import router as online_router
from app.api.sources import router as sources_router
from app.api.trends import router as trends_router

__all__ = [
    "ai_news_router",
    "home_router",
    "trends_router",
    "sources_router",
    "market_router",
    "online_router",
    "health_router",
]
