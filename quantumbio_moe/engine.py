import asyncio
import logging
import os
import time
import uuid

from .config import settings
from .inference import (
    DiffusionBackend,
    InferenceBackend,
    OfflineHeuristicBackend,
    ModelRegistry,
    estimate_tokens,
    build_backend,
    WhisperBackend,
)
from .inference.registry import default_directories
from .prompts import PromptProfile
from .quantum import QuantumBridge
from .router import MoERouter
from .schemas import GenerationParams, GenerationResponse
from .storage import Database, RedisStore, VectorCache
from .utils.security import apply_airgap_config, scrub_memory

logger = logging.getLogger("quantumbio_moe.engine")


class LocalMoEEngine:
    def __init__(self, model_path: str | None = None,
                 quantization: str | None = None,
                 draft_model_path: str | None = None,
                 directories: list[str] | None = None):
        apply_airgap_config()
        self.model_path = model_path
        self.quantization = quantization or settings.QUANTIZATION_TYPE
        self.directories = directories or default_directories()
        self.draft_model_path = draft_model_path

        self.registry = ModelRegistry(self.directories)
        resolved_main = model_path or self.registry.select_main_text()
        resolved_draft = draft_model_path or settings.DRAFT_MODEL_PATH or self.registry.select_draft()

        self.backend: InferenceBackend = build_backend(
            resolved_main, draft_model_path=resolved_draft, directories=self.directories
        )
        self.diffusion_backend: DiffusionBackend | None = None
        self.whisper_backend: WhisperBackend | None = None
        self.router: MoERouter | None = None
        self.prompts = PromptProfile()
        self.cache = VectorCache()
        self.redis = RedisStore()
        self.database = Database()
        self.quantum = QuantumBridge()
        self._started = False

    async def start(self) -> None:
        logger.info("Starting QuantumBio-LocalMoE engine (quantization=%s)", self.quantization)
        try:
            await self.backend.start()
        except RuntimeError as exc:
            logger.warning("%s - switching to offline heuristic backend.", exc)
            self.backend = OfflineHeuristicBackend(
                model_path=getattr(self.backend, "model_path", None),
                draft_model_path=getattr(self.backend, "draft_model_path", None),
                note=str(exc),
            )

        diffusion_models = self.registry.by_kind("diffusion")
        if diffusion_models and self.quantization.lower() in ("awq", "int4", "gguf", "q4", "q8"):
            path = self.registry.select("diffusion")
            candidate = DiffusionBackend(path)
            try:
                await candidate.start()
                self.diffusion_backend = candidate
                logger.info("Diffusion expert ready with %s", os.path.basename(path))
            except RuntimeError:
                logger.warning("Diffusion backend unavailable; image requests will be text-only.");

        audio_models = self.registry.by_kind("audio")
        if audio_models:
            path = self.registry.select("audio")
            candidate = WhisperBackend(path)
            try:
                await candidate.start()
                self.whisper_backend = candidate
                logger.info("Audio expert ready with %s", os.path.basename(path))
            except RuntimeError:
                logger.warning("Audio backend unavailable; transcription requests disabled.");

        self.router = MoERouter(self.backend, diffusion_backend=self.diffusion_backend)
        self.quantum.load()
        if settings.AUTO_CONNECT_INFRA:
            await self.cache.start()
            await self.redis.start()
            await self.database.start()
        else:
            logger.info("External infrastructure auto-connect disabled (AUTO_CONNECT_INFRA=false).")
        self._started = True

    async def close(self) -> None:
        for store in (self.cache, self.redis, self.database):
            await store.close()
        if self.backend:
            await self.backend.close()
        if self.diffusion_backend:
            await self.diffusion_backend.close()
        if self.whisper_backend:
            await self.whisper_backend.close()
        scrub_memory()
        logger.info("Engine shut down; memory scrubbed.")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    @property
    def current_model(self) -> str | None:
        return getattr(self.backend, "model_path", None)

    async def select_model(self, path: str) -> dict:
        if not path:
            raise ValueError("model path is required")
        if not (os.path.isfile(path) or os.path.isdir(path)):
            raise ValueError(f"path does not exist: {path}")
        if self.backend:
            await self.backend.close()

        selected = build_backend(
            model_path=path,
            draft_model_path=self.draft_model_path or settings.DRAFT_MODEL_PATH,
            directories=self.directories,
        )
        fell_back = False
        try:
            await selected.start()
            self.backend = selected
        except RuntimeError as exc:
            logger.warning("%s - selected model using offline heuristic backend.", exc)
            self.backend = OfflineHeuristicBackend(
                model_path=path,
                draft_model_path=self.draft_model_path or settings.DRAFT_MODEL_PATH,
                note=str(exc),
            )
            fell_back = True
        if self.router:
            self.router = MoERouter(self.backend, diffusion_backend=self.diffusion_backend)
        return {
            "ok": True,
            "active": self.current_model,
            "backend": self.backend.name,
            "fallback": fell_back,
        }

    def add_model_directory(self, directory: str) -> list[dict]:
        self.registry.add_directory(directory)
        return [
            {"name": model.name, "path": model.path, "kind": model.kind,
             "size_bytes": model.size_bytes}
            for model in self.registry.models
        ]

    def resolve_system_prompt(self, expert_key: str, request_system: str | None = None) -> str:
        """Highest priority wins: per-request, per-expert override, global default, built-in."""
        if request_system:
            return request_system
        if expert_key in self.prompts.overrides:
            return self.prompts.overrides[expert_key]
        if PromptProfile.DEFAULT_KEY in self.prompts.overrides:
            return self.prompts.overrides[PromptProfile.DEFAULT_KEY]
        if self.router:
            return self.router.experts[expert_key].system_prompt
        return ""

    def update_system_prompt(self, expert_key: str, system_prompt: str | None) -> None:
        self.prompts.update(expert_key, system_prompt)

    def reset_all_system_prompts(self) -> None:
        self.prompts.clear_all()

    def prompt_profile_view(self) -> dict:
        view: dict[str, dict] = {}
        if self.router:
            for key, expert in self.router.experts.items():
                default_prompt = self.router.experts[key].system_prompt
                view[key] = {
                    "default": default_prompt,
                    "active": self.resolve_system_prompt(key),
                    "customized": key in self.prompts.overrides,
                }
        return {
            "experts": view,
            "overrides": dict(self.prompts.overrides),
            "default_override": self.prompts.default(),
        }

    async def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.2,
                       expert: str | None = None,
                       params: GenerationParams | None = None,
                       system_prompt: str | None = None) -> GenerationResponse:
        if not self._started:
            await self.start()
        if params is None:
            params = GenerationParams(max_tokens=max_tokens, temperature=temperature)
        started = time.perf_counter()
        prompt_tokens = estimate_tokens(prompt)
        expert_key = expert or self.router.route(prompt)[0]
        selected = self.router.experts[expert_key]
        prompt_instruction = self.resolve_system_prompt(expert_key, system_prompt)

        await self.cache.upsert(key=f"prompt:{prompt_tokens}:{expert_key}", text=prompt)
        text = await selected.generate(prompt, params=params, system_prompt=prompt_instruction)

        elapsed = max(time.perf_counter() - started, 1e-6)
        completion_tokens = estimate_tokens(text)
        response = GenerationResponse(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_per_second=round(completion_tokens / elapsed, 2),
            expert=expert_key,
            model=getattr(self.backend, "name", "local"),
        )
        await self.redis.set(f"response:{uuid.uuid4().hex}", text[:1024])
        await self.database.log_request(
            request_id=f"req_{uuid.uuid4().hex}",
            model=response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            expert=expert_key,
            latency_ms=int(elapsed * 1000),
        )
        return response

    async def generate_image(self, prompt: str, negative_prompt: str = "",
                             width: int = 512, height: int = 512, steps: int = 20) -> str:
        if not self._started:
            await self.start()
        if self.diffusion_backend is None:
            raise RuntimeError("No diffusion model available (missing GGUF or stable-diffusion-cpp).")
        return await self.diffusion_backend.txt_to_img(
            prompt, negative_prompt=negative_prompt, width=width, height=height, steps=steps
        )

    async def transcribe(self, audio_path: str) -> str:
        if not self._started:
            await self.start()
        if self.whisper_backend is None:
            raise RuntimeError("No audio model available.")
        return await self.whisper_backend.transcribe(audio_path)

    def expert_catalog(self) -> list[dict]:
        return [expert.describe() for expert in self.router.experts.values()]