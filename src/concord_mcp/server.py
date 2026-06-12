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
from concord_mcp.render import (
    render_cross_references,
    render_semantic,
    render_strongs,
    render_topic_candidates,
    render_topic_verses,
    render_verses,
    render_word_study,
    topic_zero_match,
)

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
    " 'Genesis 1:1-5', 'Psalm 23', 'Romans 3:23,25'. Pass translations to"
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
    " phrase match, use search_keyword. For classic study subjects with a"
    " curated index entry ('faith', 'prayer'), topic_verses returns an"
    " editor's chosen verses rather than a similarity ranking."
)

CROSS_REFERENCES_DESCRIPTION = (
    "List the passages traditionally linked to a verse or passage — the"
    " places Scripture echoes Scripture. Use after lookup_verse when the"
    " question is 'what other passages relate to this one?' — e.g. reference"
    " 'John 3:16' or 'Genesis 1:1-5'. Results are ranked by how strongly"
    " readers have linked them (votes, shown per line). Set include_text"
    " true to fetch each linked passage's opening verse text in the server's"
    " default translation. Returns up to limit links (default 10, max 25)"
    " plus the true total. Each target is tagged 'Book Chapter:Verse' so you"
    " can lookup_verse it."
)

WORD_STUDY_DESCRIPTION = (
    "Show the original-language words behind a verse or short passage —"
    " Greek for the New Testament, Hebrew for the Old, chosen automatically."
    " Use when the question is about wording, nuance, or 'what does this"
    " word really mean?' — e.g. 'John 21:15-17' to see the two different"
    " Greek words for 'love'. Each word line carries its position, surface"
    " form, lemma, transliteration, Strong's id, morphology code, and a"
    " short gloss; follow a Strong's id with strongs_entry for the full"
    " definition. Verse blocks inside a range are labeled where possible."
    " Keep references short — a verse or a few; output is capped at 10"
    " verses of words."
)

STRONGS_ENTRY_DESCRIPTION = (
    "Look up a Strong's lexicon entry — lemma, transliteration, gloss, and"
    " full definition — by its id: 'G26' (Greek ἀγάπη), 'H7225' (Hebrew"
    " רֵאשִׁית). Formats like 'g26' or 'G0026' are accepted. Use after"
    " word_study surfaces an id, or whenever a Strong's number appears. Set"
    " include_verses true to also list where the word occurs (up to limit,"
    " default 10, max 25, with the true total), each verse tagged so you can"
    " lookup_verse it. For the words of a specific verse, use word_study"
    " with the reference instead."
)

TOPIC_VERSES_DESCRIPTION = (
    "Look up a subject in Nave's Topical Bible — a curated index compiled by"
    " a human editor — and return its verses, e.g. topic 'faith', 'care',"
    " 'prayer'. Use this for 'what does the Bible say about X?' when X is a"
    " classic study subject; it returns the editor's chosen verses, not a"
    " similarity search. (For ideas or phrasings that aren't index entries —"
    " 'feeling overwhelmed at work' — use search_by_meaning.) If several"
    " index entries match, you get the candidate list — call again with one"
    " of the listed ids. 'See X' redirects are followed and labeled. Returns"
    " up to limit verses (default 10, max 25) with the true total, tagged"
    " 'Book Chapter:Verse (TRANSLATION)'."
)

REFERENCE_HINT = (
    "Expected a reference like 'John 3:16', 'Genesis 1:1-5', or 'Psalm 23'."
)
SEARCH_HINT = "Check the parameters: limit must be 1-25 and min_score between -1 and 1."
STRONGS_HINT = (
    "Strong's ids look like 'G26' (Greek) or 'H7225' (Hebrew) — get them"
    " from word_study."
)
TOPIC_HINT = (
    "Nave's indexes classic study subjects; for ideas in your own words,"
    " use search_by_meaning."
)


