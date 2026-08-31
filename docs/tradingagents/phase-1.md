# 第 1 期：能在管控面里配、能在管控面里跑

本文是第 1 期的施工说明。看完应能直接按章节动手，不必再翻聊天记录。三期总图见 [README.md](./README.md)。

第 1 期结束时，人在浏览器里就能：

1. 在「系统设置」填 LLM 提供商、模型、密钥、分析师组合
2. 打开「多智能体分析」页，从当前股票池挑一只票、选交易日、点开始
3. 看实时日志（任务会跑很久）
4. 跑完后看决策摘要和分段研报
5. 在「任务」页找回还在跑或已经结束的 `analyze.run`

行情第 1 期仍走 Yahoo（`000001.SZ` / `600519.SS`）。价格可能和 `market.db` 对不上，页面上要写清楚。第 2 期再接本地日线。

---

## 1. 为什么第 1 期就要接 UI

原先拆法是：第 1 期只做 CLI，第 3 期再接管控面。现在改成第 1 期就把调用和配置做到网页里，因为：

- 一次完整图是多轮 LLM，命令行盯日志不合适，现有 job + SSE 才是给人看的
- 密钥、模型、分析师组合如果只能改 `.env`，以后每次换模型都要离开 UI
- 管控面已经有「设置写入版本化 system DB、长任务走 `POST /api/jobs` + `/api/jobs/{id}/events`」这条路，ingest 的 `quotes.sync` 就是先例
- 「任务」页现在是占位。不做它，分析跑到一半一刷新就找不回来

第 1 期仍然**不做**：批量全池扫描、接 `market.db` 行情、接 Qlib 候选、财报/公告入库、social 分析师（Reddit / StockTwits 对 A 股无意义）。

---

## 2. 现状（动手时不要破坏）

### 仓库边界

每个工具自己的 `.venv`，根目录不 `uv sync`。`packages/core` 无独立环境，被 ingest / select / analyze / qlib / control-plane core 以可编辑路径依赖。

`tools/analyze` 现在几乎是空壳：`pyproject.toml` 只依赖 `astock-core`，`__main__.py` 读库打一条 JSON。第 1 期就在这里长出来，不新建 `tools/tradingagents`。

### 管控面已经能用的能力

| 能力 | 现在怎样 | 第 1 期怎么用 |
|------|----------|----------------|
| `POST /api/jobs` | 提交任务，立即返回 Job | 任务类型 `analyze.run` |
| `GET /api/jobs`、`GET /api/jobs/{id}` | 持久化任务仓库 | 任务页列表；分析页重连进行中的任务 |
| `GET /api/jobs/{id}/events` | SSE 推日志直到 succeeded/failed | 分析页实时日志 |
| `GET /api/settings` | 读版本化设置库 | 设置页读 `analyze` 段 |
| `settings.update` | **立即执行**，不排队 | 改 LLM 配置不能卡在正在跑的分析后面 |
| `IngestRunner` | `uv --directory tools/ingest run ...`，stderr 进 job.log，stdout 末尾 JSON | `AnalyzeRunner` 原样抄 |
| JobService / Executor | **单 worker 串行**，状态与日志持久化 | 分析排队即可；研报仍另写磁盘，不能只活在 Job 里 |
| 网页 | 股票池可用；股票 / Qlib / 任务都是占位；设置只有行情和调度 | 新「分析」页；把任务页做真；设置加分析段 |

core 只绑 `127.0.0.1`。密钥保存在本地设置库且不进 git；读接口必须脱敏，日志里不能出现密钥。

### 上游能直接用的接口

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
ta = TradingAgentsGraph(
    selected_analysts=("market", "news", "fundamentals"),
    debug=False,
    config=config,
)
state, decision = ta.propagate("000001.SZ", "2026-08-25")
ta.save_reports(state, "000001.SZ", save_path=...)
```

`save_reports` 会写出：

```
{save_path}/
  complete_report.md
  1_analysts/market.md, news.md, fundamentals.md
  2_research/bull.md, bear.md, manager.md
  3_trading/trader.md
  4_risk/aggressive.md, conservative.md, neutral.md
  5_portfolio/decision.md
