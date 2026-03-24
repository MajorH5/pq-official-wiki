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

if [ -f resources/images/logo.png ]; then
  echo "Copying logo to mediawiki..."
  sleep 3
  docker cp resources/images/logo.png "$(docker compose ps -q mediawiki):/var/www/html/images/logo.png"
fi

echo ""
echo "Services started:"
echo "  Wiki:      http://localhost:8080"
echo "  Ingest:    http://localhost:8081"
echo ""
echo "Stop with: docker compose down"
