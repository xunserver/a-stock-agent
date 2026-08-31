#!/usr/bin/env bash
set -euo pipefail

fail_if_found() {
  local pattern="$1"
  shift
  if rg -n "$pattern" "$@"; then
    echo "architecture check failed: forbidden pattern $pattern" >&2
    exit 1
  fi
}

fail_if_found 'api/(commands|queries)' \
  apps/control-plane/core/src apps/control-plane/cli/src packages/ui/src
fail_if_found 'db\.conn|sqlite3\.connect\(DB_PATH\)' \
  apps/control-plane/core/src tools/ingest/src tools/analyze/src tools/qlib/src \
  --glob '*.py'

if rg -n '\bfetch\(' packages/ui/src --glob '*.{ts,tsx}' \
  --glob '!**/lib/api/http.ts'; then
  echo "architecture check failed: HTTP fetch must go through lib/api/http.ts" >&2
  exit 1
fi

if rg -n 'setInterval' packages/ui/src/pages packages/ui/src/components/job-provider.tsx; then
  echo "architecture check failed: business pages must use the shared Job SSE source" >&2
  exit 1
fi

for page in packages/ui/src/pages/*.tsx; do
  lines=$(wc -l < "$page")
  if (( lines > 200 )); then
    echo "architecture check failed: page shell exceeds 200 lines: $page ($lines)" >&2
    exit 1
  fi
done

# Market-data source calls must stay inside provider Adapters.
MARKET_DATA_SCAN_ROOTS=(
  tools/ingest/src/astock
  apps/control-plane/core/src
  packages/core/src
  tools/analyze/src
  tools/qlib/src
)
MARKET_DATA_ADAPTER_GLOBS=(
  --glob '**/providers/**/[!_]*.py'
  --glob '**/providers/**/__init__.py'
)
MARKET_DATA_FORBIDDEN=(
  'import akshare|from akshare'
  'ak\.stock_|ak\.tool_|ak\.index_'
  'push2(his)?\.eastmoney'
  'stock_zh_|tool_trade_date'
  'stock_board_|stock_financial_|stock_news_em|stock_individual_|stock_balance_sheet|stock_profit_sheet|stock_cash_flow'
  'import curl_cffi|from curl_cffi'
)

for pattern in "${MARKET_DATA_FORBIDDEN[@]}"; do
  if rg -n "$pattern" "${MARKET_DATA_SCAN_ROOTS[@]}" \
    --glob '*.py' \
    --glob '!**/providers/akshare/**' \
    --glob '!**/providers/eastmoney/**' \
    --glob '!**/tests/**' \
    --glob '!**/__pycache__/**'; then
    echo "architecture check failed: direct market-data source call outside adapters: $pattern" >&2
    exit 1
  fi
done

if rg -n 'import pandas|from pandas|import akshare|from akshare|import curl_cffi|from curl_cffi|from astock(\.| import)|^import astock$' packages/core/src/astock_core/market_data --glob '*.py'; then
  echo "architecture check failed: astock_core.market_data must stay dependency-free" >&2
  exit 1
fi
