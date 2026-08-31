from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from astock_ctl.client import request


class RequestTests(unittest.TestCase):
    def test_get_query_parameters_are_encoded_by_httpx(self) -> None:
        response = httpx.Response(200, json={"ok": True})
        with patch("astock_ctl.client.httpx.request", return_value=response) as send:
            self.assertEqual(
                request("GET", "/api/settings", params={"module": "ingest", "section": "quotes"}),
                {"ok": True},
            )

        method, url = send.call_args.args[:2]
        self.assertEqual((method, url), ("GET", "http://127.0.0.1:8787/api/settings"))
        self.assertEqual(
            send.call_args.kwargs["params"],
            {"module": "ingest", "section": "quotes"},
        )
