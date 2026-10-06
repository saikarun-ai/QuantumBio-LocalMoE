#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE="docker compose"
command -v "docker" >/dev/null && ! docker compose version >/dev/null 2>&1 && COMPOSE="docker-compose"
echo "[Stop] Stopping all QuantumBio-LocalMoE services..."
$COMPOSE down
echo "[Stop] Done. Volumes kept; use \"$COMPOSE down -v\" to remove data."