from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_home_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/home")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert payload["calendar"]["date"]
    assert isinstance(payload["calendar"]["isRestDay"], bool)
    assert payload["calendar"]["kind"] in {"holiday", "weekend", "workday"}
    assert len(payload["trends"]) > 0
    assert len(payload["sources"]) > 0
    assert len(payload["markets"]) > 0
    assert payload["markets"][0]["disclaimer"] == "仅供信息展示，不构成投资建议"


@pytest.mark.asyncio
async def test_home_uses_fresh_cache(client: AsyncClient, test_app) -> None:
    response = await client.get("/api/home")
    assert response.status_code == 200

    class FailSeeSeaClient:
        async def fetch_multiple(self, platforms: list[str]) -> list[object]:
            raise AssertionError("fresh home cache should avoid SeeSea")

        async def fetch_platforms(self) -> list[object]:
            raise AssertionError("fresh home cache should avoid SeeSea")

    class FailAkShareClient:
        async def fetch_us_indices(self) -> list[object]:
            raise AssertionError("fresh home cache should avoid AkShare")

    test_app.state.seesea_client = FailSeeSeaClient()
    test_app.state.akshare_client = FailAkShareClient()

    cached_response = await client.get("/api/home")
    assert cached_response.status_code == 200
    assert cached_response.json()["stale"] is False


@pytest.mark.asyncio
async def test_trends_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/trends")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert len(payload["items"]) > 0
    assert payload["items"][0]["platform"]
    assert payload["items"][0]["platformName"]
    assert payload["items"][0]["updatedAt"]


@pytest.mark.asyncio
async def test_sources_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/sources")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert len(payload["items"]) > 0
    assert payload["items"][0]["platform"]
    assert payload["items"][0]["platformName"]
    assert payload["items"][0]["updatedAt"]


@pytest.mark.asyncio
async def test_market_us_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/market/us")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert len(payload["items"]) > 0
    assert payload["items"][0]["symbol"]
    assert payload["items"][0]["url"].startswith(
        "https://stock.finance.sina.com.cn/usstock/quotes/"
    )
    assert payload["items"][0]["disclaimer"] == "仅供信息展示，不构成投资建议"


@pytest.mark.asyncio
async def test_market_cn_happy_path(client: AsyncClient, test_app) -> None:
    from app.scheduler import _refresh_cn_market

    await _refresh_cn_market(test_app.state.cn_market_client, test_app.state.cache)

    response = await client.get("/api/market/cn")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["stocks"][0]["symbol"] == "600500"
    assert payload["analysis"]["fundFlows"][0]["name"] == "上涨家数"
    assert payload["analysis"]["limitUp"] == []
    assert payload["analysis"]["limitDown"] == []
    assert payload["analysis"]["topGainers"][0]["reason"] == "涨幅靠前"
    assert payload["analysis"]["topLosers"][0]["reason"] == "跌幅靠前"


@pytest.mark.asyncio
async def test_hot_sdk_fallback_is_disabled_by_default() -> None:
    from app.clients.seesea import SeeSeaClient, SeeSeaError

    class FailingHotTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"error": "unavailable"}, request=request)

    class FailIfCalledHotClient:
        def fetch_multiple_platforms(self, platforms: list[str]) -> object:
            raise AssertionError("hot SDK fallback should be opt-in")

    seesea = SeeSeaClient(base_url="http://test-seesea")
    await seesea._client.aclose()
    seesea._client = httpx.AsyncClient(
        base_url="http://test-seesea",
        transport=FailingHotTransport(),
    )
    seesea._sdk_client = FailIfCalledHotClient()

    with pytest.raises(SeeSeaError):
        await seesea.fetch_multiple(["weibo"])

    await seesea.aclose()


@pytest.mark.asyncio
async def test_market_cn_reads_expired_cache_as_stale(client: AsyncClient, test_app) -> None:
    import sqlite3
    from datetime import UTC, datetime, timedelta

    from app.cache.policy import market_ttl_seconds

    cached_payload = await test_app.state.cn_market_client.fetch_cn_market()
    cached_payload = cached_payload.model_copy(update={"updated_at": "2026-05-24T00:00:00+00:00"})
    await test_app.state.cache.set(
        "market:cn",
        cached_payload.model_dump(mode="json"),
        ttl_seconds=market_ttl_seconds("open"),
        source_status="ok",
    )
    conn = sqlite3.connect(test_app.state.cache._db_path.as_posix())
    conn.execute(
        "UPDATE cache_entries SET expires_at = ? WHERE key = ?",
        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), "market:cn"),
    )
    conn.commit()
    conn.close()

    class FailIfCalledSeeSeaClient:
        async def aclose(self) -> None:
            return None

    test_app.state.seesea_client = FailIfCalledSeeSeaClient()

    response = await client.get("/api/market/cn")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale"] is True
    assert payload["staleReason"] == "CN_MARKET_CACHE_EXPIRED"
    assert payload["updatedAt"] == "2026-05-24T00:00:00+00:00"
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["stocks"][0]["symbol"] == "600500"


