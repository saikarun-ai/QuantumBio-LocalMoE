#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
echo "[Infra] Starting postgres, redis and qdrant..."
docker compose up -d postgres redis qdrant 2>/dev/null \
  || docker-compose up -d postgres redis qdrant
echo "[Infra] Services started:"
docker compose ps postgres redis qdrant 2>/dev/null \
  || docker-compose ps postgres redis qdrant