import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fixture():
    def load(name: str) -> dict:
        return json.loads((FIXTURES / f"{name}.json").read_text())

    return load
