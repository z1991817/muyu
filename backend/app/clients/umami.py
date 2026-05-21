from __future__ import annotations

import httpx
from fastapi import Request

from app.config import settings


class UmamiError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UmamiClient:
    def __init__(self, base_url: str | None = None, website_id: str | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url=(base_url or settings.umami_api_base).rstrip("/"),
            timeout=httpx.Timeout(8.0, connect=3.0),
            headers={"User-Agent": "moyu-aggregator/0.1"},
        )
        self._website_id = (website_id or settings.umami_website_id).strip()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_active_visitors(self) -> int:
        api_key = settings.umami_api_key.strip()
        if not self._website_id or not api_key:
            raise UmamiError("UMAMI_DISABLED", "统计服务暂未配置")

        try:
            response = await self._client.get(
                f"/websites/{self._website_id}/active",
                headers={"x-umami-api-key": api_key},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UmamiError("UMAMI_UPSTREAM", "统计服务暂不可用") from exc

        if not isinstance(payload, dict):
            raise UmamiError("UMAMI_PAYLOAD", "统计服务返回异常")

        visitors = payload.get("visitors")
        if isinstance(visitors, int) and not isinstance(visitors, bool):
            return visitors

        legacy_visitors = payload.get("x")
        if isinstance(legacy_visitors, int) and not isinstance(legacy_visitors, bool):
            return legacy_visitors

        raise UmamiError("UMAMI_PAYLOAD", "统计服务返回异常")


def get_umami_client(request: Request) -> UmamiClient:
    return request.app.state.umami_client