def _pick_topic(wanted: str, candidates: list[dict]) -> dict | None:
    """The exact id or name match among the search hits, if any."""
    folded = wanted.casefold()
    for topic in candidates:
        if topic["id"] == folded or topic["name"].casefold() == folded:
            return topic
    return None


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
                    " ('Genesis 1:1-5'), same-chapter list ('Romans 3:23,25'),"
                    " or whole chapter ('Psalm 23')."
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

    @mcp.tool(annotations=READ_ONLY, description=CROSS_REFERENCES_DESCRIPTION)
    async def cross_references(
        reference: Annotated[
            str,
            Field(
                description=("The source passage, e.g. 'John 3:16' or 'Genesis 1:1-5'.")
            ),
        ],
        include_text: Annotated[
            bool,
            Field(
                description=(
                    "Fetch each linked passage's opening verse text in the"
                    " server's default translation. Default false."
                )
            ),
        ] = False,
        limit: Annotated[
            int,
            Field(description="Maximum links to return. Default 10, capped at 25."),
        ] = 10,
    ) -> str:
        limit = max(1, min(limit, config.max_results))
        try:
            payload = await backend.cross_references(
                reference, include_text=include_text, limit=limit
            )
        except BackendError as exc:
            return render_error(exc, REFERENCE_HINT)
        return render_cross_references(payload)

    @mcp.tool(annotations=READ_ONLY, description=WORD_STUDY_DESCRIPTION)
    async def word_study(
        reference: Annotated[
            str,
            Field(
                description=(
                    "A verse or short passage, e.g. 'John 21:15-17' or"
                    " 'Genesis 1:1'. Output is capped at 10 verses of words."
                )
            ),
        ],
    ) -> str:
        try:
            payload = await backend.word_study(reference)
        except BackendError as exc:
            return render_error(exc, REFERENCE_HINT)
        return render_word_study(payload, reference)

    @mcp.tool(annotations=READ_ONLY, description=STRONGS_ENTRY_DESCRIPTION)
    async def strongs_entry(
        strongs_id: Annotated[
            str,
            Field(
                description=(
                    "A Strong's number, e.g. 'G26' (Greek) or 'H7225'"
                    " (Hebrew); 'g26' and 'G0026' also work."
                )
            ),
        ],
        include_verses: Annotated[
            bool,
            Field(
                description=(
                    "Also list the verses where this word occurs. Default false."
                )
            ),
        ] = False,
        limit: Annotated[
            int,
            Field(
                description=(
                    "Maximum occurrence verses (with include_verses)."
                    " Default 10, capped at 25."
                )
            ),
        ] = 10,
    ) -> str:
        limit = max(1, min(limit, config.max_results))
        try:
            entry = await backend.strongs_entry(strongs_id)
            verses = (
                await backend.strongs_verses(strongs_id, limit=limit)
                if include_verses
                else None
            )
        except BackendError as exc:
            return render_error(exc, STRONGS_HINT)
        return render_strongs(entry, verses)

    @mcp.tool(annotations=READ_ONLY, description=TOPIC_VERSES_DESCRIPTION)
    async def topic_verses(
        topic: Annotated[
            str,
            Field(
                description=(
                    "A Nave's subject name or id, e.g. 'faith', 'care'."
                    " Ambiguous names return a candidate list of ids."
                )
            ),
        ],
        include_text: Annotated[
            bool,
            Field(
                description=(
                    "Include each verse's text in the server's default"
                    " translation. Default true."
                )
            ),
        ] = True,
        limit: Annotated[
            int,
            Field(description="Maximum verses to return. Default 10, capped at 25."),
        ] = 10,
    ) -> str:
        limit = max(1, min(limit, config.max_results))
        wanted = topic.strip()
        try:
            listing = await backend.list_topics(wanted, limit=10)
            chosen = _pick_topic(wanted, listing["topics"])
            if chosen is None:
                if listing["total"] == 0:
                    return topic_zero_match(wanted)
                if len(listing["topics"]) > 1:
                    return render_topic_candidates(wanted, listing)
                chosen = listing["topics"][0]

            redirect_note = None
            if chosen["see_also"]:
                target = await backend.get_topic(chosen["see_also"])
                redirect_note = (
                    f'Nave\'s lists "{chosen["name"]}" as "See {target["name"]}"'
                    f" — showing {target['name']}."
                )
                if target["see_also"]:
                    # A redirect chain: stop after one hop, never loop.
                    return (
                        f'Nave\'s lists "{chosen["name"]}" as "See'
                        f' {target["name"]}", which itself redirects to'
                        f" '{target['see_also']}' — call topic_verses with"
                        f" '{target['see_also']}'."
                    )
                chosen = target

            payload = await backend.topic_verses(
                chosen["id"], include_text=include_text, limit=limit
            )
        except BackendError as exc:
            return render_error(exc, TOPIC_HINT)
        return render_topic_verses(payload, chosen["name"], redirect_note)

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
