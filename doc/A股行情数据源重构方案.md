# A 股行情数据源重构方案

更新时间：2026-05-29

## 目标

本次重构目标是把 `/ui-new/a-share` 从历史混合行情源切换到稳定的 TDX 实时行情源，解决线上 A 股页面出现旧涨停、旧跌停、旧缓存与新指数混合展示的问题。

本方案只覆盖 A 股行情页与 `/api/market/cn` 链路，不影响热榜、SeeSea 热搜、美股行情和 AI 新闻。

## 当前 A 股页面使用的源

当前页面入口是 `frontend/src/pages/ui-new/a-share.astro`。

页面调用链如下：

```text
/ui-new/a-share
  -> frontend/src/lib/api.ts fetchCnMarket()
  -> GET /api/market/cn
  -> backend/app/api/market.py market_cn()
  -> SQLite cache key: market:cn
  -> backend/app/jobs/refresh_cn_market.py
  -> backend/app/scheduler.py _refresh_cn_market()
  -> backend/app/clients/cn_market.py CnMarketClient.fetch_cn_market()
```

也就是说，A 股页面本身不直接访问任何行情源；它只读取 FastAPI 返回的 `market:cn` 缓存。真正的数据源在 `backend/app/clients/cn_market.py`。

### 当前指数源

当前指数链路是多源兼容：

| 优先级 | 源 | 代码位置 | 用途 |
|---:|---|---|---|
| 1 | 腾讯行情 `https://qt.gtimg.cn/q=sh000001,sh000300,sh000905` | `_fetch_tencent_indices()` | 上证指数、沪深300、中证500 |
| 2 | 新浪行情 `https://hq.sinajs.cn/list=s_sh000001,s_sh000300,s_sh000905` | `_fetch_sina_indices()` | 腾讯失败时备用 |
| 3 | 网易行情 `http://api.money.126.net/data/feed/...` | `_fetch_netease_indices()` | 新浪失败时备用 |
| 4 | AkShare `stock_zh_index_spot_em` | `_run_akshare("stock_zh_index_spot_em")` | HTTP 源全部失败时备用 |

当前模型里有科创50符号 `000688`，但腾讯/新浪/网易固定 URL 只拉了三个指数，页面实际主要展示上证指数、沪深300、中证500。

### 当前热门股票源

当前热门股票链路是：

| 源 | 代码位置 | 用途 |
|---|---|---|
| AkShare `stock_zh_a_spot` | `_run_akshare("stock_zh_a_spot")` | 全 A 实时报价 |
| AkShare `stock_hot_follow_xq` | `_run_akshare("stock_hot_follow_xq")` | 雪球关注热股排序 |
| 腾讯个股行情 `https://qt.gtimg.cn/q=...` | `_fetch_tencent_hot_stock_quotes()` | 热股无法从全 A 报价匹配时补行情 |
| 本地排序 | `stocks.sort(key=abs(change_pct))` | 上面热股为空时，用涨跌幅绝对值排序兜底 |

### 当前市场概况源

当前 `analysis.fundFlows` 字段实际优先表示市场广度，而不是严格的资金流：

| 字段 | 当前来源 | 说明 |
|---|---|---|
| 上涨家数 | AkShare `stock_zh_a_spot` 全 A 涨跌幅自算 | 来自 `_map_cn_market_breadth()` |
| 下跌家数 | AkShare `stock_zh_a_spot` 全 A 涨跌幅自算 | 来自 `_map_cn_market_breadth()` |
| 平盘家数 | AkShare `stock_zh_a_spot` 全 A 涨跌幅自算 | 来自 `_map_cn_market_breadth()` |
| 涨停家数 | AkShare 涨停池数量 | 来自 `limit_up` |
| 跌停家数 | AkShare 跌停池数量 | 来自 `limit_down` |
| 资金流 | AkShare `stock_market_fund_flow` | 只有当全 A 股票行为空时才作为兜底 |

### 当前涨跌停源

当前涨跌停来自 AkShare 的东方财富相关接口：

