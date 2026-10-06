import abc
import asyncio
import logging
import os
import time

from ..config import settings
from ..schemas import GenerationParams

logging.basicConfig(
    level=getattr(logging, settings.LOCALMOE_LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("quantumbio_moe.inference")


def estimate_tokens(text: str) -> int:
    return max(1, len([token for token in text.replace("\n", " ").split(" ") if token]))


class InferenceBackend(abc.ABC):
    name: str = "base"
    supports_streaming: bool = False

    def __init__(self, model_path: str | None = None, draft_model_path: str | None = None):
        self.model_path = model_path
        self.draft_model_path = draft_model_path

    @abc.abstractmethod
    async def complete(self, prompt: str, params: GenerationParams | None = None,
                       stop: list[str] | None = None, system_prompt: str | None = None) -> str:
        raise NotImplementedError

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass


class VLLMBackend(InferenceBackend):
    name = "vllm"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine = None
        self._sampling_factory = None

    async def start(self) -> None:
        try:
            from vllm import AsyncEngineArgs, AsyncLLMEngine, SamplingParams
        except ImportError:
            raise RuntimeError("vLLM is not installed. Install it on a Linux GPU host.")
        self._sampling_factory = SamplingParams
        args = AsyncEngineArgs(
            model=self.model_path,
            quantization=settings.QUANTIZATION_TYPE.lower(),
            tensor_parallel_size=1,
        )
        self._engine = await asyncio.to_thread(AsyncLLMEngine.from_engine_args, args)

    async def complete(self, prompt: str, params: GenerationParams | None = None,
                       stop: list[str] | None = None, system_prompt: str | None = None) -> str:
        if self._engine is None:
            raise RuntimeError("vLLM backend has not been started")
        params = params or GenerationParams()
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        sampling = self._sampling_factory(
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            top_p=params.top_p,
            top_k=params.top_k,
            min_p=params.min_p,
            repetition_penalty=params.repeat_penalty,
            presence_penalty=params.presence_penalty,
            frequency_penalty=params.frequency_penalty,
            stop=stop or [],
        )
        request_id = f"quantumbio-{int(time.time() * 1000)}"
        text = ""
        async for result in self._engine.generate(full_prompt, sampling, request_id):
            text = result.outputs[0].text
        return text


class LlamaCppBackend(InferenceBackend):
    name = "llama.cpp"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._model = None

    async def start(self) -> None:
        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError("llama-cpp-python is not installed.")
        logger.info("Loading GGUF model %s via llama.cpp ...", self.model_path)
        self._model = await asyncio.to_thread(
            Llama, model_path=self.model_path, n_ctx=4096, verbose=False
        )

    async def complete(self, prompt: str, params: GenerationParams | None = None,
                       stop: list[str] | None = None, system_prompt: str | None = None) -> str:
        if self._model is None:
            raise RuntimeError("llama.cpp backend has not been started")
        params = params or GenerationParams()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        stop_sequences = ["<|endoftext|>", "<|eot_id|>", "<|im_end|>"] + (stop or [])
        output = await asyncio.to_thread(
            self._model.create_chat_completion,
            messages,
            max_tokens=params.max_tokens,
            temperature=params.temperature,
            top_p=params.top_p,
            top_k=params.top_k,
            min_p=params.min_p,
            repeat_penalty=params.repeat_penalty,
            presence_penalty=params.presence_penalty,
            frequency_penalty=params.frequency_penalty,
            stop=stop_sequences,
            seed=-1,
        )
        return (output or {}).get("choices", [{}])[0].get("message", {}).get("content", "") or ""


class OfflineHeuristicBackend(InferenceBackend):
    name = "offline-heuristic"

    def __init__(self, model_path: str | None = None, draft_model_path: str | None = None,
                 note: str | None = None):
        super().__init__(model_path=model_path, draft_model_path=draft_model_path)
        self.note = note or (
            "No quantized model weights were found under the configured model directories.\n"
            "Place a GGUF or AWQ model in those directories - or scan an extra directory - "
            "to enable real inference."
        )

    def _build_body(self, prompt: str, params: GenerationParams, stop: list[str] | None) -> str:
        snippet = " ".join(prompt.split()[:60])
        lines = [
            "Local MoE engine (offline fallback mode).",
            "",
            self.note,
            "",
            "Request prompt preview:",
            snippet,
        ]
        body = "\n".join(lines)
        if stop:
            for token in stop:
                body = body.split(token)[0]
        return body[: params.max_tokens * 4]

    async def complete(self, prompt: str, params: GenerationParams | None = None,
                       stop: list[str] | None = None, system_prompt: str | None = None) -> str:
        await asyncio.sleep(0)
        params = params or GenerationParams()
        return self._build_body(prompt, params, stop)


class DiffusionBackend:
    name = "stable-diffusion.cpp"

    def __init__(self, model_path: str, output_dir: str = "./outputs"):
        self.model_path = model_path
        self.output_dir = output_dir
        self._sd = None

    async def start(self) -> None:
        try:
            from stable_diffusion_cpp import StableDiffusion
        except ImportError:
            raise RuntimeError("stable-diffusion-cpp-python is not installed.")
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info("Loading diffusion GGUF %s ...", self.model_path)
        self._sd = await asyncio.to_thread(StableDiffusion, model_path=self.model_path)

    async def txt_to_img(self, prompt: str, negative_prompt: str = "",
                         width: int = 512, height: int = 512, steps: int = 20) -> str:
        if self._sd is None:
            raise RuntimeError("diffusion backend has not been started")
        image = await asyncio.to_thread(
            self._sd.txt_to_img,
            prompt,
            width=width,
            height=height,
            sample_steps=steps,
            seed=int(time.time()) % (2**31),
        )
        os.makedirs(self.output_dir, exist_ok=True)
        out_path = os.path.join(self.output_dir, f"img_{int(time.time() * 1000)}.png")
        image.save(out_path)
        return out_path

    async def img_to_img(self, prompt: str, init_image: str, strength: float = 0.6,
                         width: int = 512, height: int = 512, steps: int = 20) -> str:
        if self._sd is None:
            raise RuntimeError("diffusion backend has not been started")
        image = await asyncio.to_thread(
            self._sd.img_to_img,
            prompt,
            init_image=init_image,
            width=width,
            height=height,
            sample_steps=steps,
            strength=strength,
            seed=int(time.time()) % (2**31),
        )
        os.makedirs(self.output_dir, exist_ok=True)
        out_path = os.path.join(self.output_dir, f"img_{int(time.time() * 1000)}.png")
        image.save(out_path)
        return out_path

    async def close(self) -> None:
        self._sd = None


class WhisperBackend:
    name = "whisper.cpp"

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None

    async def start(self) -> None:
        try:
            from faster_whisper import WhisperModel
            self._backend = "faster-whisper"
        except ImportError:
            try:
                from whisper_cpp import Whisper
                self._backend = "whisper_cpp"
            except ImportError:
                raise RuntimeError("Neither faster-whisper nor whisper_cpp is installed.")
        logger.info("Loading audio model %s (%s) ...", self.model_path, self._backend)
        if self._backend == "faster-whisper":
            self._model = await asyncio.to_thread(WhisperModel, self.model_path)
        else:
            self._model = await asyncio.to_thread(Whisper, self.model_path)

    async def transcribe(self, audio_path: str) -> str:
        if self._model is None:
            raise RuntimeError("audio backend has not been started")
        if self._backend == "faster-whisper":
            segments, _info = await asyncio.to_thread(self._model.transcribe, audio_path)
            return "\n".join(segment.text.strip() for segment in segments)
        result = await asyncio.to_thread(self._model.transcribe, audio_path)
        return getattr(result, "text", "") or str(result)

    async def close(self) -> None:
        self._model = None


def find_model_files(model_directory: str) -> list[str]:
    found: list[str] = []
    if not os.path.isdir(model_directory):
        return found
    for root, _dirs, files in os.walk(model_directory):
        for filename in files:
            if filename.lower().endswith(".gguf"):
                found.append(os.path.join(root, filename))
    return sorted(found)


def has_awq_model(model_directory: str) -> str | None:
    if not os.path.isdir(model_directory):
        return None
    for entry in sorted(os.listdir(model_directory)):
        path = os.path.join(model_directory, entry)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "config.json")):
            return path
    return None


def build_backend(model_path: str | None = None, draft_model_path: str | None = None,
                  directories: list[str] | None = None) -> InferenceBackend:
    dirs = directories or [settings.MODEL_DIRECTORY]
    resolved_path = model_path
    if not resolved_path:
        for directory in dirs:
            ggufs = find_model_files(directory)
            if ggufs:
                resolved_path = ggufs[0]
                break
        if not resolved_path:
            for directory in dirs:
                awq = has_awq_model(directory)
                if awq:
                    resolved_path = awq
                    break

    if resolved_path:
        if resolved_path.endswith(".gguf"):
            return LlamaCppBackend(model_path=resolved_path, draft_model_path=draft_model_path)
        return VLLMBackend(model_path=resolved_path, draft_model_path=draft_model_path)

    logger.info("No local weights found - using offline heuristic backend.")
    return OfflineHeuristicBackend(model_path=draft_model_path or None,
                                   draft_model_path=draft_model_path)