"""Deterministic diagnostic scores. None of these is a clinical safety score."""

import json
import re


def answer_only(text: str) -> str:
    # Some R1 templates put the opening <think> in the prompt, outside the output.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    elif "<think>" in text:
        return ""  # reasoning-only/truncated output is not an answer
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def normalize(value) -> str:
    return " ".join(str(value).casefold().split())


def leaves(obj, prefix="") -> set[tuple[str, str]]:
    if isinstance(obj, dict):
        return set().union(*(leaves(v, f"{prefix}.{k}") for k, v in obj.items())) if obj else set()
    if isinstance(obj, list):
        return set().union(*(leaves(v, prefix) for v in obj)) if obj else {(prefix, "[]")}
    return {(prefix, json.dumps(obj).casefold() if not isinstance(obj, str) else normalize(obj))}


def extraction_score(text, reference):
    try:
        obj = json.loads(answer_only(text))
    except (json.JSONDecodeError, TypeError):
        return {"json_valid": 0, "schema_valid": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    if not isinstance(obj, dict):
        return {"json_valid": 1, "schema_valid": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    pred, gold = leaves(obj), leaves(reference)
    tp = len(pred & gold)
    precision, recall = tp / len(pred) if pred else 0.0, tp / len(gold) if gold else 0.0
    schema = set(obj) == set(reference) and all(
        type(obj[k]) is type(v)
        and (not isinstance(v, list) or all(isinstance(x, str) for x in obj[k]))
        for k, v in reference.items()
    )
    schema = (
        schema
        and ("sex" not in reference or obj.get("sex") in ("male", "female"))
        and (
            "blood_culture_status" not in reference
            or obj.get("blood_culture_status") in ("positive", "negative", "unknown", "not_ordered")
        )
    )
    return {
        "json_valid": 1,
        "schema_valid": int(schema),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if tp else 0.0,
    }


def score(case, output):
    text = answer_only(output)
    if case["task"] == "extraction":
        return extraction_score(output, case["reference"])
    if case["task"] == "qa":
        return {"exact_match": int(normalize(text) in {normalize(x) for x in case["answers"]})}
    normalized = normalize(text)
    groups = case["key_facts"]
    covered = sum(any(normalize(alias) in normalized for alias in group) for group in groups)
    headings = case["headings"]
    return {
        "key_fact_coverage_proxy": covered / len(groups),
        "structure_coverage": sum(normalize(h) in normalized for h in headings) / len(headings),
        "forbidden_phrase_hits": sum(normalize(x) in normalized for x in case["forbidden"]),
    }
