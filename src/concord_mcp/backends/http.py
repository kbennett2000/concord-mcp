"""HttpBackend — a thin httpx client over a reachable Concord (ADR 0002)."""

from typing import Any
from urllib.parse import quote

import anyio
import httpx

from concord_mcp.backends.base import ApiError, ConcordBusy, ConcordUnreachable
from concord_mcp.config import Config

# When a 503 arrives without a Retry-After header.
DEFAULT_RETRY_AFTER_S = 5.0


class HttpBackend:
    def __init__(self, config: Config):
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.concord_url, timeout=config.timeout_s
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_verses(
        self, reference: str, translations: list[str] | None = None
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if translations:
            params["translations"] = ",".join(translations)
        response = await self._get(f"/v1/verses/{quote(reference, safe='')}", params)
        return self._payload_or_raise(response)

    async def semantic_search(
        self,
        query: str,
        translation: str | None = None,
        limit: int = 10,
        min_score: float | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "q": query,
            "limit": limit,
            # Sent explicitly even when the caller omits it: the endpoint's own
            # default is WEB, not our configured default (SPEC §7).
            "translation": translation or self._config.default_translation,
        }
        if min_score is not None:
            params["min_score"] = min_score

        response = await self._get("/v1/semantic-search", params)
        if response.status_code == 503:
            # One polite retry (SPEC §8) — never more.
            retry_after = _retry_after_seconds(response)
            await anyio.sleep(min(retry_after, self._config.timeout_s))
            response = await self._get("/v1/semantic-search", params)
            if response.status_code == 503:
                raise ConcordBusy(_retry_after_seconds(response))
        return self._payload_or_raise(response)

    async def _get(self, path: str, params: dict[str, Any]) -> httpx.Response:
        try:
            return await self._client.get(path, params=params)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise ConcordUnreachable(self._config.concord_url) from None

    def _payload_or_raise(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_success:
            return response.json()
        try:
            envelope = response.json().get("error", {})
        except ValueError:
            envelope = {}
        raise ApiError(
            status=response.status_code,
            code=envelope.get("code", "unknown_error"),
            message=envelope.get("message", response.text),
            detail=envelope.get("detail"),
        )


def _retry_after_seconds(response: httpx.Response) -> float:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return DEFAULT_RETRY_AFTER_S
