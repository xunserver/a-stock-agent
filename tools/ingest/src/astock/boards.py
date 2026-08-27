from __future__ import annotations

import logging
import time

import pandas as pd

from astock.config import REQUEST_SLEEP_SECONDS
from astock.ingest import _call
from astock_core.db import MarketDB

logger = logging.getLogger(__name__)

BOARD_SOURCE = "em"
BOARD_KINDS = ("industry", "concept")


def _normalize_code(raw: object) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 6:
        return None
    return digits[-6:].zfill(6)


def _codes_from_cons(frame: pd.DataFrame | None, allowed: set[str]) -> list[str]:
    if frame is None or frame.empty or "代码" not in frame.columns:
        return []
    out: list[str] = []
    for raw in frame["代码"]:
        code = _normalize_code(raw)
        if code and code in allowed:
            out.append(code)
    return out


def _fetch_board_names(kind: str) -> pd.DataFrame:
    import akshare as ak

    if kind == "industry":
        return _call(ak.stock_board_industry_name_em)
    if kind == "concept":
        return _call(ak.stock_board_concept_name_em)
    raise ValueError(f"不支持的板块类型: {kind}")


def _fetch_board_cons(kind: str, board_id: str) -> pd.DataFrame:
    import akshare as ak

    if kind == "industry":
        return _call(ak.stock_board_industry_cons_em, symbol=board_id)
    if kind == "concept":
        return _call(ak.stock_board_concept_cons_em, symbol=board_id)
    raise ValueError(f"不支持的板块类型: {kind}")


def sync_boards(
    db: MarketDB,
    *,
    kinds: tuple[str, ...] = BOARD_KINDS,
    sleep: float = REQUEST_SLEEP_SECONDS,
    limit: int | None = None,
) -> dict:
    """同步东财行业/概念板块；成员只保留系统 stocks 内代码。"""
    selected = tuple(kind for kind in kinds if kind in BOARD_KINDS)
    if not selected:
        raise ValueError("kinds 需要包含 industry 或 concept")

    allowed = set(db.stock_codes())
    if not allowed:
        logger.warning("系统内尚无股票，跳过板块成分写入（仍会更新板块名录）")

    stats = {
        "kinds": list(selected),
        "system_stocks": len(allowed),
        "boards": 0,
        "members": 0,
        "empty_boards": 0,
        "error": 0,
    }

    for kind in selected:
        logger.info("拉取东财%s板块名录", "行业" if kind == "industry" else "概念")
        names = _fetch_board_names(kind)
        if names is None or names.empty:
            logger.warning("%s 板块名录为空", kind)
            continue
        if "板块代码" not in names.columns or "板块名称" not in names.columns:
            raise RuntimeError(f"{kind} 板块名录缺少 板块代码/板块名称 列")

        board_rows: list[tuple[str, str, str, str]] = []
        board_ids: list[str] = []
        for item in names.itertuples(index=False):
            board_id = str(getattr(item, "板块代码") or "").strip()
            board_name = str(getattr(item, "板块名称") or "").strip()
            if not board_id or not board_name:
                continue
            board_rows.append((board_id, kind, board_name, BOARD_SOURCE))
            board_ids.append(board_id)
        if limit is not None:
            board_rows = board_rows[:limit]
            board_ids = board_ids[:limit]
        stats["boards"] += db.upsert_boards(board_rows)
        logger.info("%s 板块名录写入 %s 个", kind, len(board_rows))

        total = len(board_ids)
        for i, board_id in enumerate(board_ids, start=1):
            try:
                cons = _fetch_board_cons(kind, board_id)
                codes = _codes_from_cons(cons, allowed) if allowed else []
                written = db.replace_board_members(board_id, codes)
                stats["members"] += written
                if written == 0:
                    stats["empty_boards"] += 1
                if i % 20 == 0 or i == total:
                    logger.info(
                        "%s 进度 %s/%s  %s 本板系统内 %s 只  累计成员 %s",
                        kind,
                        i,
                        total,
                        board_id,
                        written,
                        stats["members"],
                    )
            except Exception as exc:
                stats["error"] += 1
                logger.warning("%s 板块 %s 成分失败: %s", kind, board_id, exc)
            time.sleep(sleep)

    return stats
