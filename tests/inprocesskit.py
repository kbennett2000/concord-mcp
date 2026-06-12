"""Synthetic local artifacts for hermetic in-process tests.

Builds a tiny ``bible.db`` through bible-core's own loader (so the schema is
always the real one) and a tiny ``embeddings.db`` through bible-semantic's own
schema + a valid guard row. Verse text deliberately matches the S1 HTTP
fixtures in tests/fixtures/, which is what makes the parity suite meaningful.

The translation-JSON builders are adapted from bible-core's tests/loaderkit.py
(not shipped in the wheel).
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
from bible_core.loader import build_database
from bible_semantic.model import EMBEDDING_DIM, MODEL_ID, MODEL_REVISION, model_precision
from bible_semantic.schema import create_embeddings_schema

FIXTURES = Path(__file__).parent / "fixtures"


def _verse(number: int, text: str) -> dict[str, Any]:
    return {"number": number, "text": text, "is_red_letter": False}


def _chapter(number: int, verses: list[dict[str, Any]]) -> dict[str, Any]:
    return {"number": number, "verses": verses, "headings": [], "footnotes": []}


def _book(abbreviation: str, order_index: int, chapters: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "abbreviation": abbreviation,
        "name": abbreviation,
        "order_index": order_index,
        "chapters": chapters,
    }


def _translation(code: str, books: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "code": code,
        "name": f"{code} (synthetic)",
        "language": "en",
        "copyright": "Public domain.",
        "books": books,
    }


def _fixture_text(name: str, **keys: Any) -> str:
    """Pull verse text out of an S1 fixture so db and fixtures never drift."""
    payload = json.loads((FIXTURES / f"{name}.json").read_text())
    if "results" in payload:
        for hit in payload["results"]:
            if (hit["book"], hit["chapter"], hit["verse"]) == (
                keys["book"],
                keys["chapter"],
                keys["verse"],
            ):
                return hit["text"]
    for verse in payload["verses"]:
        if (verse["chapter"], verse["verse"]) == (keys["chapter"], keys["verse"]):
            return verse["text"][keys["translation"]]
    raise KeyError(keys)


def build_bible_db(target_dir: Path) -> Path:
    """Build a synthetic bible.db whose content mirrors the S1 fixtures."""
    json_dir = target_dir / "translations"
    json_dir.mkdir(parents=True)

    kjv = _translation(
        "KJV",
        [
            _book(
                "Psa",
                19,
                [
                    _chapter(
                        23,
                        [
                            _verse(
                                v,
                                _fixture_text(
                                    "verses_psalm23_range",
                                    chapter=23,
                                    verse=v,
                                    translation="KJV",
                                ),
                            )
                            for v in (1, 2, 3)
                        ],
                    )
                ],
            ),
            _book(
                "Mat",
                40,
                [
                    _chapter(
                        6,
                        [
                            _verse(
                                25,
                                _fixture_text(
                                    "semantic_anxious", book="MAT", chapter=6, verse=25
                                ),
                            )
                        ],
                    )
                ],
            ),
            _book(
                "John",
                43,
                [
                    _chapter(
                        3,
                        [
                            _verse(
                                16,
                                _fixture_text(
                                    "verses_john316_kjv_web",
                                    chapter=3,
                                    verse=16,
                                    translation="KJV",
                                ),
                            )
                        ],
                    )
                ],
            ),
            _book(
                "Php",
                50,
                [
                    _chapter(
                        4,
                        [
                            _verse(
                                6,
                                _fixture_text(
                                    "semantic_anxious", book="PHP", chapter=4, verse=6
                                ),
                            )
                        ],
                    )
                ],
            ),
            _book(
                "1Pe",
                60,
                [
                    _chapter(
                        5,
                        [
                            _verse(
                                7,
                                _fixture_text(
                                    "semantic_anxious", book="1PE", chapter=5, verse=7
                                ),
                            )
                        ],
                    )
                ],
            ),
        ],
    )
    web = _translation(
        "WEB",
        [
            _book(
                "John",
                43,
                [
                    _chapter(
                        3,
                        [
                            _verse(
                                16,
                                _fixture_text(
                                    "verses_john316_kjv_web",
                                    chapter=3,
                                    verse=16,
                                    translation="WEB",
                                ),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    # YLT is loaded but has no Psalms text — the fixture's null-text scenario.
    ylt = _translation(
        "YLT",
        [_book("Gen", 1, [_chapter(1, [_verse(1, "In the beginning…")])])],
    )

    for payload in (kjv, web, ylt):
        (json_dir / f"{payload['code']}.json").write_text(json.dumps(payload))

    db_path = target_dir / "bible.db"
    build_database(db_path, [json_dir])
    return db_path


# Store rows come back ORDER BY book_id — "1PE" < "MAT" < "PHP". Each verse gets
# a distinct one-hot unit vector; the fake encoder's query vector then carries
# the exact cosine score for each at that index.
_STORE_ROWS = [("1PE", 5, 7, 2), ("MAT", 6, 25, 1), ("PHP", 4, 6, 0)]
_QUERY_SCORES = {"do not be anxious": {0: 0.9312, 1: 0.9011, 2: 0.8847}}


def fake_encoder(query: str) -> np.ndarray:
    """Deterministic stand-in for embed_query — no model, exact scores."""
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    for index, score in _QUERY_SCORES.get(query, {}).items():
        vec[index] = score
    return vec


def build_embeddings_db(target_dir: Path, *, model_id: str = MODEL_ID) -> Path:
    """Write a guard-valid embeddings.db with one-hot vectors per _STORE_ROWS.

    Pass a wrong ``model_id`` to exercise the store's model-mismatch guard.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    db_path = target_dir / "embeddings.db"
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        create_embeddings_schema(conn)
        conn.execute(
            "INSERT INTO embedding_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
            (model_id, MODEL_REVISION, EMBEDDING_DIM, model_precision(), "WEB", 1, "test"),
        )
        for book_id, chapter, verse, hot_index in _STORE_ROWS:
            vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
            vec[hot_index] = 1.0
            conn.execute(
                "INSERT INTO verse_embeddings VALUES (?, ?, ?, ?)",
                (book_id, chapter, verse, vec.tobytes()),
            )
        conn.commit()
    finally:
        conn.close()
    return db_path
