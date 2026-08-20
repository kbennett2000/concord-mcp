# Changelog

All notable changes to concord-mcp. Versions follow semver; the format
loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed
- MCP Python SDK v2 (`mcp>=2.0.0,<3`; ADR 0005, closes #1): `FastMCP` →
  `MCPServer`. Tool surface, descriptions, and payloads are unchanged.
- Resource reads (`concord://translations`, `concord://books`) render
  backend errors as self-correctable text instead of raising — SDK v2 would
  otherwise replace the message with a generic one.
- SPEC §5: structured output stays deferred (moved to §12) — v2 did not make
  dual text+structured output cheaper.

## [1.0.0] — 2026-06-12

The complete v1 surface: ten read-only tools over Concord's `/v1` API, two
backends behind one protocol, two MCP resources, and a verified ten-question
eval set. Read-only forever; no telemetry; fully offline once set up.

### S1 — HTTP skeleton (`feat/http-skeleton`, PR #2)
- FastMCP stdio server; `ConcordBackend` protocol + `HttpBackend` (httpx).
- `lookup_verse` and `search_by_meaning` with the §4 contract descriptions.
- §7 config from env; §8 error rendering with the single polite 503 retry.
- Hermetic test rails: respx fixtures transcribed from Concord's `docs/API.md`.

### S2 — In-process backend (`feat/inprocess-backend`, PR #4)
- `InProcessBackend` importing `bible-core` + `bible-semantic` (pinned to
  concord v1.2.0); no container, no network.
- `make get-db`: artifact extraction from the published GHCR image (ADR 0004)
  into `data/concord/`.
- Graceful degradation: missing artifacts answer with the fixes, never crash.
- The parity suite: one scenario set, both backends, byte-equal payloads.

### S3 — Study tools (`feat/study-tools`, PR #5)
- `cross_references` (votes shown), `word_study` (guarded verse-block labels,
  10-verse cap), `strongs_entry` (id normalization), `topic_verses`
  (did-you-mean candidates, labeled "See X" redirects).

### S4 — Geography, journeys, random (`feat/geo-journeys`, PR #6)
- `places_for_passage` with the five-status honesty rendering — coordinates
  only for `identified`/`disputed`; `unknown` stays honestly unmapped.
- `journeys`: list + detail with the data's reconstruction note verbatim.
- `random_verse` (`idempotentHint: false` — the surface's one exception).

### S5a — Surface completion (`feat/complete-surface`, PR #7)
- `search_keyword`: the third leg of the routing triple, with excerpt-honest
  snippets and multi-translation side-by-side results.
- MCP resources `concord://translations` and `concord://books` (per-read).
- The server instructions rewritten to route all ten tools.

### S5b — Release prep (`feat/release-prep`, PR #8)
- `evals/concord-mcp-evals.xml` + manual protocol; CHANGELOG; version 1.0.0.

### Post-prep — Beginner-first front door (`feat/front-door`, PR #9)
- README rewritten for the non-technical reader; everything technical moved
  intact to `docs/DEVELOPERS.md`; the family banner (`docs/banner.svg`,
  "looked up, never made up").

### Findings ledger
Things the read-the-source rule (and the parity suite) caught along the way:
- **S2:** Concord's canonical book name is "Psalms" — the S1 fixture had
  invented "Psalm 23:1", which no live Concord would return. Caught by the
  first parity run; fixture corrected.
- **S3:** `lookup_verse`'s original example `Romans 3:23,6:23` was invalid —
  Concord's grammar rejects cross-chapter verse lists. A model copying our
  own example would have gotten a 400. Corrected to `Romans 3:23,25`.
- **S3:** `/v1/verses/{ref}/words` returns a flat token list with no verse
  labels; concord-mcp reconstructs verse blocks guardedly (labels only on an
  exact count match). Upstream enhancement filed: kbennett2000/concord#69.
- **S4 gate:** Concord validates `testament` strictly as `ot|nt` — a
  `testament=old` filter 422s rather than matching; checklists and
  descriptions say 'OT' or 'NT'.
- **S5a:** `search_keyword` had been referenced by two shipped tool
  descriptions since S1 but was never assigned a slice — recorded and
  shipped in the §11 amendment.
