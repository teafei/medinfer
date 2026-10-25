# Validation record · 2026-10-25

## Actually executed

| Check | Evidence / outcome |
|---|---|
| Local code lint and formatting | Ruff passed |
| Automated tests | **37 passed** on Python 3.12.14 |
| Fresh installation without MLX | Built wheel; installed hashed core/dev dependencies into a separate fresh environment; verified imports came from installed wheel; **37 passed**, one upstream TestClient deprecation warning |
| Wheel package assets | Bundled Python modules, dashboard HTML/CSS/JS and synthetic JSONL loaded successfully |
| No-model smoke | Installed wheel ran six mock requests at concurrency 4; completion token counts and tokens/s remained `null` |
| Real MLX benchmark | `evidence/mlx-m5-c1.json`, 36 requests, c1, 0 request failures, 2 length-limited |
| Real MLX concurrency | `evidence/mlx-m5-c4.json`, 36 requests, c4, 0 request failures, 2 length-limited |
| Derived results audit | `scripts/verify_evidence.py` recalculated all summary statistics and task scores from committed raw outputs; both runs matched |
| Real OpenAI SDK over HTTP | `evidence/live-api-smoke.json`: actual MLX gateway; nonstream and stream each reported 241 completion tokens; streamed usage and finish reason parsed successfully |
| Browser workflow | Mock experiment submission, c4 execution, history, per-request details, chart rendering and playground; then displayed actual MLX c1/c4 history and captured screenshots |
| Remote GitHub Actions | [Run 2](https://github.com/teafei/medinfer/actions/runs/40207616589), commit `6831ef7a755153c35974e538867157a80715140c`: Python 3.11 / 3.12 / 3.13 each **37 passed**; Docker build/startup/authenticated models endpoint passed |
| Browser console | No application-origin errors observed; later console inspection showed unrelated Zotero browser-extension connection errors |

Hardware metadata is in `evidence/hardware.json`. The default model is community-quantized DeepSeek-R1-Distill-Qwen-1.5B, four-bit group size 64, snapshot `933185be1b8f81d9a21dcfa15ff73470d3545240`. The raw run records contain dataset hash, exact generation settings, OS/Python/dependency versions and per-request outputs/timings. The benchmark is not an isolated laboratory hardware comparison; normal desktop activity was present. Neither a stable production P95 nor clinical competence is inferred.

## Findings that constrain claims

The real c4 run did not improve throughput: MLX generation is serialized and requests queued behind the dedicated worker. Both runs generated the same counted token total under this profile. Two summaries exhausted the generation budget in reasoning; their final-answer coverage is zero. Extraction enum violations, misplaced diagnoses/symptoms and strict QA format failures remain in evidence. References were not changed to make observed results look better. `forbidden_phrase_hits=0` is not proof of factual safety.

During initial development, a three-case smoke run exposed that implicit R1 thinking could be mistaken for a summary answer, and that type-only extraction validation accepted invalid enums. Those paths were fixed and covered by regression tests **before the two published runs**. Initial smoke/interrupted development runs are excluded from published measurement evidence. The final source changes after the runs were defaults, presentation and documentation; measurement/scoring definitions used for the published runs are unchanged and the recalculation check passes.

## Not executed

- Live Ollama inference: adapter tested against protocol fixtures only.
- NVIDIA hardware, `nvidia-smi` live sampling and vLLM serving: no GPU allocated, **$0 cloud GPU spend** for this deliverable.
- 7B/14B/32B, quantization comparisons or cross-hardware model ranking: no measurements claimed.
- Local Docker/compose on macOS: Docker is absent locally. The Linux Docker image build and container smoke test passed in GitHub Actions; compose orchestration itself was not run.


The public repository is https://github.com/teafei/medinfer. Publication and remote validation status are recorded in `publishing.md`. No fabricated GPU benchmark has been added.

The first remote attempt failed before running jobs because an unquoted pip option made the workflow YAML invalid. The command now uses a YAML block scalar; the subsequent four jobs passed. Initial failure remains visible in Actions history. Remote source verification found all 68 tracked files with identical blob contents. Browser-uploaded shell scripts use regular file mode and are invoked explicitly with `sh`.
