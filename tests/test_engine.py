import pytest

from quantumbio_moe.engine import LocalMoEEngine
from quantumbio_moe.inference.backends import OfflineHeuristicBackend
from quantumbio_moe.prompts import PromptProfile
from quantumbio_moe.router import MoERouter
from quantumbio_moe.schemas import GenerationParams, GenerationResponse


@pytest.mark.asyncio
async def test_generate_offline():
    engine = LocalMoEEngine(directories=["."])
    await engine.start()
    assert engine.backend is not None
    response = await engine.generate("Explain a quantum annealer", max_tokens=50)
    assert isinstance(response, GenerationResponse)
    assert response.text
    assert response.prompt_tokens > 0
    assert response.completion_tokens > 0
    assert response.expert == "quantum"
    assert response.finish_reason == "stop"
    await engine.close()


@pytest.mark.asyncio
async def test_generate_spans_experts():
    engine = LocalMoEEngine(directories=["."])
    await engine.start()
    response = await engine.generate("Draft a general note about local inference.", max_tokens=30)
    assert response.expert == "general"
    await engine.close()


def test_schema_fields():
    response = GenerationResponse(text="hello world", prompt_tokens=4, completion_tokens=2)
    assert response.total_tokens == 6
    assert response.tokens_per_second == 0.0


def test_router_with_offline_backend():
    router = MoERouter(backend=OfflineHeuristicBackend())
    assert set(router.experts.keys()) >= {"quantum", "genomic", "biosecurity", "general"}


def test_resolve_system_prompt_override(tmp_path):
    engine = LocalMoEEngine(directories=["."])
    engine.prompts = PromptProfile(str(tmp_path / "system_prompts.json"))
    engine.router = MoERouter(backend=OfflineHeuristicBackend())
    assert "Genomic" in engine.resolve_system_prompt("genomic")

    engine.update_system_prompt("genomic", "Custom genomic expert prompt.")
    assert engine.resolve_system_prompt("genomic") == "Custom genomic expert prompt."
    assert engine.resolve_system_prompt("genomic", "request wins") == "request wins"

    engine.update_system_prompt("default", "Global custom prompt.")
    engine.update_system_prompt("genomic", None)  # remove per-expert override
    assert engine.resolve_system_prompt("genomic") == "Global custom prompt."

    engine.reset_all_system_prompts()
    assert engine.prompts.overrides == {}

    profile = PromptProfile(str(tmp_path / "system_prompts.json"))
    assert profile.overrides == {}


def test_generation_params_defaults():
    params = GenerationParams()
    assert params.temperature == 0.2
    assert params.top_p == 0.9
    assert params.top_k == 40
    assert params.repeat_penalty == 1.1
    assert params.max_tokens == 256
    assert "repeat_penalty" in params.param_names()
    d = params.as_dict()
    assert set(d) >= {"temperature", "top_p", "top_k", "repeat_penalty", "min_p", "max_tokens"}


@pytest.mark.asyncio
async def test_offline_backend_accepts_full_params():
    params = GenerationParams(max_tokens=16, temperature=0.0, top_p=0.5, top_k=10,
                              repeat_penalty=1.5, min_p=0.2)
    backend = OfflineHeuristicBackend()
    text = await backend.complete("summarize something", params=params, stop=["--"])
    assert text
    await backend.close()


@pytest.mark.asyncio
async def test_generate_with_params():
    engine = LocalMoEEngine(directories=["."])
    await engine.start()
    params = GenerationParams(max_tokens=30, temperature=0.0, repeat_penalty=1.4)
    response = await engine.generate("Draft a short note on local inference.", params=params)
    assert isinstance(response, GenerationResponse)
    assert response.text
    await engine.close()