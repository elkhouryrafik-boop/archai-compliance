"""Optional LLM path with a mocked client: schema validation, retry, finish_reason handling."""

import json
from types import SimpleNamespace

import pytest

from archai import llm
from archai.schemas import RULE_GRAPH_SCHEMA

GOOD = {
    "regulation": {"title": "T"},
    "rules": [
        {
            "id": "X-1",
            "article": "X",
            "text": "Height shall not exceed 9 m.",
            "metric": "height_m",
            "operator": "<=",
            "value": 9,
            "unit": "m",
        }
    ],
}


class FakeClient:
    """Replays scripted (content, finish_reason) replies and records the messages sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append([dict(m) for m in kw["messages"]])
        content, reason = self.replies.pop(0)
        choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=reason)
        return SimpleNamespace(choices=[choice])


def test_valid_reply_first_try():
    c = FakeClient([(json.dumps(GOOD), "stop")])
    assert llm.structured_call("s", "u", RULE_GRAPH_SCHEMA, client=c) == GOOD
    assert len(c.calls) == 1


def test_invalid_json_retried_with_error_fed_back():
    c = FakeClient([("{not json", "stop"), (json.dumps(GOOD), "stop")])
    assert llm.structured_call("s", "u", RULE_GRAPH_SCHEMA, client=c) == GOOD
    assert len(c.calls) == 2
    assert "failed validation" in c.calls[1][-1]["content"]
    assert c.calls[1][-2] == {"role": "assistant", "content": "{not json"}


def test_schema_violation_retried():
    bad = json.dumps({"regulation": {}, "rules": [{"id": "x"}]})
    c = FakeClient([(bad, "stop"), (json.dumps(GOOD), "stop")])
    assert llm.structured_call("s", "u", RULE_GRAPH_SCHEMA, client=c) == GOOD


def test_truncated_reply_judged_by_finish_reason_not_text():
    # content is valid JSON but finish_reason says it was cut off -> not accepted
    c = FakeClient([(json.dumps(GOOD), "length"), (json.dumps(GOOD), "stop")])
    llm.structured_call("s", "u", RULE_GRAPH_SCHEMA, client=c)
    assert len(c.calls) == 2 and "finish_reason=length" in c.calls[1][-1]["content"]


def test_gives_up_after_retries():
    c = FakeClient([("nope", "stop")] * 3)
    with pytest.raises(llm.LLMError):
        llm.structured_call("s", "u", RULE_GRAPH_SCHEMA, client=c, retries=2)
    assert len(c.calls) == 3


def test_retries_zero_means_single_attempt():
    c = FakeClient([("nope", "stop")])
    with pytest.raises(llm.LLMError):
        llm.structured_call("s", "u", RULE_GRAPH_SCHEMA, client=c, retries=0)
    assert len(c.calls) == 1


def test_missing_key_raises_without_network(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError, match="OPENAI_API_KEY"):
        llm.get_client()


def test_model_name_env_override(monkeypatch):
    monkeypatch.delenv("ARCHAI_OPENAI_MODEL", raising=False)
    assert llm.model_name() == "gpt-4o-mini"
    monkeypatch.setenv("ARCHAI_OPENAI_MODEL", "other-model")
    assert llm.model_name() == "other-model"


def test_extract_with_llm_fills_graph_defaults(reg_md):
    c = FakeClient([(json.dumps(GOOD), "stop")])
    g = llm.extract_with_llm(reg_md, client=c)
    assert g["regulation"]["source"] == "regulation.md"
    assert g["nodes"] == [] and g["edges"] == []
    assert g["rules"][0]["id"] == "X-1"
