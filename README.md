# 摸鱼热榜（moyu）

> 公开榜单链接聚合站点。第一版只展示标题与原站链接，点击跳转外站，不做内容转载。

## 技术栈

- **前端**：Astro 5 + TypeScript（`frontend/`）
- **后端**：FastAPI + Pydantic v2 + httpx + APScheduler + SQLite（`backend/`）
- **数据源**：[SeeSea](https://github.com/nostalgiatan/SeeSea)（内网采集）+ AkShare（美股补充）
- **部署**：Docker Compose + Nginx，推荐 2C8G / 40G SSD

## 数据获取与致谢

本项目使用 [SeeSea](https://github.com/nostalgiatan/SeeSea) 框架进行公开热榜数据获取，并在后端服务中完成字段清洗、缓存与统一输出。感谢 SeeSea 项目提供稳定、易用的数据采集能力，让摸鱼热榜可以更专注于链接聚合、展示体验与安全边界。

## AI 协作入口（必读）

本项目对 AI 编程助手做了规范化。**写代码前请按以下顺序加载上下文**：

| 工具 | 入口文件 | 加载方式 |
|---|---|---|
| **Codex** | [AGENTS.md](AGENTS.md) | 启动时自动加载 |
| **Claude Code** | [CLAUDE.md](CLAUDE.md) → `@AGENTS.md` | 启动时自动加载，内部引用 AGENTS.md |
| Cursor / Windsurf | 用户可手动同步 AGENTS.md 摘要 | — |

**唯一真理源是 [AGENTS.md](AGENTS.md)**，CLAUDE.md 只做引用 + Claude 专属补充（skills / hooks / permissions）。

### 规范文档

- [AGENTS.md](AGENTS.md) —— AI 开发主规范（技术栈红线、目录、安全合规、工作流）
- [frontend/AGENTS.md](frontend/AGENTS.md) —— Astro 前端细则
- [backend/AGENTS.md](backend/AGENTS.md) —— FastAPI 后端细则
- [doc/摸鱼热榜技术选型方案.md](doc/摸鱼热榜技术选型方案.md) —— 架构选型、API 设计、缓存策略、部署
- [doc/摸鱼热榜-趣味Riso风格设计规范.md](doc/摸鱼热榜-趣味Riso风格设计规范.md) —— 视觉规范（Riso/Zine 风格）
- [doc/摸鱼热榜首页设计规范.md](doc/摸鱼热榜首页设计规范.md) —— 首页信息架构

### 项目专属 Skills（Claude Code）

- `moyu-riso-card` —— 生成符合 Riso 规范的卡片组件
- `seesea-client` —— 在 backend 里新增或修改 SeeSea 调用

通用 skills（已安装）：`frontend-design`、`ui-ux-pro-max`、`update-config`、`simplify`、`init`、`review`、`security-review`。

## 目录速览

```
moyu/
├── AGENTS.md / CLAUDE.md       ← AI 规范入口（双工具兼容）
├── doc/                        ← 设计与技术文档（只读真理源）
├── demo*.html                  ← 历史设计稿（只读）
├── frontend/                   ← Astro 5 项目（待创建）
├── backend/                    ← FastAPI 项目（待创建）
├── ops/                        ← Docker Compose / Nginx（待创建）
└── .claude/
    └── skills/                 ← Claude Code skills
```

## 开发原则速记

1. SeeSea 内网，永不暴露公网。
2. 前端永不直连 SeeSea，必须经 FastAPI。
3. 只保留标题 + 原站链接，禁止转载正文 / AI 摘要 / 评论 / UGC。
4. UI 一律沿用 Riso 设计规范，禁止重选风格、禁止引入 React/Vue/Element 类 UI 库。
5. 字段命名：API 响应 camelCase，Python 内部 snake_case，由 Pydantic alias 完成边界转换。
6. 美股响应必须带"仅供信息展示，不构成投资建议"。

详见 [AGENTS.md](AGENTS.md)。

## License & 合规

本站定位为「个人工具网站 · 公开链接索引」。
- 内容版权归原平台及原作者所有。
- 美股数据仅供信息展示，不构成投资建议。
- 中国大陆服务器需完成 ICP 备案与公安联网备案。
