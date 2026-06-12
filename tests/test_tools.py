"""The MCP layer end to end, over the SDK's in-memory client session."""

import httpx
import pytest
import respx
from mcp.shared.memory import create_connected_server_and_client_session

from concord_mcp.backends import HttpBackend
from concord_mcp.config import Config
from concord_mcp.server import create_server

BASE = "http://concord.test"

pytestmark = pytest.mark.anyio


@pytest.fixture
def server():
    config = Config(concord_url=BASE)
    return create_server(config, HttpBackend(config))


async def test_lists_exactly_six_read_only_tools(server):
    async with create_connected_server_and_client_session(server) as session:
        result = await session.list_tools()

    tools = {tool.name: tool for tool in result.tools}
    assert set(tools) == {
        "lookup_verse",
        "search_by_meaning",
        "cross_references",
        "word_study",
        "strongs_entry",
        "topic_verses",
    }
    for tool in tools.values():
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is False


async def test_descriptions_carry_the_search_disambiguation(server):
    async with create_connected_server_and_client_session(server) as session:
        result = await session.list_tools()

    by_name = {tool.name: tool.description for tool in result.tools}
    # The three-search routing rule (SPEC §4) must be stated plainly in both.
    assert "search_by_meaning" in by_name["lookup_verse"]
    assert "search_keyword" in by_name["lookup_verse"]
    assert "lookup_verse" in by_name["search_by_meaning"]
    assert "search_keyword" in by_name["search_by_meaning"]
    # The S3 routing pairs: curated index vs similarity, verse-words vs lexicon.
    assert "topic_verses" in by_name["search_by_meaning"]
    assert "search_by_meaning" in by_name["topic_verses"]
    assert "strongs_entry" in by_name["word_study"]
    assert "word_study" in by_name["strongs_entry"]


@respx.mock
async def test_lookup_verse_returns_tagged_text(server, fixture):
    respx.get(f"{BASE}/v1/verses/John%203%3A16").respond(
        json=fixture("verses_john316_kjv_web")
    )
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool(
            "lookup_verse",
            {"reference": "John 3:16", "translations": ["kjv", "web"]},
        )

    assert result.isError is False
    text = result.content[0].text
    assert "John 3:16 (KJV) — For God so loved the world," in text
    assert "John 3:16 (WEB) — " in text


@respx.mock
async def test_search_by_meaning_returns_scored_lines(server, fixture):
    respx.get(f"{BASE}/v1/semantic-search").respond(json=fixture("semantic_anxious"))
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool(
            "search_by_meaning", {"query": "do not be anxious"}
        )

    text = result.content[0].text
    assert text.startswith('Top 3 verses for "do not be anxious" (KJV):')
    assert "Philippians 4:6 (KJV) [score 0.93] — " in text


@respx.mock
async def test_limit_is_clamped_to_max_results(server, fixture):
    route = respx.get(f"{BASE}/v1/semantic-search").respond(
        json=fixture("semantic_anxious")
    )
    async with create_connected_server_and_client_session(server) as session:
        await session.call_tool("search_by_meaning", {"query": "shepherd", "limit": 99})

    assert route.calls.last.request.url.params["limit"] == "25"


@respx.mock
async def test_bad_reference_returns_correctable_text(server, fixture):
    respx.get(url__startswith=f"{BASE}/v1/verses/").respond(
        status_code=404, json=fixture("error_unknown_book")
    )
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("lookup_verse", {"reference": "Hezekiah 3:16"})

    text = result.content[0].text
    assert "unknown_book" in text
    assert "Unknown book 'Hezekiah'." in text
    assert "'John 3:16'" in text  # restates the expected format with an example


@respx.mock
async def test_unreachable_concord_names_the_url_and_the_fix(server):
    respx.get(url__startswith=f"{BASE}/v1/").mock(
        side_effect=httpx.ConnectError("refused")
    )
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("lookup_verse", {"reference": "John 3:16"})

    text = result.content[0].text
    assert f"Concord isn't reachable at {BASE}." in text
    assert "CONCORD_URL" in text


@respx.mock
async def test_word_study_end_to_end_labels_verse_blocks(server, fixture):
    respx.get(f"{BASE}/v1/verses/John%2021%3A15-17/words").respond(
        json=fixture("words_john211517")
    )
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("word_study", {"reference": "John 21:15-17"})

    text = result.content[0].text
    assert "John 21:15:" in text and "John 21:17:" in text
    assert "ἀγαπάω (agapaō, G25, V-PAI-2S)" in text


@respx.mock
async def test_topic_verses_ambiguous_returns_candidates(server, fixture):
    respx.get(f"{BASE}/v1/topics").respond(json=fixture("topics_q_faith"))
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("topic_verses", {"topic": "fait"})

    text = result.content[0].text
    assert 'Several topical-Bible entries match "fait"' in text
    assert "faithfulness (FAITHFULNESS)" in text


@respx.mock
async def test_topic_verses_follows_and_labels_a_redirect(server, fixture):
    respx.get(f"{BASE}/v1/topics").respond(json=fixture("topics_q_kindness"))
    respx.get(f"{BASE}/v1/topics/care").respond(json=fixture("topic_care_detail"))
    respx.get(f"{BASE}/v1/topics/care/verses").respond(
        json=fixture("topic_care_verses")
    )
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("topic_verses", {"topic": "kindness"})

    text = result.content[0].text
    assert text.startswith('Nave\'s lists "KINDNESS" as "See CARE" — showing CARE.')
    assert "Topic: CARE (Nave's Topical Bible) — 4 verses:" in text


@respx.mock
async def test_strongs_entry_with_occurrences(server, fixture):
    respx.get(f"{BASE}/v1/strongs/G5368").respond(json=fixture("strongs_g26"))
    respx.get(f"{BASE}/v1/strongs/G5368/verses").respond(
        json=fixture("strongs_g5368_verses_p2")
    )
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool(
            "strongs_entry", {"strongs_id": "G5368", "include_verses": True}
        )

    text = result.content[0].text
    assert text.startswith("G26 — ἀγάπη (agapē), Greek — love")
    assert "Occurs in 3 verses (SBLGNT). Showing 2:" in text


@respx.mock
async def test_unknown_strongs_id_self_corrects(server, fixture):
    respx.get(url__startswith=f"{BASE}/v1/strongs/").respond(
        status_code=404, json=fixture("error_unknown_strongs")
    )
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("strongs_entry", {"strongs_id": "Q99"})

    text = result.content[0].text
    assert "unknown_strongs" in text
    assert "'G26' (Greek) or 'H7225' (Hebrew)" in text
