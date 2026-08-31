"""Eastmoney HTTP transport owned by the source Adapter package."""

from __future__ import annotations

from curl_cffi import requests as creq


def get_response(url: str, params: dict, timeout: float = 20):
    response = creq.get(url, params=params, timeout=timeout, impersonate="chrome")
    response.raise_for_status()
    return response
