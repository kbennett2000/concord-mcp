import pytest

from concord_mcp.config import Config


def test_defaults_with_empty_env():
    cfg = Config.from_env({})
    assert cfg.backend == "http"
    assert cfg.concord_url == "http://localhost:8000"
    assert cfg.default_translation == "KJV"
    assert cfg.timeout_s == 10.0
    assert cfg.max_results == 25


def test_env_overrides():
    cfg = Config.from_env(
        {
            "CONCORD_URL": "http://192.168.1.62:8000",
            "CONCORD_MCP_DEFAULT_TRANSLATION": "WEB",
            "CONCORD_MCP_TIMEOUT_S": "3.5",
            "CONCORD_MCP_MAX_RESULTS": "5",
        }
    )
    assert cfg.concord_url == "http://192.168.1.62:8000"
    assert cfg.default_translation == "WEB"
    assert cfg.timeout_s == 3.5
    assert cfg.max_results == 5


def test_inprocess_backend_not_yet_implemented():
    with pytest.raises(NotImplementedError, match="slice 2"):
        Config.from_env({"CONCORD_MCP_BACKEND": "inprocess"})


def test_unknown_backend_rejected():
    with pytest.raises(ValueError, match="CONCORD_MCP_BACKEND"):
        Config.from_env({"CONCORD_MCP_BACKEND": "carrier-pigeon"})
