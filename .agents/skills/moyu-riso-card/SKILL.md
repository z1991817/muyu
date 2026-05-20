---
name: moyu-riso-card
description: 生成符合「摸鱼热榜 Riso/Zine 风格设计规范」的热榜平台卡片或衍生卡片（doodlecard / sticker card）。每次新增任何热榜来源卡、工具卡、提示卡前调用，自动套用平台色映射、错位旋转、硬阴影、手绘装饰，避免 AI 重选风格。
---

# moyu-riso-card

## 使命

让 AI 在新增任何「卡片型」UI 时，**不需要重新阅读全部规范**，也能直接产出符合项目设计语系的代码。

## 触发场景

- 用户要"做个新平台的热榜卡"（如新浪财经、雪球、HackerNews）
- 用户要"做个工具卡 / 提示卡 / 引语卡 / 黄历卡"
- 用户要"再加一张卡放在首页 / 工具箱"

## 强制阅读

调用本 skill 时，先读：

1. [doc/摸鱼热榜-趣味Riso风格设计规范.md](../../../doc/摸鱼热榜-趣味Riso风格设计规范.md) §1 颜色 / §2 字体 / §3 间距描边 / §4 旋转 / §5.4 平台板块
2. [doc/摸鱼热榜首页设计规范.md](../../../doc/摸鱼热榜首页设计规范.md)（如果是首页卡片）
3. `demo7.html`（如果存在，用作视觉对照基线，**只读不改**）

## 输出契约

生成卡片代码必须满足下面 12 条，全部满足才能交付。

### 颜色

1. 卡片底色：必须来自规范 §5.4 平台色表，或从糖果色 token (`--pink-soft / --blue-soft / --green-soft / --yellow / --orange / --lilac / --paper-deep`) 中选一个；**禁止** `#FFFFFF / #FFF / white`。
2. 描边：`border: 2.5px solid var(--ink);`
3. 文字默认 `color: var(--ink);` 深色卡反白则用 `var(--paper);`

### 阴影

4. 静态：`box-shadow: 5px 5px 0 var(--ink);`
5. Hover：`box-shadow: 8px 9px 0 var(--ink);` 并 `transform: translate(-2px,-3px) rotate(-.4deg);`
6. **禁止任何 blur > 0** 的 `box-shadow`（`inset` 边框例外）。

### 形状

7. 圆角：小卡 `14px`、大卡 `18px`、pill `999px`。
8. 旋转：卡片根元素必须 `transform: rotate(<a>deg)`，`<a>` 从 `[-3, -2, -1, -0.5, 0.5, 1, 2, 3]` 选；**严禁 0°**（移动端 `@media (max-width: 768px)` 可降级为 `transform: none`）。
9. 角标 sticker：每张卡 ≤1 个；`position: absolute; transform: rotate(-8deg) ~ rotate(8deg);` 带 2px 描边 + 2px 硬阴影。

### 字体

10. 卡片标题用 `"ZCOOL KuaiLe", sans-serif`；数字/英文爆点用 `"Bagel Fat One", sans-serif`；列表标题用 `"Space Mono", monospace`；衬线引语用 `"Fraunces", serif italic`。**不可混入其它字体**。

### 装饰

11. 卡片至少包含**一个**手绘元素：波浪下划线（SVG path）/ 胶带 / 角标 / 印章 / 半色调点阵 / 虚线分隔（任选其一），增强 Riso 印刷感。
12. 如果是平台卡，列表 `<ol>` 的前 3 名 `rk` 数字必须用 Bagel Fat One，颜色顺序 `--pink / --orange / --blue`。

## 平台 → class 映射（仅认这张表）

| 平台 | platform ID | class | 底色 | icon 底色 |
|---|---|---|---|---|
| 微博热搜 | `weibo` | `.b-weibo` | `#FFE6E1` | `--pink` |
| 知乎热榜 | `zhihu` | `.b-zhihu` | `#E5EBFF` | `--blue` |
| B站热搜 | `bilibili-hot-search` | `.b-bili` | `#E2F5FF` | `#FF7BAC` |
| 抖音热点 | `douyin` | `.b-douyin` | `var(--ink)` 反白 | `var(--paper)` |
| GitHub Trending | `github-trending-today` | `.b-github` | `#FFF1C2` | `var(--ink)` |
| 虎扑步行街 | `hupu` | `.b-hupu` | `#FFD9C2` | `--orange` |
| 百度贴吧 | `tieba` | `.b-tieba` | `#E6F7E0` | `--green` |
| 豆瓣讨论 | `douban` | `.b-douban` | `#F1E2FF` | `--lilac` |
| V2EX | `v2ex` | `.b-v2ex` | `#FFE9A8` | `var(--ink)` |
| 百度热搜 | `baidu` | `.b-baidu` | `#E5EBFF` | `--blue` |

