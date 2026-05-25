# 摸鱼热榜 · 趣味 Riso 风格设计规范

> 基于 `demo7.html` 提炼，适用于 `/bold` 大胆版与后续所有 Riso/Zine 页面延续同一视觉语系。
> 版本：v1.0 · 2026-05-18
>
> **生成方式**：本风格由 `frontend-design` skill 在「趣味主题」方向上落地完成。
> skill 提供的能力：bold 美学方向选型（最终选择 Riso 印刷 / Zine 拼贴）、字体与配色组合推荐、
> 反"AI 通用感"的细节把控（手绘 SVG 装饰、错位旋转、硬阴影、半色调网点）。
>
> **后续延续做法**：新页面继续调用 `frontend-design` skill，并在 prompt 中明确
> "沿用《摸鱼热榜-趣味Riso风格设计规范》"，让 skill 在已有美学约束内创作，而不是重新选风格。

---

## 0. 设计哲学（Design DNA）

一份"贴在工位的纸质小报 / 独立印刷工坊出品的 Zine"。当前站点默认首页 `/` 是简约版；本规范负责 `/bold` 大胆版与后续明确选择 Riso/Zine 的页面。
关键词：**纸质感 · 油墨网点 · 手写感 · 错位拼贴 · 糖果色块 · 硬阴影**。

三句话立场（均可在 `demo7.html` 中找到对应实现）：

1. **印刷品感优先于 UI 感**：纸质底色 `#FFF4D6` + SVG 噪点滤镜 + 7px 半色调网点叠层，模拟 Riso / 复印机的油墨纸张感。
2. **歪一点更亲切**：报头吉祥物卡 `rotate(2deg)` + bob 浮动、印章 `rotate(-3deg)` + wig 摇摆、ticker 在 ±1° 间错位、角标 `rotate(±6°~8°)`——全局**没有任何 0° 严格对齐**的模块。
3. **少而强烈的颜色**：糖果色作卡片底，主色（粉/黄/蓝）做强调，`#1A1714` 黑做骨架。**没有大面积纯白底**，仅在标题块、深色卡反白时用奶油色。

从 demo7 提炼出的"不要做"清单（这些都是因为它们会**破坏**已有视觉语系）：

- 不要用纯白 `#FFFFFF` 做底——会立刻失去纸质感。
- 不要用 `box-shadow` 的模糊阴影（带 blur 的）——demo7 全部是 `0 blur` 的硬阴影。
- 不要用线性 / 径向渐变填充卡片——demo7 的颜色都是色块平涂，渐变只用于 body 底层氛围。
- 不要让任何卡片 `transform: none` 强对齐（移动端例外）。
- 不要混用本规范外的字体——5 套字体已经分工到位，新增会立刻"出戏"。

---

## 1. 颜色系统（CSS Variables）

直接复用以下变量，不要自创近似色。

```css
:root{
  /* 纸 / 底 */
  --paper:        #FFF4D6;  /* 主底，奶油黄 */
  --paper-deep:   #FFE9A8;  /* 卡片二层底 */

  /* 墨 */
  --ink:          #1A1714;  /* 描边、正文、阴影 */

  /* 糖果色 · 平台与强调 */
  --pink:         #FF3D7F;  --pink-soft:  #FFD6E2;
  --blue:         #2540D9;  --blue-soft:  #CFD8FF;
  --yellow:       #FFC93C;
  --green:        #1F9F5F;  --green-soft: #C8F3D9;
  --orange:       #FF6B2C;
  --lilac:        #B080FF;
}
```

**配色铁律**

| 规则 | 说明 |
|---|---|
| 底色用 `--paper` | 不要用 `#FFFFFF`。深色卡片可以用 `--ink` 反白。 |
| 描边一律 `--ink` 实色 | 粗细 `2.5px` 起步，圆角配粗描边才有印刷感。 |
| 阴影一律 `--ink` 硬阴影 | `box-shadow:5px 5px 0 var(--ink);` —— 不要 blur。 |
| 强调 ≤ 2 色 / 屏 | 一段视觉里主色 + 一个对比色，其它降为 soft 色卡。 |
| 平台色映射固定 | 见下表 6 节，新增平台沿用同色族。 |

**底层叠加（必加，决定"纸感"）**

