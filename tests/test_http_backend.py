import httpx
import pytest
import respx

from concord_mcp.backends import (
    ApiError,
    ConcordBusy,
    ConcordUnreachable,
    HttpBackend,
)
from concord_mcp.backends import http as http_module
from concord_mcp.config import Config

BASE = "http://concord.test"

pytestmark = pytest.mark.anyio


@pytest.fixture
def backend():
    return HttpBackend(Config(concord_url=BASE))


@pytest.fixture
def no_sleep(monkeypatch):
    slept: list[float] = []

    async def record(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(http_module.anyio, "sleep", record)
    return slept


@respx.mock
async def test_get_verses_quotes_reference_and_sends_csv(backend, fixture):
    route = respx.get(f"{BASE}/v1/verses/John%203%3A16").respond(
        json=fixture("verses_john316_kjv_web")
    )
    payload = await backend.get_verses("John 3:16", translations=["kjv", "web"])
    assert payload["reference"] == "John 3:16"
    assert route.calls.last.request.url.params["translations"] == "kjv,web"


@respx.mock
async def test_get_verses_omits_translations_when_not_given(backend, fixture):
    route = respx.get(f"{BASE}/v1/verses/Psalm%2023%3A1-3").respond(
        json=fixture("verses_psalm23_range")
    )
    await backend.get_verses("Psalm 23:1-3")
    assert "translations" not in route.calls.last.request.url.params


@respx.mock
@pytest.mark.parametrize(
    ("status", "fixture_name", "code"),
    [
        (400, "error_unparseable_reference", "unparseable_reference"),
        (404, "error_unknown_book", "unknown_book"),
        (404, "error_unknown_translation", "unknown_translation"),
    ],
)
async def test_error_envelope_becomes_api_error(
    backend, fixture, status, fixture_name, code
):
    respx.get(url__startswith=f"{BASE}/v1/verses/").respond(
        status_code=status, json=fixture(fixture_name)
    )
    with pytest.raises(ApiError) as excinfo:
        await backend.get_verses("whatever")
    assert excinfo.value.status == status
    assert excinfo.value.code == code
    assert excinfo.value.message


@respx.mock
async def test_connect_error_becomes_unreachable(backend):
    respx.get(url__startswith=f"{BASE}/v1/").mock(
        side_effect=httpx.ConnectError("refused")
    )
    with pytest.raises(ConcordUnreachable) as excinfo:
        await backend.get_verses("John 3:16")
    assert excinfo.value.url == BASE


@respx.mock
async def test_semantic_sends_translation_explicitly(backend, fixture):
    route = respx.get(f"{BASE}/v1/semantic-search").respond(
        json=fixture("semantic_anxious")
    )
    await backend.semantic_search("do not be anxious", limit=3)
    params = route.calls.last.request.url.params
    assert params["q"] == "do not be anxious"
    assert params["limit"] == "3"
    assert params["translation"] == "KJV"  # config default, never the endpoint's WEB
    assert "min_score" not in params


@respx.mock
async def test_semantic_passes_caller_translation_and_min_score(backend, fixture):
    route = respx.get(f"{BASE}/v1/semantic-search").respond(
        json=fixture("semantic_anxious")
    )
    await backend.semantic_search("shepherd", translation="WEB", min_score=0.5)
    params = route.calls.last.request.url.params
    assert params["translation"] == "WEB"
    assert params["min_score"] == "0.5"


@respx.mock
async def test_503_retries_once_honoring_retry_after(backend, fixture, no_sleep):
    route = respx.get(f"{BASE}/v1/semantic-search")
    route.side_effect = [
        httpx.Response(503, headers={"Retry-After": "2"}),
        httpx.Response(200, json=fixture("semantic_anxious")),
    ]
    payload = await backend.semantic_search("do not be anxious")
    assert payload["count"] == 3
    assert route.call_count == 2  # exactly one retry
    assert no_sleep == [2.0]


@respx.mock
async def test_503_twice_raises_busy_with_no_retry_storm(backend, no_sleep):
    route = respx.get(f"{BASE}/v1/semantic-search")
    route.side_effect = [
        httpx.Response(503, headers={"Retry-After": "2"}),
        httpx.Response(503, headers={"Retry-After": "7"}),
    ]
    with pytest.raises(ConcordBusy) as excinfo:
        await backend.semantic_search("do not be anxious")
    assert route.call_count == 2  # exactly two requests, never a storm
    assert excinfo.value.retry_after == 7.0


@respx.mock
async def test_503_retry_sleep_is_capped_at_timeout(fixture, no_sleep):
    backend = HttpBackend(Config(concord_url=BASE, timeout_s=4.0))
    route = respx.get(f"{BASE}/v1/semantic-search")
    route.side_effect = [
        httpx.Response(503, headers={"Retry-After": "60"}),
        httpx.Response(200, json=fixture("semantic_anxious")),
    ]
    await backend.semantic_search("do not be anxious")
    assert no_sleep == [4.0]


@respx.mock
async def test_503_without_retry_after_uses_default(backend, fixture, no_sleep):
    route = respx.get(f"{BASE}/v1/semantic-search")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json=fixture("semantic_anxious")),
    ]
    await backend.semantic_search("do not be anxious")
    assert no_sleep == [http_module.DEFAULT_RETRY_AFTER_S]


