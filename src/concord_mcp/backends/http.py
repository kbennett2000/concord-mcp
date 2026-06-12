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

    async def cross_references(
        self, reference: str, include_text: bool = False, limit: int = 10
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if include_text:
            params["include_text"] = True
            params["translation"] = self._config.default_translation
        response = await self._get(
            f"/v1/cross-references/{quote(reference, safe='')}", params
        )
        return self._payload_or_raise(response)

    async def word_study(self, reference: str) -> dict[str, Any]:
        # No text param: Concord picks the tagged text by the reference's testament.
        response = await self._get(f"/v1/verses/{quote(reference, safe='')}/words", {})
        return self._payload_or_raise(response)

    async def strongs_entry(self, strongs_id: str) -> dict[str, Any]:
        response = await self._get(f"/v1/strongs/{quote(strongs_id, safe='')}", {})
        return self._payload_or_raise(response)

    async def strongs_verses(self, strongs_id: str, limit: int = 10) -> dict[str, Any]:
        response = await self._get(
            f"/v1/strongs/{quote(strongs_id, safe='')}/verses",
            {"limit": limit, "translation": self._config.default_translation},
        )
        return self._payload_or_raise(response)

    async def list_topics(self, query: str, limit: int = 10) -> dict[str, Any]:
        response = await self._get("/v1/topics", {"q": query, "limit": limit})
        return self._payload_or_raise(response)

    async def get_topic(self, topic_id: str) -> dict[str, Any]:
        response = await self._get(f"/v1/topics/{quote(topic_id, safe='')}", {})
        return self._payload_or_raise(response)

    async def topic_verses(
        self, topic_id: str, include_text: bool = True, limit: int = 10
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "include_text": include_text}
        if include_text:
            params["translation"] = self._config.default_translation
        response = await self._get(
            f"/v1/topics/{quote(topic_id, safe='')}/verses", params
        )
        return self._payload_or_raise(response)

    async def search_keyword(
        self, query: str, translations: list[str] | None = None, limit: int = 10
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"q": query, "limit": limit}
        if translations:
            params["translations"] = ",".join(translations)
        else:
            params["translation"] = self._config.default_translation
        response = await self._get("/v1/search", params)
        return self._payload_or_raise(response)

    async def translations(self) -> dict[str, Any]:
        response = await self._get("/v1/translations", {})
        return self._payload_or_raise(response)

    async def books(self) -> dict[str, Any]:
        response = await self._get("/v1/books", {})
        return self._payload_or_raise(response)

    async def places_for_passage(self, reference: str) -> dict[str, Any]:
        response = await self._get(f"/v1/verses/{quote(reference, safe='')}/places", {})
        return self._payload_or_raise(response)

    async def list_journeys(self) -> dict[str, Any]:
        response = await self._get("/v1/journeys", {})
        return self._payload_or_raise(response)

    async def journey_detail(self, journey_id: str) -> dict[str, Any]:
        response = await self._get(f"/v1/journeys/{quote(journey_id, safe='')}", {})
        return self._payload_or_raise(response)

    async def random_verse(
        self,
        book: str | None = None,
        testament: str | None = None,
        translation: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "translation": translation or self._config.default_translation
        }
        if book:
            params["book"] = book
        if testament:
            params["testament"] = testament
        response = await self._get("/v1/random", params)
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
