import json

import pytest

from medinfer.benchmark.dataset import dataset_hash, load_cases
from medinfer.benchmark.scoring import answer_only, extraction_score, score


def test_dataset_provenance_and_balance():
    cases = load_cases()
    assert len(cases) == 36 and len({c["id"] for c in cases}) == 36
    assert all(c["synthetic"] for c in cases)
    assert all(len(load_cases(t)) == 12 for t in ("extraction", "qa", "summary"))
    assert len(dataset_hash()) == 64


def test_extraction_gold_and_unknown_are_distinct():
    ref = load_cases("extraction")[2]["reference"]
    assert extraction_score(json.dumps(ref), ref)["f1"] == 1
    wrong = {**ref, "blood_culture_status": "negative"}
    assert extraction_score(json.dumps(wrong), ref)["f1"] < 1


@pytest.mark.parametrize("output", ["", "not json", "<think>unfinished", "null", "[]"])
def test_bad_json_does_not_crash(output):
    assert extraction_score(output, {"age": 50})["f1"] == 0


def test_hallucination_and_missing_keys_penalized():
    gold = {"age": 50, "symptoms": []}
    assert extraction_score('{"age": 50, "symptoms": [], "fever": true}', gold)["precision"] < 1
    assert extraction_score('{"age": "50", "symptoms": []}', gold)["schema_valid"] == 0
    assert extraction_score('{"age": 50}', gold)["recall"] < 1


def test_thinking_and_code_fence():
    assert answer_only('reasoning</think>```json\n{"x":1}\n```') == '{"x":1}'
    assert answer_only("<think>not done") == ""
    assert score(load_cases("qa")[0], "thinking</think>no")["exact_match"] == 1
    assert score(load_cases("qa")[0], "No, not ordered")["exact_match"] == 0


def test_summary_is_explicit_proxy():
    case = load_cases("summary")[0]
    good = "Presentation: 68. Findings: 3 months; L1 compression fracture. Unknowns: none."
    result = score(case, good)
    assert result["key_fact_coverage_proxy"] == 1
    assert result["structure_coverage"] == 1
    assert score(case, good + " positive blood culture")["forbidden_phrase_hits"] == 1