```

LLM 用环境变量或 `TRADINGAGENTS_*`。`openai_compatible` 可以打任意 OpenAI 兼容端。国内常用：`DASHSCOPE_CN_API_KEY`、`DEEPSEEK_API_KEY`、`ZHIPU_CN_API_KEY`。

数据 vendor 第 1 期不改，继续 yfinance。A 股 ticker 必须带 `.SS` / `.SZ`。

---

## 3. 第 1 期目录和职责

```
a-stock-agent/
  vendor/tradingagents/          # clone 上游，钉 commit；源码参考 + editable 依赖
  tools/analyze/                 # 唯一运行环境
    pyproject.toml               # astock-core + tradingagents(path) + 上游传递依赖
    src/astock_analyze/
      __main__.py                # CLI：run / status / report
      codes.py                   # 000001 → 000001.SZ
      config.py                  # 读 control.json 的 analyze 段 + 环境变量
      run.py                     # 组装 DEFAULT_CONFIG，调 propagate，写报告
  data/tradingagents/
    cache/                       # 上游 data_cache_dir
    memory/trading_memory.md
    reports/{code}/{date}/{run_id}/
  data/control.json              # 新增 analyze 段（含密钥，gitignore 已覆盖）
  apps/control-plane/
    core/.../adapters/analyze.py # 子进程封装
    core/.../config.py           # analyze 默认值、校验、脱敏
    core/.../protocol.py         # analyze.run / analyze.list / analyze.get
    ui/src/pages/analyze-page.tsx
    ui/src/pages/jobs-page.tsx
    ui/src/pages/settings-page.tsx   # 加「多智能体分析」字段
```

边界：

- `astock_analyze` **不依赖** `astock_control`。它可以自己读 `data/control.json` 的 `analyze` 键（只当 JSON），这样 CLI 和 UI 用同一份配置。
- core 启动子进程时仍把配置打成环境变量，作为第二来源，并保证密钥不出现在 argv 里。
- 研报是磁盘上的文件。Job 只带 `decision`、路径、代码、日期。UI 用 `analyze.get` 读正文。

---

## 4. 配置：全部从 UI 来，落到 control.json

### 4.1 `data/control.json` 新增段

现有文件只有 `pool` / `adjust` / `quotes`。第 1 期在旁边加 `analyze`，和行情设置同一套 `settings.get` / `settings.update`。

```json
{
  "pool": "default",
  "adjust": "qfq",
  "quotes": { "...": "..." },
  "analyze": {
    "llm_provider": "openai_compatible",
    "deep_think_llm": "",
    "quick_think_llm": "",
    "backend_url": "",
    "api_key": "",
    "output_language": "Chinese",
    "analysts": ["market", "news", "fundamentals"],
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "temperature": null,
    "checkpoint_enabled": false
  }
}
```

默认值要让「没配密钥也能打开设置页」，不能让页面一进就 500。没配密钥时，点「开始分析」才报错，错误写进任务，设置页用 Alert 提示「还没有 API 密钥」。

### 4.2 提供商怎么映射到上游

设置页用下拉，不要让人填任意字符串当第一选择。第 1 期只露出国内/本地最常用的：

| UI 选项 | 写入 `llm_provider` | 密钥环境变量 | 是否显示「接口地址」 |
|---------|---------------------|--------------|----------------------|
| OpenAI 兼容端（中转 / vLLM / LM Studio） | `openai_compatible` | `OPENAI_COMPATIBLE_API_KEY` | 是，必填 |
| 通义（国内 DashScope） | 上游实际值按他们客户端为准，包装层写成他们认的 provider 名 | `DASHSCOPE_CN_API_KEY` | 否 |
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | 否 |
| 智谱 GLM（国内） | 同上，包装层对齐上游 | `ZHIPU_CN_API_KEY` | 否 |
| Ollama | `ollama` | 无 | 是，默认 `http://127.0.0.1:11434/v1` |
| OpenAI 官方 | `openai` | `OPENAI_API_KEY` | 否 |

