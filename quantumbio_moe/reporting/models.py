import time
from dataclasses import dataclass, field


@dataclass
class Report:
    """A curated, exportable report produced from source engine output."""

    title: str
    source: str
    draft: str = ""
    expert: str = "general"
    model: str = "quantumbio-moe-local"
    created_at: float = field(default_factory=time.time)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def created_iso(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.created_at))