# ADR 0001 — Standalone repo, written in Python

Status: accepted · 2026-06-12

## Context

Concord is deliberately scoped: the engine, nothing else. Everything built on
it (songbird, the tutorials) lives in its own repo and consumes the `/v1`
contract. concord-mcp could instead live as a fourth package inside Concord's
uv monorepo. Separately, the MCP ecosystem's general recommendation leans
TypeScript — and our tutorial graduates know JavaScript, not Python.

## Decision

concord-mcp is a **standalone public repo** and it is written in **Python**.

- Standalone: it consumes the `/v1` contract exactly like songbird, gets its
  own release cadence (the MCP SDK moves faster than Concord), slots into the
  README's "Building on Concord" list, and stays small enough for a
  `concord-tutorial-ai` graduate to read top to bottom — no monorepo
  spelunking.
- Python: the in-process backend (ADR 0002) imports `bible-core` and
  `bible-semantic` directly, which is a hard requirement only Python can
  satisfy. The tutorial audience doesn't *write* this repo, they *read* it at
  the end of the course — and a small FastMCP server of decorated functions
  is readable to someone who just learned fetch-and-render JavaScript.

## Consequences

- Cross-repo coupling is managed by pinning: git-subdirectory deps on a
  Concord tag for in-process mode, and the `/v1` contract (additive by
  promise) for HTTP mode.
- Independent versioning; this repo can ship weekly while Concord ships
  quarterly.
- We accept the ecosystem-default-TS tradeoff knowingly; revisit only if a
  client-compatibility problem actually materializes.
