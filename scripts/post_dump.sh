#!/usr/bin/env bash
# POST a datadump to the ingest endpoint.
# Usage: ./post_dump.sh [dump.json]
# Env: DATADUMP_INGEST_SECRET

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

DUMP="${1:-pq-datadump.json}"
URL="${INGEST_URL:-http://localhost:8081/ingest}"
TOKEN="${DATADUMP_INGEST_SECRET}"

if [ -z "$TOKEN" ]; then
  echo "Set DATADUMP_INGEST_SECRET"
  exit 1
fi

if [ ! -f "$DUMP" ]; then
  echo "File not found: $DUMP"
  exit 1
fi

echo "POSTing $DUMP to $URL ..."
curl -s -X POST "$URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @"$DUMP"
