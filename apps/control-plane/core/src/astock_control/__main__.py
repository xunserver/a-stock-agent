from __future__ import annotations

import argparse

import uvicorn

from astock_control.settings import DEFAULT_HOST, DEFAULT_PORT


def main() -> None:
    parser = argparse.ArgumentParser(description="My Trading core：接收 Web / CLI 提交的命令并执行。")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    uvicorn.run(
        "astock_control.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
