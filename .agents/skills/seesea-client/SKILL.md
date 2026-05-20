---
name: seesea-client
description: 在 backend/app/clients/seesea.py 中新增或修改 SeeSea 接口调用时调用。强制走唯一封装、字段映射、超时、失败兜底，杜绝 SeeSea 字段直通前端或异常向上抛。
---

# seesea-client

## 使命

把 SeeSea 的所有调用收敛到一个文件、一个 client 类、一套字段映射、一套错误兜底——任何 AI 想"快速调一下 SeeSea"必须走这套规范，没有捷径。

## 触发场景

- 用户要新增热榜来源（如雪球、虎扑 → 改 `fetch_multiple` 默认平台清单）
- 用户要接 SeeSea 的新接口（股票行情列表、RSS、搜索）
- 用户报错 SeeSea 字段对不上 / 超时 / 内网泄露
- 用户要给 SeeSea 加重试、加缓存键、加 stale 标记

## 强制阅读

1. SeeSea README：`https://github.com/nostalgiatan/SeeSea`（确认接口路径与字段以当前版本为准）
2. [doc/摸鱼热榜技术选型方案.md](../../../doc/摸鱼热榜技术选型方案.md) §5 SeeSea 接入方案、§6 美股、§8 缓存
3. [backend/AGENTS.md](../../../backend/AGENTS.md) §4 SeeSea 接入硬规则

## 硬规则（违反即拒绝合并）

1. **唯一调用点**：`backend/app/clients/seesea.py`。其它任何文件出现 `httpx.get("http://seesea")` 或 `seesea` 字符串拼 URL 都视为违规。
2. **类型边界**：方法签名只返回 `app/models/` 下定义的统一模型（`Trend / Source / ...`），**禁止**返回 `dict` / `Any` / SeeSea 原始结构。
3. **错误隔离**：内部所有异常统一包装为 `SeeSeaError(code, message)`；`message` 不带任何内网地址、容器名、端口、token。
4. **超时**：`httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0))`，不可设为 `None`。
5. **不要重试无限次**：最多 2 次，间隔 0.5s / 1s，使用 `tenacity` 或手写均可。
6. **不暴露原字段**：哪怕新增字段，也要先在 `models/` 里定义，再让 client 做映射。
7. **配置走 settings**：SeeSea base URL、平台白名单从 `app/config.py` 读取，**禁止**硬编码 `127.0.0.1:8000`。

## 模板代码

```python
# backend/app/clients/seesea.py
from __future__ import annotations

import httpx
from typing import Iterable

from app.config import settings
from app.logging import logger
from app.models.trend import Trend
from app.models.source import Source


class SeeSeaError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SeeSeaClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.seesea_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(8.0, connect=3.0),
            headers={"User-Agent": "moyu-aggregator/0.1"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_multiple(self, platforms: Iterable[str]) -> list[Trend]:
        params = {"platforms": ",".join(platforms), "latest": "true"}
        try:
            resp = await self._client.get("/hot/multiple", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("seesea.fetch_multiple failed", extra={"error": str(e)})
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用") from e

        raw = resp.json()
        return [_map_trend(item) for item in _iter_items(raw)]

    async def fetch_platforms(self) -> list[Source]:
        try:
            resp = await self._client.get("/hot/platforms")
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用") from e
        return [_map_source(item) for item in resp.json()]

    async def fetch_single(self, platform: str) -> list[Trend]:
        try:
            resp = await self._client.get(
                f"/hot/{platform}", params={"latest": "true"}
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SeeSeaError("SEESEA_UPSTREAM", "上游数据源暂不可用") from e
        return [_map_trend(item) for item in resp.json().get("items", [])]


def _iter_items(payload: dict | list) -> Iterable[dict]:
    # SeeSea 多平台响应结构：参考其当前版本 README
    if isinstance(payload, list):
        for entry in payload:
            yield from entry.get("items", [])
    elif isinstance(payload, dict):
        for entry in payload.get("results", []):
            yield from entry.get("items", [])


def _map_trend(raw: dict) -> Trend:
    return Trend(
        platform=raw["platform"],
        platform_name=raw.get("platform_name") or raw.get("platformName") or raw["platform"],
        title=raw["title"],
        url=raw["url"],
        rank=int(raw.get("rank", 0)),
        heat=str(raw.get("heat", "")),
        source=raw.get("source", raw["platform"]),
        updated_at=raw["updated_at"],
    )


def _map_source(raw: dict) -> Source:
    return Source(
        platform=raw["id"],
        platform_name=raw.get("name", raw["id"]),
        category=raw.get("category", "other"),
        updated_at=raw.get("updated_at"),
    )
```

## 路由侧调用模板

```python
# backend/app/api/trends.py
from fastapi import APIRouter, Depends
from app.clients.seesea import SeeSeaClient, SeeSeaError
from app.cache.sqlite import cache_get, cache_put
from app.models.trend import TrendsResponse

router = APIRouter(prefix="/api", tags=["trends"])


def get_seesea() -> SeeSeaClient:
    # 由 lifespan 注入单例，这里只是示例
    ...


@router.get("/trends", response_model=TrendsResponse)
async def list_trends(
    platform: str = "weibo,zhihu,baidu",
    client: SeeSeaClient = Depends(get_seesea),
) -> TrendsResponse:
    cache_key = f"trends:multi:{platform}"
    try:
        trends = await client.fetch_multiple(platform.split(","))
        payload = TrendsResponse(items=trends, stale=False)
        await cache_put(cache_key, payload.model_dump(by_alias=True), ttl_seconds=300)
        return payload
    except SeeSeaError:
        cached = await cache_get(cache_key)
        if cached:
            return TrendsResponse.model_validate(cached).model_copy(update={"stale": True})
        return TrendsResponse(items=[], stale=True)
```

## 自检清单

- [ ] 没有任何 `app/clients/seesea.py` 以外的文件出现 `seesea` 字符串拼接 URL
- [ ] 所有方法返回 `Trend / Source / Index` 之类的统一模型
- [ ] 异常一律 `SeeSeaError`，消息不含内网地址
- [ ] `httpx.AsyncClient` 有 timeout
- [ ] 路由层做了缓存回退，返回 `stale: true` 而不是 5xx
- [ ] 新增平台同步改了 `platforms.py` 映射 + 前端 `lib/platforms.ts` + 规范 §5.4 配色

## 反例

```python
# ❌ 在路由里直接调
@router.get("/trends")
async def list_trends():
    return httpx.get("http://seesea:8000/hot/multiple").json()

# ❌ 把异常往上抛
trends = await client.fetch_multiple(["weibo"])  # 失败就 500

# ❌ 返回 dict
async def fetch_multiple(self, platforms): -> dict
    return resp.json()
```
