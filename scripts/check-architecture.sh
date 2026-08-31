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
