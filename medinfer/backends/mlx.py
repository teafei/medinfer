import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from medinfer.backends.base import Backend, BackendError, Event
from medinfer.backends.reasoning import ThinkSplitter


class MLXBackend(Backend):
    """A single dedicated worker owns Metal state; local generation is serialized."""

    def __init__(self, settings):
        super().__init__(settings)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="medinfer-mlx")
        self.lock = asyncio.Lock()
        self.model = self.tokenizer = None
        self.resolved_revision = None

    def _load(self):
        if self.model is None:
            from huggingface_hub import snapshot_download
            from mlx_lm import load

            path = snapshot_download(self.settings.model, revision=self.settings.model_revision)
            self.resolved_revision = path.rstrip("/").split("/")[-1]
            # Standard built-in architecture + safetensors; remote Python code is disabled.
            self.model, self.tokenizer = load(path, tokenizer_config={"trust_remote_code": False})

    def metadata(self):
        return {
            **super().metadata(),
            "resolved_revision": self.resolved_revision,
            "scheduler": "single dedicated MLX worker; no continuous batching",
        }

    async def health(self):
        import importlib.util

        return {
            "ready": importlib.util.find_spec("mlx_lm") is not None,
            "loaded": self.model is not None,
            **self.metadata(),
        }

    async def stream(self, request):
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        cancelled = threading.Event()

        def send(value):
            if not cancelled.is_set() and not loop.is_closed():
                loop.call_soon_threadsafe(queue.put_nowait, value)

        def worker():
            try:
                import mlx.core as mx
                from mlx_lm import stream_generate
                from mlx_lm.sample_utils import make_sampler

                self._load()
                if request.seed is not None:
                    mx.random.seed(request.seed)
                mx.reset_peak_memory()
                prompt = self.tokenizer.apply_chat_template(
                    [m.model_dump() for m in request.messages],
                    tokenize=False,
                    add_generation_prompt=True,
                )
                splitter = ThinkSplitter(thinking=prompt.rstrip().endswith("<think>"))
                for response in stream_generate(
                    self.model,
                    self.tokenizer,
                    prompt=prompt,
                    max_tokens=request.max_tokens,
                    sampler=make_sampler(temp=request.temperature, top_p=request.top_p),
                ):
                    if cancelled.is_set():
                        break
                    text, reasoning = splitter.feed(
                        response.text, final=response.finish_reason is not None
                    )
                    send(
                        Event(
                            text=text,
                            reasoning=reasoning,
                            prompt_tokens=response.prompt_tokens,
                            completion_tokens=response.generation_tokens,
                            finish_reason=response.finish_reason,
                            extra={"mlx_metal_peak_gb": response.peak_memory},
                        )
                    )
            except Exception:
                send(BackendError("MLX generation failed; check model, context and installation"))
            finally:
                send(None)

        async with self.lock:
            future = loop.run_in_executor(self.executor, worker)
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        raise item
                    yield item
                await future
            finally:
                cancelled.set()
                # Cancellation cannot terminate a running Metal operation. The dedicated
                # executor still serializes the next request after it exits.

    async def close(self):
        await asyncio.to_thread(self.executor.shutdown, wait=True, cancel_futures=True)
