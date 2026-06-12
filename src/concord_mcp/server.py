"""The FastMCP server: tool registration, error rendering, entry point.

Tool descriptions are product copy for the model (ADR 0003). Editing one is
a reviewed change with rationale, never a drive-by edit.
"""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from concord_mcp.backends import (
    ApiError,
    BackendError,
    ConcordBackend,
    ConcordBusy,
    ConcordUnreachable,
    HttpBackend,
    InProcessBackend,
    LocalDataMissing,
)
from concord_mcp.config import Config
from concord_mcp.render import render_semantic, render_verses

INSTRUCTIONS = (
    "Read-only Scripture tools backed by a Concord instance the operator"
    " controls. Use lookup_verse when you have a reference and"
    " search_by_meaning when you have an idea or theme. Every verse comes"
    " back tagged 'Book Chapter:Verse (TRANSLATION)' — quote and cite it"
    " exactly as returned."
)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

LOOKUP_VERSE_DESCRIPTION = (
    "Fetch the exact text of a Bible verse, verse range, verse list, or whole"
    " chapter. Use this whenever you already have a reference — 'John 3:16',"
    " 'Genesis 1:1-5', 'Psalm 23', 'Romans 3:23,6:23'. Pass translations to"
    ' compare versions side by side (e.g. ["KJV", "WEB"]; default is the'
    " server's configured translation, KJV). Returns each verse on its own"
    " line, tagged 'Book Chapter:Verse (TRANSLATION)' so you can cite it"
    " exactly. If you don't have a reference, use search_keyword for exact"
    " wording or search_by_meaning for ideas and themes."
)

SEARCH_BY_MEANING_DESCRIPTION = (
    "Find Bible verses by meaning rather than exact wording. Use this when"
    " the question is about an idea, theme, or feeling — 'verses about"
    " anxiety', 'the good shepherd', 'forgiving people who wronged you' —"
    " and you don't already have a verse reference. Results are ranked by"
    " closeness of meaning and can be returned in any loaded translation via"
    " translation (default KJV). Returns up to limit verses (default 10,"
    " max 25), each tagged with its reference and translation so you can"
    " cite it exactly. Each result carries a similarity score; set min_score"
    " (between -1 and 1) to drop weak matches. If you already know the"
    " reference, use lookup_verse instead; if you need an exact word or"
    " phrase match, use search_keyword."
)

REFERENCE_HINT = (
    "Expected a reference like 'John 3:16', 'Genesis 1:1-5', or 'Psalm 23'."
)
SEARCH_HINT = "Check the parameters: limit must be 1-25 and min_score between -1 and 1."


def render_error(exc: BackendError, hint: str) -> str:
    """SPEC §8: errors the model can self-correct from."""
    if isinstance(exc, ConcordUnreachable):
        return (
            f"Concord isn't reachable at {exc.url}. Is it running?"
            " (docker compose up in the concord folder, or check CONCORD_URL.)"
        )
    if isinstance(exc, ConcordBusy):
        return f"Concord is busy; retry in {exc.retry_after:g}s."
    if isinstance(exc, LocalDataMissing):
        return str(exc)  # already names the fixes (SPEC §8)
    if isinstance(exc, ApiError):
        if exc.code == "unknown_translation":
            return (
                f"Concord error ({exc.code}): {exc.message}"
                " Retry with a translation that is loaded, e.g. 'KJV'."
            )
        return f"Concord error ({exc.code}): {exc.message} {hint}"
    return f"Concord error: {exc}"


def create_server(config: Config, backend: ConcordBackend) -> FastMCP:
    mcp = FastMCP("concord", instructions=INSTRUCTIONS)

    @mcp.tool(annotations=READ_ONLY, description=LOOKUP_VERSE_DESCRIPTION)
    async def lookup_verse(
        reference: Annotated[
            str,
            Field(
                description=(
                    "A Scripture reference: a verse ('John 3:16'), range"
                    " ('Genesis 1:1-5'), list ('Romans 3:23,6:23'), or whole"
                    " chapter ('Psalm 23')."
                )
            ),
        ],
        translations: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Translation ids to return side by side, e.g."
                    " ['KJV', 'WEB']. Default: the server's configured"
                    " translation (KJV)."
                )
            ),
        ] = None,
    ) -> str:
        try:
            payload = await backend.get_verses(reference, translations)
        except BackendError as exc:
            return render_error(exc, REFERENCE_HINT)
        return render_verses(payload)

    @mcp.tool(annotations=READ_ONLY, description=SEARCH_BY_MEANING_DESCRIPTION)
    async def search_by_meaning(
        query: Annotated[
            str,
            Field(
                description=(
                    "The idea, theme, or feeling to search for, e.g."
                    " 'verses about anxiety'."
                )
            ),
        ],
        translation: Annotated[
            str | None,
            Field(
                description=(
                    "Translation id for the verse text, e.g. 'WEB'. Default:"
                    " the server's configured translation (KJV)."
                )
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum verses to return. Default 10, capped at 25."),
        ] = 10,
        min_score: Annotated[
            float | None,
            Field(
                description=(
                    "Similarity floor between -1 and 1; results scoring below"
                    " it are dropped. Default: no floor."
                )
            ),
        ] = None,
    ) -> str:
        limit = max(1, min(limit, config.max_results))
        try:
            payload = await backend.semantic_search(
                query, translation=translation, limit=limit, min_score=min_score
            )
        except BackendError as exc:
            return render_error(exc, SEARCH_HINT)
        return render_semantic(payload, limit)

    return mcp


def main() -> None:
    config = Config.from_env()
    backend: ConcordBackend = (
        InProcessBackend(config)
        if config.backend == "inprocess"
        else HttpBackend(config)
    )
    server = create_server(config, backend)
    server.run()
