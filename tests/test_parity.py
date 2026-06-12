"""ADR 0002's parity obligation: one scenario suite, both backends.

The synthetic bible.db is built from the same verse text as the S1 HTTP
fixtures, so each scenario asserts that both backends produce the *same*
payload (or the same typed error). The one documented, intentional
behavioral difference: 503/Retry-After load shedding (`ConcordBusy`) is a
Concord-server concurrency cap and exists only in http mode — in-process
inference runs inline and never sheds.
"""

import inspect

import pytest
import respx

from concord_mcp.backends import ApiError, HttpBackend, InProcessBackend
from concord_mcp.backends import inprocess as inprocess_module
from concord_mcp.config import Config
from inprocesskit import fake_encoder

BASE = "http://concord.test"

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["http", "inprocess"])
def call(request, fixture, synthetic_data):
    """Run a backend method in either mode; http serves the named fixture."""
    mode = request.param

    async def _call(method, http_fixture, status, /, **kwargs):
        if mode == "inprocess":
            backend = InProcessBackend(
                Config(
                    backend="inprocess",
                    bible_db_path=synthetic_data["bible_db"],
                    semantic_assets=synthetic_data["semantic"],
                ),
                encoder=fake_encoder,
            )
            return await getattr(backend, method)(**kwargs)
        backend = HttpBackend(Config(concord_url=BASE))
        with respx.mock:
            respx.get(url__startswith=f"{BASE}/v1/").respond(
                status_code=status, json=fixture(http_fixture)
            )
            return await getattr(backend, method)(**kwargs)

    return _call


async def test_verses_multi_translation(call, fixture):
    payload = await call(
        "get_verses",
        "verses_john316_kjv_web",
        200,
        reference="John 3:16",
        translations=["kjv", "web"],
    )
    assert payload == fixture("verses_john316_kjv_web")


async def test_verses_range_with_absent_translation(call, fixture):
    payload = await call(
        "get_verses",
        "verses_psalm23_range",
        200,
        reference="Psalm 23:1-3",
        translations=["KJV", "YLT"],
    )
    assert payload == fixture("verses_psalm23_range")


@pytest.mark.parametrize(
    ("reference", "http_fixture", "status", "code"),
    [
        ("John 3:16; 17", "error_unparseable_reference", 400, "unparseable_reference"),
        ("Hezekiah 3:16", "error_unknown_book", 404, "unknown_book"),
        ("John 99:99", "error_no_verses_found", 404, "no_verses_found"),
    ],
)
async def test_verses_error_codes(call, reference, http_fixture, status, code):
    with pytest.raises(ApiError) as excinfo:
        await call("get_verses", http_fixture, status, reference=reference)
    assert excinfo.value.status == status
    assert excinfo.value.code == code


async def test_unknown_translation_error(call):
    with pytest.raises(ApiError) as excinfo:
        await call(
            "get_verses",
            "error_unknown_translation",
            404,
            reference="John 3:16",
            translations=["NIV"],
        )
    assert excinfo.value.status == 404
    assert excinfo.value.code == "unknown_translation"


async def test_semantic_search(call, fixture):
    payload = await call(
        "semantic_search", "semantic_anxious", 200, query="do not be anxious"
    )
    assert payload == fixture("semantic_anxious")


async def test_semantic_min_score(call, fixture):
    payload = await call(
        "semantic_search",
        "semantic_anxious_min090",
        200,
        query="do not be anxious",
        min_score=0.9,
    )
    assert payload == fixture("semantic_anxious_min090")


async def test_semantic_empty(call, fixture):
    payload = await call(
        "semantic_search",
        "semantic_empty",
        200,
        query="quantum chromodynamics",
        min_score=0.5,
    )
    assert payload == fixture("semantic_empty")


def test_busy_is_http_only():
    """The documented parity exception (S2 ruling 3): ConcordBusy belongs to
    Concord's HTTP load shedding; the in-process backend has no 503 path."""
    assert "ConcordBusy" not in inspect.getsource(inprocess_module)


