"""个股事件：公告 / 研报 / 大宗 / 股东变更。实时拉取，不入库。"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from astock.ingest import _call

_TAG_RE = re.compile(r"<[^>]+>")

EVENT_KINDS = frozenset({"notices", "research", "block_trades", "holder_changes"})
EVENTS_DEFAULT_LIMIT = 50
EVENTS_MAX_LIMIT = 50
RESEARCH_DEFAULT_LIMIT = 20
NOTICES_LOOKBACK_DAYS = 365
BLOCK_TRADES_LOOKBACK_DAYS = 90


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = _TAG_RE.sub("", str(value)).replace("\u3000", " ").replace("\r\n", " ")
    text = " ".join(text.split())
    if text.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    return text


def _clamp_limit(limit: int | None, *, default: int) -> int:
    if limit is None:
        return default
    return max(1, min(int(limit), EVENTS_MAX_LIMIT))


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _item(
    *,
    title: str,
    published_at: str = "",
    summary: str = "",
    source: str = "",
    url: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "summary": summary,
        "published_at": published_at,
        "source": source,
        "url": url,
    }
    if extra:
        payload["extra"] = extra
    return payload


def _holder_exchange(code: str) -> str:
    if code.startswith(("6", "9", "5")):
        return "sse"
    if code.startswith(("4", "8")):
        return "bse"
    return "szse"


def fetch_notices(code: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    import akshare as ak

    symbol = str(code).strip().zfill(6)
    cap = _clamp_limit(limit, default=EVENTS_DEFAULT_LIMIT)
    end = date.today()
    begin = end - timedelta(days=NOTICES_LOOKBACK_DAYS)
    frame = _call(
        ak.stock_individual_notice_report,
        security=symbol,
        symbol="全部",
        begin_date=_ymd(begin),
        end_date=_ymd(end),
        retries=2,
    )
    if frame is None or getattr(frame, "empty", True):
        return []
    items: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        title = _text(row.get("公告标题"))
        if not title:
            continue
        notice_type = _text(row.get("公告类型"))
        items.append(
            _item(
                title=title,
                published_at=_text(row.get("公告日期")),
                source=notice_type,
                url=_text(row.get("网址")),
                extra={"notice_type": notice_type} if notice_type else None,
            )
        )
        if len(items) >= cap:
            break
    return items


def fetch_research(code: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    import akshare as ak

    symbol = str(code).strip().zfill(6)
    cap = _clamp_limit(limit, default=RESEARCH_DEFAULT_LIMIT)
    frame = _call(ak.stock_research_report_em, symbol=symbol, retries=2)
    if frame is None or getattr(frame, "empty", True):
        return []
    items: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        title = _text(row.get("报告名称"))
        if not title:
            continue
        org = _text(row.get("机构"))
        rating = _text(row.get("东财评级"))
        summary_parts = [part for part in (org, rating) if part]
        items.append(
            _item(
                title=title,
                published_at=_text(row.get("日期")),
                summary=" · ".join(summary_parts),
                source=org,
                url=_text(row.get("报告PDF链接")),
                extra={
                    "org": org,
                    "rating": rating,
                },
            )
        )
        if len(items) >= cap:
            break
    return items


def fetch_block_trades(code: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    import akshare as ak

    symbol = str(code).strip().zfill(6)
    cap = _clamp_limit(limit, default=EVENTS_DEFAULT_LIMIT)
    end = date.today()
    begin = end - timedelta(days=BLOCK_TRADES_LOOKBACK_DAYS)
    frame = _call(
        ak.stock_dzjy_mrmx,
        symbol="A股",
        start_date=_ymd(begin),
        end_date=_ymd(end),
        retries=2,
    )
    if frame is None or getattr(frame, "empty", True):
        return []
    code_col = "证券代码" if "证券代码" in frame.columns else None
    if code_col is None:
        return []
    matched = frame[frame[code_col].astype(str).str.zfill(6) == symbol].copy()
    if matched.empty:
        return []
    if "交易日期" in matched.columns:
        matched = matched.sort_values("交易日期", ascending=False)
    items: list[dict[str, Any]] = []
    for row in matched.to_dict(orient="records"):
        trade_date = _text(row.get("交易日期"))
        deal_price = row.get("成交价")
        premium = row.get("折溢率")
        title = f"大宗成交 {deal_price}" if deal_price is not None and _text(deal_price) else "大宗交易"
        buyer = _text(row.get("买方营业部"))
        seller = _text(row.get("卖方营业部"))
        summary_parts = []
        if premium is not None and _text(premium):
            summary_parts.append(f"折溢率 {premium}%")
        volume = row.get("成交量")
        amount = row.get("成交额")
        if volume is not None and _text(volume):
            summary_parts.append(f"量 {volume}")
        if amount is not None and _text(amount):
            summary_parts.append(f"额 {amount}")
        items.append(
            _item(
                title=title,
                published_at=trade_date,
                summary=" · ".join(summary_parts),
                source=buyer or seller,
                extra={
                    "deal_price": deal_price,
                    "premium_ratio": premium,
                    "volume": volume,
                    "amount": amount,
                    "buyer": buyer,
                    "seller": seller,
                    "close_price": row.get("收盘价"),
                    "pct_chg": row.get("涨跌幅"),
                },
            )
        )
        if len(items) >= cap:
            break
    return items


def fetch_holder_changes(code: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    import akshare as ak

    symbol = str(code).strip().zfill(6)
    cap = _clamp_limit(limit, default=EVENTS_DEFAULT_LIMIT)
    exchange = _holder_exchange(symbol)
    if exchange == "sse":
        frame = _call(ak.stock_share_hold_change_sse, symbol=symbol, retries=2)
    elif exchange == "bse":
        frame = _call(ak.stock_share_hold_change_bse, symbol=symbol, retries=2)
    else:
        frame = _call(ak.stock_share_hold_change_szse, symbol=symbol, retries=2)
    if frame is None or getattr(frame, "empty", True):
        return []
    items: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        if exchange == "sse":
            name = _text(row.get("姓名"))
            role = _text(row.get("职务"))
            change_qty = row.get("变动数")
            avg_price = row.get("本次变动平均价格")
            reason = _text(row.get("变动原因"))
            published = _text(row.get("变动日期")) or _text(row.get("填报日期"))
        else:
            name = _text(row.get("股份变动人姓名")) or _text(row.get("董监高姓名"))
            role = _text(row.get("职务"))
            change_qty = row.get("变动股份数量")
            avg_price = row.get("成交均价")
            reason = _text(row.get("变动原因"))
            published = _text(row.get("变动日期"))
        if not name and change_qty is None:
            continue
        title = name or "股东变更"
        if role:
            title = f"{name}（{role}）" if name else role
        summary_parts = []
        if change_qty is not None and _text(change_qty):
            summary_parts.append(f"变动 {change_qty}")
        if avg_price is not None and _text(avg_price):
            summary_parts.append(f"均价 {avg_price}")
        if reason:
            summary_parts.append(reason)
        items.append(
            _item(
                title=title,
                published_at=published,
                summary=" · ".join(summary_parts),
                source=reason,
                extra={
                    "name": name,
                    "role": role,
                    "change_qty": change_qty,
                    "avg_price": avg_price,
                    "reason": reason,
                },
            )
        )
        if len(items) >= cap:
            break
    return items


def fetch_stock_events(
    code: str,
    kind: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    key = str(kind).strip()
    if key == "notices":
        return fetch_notices(code, limit=limit)
    if key == "research":
        return fetch_research(code, limit=limit)
    if key == "block_trades":
        return fetch_block_trades(code, limit=limit)
    if key == "holder_changes":
        return fetch_holder_changes(code, limit=limit)
    raise ValueError(f"未知事件类型: {kind}")


def format_stock_events(payload: dict[str, Any]) -> str:
    code = str(payload.get("code") or "")
    kind = str(payload.get("kind") or "")
    items = payload.get("events") or []
    if not items:
        return f"{code}  {kind}  暂无数据"
    lines = [f"{code}  {kind}  {len(items)} 条", ""]
    for item in items:
        if not isinstance(item, dict):
            continue
        meta = "  ".join(
            part
            for part in (str(item.get("published_at") or ""), str(item.get("source") or ""))
            if part
        )
        title = str(item.get("title") or "")
        lines.append(f"{meta}  {title}".strip())
        summary = str(item.get("summary") or "")
        if summary:
            lines.append(f"  {summary}")
        url = str(item.get("url") or "")
        if url:
            lines.append(f"  {url}")
        lines.append("")
    return "\n".join(lines).rstrip()
