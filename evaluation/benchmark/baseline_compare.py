"""Phase 2.2: dense-baseline comparison (primary router model vs Phi-3-mini dense).

Same harness, same prompts: (a) end-to-end token throughput over 5 fixed-prompt runs,
(b) domain MCQ accuracy on a shared 6-question set (3 quantum + 3 bioinformatics).
Per-call wall latency includes prompt evaluation + decode."""

import argparse
import os
import re
import statistics
import time

from toolbox import save

MCQS = [
    {"id": "q1", "question": "In DNA, adenine pairs with which base? (A) Guanine (B) Cytosine "
                             "(C) Thymine (D) Uracil", "expected": "thymine"},
    {"id": "q3", "question": "Which single-qubit gate is its own inverse and maps |0> to |1>? "
                             "(A) X gate (B) T gate (C) S gate (D) Z gate", "expected": "x gate"},
    {"id": "q4", "question": "The Bell state (|00>+|11>)/sqrt(2) is produced by which gate "
                             "sequence on |00>? (A) H then CNOT (B) CNOT then H (C) two T gates "
                             "(D) SWAP", "expected": "h then cnot"},
    {"id": "q5", "question": "Which codon is the universal start codon in the standard genetic "
                             "code? (A) UAA (B) AUG (C) UGA (D) GGU", "expected": "aug"},
    {"id": "q7", "question": "In Grover's algorithm on N unstructured items, the optimal number "
                             "of oracle iterations scales approximately as: (A) pi/4*sqrt(N) "
                             "(B) 2*N (C) log(N) (D) N/2", "expected": "sqrt(n)"},
    {"id": "q8", "question": "CRISPR-Cas9 makes a targeted double-strand break guided by which "
                             "molecule? (A) guide RNA (B) primer DNA (C) a ribozyme "
                             "(D) transfer RNA", "expected": "guide rna"},
]

THROUGHPUT_PROMPT = (
    "Explain how a quantum error-correcting code protects a logical qubit, in three sentences."
)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


async def throughput(engine, runs: int, max_tokens: int) -> list[dict]:
    from quantumbio_moe.schemas import GenerationParams

    rows = []
    for i in range(runs):
        params = GenerationParams(max_tokens=max_tokens, temperature=0.2)
        t0 = time.perf_counter()
        resp = await engine.generate(THROUGHPUT_PROMPT, params=params, expert="general")
        elapsed = time.perf_counter() - t0
        tokens = max(getattr(resp, "completion_tokens", None) or 0, 1)
        rows.append({"run": i + 1, "latency_s": round(elapsed, 4), "tokens": tokens,
                     "tok_per_s": round(tokens / elapsed, 3)})
        print(f"  throughput run {i + 1}: tok/s={tokens / elapsed:6.2f} latency={elapsed:5.2f}s "
              f"tokens={tokens}", flush=True)
    return rows


async def mcq_accuracy(engine, max_tokens: int) -> list[dict]:
    from quantumbio_moe.schemas import GenerationParams

    results = []
    for item in MCQS:
        params = GenerationParams(max_tokens=max_tokens, temperature=0.0)
        resp = await engine.generate(item["question"], params=params, expert="general")
        text = resp.text or ""
        correct = normalize(item["expected"]) in normalize(text)
        results.append({"id": item["id"], "correct": correct,
                        "expected": item["expected"], "text": text})
        print(f"  mcq {item['id']}: {'PASS' if correct else 'FAIL'}", flush=True)
    return results


def summarize(values) -> dict:
    n = len(values)
    mean = statistics.mean(values)
    std = statistics.stdev(values) if n > 1 else 0.0
    return {
        "n": n, "mean": round(mean, 4), "std": round(std, 4),
        "median": round(statistics.median(values), 4),
        "p95": round(sorted(values)[int(0.95 * n) - 1], 4) if n else None,
        "min": round(min(values), 4), "max": round(max(values), 4),
    }


async def main() -> None:
    import math

    from toolbox import quiet

    quiet()
    from quantumbio_moe.engine import LocalMoEEngine

    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default=None,
                        help="Comma-separated GGUF paths (primary, dense baseline).")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--max-mcq-tokens", type=int, default=256)
    args = parser.parse_args()

    model_paths = []
    if args.models:
        model_paths = [os.path.abspath(p.strip()) for p in args.models.split(",") if p.strip()]
    default_primary = None

    engine = LocalMoEEngine()
    await engine.start()
    results = []
    for path in model_paths or [None]:
        if path and os.path.isfile(path):
            await engine.select_model(path)
        elif default_primary is None:
            default_primary = engine.current_model
        active = engine.current_model or "unknown"
        print(f"\n### model: {active}", flush=True)
        tp = await throughput(engine, args.runs, max_tokens=64)
        mcq = await mcq_accuracy(engine, args.max_mcq_tokens)
        n_correct = sum(1 for r in mcq if r["correct"])
        results.append({
            "model_path": active,
            "file_size_bytes": os.path.getsize(active) if os.path.isfile(active) else None,
            "throughput_tok_per_s": summarize([r["tok_per_s"] for r in tp]),
            "throughput_latency_s": summarize([r["latency_s"] for r in tp]),
            "throughput_rows": tp,
            "mcq_accuracy": round(n_correct / len(mcq), 4),
            "mcq_correct": n_correct,
            "mcq_total": len(mcq),
            "mcq_rows": mcq,
        })
    await engine.close()

    payload = {
        "methodology": (
            "Same fixed prompts run through both models in the same engine process: per-call wall "
            "latency includes prompt evaluation + decode; tok/s = completion tokens / wall latency. "
            "Throughput: 5 runs of the error-correction prompt, max_tokens 64, temperature 0.2. "
            "Accuracy: 6 shared MCQs (3 quantum, 3 bioinformatics), temperature 0, max_tokens 256; "
            "correct if the expected answer phrase appears in the response. Note per-call end-to-end "
            "tok/s reports effective throughput incl. variable R1 thinking preamble, so it is lower "
            "than the earlier pure-decode quantization figures; both models are compared on the "
            "identical, router-less (expert=general) harness for apples-to-apples."
        ),
        "models": results,
    }
    if results:
        payload["summary_table"] = [
            {
                "model_path": r["model_path"],
                "tok_per_s_mean": r["throughput_tok_per_s"]["mean"],
                "latency_s_mean": r["throughput_latency_s"]["mean"],
                "mcq_accuracy": r["mcq_accuracy"],
            }
            for r in results
        ]
    save("baseline_compare.json", payload)
    print("\nsaved evaluation/results/raw/baseline_compare.json")
    for r in results:
        print(f"\n{r['model_path']}:\n  tok/s mean={r['throughput_tok_per_s']['mean']} "
              f"latency mean={r['throughput_latency_s']['mean']}s "
              f"MCQ={r['mcq_correct']}/{r['mcq_total']}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())