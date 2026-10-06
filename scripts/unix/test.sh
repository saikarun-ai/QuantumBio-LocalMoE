#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
# shellcheck source=/dev/null
source .venv/bin/activate
echo "[Test] Installing dev dependencies..."
pip install -r requirements-dev.txt
echo "[Test] Running test suite..."
pytest tests -v