import json

import httpx
import pytest

from medinfer.backends.base import BackendError
from medinfer.backends.http import HTTPBackend
from medinfer.benchmark.engine import measure
from medinfer.config import Settings
from medinfer.schemas import ChatRequest, Message


def request():
    return ChatRequest(model="test", messages=[Message(role="user", content="synthetic")])


async def test_ollama_ndjson_translation():
    def handler(req):
        body = json.loads(req.content)
        assert req.url.path == "/api/chat"
        assert body["options"]["num_predict"] == 512
        return httpx.Response(
            200,
            text='{"message":{"thinking":"hmm"},"done":false}\n'
            '{"message":{"content":"answer"},"done":false}\n'
            '{"done":true,"eval_count":3,"prompt_eval_count":9,'
            '"eval_duration":1000000}\n',
        )

    backend = HTTPBackend(Settings(backend="ollama", model="test"), httpx.MockTransport(handler))
    result = await measure(backend, request())
    assert result["output"] == "answer" and result["reasoning"] == "hmm"
    assert result["completion_tokens"] == 3
    assert result["extra"]["provider_eval_duration_ns"] == 1000000
    await backend.close()


async def test_vllm_sse_usage_only_chunk():
    def handler(req):
        body = json.loads(req.content)
        assert body["stream_options"]["include_usage"]
        return httpx.Response(
            200,
            text=': heartbeat\r\n\r\ndata: {"choices":[{"delta":'
            '{"content":"answer"},"finish_reason":null}]}\r\n\r\n'
            'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n'
            'data: {"choices":[],"usage":{"prompt_tokens":8,'
            '"completion_tokens":2}}\n\ndata: [DONE]\n\n',
        )

    backend = HTTPBackend(Settings(backend="vllm", model="test"), httpx.MockTransport(handler))
    result = await measure(backend, request())
    assert result["output"] == "answer" and result["finish_reason"] == "length"
    assert result["completion_tokens"] == 2
    await backend.close()


@pytest.mark.parametrize(
    "status,text",
    [
        (500, "secret upstream body"),
        (200, "not json\n"),
        (200, '{"message":{"content":"partial"}}\n'),
    ],
)
async def test_upstream_failures_are_safe(status, text):
    backend = HTTPBackend(
        Settings(backend="ollama"), httpx.MockTransport(lambda r: httpx.Response(status, text=text))
    )
    with pytest.raises(BackendError) as error:
        await measure(backend, request())
    assert "secret" not in str(error.value)
    await backend.close()
