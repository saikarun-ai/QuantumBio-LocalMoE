#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "============================================================"
echo " QuantumBio-LocalMoE - Model Catalog & Management"
echo "============================================================"

if [[ ! -d .venv ]]; then
  echo "[Models] No virtual environment found. Run: ./scripts/unix/setup.sh"
  exit 1
fi
# shellcheck source=/dev/null
source .venv/bin/activate

COMMAND="${1:-list}"
case "$COMMAND" in
  list)
    python scripts/manage_models.py list
    ;;
  export)
    shift
    python scripts/manage_models.py export "$@"
    ;;
  *)
    echo "[Models] Unknown command \"$COMMAND\". Usage:"
    echo "  ./scripts/unix/models.sh list"
    echo "  ./scripts/unix/models.sh export [--source DIR] [--dest DIR] [--hardlink]"
    exit 1
    ;;
esac