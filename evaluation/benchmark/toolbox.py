"""Shared helpers for the evaluation benchmarks. Run from anywhere."""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RESULT_DIR = os.path.join(ROOT, "evaluation", "results", "raw")
DATASET_DIR = os.path.join(ROOT, "evaluation", "datasets")
PROCESSED_DIR = os.path.join(ROOT, "evaluation", "results", "processed")
FIGURES_DIR = os.path.join(ROOT, "evaluation", "results", "figures")
LOGS_DIR = os.path.join(ROOT, "evaluation", "logs")
CONFIGS_DIR = os.path.join(ROOT, "evaluation", "configs")


def ensure_dirs() -> None:
    for path in (RESULT_DIR, PROCESSED_DIR, FIGURES_DIR, LOGS_DIR, CONFIGS_DIR, DATASET_DIR):
        os.makedirs(path, exist_ok=True)


def save(name: str, payload: dict) -> str:
    ensure_dirs()
    path = os.path.join(RESULT_DIR, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    print(f"[saved] {os.path.relpath(path, ROOT)}")
    return path


def quiet() -> None:
    import logging

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("quantumbio_moe").setLevel(logging.ERROR)
    logging.getLogger("fastapi").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)