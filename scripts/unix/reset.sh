#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE="docker compose"
command -v docker >/dev/null && ! docker compose version >/dev/null 2>&1 && COMPOSE="docker-compose"

echo "============================================================"
echo " QuantumBio-LocalMoE - Full Reset & Rebuild"
echo "============================================================"

echo "[Reset] Tearing down the docker stack (INCLUDING data volumes)..."
$COMPOSE down -v 2>/dev/null || echo "  (nothing to stop)"

echo "[Reset] Cleaning caches..."
find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} + 2>/dev/null || true

echo "[Reset] Running setup..."
./scripts/unix/setup.sh

echo "[Reset] Rebuilding the container image..."
./scripts/unix/build.sh

echo "[Reset] Deploying fresh stack..."
./scripts/unix/deploy.sh

echo "[Reset] Refresh complete."