实施时对照 `vendor/tradingagents` 里的 `llm_clients`，**以上游源码里的 provider 字符串为准**，不要凭记忆写。通义和智谱的国际/国内端点如果不一样，UI 用国内。

`deep_think_llm` / `quick_think_llm` 用普通文本框。上游模型目录变得太快，第 1 期不做模型市场。placeholder 按当前提供商给一个例子（例如兼容端 `qwen-plus`，Ollama `qwen2.5`）。

深度思考模型和快速模型都必填才能跑。可以做成「只填一个就两个都用它」，少一个心智负担。

### 4.3 密钥怎么存、怎么回显

- 明文只存在 `data/control.json` 的 `analyze.api_key`。文件已 gitignore。
- `settings.get` **不返回**明文。返回：
  - `api_key_set`: boolean
  - `api_key_hint`: 有密钥时 `"••••"` 或末四位，没有则为 `""`
- `settings.update` 里：
  - 字段缺席或 `""`：**保持原密钥**（设置页保存行情时不会把密钥抹掉）
  - 字段为非空字符串：写成新密钥
  - 字段为 `null` 或约定哨兵 `"__clear__"`：清空
- Job 日志、argv、`analyze.get`、前端 `console` 都不打密钥。
- `AnalyzeRunner` 只通过子进程 `env` 注入，不写到命令行。

设置页密码框：未改时保持空，placeholder 为「已配置，留空则不修改」或「未配置」。不要把 hint 填进 input 的 value，避免保存时把 `••••` 当新密钥写回去。

### 4.4 分析师和语言

- 默认 `["market", "news", "fundamentals"]`。social 默认关，设置里可以打开，但描述要写「依赖 Reddit / StockTwits，A 股几乎没用」。
- `output_language` 默认 `Chinese`。上游内部辩论仍是英文，这是他们的设计，页面用一句话说明即可。
- `max_debate_rounds` / `max_risk_discuss_rounds` 默认 1。调大 = 更贵更慢。数字输入，范围 1–5。
- `checkpoint_enabled` 默认关。开了会在 `data/tradingagents/cache` 写下游的 SQLite。第 1 期可以做开关，但 UI 不必做「从断点恢复」的单独按钮：同一只票同一天再跑就是新 run。真正的 resume 留给以后。

### 4.5 配置谁读

优先级（高到低）：

1. CLI 显式参数（debug 用）
2. 子进程环境变量（core 注入）
3. `data/control.json` 的 `analyze`
4. 包装层内置默认（中文、三分析师、rounds=1）

UI 正常路径走 2+3，人不必碰 `.env`。

`results_dir` / `data_cache_dir` / `memory_log_path` **不进设置页**，由包装层写死到 `data/tradingagents/...`。路径区只多一行只读「分析报告」，和现在的行情库 / Qlib 一样。

---

## 5. 协议

### 5.1 命令 `analyze.run`

```json
{
  "type": "analyze.run",
  "pool": "default",
  "code": "000001",
  "date": "2026-08-25",
  "analysts": ["market", "news", "fundamentals"]
}
```

规范化：

- `code`：6 位数字，不足补零。必须能在 `pool` 的活跃成员里找到，否则 400。
- `date`：`YYYY-MM-DD`。省略则用该票在库里的 `last_bar`；还没有日线就用今天（上海）。第 1 期不强制「必须是交易日」——Yahoo 自己会处理，本地日历校验放到第 2 期。
- `analysts`：省略则用设置里的列表。每项只能是 `market` / `social` / `news` / `fundamentals`。空数组拒绝。
- `pool`：省略则用系统默认池。

这不是 `IMMEDIATE_COMMANDS`。进队列，和 `quotes.sync` 一样走 worker。Engine 是串行的：正在 sync 时分析会排队；正在分析时 sync 也会排队。任务页要能看出来。

提交后的 Job.command 里带规范化后的 code / ticker / date / analysts，方便 UI 展示。密钥不得进入 command。

### 5.2 查询 `analyze.list`

```json
{ "type": "analyze.list", "pool": "default", "code": "000001" }
```

`code` 可选。读 `data/tradingagents/reports/`，不读内存 Job。core 重启后历史报告还在。

