# Third-party decisions and provenance

Bounded discovery on 2026-10-25 compared the official MLX-LM and GuideLLM repositories. MedInfer uses published runtime packages and a small independently written orchestration/evaluation layer; it copies no source modules, repository hooks, agent instructions or installation scripts from either candidate.

| Candidate | Pinned source inspected | License | Decision |
|---|---|---|---|
| [MLX-LM](https://github.com/ml-explore/mlx-lm) | `4cfc6478473b0668ede3eb0cc93f2a9181a15052` | MIT | Use published `mlx-lm` wheel; inspect generation response/stream API and project dependency metadata; avoid reimplementing model execution |
| [GuideLLM](https://github.com/vllm-project/guidellm) | `39a02bd37e410cb3c5f47889eeb637cdad6402b0` | Apache-2.0 | Relevant serving load-test framework; not imported because this small lab needs explicit clinical task scoring, SQLite evidence and a bounded closed-loop runner; acknowledge that mature load-testing tools cover broader production load models |
| [Ollama](https://github.com/ollama/ollama) | [official API documentation](https://docs.ollama.com/api/chat) | MIT runtime | Independently written HTTP adapter; no bundled binary/model |
| [vLLM](https://github.com/vllm-project/vllm) | [official serving documentation](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/) | Apache-2.0 | Independently written OpenAI SSE client; GPU serving is delegated to the external official runtime |

The exact installed package versions/hashes are recorded in `uv.lock`; requirements exports include hashes. Third-party dependency licenses remain their own; the project MIT license does not relicense runtimes or models. The actual installed MLX-LM wheel version may differ from the inspected repository head; the installed stream API was exercised by the real local benchmark. The standard Qwen2 model config and community model file list were inspected at snapshot `933185be1b8f81d9a21dcfa15ff73470d3545240`. Weights use safetensors. Model weights are downloaded into a cache, never committed.

Reviewed execution scope: our backend adapters, official streaming shapes, model config, package metadata, wheel-based dependency installation, our own CLI/API/test paths. No candidate repository was cloned or executed, so the repository scanner was not applicable. This is a bounded provenance review, not a complete source audit of the dependency graph. `uv` was installed from its PyPI wheel; dependency installation used wheels, then built only the authored MedInfer package. Model downloading and local execution use public model assets and no supplied credentials. No secrets were searched for, extracted or embedded.

Dashboard sources were formatted with Prettier 3.6.2 (MIT), obtained from its official npm package with registry SHA512 integrity verification. It has no runtime dependencies or install hooks; formatting used explicit authored files with configuration discovery disabled. This temporary development tool is not a MedInfer runtime dependency.
