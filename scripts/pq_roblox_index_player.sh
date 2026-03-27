#!/usr/bin/env bash
# Index a Roblox player in the wiki search index (PixelQuestRoblox API).
# Usage: ./scripts/pq_roblox_index_player.sh <robloxUserId> [optionalUsername]
# Env: WIKI_BASE_URL (default http://localhost:8080), PQ_API_SECRET or DATADUMP_INGEST_SECRET

set -euo pipefail
cd "$(dirname "$0")/.."

ROBLOX_USER_ID="${1:-${ROBLOX_USER_ID:-}}"
if [[ -z "$ROBLOX_USER_ID" ]]; then
  echo "Usage: $0 <robloxUserId> [optionalUsername]" >&2
  exit 1
fi

BASE="${WIKI_BASE_URL:-http://localhost:8080}"
BASE="${BASE%/}"
TOKEN="${PQ_API_SECRET:-${DATADUMP_INGEST_SECRET:-}}"
if [[ -z "$TOKEN" ]]; then
  echo "Set PQ_API_SECRET or DATADUMP_INGEST_SECRET" >&2
  exit 1
fi

BODY="action=pqrobloxindexplayer&format=json&formatversion=2&userid=${ROBLOX_USER_ID}"
if [[ $# -ge 2 ]]; then
  BODY+="&username=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$2'))" 2>/dev/null || printf '%s' "$2")"
fi

echo "POST ${BASE}/api.php (userid=${ROBLOX_USER_ID}) ..."
curl -sS -X POST "${BASE}/api.php" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "X-PQ-API-Secret: ${TOKEN}" \
  --data-binary "${BODY}" | python3 -m json.tool 2>/dev/null || cat