返回大致：

```json
{
  "count": 1,
  "reports": [
    {
      "code": "000001",
      "ticker": "000001.SZ",
      "name": "平安银行",
      "date": "2026-08-25",
      "run_id": "a1b2c3d4e5f6",
      "decision": "Hold",
      "created_at": "2026-08-26T15:01:00+00:00",
      "report_dir": "/.../data/tradingagents/reports/000001/2026-08-25/a1b2c3d4e5f6"
    }
  ]
}
```

按 `created_at` 倒序。第 1 期可以全量返回（报告不会很多）；超过 50 条再截。

每份报告目录写一个 `meta.json`，list 只读这个小文件，不扫 markdown。

### 5.3 查询 `analyze.get`

```json
{ "type": "analyze.get", "code": "000001", "date": "2026-08-25", "run_id": "a1b2c3d4e5f6" }
```

`run_id` 省略则取该日最新一次。返回 `meta` + 各段 markdown 字符串 + `complete_report`。单份报告可能几十 KB，JSON 可以扛。不要在 get 里塞 job 日志。

### 5.4 Job 成功时的 `result`

```json
{
  "code": "000001",
  "ticker": "000001.SZ",
  "date": "2026-08-25",
  "run_id": "a1b2c3d4e5f6",
  "decision": "Hold",
  "report_dir": "...",
  "complete_report": "..."
}
```

`decision` 来自 `propagate` 的第二返回值（上游是处理后的交易信号字符串）。正文用 `analyze.get`。

失败：`job.status = failed`，`error` 用人能看懂的中文（没配密钥、Yahoo 无数据、子进程非 0、LLM 4xx）。stderr 最后几行进 log。

---

## 6. `tools/analyze` 包装层

### 6.1 依赖

```toml
requires-python = ">=3.11,<3.13"
dependencies = [
    "astock-core",
    "tradingagents",
]

[tool.uv.sources]
astock-core = { path = "../../packages/core", editable = true }
tradingagents = { path = "../../vendor/tradingagents", editable = true }
```

Python 钉 3.12，和 qlib 工具一致。不要把 langchain 写进 control-plane core。

`vendor/tradingagents`：浅克隆官方仓库，README 记 commit。本仓如果还没有 git，就先把目录放在那里，和现在的 `vendor/qlib`、`vendor/akshare` 一样当嵌套克隆。

### 6.2 代码映射

| 规则 | 例子 |
|------|------|
| `6xxxxx`、`9xxxxx`、`5xxxxx` → `.SS` | `600519.SS`、`688111.SS` |
| 其余 6 位 → `.SZ` | `000001.SZ`、`300750.SZ`、`001xxx` |
| 已经带 `.SS` / `.SZ` / `.BJ` 的原样 | 仅 CLI debug |

北交所 `.BJ` 第 1 期不作为主路径。映射函数单测覆盖：000001、600519、300750、688111。

包装层在跑之前用 `MarketDB` 查名称，只用于我们的 `meta.json` 和 UI。上游 `propagate` 仍吃 Yahoo ticker。

### 6.3 CLI

```bash
uv --directory tools/analyze run python -m astock_analyze run --code 000001 --date 2026-08-25
uv --directory tools/analyze run python -m astock_analyze run --code 000001 --json
uv --directory tools/analyze run python -m astock_analyze status
uv --directory tools/analyze run python -m astock_analyze report --code 000001 --date 2026-08-25
```

`run`：

- 进度打到 **stderr**（core 才能进 job.log）
- 结束时 stdout **只有**一段 JSON（和 ingest 一样，用 `parse_trailing_json`）
- `--json` 仍然 stderr 日志 + stdout JSON
- 校验：code 合法、密钥或兼容端地址配好了、vendor 目录能 import

`status`：tradingagents 能否 import、密钥是否存在（不打印）、`data/tradingagents` 是否可写、最近 N 份报告。

`report`：把 `complete_report.md` 打到 stdout，给 CLI debug。UI 走 `analyze.get`。

### 6.4 一次 `run` 内部步骤

