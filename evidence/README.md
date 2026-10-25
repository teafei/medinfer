# Evidence

- `mlx-m5-c1.json`, `mlx-m5-c4.json`: two real complete 36-request runs of the fixed synthetic suite. JSON is the primary evidence; CSV is a derived table and omits bulky generated text.
- `hardware.json`: non-identifying system/runtime metadata. No hostname or username is collected.
- `live-api-smoke.json`: real OpenAI Python SDK → local FastAPI → MLX calls, separate from workload benchmark timing.
- `SHA256SUMS`: integrity hashes of evidence files and screenshots, generated after final export.

Run `python scripts/verify_evidence.py` in the installed environment to recalculate scores/statistics. Timing values are observations; recalculation checks arithmetic and consistency, not independent remeasurement. Original synthetic prompts/references are versioned in `medinfer/datasets/synthetic-v1.jsonl`, identified by the run's SHA256.

No mock-run numbers are presented as model performance. No real clinical records are included. Reasoning and answers in these files are model-generated text for fictional vignettes and may be wrong.
