# CLAUDE.md · 摸鱼热榜

> Claude Code 入口。**所有规范主源在 [AGENTS.md](./AGENTS.md)，本文件不重复内容，只做引用 + Claude 专属补充。**

## 必读

@AGENTS.md
@doc/摸鱼热榜技术选型方案.md
@doc/摸鱼热榜-趣味Riso风格设计规范.md
@doc/摸鱼热榜首页设计规范.md

> 上面四个文件是写代码前的强制阅读清单。无论用户问什么编码任务，先确认这些约束。

## 技术栈速查

- 前端：**Astro 5 + TypeScript**（`frontend/`）
- 后端：**FastAPI + Pydantic v2 + httpx + APScheduler + SQLite**（`backend/`）
- 数据：**SeeSea**（内网）+ **AkShare**（美股补充）
- 部署：Docker Compose + Nginx，2C8G 起步

## Claude Code 专属补充

### 1. 工作流偏好
- 写代码默认中文沟通，回应简洁；不要复述 diff。
- 多步任务用 `TodoWrite` 跟踪；单步小改不需要。
- 探索类问题（"应该怎么做"）先给 2-3 句建议 + 主要权衡，等用户确认再动手。
- UI 类改动必须在浏览器里跑一遍 dev server 才能报告完成。

### 2. 可用 Skills
项目已安装：
- `frontend-design` —— 新建前端页面时调用，**prompt 必须包含**"沿用《摸鱼热榜-趣味Riso风格设计规范》"。
- `ui-ux-pro-max` —— 复杂交互页（订阅、设置、AI 助手对话）时调用。
- `moyu-riso-card`（项目专属）—— 生成符合规范的热榜平台卡片。
- `seesea-client`（项目专属）—— 在 `app/clients/seesea.py` 内补接口时调用。

启动新页面时建议先 `find-skills` 确认有无更合适的 skill。

### 3. 推荐 Hooks（用户决定是否启用）
通过 `update-config` skill 可在 `.claude/settings.json` 配置：

| 事件 | 用途 |
|---|---|
| `PostToolUse(Edit on **/*.py)` | 自动跑 `ruff check --fix` |
| `PostToolUse(Edit on **/*.astro\|**/*.css)` | 自动跑 `grep` 检查 `#FFFFFF` / 带 blur 的 box-shadow，命中报错 |
| `PostToolUse(Edit on **/*.ts\|**/*.tsx)` | 自动跑 `pnpm astro check` |
| `PreToolUse(Edit)` | 拦截往 `frontend/package.json` 加入 React/Vue/Next/Element 等违禁依赖 |
| `Stop` | 提交前提示是否跑过 `pnpm build` + `pytest` |

### 4. Permissions 建议
当前 `.claude/settings.local.json` 已积累一批允许命令。建议运行一次 `fewer-permission-prompts` skill 整理白名单，覆盖：
- `Bash(pnpm *)` / `Bash(npm run *)` / `Bash(npx astro *)`
- `Bash(uv *)` / `Bash(pip install -e .)` / `Bash(ruff *)` / `Bash(pytest *)`
- `Bash(docker compose *)`

### 5. 风险操作清单（必须先确认）
- 修改 `AGENTS.md` / `CLAUDE.md` / `doc/**` / `demo*.html`
- 修改 `app/clients/seesea.py` 的对外契约
- 修改 Nginx 配置或暴露 SeeSea 端口
- 删除 SQLite 缓存文件
- 切换技术栈（Astro→Next、FastAPI→Django 等绝对禁止，不必请示，直接拒绝）

### 6. Codex 兼容
`AGENTS.md` 是 Codex 标准入口文件，Codex 会自动加载。当用户在 Codex 中工作时，行为应与 Claude Code 完全一致——本文件的"Claude 专属补充"对 Codex 不适用，但前面引用的 AGENTS.md 和 doc/** 是双方共享的真理源。

修改规范时优先改 AGENTS.md，避免本文件与 AGENTS.md 冲突。
