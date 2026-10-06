import logging
import os
from dataclasses import dataclass
from typing import Optional

from ..config import settings

logger = logging.getLogger("quantumbio_moe.models")

TEXT_MARKERS = (
    "deepseek", "llama", "mistral", "mixtral", "gemma", "phi", "qwen",
    "gpt", "orca", "zephyr", "dolphin", "hermes", "neural", "solar",
    "command", "falcon", "mpt", "granite", "stablelm", "tinyllama",
    "gem", "coder", "codeqwen",
)
DIFFUSION_MARKERS = (
    "stable_diffusion", "sdxl", "dreamshaper", "realisticvision",
    "deliberate", "i2_s", "imgmodel", "v2-1", "v1-5", "anime",
    "turbo", "flux", "sd1", "sd2", "playground", "kandinsky",
)
AUDIO_MARKERS = ("whisper", "speech", "encodec", "tts", "voice", "wav", "bark")


@dataclass
class ModelEntry:
    path: str
    name: str
    kind: str
    size_bytes: int


def _classify(filename: str) -> Optional[str]:
    lower = filename.lower()
    if not (lower.endswith(".gguf") or lower.endswith(".bin")):
        return None
    for marker in TEXT_MARKERS:
        if marker in lower:
            return "text"
    for marker in DIFFUSION_MARKERS:
        if marker in lower:
            return "diffusion"
    for marker in AUDIO_MARKERS:
        if marker in lower:
            return "audio"
    return None


def default_directories() -> list[str]:
    dirs = []
    for raw in [settings.MODEL_DIRECTORY] + [d for d in settings.MODEL_EXTRA_DIRECTORIES.split(",") if d.strip()]:
        path = os.path.abspath(os.path.expanduser(raw.strip()))
        if os.path.isdir(path) and path not in dirs:
            dirs.append(path)
    for path in list(dirs):
        os.makedirs(path, exist_ok=True)
    return dirs


class ModelRegistry:
    def __init__(self, directories: list[str] | None = None):
        self.directories = directories or default_directories()
        self.models: list[ModelEntry] = []
        self._scan()

    def _scan(self) -> None:
        self.models = []
        seen = set()
        for directory in self.directories:
            if not os.path.isdir(directory):
                continue
            for filename in sorted(os.listdir(directory)):
                path = os.path.join(directory, filename)
                if not os.path.isfile(path):
                    continue
                kind = _classify(filename)
                if kind is None:
                    continue
                key = filename.lower()
                if key in seen:
                    continue
                seen.add(key)
                self.models.append(
                    ModelEntry(path=path, name=filename, kind=kind, size_bytes=os.path.getsize(path))
                )
        logger.info(
            "Model registry scanned %d directories: %s",
            len(self.directories),
            ", ".join(self.directories),
        )

    def add_directory(self, directory: str) -> None:
        directory = os.path.abspath(os.path.expanduser(directory.strip()))
        if not os.path.isdir(directory):
            raise ValueError(f"directory does not exist: {directory}")
        if directory not in self.directories:
            self.directories.append(directory)
            self._scan()

    def by_kind(self, kind: str) -> list[ModelEntry]:
        return sorted(
            [model for model in self.models if model.kind == kind],
            key=lambda m: m.size_bytes,
        )

    @property
    def text_models(self) -> list[ModelEntry]:
        return self.by_kind("text")

    @property
    def diffusion_models(self) -> list[ModelEntry]:
        return self.by_kind("diffusion")

    @property
    def audio_models(self) -> list[ModelEntry]:
        return self.by_kind("audio")

    def select(self, kind: str, preferred: str = "") -> str | None:
        matches = self.by_kind(kind)
        if not matches:
            return None
        if preferred:
            clean = os.path.basename(preferred).lower()
            for model in matches:
                if model.name.lower() == clean or preferred in model.path:
                    return model.path
            if os.path.exists(preferred):
                return preferred
        return matches[-1].path

    def select_main_text(self) -> str | None:
        return self.select("text", settings.MODEL_NAME)

    def select_draft(self) -> str | None:
        preferred = settings.DRAFT_MODEL_PATH
        matches = self.by_kind("text")
        if not matches:
            return None
        if preferred:
            for model in matches:
                if os.path.basename(preferred).lower() in model.name.lower():
                    return model.path
            if os.path.exists(preferred):
                return preferred
        return matches[0].path