"""The backend contract: Concord's documented /v1 response shapes (ADR 0002).

Both backends return the plain dicts documented in Concord's docs/API.md, so
the rendering layer and the fixtures speak one language. The in-process
backend (slice 2) adapts to these same shapes.
"""

from typing import Any, Protocol


class BackendError(Exception):
    """Base for everything a backend can raise; tools render these per SPEC §8."""


class ApiError(BackendError):
    """A 4xx/422 from Concord, carrying its error envelope verbatim."""

    def __init__(self, status: int, code: str, message: str, detail: Any = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail


class ConcordUnreachable(BackendError):
    """Concord didn't answer at all (http mode)."""

    def __init__(self, url: str):
        super().__init__(f"Concord isn't reachable at {url}.")
        self.url = url


class ConcordBusy(BackendError):
    """Concord shed load (503) and the one polite retry didn't help."""

    def __init__(self, retry_after: float):
        super().__init__(f"Concord is busy; retry in {retry_after:g}s.")
        self.retry_after = retry_after


class ConcordBackend(Protocol):
    async def get_verses(
        self, reference: str, translations: list[str] | None = None
    ) -> dict[str, Any]:
        """Return the parallel-format shape of GET /v1/verses/{ref}."""
        ...

    async def semantic_search(
        self,
        query: str,
        translation: str | None = None,
        limit: int = 10,
        min_score: float | None = None,
    ) -> dict[str, Any]:
        """Return the shape of GET /v1/semantic-search."""
        ...
