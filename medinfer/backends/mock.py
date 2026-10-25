import asyncio

from medinfer.backends.base import Backend, Event


class MockBackend(Backend):
    """Deliberately imperfect fixed output; never reads benchmark references."""

    async def health(self):
        return {"ready": True, **self.metadata()}

    async def stream(self, request):
        text = "SIMULATED OUTPUT. No model inference was performed."
        for word in text.split(" "):
            await asyncio.sleep(0.002)
            yield Event(text=word + " ")
        # There is no tokenizer: mock must not invent token counts or tokens/s.
        yield Event(finish_reason="stop")
