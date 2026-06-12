"""InProcessBackend — bible-core + bible-semantic imported directly (ADR 0002).

No Concord container: verses come straight from a read-only ``bible.db`` and
semantic search from the extracted model + vector store (ADR 0004,
``make get-db``). The methods mirror how Concord's own /v1 endpoints compose
the same libraries, so both backends speak identical dict shapes — that parity
is asserted by tests/test_parity.py.

bible-core and bible-semantic are synchronous; calls run via
``anyio.to_thread.run_sync`` so a slow ONNX inference never blocks the server's
event loop.
"""

import os
import re
import sqlite3
from collections.abc import Callable
from functools import partial
from typing import Any

import anyio.to_thread
from bible_core import queries
from bible_core.db import connect_readonly
from bible_core.parser import ParseError, Reference, UnknownBookError, parse_reference
from bible_core.resolver import SqliteBookResolver
from bible_semantic.model import embed_query
from bible_semantic.search import cosine_top_k
from bible_semantic.store import StoreError, VectorStore, load_store

from concord_mcp.backends.base import ApiError, LocalDataMissing
from concord_mcp.config import Config

# Concord's tagged original-language texts, picked by testament (words) or by
# the Strong's id's letter (occurrences) — mirrors bible_api/routers.py.
GREEK_TEXT = "SBLGNT"
HEBREW_TEXT = "OSHB"

# Concord's id normalization, copied from bible_api/routers.py: "g0026" → "G26";
# anything that isn't a Strong's number is upper-cased and left to 404.
_STRONGS_ID_RE = re.compile(r"([GH])0*(\d+)", re.IGNORECASE)


def _normalize_strongs_id(raw: str) -> str:
    m = _STRONGS_ID_RE.fullmatch(raw.strip())
    return f"{m.group(1).upper()}{m.group(2)}" if m else raw.strip().upper()


def _target_reference(row: Any) -> str:
    """A cross-reference target's display reference, ranges included."""
    if row.to_verse_end is not None and row.to_verse_end != row.to_verse_start:
        return f"{row.to_book_name} {row.to_chapter}:{row.to_verse_start}-{row.to_verse_end}"
    return f"{row.to_book_name} {row.to_chapter}:{row.to_verse_start}"


MISSING_DB_TEXT = (
    "No local Bible database at {path}. Run `make get-db` in the concord-mcp"
    " folder (needs Docker once), or set BIBLE_DB_PATH. Alternatively set"
    " CONCORD_MCP_BACKEND=http and use a running Concord."
)

SEMANTIC_UNAVAILABLE_TEXT = (
    "Semantic search isn't available in inprocess mode: {reason}. Two fixes:"
    " (1) switch to the http backend — set CONCORD_MCP_BACKEND=http with a"
    " running Concord — or (2) fetch the local artifacts: run `make get-db`"
    " in the concord-mcp folder (needs Docker once; see ADR 0004), then"
    " restart."
)


