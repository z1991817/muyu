# frontend/AGENTS.md · Astro 5 前端规范

> 根规范见 [../AGENTS.md](../AGENTS.md)。本文件只写前端独有的细则。**冲突以本文件 + 根规范为准，最新的设计规范文档优先。**

## 1. 技术栈

```
Astro 5
TypeScript（strict: true）
原生 CSS / CSS Modules（推荐）或 Tailwind v4
pnpm（包管理器）
Vite（Astro 内置）
```

前端使用 TypeScript 时，必须遵循 `.agents/skills/typescript-advanced-types/SKILL.md` 的类型约束；若与根 `AGENTS.md` 或本文件冲突，以根 `AGENTS.md` 与本文件为准。

**禁止**：React Router、Next.js、Vue、Nuxt、Element、AntD、MUI、shadcn、DaisyUI、Bootstrap、styled-components、emotion。

**允许引入的 npm 包白名单**（其它需用户确认）：
- `astro`、`@astrojs/check`、`@astrojs/sitemap`、`@astrojs/node`
- `typescript`、`@types/node`
- `nanostores` / `@nanostores/persistent`（跨岛屿状态用）
- `echarts`（仅美股指数小图）

## 2. 目录约定

```
frontend/
├── astro.config.mjs
├── tsconfig.json
├── package.json
├── public/
│   ├── favicon.svg
│   └── fonts/                  ← 可选自托管字体
└── src/
    ├── pages/
    │   ├── index.astro         ← /          首页（热榜矩阵 + 美股大盘）
    │   ├── trends.astro        ← /trends    全部热榜（平台筛选）
    │   ├── market.astro        ← /market    美股大盘
    │   └── source/[id].astro   ← /source/:id 单平台热榜
    ├── components/             ← 纯 Astro 组件（零 JS）
    │   ├── TopBar.astro
    │   ├── Mast.astro          ← 报头
    │   ├── Tickers.astro       ← 数据 ticker 四列
    │   ├── HotBoard.astro      ← 平台热榜卡片
    │   ├── PlatformPill.astro
    │   ├── Sticker.astro
    │   ├── Stamp.astro
    │   ├── Squiggle.astro      ← SVG 波浪线
    │   └── Tape.astro          ← 胶带
    ├── islands/                ← 交互岛屿（少量 TS）
    │   ├── RefreshButton.island.ts
    │   ├── PlatformFilter.island.ts
    │   └── BossKey.island.ts   ← 老板键
    ├── styles/
    │   ├── global.css          ← CSS Variables + body 噪点 + 字体加载
    │   └── tokens.css
    ├── lib/
    │   ├── api.ts              ← 调用 FastAPI 的唯一出口
    │   ├── types.ts            ← 后端共享类型（手写或 openapi 生成）
    │   └── platforms.ts        ← 平台→class/色卡映射
    └── env.d.ts
```

**禁止**：
- 在 `pages/` 之外放路由文件。
- 在 `components/` 里写 `client:*`（交互必须搬到 `islands/`）。
- 在组件里裸 `fetch`（统一走 `lib/api.ts`）。
- 在 `pages/api/` 写后端逻辑——本项目所有 API 都在 FastAPI。

## 3. 路由与 SSR

- `output: 'server'` 或 `'hybrid'`，默认 SSR；列表页可加 `export const prerender = true` 启用预渲染。
- 首页必须 SSR 输出真实 `<a>` + 热搜标题：`curl https://localhost:4321/` 必须能看见热搜文字。
- `<head>` 必备：`<title>` / `<meta description>` / `<link rel="canonical">` / Open Graph 基础字段。
- 每条热搜用真实 `<a href="原站链接" target="_blank" rel="noopener noreferrer">`，**禁止** `onclick` 跳转。

## 4. 岛屿规则

- 默认 `client:visible`，**禁止** `client:load` 用于首屏装饰。
- 单文件 ≤ 100 行；超出说明你在客户端做太多事。
- 岛屿与岛屿之间通过 `nanostores` 通信，**禁止** 用 `window.dispatchEvent` 字符串事件。
- 岛屿挂载点必须有 `aria-*` 属性保留可访问性。

