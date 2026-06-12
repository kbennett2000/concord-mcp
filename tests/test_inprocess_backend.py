"""InProcessBackend over synthetic artifacts — shapes, errors, degradation."""

import pytest

from concord_mcp.backends import ApiError, InProcessBackend, LocalDataMissing
from concord_mcp.config import Config
from inprocesskit import build_embeddings_db, fake_encoder

pytestmark = pytest.mark.anyio


async def test_john316_matches_the_http_fixture_exactly(inprocess_backend, fixture):
    payload = await inprocess_backend.get_verses("John 3:16", ["kjv", "web"])
    assert payload == fixture("verses_john316_kjv_web")


async def test_psalms_range_with_absent_translation(inprocess_backend, fixture):
    payload = await inprocess_backend.get_verses("Psalm 23:1-3", ["KJV", "YLT"])
    assert payload == fixture("verses_psalm23_range")


async def test_omitted_translations_use_the_configured_default(inprocess_backend):
    payload = await inprocess_backend.get_verses("John 3:16")
    assert payload["translations"] == ["KJV"]
    assert payload["verses"][0]["text"]["KJV"].startswith("For God so loved")


async def test_unknown_translation_lists_loaded_ids(inprocess_backend):
    with pytest.raises(ApiError) as excinfo:
        await inprocess_backend.get_verses("John 3:16", ["NIV"])
    assert excinfo.value.status == 404
    assert excinfo.value.code == "unknown_translation"
    assert "KJV" in excinfo.value.message


async def test_unparseable_reference(inprocess_backend):
    with pytest.raises(ApiError) as excinfo:
        await inprocess_backend.get_verses("John 3:16; 17")
    assert excinfo.value.status == 400
    assert excinfo.value.code == "unparseable_reference"


async def test_unknown_book(inprocess_backend):
    with pytest.raises(ApiError) as excinfo:
        await inprocess_backend.get_verses("Hezekiah 3:16")
    assert excinfo.value.status == 404
    assert excinfo.value.code == "unknown_book"


async def test_valid_reference_with_no_rows(inprocess_backend):
    with pytest.raises(ApiError) as excinfo:
        await inprocess_backend.get_verses("John 99:99")
    assert excinfo.value.status == 404
    assert excinfo.value.code == "no_verses_found"


async def test_semantic_matches_the_http_fixture_exactly(inprocess_backend, fixture):
    payload = await inprocess_backend.semantic_search("do not be anxious")
    assert payload == fixture("semantic_anxious")


async def test_semantic_min_score_floor(inprocess_backend, fixture):
    payload = await inprocess_backend.semantic_search("do not be anxious", min_score=0.9)
    assert payload == fixture("semantic_anxious_min090")


async def test_semantic_empty_result(inprocess_backend, fixture):
    payload = await inprocess_backend.semantic_search(
        "quantum chromodynamics", min_score=0.5
    )
    assert payload == fixture("semantic_empty")


async def test_semantic_text_hydration_is_honest_about_absent_translations(
    inprocess_backend,
):
    # WEB is loaded but has none of the matched verses — text must be null,
    # never silently swapped for another translation.
    payload = await inprocess_backend.semantic_search(
        "do not be anxious", translation="WEB"
    )
    assert payload["translation"] == "WEB"
    assert [hit["text"] for hit in payload["results"]] == [None, None, None]


async def test_missing_bible_db_names_both_fixes(tmp_path):
    backend = InProcessBackend(
        Config(backend="inprocess", bible_db_path=tmp_path / "nope.db"),
        encoder=fake_encoder,
    )
    with pytest.raises(LocalDataMissing) as excinfo:
        await backend.get_verses("John 3:16")
    text = str(excinfo.value)
    assert "No local Bible database" in text
    assert "make get-db" in text
    assert "BIBLE_DB_PATH" in text
    assert "CONCORD_MCP_BACKEND=http" in text


async def test_missing_semantic_assets_degrade_but_lookup_still_works(
    synthetic_data, tmp_path
):
    backend = InProcessBackend(
        Config(
            backend="inprocess",
            bible_db_path=synthetic_data["bible_db"],
            semantic_assets=tmp_path / "absent",
        ),
        encoder=fake_encoder,
    )
    payload = await backend.get_verses("John 3:16")
    assert payload["verses"][0]["text"]["KJV"]

    with pytest.raises(LocalDataMissing) as excinfo:
        await backend.semantic_search("do not be anxious")
    text = str(excinfo.value)
    assert "Semantic search isn't available in inprocess mode" in text
    assert "CONCORD_MCP_BACKEND=http" in text
    assert "make get-db" in text


async def test_model_mismatched_store_degrades_with_the_guards_reason(
    synthetic_data, tmp_path
):
    assets = tmp_path / "stale"
    build_embeddings_db(assets, model_id="acme/other-model")
    backend = InProcessBackend(
        Config(
            backend="inprocess",
            bible_db_path=synthetic_data["bible_db"],
            semantic_assets=assets,
        ),
        encoder=fake_encoder,
    )
    with pytest.raises(LocalDataMissing) as excinfo:
        await backend.semantic_search("do not be anxious")
    assert "different model" in str(excinfo.value)
