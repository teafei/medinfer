import argparse
import asyncio
import json
import os
from pathlib import Path

from medinfer.backends import create_backend
from medinfer.benchmark.engine import BenchmarkRunner
from medinfer.benchmark.storage import Store
from medinfer.config import Settings
from medinfer.schemas import BenchmarkRequest


def main():
    parser = argparse.ArgumentParser(description="MedInfer inference and synthetic workload lab")
    parser.add_argument("--backend", choices=["ollama", "mlx", "vllm", "mock"])
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--db")
    parser.add_argument("--revision")
    subs = parser.add_subparsers(dest="command", required=True)
    serve = subs.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    bench = subs.add_parser("benchmark")
    bench.add_argument("--concurrency", type=int, default=1)
    bench.add_argument("--repetitions", type=int, default=1)
    bench.add_argument("--limit", type=int)
    bench.add_argument("--max-tokens", type=int, default=1024)
    bench.add_argument("--warmup", type=int, default=1)
    bench.add_argument("--task", choices=["all", "extraction", "qa", "summary"], default="all")
    bench.add_argument("--timeout-s", type=float, default=180)
    bench.add_argument("--gpu-index", type=int)
    bench.add_argument("--output", type=Path)
    subs.add_parser("doctor")
    subs.add_parser("runs")
    export = subs.add_parser("export")
    export.add_argument("run_id")
    export.add_argument("--format", choices=["json", "csv"], default="json")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for attr, key in (
        ("backend", "BACKEND"),
        ("model", "MODEL"),
        ("base_url", "BASE_URL"),
        ("db", "DB"),
        ("revision", "MODEL_REVISION"),
    ):
        value = getattr(args, attr)
        if value is not None:
            os.environ["MEDINFER_" + key] = value
    settings = Settings.from_env()
    if args.command == "serve":
        import uvicorn

        from medinfer.api import create_app

        if args.host not in ("127.0.0.1", "localhost", "::1") and not settings.api_key:
            parser.error("set MEDINFER_API_KEY before binding to a network interface")
        uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1)
        return
    store = Store(settings.db)
    if args.command == "runs":
        print(json.dumps(store.list(), indent=2))
        return
    if args.command == "export":
        from medinfer.api import csv_export

        run = store.get(args.run_id)
        if run is None:
            parser.error("run not found")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            csv_export(run) if args.format == "csv" else json.dumps(run, indent=2)
        )
        return

    async def execute():
        backend = create_backend(settings)
        try:
            if args.command == "doctor":
                result = await backend.health()
                print(json.dumps(result, indent=2))
                return 0 if result["ready"] else 1
            options = BenchmarkRequest(
                **{k: getattr(args, k) for k in BenchmarkRequest.model_fields}
            )
            run = await BenchmarkRunner(backend, store).run(options)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(run, indent=2))
            print(
                json.dumps(
                    {"id": run["id"], "status": run["status"], "summary": run["summary"]}, indent=2
                )
            )
            return 1 if run["summary"]["failed"] else 0
        finally:
            await backend.close()

    try:
        raise SystemExit(asyncio.run(execute()))
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"MedInfer: {exc}\n")


if __name__ == "__main__":
    main()
