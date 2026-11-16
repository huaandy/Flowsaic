"""Embedding helper tests. Gemini is always faked here: no real API calls."""

from types import SimpleNamespace

import pytest
from google.genai import errors

from app.embeddings import (
    RETRY_WAITS,
    chunk_content,
    document_prompt,
    embed_texts,
    query_prompt,
)
from app.models import EMBEDDING_DIM


def api_error(code: int, status: str) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "status": status, "message": "test"}})


class FakeClient:
    """Stands in for genai.Client. Each call pops the next outcome: an error or a vector count."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.models = SimpleNamespace(embed_content=self.embed_content)

    def embed_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        count, dimensions = outcome
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.0] * dimensions) for _ in range(count)]
        )


def test_text_formats():
    assert chunk_content("CSCI 3103", "Data Structures", "Lists and trees.") == (
        "CSCI 3103 Data Structures: Lists and trees."
    )
    assert document_prompt("CSCI 3103", "Data Structures", "Lists and trees.") == (
        "title: CSCI 3103 Data Structures | text: Lists and trees."
    )
    assert query_prompt("intro to programming") == "task: search result | query: intro to programming"


def test_each_text_is_sent_as_its_own_content_and_768_dims_are_requested():
    client = FakeClient([(2, EMBEDDING_DIM)])
    vectors = embed_texts(client, ["first", "second"])

    assert len(vectors) == 2
    call = client.calls[0]
    # One Content per text. A plain list of strings would be merged into one embedding.
    assert [content.parts[0].text for content in call["contents"]] == ["first", "second"]
    assert call["config"].output_dimensionality == EMBEDDING_DIM


def test_retries_on_rate_limit_then_succeeds():
    client = FakeClient([api_error(429, "RESOURCE_EXHAUSTED"), (1, EMBEDDING_DIM)])
    waits = []
    vectors = embed_texts(client, ["text"], sleep=waits.append, log=lambda message: None)

    assert len(vectors) == 1
    assert len(client.calls) == 2
    assert waits == [15]


def test_gives_up_after_the_last_retry():
    tries = len(RETRY_WAITS) + 1  # the first call plus one per retry
    client = FakeClient([api_error(429, "RESOURCE_EXHAUSTED")] * tries)
    with pytest.raises(errors.APIError):
        embed_texts(client, ["text"], sleep=lambda seconds: None, log=lambda message: None)
    assert len(client.calls) == tries


def test_does_not_retry_when_the_daily_quota_is_used_up():
    # Shape of the real free-tier error: waiting a minute cannot fix a per-day limit.
    daily = errors.APIError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "test",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [
                            {"quotaId": "EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier"}
                        ],
                    }
                ],
            }
        },
    )
    client = FakeClient([daily])
    waits = []
    with pytest.raises(errors.APIError):
        embed_texts(client, ["text"], sleep=waits.append, log=lambda message: None)
    assert len(client.calls) == 1
    assert waits == []


def test_does_not_retry_other_errors():
    client = FakeClient([api_error(400, "INVALID_ARGUMENT")])
    with pytest.raises(errors.APIError):
        embed_texts(client, ["text"], sleep=lambda seconds: None)
    assert len(client.calls) == 1


def test_rejects_a_merged_response():
    # Two texts in, one embedding out means the texts were merged: never store that.
    client = FakeClient([(1, EMBEDDING_DIM)])
    with pytest.raises(RuntimeError, match="got 1 embeddings"):
        embed_texts(client, ["first", "second"])


def test_rejects_wrong_dimensions():
    client = FakeClient([(1, 3072)])
    with pytest.raises(RuntimeError, match="expected 768"):
        embed_texts(client, ["text"])
