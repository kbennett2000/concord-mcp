"""Real-artifact in-process smoke (local only, never CI).

Runs only under `uv run pytest -m integration` and only when `make get-db`
has populated the default data/concord/ paths. Uses the real embedding
model — first call loads ~313 MB of weights.
"""

from pathlib import Path

import pytest

from concord_mcp.backends import InProcessBackend
from concord_mcp.config import Config

DB = Path("data/concord/bible.db")
ASSETS = Path("data/concord/semantic")

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not (DB.is_file() and (ASSETS / "embeddings.db").is_file()),
        reason="run `make get-db` first (data/concord/ is empty)",
    ),
]


@pytest.fixture
def real_backend():
    return InProcessBackend(Config(backend="inprocess"))


async def test_real_lookup(real_backend):
    payload = await real_backend.get_verses("John 3:16", ["KJV"])
    assert payload["verses"][0]["reference"] == "John 3:16"
    assert "loved the world" in payload["verses"][0]["text"]["KJV"]


async def test_real_semantic_search(real_backend):
    payload = await real_backend.semantic_search("do not be anxious", limit=5)
    assert payload["count"] == 5
    assert all(-1.0 <= hit["score"] <= 1.0 for hit in payload["results"])
    assert all(hit["text"] for hit in payload["results"])
