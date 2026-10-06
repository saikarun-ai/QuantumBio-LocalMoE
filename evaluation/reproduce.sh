#!/usr/bin/env bash
# Regenerate all evaluation results. Run from the repository root.
set -euo pipefail
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

PY=".venv/bin/python"
[ -x "$PY" ] || PY=python

echo "==> environment"
"$PY" evaluation/benchmark/environment.py
echo "==> routing"
"$PY" evaluation/benchmark/routing_benchmark.py
echo "==> quantum"
"$PY" evaluation/benchmark/quantum_benchmark.py
echo "==> offline"
"$PY" evaluation/benchmark/offline_check.py
echo "==> reliability (loads model)"
"$PY" evaluation/benchmark/reliability_test.py
echo "==> api extended (model select + LLM report calls)"
"$PY" evaluation/benchmark/api_extended_test.py
echo "==> quantization (loads 3 models)"
"$PY" evaluation/benchmark/quantization_benchmark.py
echo "==> speculative (loads model twice)"
"$PY" evaluation/benchmark/speculative_test.py
echo "==> scientific (10 LLM calls)"
"$PY" evaluation/benchmark/scientific_task.py
echo "==> aggregate"
"$PY" evaluation/benchmark/process_results.py
echo "done"