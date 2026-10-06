#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE="docker compose"
command -v docker >/dev/null && ! docker compose version >/dev/null 2>&1 && COMPOSE="docker-compose"

echo "============================================================"
echo " QuantumBio-LocalMoE - Container Logs"
echo "============================================================"

$COMPOSE logs -f quantumbio-localmoe 2>/dev/null || {
  echo "  Container not running. Start it with: ./scripts/unix/deploy.sh"
  exit 1
}