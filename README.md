# concord-mcp

Ask your LLM a Scripture question and get the verse looked up, not half-remembered.
concord-mcp is a read-only [MCP](https://modelcontextprotocol.io) server that exposes
[Concord](https://github.com/kbennett2000/concord)'s `/v1` Scripture API as tools for
any MCP-capable client — Claude Desktop, Claude Code, MCP Inspector. Verse text,
semantic search, places, journeys, and original-language word study all come from a
Concord you control, on your LAN or in-process on your machine, fully offline once set
up. The assistant inherits Concord's honesty about uncertainty instead of inventing
coordinates and citations.

**Status: pre-v1 — slice 1 in progress.**

The full design lives in [docs/v1/SPEC.md](docs/v1/SPEC.md).
