import json
from collections.abc import AsyncIterator

import httpx

from medinfer.backends.base import Backend, BackendError, Event


async def sse_payloads(lines) -> AsyncIterator[str]:
    """SSE framing allows comments, CRLF and multiple data lines per event."""
    data = []
    async for line in lines:
        if not line:
            if data:
                yield "\n".join(data)
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield "\n".join(data)


class HTTPBackend(Backend):
    def __init__(self, settings, transport=None):
        super().__init__(settings)
        headers = {}
        if settings.upstream_api_key:
            headers["Authorization"] = f"Bearer {settings.upstream_api_key}"
        self.client = httpx.AsyncClient(
            base_url=settings.base_url,
            headers=headers,
            timeout=settings.timeout_s,
            transport=transport,
            trust_env=False,
        )

    async def health(self):
        try:
            path = "/api/tags" if self.settings.backend == "ollama" else "/v1/models"
            res = await self.client.get(path)
            res.raise_for_status()
            data = res.json()
            models = (
                [x.get("name") for x in data.get("models", [])]
                if path == "/api/tags"
                else [x.get("id") for x in data.get("data", [])]
            )
            return {
                "ready": self.settings.model in models,
                "available_models": models,
                **self.metadata(),
            }
        except (httpx.HTTPError, ValueError):
            return {"ready": False, "error": "upstream unavailable", **self.metadata()}

    async def stream(self, request):
        is_ollama = self.settings.backend == "ollama"
        if is_ollama:
            options = {
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
            }
            if request.seed is not None:
                options["seed"] = request.seed
            body = {
                "model": request.model,
                "messages": [m.model_dump() for m in request.messages],
                "stream": True,
                "options": options,
            }
            path = "/api/chat"
        else:
            body = request.model_dump(exclude_none=True)
            body.update(stream=True, stream_options={"include_usage": True})
            path = "/v1/chat/completions"
        finished = False
        try:
            async with self.client.stream("POST", path, json=body) as response:
                if response.status_code >= 400:
                    raise BackendError(f"upstream HTTP {response.status_code}")
                lines = response.aiter_lines()
                if is_ollama:
                    async for line in lines:
                        if not line.strip():
                            continue
                        obj = json.loads(line)
                        if "error" in obj:
                            raise BackendError("upstream generation error")
                        msg = obj.get("message", {})
                        done = obj.get("done", False)
                        finished |= done
                        yield Event(
                            text=msg.get("content", ""),
                            reasoning=msg.get("thinking", ""),
                            prompt_tokens=obj.get("prompt_eval_count"),
                            completion_tokens=obj.get("eval_count"),
                            finish_reason=obj.get("done_reason", "stop") if done else None,
                            extra={"provider_eval_duration_ns": obj.get("eval_duration")},
                        )
                else:
                    async for payload in sse_payloads(lines):
                        if payload == "[DONE]":
                            break
                        obj = json.loads(payload)
                        if "error" in obj:
                            raise BackendError("upstream generation error")
                        usage = obj.get("usage") or {}
                        choices = obj.get("choices") or []
                        choice = choices[0] if choices else {}
                        delta = choice.get("delta", {})
                        reason = choice.get("finish_reason")
                        finished |= reason is not None
                        yield Event(
                            text=delta.get("content") or "",
                            reasoning=delta.get("reasoning_content") or "",
                            finish_reason=reason,
                            prompt_tokens=usage.get("prompt_tokens"),
                            completion_tokens=usage.get("completion_tokens"),
                        )
            if not finished:
                raise BackendError("upstream stream ended without completion marker")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise BackendError("upstream connection or stream protocol failure") from exc

    async def close(self):
        await self.client.aclose()
