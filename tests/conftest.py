import asyncio

import pytest

from medinfer.backends.base import Backend, Event
from medinfer.config import Settings


class ScriptedBackend(Backend):
    def __init__(self, settings, text="negative", fail=False):
        super().__init__(settings)
        self.text, self.fail = text, fail
        self.active = self.peak = self.calls = 0

    async def health(self):
        return {"ready": True, **self.metadata()}

    async def stream(self, request):
        from medinfer.backends.base import BackendError

        self.calls += 1
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.005)
            if self.fail:
                raise BackendError("test upstream failure")
            yield Event()  # Empty metadata chunk must not define TTFT.
            await asyncio.sleep(0.005)
            yield Event(reasoning="checking")
            await asyncio.sleep(0.005)
            yield Event(text=self.text)
            yield Event(prompt_tokens=10, completion_tokens=4, finish_reason="stop")
        finally:
            self.active -= 1


@pytest.fixture
def settings(tmp_path):
    return Settings(backend="mock", model="mock-synthetic", db=str(tmp_path / "run.sqlite3"))


@pytest.fixture
def scripted(settings):
    return ScriptedBackend(settings)
