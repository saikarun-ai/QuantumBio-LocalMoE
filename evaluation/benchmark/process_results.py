"""Aggregate raw benchmark JSON into a single processed summary + derived stats."""

import json
import math
import os

from toolbox import PROCESSED_DIR, RESULT_DIR, ensure_dirs


def _load(name):
    path = os.path.join(RESULT_DIR, name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    ensure_dirs()
    routing = _load("routing_benchmark.json")
    reliability = _load("reliability_test.json")
    quantum = _load("quantum_benchmark.json")
    scientific = _load("scientific_task.json")
    api_ext = _load("api_extended_test.json")

    # expert load balance (dataset composition = routing workload)
    counts = routing["class_counts"]
    total = sum(counts.values())
    p = {c: v / total for c, v in counts.items()}
    entropy = -sum(prob * math.log2(prob) for prob in p.values() if prob)
    lo = min(counts.values())
    hi = max(counts.values())

    # ablation: fixed/always-general router baseline accuracy on the same dataset
    always_general_acc = counts.get("general", 0) / total

    quantum_validate_latency = quantum["validate_latency_ms"]
    valuation_new = {"quantum_validate_latency_ms": quantum_validate_latency,
                     "vqe_latency_ms": quantum["vqe_program"]["latency_ms"]}

    chat_tokens = [c.get("completion_tokens") for c in reliability["chat_inference"]["calls"] if c.get("completion_tokens")]
    chat_latency = reliability["chat_inference"]["stats_ms"]

    derived = {
        "routing": {
            "total_prompts": total,
            "class_distribution_pct": {k: round(v * 100, 1) for k, v in p.items()},
            "entropy_bits": round(entropy, 3),
            "max_entropy_4_classes": 2.0,
            "imbalance_ratio_max_min": round(hi / lo, 2),
            "max_expert_load": hi,
            "min_expert_load": lo,
            "ablation_always_general_accuracy": round(always_general_acc, 4),
            "measured_router_accuracy": routing["metrics"]["accuracy"],
        },
        "quantum": valuation_new,
        "chat_inference": {"mean_ms": chat_latency["mean_ms"], "p95_ms": chat_latency["p95_ms"],
                           "n": len(chat_tokens), "completion_tokens": chat_tokens},
        "integration": {
            "report_draft_elapsed_s": [f["elapsed_s"] for f in api_ext["findings"] if f["test"].startswith("report draft")],
            "report_generate_pdf_elapsed_s": [f["elapsed_s"] for f in api_ext["findings"] if f["test"].startswith("report generate")],
            "model_select_elapsed_s": [f["elapsed_s"] for f in api_ext["findings"] if "select" in f["test"] and "elapsed_s" in f],
        },
        "reliability_success_rate": reliability["success_rate"],
        "reliability_requests": reliability["total_requests"],
    }

    out_path = os.path.join(PROCESSED_DIR, "summary.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(derived, fh, indent=2)
    print(json.dumps(derived, indent=2, default=str))
    print("\n[saved]", out_path)


if __name__ == "__main__":
    main()