@pytest.mark.asyncio
async def test_market_cn_returns_empty_stale_payload_without_cache(
    client: AsyncClient, test_app
) -> None:
    class FailIfCalledSeeSeaClient:
        async def aclose(self) -> None:
            return None

    test_app.state.seesea_client = FailIfCalledSeeSeaClient()

    response = await client.get("/api/market/cn")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale"] is True
    assert payload["indices"] == []
    assert payload["stocks"] == []
    assert payload["analysis"]["fundFlows"] == []
    assert payload["analysis"]["limitUp"] == []
    assert payload["analysis"]["limitDown"] == []


@pytest.mark.asyncio
async def test_market_cn_deletes_legacy_cache_payload(client: AsyncClient, test_app) -> None:
    from app.models.cn_market import CnMarketAnalysis, CnMarketResponse

    legacy_payload = CnMarketResponse(
        indices=[],
        stocks=[],
        analysis=CnMarketAnalysis(fund_flows=[], limit_up=[], limit_down=[]),
        source="seesea",
        stale=False,
        updated_at="2026-05-24T00:00:00+00:00",
    )
    await test_app.state.cache.set(
        "market:cn",
        legacy_payload.model_dump(mode="json"),
        ttl_seconds=60,
        source_status="ok",
    )

    response = await client.get("/api/market/cn")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "opentdx"
    assert payload["stale"] is True
    assert payload["staleReason"] == "NO_CN_MARKET_SNAPSHOT"
    assert await test_app.state.cache.get("market:cn") is None


