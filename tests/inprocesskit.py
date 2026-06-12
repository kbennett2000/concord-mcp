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
from bible_semantic.model import (
    EMBEDDING_DIM,
    MODEL_ID,
    MODEL_REVISION,
    model_precision,
)
from bible_semantic.schema import create_embeddings_schema

FIXTURES = Path(__file__).parent / "fixtures"


def _verse(number: int, text: str) -> dict[str, Any]:
    return {"number": number, "text": text, "is_red_letter": False}


def _chapter(number: int, verses: list[dict[str, Any]]) -> dict[str, Any]:
    return {"number": number, "verses": verses, "headings": [], "footnotes": []}


def _book(
    abbreviation: str, order_index: int, chapters: list[dict[str, Any]]
) -> dict[str, Any]:
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


_BOOK_ORDER = {
    "Gen": 1,
    "Psa": 19,
    "Mat": 40,
    "John": 43,
    "Rom": 45,
    "Php": 50,
    "1Pe": 60,
    "1Jn": 62,
}

# KJV text for the study-tool seeds (public domain). The matching HTTP fixtures
# repeat these strings; the parity suite fails on any drift between the two.
KJV_TEXTS = {
    ("Psa", 37, 5): (
        "Commit thy way unto the LORD; trust also in him;"
        " and he shall bring it to pass."
    ),
    ("John", 21, 15): (
        "So when they had dined, Jesus saith to Simon Peter, Simon, son of"
        " Jonas, lovest thou me more than these? He saith unto him, Yea, Lord;"
        " thou knowest that I love thee. He saith unto him, Feed my lambs."
    ),
    ("John", 21, 16): (
        "He saith to him again the second time, Simon, son of Jonas, lovest"
        " thou me? He saith unto him, Yea, Lord; thou knowest that I love"
        " thee. He saith unto him, Feed my sheep."
    ),
    ("John", 21, 17): (
        "He saith unto him the third time, Simon, son of Jonas, lovest thou"
        " me? Peter was grieved because he said unto him the third time,"
        " Lovest thou me? And he said unto him, Lord, thou knowest all"
        " things; thou knowest that I love thee. Jesus saith unto him, Feed"
        " my sheep."
    ),
    ("Rom", 5, 8): (
        "But God commendeth his love toward us, in that, while we were yet"
        " sinners, Christ died for us."
    ),
    ("Rom", 8, 32): (
        "He that spared not his own Son, but delivered him up for us all,"
        " how shall he not with him also freely give us all things?"
    ),
    ("1Jn", 4, 9): (
        "In this was manifested the love of God toward us, because that God"
        " sent his only begotten Son into the world, that we might live"
        " through him."
    ),
}

# The loader requires translations sharing a book to agree on its chapter
# set, so SBLGNT carries a John 3 verse and WEB a John 21 verse (see below).
SBLGNT_TEXTS = {
    ("John", 3, 16): "Οὕτως γὰρ ἠγάπησεν ὁ θεὸς τὸν κόσμον…",
    ("John", 21, 15): "Σίμων Ἰωάννου, ἀγαπᾷς με πλέον τούτων; … φιλῶ σε.",
    ("John", 21, 16): "Σίμων Ἰωάννου, ἀγαπᾷς με; … φιλῶ σε.",
    ("John", 21, 17): "Σίμων Ἰωάννου, φιλεῖς με; … φιλῶ σε.",
}

WEB_JOHN_2115 = (
    "So when they had eaten their breakfast, Jesus said to Simon Peter,"
    " Simon, son of Jonah, do you love me more than these?"
)

# (book, chapter, verse, position, surface, strongs_id, morph) — the famous
# ἀγαπάω/φιλέω exchange, tiny: questions use G25 in vv. 15-16, answers G5368,
# and v. 17 switches to G5368 for both. One untagged token exercises [untagged].
SBLGNT_TOKENS = [
    ("John", 21, 15, 1, "ἀγαπᾷς", "G25", "V-PAI-2S"),
    ("John", 21, 15, 2, "καί", None, None),
    ("John", 21, 15, 3, "φιλῶ", "G5368", "V-PAI-1S"),
    ("John", 21, 16, 1, "ἀγαπᾷς", "G25", "V-PAI-2S"),
    ("John", 21, 16, 2, "φιλῶ", "G5368", "V-PAI-1S"),
    ("John", 21, 17, 1, "φιλεῖς", "G5368", "V-PAI-2S"),
    ("John", 21, 17, 2, "φιλῶ", "G5368", "V-PAI-1S"),
]

