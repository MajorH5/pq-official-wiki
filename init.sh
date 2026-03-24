#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "Missing .env file. Copy .env.example and fill in values."
  exit 1
fi

echo "Starting Pixel Quest Wiki stack..."
docker compose up -d --build

if [ -f resources/images/logo.png ] || [ -f resources/images/favicon.ico ]; then
  echo "Copying wiki images to mediawiki..."
  sleep 3
  MW_CID="$(docker compose ps -q mediawiki)"
  if [ -f resources/images/logo.png ]; then
    docker cp resources/images/logo.png "$MW_CID:/var/www/html/images/logo.png"
  fi
  if [ -f resources/images/favicon.ico ]; then
    docker cp resources/images/favicon.ico "$MW_CID:/var/www/html/images/favicon.ico"
  fi
fi

echo ""
echo "Services started:"
echo "  Wiki:      http://localhost:8080"
echo "  Ingest:    http://localhost:8081"
echo ""
echo "Stop with: docker compose down"
