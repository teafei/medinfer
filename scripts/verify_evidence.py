"""Recalculate published metrics and task scores from the committed raw records."""

import json
import math
from pathlib import Path

from medinfer.benchmark.dataset import dataset_hash, load_cases
from medinfer.benchmark.metrics import aggregate
from medinfer.benchmark.scoring import score


def compare(actual, expected):
    if isinstance(expected, dict):
        for key, value in expected.items():
            compare(actual[key], value)
    elif isinstance(expected, (int, float)):
        assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), (actual, expected)
    else:
        assert actual == expected, (actual, expected)


def main():
    cases = {case["id"]: case for case in load_cases()}
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "evidence").glob("mlx-*.json"))
    assert files, "no real model evidence found"
    for path in files:
        run = json.loads(path.read_text())
        assert run["status"] == "completed" and not run["config"]["simulated"]
        assert run["config"]["dataset_sha256"] == dataset_hash()
        assert len({r["sequence"] for r in run["records"]}) == len(run["records"])
        for record in run["records"]:
            if record["error"] is None:
                compare(record["scores"], score(cases[record["case_id"]], record["output"]))
        compare(run["summary"], aggregate(run["records"], run["summary"]["wall_s"]))
        print(f"Verified {path.name}: {len(run['records'])} raw requests and all derived metrics")


if __name__ == "__main__":
    main()
