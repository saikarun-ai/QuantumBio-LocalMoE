#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
# shellcheck source=/dev/null
source .venv/bin/activate
echo "[Start] Launching QuantumBio-LocalMoE API on http://localhost:8000 ..."
exec uvicorn main:app --host 0.0.0.0 --port 8000