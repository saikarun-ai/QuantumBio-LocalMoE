#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/../.."
COMPOSE="docker compose"
command -v docker >/dev/null && ! docker compose version >/dev/null 2>&1 && COMPOSE="docker-compose"

echo "============================================================"
echo " QuantumBio-LocalMoE - Stack Status"
echo "============================================================"

echo "[Compose] Running containers:"
$COMPOSE ps 2>/dev/null || echo "  (Docker not running or no stack)"

echo
echo "[API] Health check on localhost:8000 ..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" --max-time 3 http://localhost:8000/health \
  || echo "  API not reachable"