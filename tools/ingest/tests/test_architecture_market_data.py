from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_architecture_rejects_direct_market_data_calls_outside_adapters() -> None:
    violation = REPO_ROOT / "tools/ingest/src/astock/_architecture_violation_probe.py"
    violation.write_text("import akshare as ak\nak.stock_zh_a_hist()\n", encoding="utf-8")
    try:
        result = subprocess.run(
            ["bash", "scripts/check-architecture.sh"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "direct market-data source call outside adapters" in result.stderr
    finally:
        violation.unlink(missing_ok=True)


def test_architecture_rejects_source_calls_in_provider_composition_modules() -> None:
    violation = REPO_ROOT / "tools/ingest/src/astock/providers/_violation_probe.py"
    violation.write_text("import akshare as ak\nak.stock_zh_a_hist()\n", encoding="utf-8")
    try:
        result = subprocess.run(
            ["bash", "scripts/check-architecture.sh"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "direct market-data source call outside adapters" in result.stderr
    finally:
        violation.unlink(missing_ok=True)


def test_architecture_rejects_ingest_import_from_core_market_data() -> None:
    violation = REPO_ROOT / "packages/core/src/astock_core/market_data/_violation_probe.py"
    violation.write_text("from astock.providers import registry\n", encoding="utf-8")
    try:
        result = subprocess.run(
            ["bash", "scripts/check-architecture.sh"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "must stay dependency-free" in result.stderr
    finally:
        violation.unlink(missing_ok=True)


def test_architecture_passes_for_current_tree() -> None:
    result = subprocess.run(
        ["bash", "scripts/check-architecture.sh"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
