#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "============================================================"
echo " QuantumBio-LocalMoE - One-Click Local Run"
echo "============================================================"

if [[ ! -d .venv ]]; then
  echo "[Run] First-time setup detected - running setup..."
  ./scripts/unix/setup.sh
  test -d .venv || { echo "[Run] ERROR: setup did not create .venv"; exit 1; }
fi
# shellcheck source=/dev/null
source .venv/bin/activate
echo "[Run] Using existing virtual environment."

read -rp "[Run] Start docker-compose infra (postgres/redis/qdrant)? [y/N] " ANSWER
if [[ "${ANSWER:-n}" =~ ^[Yy]$ ]]; then
  ./scripts/unix/start_infra.sh
fi

echo "[Run] Launching API at http://localhost:8000 ... (Ctrl+C to stop)"
exec uvicorn main:app --host 0.0.0.0 --port 8000