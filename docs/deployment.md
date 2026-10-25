# Deployment

## Install

Python 3.11–3.13 passed the GitHub Actions test matrix; the local validated environment uses Python 3.12. Use the committed `uv.lock` with [uv](https://docs.astral.sh/uv/) for a frozen dependency set:

```bash
uv sync --locked --extra dev
uv run medinfer --backend mock serve
```

Open `http://127.0.0.1:8000`. Mock is clearly labelled simulated and reports no token counts. To use pip for the lightweight gateway: `python -m pip install --require-hashes --only-binary=:all: -r requirements.lock`, then `python -m pip install --no-deps -e .`. Install dev tools with `requirements-dev.lock`. Project flags (`--backend`, `--model`, `--db`, `--base-url`, `--revision`) go **before** the subcommand. `--help` lists all options. Environment variables in `.env.example` must be exported explicitly; the CLI does not automatically read that file.

## Apple Silicon / MLX

```bash
uv sync --locked --extra dev --extra mlx
uv run medinfer --backend mlx \
  --revision 933185be1b8f81d9a21dcfa15ff73470d3545240 doctor
uv run medinfer --backend mlx \
  --revision 933185be1b8f81d9a21dcfa15ff73470d3545240 serve
```

The default is `mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit`, a community MLX quantization of the DeepSeek distill model. The small model is a runnable baseline, not a medical specialist. The first request downloads weights and includes loading unless warmed up. Set `HF_HOME` to choose the cache directory. Standard model code only; no `trust_remote_code=True`.

For a larger experiment, select a compatible 7B MLX quantization with `--model`, inspect the model card/config and pin its snapshot. Memory depends on context length, KV cache and runtime; size alone is not a sufficient fit guarantee. Do not run MLX inside the Linux Docker image: Metal runs natively on macOS.

## Apple Silicon / Ollama

Install [Ollama from its official distribution](https://ollama.com/download), start its service, then:

```bash
ollama pull deepseek-r1:1.5b
uv run medinfer --backend ollama doctor
uv run medinfer --backend ollama serve
# Larger local option, downloaded only when explicitly chosen:
ollama pull deepseek-r1:7b
uv run medinfer --backend ollama --model deepseek-r1:7b serve
```

MedInfer uses native `/api/chat` NDJSON to preserve provider token counts and timing metadata. Record the actual Ollama model digest (`ollama show` / `/api/tags`), quantization and Ollama version with exported evidence; tags can change. Live Ollama validation is listed separately from protocol fixtures.

## NVIDIA / vLLM

Use an NVIDIA Linux host with the driver and container toolkit required by the selected vLLM image. The project implements an HTTP client; it does not install or emulate a GPU scheduler. The [official vLLM Docker guide](https://docs.vllm.ai/en/latest/deployment/docker/) and [OpenAI-compatible server documentation](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/) are the reference.

Choose a tested official release image and set `VLLM_IMAGE` to a **digest-pinned** `vllm/vllm-openai@sha256:...` value. A universal image digest is not invented here. On the GPU host:

```bash
export VLLM_IMAGE='vllm/vllm-openai@sha256:REPLACE_WITH_VERIFIED_DIGEST'
# Supply private keys through the host environment; do not commit them.
docker run --rm --gpus all --ipc=host \
  -p 127.0.0.1:8001:8000 \
  -e VLLM_API_KEY -e HF_HOME=/models/hf \
  -v medinfer-models:/models \
  "$VLLM_IMAGE" \
  --model deepseek-ai/DeepSeek-R1-Distill-Qwen-7B \
  --max-model-len 4096 --gpu-memory-utilization 0.85 \
  --reasoning-parser deepseek_r1

export MEDINFER_UPSTREAM_API_KEY="$VLLM_API_KEY"
uv run medinfer --backend vllm --base-url http://127.0.0.1:8001 doctor
uv run medinfer --backend vllm benchmark --concurrency 4 --repetitions 3 \
  --max-tokens 2048 --gpu-index 0 --output results/vllm-7b-c4.json
```

Confirm the chosen vLLM release supports the reasoning parser and model. Pin the model revision in the upstream launch command for an actual run. Use the exact served model ID in MedInfer. `--revision` on MedInfer is provenance metadata for HTTP backends; it cannot force the remote model revision. Do not claim it does. A 7B BF16 model has roughly 14 GB of weight storage before runtime/KV overhead; 24 GB may fit short contexts, but admission capacity must be tested. 14B and 32B need separate memory planning; no 32B-on-24GB promise is made.

For access from a Mac, keep the GPU endpoint loopback-bound and forward it with SSH: `ssh -L 8001:127.0.0.1:8001 user@gpu-host`. Then use the local forwarded endpoint. Remote GPU memory remains `null` when the benchmark client runs on the Mac.

## Gateway Docker

```bash
export MEDINFER_API_KEY='choose-a-private-key'
docker compose up --build
```

The compose default is **mock**, explicitly labelled. Set `MEDINFER_BACKEND=ollama` and `MEDINFER_MODEL=deepseek-r1:1.5b` to reach a host Ollama at `host.docker.internal:11434`; host service binding/firewall must permit container access. For vLLM set its URL and served ID. Docker is a Linux gateway/client container, not a way to run MLX Metal. Named volume `results` preserves SQLite data. Enter the gateway key in the dashboard; it stays in page memory. Keep a single worker and one process per results database.

## Cloud cost decision

No cloud resources are provisioned by this repository. The first useful purchase is a short **7B vLLM verification session**, after local work passes; 14B/32B comparisons can wait. On 2026-10-25, [Runpod's public pricing page](https://www.runpod.io/pricing) listed L40S 48 GB at $1.09/hour and A100 PCIe 80 GB at $1.79/hour. Availability, region and storage change the actual bill. A planning envelope of 4–8 hours on those listed GPU rates gives approximately **$4.36–$14.32 for GPU time**, plus storage, downloads/setup and any taxes. This is an estimate, not money spent or a guaranteed quote. Set a provider-side budget and terminate the rented instance and billable storage when finished. No purchase has been made for the current local deliverable.
