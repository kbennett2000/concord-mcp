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
import sqlite3
from collections.abc import Callable
from functools import partial
from typing import Any

import anyio.to_thread
from bible_core.db import connect_readonly
from bible_core.parser import ParseError, UnknownBookError, parse_reference
from bible_core.queries import get_books, get_translations, get_verse_text, get_verses
from bible_core.resolver import SqliteBookResolver
from bible_semantic.model import embed_query
from bible_semantic.search import cosine_top_k
from bible_semantic.store import StoreError, VectorStore, load_store

from concord_mcp.backends.base import ApiError, LocalDataMissing
from concord_mcp.config import Config

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
        try:
            parsed = parse_reference(reference, SqliteBookResolver(conn))
        except UnknownBookError as exc:
            raise ApiError(404, "unknown_book", str(exc)) from exc
        except ParseError as exc:
            raise ApiError(400, "unparseable_reference", str(exc)) from exc

        result = get_verses(conn, parsed, ids)
        if not result.rows:
            raise ApiError(
                404,
                "no_verses_found",
                f"no verses found for {result.reference!r} in the requested translations",
            )

        by_position: dict[tuple[int, int], dict[str, str]] = {}
        for row in result.rows:
            by_position.setdefault((row.chapter, row.verse), {})[
                row.translation_id
            ] = row.text
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
                "text": get_verse_text(
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

    # --- lazy local state ------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            path = self._config.bible_db_path
            if not path.is_file():
                raise LocalDataMissing(MISSING_DB_TEXT.format(path=path))
            self._conn = connect_readonly(path)
            self._translations = {t.id for t in get_translations(self._conn)}
            self._book_names = {b.id: b.name for b in get_books(self._conn)}
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
            tuple(resolved)
            if resolved
            else (self._config.default_translation.upper(),)
        )
