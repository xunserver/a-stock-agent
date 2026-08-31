from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
from astock_core.db import MarketDB
from astock_core.paths import DB_PATH, REPO_ROOT


def latest_pred_frame(mlruns: Path | None = None) -> tuple[Path, pd.DataFrame]:
    """在 mlruns 里找覆盖股票数最多、且最新的那份 pred.pkl。"""
    root = Path(mlruns or (REPO_ROOT / "mlruns"))
    candidates: list[tuple[int, float, Path, pd.DataFrame]] = []
    for path in root.rglob("pred.pkl"):
        with path.open("rb") as fh:
            obj = pickle.load(fh)
        if not isinstance(obj, pd.DataFrame) or not isinstance(
            obj.index, pd.MultiIndex
        ):
            continue
        n = int(obj.index.get_level_values(-1).nunique())
        candidates.append((n, path.stat().st_mtime, path, obj))
    if not candidates:
        raise FileNotFoundError(
            "未找到 pred.pkl，请先跑：uv --directory tools/qlib run python -m astock_qlib workflow"
        )
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, _, best_path, best_df = candidates[0]
    return best_path, best_df


def scores_from_frame(
    frame: pd.DataFrame,
    *,
    n: int = 5,
    as_of: str | None = None,
    pool_codes: set[str] | None = None,
) -> dict:
    df = frame.copy()
    if "score" not in df.columns:
        df = df.rename(columns={df.columns[0]: "score"})
    if pool_codes is not None:
        instruments = df.index.get_level_values(-1)
        df = df[[str(item)[-6:] in pool_codes for item in instruments]]
    if df.empty:
        raise ValueError("预测结果里没有当前股票池的标的")
    dates = df.index.get_level_values(0)
    day = pd.Timestamp(as_of) if as_of else dates.max()
    if day not in set(dates):
        # 允许只写日期
        matches = [d for d in dates.unique() if str(d)[:10] == str(day)[:10]]
        if not matches:
            raise ValueError(
                f"pred 里没有日期 {day}，范围 {dates.min()} ~ {dates.max()}"
            )
        day = matches[0]
    ranked = df.xs(day).sort_values("score", ascending=False).head(n)

    with MarketDB(DB_PATH) as db:
        names = db.stock_names()
    rows = []
    for i, (inst, row) in enumerate(ranked.iterrows(), start=1):
        code6 = str(inst)[-6:]
        rows.append(
            {
                "rank": i,
                "symbol": str(inst),
                "code": code6,
                "name": names.get(code6, ""),
                "score": float(row["score"]),
            }
        )
    return {
        "as_of": str(day)[:10],
        "universe_size": int(df.index.get_level_values(-1).nunique()),
        "top": rows,
    }


def top_scores(
    n: int = 5,
    *,
    as_of: str | None = None,
    pred_path: Path | None = None,
    pool_codes: set[str] | None = None,
) -> dict:
    if pred_path is None:
        path, frame = latest_pred_frame()
    else:
        path = Path(pred_path)
        with path.open("rb") as fh:
            frame = pickle.load(fh)
        if not isinstance(frame, pd.DataFrame) or not isinstance(
            frame.index, pd.MultiIndex
        ):
            raise ValueError(f"不是有效的 Qlib pred DataFrame: {path}")
    result = scores_from_frame(frame, n=n, as_of=as_of, pool_codes=pool_codes)
    result["pred_path"] = str(path)
    return result
