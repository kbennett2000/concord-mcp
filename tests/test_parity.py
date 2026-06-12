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