```css
body{
  background-image:
    radial-gradient(circle at 22% 18%, rgba(255,61,127,.10) 0, transparent 38%),
    radial-gradient(circle at 82% 8%,  rgba(37,64,217,.10) 0, transparent 40%),
    radial-gradient(circle at 92% 88%, rgba(255,201,60,.18) 0, transparent 45%),
    radial-gradient(circle at 8% 92%,  rgba(31,159,95,.10) 0, transparent 40%);
  background-color: var(--paper);
}

/* 噪点：multiply 模式叠在上层 */
body::before{
  content:""; position:fixed; inset:0; z-index:1; pointer-events:none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.92' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.10 0 0 0 0 0.09 0 0 0 0 0.08 0 0 0 0.55 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.18'/></svg>");
  mix-blend-mode: multiply; opacity:.55;
}

/* 半色调网点 */
body::after{
  content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
  background-image: radial-gradient(circle at center, var(--ink) 0.6px, transparent 1.1px);
  background-size: 7px 7px; opacity:.05;
}
```

> 主内容必须包在 `position:relative; z-index:2;` 容器中，避免被噪点遮挡。

---

## 2. 字体系统

**统一通过 Google Fonts 加载这一组，不要替换：**

```html
<link href="https://fonts.googleapis.com/css2?family=Bagel+Fat+One&family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,800;1,9..144,400&family=Ma+Shan+Zheng&family=Space+Mono:wght@400;700&family=ZCOOL+KuaiLe&display=swap" rel="stylesheet">
```

| 用途 | 字体 | 备注 |
|---|---|---|
| 正文 / 数据 / 英文小标 | `"Space Mono", monospace` | 全局 `body` 默认 |
| 中文大标题 / 手写感 | `"Ma Shan Zheng", cursive` | 报头、quote |
| 中文导航 / 模块名 | `"ZCOOL KuaiLe", sans-serif` | 圆润可爱，用于 nav、卡片名 |
| 英文展示 / 数字爆点 | `"Bagel Fat One", sans-serif` | 印章、数字、tag |
| 衬线导语 / 引言 | `"Fraunces", serif` (italic) | 仅用于 lede / colophon 段落 |

**字号阶梯**

```
报头 H1     clamp(86px, 11.5vw, 170px)   Ma Shan Zheng
版块大标    22 ~ 30px                    ZCOOL KuaiLe / Bagel Fat One
卡片名      22px                         ZCOOL KuaiLe
列表标题    13.5px                       Space Mono
正文导语    18px italic                  Fraunces
小标 / 元   11 ~ 12px / letter-spacing:.18em / uppercase
数字爆点    36px                         Bagel Fat One
```

中英混排时，中文走 Ma Shan Zheng / ZCOOL KuaiLe，英文走 Bagel Fat One / Space Mono，**不要**用一种字体硬撑双语。

---

## 3. 间距 · 圆角 · 描边

```
间距尺度 (px):  4 · 6 · 10 · 14 · 18 · 22 · 28 · 38 · 60 · 80
最大宽度:       1380px (.wrap)
内边距:         28~36px (页面级) / 14~18px (卡片级)
卡片圆角:       14px (小) · 18px (大)
描边:           2.5px solid var(--ink)  —— 卡片标准
                2px   solid var(--ink)  —— icon / pill
硬阴影:         5px 5px 0 var(--ink)    —— 静态
                8px 9px 0 var(--ink)    —— hover
按钮 / pill:    border-radius: 999px
```

**核心：圆角 + 粗黑描边 + 硬黑阴影是这套风格的"骨架三件套"，缺一个就变味。**

---

## 4. 旋转 / 错位 / 手绘装饰

这套风格**禁止**所有元素 0° 对齐。常用旋转值：

```css
transform: rotate(-3deg);   /* 印章 stamp */
transform: rotate(2deg);    /* 立体卡 figureCard */
transform: rotate(-1deg)   ~ rotate(1deg);  /* ticker 错位 */
transform: rotate(-8deg)   ~ rotate(8deg);  /* 角标 sticker、badge */
```

**手绘装饰（必备元素库）**

| 元素 | 实现 |
|---|---|
| 波浪下划线 squiggle | 内联 SVG `<path>`，stroke 4.5px，配合标题 `position:absolute` |
| 胶带 tape | 半透明白 + 45° 斜纹 `repeating-linear-gradient` |
| 角标 sticker | `position:absolute; transform:rotate(-8deg)`；带粗描边硬阴影 |
| 印章 stamp | 粉/黄底 + 黑描边 + Bagel Fat One 大写英文 + 轻微旋转动画 |
| 半色调点阵 | SVG `<pattern>` 在图形内做填充 |
| 虚线分隔 | `border-top: 1.5px dashed currentColor;` |
| 手绘小鱼 / 吉祥物 | 全部内联 SVG 手画路径，色块 + 黑描边，搭配 SVG `<pattern>` 网点 |

