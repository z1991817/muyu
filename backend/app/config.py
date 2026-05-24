from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Moyu API"
    app_env: str = "development"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:4321", "http://127.0.0.1:4321"]
    )

    seesea_base_url: str = "http://127.0.0.1:8888"
    seesea_stock_sdk_fallback_enabled: bool = False
    seesea_default_platforms: list[str] = Field(
        default_factory=lambda: [
            "weibo",
            "douyin",
            "kuaishou",
            "bilibili-hot-search",
            "douban",
            "hupu",
            "toutiao",
            "baidu",
            "thepaper",
            "ifeng",
            "tencent-hot",
            "wallstreetcn-hot",
            "cls-hot",
            "jin10",
            "gelonghui",
            "xueqiu-hotstock",
            "github-trending-today",
            "hackernews",
            "producthunt",
            "juejin",
            "sspai",
            "ithome",
            "coolapk",
            "nowcoder",
            "freebuf",
            "steam",
            "zhihu",
            "tieba",
            "36kr-renqi",
            "v2ex",
        ]
    )

    cache_db_path: str = "data/cache.db"
    home_cache_ttl_seconds: int = 60
    trends_cache_ttl_seconds: int = 300
    sources_cache_ttl_seconds: int = 600
    market_open_cache_ttl_seconds: int = 180
    market_closed_cache_ttl_seconds: int = 1800

    market_disclaimer: str = "仅供信息展示，不构成投资建议"
    public_site_url: str = "https://moyu.example.com"

    umami_api_base: str = "https://api.umami.is/v1"
    umami_website_id: str = "5ed62d5d-3114-49cb-85b7-491c0cf277c1"
    umami_api_key: str = ""
    online_cache_ttl_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
