from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from medinfer.config import Settings
from medinfer.schemas import ChatRequest


class BackendError(RuntimeError):
    """Public-safe failure; do not forward upstream bodies or credentials."""


@dataclass
class Event:
    text: str = ""
    reasoning: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None
    extra: dict = field(default_factory=dict)


class Backend(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def stream(self, request: ChatRequest) -> AsyncIterator[Event]: ...

    @abstractmethod
    async def health(self) -> dict: ...

    async def close(self):
        """Release resources when a concrete backend owns any."""
        return None

    def metadata(self) -> dict:
        return {
            "backend": self.settings.backend,
            "model": self.settings.model,
            "model_revision": self.settings.model_revision,
            "simulated": self.settings.backend == "mock",
        }