---

## 5. 组件库（直接复用 class 名）

### 5.1 顶栏 `.topbar`

```html
<header class="topbar">
  <div class="stamp">摸鱼 ISSUE №073</div>
  <div class="crumbs">
    <span><b>05/18</b> 周一</span>
    <span>北京 · 多云 23°</span>
    <span>距下班 <b>04:12:38</b></span>
  </div>
  <nav>
    <a class="active" href="#boards-section">热榜</a>
    <a href="/about">关于我</a>
    <a href="/">简约版</a>
  </nav>
</header>
```

要求：印章在最左、面包屑居中、导航靠右；nav 链接用 pill 风格，hover 加 `--yellow` 背景 + 轻微抬升旋转。

当前 `/bold` 顶栏导航顺序固定为：`热榜` / `关于我` / `简约版`。点击“简约版”必须写入 `localStorage.moyu-ui-version = "simple"`，避免用户刷新 `/` 后又被版本偏好带回大胆版。

### 5.2 报头 `.mast` + `.title` + `.lede` + `.figureCard`

报头采用 **1.55fr / .9fr** 双栏：左侧巨型中文标题（Ma Shan Zheng）+ 衬线导语（Fraunces italic）；右侧手绘吉祥物卡片（带胶带、角标、bob 浮动动画）。

第二行标题色调对比，关键词用 `<em>` 包成黄底圆角粗描边块，配 `box-shadow:6px 6px 0 var(--ink)` 硬阴影 + `rotate(-2deg)`。

### 5.3 数据 ticker `.tickers > .ticker`

四列等宽，每个 ticker 不同糖果底色 + 不同方向轻旋转（-1° / +.6° / -.4° / 1°）。结构：

```
┌───────────────────────────┐
│ 全网热度  (lab uppercase)  │
│ 8,427 万 (Bagel Fat One)  │
│ ↑12.4% ...  (delta)       │
│           [SVG 小图位右下] │
└───────────────────────────┘
```

升 `.delta.up` 用 `--green`，降 `.delta.down` 用 `--pink`。

### 5.4 平台板块 `.board.b-{platform}`

**栅格：12 列网格**，平台块用 `grid-column: span N` 拼摆（demo7 使用 5/4/3 + 4/4/4 + 6/6 三排不规则布局）。

固定平台底色映射（**新增页面延续**）：

| 平台 | class | 底色 | icon 底色 |
|---|---|---|---|
| 微博 | `.b-weibo` | `#FFE6E1` | `--pink` |
| 知乎 | `.b-zhihu` | `#E5EBFF` | `--blue` |
| B站 | `.b-bili` | `#E2F5FF` | `#FF7BAC` |
| 抖音 | `.b-douyin` | `--ink` (反白) | `--paper` |
| GitHub | `.b-github` | `#FFF1C2` | `--ink` |
| 虎扑 | `.b-hupu` | `#FFD9C2` | `--orange` |
| 贴吧 | `.b-tieba` | `#E6F7E0` | `--green` |
| 豆瓣 | `.b-douban` | `#F1E2FF` | `--lilac` |

每张卡 hover：`translate(-2px,-3px) rotate(-.4deg)` + 阴影加深至 `8px 9px 0 var(--ink)`，过渡 `.25s cubic-bezier(.2,.7,.2,1)`。

板块结构：

```
.b-head    →  [b-icon] [b-name + b-sub]   [b-tag]
.b-meta    →  辅助说明（可选）
.b-list    →  ol > li > a > [rk] [ttl(+pill)] [heat]
.b-foot    →  [脚注 caps]   [更多 →]
```

`.b-list .top1/2/3 .rk` 使用粉 / 橙 / 蓝高亮，`.rk` 用 Bagel Fat One。

### 5.5 列表 pill 状态 tag

```css
.pill { font-size:9.5px; letter-spacing:.12em; text-transform:uppercase;
        border:1.5px solid currentColor; border-radius:999px; padding:0 6px; }
.pill.hot  { color: var(--pink);  }   /* 热 / 沸 */
.pill.new  { color: var(--blue);  }   /* 新 */
.pill.boom { color: var(--orange); animation: blink 2s linear infinite; }  /* 爆 */
.pill.brk  { color: var(--green); }   /* 突 */
```

### 5.6 角标 sticker

四角悬挂的小标签，**每张卡片不超过 1 个**：

```html
<span class="sticker" style="top:-12px;right:18px;background:var(--yellow);">FRESH</span>
```

