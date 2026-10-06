#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
echo "[Build] Building the QuantumBio-LocalMoE container image..."
docker compose build quantumbio-localmoe 2>/dev/null \
  || docker-compose build quantumbio-localmoe