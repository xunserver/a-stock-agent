# a-stock-agent

本地低频 A 股工具仓：采集、选股、分析与管控面彼此独立，**各有各的环境**，根目录不放 Python `.venv`。JS 用仓库根 pnpm workspace。

```
a-stock-agent/
  .astock-root          # 仓库根标记，供各工具定位共享 data/
  data/                 # 共享 SQLite（market.db）和 Qlib .bin（data/qlib）
  packages/core/        # 共享 SQLite 访问（astock-core，无独立 venv）
  packages/ui/          # 共享 React 页面（@astock/ui）
  tools/ingest/         # 数据采集  →  tools/ingest/.venv
  tools/select/         # 选股      →  tools/select/.venv
  tools/analyze/        # 分析      →  tools/analyze/.venv
  tools/qlib/           # Qlib 研究框架 → tools/qlib/.venv（Python 3.12）
  apps/desktop/         # Electron 壳：开窗时拉起 core
  apps/control-plane/
    core/               # 管控面编排进程 → apps/control-plane/core/.venv
    cli/                # 薄 HTTP 客户端 → apps/control-plane/cli/.venv
    ui/                 # 浏览端薄宿主（可选）
  vendor/akshare/       # AKShare 源码参考，不要当运行目录
  vendor/qlib/          # Qlib 源码参考，不要当运行目录
```

## 环境

每个工具在自己的目录里 `uv sync`，不要在仓库根执行 `uv sync`。

```bash
# 采集（依赖 akshare）
cd tools/ingest && uv sync

# 选股 / 分析（目前只依赖 core 读库，以后各自加包）
cd tools/select && uv sync
cd tools/analyze && uv sync

# Qlib（pyqlib 官方支持到 3.12，本工具单独钉 3.12）
cd tools/qlib && uv sync

# 管控面 core（编排 daemon）
cd apps/control-plane/core && uv sync

# 管控面 CLI（只打 HTTP）
cd apps/control-plane/cli && uv sync

# 管控面 UI（Electron 桌面 + 可选浏览端，仓库根 pnpm workspace）
pnpm install
```

`packages/core` 没有自己的虚拟环境。ingest / select / analyze / qlib / control-plane core 通过 `tool.uv.sources` 以可编辑路径依赖它，读的是同一份 `data/market.db`。

## 管控面

桌面端、浏览端和 CLI 都把命令交给 **core 常驻进程**。core 自己读库做查询，长任务用子进程调用 `tools/ingest`（以后也包括 qlib）。core 没起来时，CLI 会直接报错，不会本地偷偷执行。

日常用 Electron：打开窗口时 main 进程会自己拉起 core（`127.0.0.1:8787`），关窗一起停。不要同时再手动起一份 core，否则桌面会因端口占用而报错。

```bash
# 桌面端（一条命令：窗口 + core）
pnpm --filter desktop dev
# 或在仓库根：pnpm dev

# 浏览端仍可用（需另开终端自己起 core）
uv --directory apps/control-plane/core run python -m astock_control
pnpm --filter ui dev

# CLI
uv --directory apps/control-plane/cli run python -m astock_ctl status
uv --directory apps/control-plane/cli run python -m astock_ctl quotes sync
uv --directory apps/control-plane/cli run python -m astock_ctl jobs
```

工具自己的 CLI 仍可直接跑，给 debug 用：`uv --directory tools/ingest run python -m astock …`

## 股票管理

所有命令都在 `tools/ingest` 环境里跑。`--pool` 不写就是 `default`，可放在子命令前后：

```bash
uv --directory tools/ingest run python -m astock --pool default pool
uv --directory tools/ingest run python -m astock pool --pool default
```

### 股票池

盘后先改池，再按池拉行情。**移出不会删已入库的日线**；再次加入只补缺口。从未进过库的新票拉上市以来全部日线。

