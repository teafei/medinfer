# MedInfer

**Private Medical LLM Inference & Benchmark Platform**
An inspectable personal engineering lab for clinical text workloads.

[中文说明](README_CN.md) · [Architecture](docs/architecture.md) · [Deploy](docs/deployment.md) · [Benchmark protocol](docs/benchmark.md) · [Validation](docs/validation.md)

![Live MLX dashboard with measured results](assets/dashboard.jpg)

Run a small DeepSeek-R1-Distill model on Apple Silicon, expose a common chat API, and keep the evidence behind every performance and task-quality number. The project owns the adapters and evaluation pipeline; model execution uses MLX-LM, Ollama or vLLM. It does not implement DeepInfer, distributed prefill/decode, or a new inference kernel.

## What is verified

| Capability | Implementation | Execution evidence |
|---|---|---|
| Apple Silicon / MLX | Dedicated worker, incremental R1 reasoning split, pinned model snapshot | **Real model run** on Apple M5 / 16 GB |
| Ollama | Native NDJSON chat adapter, usage and error handling | Protocol fixtures; live Ollama not run |
| NVIDIA / vLLM | OpenAI SSE adapter, usage-only chunks, GPU deployment guide | Protocol fixtures; cloud GPU not run |
| FastAPI chat API | Text chat subset, streaming, usage, API-key option | OpenAI SDK tests and real HTTP → MLX smoke |
| Medical workload suite | 12 synthetic vignettes × extraction / passage QA / summary | 36 requests per real run |
| Load measurement | TTFT, tokens/s, P50/P95, request throughput, concurrency | Real c1 and c4 runs; scripts for c1/4/8/16 |
| Resources | Gateway RSS, MLX Metal peak; optional local NVIDIA device sampling | RSS/Metal measured; NVIDIA unavailable |
| Persistence / dashboard | SQLite, per-request outputs, compare charts, JSON/CSV | Tests and browser flow exercised |
| Automated checks | 37 tests, Ruff, locked dependencies, installable wheel | Local Python 3.12 and GitHub Ubuntu Python 3.11 / 3.12 / 3.13 passed |
| Docker / GitHub Actions | Non-root image, compose, CPU test matrix, Docker smoke job | [All four remote jobs passed](https://github.com/teafei/medinfer/actions/runs/40207616589); image build, startup and authenticated models endpoint verified |

This is an engineering evaluation tool, not a clinical decision system. All bundled records are original synthetic text. No real patient data, credentials or model weights are committed. Public repository: [teafei/medinfer](https://github.com/teafei/medinfer). [Publication and validation status](docs/publishing.md) are recorded explicitly.

## Quick start

Use Python 3.12 and [uv](https://docs.astral.sh/uv/), then run from the repository directory:

```bash
uv sync --locked --extra dev
uv run medinfer --backend mock serve
```

Open **http://127.0.0.1:8000**. Mock mode is visibly marked simulated, never invents token counts, and is suitable for exploring the UI without a model download.

For actual Apple Silicon inference:

```bash
uv sync --locked --extra dev --extra mlx
uv run medinfer --backend mlx \
  --revision 933185be1b8f81d9a21dcfa15ff73470d3545240 serve
```

The default MLX model is `mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit`, a small community quantization that actually ran on the validation machine. Larger models are selected explicitly. The first request downloads/loads weights. See [deployment](docs/deployment.md) for Ollama, 7B options, vLLM, Docker and cache configuration.

```bash
# Standalone benchmark; stop the server or use a separate --db first.
uv run medinfer --backend mlx \
  --revision 933185be1b8f81d9a21dcfa15ff73470d3545240 \
  benchmark --concurrency 1 --max-tokens 1024 --warmup 1 \
  --output results/mlx-c1.json

# A bounded software smoke test without model dependencies:
uv run medinfer --backend mock benchmark --concurrency 4 --limit 6 --warmup 0
```

Project flags go before the subcommand. Changing the configured backend/model and restarting switches the runtime; v0.1 serves one configured model at a time. Run history persists across switches.

## Actual local measurements

2026-10-25 · Apple M5 · 16 GB unified memory · macOS 27.0.1 · MLX 0.32.4 / MLX-LM 0.32.2 · model snapshot `933185be1b8f81d9a21dcfa15ff73470d3545240`. Each run uses the same 36 tasks, temperature 0, seed 42, one excluded warmup and **1,024 maximum generated tokens**.

| Client concurrency | Successful | TTFT P50 | Latency P50 | Latency P95 | Output tokens / wall s | Length-limited |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 36 / 36 | 0.106 s | 4.623 s | 8.139 s | 97.87 | 2 |
| 4 | 36 / 36 | 15.166 s | 20.442 s | 27.871 s | 87.38 | 2 |

These are **single-run diagnostic observations**, not a production capacity estimate or a controlled cross-hardware comparison. MLX generation is serialized: c4 adds backend queueing, which is included in TTFT and latency. It did not improve throughput in this run. Completion counts include reasoning. Token throughput is counted across run wall time, not pure GPU decode speed. Both runs produced 16,125 provider-counted completion tokens. Gateway RSS sampled peaks were 1.327 / 1.265 GB; MLX runtime Metal peak was 1.263 GB in both runs. RSS and Metal allocation have different scopes and must not be summed.

**Quality results are retained even when poor:** extraction macro leaf F1 **0.690**, schema validity **75%**, strict passage QA exact match **1/12**, and summary lexical fact coverage proxy **0.583**. Two summaries exhausted the budget in reasoning and received zero answer coverage. Strict QA output-format failures are not equivalent to medical knowledge errors. The suite is tiny, shares vignettes across tasks, and cannot establish clinical competence or safety.

![Measured latency comparison and task diagnostics](assets/comparison.jpg)

[c1 raw evidence](evidence/mlx-m5-c1.json) · [c4 raw evidence](evidence/mlx-m5-c4.json) · [c1 CSV](evidence/mlx-m5-c1.csv) · [c4 CSV](evidence/mlx-m5-c4.csv)

```bash
# Recompute every published summary statistic and task score from raw records:
uv run python scripts/verify_evidence.py
```

The [protocol](docs/benchmark.md) defines timing, failure denominators, missing usage, memory scope, warmup, truncation and scoring limitations. No cloud/7B/14B/32B result is presented as measured.

## API

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="local-unused")
model = client.models.list().data[0].id
stream = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Explain unknown versus negative culture."}],
    stream=True,
    stream_options={"include_usage": True},
    max_tokens=512,
)
for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="")
```

Supported: text messages, model, stream, `stream_options.include_usage`, max_tokens, temperature, top_p, seed. Unknown parameters fail validation. Tools, images, embeddings and the Responses API are outside this chat subset. The dashboard can start experiments, inspect request outputs and export evidence. Network binding requires `MEDINFER_API_KEY`; the default is loopback only.

## Layout and checks

```text
medinfer/
  api.py, cli.py, config.py, schemas.py
  backends/        # MLX / Ollama / vLLM / explicitly simulated mock
  benchmark/       # streaming observer, scoring, resources, SQLite
  datasets/        # original synthetic-v1.jsonl
  dashboard/       # local assets, no JS build service or CDN
tests/             # SDK, streaming, concurrency, failures, scoring, persistence
evidence/          # actual raw runs and derived CSV files
assets/            # screenshots from the running app
docs/              # methods, deployment, scope, résumé and demo materials
scripts/           # concurrency sweep, evidence verification, publication helper
.github/workflows/ # CPU matrix + Docker smoke configuration
```

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

[20-day roadmap](docs/20-day-plan.md) · [Interview guide](docs/interview-guide.md) · [Résumé wording](docs/resume.md) · [Demo script](docs/demo-script.md) · [Third-party decisions](docs/third-party-reuse.md)

MIT license for MedInfer code and original synthetic fixtures. Runtime and model licenses remain their own. Built with AI assistance; scope and actual validation are documented for review.
