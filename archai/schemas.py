"""JSON schemas and shared constants for the pipeline stages."""

PASS = "PASS"
FAIL = "FAIL"
MISSING_METRIC = "MISSING_METRIC"
CANNOT_CHECK = "CANNOT_CHECK"
STATUSES = (PASS, FAIL, MISSING_METRIC, CANNOT_CHECK)

OPERATORS = ("<=", ">=", "<", ">", "=", "range")

RULE_SCHEMA = {
    "type": "object",
    "required": ["id", "article", "text", "metric", "operator"],
    "properties": {
        "id": {"type": "string"},
        "article": {"type": "string"},
        "article_title": {"type": "string"},
        "clause": {"type": ["string", "null"]},
        "text": {"type": "string"},
        "concept": {"type": ["string", "null"]},
        "zone": {"type": ["string", "null"]},
        "metric": {"type": ["string", "null"]},
        "operator": {"type": ["string", "null"]},
        "value": {"type": ["number", "null"]},
        "value_max": {"type": ["number", "null"]},
        "unit": {"type": ["string", "null"]},
    },
}

RULE_GRAPH_SCHEMA = {
    "type": "object",
    "required": ["regulation", "rules"],
    "properties": {
        "regulation": {"type": "object"},
        "rules": {"type": "array", "items": RULE_SCHEMA},
    },
}
