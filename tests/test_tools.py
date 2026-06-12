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


async def test_lists_exactly_two_read_only_tools(server):
    async with create_connected_server_and_client_session(server) as session:
        result = await session.list_tools()

    tools = {tool.name: tool for tool in result.tools}
    assert set(tools) == {"lookup_verse", "search_by_meaning"}
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
