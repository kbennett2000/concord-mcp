# concord-mcp

Ask your LLM a Scripture question and get the verse looked up, not half-remembered.
concord-mcp is a read-only [MCP](https://modelcontextprotocol.io) server that exposes
[Concord](https://github.com/kbennett2000/concord)'s `/v1` Scripture API as tools for
any MCP-capable client — Claude Desktop, Claude Code, MCP Inspector. Verse text,
semantic search, places, journeys, and original-language word study all come from a
Concord you control, on your LAN or in-process on your machine, fully offline once set
up. The assistant inherits Concord's honesty about uncertainty instead of inventing
coordinates and citations.

**Status: pre-v1 — slice 1 under review.**

The full design lives in [docs/v1/SPEC.md](docs/v1/SPEC.md).

## Quickstart

You need a reachable [Concord](https://github.com/kbennett2000/concord) (its
quickstart is `docker compose up`) and [uv](https://docs.astral.sh/uv/). Then:

```bash
git clone https://github.com/kbennett2000/concord-mcp
cd concord-mcp
uv sync
```

The server talks to `http://localhost:8000` by default; point `CONCORD_URL` at your
Concord if it lives elsewhere (e.g. on your LAN).

### Claude Desktop

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "concord": {
      "command": "uv",
      "args": ["--directory", "/path/to/concord-mcp", "run", "concord-mcp"],
      "env": { "CONCORD_URL": "http://<your-concord-host>:port-number" }
    }
  }
}
```

Restart Claude Desktop, then try: *"What does John 3:16 say in the WEB?"* — and watch
it call `lookup_verse` instead of reciting from memory.

### Claude Code

```bash
claude mcp add concord --env CONCORD_URL=http://<your-concord-host>:port-number \
  -- uv run --directory /path/to/concord-mcp concord-mcp
```

### MCP Inspector (manual harness)

```bash
npx @modelcontextprotocol/inspector -e CONCORD_URL=http://<your-concord-host>:port-number uv run concord-mcp
```

## Tools (slice 1)

- `lookup_verse` — exact text of a verse, range, list, or chapter, in one or more
  translations. `John 3:16`, `Genesis 1:1-5`, `Psalm 23`.
- `search_by_meaning` — verses by idea or theme ("verses about anxiety"), ranked by
  closeness of meaning, even when they don't contain the words.

Every verse comes back tagged `Book Chapter:Verse (TRANSLATION)`, so citations are
verifiable. The rest of the ten-tool surface lands slice by slice — see
[SPEC §11](docs/v1/SPEC.md#11-slice-plan).