@pytest.mark.asyncio
async def test_refresh_all_skips_cn_market_by_default(
    test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import scheduler
    from app.config import settings

    async def fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("cn market should be refreshed by the standalone job")

    monkeypatch.setattr(settings, "cn_market_scheduler_enabled", False)
    monkeypatch.setattr(scheduler, "_refresh_cn_market", fail_if_called)

    await scheduler._refresh_all(
        test_app.state.seesea_client,
        test_app.state.akshare_client,
        test_app.state.cn_market_client,
        test_app.state.cache,
        test_app.state.default_platforms,
    )

    assert await test_app.state.cache.get("market:cn") is None


def test_cn_market_refresh_interval_tracks_trading_hours() -> None:
    from datetime import UTC, datetime

    from app.scheduler import cn_market_refresh_interval_seconds

    assert cn_market_refresh_interval_seconds(datetime(2026, 5, 26, 2, 0, tzinfo=UTC)) == 180
    assert cn_market_refresh_interval_seconds(datetime(2026, 5, 26, 4, 0, tzinfo=UTC)) == 1800
    assert cn_market_refresh_interval_seconds(datetime(2026, 5, 26, 6, 0, tzinfo=UTC)) == 180
    assert cn_market_refresh_interval_seconds(datetime(2026, 5, 30, 2, 0, tzinfo=UTC)) == 1800


@pytest.mark.asyncio
async def test_cn_market_job_writes_cache(
    client: AsyncClient, test_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.jobs import refresh_cn_market

    monkeypatch.setattr(
        refresh_cn_market.settings, "cache_db_path", test_app.state.cache._db_path.as_posix()
    )
    monkeypatch.setattr(
        "app.jobs.refresh_cn_market.TdxMarketClient",
        lambda: test_app.state.cn_market_client,
    )

    await test_app.state.cache.set(
        "market:cn",
        {
            "indices": [],
            "stocks": [],
            "analysis": {"fundFlows": [], "limitUp": [], "limitDown": []},
            "source": "seesea",
            "updatedAt": "2026-05-24T00:00:00+00:00",
        },
        ttl_seconds=60,
        source_status="ok",
    )

    exit_code = await refresh_cn_market.refresh_once(purge=True)

    assert exit_code == 0
    cached = await test_app.state.cache.get("market:cn")
    assert cached is not None
    assert cached[0]["source"] == "opentdx"
    response = await client.get("/api/market/cn")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale"] is False
    assert payload["indices"][0]["name"] == "上证指数"
    assert payload["stocks"][0]["symbol"] == "600500"
    assert payload["analysis"]["fundFlows"][0]["name"] == "上涨家数"


@pytest.mark.asyncio
async def test_online_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/online")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is False
    assert payload["updatedAt"]
    assert payload["visitors"] == 12


@pytest.mark.asyncio
async def test_ai_news_happy_path(client: AsyncClient) -> None:
    response = await client.get("/api/ai-news?date=2026-05-27")
    assert response.status_code == 200

    payload = response.json()
    assert payload["date"] == "2026-05-27"
    assert payload["stale"] is False
    assert payload["groups"][0]["category"] == "产品与功能更新"
    assert payload["groups"][0]["categoryKey"] == "product"
    assert payload["groups"][0]["items"][0]["url"].startswith("https://huggingface.co/")


def test_ai_news_parser_reads_hex2077_daily_sections() -> None:
    from app.clients.ai_news_fetcher import parse_markdown

    markdown = "\n".join(
        [
            "## **今日摘要**",
            "```",
            "今天的摘要不应该作为资讯卡片展示。",
            "```",
            "### 产品与功能更新",
            (
                "1. **正式发布 stable audio 3 权重。** "
                "该系列模型已上线 [最新音频权重合集(ai资讯)]"
                "(https://huggingface.co/collections/stabilityai/stable-audio-3) 中。"
                "![配图](https://source.hex2077.dev/images/demo.avif)"
            ),
            "### 前沿研究",
            (
                "1. **surgicalmamba 系统大幅提升手术安全。** "
                "详见 [手术智能识别模型(ai资讯)](https://arxiv.org/abs/2605.14889) 报告。"
            ),
        ]
    )

    groups = parse_markdown(markdown)

    assert groups[0]["category"] == "产品与功能更新"
    assert groups[0]["category_key"] == "product"
    assert groups[0]["items"][0]["title"] == "正式发布 stable audio 3 权重。"
    assert (
        groups[0]["items"][0]["url"]
        == "https://huggingface.co/collections/stabilityai/stable-audio-3"
    )
    assert groups[0]["items"][0]["source"] == "最新音频权重合集"
    assert groups[1]["category"] == "前沿研究"


@pytest.mark.asyncio
async def test_ai_news_fetcher_force_refreshes_future_date_when_cache_misses() -> None:
    from app.clients.ai_news_fetcher import AiNewsFetcher

    calls = 0

    class SearchIndexTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            payload = [
                {
                    "slug": "2999-01/2999-01-01",
                    "title": "2999-01-01 AI 日报",
                    "type": "docs",
                    "content": (
                        "### 产品与功能更新\n"
                        "1. **未来日报已更新。** "
                        "[未来来源(ai资讯)](https://example.com/future)"
                    ),
                }
            ]
            if calls == 1:
                payload = []
            return httpx.Response(200, json=payload, request=request)

    fetcher = AiNewsFetcher()
    await fetcher._client.aclose()
    fetcher._client = httpx.AsyncClient(transport=SearchIndexTransport())
    try:
        groups = await fetcher.fetch_date("2999-01-01")
    finally:
        await fetcher.aclose()

    assert calls == 2
    assert groups[0]["category"] == "产品与功能更新"
    assert groups[0]["items"][0]["title"] == "未来日报已更新。"


@pytest.mark.asyncio
async def test_market_us_has_items_when_upstream_fails(client: AsyncClient, test_app) -> None:
    from app.clients.akshare import AkShareError

    class FailAkShareClient:
        async def fetch_us_indices(self) -> list[object]:
            raise AkShareError("AKSHARE_UPSTREAM", "mock fail")

    test_app.state.akshare_client = FailAkShareClient()

    response = await client.get("/api/market/us")
    assert response.status_code == 200

    payload = response.json()
    assert payload["stale"] is True
    assert payload["items"] == []


@pytest.mark.asyncio
async def test_market_us_does_not_cache_zero_fallback(client: AsyncClient, test_app) -> None:
    from app.models.market import MarketIndex

    class ZeroFallbackAkShareClient:
        async def fetch_us_indices(self) -> list[object]:
            return [
                MarketIndex(
                    symbol="SPX",
                    name="S&P 500",
                    price=0.0,
                    change=0.0,
                    change_pct=0.0,
                    url="https://stock.finance.sina.com.cn/usstock/quotes/.INX.html",
                    market_status="closed",
                    trade_date="2026-05-24",
                    updated_at="2026-05-24T00:00:00+00:00",
                    disclaimer="仅供信息展示，不构成投资建议",
                )
            ]

    test_app.state.akshare_client = ZeroFallbackAkShareClient()

    response = await client.get("/api/market/us")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale"] is True
    assert payload["items"] == []


@pytest.mark.asyncio
async def test_akshare_client_fallback_returns_items() -> None:
    from app.clients.akshare import AkShareClient

    client = AkShareClient()
    items = client._fallback_indices(status="closed")

    assert len(items) == 5
    assert items[0].symbol
    assert all(
        item.url.startswith("https://stock.finance.sina.com.cn/usstock/quotes/") for item in items
    )
    assert items[0].disclaimer == "仅供信息展示，不构成投资建议"


@pytest.mark.asyncio
async def test_akshare_client_parses_us_indices_payload() -> None:
    from app.clients.akshare import _parse_sina

    payload = (
        'var hq_str_gb_$inx="标普500指数,7473.4702,0.37,2026-05-23 04:45:23,'
        '27.7500";\n'
        'var hq_str_gb_$dji="道琼斯,50579.6992,0.58,2026-05-23 04:45:23,'
        '294.0400";\n'
        'var hq_str_gb_$ixic="纳斯达克,26343.9700,0.19,2026-05-23 04:45:23,'
        '50.8700";'
    )
    items = _parse_sina(payload, "closed")

    assert len(items) == 3
    assert [(item.symbol, item.price) for item in items] == [
        ("SPX", 7473.47),
        ("DJI", 50579.7),
        ("IXIC", 26343.97),
    ]
