import pytest

from medinfer.backends.reasoning import ThinkSplitter
from medinfer.benchmark.dataset import load_cases
from medinfer.benchmark.scoring import extraction_score


@pytest.mark.parametrize("size", [1, 2, 3, 7, 50])
def test_think_tags_split_across_chunks(size):
    splitter = ThinkSplitter()
    source = "<think>reasoning only</think>final answer"
    output, reasoning = "", ""
    for index in range(0, len(source), size):
        a, b = splitter.feed(source[index : index + size], final=index + size >= len(source))
        output += a
        reasoning += b
    assert output == "final answer" and reasoning == "reasoning only"


def test_implicit_think_and_truncation():
    splitter = ThinkSplitter(thinking=True)
    assert splitter.feed("Presentation: 68 findings", final=True) == (
        "",
        "Presentation: 68 findings",
    )
    splitter = ThinkSplitter(thinking=True)
    assert splitter.feed("reasoning</think>answer", final=True) == ("answer", "reasoning")


def test_extraction_enum_rejected():
    import json

    reference = load_cases("extraction")[0]["reference"]
    wrong = {**reference, "blood_culture_status": "unknown/not_ordered"}
    assert extraction_score(json.dumps(wrong), reference)["schema_valid"] == 0
