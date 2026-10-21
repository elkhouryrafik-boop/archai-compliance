"""Optional OpenAI helper. Nothing runs at import time; the key comes from the environment only.

Contract: the reply is parsed as JSON and validated against a schema. On a validation error the
error text is fed back and the call is retried (max ``retries``). Each attempt is judged by the
API's ``finish_reason`` (``stop`` = complete; anything else is a failed attempt), never by reply text.
"""

from __future__ import annotations

import json
import os
from typing import Any

import jsonschema

DEFAULT_MODEL = "gpt-4o-mini"


class LLMError(RuntimeError):
    pass


def get_client() -> Any:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LLMError("OPENAI_API_KEY is not set (see .env.example)")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise LLMError("Install the 'llm' extra: pip install -e .[llm]") from exc
    return OpenAI(api_key=key)


def model_name() -> str:
    return os.environ.get("ARCHAI_OPENAI_MODEL") or DEFAULT_MODEL


def structured_call(
    system: str, user: str, schema: dict[str, Any], *, client: Any = None, retries: int = 2
) -> dict[str, Any]:
    """Return schema-valid JSON from the model or raise ``LLMError``."""
    client = client or get_client()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_error = "no attempt made"
    for _ in range(retries + 1):
        resp = client.chat.completions.create(
            model=model_name(), messages=messages, response_format={"type": "json_object"}
        )
        choice = resp.choices[0]
        content = choice.message.content or ""
        if choice.finish_reason != "stop":
            last_error = f"finish_reason={choice.finish_reason}"
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": f"Previous reply was incomplete ({last_error}). "
                    "Return the complete JSON object only.",
                },
            ]
            continue
        try:
            data = json.loads(content)
            jsonschema.validate(data, schema)
            return data
        except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
            last_error = str(exc).splitlines()[0]
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": f"Output failed validation: {last_error}. Return corrected JSON only.",
                },
            ]
    raise LLMError(f"No valid output after {retries + 1} attempts: {last_error}")


_EXTRACT_SYSTEM = (
    "You extract machine-checkable rules from urban-regulation text. Reply with one JSON object "
    '{"regulation": {"title": str}, "rules": [...]}. Each rule has: id, article, article_title, '
    "clause, text (verbatim quote), concept, zone, metric (one of height_m, floors, far, "
    "site_coverage_pct, front_setback_m, side_setback_m, plot_area_m2, or null), operator "
    "(<=, >=, <, >, = or null), value, value_max, unit. Use null when a clause is not numeric."
)


def extract_with_llm(source: Any, *, client: Any = None) -> dict[str, Any]:
    """Optional LLM extractor for unstructured regulations (schema-validated, retried)."""
    from archai.extract.deterministic import read_text
    from archai.schemas import RULE_GRAPH_SCHEMA

    data = structured_call(_EXTRACT_SYSTEM, read_text(source), RULE_GRAPH_SCHEMA, client=client)
    data["regulation"].setdefault("source", source.name)
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    return data
