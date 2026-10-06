#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "============================================================"
echo " QuantumBio-LocalMoE - API Smoke Test"
echo "============================================================"

if [[ ! -d .venv ]]; then
  echo "[Smoke] No virtual environment found. Run: ./scripts/unix/setup.sh"
  exit 1
fi
# shellcheck source=/dev/null
source .venv/bin/activate

python scripts/smoke_test.py "$@"