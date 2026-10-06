import json
import logging
import os

logger = logging.getLogger("quantumbio_moe.prompts")


class PromptProfile:
    """Persistent per-expert system-prompt overrides plus a global 'default'.

    Users customize the LLM's behaviour through ``overrides`` keyed by expert key.
    The special key ``"default"`` is the fallback used when a specific expert has
    no override. JSON is stored at ``data/system_prompts.json`` (air-gapped local).
    """

    DEFAULT_KEY = "default"

    def __init__(self, path: str = "data/system_prompts.json"):
        self.path = path
        self.overrides: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.overrides = {str(k): str(v) for k, v in data.get("overrides", {}).items()}
        except FileNotFoundError:
            self.overrides = {}
        except (ValueError, OSError) as exc:  # pragma: no cover
            logger.warning("Failed to load prompt profile %s: %s", self.path, exc)
            self.overrides = {}

    def save(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        blob = {"overrides": self.overrides}
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(blob, handle, indent=2, ensure_ascii=False)

    def get(self, expert_key: str) -> str | None:
        return self.overrides.get(expert_key)

    def default(self) -> str | None:
        return self.overrides.get(self.DEFAULT_KEY)

    def update(self, expert_key: str, system_prompt: str | None) -> None:
        if system_prompt is None or not system_prompt.strip():
            self.overrides.pop(expert_key, None)
        else:
            self.overrides[expert_key] = system_prompt.strip()
        self.save()

    def clear_all(self) -> None:
        self.overrides = {}
        self.save()