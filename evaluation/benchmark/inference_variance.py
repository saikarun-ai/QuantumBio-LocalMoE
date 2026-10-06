"""Phase 2.1: multi-seed inference variance (N >= 30, temperature 0.1..0.7).

Measures token throughput and per-call latency across 30 independent chat
completions, all sharing one model, prompt and max_tokens; only sampling
temperature differs (cycled 0.1..0.7). Reports mean, std, median, p95 and
95% normal-approximation confidence intervals for tok/s and latency."""

import argparse
import os
import statistics
import time

from toolbox import ROOT, save


async def main() -> None:
    import math

    from toolbox import quiet

    quiet()
    from quantumbio_moe.engine import LocalMoEEngine
    from quantumbio_moe.schemas import GenerationParams

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="GGUF path to benchmark.")
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--temps", default="0.1,0.25,0.4,0.55,0.7")
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--prompt", default=None,
                        help="Fixed prompt (default: quantum/biosecurity MCQ-style question).")
    args = parser.parse_args()

    temps = [float(t) for t in args.temps.split(",") if t.strip()]
    prompt = args.prompt or (
        "A draft genome contains a 21,471 bp plasmid carrying a colistin resistance gene. "
        "Describe the minimal experimental safety controls for handling this sample in a BSL-2 lab."
    )

    engine = LocalMoEEngine()
    await engine.start()
    if args.model and os.path.isfile(args.model):
        await engine.select_model(os.path.abspath(args.model))
    model_path = engine.current_model or "unknown"
    print(f"model: {model_path}")
    print(f"params: trials={args.trials} temps={temps} max_tokens={args.max_tokens}")

    rows = []
    for i in range(args.trials):
        temp = temps[i % len(temps)]
        params = GenerationParams(max_tokens=args.max_tokens, temperature=temp)
        t0 = time.perf_counter()
        resp = await engine.generate(prompt, params=params, expert="general")
        elapsed = time.perf_counter() - t0
        tokens = max(getattr(resp, "completion_tokens", None) or 0, 1)
        tps = tokens / elapsed
        rows.append({
            "trial": i + 1, "temperature": temp,
            "latency_s": round(elapsed, 4), "tokens": tokens,
            "tok_per_s": round(tps, 3),
        })
        print(f"trial {i + 1:3d}/{args.trials:3d} temp={temp} tok/s={tps:6.2f} "
              f"latency={elapsed:5.2f}s tokens={tokens}", flush=True)

    await engine.close()

    def summarize(values):
        n = len(values)
        mean = statistics.mean(values)
        std = statistics.stdev(values) if n > 1 else 0.0
        return {
            "n": n,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "median": round(statistics.median(values), 4),
            "p95": round(sorted(values)[int(math.ceil(0.95 * n)) - 1], 4) if n else None,
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "ci95_low": round(mean - 1.96 * std / math.sqrt(n), 4),
            "ci95_high": round(mean + 1.96 * std / math.sqrt(n), 4),
        }

    payload = {
        "methodology": (
            f"{args.trials} independent chat completions of one fixed prompt, default model "
            f"(routed expert=general), max_tokens={args.max_tokens}, temperatures cycled "
            f"{args.temps} (5 temps x {args.trials // len(temps)} repeats). Time measured from engine "
            f"call to full response ('wall' per-call latency includes prompt evaluation + decode); "
            f"tok/s = completion tokens / wall latency. Not incl. engine boot. "
            f"95% CI is the normal approximation mean +/- 1.96*s/sqrt(n). "
            f"Note: a reasoning model (DeepSeek-R1) may emit variable-length thinking; latency and "
            f"tok/s therefore co-vary with response token count, and tok/s here is a per-call "
            f"end-to-end rate, not a pure decode rate."
        ),
        "model": model_path,
        "trials": args.trials,
        "temps": temps,
        "max_tokens": args.max_tokens,
        "latency_s": summarize([r["latency_s"] for r in rows]),
        "tok_per_s": summarize([r["tok_per_s"] for r in rows]),
        "tokens_per_call": {
            "mean": round(statistics.mean([r["tokens"] for r in rows]), 2),
            "std": round(statistics.stdev([r["tokens"] for r in rows]) if len(rows) > 1 else 0.0, 2),
        },
        "rows": rows,
    }
    save("inference_variance.json", payload)
    print("\n--- tok/s ---", payload["tok_per_s"])
    print("--- latency_s ---", payload["latency_s"])


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())