@respx.mock
async def test_get_verses_503_is_not_retried(backend, fixture, no_sleep):
    route = respx.get(url__startswith=f"{BASE}/v1/verses/")
    route.side_effect = [httpx.Response(503, json=fixture("error_unknown_book"))]
    with pytest.raises(ApiError):
        await backend.get_verses("John 3:16")
    assert route.call_count == 1
    assert no_sleep == []


@respx.mock
async def test_cross_references_params(backend, fixture):
    route = respx.get(f"{BASE}/v1/cross-references/John%203%3A16").respond(
        json=fixture("xrefs_john316_text")
    )
    await backend.cross_references("John 3:16", include_text=True, limit=10)
    params = route.calls.last.request.url.params
    assert params["include_text"] == "true"
    assert params["translation"] == "KJV"  # explicit default, as with semantic
    assert params["limit"] == "10"


@respx.mock
async def test_cross_references_omits_translation_without_text(backend, fixture):
    route = respx.get(f"{BASE}/v1/cross-references/John%203%3A16").respond(
        json=fixture("xrefs_john316")
    )
    await backend.cross_references("John 3:16")
    params = route.calls.last.request.url.params
    assert "include_text" not in params
    assert "translation" not in params


@respx.mock
async def test_word_study_sends_no_text_param(backend, fixture):
    route = respx.get(f"{BASE}/v1/verses/John%2021%3A15/words").respond(
        json=fixture("words_john2115")
    )
    await backend.word_study("John 21:15")
    assert "text" not in route.calls.last.request.url.params


@respx.mock
async def test_strongs_verses_params(backend, fixture):
    route = respx.get(f"{BASE}/v1/strongs/G5368/verses").respond(
        json=fixture("strongs_g5368_verses_p2")
    )
    await backend.strongs_verses("G5368", limit=2)
    params = route.calls.last.request.url.params
    assert params["limit"] == "2"
    assert params["translation"] == "KJV"


@respx.mock
async def test_topic_verses_without_text_omits_translation(backend, fixture):
    route = respx.get(f"{BASE}/v1/topics/care/verses").respond(
        json=fixture("topic_care_verses")
    )
    await backend.topic_verses("care", include_text=False)
    params = route.calls.last.request.url.params
    assert params["include_text"] == "false"
    assert "translation" not in params


@respx.mock
async def test_places_for_passage_url(backend, fixture):
    route = respx.get(f"{BASE}/v1/verses/Genesis%204%3A16/places").respond(
        json=fixture("places_gen416")
    )
    payload = await backend.places_for_passage("Genesis 4:16")
    assert payload["total"] == 1
    assert not route.calls.last.request.url.params


@respx.mock
async def test_random_sends_translation_explicitly_and_filters(backend, fixture):
    route = respx.get(f"{BASE}/v1/random").respond(json=fixture("random_gen_ylt"))
    await backend.random_verse(book="Gen", testament="ot")
    params = route.calls.last.request.url.params
    assert params["translation"] == "KJV"  # explicit default, house rule
    assert params["book"] == "Gen"
    assert params["testament"] == "ot"  # passed through; Concord validates


@respx.mock
async def test_random_omits_absent_filters(backend, fixture):
    route = respx.get(f"{BASE}/v1/random").respond(json=fixture("random_gen_ylt"))
    await backend.random_verse()
    params = route.calls.last.request.url.params
    assert "book" not in params and "testament" not in params
