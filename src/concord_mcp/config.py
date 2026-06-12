"""Configuration from environment variables (SPEC §7).

Every setting has a default; nothing is required for `http` mode against a
local Concord.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONCORD_URL = "http://localhost:8000"
DEFAULT_TRANSLATION = "KJV"
DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_RESULTS = 25
# Defaults match the `make get-db` output paths (ADR 0004); relative paths
# resolve against the working directory (the repo root under `uv --directory`).
DEFAULT_BIBLE_DB_PATH = Path("data/concord/bible.db")
DEFAULT_SEMANTIC_ASSETS = Path("data/concord/semantic")


@dataclass(frozen=True)
class Config:
    backend: str = "http"
    concord_url: str = DEFAULT_CONCORD_URL
    default_translation: str = DEFAULT_TRANSLATION
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_results: int = DEFAULT_MAX_RESULTS
    bible_db_path: Path = DEFAULT_BIBLE_DB_PATH
    semantic_assets: Path = DEFAULT_SEMANTIC_ASSETS

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        if env is None:
            env = os.environ
        backend = env.get("CONCORD_MCP_BACKEND", "http")
        if backend not in ("http", "inprocess"):
            raise ValueError(
                f"CONCORD_MCP_BACKEND must be 'http' or 'inprocess', got {backend!r}."
            )
        return cls(
            backend=backend,
            concord_url=env.get("CONCORD_URL", DEFAULT_CONCORD_URL),
            default_translation=env.get(
                "CONCORD_MCP_DEFAULT_TRANSLATION", DEFAULT_TRANSLATION
            ),
            timeout_s=float(env.get("CONCORD_MCP_TIMEOUT_S", DEFAULT_TIMEOUT_S)),
            max_results=int(env.get("CONCORD_MCP_MAX_RESULTS", DEFAULT_MAX_RESULTS)),
            bible_db_path=Path(env.get("BIBLE_DB_PATH", DEFAULT_BIBLE_DB_PATH)),
            semantic_assets=Path(
                env.get("CONCORD_SEMANTIC_ASSETS", DEFAULT_SEMANTIC_ASSETS)
            ),
        )
