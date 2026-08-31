from __future__ import annotations

from pathlib import Path

FORBIDDEN = (
    "cookie",
    "set-cookie",
    "authorization",
    "bearer ",
    "api_key",
    "apikey",
    "x-api-key",
)


def test_provider_fixtures_contain_no_credentials() -> None:
    root = Path(__file__).parent / "fixtures"
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN:
            if token in text:
                hits.append(f"{path.relative_to(root)}: {token}")
    assert hits == []
