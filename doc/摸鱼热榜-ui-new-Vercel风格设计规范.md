# 摸鱼热榜 · ui-new Vercel 风格设计规范

> 适用范围：所有 `/ui-new/*` 页面及其专属样式文件。
>
> 参考来源：[getdesign.md Vercel DESIGN.md](https://getdesign.md/vercel/design-md) 对 Vercel 公开界面的独立分析：Frontend deployment、Black and white precision、Geist font。
> 本规范不是 Vercel 官方设计系统，也不是照搬品牌资产；它只作为本项目新 UI 的设计语言约束。

---

## 0. 设计立场

`/ui-new/*` 是摸鱼热榜的新 UI 探索线，**不遵守 Riso/Zine 设计规范**。

视觉方向：**Vercel-like developer dashboard**。

关键词：

- 黑白精密
- 极简克制
- 高信息密度
- 1px hairline
- 小圆角
- 轻阴影
- Geist / system sans
- 亮暗双主题

这套 UI 的目标不是“有趣拼贴”，而是让热榜像一个开发者控制台：扫描快、边界清楚、干净、不乱。

---

## 1. 设计 Token

`/ui-new/*` 页面不走 `src/styles/global.css` 的 Riso 变量，统一使用公共基础样式：

- 全局 token、暗色 token、基础 reset 必须维护在 `frontend/public/ui-new/base.css`。
- 页面必须先引入 `/ui-new/base.css`，再引入自己的页面 CSS。
- 页面专属 CSS 只写布局、组件细节和必要的局部变量；不要重复定义 `:root`、`[data-skin="dim"]`、`body` 等全局主题规则。

当前亮色 token：

```css
:root {
  --background: #ffffff;
  --foreground: #171717;
  --muted-background: #fafafa;
  --subtle-background: #ffffff;
  --surface: #ffffff;
  --surface-elevated: #ffffff;
  --topbar-bg: rgba(255, 255, 255, 0.92);
  --hero-start: #ffffff;
  --hero-end: #fafafa;
  --border: #eaeaea;
  --border-light: #ededed;
  --text-primary: #171717;
  --text-secondary: #525252;
  --text-tertiary: #8f8f8f;
  --accent: #000000;
  --accent-subtle: #f5f5f5;
  --success-subtle: #f0fdf4;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --card-shadow: 0 1px 2px rgb(0 0 0 / 4%);
  --font-main: Geist, Inter, ui-sans-serif, system-ui, sans-serif;
  --font-heading: Geist, Inter, ui-sans-serif, system-ui, sans-serif;
}
```

当前暗色 token：

```css
[data-skin="dim"] {
  --background: #16181d;
  --foreground: #e7e9ee;
  --muted-background: #20232a;
  --subtle-background: #1b1e24;
  --surface: #1c1f26;
  --surface-elevated: #232731;
  --topbar-bg: rgba(22, 24, 29, 0.86);
  --hero-start: #20242d;
  --hero-end: #16181d;
  --border: #323742;
  --border-light: #2b303a;
  --text-primary: #f0f2f5;
  --text-secondary: #b9c0cc;
  --text-tertiary: #858e9d;
  --accent: #d7dce6;
  --accent-subtle: rgba(215, 220, 230, 0.12);
  --success-subtle: rgba(104, 179, 132, 0.14);
  --success: #8fd4a8;
  --danger: #f18a8f;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
}
```

允许 `#ffffff`、`#fafafa`、blur 阴影、`transform: none`；这些在 `/ui-new/*` 中不是违规项。

---

## 2. 字体与排版

- 首选字体：`Geist, Inter, ui-sans-serif, system-ui, sans-serif`。
- 不加载 Riso 的 Bagel Fat One / Fraunces / Ma Shan Zheng / Space Mono / ZCOOL KuaiLe。
- 标题克制：页面主标题通常 23-32px；除非是专门的营销 hero，不使用巨大展示字。
- 字重以 500 / 650 / 700 为主。
- 正文默认 13-15px，行高 1.5-1.7。
- 数字使用 `font-variant-numeric: tabular-nums;`。
- 字距保持 `0` 或轻微负字距（例如标题 `-0.02em`），不要做手写感或夸张装饰。

---

## 3. 布局原则

- 页面最大宽度优先使用 `1240px`，窄文档页可用 `960-1120px`。
- 顶栏高度约 `58px`，sticky，底部 `1px solid var(--border-light)`。
- 主内容使用 `24px` 左右页边距，移动端收至 `14-16px`。
- 卡片/模块之间用 `12-18px` gap；页面分区之间用 `26-32px` gap。
- 信息卡不要漂浮拼贴，不旋转，不使用胶带、印章、贴纸。
- 首页类页面可以用 4 列卡片网格：桌面 4 列、平板 2 列、移动 1 列。
- 文档/关于页优先使用正文流、细线分区、轻量 side note；避免大色块和大卡片堆叠。

---

## 4. 组件规则

### 顶栏

- 所有 `/ui-new/*` 页面必须使用公共组件 `frontend/src/components/ui-new/UiNewTopBar.astro`，禁止在页面内重复手写导航结构。
- 页面通过 `active="home"` / `active="about"` 等参数声明当前导航项。
- 顶栏 sticky。
- 背景使用半透明 `--topbar-bg` + `backdrop-filter: blur(12px)`。
- 导航是低调文本 pill，active 用下划线或浅底，不用粗描边。
- 图标按钮 32-36px，1px 边框，小圆角。

### 卡片

- `border: 1px solid var(--border)`。
- `border-radius: var(--radius-lg)`，通常 8px。
- 背景 `var(--surface)` 或 `var(--surface-elevated)`。
- 轻阴影：`0 1px 2px rgb(0 0 0 / 4%)`。
- hover 只做浅背景、边框、轻微 `translateY(-1px)`；禁止 Riso 式硬阴影和旋转。

### 列表

- 热榜列表保持真实 `<a>` 链接。
- 列项高度约 40-48px。
- rank 列宽约 30px。
- 标题默认单行省略；详情页可放开换行。
- hover 用 `var(--subtle-background)`。

### 按钮与图标

- 图标优先使用 inline SVG 或已有图标，不新增 UI 库。
- 按钮边框 1px，小圆角 6-8px。
- focus 使用 `box-shadow: 0 0 0 3px var(--accent-subtle)`。
- 不使用 Riso pill 粗描边、胶带、贴纸、印章。

### Toast / 浮层

- 允许轻 blur / 轻阴影。
- 背景跟随 `--surface-elevated`。
- 错误态只用 `--danger`，不要大面积红色。

---

## 5. 主题系统

`/ui-new/*` 推荐支持亮暗主题：

- 默认亮色主题命名为 `vercel`。
- 暗色主题命名为 `dim`。
- 使用 `document.documentElement.dataset.skin = "dim"` 切换。
- 用 `localStorage` 保存主题时，key 沿用 `trend-skin`，避免多个 ui-new 页面状态割裂。
- 暗色变量只在 `frontend/public/ui-new/base.css` 定义；新增页面不需要、也不应该单独配置一份暗色变量。
- 切换按钮必须有 `aria-label` 和 `title`。

---

## 6. 数据与工程边界

视觉例外不改变工程红线：

- 必须使用 Astro 5 + TypeScript + 原生 CSS，不得引入额外 UI 框架。
- 热榜内容仍必须 SSR 输出真实 HTML。
- 热榜链接必须是原站真实 `<a href="..." target="_blank" rel="noopener noreferrer">`。
- 调后端仍必须走 `src/lib/api.ts`，或页面内已明确用于预览的 FastAPI API base。
- 禁止直连 SeeSea。
- 禁止透传 SeeSea 原始字段到前端。
- 美股信息必须保留“仅供信息展示，不构成投资建议”。

---

## 7. 自检清单

新增或修改 `/ui-new/*` 页面时检查：

- [ ] 页面使用 `doc/摸鱼热榜-ui-new-Vercel风格设计规范.md`，不是 Riso/Zine 规范。
- [ ] 已判断本次 UI / 交互问题是否属于公共层能力；如果新增同类页面会复制代码，必须抽到公共组件、公共 CSS 或本规范。
- [ ] 页面使用 `frontend/src/components/ui-new/UiNewTopBar.astro`，没有自定义重复导航。
- [ ] 页面先引入 `/ui-new/base.css`，再引入自己的页面 CSS。
- [ ] 暗色 token 只来自 `frontend/public/ui-new/base.css`，页面 CSS 没有重复写 `[data-skin="dim"]`。
- [ ] 字体栈为 Geist / Inter / system sans，不加载 Riso 五套字体。
- [ ] 主色是黑白灰，强调色极少，不使用糖果色平台卡。
- [ ] 使用 1px hairline 边框、小圆角、轻阴影。
- [ ] 没有胶带、贴纸、印章、半色调噪点、手绘鱼等 Riso 装饰。
- [ ] 页面信息密度适中，视觉安静，移动端无横向溢出。
- [ ] SSR 输出真实内容和真实链接。
- [ ] `pnpm check` 和 `pnpm build` 通过。
- [ ] UI 改动已在浏览器验证。
