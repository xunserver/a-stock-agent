"""东方财富行情：用 curl_cffi 模拟浏览器，避免本机 requests 被断开。"""

from __future__ import annotations

from curl_cffi import requests as creq


def _get(url: str, params: dict, timeout: float = 20):
    response = creq.get(url, params=params, timeout=timeout, impersonate="chrome")
    response.raise_for_status()
    return response