LEXICON_ENTRIES = [
    {
        "strongs_id": "G25",
        "language": "grc",
        "lemma": "ἀγαπάω",
        "transliteration": "agapaō",
        "gloss": "to love",
        "definition": "ἀγαπάω … to love, value, esteem; the love of deliberate choice.",
    },
    {
        "strongs_id": "G26",
        "language": "grc",
        "lemma": "ἀγάπη",
        "transliteration": "agapē",
        "gloss": "love",
        "definition": "ἀγάπη, -ης, ἡ … love, goodwill, esteem; the highest form of love.",
    },
    {
        "strongs_id": "G5368",
        "language": "grc",
        "lemma": "φιλέω",
        "transliteration": "phileō",
        "gloss": "to have affection for",
        "definition": "φιλέω … to love as a friend, have affection for; also: to kiss.",
    },
]
LEXICON_SOURCE = "STEP Bible (Tyndale House)"

TOPICS = [
    {
        "id": "care",
        "name": "CARE",
        "section": "C",
        "verses": [
            {"book": "Psa", "chapter": 37, "verse": 5},
            {"book": "Mat", "chapter": 6, "verse": 25},
            {"book": "Php", "chapter": 4, "verse": 6},
            {"book": "1Pe", "chapter": 5, "verse": 7},
        ],
    },
    {
        "id": "faith",
        "name": "FAITH",
        "section": "F",
        "verses": [{"book": "John", "chapter": 3, "verse": 16}],
    },
    {
        "id": "faithfulness",
        "name": "FAITHFULNESS",
        "section": "F",
        "verses": [{"book": "Psa", "chapter": 37, "verse": 5}],
    },
    {
        "id": "kindness",
        "name": "KINDNESS",
        "section": "K",
        "see_also": "care",
        "verses": [],
    },
]

# --- geography + journeys (S4) -------------------------------------------------
# Builders adapted from bible-core's tests/geokit.py (not shipped in the wheel):
# only the subset of OpenBible's ancient/modern structure the geo loader reads.


def _modern_loc(modern_id: str, longitude: float, latitude: float) -> dict[str, Any]:
    # modern.jsonl lonlat is "longitude,latitude" order (longitude first).
    return {"id": modern_id, "lonlat": f"{longitude},{latitude}"}


def _assoc(score: int, name: str) -> dict[str, Any]:
    return {"score": score, "name": name, "url_slug": name.lower().replace(" ", "-")}


def _geo_verse(book_order: int, chapter: int, verse: int) -> dict[str, Any]:
    return {"sort": f"{book_order:02d}{chapter:03d}{verse:03d}"}


def _ancient_place(
    place_id: str,
    friendly_id: str,
    *,
    types: tuple[str, ...] = ("settlement",),
    associations: dict[str, dict[str, Any]] | None = None,
    specials: tuple[str, ...] = (),
    verses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": place_id,
        "friendly_id": friendly_id,
        "url_slug": friendly_id.lower().replace(" ", "-"),
        "preceding_article": "",
        "types": list(types),
        "modern_associations": associations or {},
        "verses": verses or [],
    }
    if specials:
        record["identifications"] = [
            {"resolutions": [{"special": special} for special in specials]}
        ]
    return record


JOHN_2116 = _geo_verse(43, 21, 16)

# One place per honesty status, all named in John 21:16; Nod also in Gen 4:16.
ANCIENT_PLACES = [
    _ancient_place(
        "a-amphipolis",
        "Amphipolis",
        associations={"m-amphipolis": _assoc(1000, "Amphipolis")},
        verses=[JOHN_2116],
    ),
    _ancient_place(
        "a-aenon",
        "Aenon",
        # Two competing associations (runner-up ≥ 0.8 × best, both ≥ 100) → disputed.
        associations={
            "m-ainun": _assoc(276, "Khirbat Ainun"),
            "m-umdan": _assoc(226, "Umm al-Umdan"),
        },
        verses=[JOHN_2116],
    ),
    _ancient_place(
        "a-nod",
        "Nod",
        types=("region",),
        specials=("unknown_place",),
        verses=[_geo_verse(1, 4, 16), JOHN_2116],
    ),
    _ancient_place(
        "a-hamon-gog",
        "Valley of Hamon-gog",
        types=("valley",),
        specials=("nonspecific_place",),
        verses=[JOHN_2116],
    ),
    _ancient_place(
        "a-holy-place",
        "Holy Place",
        types=("special",),
        specials=("multiple_locations",),
        verses=[JOHN_2116],
    ),
]

MODERN_LOCS = [
    _modern_loc("m-amphipolis", 23.847209, 40.820159),
    _modern_loc("m-ainun", 35.45, 32.05),
    _modern_loc("m-umdan", 35.2, 31.9),
]

JOURNEYS = {
    "journeys": [
        {
            "id": "galilee-loop",
            "name": "A Galilean Loop",
            "scripture": "John 21",
            "dating": "c. AD 30 (conventional)",
            "source": "Synthetic itinerary for tests.",
            "note": (
                "One commonly proposed reconstruction assembled for the test suite."
            ),
            "stops": [
                {"ordinal": 1, "place_id": "a-amphipolis", "reference": "John 21:15"},
                {"ordinal": 2, "place_id": "a-aenon", "reference": "John 21:16"},
                {"ordinal": 3, "place_id": "a-nod", "reference": "John 21:17"},
                {"ordinal": 4, "place_id": "a-amphipolis", "reference": "John 21:19"},
            ],
        }
    ]
}

