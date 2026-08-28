from __future__ import annotations

import os
from pathlib import Path

SYSTEM_DB_ENV = "ASTOCK_SYSTEM_DB"
CONTROL_JSON_ENV = "ASTOCK_CONTROL_CONFIG"


def find_repo_root() -> Path:
    for path in Path(__file__).resolve().parents:
        if (path / ".astock-root").is_file():
            return path
    raise RuntimeError("找不到仓库根目录（缺少 .astock-root）")


REPO_ROOT = find_repo_root()
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "market.db"
SYSTEM_DB_PATH = DATA_DIR / "system.db"
QLIB_DIR = DATA_DIR / "qlib"
ANALYZE_DIR = DATA_DIR / "tradingagents"
DEFAULT_ADJUST = "qfq"
DEFAULT_POOL_ID = "default"


def pool_qlib_dir(pool_id: str) -> Path:
    return QLIB_DIR / "pools" / pool_id


def system_db_path() -> Path:
    override = os.environ.get(SYSTEM_DB_ENV)
    if override:
        return Path(override)
    return SYSTEM_DB_PATH


def control_json_path() -> Path:
    override = os.environ.get(CONTROL_JSON_ENV)
    if override:
        return Path(override)
    return DATA_DIR / "control.json"
