import asyncio
import time
import uuid
from datetime import UTC, datetime

from medinfer.backends.base import BackendError
from medinfer.benchmark.dataset import dataset_hash, load_cases
from medinfer.benchmark.metrics import ResourceSampler, aggregate, environment
from medinfer.benchmark.scoring import score
from medinfer.schemas import ChatRequest, Message


async def measure(backend, request, timeout_s=180, sink=None):
    start = time.perf_counter()
    first = answer_first = None
    content, reasoning = [], []
    prompt_tokens = completion_tokens = None
    finish_reason = None
    extra = {}
    async with asyncio.timeout(timeout_s):
        stream = backend.stream(request)
        try:
            async for event in stream:
                now = time.perf_counter()
                if (event.text or event.reasoning) and first is None:
                    first = now
                if event.text and answer_first is None:
                    answer_first = now
                content.append(event.text)
                reasoning.append(event.reasoning)
                if event.prompt_tokens is not None:
                    prompt_tokens = event.prompt_tokens
                if event.completion_tokens is not None:
                    completion_tokens = event.completion_tokens
                if event.finish_reason:
                    finish_reason = event.finish_reason
                extra.update({k: v for k, v in event.extra.items() if v is not None})
                if sink:
                    await sink(event)
        finally:
            await stream.aclose()
    end = time.perf_counter()
    if finish_reason is None:
        raise BackendError("generation ended without a finish reason")
    return {
        "output": "".join(content),
        "reasoning": "".join(reasoning),
        "latency_s": end - start,
        "ttft_s": first - start if first else None,
        "first_content_s": answer_first - start if answer_first else None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_s": completion_tokens / (end - first)
        if completion_tokens is not None and first and end > first
        else None,
        "finish_reason": finish_reason,
        "extra": extra,
    }


class BenchmarkRunner:
    def __init__(self, backend, store):
        self.backend, self.store = backend, store

    async def run(self, options, run_id=None):
        run_id = run_id or str(uuid.uuid4())
        cases = load_cases(options.task, options.limit)
        config = {
            **options.model_dump(),
            **self.backend.metadata(),
            "dataset_sha256": dataset_hash(),
            "dataset": "synthetic-v1",
            "environment": environment(),
            "temperature": 0,
            "top_p": 1,
            "seed": 42,
            "measurement": "closed-loop; warmup excluded; no prefix-cache reset",
        }
        self.store.create(run_id, datetime.now(UTC).isoformat(), config)

        def request(case):
            return ChatRequest(
                model=self.backend.settings.model,
                messages=[Message(role="user", content=case["prompt"])],
                max_tokens=options.max_tokens,
                temperature=0,
                seed=42,
            )

        records = []
        try:
            for _ in range(options.warmup):
                await measure(self.backend, request(cases[0]), options.timeout_s)
            sem = asyncio.Semaphore(options.concurrency)

            async def one(sequence, case, repetition):
                queued = time.perf_counter()
                async with sem:
                    started = time.perf_counter()
                    record = {
                        "sequence": sequence,
                        "case_id": case["id"],
                        "task": case["task"],
                        "repetition": repetition,
                        "queue_s": started - queued,
                        "error": None,
                        "scores": {},
                    }
                    try:
                        result = await measure(self.backend, request(case), options.timeout_s)
                        record.update(result)
                        record["scores"] = score(case, result["output"])
                    except (BackendError, TimeoutError) as exc:
                        record.update(
                            error="request timed out"
                            if isinstance(exc, TimeoutError)
                            else str(exc),
                            latency_s=time.perf_counter() - started,
                            ttft_s=None,
                            completion_tokens=None,
                            finish_reason=None,
                        )
                    record["end_to_end_s"] = time.perf_counter() - queued
                    self.store.append(run_id, sequence, record)
                    records.append(record)

            wall_start = time.perf_counter()
            async with ResourceSampler(options.gpu_index) as resources:
                # TaskGroup cancels sibling work if an unexpected programming/storage error occurs.
                async with asyncio.TaskGroup() as group:
                    sequence = 0
                    for repetition in range(options.repetitions):
                        for case in cases:
                            group.create_task(one(sequence, case, repetition))
                            sequence += 1
            wall = time.perf_counter() - wall_start
            summary = {
                **aggregate(records, wall),
                "resources": resources.result(),
                "backend_at_finish": self.backend.metadata(),
            }
            self.store.finish(run_id, "completed", summary)
        except asyncio.CancelledError:
            self.store.finish(run_id, "interrupted", error="run cancelled")
            raise
        except Exception:
            self.store.finish(run_id, "failed", error="warmup, backend or persistence failure")
            raise
        return self.store.get(run_id)
