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

if [ -f resources/images/logo.png ] || [ -f resources/images/favicon.ico ] || [ -f resources/images/hero-header.png ] || [ -f resources/images/pq-thumbnail-1920x1080.png ] || [ -f resources/images/default-preview.png ]; then
  echo "Copying wiki images to mediawiki..."
  sleep 3
  MW_CID="$(docker compose ps -q mediawiki)"
  if [ -f resources/images/logo.png ]; then
    docker cp resources/images/logo.png "$MW_CID:/var/www/html/images/logo.png"
  fi
  if [ -f resources/images/favicon.ico ]; then
    docker cp resources/images/favicon.ico "$MW_CID:/var/www/html/images/favicon.ico"
  fi
  if [ -f resources/images/hero-header.png ]; then
    docker cp resources/images/hero-header.png "$MW_CID:/var/www/html/images/hero-header.png"
  fi
  if [ -f resources/images/pq-thumbnail-1920x1080.png ]; then
    docker cp resources/images/pq-thumbnail-1920x1080.png "$MW_CID:/var/www/html/images/pq-thumbnail-1920x1080.png"
  fi
  if [ -f resources/images/default-preview.png ]; then
    docker cp resources/images/default-preview.png "$MW_CID:/var/www/html/images/default-preview.png"
  fi
fi

echo ""
echo "Services started:"
echo "  Wiki:      http://localhost:8080"
echo "  Ingest:    http://localhost:8081"
echo ""
echo "Stop with: docker compose down"