1. 读配置，拼 `DEFAULT_CONFIG.copy()`：provider、模型、`backend_url`、语言、rounds、路径全部改到 `data/tradingagents/`。
2. `000001` → `000001.SZ`。
3. `run_id` 用时间戳或 uuid 短号。目录：`data/tradingagents/reports/{code}/{date}/{run_id}/`。
4. 先写 `meta.json`（status=`running`），方便 UI 看见「已经开始但还没结论」。
5. `TradingAgentsGraph(...).propagate(ticker, date)`。
6. `save_reports(..., save_path=该目录)`。
7. 更新 `meta.json`：decision、status=`succeeded`、耗时。
8. stdout 打 JSON。

`debug=False`。上游若把每个 node 打到 stdout，会破坏 JSON 约定，必须确认日志在 stderr，或我们自己重定向。

进度：在包装层打阶段行，例如 `分析师: market`、`研究员辩论`、`Trader`、`风险`、`组合经理`。做不到逐 node 也没关系，至少有心跳，避免 SSE 十几分钟无输出。

### 6.5 分析前检查（失败要快）

在调 LLM 之前就失败：

- `analyze.api_key` 为空，且 provider 不是 ollama
- `openai_compatible` / `ollama` 却没有 `backend_url`
- 模型名为空
- `vendor/tradingagents` 不存在或 import 失败
- 代码不是 6 位数字

这些失败应该秒回，不要进 20 分钟的图。

Yahoo 无数据、LLM 超时是运行中失败，进 job.failed。

---

## 7. 管控面 core

### 7.1 `AnalyzeRunner`

照 `IngestRunner`：

```
uv --directory tools/analyze run python -m astock_analyze --json run --code ... --date ... --analysts ...
```

`--pool` 给包装层做「是否在池里」检查。core 在 submit 时已经查过池，子进程再查一次防止 CLI 误用。

环境变量：按提供商设置对应 `*_API_KEY`、`TRADINGAGENTS_LLM_PROVIDER`、`TRADINGAGENTS_DEEP_THINK_LLM` 等。`env.pop("VIRTUAL_ENV")` 等与 ingest 相同。argv 只打 code/date/analysts，不打密钥。

`on_log("$ " + argv)` 可以打，argv 里没有密钥。

### 7.2 配置校验

`merge_settings` / `validate_settings` 认识 `analyze`。非法 provider、rounds 越界、analysts 含未知值 → `settings.update` 在入队前就 `ProtocolError`（现在行情非法复权也是这样）。

`settings_view()` 返回脱敏后的 `analyze`，并在 `paths` 里加 `analyze: str(DATA_DIR / "tradingagents")`。

### 7.3 查询实现

`analyze.list` / `analyze.get` 只扫 `data/tradingagents/reports/**/meta.json`。core 不必 import tradingagents。

名称从 `market.db` 的 `stocks` 表补。文件在、库里没名称就空字符串。

---

## 8. UI

现有页面风格：shadcn 默认主题、`Card` + `Field` + `Table` + `Alert` + `Empty`。新页跟股票池、设置走，不另起视觉系统。缺的组件（如 `tabs`）用项目里的 shadcn skill 加，不手写一套。

没有 markdown 依赖。第 1 期报告用 `whitespace-pre-wrap` 的等宽/正文混排即可，不引入 `react-markdown`，除非正文难看再加。

### 8.1 导航

`nav.ts` 股票管理下增加：

- 标题：`多智能体分析`
- 路径：`/analyze`
- 图标：现有 lucide 里找一个（例如 `BrainIcon` 或 `FileSearchIcon`），不要和 Qlib 的 `SparklesIcon` 撞

「任务」仍在「运行」组，但要从占位改成真页面。

面包屑走现在的 `site-header` + `navGroups`，新项加进 groups 就会亮。

### 8.2 系统设置：多智能体分析

在现有「行情 / 调度 / 路径」下面加第四段 `FieldSet`，同一张表单一次保存。保存仍走 `updateSettings`，patch 带 `analyze`。

字段：

