import json
from pathlib import Path

import pytest

from concord_mcp.backends import InProcessBackend
from concord_mcp.config import Config
from inprocesskit import build_bible_db, build_embeddings_db, fake_encoder

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fixture():
    def load(name: str) -> dict:
        return json.loads((FIXTURES / f"{name}.json").read_text())

    return load


@pytest.fixture(scope="session")
def synthetic_data(tmp_path_factory):
    """Synthetic bible.db + embeddings.db mirroring the S1 fixtures (built once)."""
    base = tmp_path_factory.mktemp("concord-data")
    bible_db = build_bible_db(base)
    semantic = base / "semantic"
    build_embeddings_db(semantic)
    return {"bible_db": bible_db, "semantic": semantic}


@pytest.fixture
def inprocess_backend(synthetic_data):
    config = Config(
        backend="inprocess",
        bible_db_path=synthetic_data["bible_db"],
        semantic_assets=synthetic_data["semantic"],
    )
    return InProcessBackend(config, encoder=fake_encoder)
