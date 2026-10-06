#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE="docker compose"
command -v docker >/dev/null && ! docker compose version >/dev/null 2>&1 && COMPOSE="docker-compose"

echo "============================================================"
echo " QuantumBio-LocalMoE - Clean Workspace"
echo "============================================================"

echo "[Clean] Stopping containers (data volumes kept)..."
$COMPOSE down 2>/dev/null || echo "  (nothing to stop)"

echo "[Clean] Removing generated caches..."
find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \) -prune -exec rm -rf {} + 2>/dev/null || true

read -rp "[Clean] Delete the virtual environment .venv? [y/N] " ANSWER
if [[ "${ANSWER:-n}" =~ ^[Yy]$ ]]; then
  rm -rf .venv
  echo "  Removed .venv"
fi

echo "[Clean] Done."