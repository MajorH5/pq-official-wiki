#!/usr/bin/env bash
# Request a Pixel Quest wiki ↔ Roblox link code (PixelQuestRoblox API).
# Usage: ./scripts/pq_roblox_request_code.sh <robloxUserId>
# Env: WIKI_BASE_URL (default http://localhost:8080), PQ_API_SECRET or DATADUMP_INGEST_SECRET

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

ROBLOX_ID="${1:-${ROBLOX_USER_ID:-}}"
if [ -z "$ROBLOX_ID" ]; then
  echo "Usage: $0 <robloxUserId>"
  exit 1
fi

BASE="${WIKI_BASE_URL:-http://localhost:8080}"
BASE="${BASE%/}"
TOKEN="${PQ_API_SECRET:-${DATADUMP_INGEST_SECRET:-}}"

if [ -z "$TOKEN" ]; then
  echo "Set PQ_API_SECRET or DATADUMP_INGEST_SECRET"
  exit 1
fi

URI="${BASE}/api.php"
BODY="action=pqrobloxrequestcode&format=json&robloxuserid=${ROBLOX_ID}"

echo "POST ${URI} (robloxuserid=${ROBLOX_ID}) ..."
curl -sS -X POST "$URI" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "X-PQ-API-Secret: ${TOKEN}" \
  --data-binary "$BODY"
echo
