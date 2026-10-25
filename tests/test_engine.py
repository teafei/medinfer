import asyncio
import json

import pytest

from medinfer.backends.mock import MockBackend
from medinfer.benchmark.engine import BenchmarkRunner, measure
from medinfer.benchmark.metrics import aggregate, percentile
from medinfer.benchmark.storage import Store
from medinfer.schemas import BenchmarkRequest, ChatRequest, Message


def req(backend):
    return ChatRequest(
        model=backend.settings.model, messages=[Message(role="user", content="test")]
    )


async def test_ttft_skips_empty_and_includes_reasoning(scripted):
    result = await measure(scripted, req(scripted))
    assert 0 < result["ttft_s"] < result["first_content_s"] < result["latency_s"]
    assert result["completion_tokens"] == 4 and result["tokens_s"] > 0


async def test_mock_has_no_invented_tokens(settings):
    backend = MockBackend(settings)
    result = await measure(backend, req(backend))
    assert result["completion_tokens"] is None and result["tokens_s"] is None


async def test_concurrency_warmup_persistence_and_export(scripted, settings):
    store = Store(settings.db)
    result = await BenchmarkRunner(scripted, store).run(
        BenchmarkRequest(concurrency=4, repetitions=2, limit=3, warmup=1)
    )
    assert result["status"] == "completed"
    assert result["summary"]["successful"] == 6
    assert len(result["records"]) == 6 and scripted.calls == 7
    assert 1 < scripted.peak <= 4
    assert result["summary"]["output_tokens_s"] > 0
    assert result["summary"]["resources"]["gateway_rss_peak_bytes"] > 0
    assert result["summary"]["resources"]["gpu_device_memory_peak_mib"] is None
    assert json.loads(json.dumps(result)) == store.get(result["id"])
    assert Store(settings.db).list()[0]["id"] == result["id"]


async def test_failures_stay_in_denominator(scripted, settings):
    scripted.fail = True
    result = await BenchmarkRunner(scripted, Store(settings.db)).run(
        BenchmarkRequest(limit=3, warmup=0)
    )
    assert result["summary"]["failed"] == 3
    assert result["summary"]["error_rate"] == 1
    assert result["summary"]["latency_p95_s"] is None
    assert result["summary"]["quality"]["qa"]["n_successful"] == 0


async def test_timeout_cleans_generator(scripted):
    with pytest.raises(TimeoutError):
        await measure(scripted, req(scripted), timeout_s=0.001)
    assert scripted.active == 0


async def test_warmup_failure_is_failed_run(scripted, settings):
    scripted.fail = True
    store = Store(settings.db)
    with pytest.raises(RuntimeError):
        await BenchmarkRunner(scripted, store).run(BenchmarkRequest(limit=1))
    assert store.list()[0]["status"] == "failed"


async def test_cancel_persists_interrupted(scripted, settings):
    store = Store(settings.db)
    task = asyncio.create_task(
        BenchmarkRunner(scripted, store).run(BenchmarkRequest(limit=3, warmup=0))
    )
    await asyncio.sleep(0.002)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert store.list()[0]["status"] == "interrupted"


def test_percentile_linear_and_empty():
    assert percentile([], 0.95) is None
    assert percentile([10], 0.95) == 10
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([1, 2, 3, 4], 0.95) == pytest.approx(3.85)


def test_missing_tokens_are_not_zero():
    record = dict(
        error=None,
        task="qa",
        scores={"exact_match": 0},
        latency_s=2,
        ttft_s=None,
        completion_tokens=None,
        tokens_s=None,
        finish_reason="stop",
    )
    result = aggregate([record], 2)
    assert result["output_tokens_s"] is None
    assert result["token_count_coverage"] == 0


def test_restart_marks_stale(settings):
    store = Store(settings.db)
    store.create("run-1", "2026-10-25", {})
    store.interrupt_stale()
    assert store.get("run-1")["status"] == "interrupted"
