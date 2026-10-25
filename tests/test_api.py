import asyncio
from dataclasses import replace

import httpx
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from medinfer.api import create_app, csv_export


def body(settings, **extra):
    return {
        "model": settings.model,
        "messages": [{"role": "user", "content": "synthetic"}],
        **extra,
    }


def test_health_auth_and_static(settings, scripted):
    settings = replace(settings, api_key="test-only")
    with TestClient(create_app(settings, scripted)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/api/runs").status_code == 401
        assert (
            client.get("/v1/models", headers={"Authorization": "Bearer test-only"}).status_code
            == 200
        )


def test_chat_validation_and_unknown_model(settings, scripted):
    with TestClient(create_app(settings, scripted)) as client:
        result = client.post("/v1/chat/completions", json=body(settings)).json()
        assert result["choices"][0]["message"]["content"] == "negative"
        assert result["usage"]["total_tokens"] == 14
        assert (
            client.post("/v1/chat/completions", json=body(settings, max_tokens=0)).status_code
            == 422
        )
        assert client.post("/v1/chat/completions", json=body(settings, tools=[])).status_code == 422
        assert (
            client.post("/v1/chat/completions", json=body(settings, model="unknown")).status_code
            == 404
        )


async def test_real_openai_sdk_nonstream_and_stream(settings, scripted):
    app = create_app(settings, scripted)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as http:
        async with AsyncOpenAI(
            base_url="http://medinfer/v1", api_key="unused", http_client=http
        ) as sdk:
            messages = [{"role": "user", "content": "synthetic"}]
            result = await sdk.chat.completions.create(model=settings.model, messages=messages)
            assert result.choices[0].message.content == "negative"
            stream = await sdk.chat.completions.create(
                model=settings.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            text, tokens = "", None
            async for chunk in stream:
                if chunk.choices:
                    text += chunk.choices[0].delta.content or ""
                if chunk.usage:
                    tokens = chunk.usage.completion_tokens
            assert text == "negative" and tokens == 4


async def test_benchmark_job_poll_and_exports(settings, scripted):
    app = create_app(settings, scripted)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post("/api/benchmarks", json={"limit": 3, "warmup": 0})
            assert response.status_code == 202
            assert (await c.post("/api/benchmarks", json={})).status_code == 409
            run_id = response.json()["id"]
            for _ in range(100):
                result = await c.get(f"/api/runs/{run_id}")
                if result.status_code == 200 and result.json()["status"] != "running":
                    break
                await asyncio.sleep(0.01)
            run = result.json()
            assert run["summary"]["successful"] == 3
            assert (await c.get(f"/api/runs/{run_id}/export?format=csv")).text == csv_export(run)
            assert (await c.get(f"/api/runs/{run_id}/export")).json() == run
            assert (await c.get(f"/api/runs/{run_id}/export?format=bad")).status_code == 422
            assert (await c.get("/api/runs/missing")).status_code == 404


def test_failed_stream_and_nonstream_release_lock(settings, scripted):
    scripted.fail = True
    with TestClient(create_app(settings, scripted)) as client:
        assert client.post("/v1/chat/completions", json=body(settings)).status_code == 502
        stream = client.post("/v1/chat/completions", json=body(settings, stream=True))
        assert '"error"' in stream.text and "[DONE]" in stream.text
        scripted.fail = False
        assert client.post("/v1/chat/completions", json=body(settings)).status_code == 200