| 字段 | 当前接口 | 代码位置 |
|---|---|---|
| `analysis.limitUp` | AkShare `stock_zt_pool_em(date)` | `_fetch_limit_up()` |
| `analysis.limitDown` | AkShare `stock_zt_pool_dtgc_em(date)` | `_fetch_limit_down()` |

线上日志已经验证，东方财富 `push2.eastmoney.com/api/qt/clist/get` 会持续返回 `502 Bad Gateway`。这会导致涨停、跌停列表缺失，再被缓存合并逻辑补回旧数据。

### 当前缓存与旧数据干扰点

当前 scheduler 在 `_merge_cn_market_cache_on_partial_empty()` 里会把旧缓存字段合并到新结果：

```text
如果新 response 缺 indices，则补旧 indices
如果新 response 缺 stocks 或 stocks 缺成交量/成交额，则补旧 stocks
如果新 response 缺 limit_up，则补旧 limit_up
如果新 response 缺 limit_down，则补旧 limit_down
合并后 stale=True
```

这个设计的初衷是“页面不断粮”，但对涨跌停这种强日期数据不合适。它会造成：

```text
今天的新指数 + 今天的新热门股票 + 昨天的涨停/跌停
```

这是当前线上和本地不一致、页面看到旧数据的主要原因。

## 历史源备份

以下源只做历史记录，重构后不再进入 A 股主链路。

### 东方财富相关源

| 历史用途 | 接口/封装 | 问题 |
|---|---|---|
| 涨停池 | AkShare `stock_zt_pool_em` | 线上多次 502 |
| 跌停池 | AkShare `stock_zt_pool_dtgc_em` | 线上多次 502 |
| 全 A 行情/指数 fallback | AkShare 部分 `*_em` 接口 | 底层容易回到东方财富 HTTP |
| 股票跳转链接 | `https://quote.eastmoney.com/...` | 只是外链，不是数据源，可后续替换为新浪/腾讯/交易所链接 |

### SeeSea 股票 SDK fallback

历史上存在 SeeSea 股票 SDK fallback 相关测试和配置，例如：

```text
SEESEA_STOCK_SDK_FALLBACK_ENABLED
SeeSeaClient(enable_stock_sdk_fallback=...)
```

这条链路不应该再作为 A 股行情页的数据源。SeeSea 继续只承担热榜聚合，不进入 `/api/market/cn`。

### 腾讯/新浪/网易指数兼容源

当前它们只承担指数兼容和个股补行情。重构后不再作为主链路兜底，避免多个源之间时间戳、交易日、字段口径不一致。

### AkShare A 股实时相关源

AkShare 继续可以保留给美股或其他已稳定功能，但 A 股页面主链路不再依赖以下方法：

```text
stock_zh_a_spot
stock_hot_follow_xq
stock_market_fund_flow
stock_zt_pool_em
stock_zt_pool_dtgc_em
stock_zh_index_spot_em
```

北向资金、融资融券、龙虎榜属于后续“盘后增强模块”，不进入第一版实时主链路。

## 新数据源方案

第一版采用 `opentdx` 作为 A 股页面主源。

已经在线上容器验证过的能力：

```text
TdxClient.stock_quotes([(MARKET.SZ, "000001"), (MARKET.SH, "600519")])
TdxClient.stock_quotes_list(CATEGORY.A, ...)
```

已验证返回字段包括：

```text
market
code
close
open
high
low
pre_close
server_time
vol
cur_vol
amount
in_vol
out_vol
rise_speed
turnover
handicap.bid
handicap.ask
```

第一版建议使用能力：

| 模块 | opentdx 能力 | 说明 |
|---|---|---|
| 大盘指数 | `stock_quotes()` | 拉上证、沪深300、中证500、科创50等指数或指定代码 |
| 热门股票 | `stock_quotes_list(CATEGORY.A, sort_type=...)` | 用涨跌幅/成交额排序生成榜单 |
| 市场广度 | `stock_quotes_list(CATEGORY.A, count=全量或分页)` | 统计上涨、下跌、平盘、成交活跃 |
| 涨跌停 | `close + pre_close + 市场规则` 自算 | 不再依赖东方财富涨跌停池 |
| 板块风向 | `stock_top_board()` | 做行业/概念强弱榜 |
| 异动雷达 | `stock_market_monitor()` / `stock_unusual()` | 需要上线前再实测；失败时降级为放量股票 |

