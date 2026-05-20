# backend/AGENTS.md · FastAPI 后端规范

> 根规范见 [../AGENTS.md](../AGENTS.md)。本文件只写后端独有的细则。

## 1. 技术栈

```
Python 3.11+
FastAPI
Pydantic v2 + pydantic-settings
httpx (异步)
APScheduler 或 FastAPI lifespan 后台任务
sqlite3 / aiosqlite
ruff (lint + format)
pyright 或 mypy (type check)
pytest + pytest-asyncio
uvicorn (--workers 2)
uv 或 pip-tools（依赖管理）
```

后端使用 FastAPI 时，必须遵循 `.agents/skills/fastapi-templates/SKILL.md` 的工程化约束；若与根 `AGENTS.md` 或本文件冲突，以根 `AGENTS.md` 与本文件为准。

**禁止**：Django、Flask、Tornado、SQLAlchemy、Alembic、Celery、Kafka、PostgreSQL、MongoDB、Redis（第一版）。

## 2. 目录约定

```
backend/
├── pyproject.toml
├── README.md
├── .env.example
├── app/
│   ├── __init__.py
│   ├── main.py                  ← FastAPI 实例 + lifespan
│   ├── config.py                ← pydantic-settings
│   ├── api/
│   │   ├── __init__.py
│   │   ├── home.py              ← /api/home
│   │   ├── trends.py            ← /api/trends · /api/trends/{platform}
│   │   ├── sources.py           ← /api/sources
│   │   ├── market.py            ← /api/market/us
│   │   └── health.py            ← /healthz
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── seesea.py            ← 唯一允许调 SeeSea 的模块
│   │   └── akshare.py           ← 美股指数
│   ├── models/
│   │   ├── __init__.py
│   │   ├── common.py            ← BaseModel 配置 (alias_generator=camelize)
│   │   ├── trend.py             ← Trend / TrendsResponse
│   │   ├── source.py            ← Source / SourcesResponse
│   │   ├── market.py            ← Index / MarketResponse
│   │   └── home.py              ← HomeResponse
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── sqlite.py            ← cache_entries 表 CRUD
│   │   └── policy.py            ← TTL / 失败回退策略
│   ├── scheduler.py             ← APScheduler 定时刷新
│   ├── platforms.py             ← 平台 ID → 显示名 / 色卡映射（与前端同步）
│   └── logging.py
└── tests/
    ├── conftest.py
    ├── test_clients_seesea.py
    ├── test_cache.py
    └── test_api_home.py
```

## 3. 命名约束

- 类型注解：公共函数与路由 100% 标注，禁止 `Any`（除非边界确实需要，并写 `# 边界:` 注释）。
- 异步：路由处理函数一律 `async def`；外部 IO 一律走 `httpx.AsyncClient`。
- 文件：snake_case；类：CapWords；常量：UPPER_SNAKE。
- API 响应：camelCase（由 Pydantic `alias_generator` 完成）。Python 内部：snake_case。
- 错误码：自定义 `ErrorCode(StrEnum)`，避免散落字符串。

## 4. SeeSea 接入硬规则

**唯一调用点**：`app/clients/seesea.py`，对外只暴露 `SeeSeaClient` 类。

```python
class SeeSeaClient:
    async def fetch_multiple(self, platforms: list[str]) -> list[Trend]:
        # 内部调 GET /hot/multiple?platforms=...
        # 必须把 SeeSea 原字段映射为统一 Trend 模型
        # 失败必须抛 SeeSeaError，并由调用方决定走缓存回退
        ...

    async def fetch_platforms(self) -> list[Source]:
        ...

    async def fetch_single(self, platform: str) -> list[Trend]:
        ...
```

红线：
- ❌ 不许在 `app/api/*` 里 `httpx.get(seesea_url)`。
- ❌ 不许把 SeeSea 原始 JSON 透传到响应。
- ❌ 不许在错误信息里暴露 SeeSea 内网地址、容器名、端口。
- ✅ SeeSea 调用必须设超时（推荐 `httpx.Timeout(8.0, connect=3.0)`）。
- ✅ 单个平台失败 → 跳过该平台、其它继续；全失败 → 返回最近缓存并 `stale=True`。

## 5. 缓存策略

SQLite 表：

```sql
CREATE TABLE cache_entries (
  key         TEXT PRIMARY KEY,
  payload     TEXT NOT NULL,         -- JSON
  updated_at  TEXT NOT NULL,         -- ISO 8601
  expires_at  TEXT NOT NULL,
  source_status TEXT NOT NULL        -- ok | stale | failed
);
```

TTL 规则（不可随意改）：

| key 模式 | TTL |
|---|---|
| `trends:{platform}` | 5–10 分钟 |
| `trends:multi:{hash}` | 5 分钟 |
| `market:us` | 交易时段 1–3 分钟 / 非交易时段 15–30 分钟 |
| `home` | 30–60 秒短缓存 |

失败兜底：所有外部失败必须返回旧缓存，响应里带 `stale: true` + `updatedAt` 原始时间。**禁止**直接返回 5xx。

## 6. Pydantic 边界

```python
# app/models/common.py
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class APIModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
```

所有响应模型继承 `APIModel`。**禁止**单独为某个字段加 `Field(alias=...)` 除非必须。

## 7. 安全 & 合规

- 路由用 `pydantic-settings` 控制 CORS：只允许配置中的前端域名。
- `/healthz` 不暴露版本、依赖、内网信息，只返回 `{"status": "ok"}`。
- 错误响应统一：`{"error": "human readable", "code": "MACHINE_CODE"}`，**不带** stack trace。
- 日志：结构化 JSON，敏感字段（如 SeeSea URL）写入前 mask。
- 美股响应必须带 `disclaimer: "仅供信息展示，不构成投资建议"`。

## 8. 验证

```bash
ruff check . && ruff format --check .
pyright           # 或 mypy app
pytest -q
uvicorn app.main:app --reload
curl http://127.0.0.1:8000/api/home | jq .
```

提交前必须全部通过。新功能至少补 happy path 测试。
