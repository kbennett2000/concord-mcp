# ADR 0005 — MCP Python SDK v2

Status: accepted · 2026-08-20

## Context

v1.0.0 shipped on the MCP Python SDK 1.x line (`mcp>=1.27.2,<2`), with a
note (issue #1, SPEC §5) to migrate once v2 went stable and to revisit the
structured-output deferral at that point. `mcp 2.0.0` reached PyPI on
2026-07-28.

Checked against the installed packages, not the release notes:

- The high-level server moved: `mcp.server.fastmcp.FastMCP` →
  `mcp.server.mcpserver.MCPServer`. The old path is gone outright — no
  deprecation shim, a hard `ModuleNotFoundError`.
- `@tool()` and `@resource()` are signature-compatible; `ToolAnnotations`
  still accepts `readOnlyHint=…` on construction (camelCase is now an
  alias; attribute *reads* are snake_case). `run()` is unchanged for stdio.
- The in-memory test helper `mcp.shared.memory.create_connected_server_and_client_session`
  was removed; `mcp.client.Client(server)` replaces it.
- One behavior change: an exception raised inside a resource reader now
  reaches the client as a generic "Error reading resource <uri>", where 1.x
  preserved our message.
- Structured output: unchanged semantics. A `-> str` tool emits its text as
  `structuredContent: {"result": …}` on both 1.x and 2.0; returning compact
  text *and* a typed structure still means a per-tool output model plus a
  hand-built `CallToolResult`. v2 did not make the dual form cheap.

## Decision

1. Pin `mcp>=2.0.0,<3` and rename the import and class. No other change to
   the tool surface, descriptions, or rendering — byte-equal payloads.
2. Resource readers render backend errors as text, the way every tool does,
   so `concord://translations` and `concord://books` keep SPEC §8's
   self-correctable messages under the SDK's new error wrapping.
3. Tests use `mcp.client.Client(server)` and the SDK's snake_case result
   fields.
4. **Structured output stays deferred.** The compact tagged-text contract
   (ADR 0003) is the product; adding ten output models and hand-built
   results would double the surface a tutorial graduate has to read for no
   gain the model has asked for. Moved from "revisit at v2" to SPEC §12.

## Consequences

- `uv.lock` gains `mcp-types`, `httpx2`, and `opentelemetry-api` (the SDK's
  own HTTP client and tracing API); `pydantic-settings` and `httpx-sse`
  leave. We keep our own `httpx` for `HttpBackend`; the two coexist. No
  telemetry is configured or emitted — the tracing dependency is inert
  without an exporter, which we never add.
- The SDK's major-version line is now a reviewed dependency boundary: the
  next major gets its own ADR, not a pin bump.
- If a client ever wants typed results, the path is known and small per
  tool (output model + `CallToolResult`); it is a deliberate widening, not a
  default.