暂不进入第一版：

| 模块 | 原因 |
|---|---|
| 北向资金 | 免费源多依赖东方财富或网页抓取，先不重新引入不稳定 HTTP 源 |
| 融资融券余额 | 非实时数据，适合日更或盘后更新 |
| 龙虎榜 | 盘后数据，不适合 3 分钟实时刷新链路 |
| mootdx | 安装测试时会降级 `httpx`，和项目依赖 `httpx>=0.28.0` 冲突 |

## 目标 API 结构

后端 `/api/market/cn` 仍返回 camelCase JSON，但需要扩展数据完整性字段。

建议目标结构：

```json
{
  "indices": [],
  "stocks": [],
  "analysis": {
    "marketBreadth": [],
    "limitUp": [],
    "limitDown": [],
    "activeStocks": [],
    "sectorTrends": []
  },
  "source": "opentdx",
  "dataDate": "2026-05-29",
  "marketStatus": "trading",
  "stale": false,
  "staleReason": null,
  "updatedAt": "2026-05-29T09:40:00+08:00"
}
```

其中 `analysis.fundFlows` 建议改名为 `analysis.marketBreadth`。如果为了前端兼容短期保留 `fundFlows`，也只能作为同源数据别名，不能再表示 AkShare 资金流。

## 必删历史兼容逻辑

重构代码时需要删除以下能力，避免历史源继续参与线上结果。

### 后端客户端层

删除或废弃 `backend/app/clients/cn_market.py` 中这些源：

```text
_TENCENT_INDEX_URL
_SINA_INDEX_URL
_NETEASE_INDEX_URL
_fetch_tencent_indices()
_fetch_sina_indices()
_fetch_netease_indices()
_fetch_tencent_hot_stock_quotes()
_run_akshare("stock_zh_a_spot")
_run_akshare("stock_hot_follow_xq")
_run_akshare("stock_market_fund_flow")
_run_akshare("stock_zt_pool_em")
_run_akshare("stock_zt_pool_dtgc_em")
_run_akshare("stock_zh_index_spot_em")
```

新增一个清晰的 TDX 客户端，例如：

```text
backend/app/clients/tdx_market.py
```

职责只包括：

```text
连接/选择 TDX 服务
拉取指数
拉取 A 股列表/榜单
计算涨跌停
生成市场广度
生成板块风向
生成放量/异动股票
```

### Scheduler 层

删除 `_merge_cn_market_cache_on_partial_empty()` 的旧字段合并策略。

新的缓存规则：

```text
TDX 完整成功：
  写入新快照，stale=false

TDX 失败或关键字段不完整：
  不写半成品快照
  保留上一份完整快照
  API 返回上一份快照时 stale=true，staleReason=本次刷新失败原因

新数据缺涨停/跌停：
  不能用旧涨停/跌停补
  本次快照视为不完整，不覆盖上一份完整快照
```

关键字段完整性建议：

```text
indices 至少 3 个
stocks 至少 10 个
analysis.marketBreadth 非空
analysis.limitUp 和 analysis.limitDown 必须是同一次 TDX 扫描结果
updatedAt 必须是本次刷新时间
dataDate 必须是中国交易日
source 必须是 opentdx
```

### API 层

`/api/market/cn` 继续只读缓存，不在请求时临时拉行情。

如果缓存不存在：

```text
返回空数据 + stale=true + staleReason="NO_CN_MARKET_SNAPSHOT"
```

如果缓存过期：

```text
返回上一份完整快照 + stale=true
不拼接任何历史字段
```

### Frontend 层

`/ui-new/a-share` 需要改成只展示新结构，不再做“未知字段自动展开”。

需要删除页面里的历史兼容展示：

```text
extraFields()
standardFields()
analysisExtraGroups
indexDetailFields()
stockDetailFields()
limitDetailFields()
fundFlowDetailFields()
```

页面只展示明确字段：

```text
指数卡片
热门/成交活跃股票
市场温度/市场广度
涨停股票
跌停股票
板块风向
放量/异动股票
数据状态条：source、dataDate、updatedAt、staleReason
```

