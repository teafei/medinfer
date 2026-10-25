import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    backend: str = "ollama"
    model: str = "deepseek-r1:1.5b"
    base_url: str = "http://127.0.0.1:11434"
    db: str = "results/medinfer.sqlite3"
    api_key: str | None = None
    upstream_api_key: str | None = None
    model_revision: str | None = None
    timeout_s: float = 180

    @classmethod
    def from_env(cls):
        backend = os.getenv("MEDINFER_BACKEND", "ollama")
        defaults = {
            "ollama": ("deepseek-r1:1.5b", "http://127.0.0.1:11434"),
            "mlx": ("mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit", ""),
            "vllm": ("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "http://127.0.0.1:8001"),
            "mock": ("mock-synthetic", ""),
        }
        if backend not in defaults:
            raise ValueError(f"unknown backend: {backend}")
        model, url = defaults[backend]
        return cls(
            backend=backend,
            model=os.getenv("MEDINFER_MODEL", model),
            base_url=os.getenv("MEDINFER_BASE_URL", url).rstrip("/"),
            db=os.getenv("MEDINFER_DB", "results/medinfer.sqlite3"),
            api_key=os.getenv("MEDINFER_API_KEY") or None,
            upstream_api_key=os.getenv("MEDINFER_UPSTREAM_API_KEY") or None,
            model_revision=os.getenv("MEDINFER_MODEL_REVISION") or None,
        )

    def ensure_db_parent(self):
        Path(self.db).expanduser().parent.mkdir(parents=True, exist_ok=True)
