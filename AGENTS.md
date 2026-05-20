# 摸鱼热榜 · AI 开发规范（AGENTS.md）

> 本文件是项目对所有 AI 编程助手的**统一指令源**。
>
> - **Codex**：自动加载根目录 `AGENTS.md`。
> - **Claude Code**：通过根目录 `CLAUDE.md` 用 `@AGENTS.md` 引用，等效加载。
> - 任何 AI 在本仓库写代码前，必须先把本文件读完。

技术栈锁定：**Astro 5 + TypeScript（前端）· FastAPI + Pydantic v2 + httpx（后端）· SeeSea（内网采集）· AkShare（美股补充）· SQLite（缓存）**。

---

## 0. 三句话立场

1. **本项目是公开榜单链接聚合器**，不是新闻站、不是资讯站。永远只保留：标题、原站链接、平台、排名、热度、更新时间。**禁止**抓正文、缓存图片、做 AI 摘要、做评论区。
2. **SeeSea 是内网数据源**，对外永远不暴露。前端永远不直连 SeeSea，必须经 FastAPI 一层清洗与字段映射。
3. **设计上 Riso/Zine 风格已经定稿**，见 [doc/摸鱼热榜-趣味Riso风格设计规范.md](doc/摸鱼热榜-趣味Riso风格设计规范.md)。所有前端 UI 必须沿用该规范，禁止重选风格、禁止引入额外 UI 库。

---

## 1. 技术栈红线（违反即拒绝）

### 1.1 前端
- ✅ 必须用：Astro 5、TypeScript、原生 CSS（或 CSS Modules / Tailwind v4）。
- ✅ 前端 TypeScript 开发必须遵循 `.agents/skills/typescript-advanced-types/SKILL.md`（如与本仓库规范冲突，以本文件与 `frontend/AGENTS.md` 为准）。
- ✅ 字体：Google Fonts 加载 Bagel Fat One / Fraunces / Ma Shan Zheng / Space Mono / ZCOOL KuaiLe，**不许换字体**。
- ✅ 颜色：必须使用 `doc/摸鱼热榜-趣味Riso风格设计规范.md` §1 中的 CSS Variables（`--paper`、`--ink`、`--pink` 等），**禁止自创近似色**。
- ❌ 禁止引入：Next.js、Nuxt、Vue、React Router、Remix、SvelteKit、Vite-only SPA、Element Plus、Ant Design、Material UI、Chakra UI、DaisyUI、shadcn/ui、Bootstrap。
- ❌ 禁止在 CSS 里出现：纯白底（`#FFFFFF` / `#FFF` / `white` 作为页面/卡片底色）、带 blur 的 `box-shadow`、线性/径向渐变填充卡片（仅 body 底层氛围渐变允许）、`transform: none` 强对齐（移动端断点例外）。
- ❌ 禁止纯客户端首屏：热榜内容必须 SSR 输出真实 HTML，再用岛屿做局部刷新。SEO 是硬指标。

### 1.2 后端
- ✅ 必须用：FastAPI、Pydantic v2、httpx（异步）、APScheduler 或 FastAPI lifespan 后台任务、sqlite3 / aiosqlite。
- ✅ 后端 FastAPI 开发必须遵循 `.agents/skills/fastapi-templates/SKILL.md`（如与本仓库规范冲突，以本文件与 `backend/AGENTS.md` 为准）。
- ✅ Python 3.11+，类型注解必须完整（公共函数/路由/Pydantic 模型 100% 标注）。
- ✅ Lint：`ruff`；Type check：`mypy` 或 `pyright` 二选一。
- ❌ 禁止引入：Django、Flask、Tornado、SQLAlchemy（第一版）、Alembic、Celery、Kafka、PostgreSQL、MongoDB。
- ❌ 禁止：在路由处理函数里直接写 SeeSea HTTP 调用，**必须**封装 `SeeSeaClient`。
- ❌ 禁止：第一版引入 Redis。需要缓存就用 SQLite `cache_entries` 表，schema 见技术选型方案 §8。

### 1.3 数据边界
- ✅ 统一热搜结构字段：`platform / platformName / title / url / rank / heat / source / updatedAt`，见 [doc/摸鱼热榜技术选型方案.md](doc/摸鱼热榜技术选型方案.md) §5。
- ✅ 统一指数结构字段：`symbol / name / price / change / changePct / url / marketStatus / updatedAt / disclaimer`，见 §6。
- ❌ 禁止字段命名漂移（如 `platformId` / `platform_id` / `source_name` 混用）：FastAPI 返回 JSON 一律 **camelCase**，Python 内部一律 **snake_case**，由 Pydantic `alias_generator` 完成边界转换。
- ❌ 禁止透传 SeeSea 原始字段到前端。

---

## 2. 设计规范红线

主源：**[doc/摸鱼热榜-趣味Riso风格设计规范.md](doc/摸鱼热榜-趣味Riso风格设计规范.md)**。

**写任何 `.astro` / `.css` / `.tsx` 前必须先读它，不要凭印象写。**