1. 提供商（Select）
2. 接口地址（仅兼容端 / Ollama 显示）
3. 深度模型、快速模型（两个 Input；可加「与深度模型相同」的小开关）
4. API 密钥（password）。placeholder 按 `api_key_set` 切换。value 只在用户开始输入后非空
5. 输出语言（中文 / English，ToggleGroup）
6. 分析师（四个 Switch：技术 / 新闻 / 基本面 / 情绪）
7. 辩论轮数、风险轮数（number）
8. 温度（可空，空 = 提供商默认）
9. 断点保存（Switch，默认关）

路径段只读增加「分析报告」。

页顶加一条非错误 Alert：**第 1 期行情来自 Yahoo，不是本地 market.db；A 股覆盖一般，价格可能和股票池里的日线不一致。** 设置页、分析页各出现一次，不要每张卡片都写。

未配密钥时，保存提供商和模型仍然成功（允许先填模型后填密钥）。只有「开始分析」才硬拦。

### 8.3 新页：`/analyze`

这是第 1 期的主界面，建议三块，都在一页，用现有 `flex flex-col gap-4`。

**A. 发起分析（Card）**

- 股票池：和股票池页一样，先 `queryPools`，默认系统设置的 pool
- 股票：当前池活跃成员，Select 或可输入过滤。显示 `code name`
- 交易日：`<Input type="date">`，选中股票后默认填 `last_bar`
- 分析师：默认跟设置，可在当次覆盖（Toggle），不必为改一次分析师去设置页
- 主按钮「开始分析」。进行中 disable，并显示 Spinner
- 未配密钥：按钮 disable + FieldDescription 链到 `/settings`

提交：`POST /api/jobs` `{ type: "analyze.run", pool, code, date, analysts }`，不要等待任务完成而卡死整页（分析可能 10–30 分钟）。实时状态统一由 `JobProvider` 的 SSE 状态源提供。

Engine 串行：若已有 `running` 任务，仍允许提交（进入 queued），按钮旁写「当前有任务在跑，会排队」。可用 `GET /api/jobs` 判断。

**B. 本次运行（Card）**

- 状态 Badge：queued / running / succeeded / failed
- `ScrollArea` 跟日志，等宽、自动滚到底
- 失败展示 `job.error`
- 成功展示决策（大号文本）+ 「查看报告」滚到下面或打开分段

进入页面时 `GET /api/jobs`，若有未结束的 `analyze.run`，自动接上 SSE，避免刷新丢进度。

**C. 历史报告（Card / Table）**

- `analyze.list`，可按当前选中 code 过滤，也可看整个池
- 列：代码、名称、日期、决策、时间、操作「打开」
- 打开后用 Tabs 或一组按钮切分段：摘要 / 技术 / 新闻 / 基本面 / 研究 / 交易 / 风险 / 组合 / 全文
- 正文来自 `analyze.get`，`pre` + `whitespace-pre-wrap` + `text-sm`
- 空状态：还没有报告时用现有 `Empty`

不在第 1 期做：导出 PDF、对比两次 run、在股票详情页内嵌（股票页仍是占位）。

### 8.4 把 `/jobs` 做成真页面

分析跑得太久，必须有一个和「这一票」解耦的任务箱。`quotes.sync` 也能从占位变成可见。

最小可用：

- 表格：id、type、status、创建时间、结束时间、error 摘要
- 点行展开或进 `/jobs/:id`：日志 ScrollArea + 若是 `analyze.run` 且成功，链到 `/analyze?code=&date=&run=`
- 初始列表读取 `GET /api/jobs`，进行中的任务统一由共享 SSE 状态源更新，不在页面重复轮询
- 空状态说明：任务和日志会持久化；进程重启时未完成任务会被明确标记为中断

第 1 期可以不做独立 `/jobs/:id` 路由，用 Sheet 或页内展开。有 `sheet` 组件。

### 8.5 `api.ts`

增加类型和函数，风格与现有一致：

- `Settings.analyze`、`SettingsPatch.analyze`
- `submitAnalyzeRun(...)` → 返回 Job（不等待结束）
- `listAnalyzeReports(...)`、`getAnalyzeReport(...)`
- `listJobs()`（现在只有 `getJob` / `watchJob`）

