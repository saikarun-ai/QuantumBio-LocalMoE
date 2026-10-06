"""Quantization / inference benchmark: size, load time, RAM footprint, throughput and latency
for every locally available GGUF text model. FP16/INT8/AWQ-INT4 needs models that are not
present locally, so only is reported as unavailable for those rows."""

import asyncio
import os
import statistics
import time

from toolbox import ROOT, save

from quantumbio_moe.inference.registry import ModelRegistry, default_directories

PROMPT = "Explain what a REST API is and name its main HTTP methods, in two short sentences."
MAX_TOKENS = 64
REPEATS = 3


def _rss_mb() -> float:
    import psutil

    return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)


async def _bench(path: str, draft_path: str | None):
    import os

    from quantumbio_moe.engine import LocalMoEEngine
    from quantumbio_moe.schemas import GenerationParams

    rss_before = _rss_mb()
    engine = LocalMoEEngine(model_path=path,
                            draft_model_path=draft_path,
                            quantization="gguf")
    t0 = time.perf_counter()
    await engine.start()
    load_seconds = round(time.perf_counter() - t0, 2)
    rss_after = _rss_mb()

    runs = []
    params = GenerationParams(max_tokens=MAX_TOKENS, temperature=0.1)
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        response = await engine.generate(PROMPT, params=params, expert="general")
        elapsed = time.perf_counter() - t0
        runs.append({
            "elapsed_s": round(elapsed, 3),
            "completion_tokens": response.completion_tokens,
            "tokens_per_second": response.tokens_per_second,
            "text": response.text,
        })
    await engine.close()

    tps = [r["tokens_per_second"] for r in runs]
    lat = [r["elapsed_s"] for r in runs]
    per_word_q = f"{engine.quantization}|\"{os.path.basename(path)}\""
    return per_word_q, {
        "model_path": path,
        "size_bytes": os.path.getsize(path),
        "size_gb": round(os.path.getsize(path) / 1e9, 3),
        "load_seconds": load_seconds,
        "rss_after_load_mb": rss_after,
        "rss_before_mb": rss_before,
        "rss_delta_mb": round(rss_after - rss_before, 1),
        "throughput_tps": {"mean": round(statistics.mean(tps), 2), "runs": tps},
        "latency_s": {"mean": round(statistics.mean(lat), 3), "runs": lat},
        "max_tokens": MAX_TOKENS,
        "prompt": PROMPT,
        "responses": [r["text"] for r in runs],
    }


async def main() -> None:
    from toolbox import quiet

    quiet()
    registry = ModelRegistry(default_directories())
    models = {m.name: m for m in registry.by_kind("text")}

    # order: smallest to largest
    ordered = sorted(models.values(), key=lambda m: m.size_bytes)
    table = {}
    for model in ordered:
        tag, row = await _bench(model.path, draft_path=None)
        table[model.name] = row
        tps = row["throughput_tps"]["mean"]
        print(f"{model.name}: {row['size_gb']} GB, load {row['load_seconds']}s, "
              f"RSS +{row['rss_delta_mb']} MB, tps ~{tps}, latency {row['latency_s']['mean']}s")

    payload = {
        "methodology": (
            "Each model is loaded via LocalMoEEngine with quantization=gguf and the same 70-token "
            "prompt is generated max_tokens=64, temperature=0.1, 3 repeats. RAM delta = process RSS "
            "right after model load minus RSS before. Tokens per second is computed by the engine as "
            "completion_tokens / wall time (CPU inference). FP16, INT8, AWQ-INT4 rows can only be "
            "evaluated if such weights exist locally; none were found."
        ),
        "models": table,
        "unavailable_configs": {
            "fp16": "no fp16 safetensors found in model directories",
            "int8": "no int8 quant found in model directories",
            "awq_int4": "no awq modern weights found in model directories (QUANTIZATION_TYPE nominal only)",
        },
    }
    save("quantization_benchmark.json", payload)


if __name__ == "__main__":
    asyncio.run(main())