硬约束摘要（违反即返工）：

| 维度 | 规则 |
|---|---|
| 底色 | `var(--paper)` (#FFF4D6)，禁止纯白 |
| 描边 | `2.5px solid var(--ink)`（卡片）/ `2px solid var(--ink)`（icon/pill） |
| 阴影 | `5px 5px 0 var(--ink)` 静态、`8px 9px 0 var(--ink)` hover，**禁止 blur** |
| 圆角 | 14px (小卡) / 18px (大卡) / 999px (pill 按钮) |
| 旋转 | 所有模块禁止 0° 对齐（移动端 ≤768px 例外）；旋转角度从规范 §4 选 |
| 平台色 | 严格按规范 §5.4 表，**新平台沿用同色族**，不许临时配色 |
| 字体分工 | 中文标题 Ma Shan Zheng；导航/卡名 ZCOOL KuaiLe；数字/英文爆点 Bagel Fat One；正文/数据 Space Mono；衬线导语 Fraunces italic |
| 装饰 | 波浪下划线、胶带、印章、角标、半色调点阵必须用内联 SVG / CSS，禁止位图 |
| 单卡 sticker | ≤1 个 |
| body 必加 | 噪点滤镜 `::before` + 半色调网点 `::after` |

新增页面 → 在 prompt / commit message 里显式写"沿用《摸鱼热榜-趣味Riso风格设计规范》"。

---

## 3. 目录结构（首版定稿）

```
moyu/
├── AGENTS.md                 ← 本文件（AI 规范主源）
├── CLAUDE.md                 ← Claude Code 入口，引用 AGENTS.md
├── README.md
├── doc/                      ← 所有设计与技术文档
│   ├── 摸鱼热榜-趣味Riso风格设计规范.md
│   ├── 摸鱼热榜首页设计规范.md
│   └── 摸鱼热榜技术选型方案.md
├── demo*.html                ← 设计稿历史快照（**只读**，不要改）
├── frontend/                 ← Astro 项目
│   ├── AGENTS.md             ← 前端专属规范
│   ├── astro.config.mjs
│   ├── package.json
│   ├── src/
│   │   ├── pages/            ← / · /trends · /market · /source/[id]
│   │   ├── components/       ← Riso 组件库（TopBar / Mast / Ticker / Board / Pill / Sticker）
│   │   ├── islands/          ← 仅交互岛屿放这里
│   │   ├── styles/           ← global.css（CSS Variables + body 噪点）
│   │   └── lib/api.ts        ← FastAPI 调用封装
│   └── public/
├── backend/                  ← FastAPI 项目
│   ├── AGENTS.md             ← 后端专属规范
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── api/              ← 路由：home / trends / sources / market / healthz
│   │   ├── clients/seesea.py ← **唯一**允许调 SeeSea 的地方
│   │   ├── clients/akshare.py
│   │   ├── models/           ← Pydantic schemas（Trend / Index / Source）
│   │   ├── cache/sqlite.py
│   │   └── scheduler.py
│   └── tests/
├── ops/                      ← Docker Compose / Nginx / 备案模板
│   ├── docker-compose.yml
│   └── nginx.conf
└── .claude/
    ├── settings.local.json
    └── skills/
        ├── frontend-design/  ← 通用 skill（已安装）
        ├── ui-ux-pro-max/    ← 通用 skill（已安装）
        ├── moyu-riso-card/   ← 项目专属：生成符合规范的热榜卡
        └── seesea-client/    ← 项目专属：SeeSea 调用模板
```

任何 AI **禁止**：
- 在仓库根新建顶层目录（除非上面已列出）。
- 在 `frontend/` 之外引入 npm 依赖。
- 在 `backend/` 之外建 Python 虚拟环境。
- 改动 `demo*.html`、`doc/**`（除非用户明确要求）。

---

## 4. 命名与编码约束

### 4.1 通用
- 文件名：前端 kebab-case (`hot-board.astro`)、后端 snake_case (`seesea_client.py`)。
- 平台 ID 使用 SeeSea 一致的小写串：`weibo / zhihu / bilibili-hot-search / douyin / v2ex / github-trending-today / hupu / tieba / douban`。新增平台必须在 `doc/摸鱼热榜-趣味Riso风格设计规范.md` §5.4 配色表里也增加映射。
- 时间字段统一使用 ISO 8601 + 时区（`2026-05-18T10:00:00+08:00`），**禁止**用毫秒时间戳。
- 注释默认不写。只在「为什么」非显然时写一行；禁止写「这里做了什么」式注释。

### 4.2 前端
- Astro 组件文件名首字母大写：`HotBoard.astro`、`PlatformPill.astro`。
- 客户端岛屿放 `src/islands/`，文件后缀 `.island.tsx`，**默认 `client:visible`**，禁止 `client:load` 用于首屏装饰。
- CSS Variables 必须在 `src/styles/global.css` 集中定义，组件内只允许引用，禁止重新定义。
- 调用后端：统一走 `src/lib/api.ts`，禁止在组件里裸写 `fetch('/api/...')`。

### 4.3 后端
- 路由放 `app/api/<resource>.py`，每个文件一个 `APIRouter`。
- Pydantic 模型放 `app/models/`，请求模型后缀 `Request`，响应模型后缀 `Response`。
- SeeSea 调用只能在 `app/clients/seesea.py`，并且通过依赖注入 `Depends(get_seesea_client)`。
- 失败兜底：所有外部依赖调用必须有 `try / except` + 旧缓存回退，**禁止**把异常往上抛到路由。
- 配置：通过 `pydantic-settings` 读 `.env`，禁止 `os.getenv` 散落各处。

---

## 5. 安全 & 合规红线（永不妥协）

- ❌ 禁止把 SeeSea 端口、内部 API、SQLite 文件、管理面板暴露到公网 Nginx。
- ❌ 禁止存储用户数据（无登录、无评论、无 UGC）。
- ❌ 禁止生成投资建议、荐股、收益预测、AI 时政摘要。
- ❌ 禁止绕过原站登录 / 付费墙。
- ❌ 禁止把内部 IP、容器名、SeeSea 路径暴露在 API 错误信息里——错误必须脱敏后返回 `{ "error": "...", "code": "..." }`。
- ✅ 美股数据响应必须带 `disclaimer: "仅供信息展示，不构成投资建议"`。
- ✅ 前端页脚必须保留版权与免责声明（见技术选型方案 §10）。

---

## 6. 工作流（AI 必须遵守）

1. **开工前**：读 `AGENTS.md`、对应子目录的 `AGENTS.md`、`doc/` 下相关规范。
2. **动手前**：列 todo / plan；涉及结构调整或新依赖，先和用户对齐。
3. **写代码**：优先编辑现存文件，不要新建重复模块；不要写未被要求的功能；不要预防性加 `try/except` 兜不存在的异常。
4. **本地校验**：
   - 前端：`pnpm astro check`（或 `npm run check`）+ `pnpm build`，要求 0 error。
   - 后端：`ruff check . && ruff format --check . && pyright`（或 `mypy app`），要求 0 error。
   - 测试：`pytest -q`（如已有），新功能至少补 happy path。
5. **提交前**：
   - 检查是否触发本文件任一 ❌；
   - 检查是否引入了未列入红线允许的依赖；
   - 检查 SeeSea 字段是否经过 `SeeSeaClient` 映射，未透传到前端；
   - 检查新 UI 是否符合 Riso 设计规范（旋转、阴影、字体、平台色）。
6. **commit message**：使用 conventional commits（`feat(frontend): ...` / `fix(backend): ...` / `docs: ...` / `chore(ops): ...`）。

---

## 7. 与用户的协作准则

- 中文回答，简洁；不要把用户能直接看到的 diff 在文字里复述一遍。
- 任何**风险动作**先确认：删除文件、强制推送、改备案信息、改 Nginx 配置、修改 `doc/` 与 `demo*.html`、修改 `SeeSeaClient` 接口字段、修改本文件。
- 任何**幂等动作**直接做：写新组件、补 docstring、补单测、跑格式化。
- 拿不准时优先问，而不是跑偏后再回头。
- 报告完成度时不要夸大：UI 类改动必须在浏览器里验证过才算完成。

---

## 8. AI 工具协作矩阵

| 工具 | 触发文件 | 加载方式 |
|---|---|---|
| **Codex** | `AGENTS.md`（根 + 子目录） | 启动时自动加载 |
| **Claude Code** | `CLAUDE.md`（根） | 启动时自动加载，内部 `@AGENTS.md` 引用 |
| **Cursor / Windsurf** | `.cursorrules` / `.windsurfrules`（如需） | 由用户启用时同步 AGENTS.md 摘要 |

**双工具一致性原则**：本文件是单一真理源；CLAUDE.md 不重复内容，只引用本文件 + 写 Claude 专属补充（skills、hooks、permissions 指引）。

---

## 9. 第一版完成定义（DoD）

- [ ] FastAPI 跑通 `/api/home /api/trends /api/sources /api/market/us /healthz` 五个端点
- [ ] SeeSea 仅在 `app/clients/seesea.py` 出现，且全部经过字段映射
- [ ] SQLite `cache_entries` 表落地，失败兜底逻辑可演示
- [ ] Astro 首页 `/` SSR 输出真实热搜 HTML（curl 能看见标题）
- [ ] Riso 设计规范关键元素齐备：噪点底、网点叠层、5 套字体、平台色卡、硬阴影、错位旋转
- [ ] Lighthouse 移动端性能 ≥ 90，可访问性 ≥ 95
- [ ] Docker Compose 一键起：nginx + frontend + api + seesea
- [ ] 页脚有版权与免责声明
- [ ] README 与 `doc/` 内容一致

> 写代码时如果发现本文件与代码现状或用户最新意图冲突，**先暂停问用户**，再决定是改文件还是改代码。不要静默偏离。