`updateSettings` 的 patch 必须能只改 `quotes` 而不碰 `analyze.api_key`（见 4.3）。

### 8.6 CLI（薄客户端）

`astock_ctl` 加：

```bash
astock_ctl analyze run --code 000001 [--date ...] [--no-wait]
astock_ctl analyze list [--code ...]
astock_ctl analyze show --code 000001 --date 2026-08-25
```

`settings set` 加分析相关 flag，不是第 1 期必须；网页能改为先。`analyze run` 建议做，方便不打开浏览器调试编排。

---

## 9. 数据流（一次完整点击）

```
浏览器 /analyze
  → POST /api/jobs  {type: analyze.run, code, date}
  → JobService 入队
  → AnalyzeRunner
       读 settings.analyze（含密钥）
       env 注入后：
       uv --directory tools/analyze run python -m astock_analyze --json run ...
  → astock_analyze
       000001 → 000001.SZ
       写 reports/.../meta.json (running)
       TradingAgentsGraph.propagate()     # Yahoo + LLM
       save_reports()
       写 meta.json (succeeded)
       stdout JSON
  → job.result = 那段 JSON
  → SSE status=succeeded
  → 浏览器 analyze.get 拉 markdown 渲染
```

配置流：

```
设置页表单
  → POST settings.update  {settings: {analyze: {...}}}
  → 立即写 data/control.json
  → settings.get 回脱敏对象，表单不回填明文密钥
```

---

## 10. 明确不做（第 1 期）

- 改上游 `interface.py` / 注册 `astock` vendor（第 2 期）
- 用 `market.db` 的 OHLCV 替代 Yahoo
- 引进 TradingAgents-CN 的前端、Mongo、Tushare 管线
- 把 LangGraph 装进 core 的 venv
- social 分析师作为默认开
- 全池批量、定时每日分析
- 和 Qlib 候选页打通
- 报告 PDF / Word
- 密钥加密或系统钥匙串（本地单用户，gitignore 足够）
- core 任务持久化到 SQLite（仍内存；报告在磁盘）
- 并行跑两个 analyze（Engine 保持单 worker）

---

## 11. 验收

### 配置

- 打开设置能看到「多智能体分析」段，保存后刷新还在。
- 只改请求间隔再保存，已有 API 密钥不会被清空。
- `settings.get` 的 JSON 里没有完整密钥。
- 路径里能看到分析报告目录。

### 运行

- 未配密钥点开始：立刻失败，中文错误，不出现 Python traceback 当唯一说明。
- 配好兼容端或国内 provider 后，对池内一只票能提交任务，状态 queued → running → succeeded/failed。
- running 时日志在涨；刷新分析页能接上未结束任务。
- 成功后有决策文本，历史表多一行，打开能看到至少技术/新闻/基本面和组合经理分段（Yahoo 某段 NO_DATA 时，该段可以是「无数据」而不是整次失败——以上游行为为准，包装层不要吞掉成功的 state）。
- `data/tradingagents/reports/000001/<date>/<run_id>/complete_report.md` 存在。
- 任务页能看到这次 `analyze.run`，也能看到以前的 `quotes.sync`。

### 边界

- `quotes.sync` 和股票池页行为与现在相同。
- control-plane core 的 `uv tree` 里没有 langchain / langgraph / yfinance。
- `tools/ingest`、`tools/qlib` 的 venv 没有 tradingagents。
- `.gitignore` 覆盖 `data/tradingagents/`；密钥文件不进版本库。

### 警告

- 分析页能看见 Yahoo 数据源说明。
- 同一只票跑两次，结论可以不同（上游非确定性）。不当 bug。

没有可用的 LLM 密钥时，用「缺密钥快速失败」验收编排，不要为了 CI 真打付费 API。包装层对 `propagate` 做可替换入口，core 测只测 argv 和 JSON 解析。

---

## 12. 测试怎么写

**core（无 LLM）**