**新增平台规则**：从规范同色族里挑（不许新调色）；必须**同时**改本表 + `frontend/src/lib/platforms.ts` + 规范文档 §5.4，三处保持一致。

## 卡片骨架（Astro 模板）

```astro
---
// HotBoard.astro
import type { Trend } from '../lib/types';
import Sticker from './Sticker.astro';
import PlatformPill from './PlatformPill.astro';

interface Props {
  platformId: string;
  platformName: string;
  trends: Trend[];
  sticker?: string;       // FRESH / HOT / NEW，可选
  rotate?: number;        // 默认 ±1°~±2°，禁止 0°
}

const { platformId, platformName, trends, sticker, rotate = 1.2 } = Astro.props;
---

<article
  class={`board b-${platformId}`}
  style={`transform: rotate(${rotate}deg);`}
>
  <header class="b-head">
    <span class="b-icon" aria-hidden="true"><!-- inline SVG --></span>
    <div>
      <h3 class="b-name">{platformName}</h3>
      <p class="b-sub">实时热搜</p>
    </div>
    <PlatformPill platform={platformId} />
  </header>

  <ol class="b-list">
    {trends.slice(0, 10).map((t, i) => (
      <li class={i < 3 ? `top${i + 1}` : ''}>
        <a href={t.url} target="_blank" rel="noopener noreferrer">
          <span class="rk">{t.rank}</span>
          <span class="ttl">{t.title}</span>
          <span class="heat">{t.heat}</span>
        </a>
      </li>
    ))}
  </ol>

  <footer class="b-foot">
    <span class="caps">UPDATED · {/* updatedAt */}</span>
    <a class="more" href={`/source/${platformId}`}>更多 →</a>
  </footer>

  {sticker && <Sticker label={sticker} angle={-8} top={-12} right={18} />}
</article>
```

```css
/* global.css 已定义 :root 颜色变量，下面只列卡片专用 */
.board {
  position: relative;
  padding: 18px;
  border: 2.5px solid var(--ink);
  border-radius: 18px;
  background: var(--paper-deep);
  box-shadow: 5px 5px 0 var(--ink);
  transition: transform .25s cubic-bezier(.2,.7,.2,1),
              box-shadow .25s cubic-bezier(.2,.7,.2,1);
}
.board:hover {
  transform: translate(-2px,-3px) rotate(-.4deg);
  box-shadow: 8px 9px 0 var(--ink);
}
.b-weibo  { background: #FFE6E1; }
.b-zhihu  { background: #E5EBFF; }
.b-bili   { background: #E2F5FF; }
.b-douyin { background: var(--ink); color: var(--paper); }
.b-github { background: #FFF1C2; }
.b-hupu   { background: #FFD9C2; }
.b-tieba  { background: #E6F7E0; }
.b-douban { background: #F1E2FF; }
.b-v2ex   { background: #FFE9A8; }

.b-list .top1 .rk { color: var(--pink);   font-family: "Bagel Fat One", sans-serif; }
.b-list .top2 .rk { color: var(--orange); font-family: "Bagel Fat One", sans-serif; }
.b-list .top3 .rk { color: var(--blue);   font-family: "Bagel Fat One", sans-serif; }
.b-list li a { font-family: "Space Mono", monospace; font-size: 13.5px; }

@media (max-width: 768px) {
  .board { transform: none !important; }
}
```

## 自检清单（交付前 AI 必须逐项打勾）

- [ ] 背景色不是纯白
- [ ] 描边 2.5px / 阴影无 blur
- [ ] 旋转角不是 0°（移动端例外）
- [ ] 字体只用 5 套规范字体
- [ ] 平台 ID / class / 配色三方一致
- [ ] 列表前 3 名颜色顺序粉/橙/蓝
- [ ] 至少 1 个手绘装饰
- [ ] sticker 数量 ≤ 1
- [ ] 真实 `<a href>` 跳转，加 `target="_blank" rel="noopener noreferrer"`

## 反例（一旦出现立即返工）

```css
/* ❌ */ background: white;
/* ❌ */ background: linear-gradient(...);
/* ❌ */ box-shadow: 0 4px 12px rgba(0,0,0,.1);
/* ❌ */ transform: none;       /* 桌面端 */
/* ❌ */ border-radius: 8px;    /* 与规范 14/18 不符 */
/* ❌ */ font-family: "Inter";  /* 不在规范 5 套字体内 */
```
