# Benchmark protocol

## Dataset and task meaning

`medinfer/datasets/synthetic-v1.jsonl` contains **12 original synthetic vignettes × 3 task types = 36 cases**. No hospital exports or real patient records were used. The same vignette is reused across tasks: these are correlated engineering test cases, not 36 independent patients. The English suite tests passage comprehension and output discipline; it is not a clinical knowledge exam or a validated medical benchmark.

- Extraction: age, sex, affirmed diagnoses/symptoms and blood-culture status. The four culture states `positive`, `negative`, `unknown`, `not_ordered` remain distinct. JSON parsing, expected-key/type/enum validity, and exact normalized leaf-set precision/recall/F1 are reported. F1 is macro-averaged across successful requests. Empty lists have their own leaf value; unknown is never converted to negative. Synonyms not in the reference are penalized by this deliberately strict lexical score.
- QA: shortest answer using only the passage; case-insensitive whitespace-normalized exact match against fixed aliases. Explanatory prose can fail despite a semantically correct answer. References are not expanded after seeing model answers.
- Summary: lexical coverage of fixed fact groups, heading coverage and exact forbidden-phrase hits. These are **proxies**, not general hallucination detection, clinical factuality or a safety score. A negated forbidden phrase may still match; an unlisted hallucination may be missed. Human review is required for any clinical interpretation.

The runner hashes the exact dataset bytes. The model sees the prompt, never reference labels. Mock output is fixed and deliberately imperfect; mock does not consult references.

## Timing definitions

| Field | Definition |
|---|---|
| `latency_s` | Admission to final stream exhaustion, including backend queues, network and stream-tail processing |
| `queue_s` | Time waiting for the benchmark admission semaphore |
| `end_to_end_s` | Task enqueue to completion; includes admission wait and persistence overhead |
| `ttft_s` | Admission to first nonempty text **or reasoning** chunk; not empty role/usage metadata |
| `first_content_s` | Admission to first answer-content chunk; MLX R1 reasoning is separated incrementally |
| `tokens_s` | Per-request provider completion tokens / (stream completion − first nonempty output); a client-observed rate, not pure kernel decode speed |
| `output_tokens_s` | Sum of successful provider completion tokens / timed run wall seconds, including scheduling/persistence overhead |
| `throughput_requests_s` | Successful requests / timed run wall seconds |
| `latency_p50_s`, `latency_p95_s` | Linear-interpolated percentiles of successful request latencies |

Reasoning and any runtime-counted special tokens are included in provider completion counts. SSE chunks are not tokens. Counts are never estimated from characters/words. Aggregate token throughput is `null` if any successful request lacks counts; coverage is reported separately. Warmup uses the same first-case prompt and token budget and is excluded from timing, quality and resource sampling. A warmup failure fails the run.

P50/P95 exclude failures and must be read alongside error rate and sample count. Length-limited responses count as successful inference requests and remain in quality scoring, often with empty/invalid answers. Truncation count is explicit. An all-failure experiment has no latency percentiles or quality averages. `completed` means the experiment finished; it does not imply that every request succeeded or that answers were correct.

## Resources and reproducibility

Gateway RSS is sampled every 50 ms: it includes the in-process MLX runtime but **does not measure a separate Ollama/vLLM process**. MLX's per-request `extra.mlx_metal_peak_gb` is runtime-reported Metal allocation peak in decimal GB, not total unified-memory usage. These scopes cannot be directly compared.

`--gpu-index 0` optionally samples local `nvidia-smi` whole-device used MiB roughly every 0.5 s. It does not isolate one model, and a remote GPU is unavailable to a client on another host. Run the benchmark client on the GPU host for this measurement, and ensure other GPU workloads are idle. The dashboard shows RSS scope; detailed JSON preserves all resource metadata.

Each run records model ID/revision (and resolved MLX snapshot), backend, parameters, concurrency, repetitions, dataset hash, OS, Python, RAM and installed library versions. Seeds do not guarantee bitwise determinism across runtimes. Record GPU model/driver, vLLM image digest, quantization, KV-cache settings and upstream launch command alongside cloud evidence. The harness does not reset provider prefix caches; repetitions and warmed prefixes can change results.

## Reproduce

```bash
uv sync --locked --extra dev --extra mlx
uv run medinfer --backend mlx \
  --revision 933185be1b8f81d9a21dcfa15ff73470d3545240 \
  benchmark --concurrency 1 --max-tokens 1024 --warmup 1 \
  --output results/mlx-c1.json

# Same workload under several concurrent client loads:
MEDINFER_BACKEND=vllm MEDINFER_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B \
  sh scripts/concurrency_sweep.sh

medinfer export RUN_ID --format csv --output results/run.csv
```

MLX serializes model execution: higher concurrency measures queueing under load, not GPU parallel inference. vLLM may batch upstream. A closed-loop semaphore test is not a production arrival-rate simulation; it can underestimate tail latency under overload. For published comparisons use multiple independent runs, longer workloads, representative distributions, an explicit cache policy and uncertainty estimates. Thirty-six cases cannot establish a stable production P95 or medical superiority.

Temperature 0 and seed 42 define this diagnostic profile. DeepSeek's model guidance may recommend different generation settings. A diagnostic score under this profile must not be advertised as an optimal model capability result.

See `evidence/` and `validation.md` for what was actually run. Only finalized measurements belong in the README; mock and contract tests do not establish GPU performance.
