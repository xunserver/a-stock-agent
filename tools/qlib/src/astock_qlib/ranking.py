from __future__ import annotations

import pickle
import sqlite3
from pathlib import Path

import pandas as pd

from astock_core.paths import DB_PATH, REPO_ROOT


def latest_pred_frame(mlruns: Path | None = None) -> tuple[Path, pd.DataFrame]:
    """在 mlruns 里找覆盖股票数最多、且最新的那份 pred.pkl。"""
    root = Path(mlruns or (REPO_ROOT / "mlruns"))
    candidates: list[tuple[int, float, Path, pd.DataFrame]] = []
    for path in root.rglob("pred.pkl"):
        with path.open("rb") as fh:
            obj = pickle.load(fh)
        if not isinstance(obj, pd.DataFrame) or not isinstance(obj.index, pd.MultiIndex):
            continue
        n = int(obj.index.get_level_values(-1).nunique())
        candidates.append((n, path.stat().st_mtime, path, obj))
    if not candidates:
        raise FileNotFoundError(
            f"未找到 pred.pkl，请先跑：uv --directory tools/qlib run python -m astock_qlib workflow"
        )
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, _, best_path, best_df = candidates[0]
    return best_path, best_df


def top_scores(n: int = 5, *, as_of: str | None = None) -> dict:
    path, frame = latest_pred_frame()
    df = frame.copy()
    if "score" not in df.columns:
        df = df.rename(columns={df.columns[0]: "score"})
    dates = df.index.get_level_values(0)
    day = pd.Timestamp(as_of) if as_of else dates.max()
    if day not in set(dates):
        # 允许只写日期
        matches = [d for d in dates.unique() if str(d)[:10] == str(day)[:10]]
        if not matches:
            raise ValueError(f"pred 里没有日期 {day}，范围 {dates.min()} ~ {dates.max()}")
        day = matches[0]
    ranked = df.xs(day).sort_values("score", ascending=False).head(n)

    names = dict(sqlite3.connect(DB_PATH).execute("SELECT code, name FROM stocks").fetchall())
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
        "pred_path": str(path),
        "universe_size": int(df.index.get_level_values(-1).nunique()),
        "top": rows,
    }
