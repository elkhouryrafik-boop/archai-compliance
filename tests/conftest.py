from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def reg_md() -> Path:
    return ROOT / "corpus" / "dreamtown" / "regulation.md"


@pytest.fixture(scope="session")
def metrics_json() -> Path:
    return ROOT / "examples" / "metrics.sample.json"
