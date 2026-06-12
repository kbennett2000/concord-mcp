# ADR 0002 — Dual backend behind one tool surface; HTTP ships first

Status: accepted · 2026-06-12

## Context

There are two real deployment shapes. (1) A Concord already running and
reachable — the LAN server case — where the MCP server should be a thin
client. (2) A laptop/desktop with an MCP client but no desire to run a
container — where `bible-core` and `bible-semantic`, which have zero web
dependencies, can be imported in-process so one Python process serves
everything from `bible.db` and the ONNX artifacts directly.

## Decision

One tool surface, two interchangeable backends behind a small
`ConcordBackend` protocol, selected by `CONCORD_MCP_BACKEND`:

- `http` (default) — httpx client against `CONCORD_URL`. **Ships in slice 1**
  because it depends on nothing but a reachable Concord, exercises the full
  tool surface immediately, and is the mode the tutorial will mirror.
- `inprocess` — imports `bible-core` (+ `bible-semantic` when artifacts are
  present). Ships in slice 2. Missing semantic artifacts degrade
  `search_by_meaning` with an actionable error; they never crash the server.

## Consequences

- The backend abstraction exists from day one, so tools are written once.
- HTTP mode inherits Concord's load-shedding: `503` + `Retry-After` is
  surfaced to the model as "busy, retry in {n}s" with at most one polite
  retry.
- In-process mode creates a data-acquisition problem (db + model artifacts
  live in the image, not git) — resolved in ADR 0004.
- Behavioral parity between backends is a test obligation: the same fixture
  scenarios run against both from slice 2 onward.
