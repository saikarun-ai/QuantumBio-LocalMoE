#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "[Setup] QuantumBio-LocalMoE - creating virtual environment..."
python3 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip

echo "[Setup] Installing core dependencies..."
pip install -r requirements.txt

if [[ -f requirements-optional.txt ]]; then
  echo "[Setup] Installing optional extras (vLLM/SD/whisper) - best effort..."
  pip install -r requirements-optional.txt || echo "[Setup] WARNING: optional extras failed; continuing."
fi

if [[ ! -f .env ]]; then
  echo "[Setup] Creating .env from .env.example..."
  cp .env.example .env
fi

echo "[Setup] Building model catalog..."
python -c "from quantumbio_moe.inference.registry import ModelRegistry; r=ModelRegistry(); print(' text:', [m.name for m in r.text_models]); print(' diffusion:', [m.name for m in r.diffusion_models]); print(' audio:', [m.name for m in r.audio_models])"

echo "[Setup] Complete. Activate with: source .venv/bin/activate"