旋转 ±6°~8°，永远带 2px 黑描边 + 2px 硬阴影。

### 5.7 颜色卡片（彩色 doodlecard）

页脚提示卡 / 小工具卡的统一样式：糖果底 + 粗描边 + 硬阴影 + ±1.5° 旋转 + ZCOOL KuaiLe 标题 + Space Mono 正文。

### 5.8 引语块 `.quote`

黑底奶油字 + Ma Shan Zheng 大字号 + 黄色 emoji 圆点装饰（伪元素径向渐变实心圆）+ 整体 `rotate(-1.2deg)`。

---

## 6. 动画规范

只允许以下四类，且**慢、轻、循环型**为主：

```css
@keyframes bob   { 0%,100%{transform:translateY(0) rotate(2deg)} 50%{transform:translateY(-6px) rotate(2.6deg)} }
@keyframes wig   { 0%,100%{transform:rotate(-3deg)} 50%{transform:rotate(3deg)} }
@keyframes blink { 0%,40%,100%{opacity:1} 45%,55%{opacity:.15} }
```

| 元素 | 动画 | 时长 |
|---|---|---|
| 吉祥物 figureCard | `bob` | 6s ease-in-out infinite |
| 印章 stamp | `wig` | 4.5s ease-in-out infinite |
| `.pill.boom` | `blink` | 2s linear infinite |
| 卡片 hover | transform + shadow | .25s cubic-bezier(.2,.7,.2,1) |

**禁止**：弹簧抖动、3D 翻转、滚动视差、长时长 fade。

---

## 7. 响应式断点

只设一个断点：

```css
@media (max-width: 1100px){
  .boards   { grid-template-columns: repeat(6, 1fr); }
  .board    { grid-column: span 6; }   /* 全部撑满双列 */
  .mast     { grid-template-columns: 1fr; }
  .figureCard { transform: none; }     /* 移动端关闭旋转 */
  .tickers  { grid-template-columns: repeat(2, 1fr); }
  .footer   { grid-template-columns: 1fr; }
}
```

移动端额外要求：
- 关闭所有非 hover 旋转（`transform:none`），避免视觉拥挤。
- 字号 H1 已用 `clamp()`，无需额外调整。
- 噪点 / 半色调层保留。

---

## 8. 文案语气

- **轻松、自嘲、不油腻**。"今天又是混日子的一天～" / "把背挺直，假装在敲代码"。
- 数字旁可加调侃单位/注解："比昨天烫嘴" / "比双十一冷静一点"。
- 法语 / 英文短语**禁用**（这是另一种风格 demo8 的事，不要混）。
- 模块名带量词："第 73 期" / "本日小鱼" / "工位哲学家"。

---

## 9. 新页面快速开始模板（Skeleton）

新 Riso 页面落地步骤：

1. 复制 `demo7.html` 的 `<head>`（字体 + `<style>` 全部 `:root` 变量、`body::before`/`::after` 噪点层、`.topbar`、`.board` 系列样式）。
2. 在 `.wrap` 容器内组装：
   - `.topbar` 顶栏（必有）
   - 1 个 hero 区域（masthead 或简化版）
   - 数据 strip / 主内容栅格（按页面用途选择）
   - colophon / footer doodle 卡片
3. 按需添加新组件，遵循"圆角 + 粗黑描边 + 硬黑阴影 + 微旋转"四件套。
4. 颜色优先在已有变量内取，新增色必须先在 `:root` 注册。
5. 任何新平台块必须使用 6.4 节的色彩映射或同色族。
6. 不要把 Riso 页面重新设为默认首页 `/`；默认入口属于简约版，Riso 入口固定为 `/bold` 或后续明确命名的大胆版路由。

---

## 10. 检查清单（Pre-flight）

发布前对照：

- [ ] 页面背景是 `--paper` 而非纯白
- [ ] 页面路由不是默认首页 `/`；大胆版当前入口为 `/bold`
- [ ] 噪点 + 半色调两层叠加都加上了
- [ ] 至少有 3 处微旋转元素
- [ ] 主标题用 Ma Shan Zheng，导航用 ZCOOL KuaiLe
- [ ] 至少 1 处 SVG 手绘装饰（小鱼 / squiggle / 半色调 pattern）
- [ ] 卡片描边 ≥ 2.5px、阴影是 `0 blur` 的硬阴影
- [ ] 强调色不超过 2 种 / 屏
- [ ] 移动端断点关闭了非 hover 旋转
- [ ] 文案带工位幽默感，不出现法/英长句
- [ ] 没有出现 Inter / Roboto / Arial / 紫白渐变