```bash
# 池摘要（在池/已移除、谁缺全历史、资料覆盖）
uv --directory tools/ingest run python -m astock pool

# 用沪深300并入（不踢掉手工加的票）
uv --directory tools/ingest run python -m astock pool add --index hs300

# 池子就是该指数：不在指数里的标为移除
uv --directory tools/ingest run python -m astock pool set --index hs300

# 手工加减
uv --directory tools/ingest run python -m astock pool add --codes 000001,600519
uv --directory tools/ingest run python -m astock pool remove --codes 000001

uv --directory tools/ingest run python -m astock pool list
uv --directory tools/ingest run python -m astock quotes pending
uv --directory tools/ingest run python -m astock quotes sync
uv --directory tools/ingest run python -m astock status
```

指数别名：`hs300` `zz500` `zz1000` `sz50` `kc50` `cyb`，也可以直接写 `000300`。

### 个股

```bash
# 资料 + 库内日线摘要 + 最新一根 K
uv --directory tools/ingest run python -m astock stock show 000001

# 同步资料并补齐日线（不写代码 = 当前池全部活跃成员）
uv --directory tools/ingest run python -m astock stock sync 000001
uv --directory tools/ingest run python -m astock stock sync 000001 --info
uv --directory tools/ingest run python -m astock stock sync 000001 --quotes
uv --directory tools/ingest run python -m astock stock sync --info
```

`--json` 可加在任意子命令上，适合脚本读取。

## Qlib

行情仍以 `data/market.db` 为准。`tools/qlib` 只负责把日线打成 Qlib 二进制，并在本地跑研究接口。不下载 Yahoo 官方 `cn_data`。

库内 6 位代码会转成 `SZ000001` / `SH600519`；指数 `sh000300` 变成基准 `SH000300`。前复权价直接入库，`factor` 固定为 1（没有未复权价，不能还原真实成交价）。`$vwap` 用 `(high+low+close)/3`，与复权价同一量纲。

```bash
# 生成 data/qlib（calendars / instruments / features）
uv --directory tools/qlib run python -m astock_qlib dump

uv --directory tools/qlib run python -m astock_qlib status
uv --directory tools/qlib run python -m astock_qlib smoke

# 表达式取数
uv --directory tools/qlib run python -m astock_qlib features --codes 000001 --fields '$close,$volume' --start 2024-01-01
```

`dump` 会写 `instruments/csi300.txt`（当前池）和 `instruments/all.txt`（含指数）。之后可在 Python 里：

```python
from astock_qlib.runtime import init_qlib
from qlib.data import D

init_qlib()
print(D.features(["SZ000001"], ["$close", "Ref($close, 1)/$close"]).tail())
```

LightGBM + Alpha158 工作流（按库内约 5 年区间切好 train/valid/test）：

```bash
# 需已 dump；结果写入仓库根 mlruns/
uv --directory tools/qlib run python -m astock_qlib workflow
```

配置文件：`tools/qlib/configs/workflow_lightgbm_alpha158.yaml`  
（`provider_uri` 运行时会改写成当前 `data/qlib`；切分约为 train 2021-11~2024-06 / valid 2024-07~2025-06 / test 2025-07~2026-08-25。结束日留在倒数第二个交易日，避免 Qlib 回测越界。）

## 多智能体分析（TradingAgents）

引进规划在 `docs/tradingagents/`。第 1 期已经能在管控面里配置 LLM、对池内个股发起分析；行情仍走 Yahoo。第 2 期再接本地 `market.db`。

```bash
cd tools/analyze && uv sync

uv --directory tools/analyze run python -m astock_analyze status
uv --directory tools/analyze run python -m astock_analyze run --code 000001
```

桌面或网页：系统设置 →「多智能体分析」填提供商/模型/密钥；`/analyze` 选股后点开始；长任务在 `/jobs`。core 用子进程调上面的 CLI，报告写在 `data/tradingagents/reports/`。

- 三期总图：[docs/tradingagents/README.md](docs/tradingagents/README.md)
- 第 1 期施工说明：[docs/tradingagents/phase-1.md](docs/tradingagents/phase-1.md)