- `validate_settings` 接受合法 `analyze`，拒绝未知 provider / 空 analysts / rounds=0
- 脱敏：写入密钥后 `settings_view()["analyze"]` 无明文，有 `api_key_set`
- 保存时省略 `api_key` 或 `""`，旧密钥仍在文件里
- `normalize_command`：code 补零、非法 code、未知 analyst
- `analyze_argv`：directory 是 `tools/analyze`，无密钥，有 `--code` `--date`
- `parse_trailing_json` 仍能从混有 stderr 风格的 stdout 取出结果
- `analyze.list` / `analyze.get` 用临时目录下的假 `meta.json` + markdown

**analyze 包装（无 LLM）**

- 代码映射表
- 缺密钥时 `run` 在 import 图之前退出非 0，stdout/stderr 有中文
- `meta.json` 字段稳定

**UI**

- 无组件单测现状。第 1 期用浏览器走主路径：设置 → 保存 → 分析页提交（可用缺密钥失败）→ 任务页能看到 failed job。有 LLM 再手跑一只票。

---

## 13. 建议动手顺序

按这个切，每一步都可以停下来看。

1. **文档已完成**（本文件）。
2. **vendor 克隆**：`vendor/tradingagents` 钉 commit；`.gitignore` 加 `data/tradingagents/`；根 README 加一小节指针。
3. **control.json 的 analyze 段**：默认值、merge、validate、脱敏。设置 API 先打通，UI 还没字段也能用 CLI/`curl` 写配置。测试先写。
4. **包装层骨架**：codes、config 读取、CLI `status` / `run` 的快速失败。此时可以还不调 `propagate`。
5. **真跑通一只**（开发者本机、有密钥）：`run.py` 接 `TradingAgentsGraph`，报告落到 `data/tradingagents/reports`。先 CLI，不接管控面。
6. **AnalyzeRunner + 协议**：`analyze.run` / `list` / `get`。`astock_ctl analyze run --no-wait` + `jobs logs`。
7. **设置页 UI**：提供商、模型、密钥、分析师。浏览器保存、刷新、脱敏。
8. **分析页 UI**：选股、提交、SSE 日志、历史、分段正文。
9. **任务页 UI**：列表 + 日志，analyze 与 quotes.sync 都能看。
10. **收尾**：README 命令、验收清单、Yahoo 警告文案、确认 core 没被污染。

5 是唯一必须碰付费/本地 LLM 的一步。5 不过，6–9 用假 Runner 也能把 UI 接上。

---

## 14. 风险和产品文案

| 风险 | 第 1 期怎么处理 |
|------|-----------------|
| Yahoo A 股差、停牌、延迟 | 页面警告；失败回 NO_DATA 而不是编价格（上游已做） |
| 一次分析很贵很慢 | 默认 rounds=1、关 social；UI 写「可能需要十几分钟」 |
| 密钥写进 git / 日志 | gitignore + 脱敏 + argv 不带密钥；code review 盯这三项 |
| Engine 内存任务丢 | 任务页写明；报告以磁盘为准 |
| 串行排队 | 分析页提示「会排队」 |
| 上游 API 改名 | editable vendor，对照源码映射 provider，不要抄过期 README |
| stdout 被上游污染 | 包装层约束：JSON 只在最后一行；core 用 raw_decode；上游日志尽量 stderr |
| 日志超过 2000 行 | 包装层打阶段，不转发 token 流；必要时再把 LOG_LIMIT 提高并写进注释 |

免责：沿用上游立场——研究工具，不是投资建议。分析页页脚一行即可，不要做成法律长文。

---

## 15. 和第 2、第 3 期的接口

第 1 期把这些名字定死，后面只换实现：

- 命令仍叫 `analyze.run`，字段仍是 `code` + `date` + `analysts`
- 报告仍在 `data/tradingagents/reports/{code}/{date}/{run_id}/`
- 设置仍在 `control.json.analyze`

第 2 期：包装层注册本地 vendor，设置里多一个只读「行情来源：本地库」，UI 可以去掉 Yahoo 警告。命令不变。

第 3 期：`analyze.run` 可以接受 `codes: []` 做批量（多次入队或一个 job 循环）；Qlib 候选页「分析这些」就是跳到 `/analyze` 带 query。第 1 期的单票 UI 还是入口。
