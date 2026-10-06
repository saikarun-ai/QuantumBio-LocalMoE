from dataclasses import dataclass, field


@dataclass
class GenerationParams:
    """Sampling parameters controlling clarity and efficiency of LLM output.

    Lower temperature + repeat penalty keeps answers focused; max_tokens bounds
    response length for efficiency.
    """
    max_tokens: int = 256
    temperature: float = 0.2
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    min_p: float = 0.05
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0

    def as_dict(self) -> dict:
        return {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
            "min_p": self.min_p,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
        }

    def param_names(self) -> list[str]:
        return [
            "top_p", "top_k", "repeat_penalty", "min_p",
            "presence_penalty", "frequency_penalty",
        ]


@dataclass
class GenerationResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_per_second: float = 0.0
    expert: str = "general"
    model: str = "quantumbio-moe-local"
    finish_reason: str = "stop"

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class RouteDecision:
    expert_key: str = "general"
    confidence: float = 0.0
    intent: str = "general"
    keywords_hit: list = field(default_factory=list)