import abc

from ..schemas import GenerationParams


class BaseExpert(abc.ABC):
    key: str = "base"
    display_name: str = "Base Expert"
    intent: str = "general"
    keywords: tuple[str, ...] = ()
    system_prompt: str = "You are a helpful local reasoning assistant."

    def __init__(self, backend):
        self.backend = backend

    async def generate(self, prompt: str, params: GenerationParams | None = None,
                       system_prompt: str | None = None) -> str:
        prompt_instruction = (system_prompt or self.system_prompt).strip()
        return await self.backend.complete(
            prompt,
            params=params,
            system_prompt=prompt_instruction,
        )

    def describe(self) -> dict:
        return {
            "key": self.key,
            "name": self.display_name,
            "intent": self.intent,
            "keywords": list(self.keywords),
        }