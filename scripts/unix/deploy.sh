#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE="docker compose"
command -v "docker" >/dev/null && ! docker compose version >/dev/null 2>&1 && COMPOSE="docker-compose"

echo "[Deploy] Phase 1: infrastructure (postgres, redis, qdrant)..."
$COMPOSE up -d postgres redis qdrant
echo "[Deploy] Phase 2: building and starting the MoE engine container..."
$COMPOSE up -d --build quantumbio-localmoe
echo "[Deploy] Done."
echo "  Health  : http://localhost:8000/health"
echo "  Models  : http://localhost:8000/v1/models"
echo "  Chat    : POST http://localhost:8000/v1/chat/completions"