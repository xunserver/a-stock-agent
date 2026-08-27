from __future__ import annotations

import json

from astock_core.db import MarketDB
from astock_core.paths import DB_PATH


def main() -> None:
    with MarketDB(DB_PATH) as db:
        print(json.dumps({"db": str(DB_PATH), **db.counts()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
