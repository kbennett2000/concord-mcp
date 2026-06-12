# CLAUDE.md — concord-mcp

## What this is

A **read-only MCP (Model Context Protocol) server** exposing Concord's `/v1`
Scripture API as tools for LLM clients (Claude Desktop, Claude Code, MCP
Inspector, and any MCP-speaking client). It is a sibling of songbird: a
consumer of the `/v1` contract, never a fork of the engine.

It is also the **destination codebase for the planned `concord-tutorial-ai`
course**. A tutorial graduate must be able to read this repo top to bottom in
one sitting. Smallness and clarity beat cleverness everywhere. If a change
makes the repo harder for that reader, it needs a very good reason.

## How we work

- **Spec first.** `docs/v1/SPEC.md` is the source of truth. Read it and this
  file before any work. Enter Plan Mode before implementing any slice, and
  present the plan for approval before writing code.
- **One PR per slice.** Smallest reviewable, load-bearing unit. The slice plan
  is SPEC §11. Branches: `feat/<short-name>` off `main`. Conventional commits
  (`feat(tools): …`, `fix(http): …`, `docs: …`).
- **Bobby (kbennett2000) merges every PR.** Never self-merge. Never push to
  `main` after the bootstrap commit. Never force-push, anywhere, ever.
- **Draft PRs at human gates.** Any PR whose checklist includes a step only
  Bobby can perform (live verification against his LAN Concord, client
  testing in Claude Desktop) opens as a GitHub **draft** until that step is
  checked off.
- **Read the source, don't guess.** Response shapes come from Concord's
  `docs/API.md` and its `bible_api` schema code — read them, never invent
  fields. If the spec and observed reality disagree, stop and surface it; the
  spec is amended in the same PR, never silently drifted from.
- **ADRs.** Any architectural decision (new dependency, new transport,
  contract change, tool-surface change) gets `docs/adr/NNNN-*.md` in the same
  PR. ADRs 0001–0004 are binding.
- **Stop and report.** Every slice ends with: verification output, test
  counts, the PR URL, and any deviations with rationale.

## Hard rules

- **Read-only, forever.** This server must never gain a tool that writes,
  mutates, or deletes anything — in Concord or anywhere else. Every tool
  carries `readOnlyHint: true` and `destructiveHint: false`. If a request
  implies otherwise, refuse and flag it.
- **No telemetry, no phone-home.** Parity with Concord. The only network
  traffic is to the configured Concord instance, and only in `http` backend
  mode.
- **CI is hermetic.** Lint + unit tests only: synthetic fixtures, no network,
  no live Concord, no model downloads. Live integration tests are local-only,
  env-gated, and pytest-marked (`-m integration`).
- **Never build Concord from source as a verification gate.** Pull the
  published image (`docker pull ghcr.io/kbennett2000/concord:<tag>`). Source
  builds wedge modest machines; this rule was earned the hard way.
- **Nothing copyrighted is ever committed.** `data/private/` is gitignored.
  Fixtures use synthetic or public-domain verse text only.

## Stack

- Python 3.12 (pinned in `.python-version` — keep matching Concord's pin),
  uv-managed, single package under `src/concord_mcp/`.
- MCP Python SDK (`mcp`, FastMCP server API), **stdio** transport.
- `httpx` for the HTTP backend; `bible-core`/`bible-semantic` (pinned git
  subdirectory deps) for the in-process backend from slice 2 onward.
- `ruff` for lint + format — scoped to `src/` and `tests/`; never sweep
  unrelated files into a feature diff.
- `pytest` + `respx` for unit tests.

## Commands

- `uv sync` — install
- `uv run pytest` — unit tests (CI-equivalent)
- `uv run pytest -m integration` — live tests against `CONCORD_URL` (local only)
- `uv run ruff check . && uv run ruff format --check .` — lint gate
- `uv run concord-mcp` — run the server on stdio
- `npx @modelcontextprotocol/inspector uv run concord-mcp` — manual harness

## Conventions

- Run `ruff format` before every commit — formatting never lands as its
  own commit.
- **Tool descriptions are product copy for the model.** Imperative,
  example-bearing, maintained beside their tools. Changing one is a reviewed
  change with rationale, never a drive-by edit.
- Every verse in a tool response is tagged `Book C:V (TRANSLATION)`. Default
  result limits stay small; the server clamps at `CONCORD_MCP_MAX_RESULTS`.
- **Honesty passthrough.** Place `status` values and journey `source`
  attributions are surfaced verbatim. Never fabricate coordinates, routes, or
  certainty the data doesn't claim.
- Versioning: semver. Package version, `CHANGELOG.md`, and git tag are
  reconciled in a release-prep PR; tags push only on explicit authorization
  (two-stop release gate).

## Documentation voice

README and docs follow the family voice: show the win before the explanation,
write for one real reader, no unexplained tooling jargon, just-in-time not
just-in-case. The README is written for the non-technical reader;
developer-facing content lives in `docs/DEVELOPERS.md`.
