# TradingAgents 引进规划

上游：[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) v0.3.1（Apache 2.0）。
多智能体 LLM 研报框架，不是实盘交易系统。本仓库只把它当**分析引擎**用。

落地原则和 Qlib 相同：

- `vendor/tradingagents/` 放源码参考（可编辑依赖），不当运行目录。当前钉 `v0.3.1`（`01477f9afb7a47b849ed4c9259d3a9a4738d9fda`）
- `tools/analyze/` 是唯一运行环境，自带 `.venv`
- 管控面 core 用子进程调用，不把 LangGraph 装进 core
- 报告、缓存写 `data/tradingagents/`，不写 `~/.tradingagents`

不要整仓引进 [TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN)。它的 `app/`、`frontend/` 许可证是混合的，还带 MongoDB / Redis / Vue，和本仓「轻量本地工具」冲突。A 股数据适配可以参考它，不当运行依赖。

```
ingest     行情进 market.db
qlib       量化特征 / 打分 / 出候选
analyze    对池内个股做多智能体研报（本规划）
select     以后可以吃 qlib 分数 + analyze 结论
control    只编排，不进 LangGraph
```

合理工作流：盘后 sync →（可选）qlib top N → 在 UI 里对候选或池内个股点「分析」。

| 期 | 文档 | 状态 | 做什么 |
|----|------|------|--------|
| 1 | [phase-1.md](./phase-1.md) | 已落地 | 引进源码 + 独立 CLI + **UI 配置 + UI 发起分析 + 看报告**。行情仍走 Yahoo。 |
| 2 | 未开写 | 未开始 | 价格和技术指标改读 `market.db`。基本面/新闻仍走外网。 |
| 3 | 未开写 | 未开始 | 批量分析、和 Qlib 候选打通、ingest 扩财报/公告。 |

第 1 期已经把「能在网页里配、能在网页里跑」算进范围，不再把管控面留到第 3 期。第 3 期只剩产品深化，不是第一次接 UI。
