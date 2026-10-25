from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["system", "user", "assistant"]
    content: str = Field(max_length=100_000)


class ChatRequest(BaseModel):
    """Supported OpenAI chat subset. Unknown parameters fail rather than silently disappear."""

    model_config = ConfigDict(extra="forbid")
    model: str
    messages: list[Message] = Field(min_length=1, max_length=64)
    stream: bool = False
    stream_options: dict[str, bool] | None = None
    max_tokens: int = Field(default=512, ge=1, le=8192)
    temperature: float = Field(default=0.0, ge=0, le=2)
    top_p: float = Field(default=1.0, gt=0, le=1)
    seed: int | None = None

    @model_validator(mode="after")
    def bounded_input(self):
        if sum(len(m.content) for m in self.messages) > 100_000:
            raise ValueError("total message size exceeds 100000 characters")
        if self.stream_options and set(self.stream_options) - {"include_usage"}:
            raise ValueError("only stream_options.include_usage is supported")
        return self


class BenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concurrency: int = Field(default=1, ge=1, le=32)
    repetitions: int = Field(default=1, ge=1, le=20)
    limit: int | None = Field(default=None, ge=1, le=36)
    max_tokens: int = Field(default=1024, ge=8, le=4096)
    warmup: int = Field(default=1, ge=0, le=5)
    task: Literal["all", "extraction", "qa", "summary"] = "all"
    timeout_s: float = Field(default=180, gt=0, le=1800)
    gpu_index: int | None = Field(default=None, ge=0, le=15)
