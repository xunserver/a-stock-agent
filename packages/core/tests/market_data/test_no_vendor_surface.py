from __future__ import annotations

from pathlib import Path

from astock_core import market_data


FORBIDDEN_COLUMNS = (
    "TOTAL_ASSETS",
    "OPERATE_INCOME",
    "PARENT_NETPROFIT",
    "NETCASH_OPERATE",
    "SECURITY_TYPE_CODE",
)
FORBIDDEN_IMPORT_SNIPPETS = (
    "import pandas",
    "from pandas",
    "import akshare",
    "from akshare",
    "import curl_cffi",
    "from curl_cffi",
)


def test_market_data_package_has_no_source_column_names() -> None:
    root = Path(market_data.__file__).parent
    hits: list[str] = []
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_COLUMNS:
            if token in text:
                hits.append(f"{path.name}: {token}")
        for snippet in FORBIDDEN_IMPORT_SNIPPETS:
            if snippet in text:
                hits.append(f"{path.name}: {snippet}")
    assert hits == []