不要把后端新增的任何临时字段自动透出到页面，避免历史兼容字段污染 UI。

## 涨跌停计算规则

涨跌停不再读东方财富涨跌停池，改为 TDX 实时行情自算。

基础规则：

| 股票类型 | 涨跌幅限制 |
|---|---:|
| 主板普通股 | 10% |
| ST / `*ST` | 5% |
| 创业板 `300` / `301` | 20% |
| 科创板 `688` | 20% |
| 北交所 `8` / `4` / `9` 开头 | 30% |

跳过或标记 unknown 的情况：

```text
pre_close <= 0
新股首日/上市前五日
停牌
除权除息日价格口径异常
close、pre_close、盘口字段缺失
```

判断涨停/跌停时不要只看百分比，建议同时参考：

```text
close 是否接近理论涨停价/跌停价
卖一为 0 或卖盘极小，可辅助判断涨停封板
买一为 0 或买盘极小，可辅助判断跌停封板
```

## 调度策略

建议调度采用北京时间：

```text
09:01  预热/连通性检查，不覆盖正式行情
09:16  集合竞价快照
09:31-11:30  每 3 分钟刷新
11:31  上午收盘快照
13:00-15:00  每 3 分钟刷新
15:01  收盘快速快照
15:05  最终收盘快照
非交易时段  每 1 小时轻量检查
周末/节假日  降低频率，只保留上一交易日完整快照
```

调度原则：

```text
预热检查不覆盖正式行情
交易中刷新必须写完整快照
收盘后 15:05 快照优先级最高
非交易时段不能用空结果覆盖收盘快照
```

## 上线前验证清单

### 容器内源验证

```bash
docker compose -f ops/docker-compose.yml exec -T api python - <<'PY'
from opentdx import TdxClient, MARKET, CATEGORY, SORT_TYPE

c = TdxClient()
print(c.stock_quotes([(MARKET.SZ, "000001"), (MARKET.SH, "600519")]))
rows = c.stock_quotes_list(CATEGORY.A, start=0, count=20, sort_type=SORT_TYPE.CHANGE_PCT, reverse=True)
for row in rows[:5]:
    close = row.get("close")
    pre_close = row.get("pre_close")
    pct = None
    if close and pre_close:
        pct = round((close - pre_close) / pre_close * 100, 2)
    print(row.get("market"), row.get("code"), close, pre_close, pct, row.get("server_time"))
PY
```

### 刷新任务验证

```bash
docker compose -f ops/docker-compose.yml exec -T api python -m app.jobs.refresh_cn_market
curl -s http://127.0.0.1:18081/api/market/cn
docker compose -f ops/docker-compose.yml logs --tail=120 cn-market-refresh
```

### 页面验证

```text
http://127.0.0.1:18081/ui-new/a-share
```

页面必须确认：

```text
有 source=opentdx 或等价来源标识
updatedAt 是本次刷新时间
dataDate 是当前交易日或上一交易日收盘日
stale=false 时所有模块来自同一快照
stale=true 时明确提示延迟原因
涨停/跌停不是旧日期缓存
```

## 实施顺序

1. 新增 TDX 客户端与 opentdx 依赖。
2. 替换 A 股刷新任务数据源。
3. 删除 AkShare/东方财富/腾讯/新浪/网易在 A 股主链路里的历史兼容。
4. 删除旧缓存字段合并逻辑。
5. 扩展 `CnMarketResponse` 数据完整性字段。
6. 重构 `/ui-new/a-share` 页面，只展示新结构。
7. 补测试：完整快照、刷新失败不覆盖、涨跌停自算、无旧字段混入。
8. Docker Compose 本地验证。
9. 构建推送镜像并在线上执行一次刷新。

## 不做事项

第一版不做：

```text
商业行情 API
东方财富/SeeSea 作为 A 股兜底源
mootdx
北向资金
融资融券
龙虎榜
前端临时拼接旧字段
请求页面时同步拉行情
```

本次修复的核心不是多接几个源，而是让 A 股页面只接受同一来源、同一时间、同一交易日的完整快照。