class InProcessBackend:
    def __init__(self, config: Config, encoder: Callable[[str], Any] | None = None):
        self._config = config
        # Seam for hermetic tests: the real encoder needs the ~313 MB model.
        self._encoder = encoder or embed_query
        self._conn: sqlite3.Connection | None = None
        self._translations: set[str] = set()
        self._book_names: dict[str, str] = {}
        self._testaments: dict[str, str] = {}
        self._store: VectorStore | None = None

    async def get_verses(
        self, reference: str, translations: list[str] | None = None
    ) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(
            partial(self._get_verses_sync, reference, translations)
        )

    async def semantic_search(
        self,
        query: str,
        translation: str | None = None,
        limit: int = 10,
        min_score: float | None = None,
    ) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(
            partial(self._search_sync, query, translation, limit, min_score)
        )

    # --- the sync mirrors of Concord's /v1 endpoint composition ---------------

    def _get_verses_sync(
        self, reference: str, translations: list[str] | None
    ) -> dict[str, Any]:
        conn = self._connect()
        ids = self._resolve_translations(translations)
        parsed = self._parse(reference)
        result = queries.get_verses(conn, parsed, ids)
        if not result.rows:
            raise ApiError(
                404,
                "no_verses_found",
                f"no verses found for {result.reference!r} in the requested translations",
            )

        by_position: dict[tuple[int, int], dict[str, str]] = {}
        for row in result.rows:
            by_position.setdefault((row.chapter, row.verse), {})[row.translation_id] = (
                row.text
            )
        return {
            "reference": result.reference,
            "translations": list(result.translations),
            "verses": [
                {
                    "book": result.book_id,
                    "chapter": chapter,
                    "verse": verse,
                    "reference": f"{result.book_name} {chapter}:{verse}",
                    "text": {
                        tid: by_position[(chapter, verse)].get(tid)
                        for tid in result.translations
                    },
                }
                for chapter, verse in sorted(by_position)
            ],
        }

    def _search_sync(
        self,
        query: str,
        translation: str | None,
        limit: int,
        min_score: float | None,
    ) -> dict[str, Any]:
        conn = self._connect()
        (display_translation,) = self._resolve_translations(
            [translation] if translation else None
        )
        store = self._load_store()

        try:
            query_vec = self._encoder(query)
        except FileNotFoundError as exc:
            raise LocalDataMissing(
                SEMANTIC_UNAVAILABLE_TEXT.format(reason=exc)
            ) from exc
        matches = cosine_top_k(query_vec, store.matrix, store.refs, limit, min_score)

        results = [
            {
                "book": ref.book_id,
                "chapter": ref.chapter,
                "verse": ref.verse,
                "reference": (
                    f"{self._book_names.get(ref.book_id, ref.book_id)}"
                    f" {ref.chapter}:{ref.verse}"
                ),
                "score": round(score, 4),
                "text": queries.get_verse_text(
                    conn, display_translation, ref.book_id, ref.chapter, ref.verse
                ),
            }
            for ref, score in matches
        ]
        return {
            "query": query,
            "translation": display_translation,
            "count": len(results),
            "results": results,
        }

    # --- the study tools (S3) ---------------------------------------------------

    async def cross_references(
        self, reference: str, include_text: bool = False, limit: int = 10
    ) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(
            partial(self._cross_references_sync, reference, include_text, limit)
        )

    async def word_study(self, reference: str) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(partial(self._word_study_sync, reference))

    async def strongs_entry(self, strongs_id: str) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(
            partial(self._strongs_entry_sync, strongs_id)
        )

    async def strongs_verses(self, strongs_id: str, limit: int = 10) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(
            partial(self._strongs_verses_sync, strongs_id, limit)
        )

    async def list_topics(self, query: str, limit: int = 10) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(
            partial(self._list_topics_sync, query, limit)
        )

    async def get_topic(self, topic_id: str) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(partial(self._get_topic_sync, topic_id))

    async def topic_verses(
        self, topic_id: str, include_text: bool = True, limit: int = 10
    ) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(
            partial(self._topic_verses_sync, topic_id, include_text, limit)
        )

    def _cross_references_sync(
        self, reference: str, include_text: bool, limit: int
    ) -> dict[str, Any]:
        conn = self._connect()
        parsed = self._parse(reference)
        if not queries.reference_exists(conn, parsed):
            raise ApiError(
                404,
                "no_verses_found",
                f"{parsed.echo!r} is out of range in every loaded translation",
            )
        (translation_id,) = (
            self._resolve_translations(None) if include_text else (None,)
        )
        page = queries.get_cross_references(conn, parsed, 0, limit, 0)
        return {
            "reference": parsed.echo,
            "translation": translation_id,
            "min_votes": 0,
            "limit": limit,
            "offset": 0,
            "total": page.total,
            "cross_references": [
                {
                    "from": {
                        "book": row.from_book_id,
                        "chapter": row.from_chapter,
                        "verse": row.from_verse,
                        "reference": (
                            f"{row.from_book_name} {row.from_chapter}:{row.from_verse}"
                        ),
                    },
                    "to": {
                        "book": row.to_book_id,
                        "chapter": row.to_chapter,
                        "verse_start": row.to_verse_start,
                        "verse_end": row.to_verse_end,
                        "reference": _target_reference(row),
                    },
                    "votes": row.votes,
                    "text": (
                        queries.get_verse_text(
                            conn,
                            translation_id,
                            row.to_book_id,
                            row.to_chapter,
                            row.to_verse_start,
                        )
                        if translation_id is not None
                        else None
                    ),
                }
                for row in page.rows
            ],
        }

    def _word_study_sync(self, reference: str) -> dict[str, Any]:
        conn = self._connect()
        parsed = self._parse(reference)
        text_id = (
            HEBREW_TEXT if self._testaments[parsed.book_id] == "OT" else GREEK_TEXT
        )
        if text_id not in self._translations:
            raise ApiError(
                404, "unknown_translation", f"Tagged text {text_id!r} is not loaded."
            )
        tokens = queries.get_words_for_reference(conn, parsed, text_id)
        return {
            "reference": parsed.echo,
            "text_id": text_id,
            "total": len(tokens),
            "tokens": [
                {
                    "position": t.position,
                    "surface_form": t.surface_form,
                    "strongs_id": t.strongs_id,
                    "morph_code": t.morph_code,
                    "lemma": t.lemma,
                    "transliteration": t.transliteration,
                    "gloss": t.gloss,
                }
                for t in tokens
            ],
        }

    def _strongs_entry_sync(self, strongs_id: str) -> dict[str, Any]:
        conn = self._connect()
        entry = queries.get_strongs(conn, _normalize_strongs_id(strongs_id))
        if entry is None:
            raise ApiError(
                404,
                "unknown_strongs",
                f"no Strong's entry for {strongs_id!r}",
                {"strongs_id": strongs_id},
            )
        return {
            "strongs_id": entry.strongs_id,
            "language": entry.language,
            "lemma": entry.lemma,
            "transliteration": entry.transliteration,
            "gloss": entry.gloss,
            "definition": entry.definition,
            "source": entry.source,
        }

    def _strongs_verses_sync(self, strongs_id: str, limit: int) -> dict[str, Any]:
        conn = self._connect()
        normalized = _normalize_strongs_id(strongs_id)
        if queries.get_strongs(conn, normalized) is None:
            raise ApiError(
                404,
                "unknown_strongs",
                f"no Strong's entry for {strongs_id!r}",
                {"strongs_id": strongs_id},
            )
        text_id = HEBREW_TEXT if normalized.startswith("H") else GREEK_TEXT
        if text_id not in self._translations:
            raise ApiError(
                404, "unknown_translation", f"Tagged text {text_id!r} is not loaded."
            )
        (translation_id,) = self._resolve_translations(None)
        rows, total = queries.get_strongs_verses(conn, normalized, text_id, limit, 0)
        return {
            "strongs_id": normalized,
            "text_id": text_id,
            "translation": translation_id,
            "include_text": True,
            "limit": limit,
            "offset": 0,
            "total": total,
            "verses": self._hydrated_verses(conn, rows, translation_id),
        }

    def _list_topics_sync(self, query: str, limit: int) -> dict[str, Any]:
        conn = self._connect()
        page = queries.list_topics(conn, query, None, limit, 0)
        return {
            "q": query,
            "section": None,
            "limit": limit,
            "offset": 0,
            "total": page.total,
            "topics": [
                {
                    "id": t.id,
                    "name": t.name,
                    "section": t.section,
                    "see_also": t.see_also,
                }
                for t in page.rows
            ],
        }

    def _get_topic_sync(self, topic_id: str) -> dict[str, Any]:
        conn = self._connect()
        topic = queries.get_topic(conn, topic_id)
        if topic is None:
            raise ApiError(
                404,
                "unknown_topic",
                f"no topic with id {topic_id!r}",
                {"topic_id": topic_id},
            )
        return {
            "id": topic.id,
            "name": topic.name,
            "section": topic.section,
            "see_also": topic.see_also,
            "verse_count": queries.count_topic_verses(conn, topic.id),
        }

    def _topic_verses_sync(
        self, topic_id: str, include_text: bool, limit: int
    ) -> dict[str, Any]:
        conn = self._connect()
        if queries.get_topic(conn, topic_id) is None:
            raise ApiError(
                404,
                "unknown_topic",
                f"no topic with id {topic_id!r}",
                {"topic_id": topic_id},
            )
        (translation_id,) = (
            self._resolve_translations(None) if include_text else (None,)
        )
        rows, total = queries.get_topic_verses(conn, topic_id, limit, 0)
        return {
            "id": topic_id,
            "translation": translation_id,
            "include_text": include_text,
            "limit": limit,
            "offset": 0,
            "total": total,
            "verses": self._hydrated_verses(conn, rows, translation_id),
        }

    def _parse(self, reference: str) -> Reference:
        """parse_reference with the S1 error mapping."""
        try:
            return parse_reference(reference, SqliteBookResolver(self._connect()))
        except UnknownBookError as exc:
            raise ApiError(404, "unknown_book", str(exc)) from exc
        except ParseError as exc:
            raise ApiError(400, "unparseable_reference", str(exc)) from exc

    def _hydrated_verses(
        self, conn: sqlite3.Connection, rows: Any, translation_id: str | None
    ) -> list[dict[str, Any]]:
        """Verse-ref rows (book_id/book_name/chapter/verse) → tagged dicts."""
        return [
            {
                "book": row.book_id,
                "chapter": row.chapter,
                "verse": row.verse,
                "reference": f"{row.book_name} {row.chapter}:{row.verse}",
                "text": (
                    queries.get_verse_text(
                        conn, translation_id, row.book_id, row.chapter, row.verse
                    )
                    if translation_id is not None
                    else None
                ),
            }
            for row in rows
        ]

    # --- lazy local state ------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            path = self._config.bible_db_path
            if not path.is_file():
                raise LocalDataMissing(MISSING_DB_TEXT.format(path=path))
            self._conn = connect_readonly(path)
            self._translations = {t.id for t in queries.get_translations(self._conn)}
            books = queries.get_books(self._conn)
            self._book_names = {b.id: b.name for b in books}
            self._testaments = {b.id: b.testament for b in books}
        return self._conn

    def _load_store(self) -> VectorStore:
        if self._store is None:
            assets = self._config.semantic_assets
            # The library reads the model directory from this env var only.
            os.environ.setdefault("CONCORD_MODEL_PATH", str(assets / "model"))
            try:
                self._store = load_store(assets / "embeddings.db")
            except StoreError as exc:
                raise LocalDataMissing(
                    SEMANTIC_UNAVAILABLE_TEXT.format(reason=exc)
                ) from exc
        return self._store

    def _resolve_translations(self, requested: list[str] | None) -> tuple[str, ...]:
        """Mirror Concord's resolve_translations: upper-case, de-duplicate,
        omitted -> the configured default, unknown -> 404."""
        self._connect()
        if not requested:
            requested = [self._config.default_translation]
        resolved: list[str] = []
        for raw in requested:
            tid = raw.strip().upper()
            if not tid:
                continue
            if tid not in self._translations:
                raise ApiError(
                    404,
                    "unknown_translation",
                    f"Translation {tid!r} is not loaded."
                    f" Loaded: {sorted(self._translations)}",
                )
            if tid not in resolved:
                resolved.append(tid)
        return (
            tuple(resolved) if resolved else (self._config.default_translation.upper(),)
        )