## 5. 设计规范执行清单（每次 PR 自检）

> 常规页面主源：[../doc/摸鱼热榜-趣味Riso风格设计规范.md](../doc/摸鱼热榜-趣味Riso风格设计规范.md)
>
> `/ui-new/*` 主源：[../doc/摸鱼热榜-ui-new-Vercel风格设计规范.md](../doc/摸鱼热榜-ui-new-Vercel风格设计规范.md)

### 5.0 `/ui-new/*` 新 UI 设计线

`src/pages/ui-new/**/*.astro` 与 `public/ui-new/**/*.css` 是新的 Vercel-like 简约 UI 设计线，不需要遵守 Riso/Zine 设计规范，也不适用本节的 Riso 自检清单。

该例外仅限视觉风格：仍必须遵守 Astro 5 + TypeScript + 原生 CSS、SSR 输出真实热榜 HTML、原站真实链接、FastAPI API 边界、禁止直连 SeeSea、禁止新增未确认依赖等工程与安全规则。

`/ui-new/*` 自检：

- [ ] 已阅读并遵守 `../doc/摸鱼热榜-ui-new-Vercel风格设计规范.md`
- [ ] 已判断本次 UI / 交互问题是否属于公共层能力；主题、导航、字体、基础 reset、按钮/输入基础态、页面宽度与间距体系、通用交互逻辑不得散落到单页重复实现
- [ ] 页面先引入 `/ui-new/base.css`，再引入自己的页面 CSS；全局 token、暗色 token、基础 reset 只维护在 `public/ui-new/base.css`
- [ ] 页面使用 `src/components/ui-new/UiNewTopBar.astro`，没有自定义重复导航
- [ ] 字体栈为 Geist / Inter / system sans，没有加载 Riso 五套字体
- [ ] 使用黑白灰 token，强调色克制，不使用糖果色平台卡
- [ ] 使用 1px hairline、小圆角、轻阴影，不使用 Riso 硬阴影、旋转、胶带、贴纸、印章
- [ ] 亮暗主题如存在，沿用 `trend-skin` 与 `data-skin="dim"`
- [ ] 移动端无横向溢出，文本不互相遮挡

常规 Riso 页面自检：

- [ ] 没有 `#FFFFFF` / `#FFF` / `white` 作为页面或卡片底色（搜索全文，确认 0 命中）
- [ ] 没有 `box-shadow:` 带 blur 半径 > 0（除 `inset` 边框）
- [ ] 没有 `linear-gradient` / `radial-gradient` 直接用在卡片背景（仅 body 底层允许）
- [ ] 没有卡片是 `transform: none`（移动端 `@media (max-width: 768px)` 例外）
- [ ] 字体只用规范允许的 5 套
- [ ] 平台色严格映射规范 §5.4 表
- [ ] body 已挂噪点 `::before` + 网点 `::after`
- [ ] 主内容容器有 `position:relative; z-index:2;`

## 6. 调后端

`src/lib/api.ts` 唯一出口：

```ts
const API_BASE = import.meta.env.PUBLIC_API_BASE ?? '/api';

export async function fetchHome(): Promise<HomeResponse> { ... }
export async function fetchTrends(platforms?: string[]): Promise<TrendsResponse> { ... }
export async function fetchMarketUs(): Promise<MarketResponse> { ... }
```

- 字段一律 camelCase（与后端 alias 对齐）。
- 失败处理：组件层判 `payload.stale`，展示"数据延迟"角标，不要抛红屏。
- 永远不要直接调 SeeSea 域名。

## 7. 验证

写完一个页面 / 组件后：

```bash
pnpm astro check    # 类型 + 模板检查，必须 0 error
pnpm build          # 构建必须通过
pnpm dev            # 浏览器肉眼验证对应视觉规范
```

UI 改动**没有浏览器验证过不算完成**。
