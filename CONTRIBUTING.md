# Contributing

Use Python 3.12 and `uv sync --locked --extra dev`; MLX is optional. Run `ruff check .`, `ruff format --check .`, and `pytest -q` for code changes. Use only synthetic inputs in tests and examples. A new result requires raw request evidence, model/runtime provenance, dataset hash and clear metric definitions. Do not edit expected answers to improve a model's observed scores. Keep claims aligned with actual execution; a mock test cannot validate GPU deployment.

When changing metric definitions or scoring, re-run the relevant measurements or explicitly version the old evidence. Keep credentials, model weights and real clinical data out of commits. Upstream adapters should reject interrupted streams and retain missing usage as `null`.