# --- S3 study families ------------------------------------------------------------


async def test_cross_references_ranked_with_votes(call, fixture):
    payload = await call(
        "cross_references", "xrefs_john316", 200, reference="John 3:16"
    )
    assert payload == fixture("xrefs_john316")


async def test_cross_references_hydrated(call, fixture):
    payload = await call(
        "cross_references",
        "xrefs_john316_text",
        200,
        reference="John 3:16",
        include_text=True,
    )
    assert payload == fixture("xrefs_john316_text")


@pytest.mark.parametrize("mode", ["http", "inprocess"])
async def test_cross_references_absent_translation_hydrates_null(
    mode, fixture, synthetic_data
):
    # A WEB-default server: Romans 8:32 isn't in the synthetic WEB → text null.
    if mode == "inprocess":
        backend = InProcessBackend(
            Config(
                backend="inprocess",
                default_translation="WEB",
                bible_db_path=synthetic_data["bible_db"],
                semantic_assets=synthetic_data["semantic"],
            ),
            encoder=fake_encoder,
        )
        payload = await backend.cross_references("John 3:16", include_text=True)
    else:
        backend = HttpBackend(Config(concord_url=BASE, default_translation="WEB"))
        with respx.mock:
            respx.get(url__startswith=f"{BASE}/v1/").respond(
                json=fixture("xrefs_john316_text_web")
            )
            payload = await backend.cross_references("John 3:16", include_text=True)
    assert payload["translation"] == "WEB"
    assert payload["cross_references"][2]["text"] is None  # Romans 8:32


async def test_word_study_single_verse(call, fixture):
    payload = await call("word_study", "words_john2115", 200, reference="John 21:15")
    assert payload == fixture("words_john2115")


async def test_word_study_range(call, fixture):
    payload = await call(
        "word_study", "words_john211517", 200, reference="John 21:15-17"
    )
    assert payload == fixture("words_john211517")


async def test_word_study_range_with_tokenless_verse(call, fixture):
    payload = await call(
        "word_study", "words_john211518", 200, reference="John 21:15-18"
    )
    assert payload == fixture("words_john211518")


async def test_strongs_entry_normalizes_ids(call, fixture):
    payload = await call("strongs_entry", "strongs_g26", 200, strongs_id="g0026")
    assert payload == fixture("strongs_g26")


async def test_strongs_verses_with_true_total(call, fixture):
    payload = await call(
        "strongs_verses", "strongs_g5368_verses_p2", 200, strongs_id="G5368", limit=2
    )
    assert payload == fixture("strongs_g5368_verses_p2")


async def test_topics_substring_search(call, fixture):
    payload = await call("list_topics", "topics_q_faith", 200, query="faith")
    assert payload == fixture("topics_q_faith")


async def test_topics_zero_matches(call, fixture):
    payload = await call("list_topics", "topics_q_zero", 200, query="zzgrindset")
    assert payload == fixture("topics_q_zero")


async def test_topic_detail_carries_see_also_and_count(call, fixture):
    payload = await call("get_topic", "topic_care_detail", 200, topic_id="care")
    assert payload == fixture("topic_care_detail")


async def test_topic_verses_hydrated(call, fixture):
    payload = await call("topic_verses", "topic_care_verses", 200, topic_id="care")
    assert payload == fixture("topic_care_verses")


async def test_unknown_strongs_error_code(call):
    with pytest.raises(ApiError) as excinfo:
        await call("strongs_entry", "error_unknown_strongs", 404, strongs_id="Q99")
    assert excinfo.value.status == 404
    assert excinfo.value.code == "unknown_strongs"


async def test_unknown_topic_error_code(call):
    with pytest.raises(ApiError) as excinfo:
        await call("topic_verses", "error_unknown_topic", 404, topic_id="caare")
    assert excinfo.value.status == 404
    assert excinfo.value.code == "unknown_topic"


# --- S4 geography, journeys, random -------------------------------------------------


