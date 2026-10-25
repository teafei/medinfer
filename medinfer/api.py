import asyncio
import contextlib
import csv
import hmac
import io
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from medinfer.backends import create_backend
from medinfer.backends.base import BackendError
from medinfer.benchmark.engine import BenchmarkRunner, measure
from medinfer.benchmark.storage import Store
from medinfer.config import Settings
from medinfer.schemas import BenchmarkRequest, ChatRequest

DASHBOARD = Path(__file__).parent / "dashboard"


def usage(result):
    p, c = result["prompt_tokens"], result["completion_tokens"]
    return (
        {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}
        if (p is not None and c is not None)
        else None
    )


def csv_export(run):
    buf = io.StringIO(newline="")
    fields = [
        "sequence",
        "case_id",
        "task",
        "repetition",
        "latency_s",
        "queue_s",
        "end_to_end_s",
        "ttft_s",
        "completion_tokens",
        "tokens_s",
        "finish_reason",
        "error",
        "scores",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in run["records"]:
        writer.writerow({**record, "scores": json.dumps(record["scores"], sort_keys=True)})
    return buf.getvalue()


def create_app(settings=None, backend=None):
    settings = settings or Settings.from_env()
    backend = backend or create_backend(settings)
    store = Store(settings.db)
    work_lock = asyncio.Lock()
    jobs = set()

    @asynccontextmanager
    async def lifespan(app):
        store.interrupt_stale()
        yield
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        await backend.close()

    app = FastAPI(title="MedInfer", version="0.1.0", lifespan=lifespan)
    app.state.backend, app.state.store = backend, store

    @app.middleware("http")
    async def safe_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        if request.url.path in ("/docs", "/redoc"):
            del response.headers["Content-Security-Policy"]
        return response

    async def auth(authorization: str | None = Header(default=None)):
        if settings.api_key and not hmac.compare_digest(
            authorization or "", f"Bearer {settings.api_key}"
        ):
            raise HTTPException(401, "API key required")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(DASHBOARD / "index.html")

    app.mount("/static", StaticFiles(directory=DASHBOARD), name="static")

    @app.get("/health")
    async def health():
        # Liveness is public; model details/readiness require the API key.
        return {"status": "ok", "service": "medinfer"}

    @app.get("/api/status", dependencies=[Depends(auth)])
    async def status():
        return {**await backend.health(), "busy": work_lock.locked()}

    @app.get("/v1/models", dependencies=[Depends(auth)])
    async def models():
        return {
            "object": "list",
            "data": [
                {
                    "id": settings.model,
                    "object": "model",
                    "created": 0,
                    "owned_by": settings.backend,
                }
            ],
        }

    @app.post("/v1/chat/completions", dependencies=[Depends(auth)])
    async def chat(request: ChatRequest):
        if request.model != settings.model:
            raise HTTPException(404, "model is not configured; see /v1/models")
        if work_lock.locked():
            raise HTTPException(409, "another chat or benchmark is active")
        await work_lock.acquire()
        completion_id, created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
        base = {"id": completion_id, "created": created, "model": request.model}
        if not request.stream:
            try:
                result = await measure(backend, request, settings.timeout_s)
                message = {"role": "assistant", "content": result["output"]}
                if result["reasoning"]:
                    message["reasoning_content"] = result["reasoning"]
                return {
                    **base,
                    "object": "chat.completion",
                    "choices": [
                        {"index": 0, "message": message, "finish_reason": result["finish_reason"]}
                    ],
                    "usage": usage(result),
                    "medinfer_metrics": {
                        k: v for k, v in result.items() if k not in ("output", "reasoning")
                    },
                    "simulated": settings.backend == "mock",
                }
            except (BackendError, TimeoutError) as exc:
                raise HTTPException(
                    504 if isinstance(exc, TimeoutError) else 502,
                    "inference timed out" if isinstance(exc, TimeoutError) else str(exc),
                ) from exc
            finally:
                work_lock.release()

        async def stream_response():
            queue = asyncio.Queue()

            async def sink(event):
                await queue.put(("event", event))

            async def producer():
                try:
                    result = await measure(backend, request, settings.timeout_s, sink=sink)
                    await queue.put(("result", result))
                except Exception:
                    await queue.put(("error", "inference stream failed or timed out"))

            def encode(value):
                return "data: " + json.dumps(value) + "\n\n"

            task = asyncio.create_task(producer())
            try:
                yield encode(
                    {
                        **base,
                        "object": "chat.completion.chunk",
                        "choices": [
                            {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
                        ],
                    }
                )
                while True:
                    kind, value = await queue.get()
                    if kind == "error":
                        yield encode({"error": {"message": value, "type": "backend_error"}})
                        break
                    if kind == "result":
                        yield encode(
                            {
                                **base,
                                "object": "chat.completion.chunk",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": value["finish_reason"],
                                    }
                                ],
                            }
                        )
                        if (request.stream_options or {}).get("include_usage"):
                            yield encode(
                                {
                                    **base,
                                    "object": "chat.completion.chunk",
                                    "choices": [],
                                    "usage": usage(value),
                                }
                            )
                        break
                    delta = {}
                    if value.text:
                        delta["content"] = value.text
                    if value.reasoning:
                        delta["reasoning_content"] = value.reasoning
                    if delta:
                        yield encode(
                            {
                                **base,
                                "object": "chat.completion.chunk",
                                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                            }
                        )
                yield "data: [DONE]\n\n"
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                work_lock.release()

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/benchmarks", status_code=202, dependencies=[Depends(auth)])
    async def benchmark(options: BenchmarkRequest):
        if work_lock.locked():
            raise HTTPException(409, "another chat or benchmark is active")
        await work_lock.acquire()
        run_id = str(uuid.uuid4())

        async def execute():
            try:
                await BenchmarkRunner(backend, store).run(options, run_id)
            except Exception:
                pass  # Runner persists failure state; no raw prompts or upstream errors in logs.
            finally:
                work_lock.release()

        job = asyncio.create_task(execute())
        jobs.add(job)
        job.add_done_callback(jobs.discard)
        return {"id": run_id, "status": "accepted"}

    @app.get("/api/runs", dependencies=[Depends(auth)])
    async def runs():
        return store.list()

    @app.get("/api/runs/{run_id}", dependencies=[Depends(auth)])
    async def run(run_id: str):
        result = store.get(run_id)
        if not result:
            raise HTTPException(404, "run not found")
        return result

    @app.get("/api/runs/{run_id}/export", dependencies=[Depends(auth)])
    async def export(run_id: str, format: str = "json"):
        result = store.get(run_id)
        if not result:
            raise HTTPException(404, "run not found")
        if format == "csv":
            return Response(
                csv_export(result),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{result["id"]}.csv"'},
            )
        if format != "json":
            raise HTTPException(422, "format must be json or csv")
        return JSONResponse(result)

    return app
