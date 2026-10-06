"""Speculative-decoding comparison: target-only vs target+draft. The llama.cpp backend does not
currently pass a draft model to the sampler, so this documents the measured effect (expected: none)
rather than assuming throughput gains."""

import asyncio
import os
import statistics
import time

from toolbox import ROOT, save

from quantumbio_moe.inference.registry import ModelRegistry, default_directories

PROMPT = "Write a one-sentence definition of a genetic algorithm."
MAX_TOKENS = 48
REPEATS = 3


def _find(name_fragment: str):
    registry = ModelRegistry(default_directories())
    for model in registry.by_kind("text"):
        if name_fragment.lower() in model.name.lower():
            return model.path
    raise FileNotFoundError(name_fragment)


async def _run(target: str, draft: str | None):
    from quantumbio_moe.engine import LocalMoEEngine
    from quantumbio_moe.schemas import GenerationParams

    engine = LocalMoEEngine(model_path=target, draft_model_path=draft, quantization="gguf")
    await engine.start()
    params = GenerationParams(max_tokens=MAX_TOKENS, temperature=0.1)
    runs = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        resp = await engine.generate(PROMPT, params=params, expert="general")
        runs.append({"elapsed_s": round(time.perf_counter() - t0, 3),
                     "completion_tokens": resp.completion_tokens,
                     "tokens_per_second": resp.tokens_per_second,
                     "text": resp.text})
    await engine.close()
    tps = [r["tokens_per_second"] for r in runs]
    return {"runs": runs,
            "mean_tps": round(statistics.mean(tps), 2),
            "mean_latency_s": round(statistics.mean([r["elapsed_s"] for r in runs]), 3)}


async def main() -> None:
    from toolbox import quiet

    quiet()
    target = _find("deepseek")
    draft = _find("gemma")

    print(f"target: {os.path.basename(target)}\ndraft:  {os.path.basename(draft)}\n")
    only = await _run(target, draft=None)
    print("target-only      ->", only["mean_tps"], "tps")
    with_draft = await _run(target, draft=draft)
    print("target+draft     ->", with_draft["mean_tps"], "tps")

    delta_pct = round((with_draft["mean_tps"] - only["mean_tps"]) / only["mean_tps"] * 100, 2)
    payload = {
        "methodology": (
            "Same target (DeepSeek Q6_K_L) generated 3x with and 3x without a configured draft model "
            "(Gemma-3-1B Q4_K_M). The llama.cpp backend stores draft_model_path but never passes a "
            "draft model to create_chat_completion, so spec-decoding is NOT active; a ~0% delta is "
            "expected and is reported as 'no speculative decoding implemented'."
        ),
        "target": os.path.basename(target),
        "draft": os.path.basename(draft) if draft else None,
        "target_only": only,
        "target_with_draft": with_draft,
        "delta_tps_pct": delta_pct,
        "speculative_decoding_active": False,
    }
    save("speculative_benchmark.json", payload)


if __name__ == "__main__":
    asyncio.run(main())