async def test_places_mixed_statuses(call, fixture):
    payload = await call(
        "places_for_passage", "places_john2116", 200, reference="John 21:16"
    )
    assert payload == fixture("places_john2116")


async def test_places_land_of_nod_unknown(call, fixture):
    payload = await call(
        "places_for_passage", "places_gen416", 200, reference="Genesis 4:16"
    )
    assert payload == fixture("places_gen416")
    nod = payload["places"][0]
    assert nod["status"] == "unknown"
    assert nod["latitude"] is None and nod["longitude"] is None


async def test_places_empty_passage(call, fixture):
    payload = await call(
        "places_for_passage", "places_empty", 200, reference="John 3:16"
    )
    assert payload == fixture("places_empty")


async def test_journeys_list(call, fixture):
    payload = await call("list_journeys", "journeys_list", 200)
    assert payload == fixture("journeys_list")


async def test_journey_detail_with_disputed_and_unknown_stops(call, fixture):
    payload = await call(
        "journey_detail", "journey_galilee_loop", 200, journey_id="galilee-loop"
    )
    assert payload == fixture("journey_galilee_loop")
    statuses = [s["status"] for s in payload["stops"]]
    assert statuses == ["identified", "disputed", "unknown", "identified"]


async def test_unknown_journey_error_code(call):
    with pytest.raises(ApiError) as excinfo:
        await call(
            "journey_detail", "error_unknown_journey", 404, journey_id="paul-fourth"
        )
    assert excinfo.value.status == 404
    assert excinfo.value.code == "unknown_journey"


async def test_random_single_candidate_universe(call, fixture):
    # YLT holds exactly one verse, so this draw is deterministic on both
    # backends — the scenario proves filter plumbing and shape, the things
    # parity can prove; randomness itself is asserted in test_inprocess_backend.
    payload = await call(
        "random_verse", "random_gen_ylt", 200, book="Gen", translation="YLT"
    )
    assert payload == fixture("random_gen_ylt")


async def test_random_no_match_error_code(call):
    with pytest.raises(ApiError) as excinfo:
        await call(
            "random_verse",
            "error_no_match",
            404,
            book="Gen",
            testament="NT",
            translation="YLT",
        )
    assert excinfo.value.status == 404
    assert excinfo.value.code == "no_match"


async def test_random_unknown_book_error_code(call, fixture):
    with pytest.raises(ApiError) as excinfo:
        await call("random_verse", "error_unknown_book", 400, book="Hezekiah")
    assert excinfo.value.status == 400
    assert excinfo.value.code == "unknown_book"


# --- S5a keyword search + catalogs ----------------------------------------------------


async def test_search_keyword_single(call, fixture):
    payload = await call("search_keyword", "search_shepherd", 200, query="shepherd")
    assert payload == fixture("search_shepherd")


async def test_search_keyword_excerpted_snippet(call, fixture):
    payload = await call("search_keyword", "search_grieved", 200, query="grieved")
    assert payload == fixture("search_grieved")
    assert "…" in payload["hits"][0]["snippet"]  # the excerpt case is real


async def test_search_keyword_multi_translation(call, fixture):
    payload = await call(
        "search_keyword",
        "search_loved_multi",
        200,
        query="loved",
        translations=["KJV", "WEB"],
    )
    assert payload == fixture("search_loved_multi")
    assert list(payload["hits"][0]["matches"]) == ["KJV", "WEB"]


async def test_search_keyword_zero(call, fixture):
    payload = await call("search_keyword", "search_zero", 200, query="zebra")
    assert payload == fixture("search_zero")


async def test_invalid_search_query_error_code(call):
    with pytest.raises(ApiError) as excinfo:
        await call("search_keyword", "error_invalid_search", 400, query='"unclosed')
    assert excinfo.value.status == 400
    assert excinfo.value.code == "invalid_search_query"


async def test_translations_catalog(call, fixture):
    payload = await call("translations", "resource_translations", 200)
    assert payload == fixture("resource_translations")


async def test_books_catalog(call, fixture):
    payload = await call("books", "resource_books", 200)
    assert payload == fixture("resource_books")
