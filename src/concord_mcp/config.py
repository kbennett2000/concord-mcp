"""Configuration from environment variables (SPEC §7).

Every setting has a default; nothing is required for `http` mode against a
local Concord.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_CONCORD_URL = "http://localhost:8000"
DEFAULT_TRANSLATION = "KJV"
DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_RESULTS = 25


@dataclass(frozen=True)
class Config:
    backend: str = "http"
    concord_url: str = DEFAULT_CONCORD_URL
    default_translation: str = DEFAULT_TRANSLATION
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_results: int = DEFAULT_MAX_RESULTS

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        if env is None:
            env = os.environ
        backend = env.get("CONCORD_MCP_BACKEND", "http")
        if backend == "inprocess":
            raise NotImplementedError(
                "CONCORD_MCP_BACKEND=inprocess ships in slice 2; use http for now."
            )
        if backend != "http":
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
        )
