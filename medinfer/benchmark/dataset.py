import hashlib
import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "synthetic-v1.jsonl"


def load_cases(task="all", limit=None):
    cases = [json.loads(line) for line in DATASET_PATH.read_text().splitlines() if line.strip()]
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)) or not all(c.get("synthetic") is True for c in cases):
        raise ValueError("dataset must have unique IDs and explicit synthetic provenance")
    if task != "all":
        cases = [c for c in cases if c["task"] == task]
    return cases[:limit] if limit else cases


def dataset_hash():
    return hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
