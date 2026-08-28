"""东方财富个股新闻：实时拉取，不入库。"""

from __future__ import annotations

import re
from typing import Any

from astock.ingest import _call

_TAG_RE = re.compile(r"<[^>]+>")
NEWS_MAX_LIMIT = 50
NEWS_DEFAULT_LIMIT = 20


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = _TAG_RE.sub("", str(value)).replace("\u3000", " ").replace("\r\n", " ")
    text = " ".join(text.split())
    if text.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    return text


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return NEWS_DEFAULT_LIMIT
    return max(1, min(int(limit), NEWS_MAX_LIMIT))


def fetch_stock_news(code: str, *, limit: int | None = None) -> list[dict[str, str]]:
    import akshare as ak

    symbol = str(code).strip().zfill(6)
    cap = _clamp_limit(limit)
    frame = _call(ak.stock_news_em, symbol=symbol, retries=2)
    if frame is None or getattr(frame, "empty", True):
        return []
    items: list[dict[str, str]] = []
    for row in frame.to_dict(orient="records"):
        title = _text(row.get("新闻标题"))
        if not title:
            continue
        items.append(
            {
                "title": title,
                "summary": _text(row.get("新闻内容")),
                "published_at": _text(row.get("发布时间")),
                "source": _text(row.get("文章来源")),
                "url": _text(row.get("新闻链接")),
            }
        )
        if len(items) >= cap:
            break
    return items


def format_stock_news(payload: dict[str, Any]) -> str:
    code = str(payload.get("code") or "")
    items = payload.get("news") or []
    if not items:
        return f"{code}  暂无新闻"
    lines = [f"{code}  {len(items)} 条", ""]
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
