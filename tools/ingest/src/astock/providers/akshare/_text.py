"""Text normalization helpers for AKShare news and event payloads."""

from __future__ import annotations

import re
from typing import Any

_TAG_RE = re.compile(r"<[^>]+>")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = _TAG_RE.sub("", str(value)).replace("\u3000", " ").replace("\r\n", " ")
    text = " ".join(text.split())
    if text.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    return text
