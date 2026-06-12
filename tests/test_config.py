from pathlib import Path

import pytest

from concord_mcp.config import Config


def test_defaults_with_empty_env():
    cfg = Config.from_env({})
    assert cfg.backend == "http"
    assert cfg.concord_url == "http://localhost:8000"
    assert cfg.default_translation == "KJV"
    assert cfg.timeout_s == 10.0
    assert cfg.max_results == 25
    assert cfg.bible_db_path == Path("data/concord/bible.db")
    assert cfg.semantic_assets == Path("data/concord/semantic")


def test_env_overrides():
    cfg = Config.from_env(
        {
            "CONCORD_URL": "http://concord.lan:8000",
            "CONCORD_MCP_DEFAULT_TRANSLATION": "WEB",
            "CONCORD_MCP_TIMEOUT_S": "3.5",
            "CONCORD_MCP_MAX_RESULTS": "5",
            "BIBLE_DB_PATH": "/srv/concord/bible.db",
            "CONCORD_SEMANTIC_ASSETS": "/srv/concord/semantic",
        }
    )
    assert cfg.concord_url == "http://concord.lan:8000"
    assert cfg.default_translation == "WEB"
    assert cfg.timeout_s == 3.5
    assert cfg.max_results == 5
    assert cfg.bible_db_path == Path("/srv/concord/bible.db")
    assert cfg.semantic_assets == Path("/srv/concord/semantic")


def test_inprocess_backend_is_accepted():
    assert Config.from_env({"CONCORD_MCP_BACKEND": "inprocess"}).backend == "inprocess"


def test_unknown_backend_rejected():
    with pytest.raises(ValueError, match="CONCORD_MCP_BACKEND"):
        Config.from_env({"CONCORD_MCP_BACKEND": "carrier-pigeon"})
