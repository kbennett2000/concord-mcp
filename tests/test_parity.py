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