CROSS_REFS_TSV = (
    "From\tTo\tVotes\n"
    "John.3.16\tRom.5.8\t968\n"
    "John.3.16\t1Jn.4.9-1Jn.4.10\t601\n"
    "John.3.16\tRom.8.32\t455\n"
)


def _translation_from_table(code: str, texts: dict) -> dict[str, Any]:
    """Build loader translation JSON from a {(book, chapter, verse): text} table."""
    books: list[dict[str, Any]] = []
    for abbr in sorted({k[0] for k in texts}, key=lambda a: _BOOK_ORDER[a]):
        chapters = []
        for ch in sorted({c for b, c, _ in texts if b == abbr}):
            verses = [
                _verse(v, texts[(abbr, ch, v)])
                for _, c, v in sorted(k for k in texts if k[0] == abbr and k[1] == ch)
                if c == ch
            ]
            chapters.append(_chapter(ch, verses))
        books.append(_book(abbr, _BOOK_ORDER[abbr], chapters))
    return _translation(code, books)


def build_bible_db(target_dir: Path) -> Path:
    """Build a synthetic bible.db whose content mirrors the HTTP fixtures."""
    json_dir = target_dir / "translations"
    json_dir.mkdir(parents=True)

    kjv_texts = {
        **{
            ("Psa", 23, v): _fixture_text(
                "verses_psalm23_range", chapter=23, verse=v, translation="KJV"
            )
            for v in (1, 2, 3)
        },
        ("Mat", 6, 25): _fixture_text(
            "semantic_anxious", book="MAT", chapter=6, verse=25
        ),
        ("John", 3, 16): _fixture_text(
            "verses_john316_kjv_web", chapter=3, verse=16, translation="KJV"
        ),
        ("Php", 4, 6): _fixture_text(
            "semantic_anxious", book="PHP", chapter=4, verse=6
        ),
        ("1Pe", 5, 7): _fixture_text(
            "semantic_anxious", book="1PE", chapter=5, verse=7
        ),
        **KJV_TEXTS,
    }
    kjv = _translation_from_table("KJV", kjv_texts)
    # WEB deliberately lacks Romans 8:32 etc. — the hydration-null honesty cases.
    web = _translation_from_table(
        "WEB",
        {
            ("John", 3, 16): _fixture_text(
                "verses_john316_kjv_web", chapter=3, verse=16, translation="WEB"
            ),
            ("John", 21, 15): WEB_JOHN_2115,
        },
    )
    # YLT is loaded but has no Psalms text — the fixture's null-text scenario.
    ylt = _translation_from_table("YLT", {("Gen", 1, 1): "In the beginning…"})
    sblgnt = _translation_from_table("SBLGNT", SBLGNT_TEXTS)

    for payload in (kjv, web, ylt, sblgnt):
        (json_dir / f"{payload['code']}.json").write_text(json.dumps(payload))

    xref_dir = target_dir / "cross_refs"
    xref_dir.mkdir()
    (xref_dir / "xrefs.tsv").write_text(CROSS_REFS_TSV)

    topics_dir = target_dir / "topics"
    topics_dir.mkdir()
    (topics_dir / "naves.json").write_text(
        json.dumps({"source": "Nave's Topical Bible (synthetic)", "topics": TOPICS})
    )

    strongs_dir = target_dir / "strongs"
    strongs_dir.mkdir()
    (strongs_dir / "lexicon.json").write_text(
        json.dumps({"source": LEXICON_SOURCE, "entries": LEXICON_ENTRIES})
    )
    (strongs_dir / "tokens-sblgnt.json").write_text(
        json.dumps(
            {
                "text_id": "SBLGNT",
                "tokens": [
                    {
                        "book": b,
                        "chapter": c,
                        "verse": v,
                        "position": p,
                        "surface_form": s,
                        "strongs_id": sid,
                        "morph_code": m,
                    }
                    for b, c, v, p, s, sid, m in SBLGNT_TOKENS
                ],
            }
        )
    )

    geo_dir = target_dir / "geography"
    geo_dir.mkdir()
    (geo_dir / "ancient.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in ANCIENT_PLACES)
    )
    (geo_dir / "modern.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in MODERN_LOCS)
    )

    journeys_dir = target_dir / "journeys"
    journeys_dir.mkdir()
    (journeys_dir / "journeys.json").write_text(json.dumps(JOURNEYS))

    db_path = target_dir / "bible.db"
    build_database(
        db_path,
        [json_dir],
        cross_ref_dirs=[xref_dir],
        geo_dir=geo_dir,
        topics_dir=topics_dir,
        lexicon_dir=strongs_dir,
        tokens_dir=strongs_dir,
        journeys_dir=journeys_dir,
    )
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
            (
                model_id,
                MODEL_REVISION,
                EMBEDDING_DIM,
                model_precision(),
                "WEB",
                1,
                "test",
            ),
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
