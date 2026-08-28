"""按市场定义的交易日切点（session as-of）与日历市场目录。

股票与期货的「当前交易日」切点不同：A 股用早盘前切日，期货夜盘可能从前一晚起算。
调用方应通过 market_id 取政策，不要写死 8 点或 date.today()。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MARKET_CN_A = "cn_a"
# 预留：夜盘开盘即进入下一交易日时，用更晚的 session_open（例如 20:30）。
MARKET_CN_FUTURES = "cn_futures"
MARKET_US = "us"

DEFAULT_MARKET = MARKET_CN_A


@dataclass(frozen=True)
class SessionPolicy:
    """单个市场的会话切日规则。"""

    market_id: str
    timezone: str
    # 本地时刻到达后，才允许把「今天」纳入 as_of 天花板（若今天是交易日）。
    session_open: time


@dataclass(frozen=True)
class TradingHours:
    """展示用交易时段（市场本地时区）。"""

    label: str
    start: time
    end: time


@dataclass(frozen=True)
class CalendarMarket:
    """可供 UI 选择的交易日历市场。"""

    market_id: str
    title: str
    # active：已有/可同步数据；planned：占位，暂无日历数据。
    status: str
    sessions: tuple[TradingHours, ...] = ()
    sessions_note: str | None = None
    badge: str = ""


CN_A = SessionPolicy(
    market_id=MARKET_CN_A,
    timezone="Asia/Shanghai",
    session_open=time(8, 0),
)

# 占位：具体切点以后按品种/交易所再定，勿在业务里写死。
CN_FUTURES = SessionPolicy(
    market_id=MARKET_CN_FUTURES,
    timezone="Asia/Shanghai",
    session_open=time(20, 30),
)

US = SessionPolicy(
    market_id=MARKET_US,
    timezone="America/New_York",
    session_open=time(4, 0),
)

_POLICIES: dict[str, SessionPolicy] = {
    CN_A.market_id: CN_A,
    CN_FUTURES.market_id: CN_FUTURES,
    US.market_id: US,
}

CALENDAR_MARKETS: tuple[CalendarMarket, ...] = (
    CalendarMarket(
        MARKET_CN_A,
        "A股",
        "active",
        sessions=(
            TradingHours("集合竞价", time(9, 15), time(9, 25)),
            TradingHours("上午连续竞价", time(9, 30), time(11, 30)),
            TradingHours("下午连续竞价", time(13, 0), time(15, 0)),
        ),
        badge="A",
    ),
    CalendarMarket(
        MARKET_CN_FUTURES,
        "国内期货",
        "planned",
        sessions=(
            TradingHours("日盘（示意）", time(9, 0), time(15, 0)),
            TradingHours("夜盘（示意）", time(21, 0), time(2, 30)),
        ),
        sessions_note="各品种日盘/夜盘时段不同，接入后按交易所规则细化。",
        badge="期",
    ),
    CalendarMarket(
        MARKET_US,
        "美股",
        "planned",
        sessions=(TradingHours("常规交易", time(9, 30), time(16, 0)),),
        sessions_note="美东时间；盘前盘后另计。",
        badge="美",
    ),
)

_CALENDAR_BY_ID = {item.market_id: item for item in CALENDAR_MARKETS}


def get_policy(market_id: str | None = None) -> SessionPolicy:
    key = market_id or DEFAULT_MARKET
    try:
        return _POLICIES[key]
    except KeyError as exc:
        raise ValueError(f"未知市场: {key}") from exc


def get_calendar_market(market_id: str | None = None) -> CalendarMarket:
    key = market_id or DEFAULT_MARKET
    try:
        return _CALENDAR_BY_ID[key]
    except KeyError as exc:
        raise ValueError(f"未知市场: {key}") from exc


def list_calendar_markets() -> list[dict[str, str]]:
    return [
        {"id": item.market_id, "title": item.title, "status": item.status, "badge": item.badge}
        for item in CALENDAR_MARKETS
    ]


def _fmt_hm(value: time) -> str:
    return value.strftime("%H:%M")


def serialize_sessions(market: CalendarMarket) -> list[dict[str, str]]:
    return [
        {
            "label": item.label,
            "start": _fmt_hm(item.start),
            "end": _fmt_hm(item.end),
        }
        for item in market.sessions
    ]


def in_trading_hours(
    now: datetime | None = None,
    *,
    market_id: str | None = None,
) -> bool:
    """当前是否落在任一展示时段内（跨午夜时段按本地日切分处理）。"""
    policy = get_policy(market_id)
    market = get_calendar_market(market_id)
    local = market_now(now, policy=policy)
    clock = local.time()
    for session in market.sessions:
        if session.start <= session.end:
            if session.start <= clock <= session.end:
                return True
        else:
            # 夜盘如 21:00–02:30
            if clock >= session.start or clock <= session.end:
                return True
    return False


def market_now(
    now: datetime | None = None,
    *,
    policy: SessionPolicy | None = None,
) -> datetime:
    resolved = policy or CN_A
    tz = ZoneInfo(resolved.timezone)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def session_ceiling_date(
    now: datetime | None = None,
    *,
    policy: SessionPolicy | None = None,
) -> date:
    """as_of 查询用的日历天花板。

    本地时刻 < session_open → 用昨天及以前；否则用今天及以前。
    再对交易日历取 MAX(trade_date <= ceiling)，即可覆盖：
    - 交易日盘前 → 上一交易日
    - 交易日盘后/盘中（过切点）→ 今天
    - 周末/节假日 → 最近上一交易日
    """
    resolved = policy or CN_A
    local = market_now(now, policy=resolved)
    if local.time() < resolved.session_open:
        return local.date() - timedelta(days=1)
    return local.date()
