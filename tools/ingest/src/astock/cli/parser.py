"""Argument parsing for ``python -m astock``."""

from __future__ import annotations

import argparse

from astock.config import index_aliases
from astock.events import EVENT_KINDS
from astock_core.paths import DEFAULT_POOL_ID


def parse_codes(raw: str | None) -> list[str]:
    """Normalize the comma-separated stock codes accepted by CLI options."""
    if not raw:
        return []
    return [item.strip().zfill(6) for item in raw.split(",") if item.strip()]


def _common_args() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--pool", default=DEFAULT_POOL_ID, help="股票池 id，默认 default")
    common.add_argument("--json", action="store_true", help="JSON 输出")
    return common


def build_parser() -> argparse.ArgumentParser:
    """Build the stable public CLI parser without executing any use case."""
    common = _common_args()
    parser = argparse.ArgumentParser(
        description="股票管理：系统股票目录 + 股票池 + 个股资料/行情。--pool 不写则用 default。",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    pool = sub.add_parser("pool", help="股票池：增删、指数填池、查看", parents=[common])
    pool_sub = pool.add_subparsers(dest="pool_cmd")
    add = pool_sub.add_parser("add", help="加入成分（指数并入或手工代码），不剔除已有成员", parents=[common])
    add.add_argument("--index", help=f"指数别名或代码，如 hs300。别名：{', '.join(index_aliases())}")
    add.add_argument("--codes", help="逗号分隔股票代码")
    replace = pool_sub.add_parser("set", help="用指数成分覆盖股票池（不在指数中的标为移除，行情保留）", parents=[common])
    replace.add_argument("--index", required=True)
    remove = pool_sub.add_parser("remove", help="移出股票池（不删历史行情）", parents=[common])
    remove.add_argument("--codes", required=True)
    listing = pool_sub.add_parser("list", help="列出池内股票", parents=[common])
    listing.add_argument("--all", action="store_true", help="包含已移除成员")

    stock = sub.add_parser("stock", help="系统股票目录，以及个股资料/行情查看与补齐", parents=[common])
    stock_sub = stock.add_subparsers(dest="stock_cmd", required=True)
    stock_sub.add_parser("list", help="列出系统内股票", parents=[common])
    sadd = stock_sub.add_parser("add", help="加入系统股票目录（指数或手工代码）", parents=[common])
    sadd.add_argument("--index", help=f"指数别名或代码，如 hs300。别名：{', '.join(index_aliases())}")
    sadd.add_argument("--codes", help="逗号分隔股票代码")
    srm = stock_sub.add_parser("remove", help="从系统移除（在任一股票池则拒绝，不删日线）", parents=[common])
    srm.add_argument("--codes", required=True)
    show = stock_sub.add_parser("show", help="查看个股资料、库内行情摘要、最新交易日 K 线", parents=[common])
    show.add_argument("code", help="股票代码，如 000001")
    news = stock_sub.add_parser("news", help="东方财富个股新闻（实时，不入库）", parents=[common])
    news.add_argument("code", help="股票代码，如 000001")
    news.add_argument("--limit", type=int, default=20, help="最多返回条数")
    events = stock_sub.add_parser("events", help="个股公告/研报/大宗/股东变更（实时，不入库）", parents=[common])
    events.add_argument("code", help="股票代码，如 000001")
    events.add_argument("--kind", required=True, choices=sorted(EVENT_KINDS), help="事件类型")
    events.add_argument("--limit", type=int, default=None, help="最多返回条数")
    sync = stock_sub.add_parser("sync", help="同步个股资料并/或补齐日线；不写代码则处理当前池全部活跃成员", parents=[common])
    sync.add_argument("codes", nargs="?", help="一个或多个代码，逗号分隔")
    sync.add_argument("--info", action="store_true", help="只同步资料（行情快照/估值/财务/ST/停牌）")
    sync.add_argument("--quotes", action="store_true", help="只补齐日线")
    sync.add_argument("--statements", action="store_true", help="同步三大报表明细（较慢，默认关闭）")
    sync.add_argument("--sleep", type=float, default=None)
    sync.add_argument("--add-to-pool", action="store_true", help="若代码不在当前池则加入")

    quotes = sub.add_parser("quotes", help="按股票池批量同步日线", parents=[common])
    quotes_sub = quotes.add_subparsers(dest="quotes_cmd", required=True)
    qsync = quotes_sub.add_parser("sync", help="池内新票拉全历史，其余补齐到最近交易日，并写入估值/财务资料", parents=[common])
    qsync.add_argument("--sleep", type=float, default=None)
    qsync.add_argument("--adjust", default=None, choices=["", "qfq", "hfq"])
    qsync.add_argument("--history-start", default=None, help="历史起点 YYYYMMDD，默认读系统设置")
    qsync.add_argument("--periods", default=None, help="逗号分隔周期，默认读系统设置")
    qsync.add_argument("--limit", type=int)
    qsync.add_argument("--codes", help="逗号分隔股票代码；不写则同步当前池全部活跃成员")
    quotes_sub.add_parser("pending", help="只看谁需要拉全历史 / 补齐", parents=[common])

    calendar = sub.add_parser("calendar", help="交易日历", parents=[common])
    calendar_sub = calendar.add_subparsers(dest="calendar_cmd", required=True)
    cal_sync = calendar_sub.add_parser("sync", help="同步 A 股交易日历并写入水位", parents=[common])
    cal_sync.add_argument("--force", action="store_true", help="忽略今日已同步标记，强制拉取")

    boards = sub.add_parser("boards", help="东财行业/概念板块", parents=[common])
    boards_sub = boards.add_subparsers(dest="boards_cmd", required=True)
    bsync = boards_sub.add_parser("sync", help="同步行业/概念名录与成分；成员只保留系统内已有股票", parents=[common])
    bsync.add_argument("--kind", default="all", choices=["all", "industry", "concept"], help="同步范围，默认 all")
    bsync.add_argument("--sleep", type=float, default=None)
    bsync.add_argument("--limit", type=int, help="每种类型最多同步多少个板块（试跑）")

    sub.add_parser("status", help="库规模与当前池摘要", parents=[common])
    return parser
