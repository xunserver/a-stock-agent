from __future__ import annotations

import logging
import time

from astock.config import request_sleep_seconds
from astock.providers.protocols import ClassificationSource, MembershipSource
from astock.providers.registry import resolve_capability
from astock_core.db import MarketDB
from astock_core.market_data import (
    ClassificationKind,
    ClassificationQuery,
    EASTMONEY_TAXONOMY,
    MembershipQuery,
    validate_classification_dataset,
    validate_membership_dataset,
)

logger = logging.getLogger(__name__)

BOARD_KINDS = (ClassificationKind.INDUSTRY, ClassificationKind.CONCEPT)


def sync_boards(
    db: MarketDB,
    *,
    kinds: tuple[str | ClassificationKind, ...] = BOARD_KINDS,
    sleep: float | None = None,
    limit: int | None = None,
    classification_source: ClassificationSource | None = None,
    membership_source: MembershipSource | None = None,
) -> dict:
    """同步东财行业/概念板块；成员只保留系统 stocks 内代码。"""
    resolved_sleep = request_sleep_seconds() if sleep is None else sleep
    selected: list[ClassificationKind] = []
    for kind in kinds:
        resolved = ClassificationKind(kind) if isinstance(kind, str) else kind
        if resolved in BOARD_KINDS:
            selected.append(resolved)
    if not selected:
        raise ValueError("kinds 需要包含 industry 或 concept")

    classifications = classification_source or resolve_capability("classifications")
    memberships = membership_source or resolve_capability("memberships")

    allowed = set(db.stock_codes())
    if not allowed:
        logger.warning("系统内尚无股票，跳过板块成分写入（仍会更新板块名录）")

    stats = {
        "kinds": [kind.value for kind in selected],
        "system_stocks": len(allowed),
        "boards": 0,
        "members": 0,
        "empty_boards": 0,
        "error": 0,
    }

    for kind in selected:
        logger.info("拉取东财%s板块名录", "行业" if kind == ClassificationKind.INDUSTRY else "概念")
        classification_query = ClassificationQuery(
            kind=kind,
            taxonomy=EASTMONEY_TAXONOMY,
        )
        catalog = validate_classification_dataset(
            classifications.fetch_classifications(classification_query),
            classification_query,
        )
        if not catalog.items:
            logger.warning("%s 板块名录为空", kind.value)
            continue

        board_rows = catalog.items
        if limit is not None:
            board_rows = board_rows[:limit]
        stats["boards"] += db.upsert_classifications(board_rows)
        logger.info("%s 板块名录写入 %s 个", kind.value, len(board_rows))

        total = len(board_rows)
        for i, classification in enumerate(board_rows, start=1):
            membership_query = MembershipQuery(
                taxonomy=EASTMONEY_TAXONOMY,
                classification_id=classification.id,
                kind=kind,
            )
            try:
                dataset = validate_membership_dataset(
                    memberships.fetch_memberships(membership_query),
                    membership_query,
                )
                written = db.replace_classification_members(
                    classification,
                    dataset.items,
                    allowed_codes=allowed if allowed else None,
                )
                stats["members"] += written
                if written == 0:
                    stats["empty_boards"] += 1
                if i % 20 == 0 or i == total:
                    logger.info(
                        "%s 进度 %s/%s  %s 本板系统内 %s 只  累计成员 %s",
                        kind.value,
                        i,
                        total,
                        classification.id,
                        written,
                        stats["members"],
                    )
            except Exception as exc:
                stats["error"] += 1
                logger.warning(
                    "%s 板块 %s 成分失败: %s",
                    kind.value,
                    classification.id,
                    exc,
                )
            time.sleep(resolved_sleep)

    return stats
