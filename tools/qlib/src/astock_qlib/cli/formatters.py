"""Output formatters for the stable Qlib command-line interface."""

from __future__ import annotations

import json
from typing import Any


def print_json(payload: object) -> None:
    """Emit the historical indented JSON representation used by automation."""
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def print_top_scores(payload: dict[str, Any], count: int) -> None:
    """Render the legacy human-readable ranking output."""
    print(f"日期 {payload['as_of']}  池子 {payload['universe_size']} 只  取 Top{count}")
    print(f"来源 {payload['pred_path']}")
    for row in payload["top"]:
        print(f"{row['rank']}. {row['code']} {row['name']:<8}  {row['symbol']}  score={row['score']:.6f}")


def print_features(frame: Any, *, as_json: bool) -> None:
    """Render a feature DataFrame in its established text or JSON form."""
    if as_json:
        print_json(json.loads(frame.reset_index().to_json(orient="records", date_format="iso")))
    else:
        print(frame.to_string())
