# concord-mcp — v1 specification

Status: **draft, pre-implementation**. This document is the source of truth;
deviations discovered during implementation are surfaced and amended here in
the same PR.

## 1. What this is

concord-mcp is a read-only MCP server that lets any MCP-capable LLM client
answer Scripture questions from **Concord's data instead of the model's
memory**. The model stops *recalling* the Bible (badly) and starts *looking it
up* (exactly). Verse text, semantic search, cross-references, places,
journeys, topics, and original-language word data all come over the wire from
a Concord the operator controls — on their LAN or in-process on their machine
— and the assistant inherits Concord's honesty about uncertainty.

Positioning: a sibling of songbird in the "Building on Concord" ecosystem,
and the destination codebase for `concord-tutorial-ai`.

## 2. Goals and non-goals

**Goals (v1):**

- Expose a curated, well-described tool surface over Concord `/v1` (ADR 0003).
- Run two ways behind one tool surface (ADR 0002): `http` mode against any
  reachable Concord, and `inprocess` mode importing `bible-core` /
  `bible-semantic` directly with no Concord container running.
- Fully offline operation in both modes once set up. No telemetry.
- Be small and readable end to end — the tutorial-graduate test.
- Ship an eval set proving an LLM can actually use the tools.

**Non-goals (v1):**

- Any write/mutate capability. Permanently out of scope, not just v1.
- Streamable-HTTP transport (LAN-served MCP). Deferred — see §12.
- Notes endpoints. The stock Concord image ships zero notes; tools for
  operator-supplied private notes are deferred.
- Caching, auth, multi-Concord federation.

## 3. Architecture

```
MCP client (Claude Desktop / Claude Code / Inspector)
        │  stdio (JSON-RPC)
        ▼
  concord-mcp  (FastMCP server)
        │
        │  ConcordBackend protocol
        ├──────────────► HttpBackend ──── httpx ───► Concord /v1 (e.g. LAN)
        └──────────────► InProcessBackend ─ import ► bible-core / bible-semantic
                                                     (bible.db + ONNX artifacts)
```

- Single package: `src/concord_mcp/` — `server.py` (FastMCP app + tool
  registration + entry point), `config.py`, `render.py` (response
  formatting), `backends/` (`base.py` protocol, `http.py`, `inprocess.py`).
  Final module layout is confirmed in the slice 1 plan; the constraint is
  that it stays readable, not that it matches this sketch exactly.
- **Backend selection** via `CONCORD_MCP_BACKEND` (`http` default).
- `HttpBackend` codes against the documented `/v1` shapes in Concord's
  `docs/API.md` — read at implementation time, never assumed.
- `InProcessBackend` imports `bible-core` (and `bible-semantic` when its
  artifacts are present) as pinned git-subdirectory dependencies. Database
  and model acquisition is ADR 0004. If semantic artifacts are absent,
  `search_by_meaning` returns a clear error pointing at `http` mode or the
  acquisition steps — it degrades, it doesn't crash the server.
- Language is Python despite the MCP ecosystem's TypeScript lean — ADR 0001
  records why.

## 4. Tool surface (the contract)

Ten tools, curated from Concord's 27 endpoints (ADR 0003). Names are
unprefixed; the server registers as `concord`. All tools carry annotations
`readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false`;
all are `idempotentHint: true` except `random_verse`.

| Tool | Parameters | Backs onto | One-line description (draft) |
|---|---|---|---|
| `lookup_verse` | `reference`, `translations?` | `GET /v1/verses/{ref}` | Fetch the exact text of a verse, range, list, or chapter, in one or more translations. |
| `search_keyword` | `query`, `translations?`, `limit?` | `GET /v1/search` | Find verses containing an exact word or phrase. |
| `search_by_meaning` | `query`, `translation?`, `limit?`, `min_score?` | `GET /v1/semantic-search` | Find verses by idea or theme, even when they don't contain the words — e.g. "verses about anxiety". |
| `cross_references` | `reference`, `include_text?`, `limit?` | `GET /v1/cross-references/{ref}` | List the passages traditionally linked to a verse. |
| `places_for_passage` | `reference` | `GET /v1/verses/{ref}/places` | List the places a passage names, with coordinates and an honesty status for each. |
| `journeys` | `journey_id?` | `GET /v1/journeys`, `GET /v1/journeys/{id}` | Browse the curated biblical journeys, or get one journey's ordered stops with source and dating. |
| `topic_verses` | `topic`, `include_text?`, `limit?` | `GET /v1/topics*` | Look up a topical-Bible subject (Nave's) by name and return its curated verses. |
| `word_study` | `reference` | `GET /v1/verses/{ref}/words` | Show a verse's original-language words — surface form, Strong's number, morphology, gloss. |
| `strongs_entry` | `strongs_id`, `include_verses?`, `limit?` | `GET /v1/strongs/{id}`, `GET /v1/strongs/{id}/verses` | Get a Strong's lexicon entry — lemma, transliteration, definition — and optionally where it occurs. |
| `random_verse` | `book?`, `testament?`, `translation?` | `GET /v1/random` | Fetch a random verse, optionally filtered by book or testament. |

**Description rules** (descriptions are the product):

- Written for the model: imperative, concrete, with at least one inline
  example of a valid argument (`reference` examples: `John 3:16`,
  `Genesis 1:1-5`, `Psalm 23`).
- State what comes back, not how it's fetched. No HTTP jargon in
  descriptions.
- State the disambiguation between the three searches plainly:
  `lookup_verse` when you have a reference, `search_keyword` for exact
  wording, `search_by_meaning` for ideas.
- Each parameter description carries its default and its cap.

**Exemplar (full model-facing description, `search_by_meaning`):**

> Find Bible verses by meaning rather than exact wording. Use this when the
> question is about an idea, theme, or feeling — "verses about anxiety",
> "the good shepherd", "forgiving people who wronged you" — and you don't
> already have a verse reference. Results are ranked by closeness of meaning
> and can be returned in any loaded translation via `translation` (default
> KJV). Returns up to `limit` verses (default 10, max 25), each tagged with
> its reference and translation so you can cite it exactly. If you already
> know the reference, use `lookup_verse` instead; if you need an exact word
> or phrase match, use `search_keyword`.

## 5. Response format rules

- **Compact plain text**, model-quotable and token-frugal — not raw JSON
  dumps. Structured output is deferred for v1: dual text+structured isn't
  cheap in MCP SDK 1.x; revisit at SDK v2.
- Every verse line: `John 3:16 (KJV) — For God so loved the world…`. The
  reference + translation tag is non-negotiable; it is what lets the model
  cite verifiably.
- Default `limit` 10 where applicable; server-side clamp at
  `CONCORD_MCP_MAX_RESULTS` (25). Result sets state truncation explicitly:
  when the API provides a true total, "showing {n} of {total}"; when it
  doesn't (semantic search), "top {n} matches — raise limit or add
  min_score to narrow". Keyword search (S3) uses whichever applies per
  Concord's actual response shape, read at S3 time.
- **Honesty passthrough:**
  - Place lines carry status verbatim: `identified` / `disputed` /
    `unknown` / `symbolic` / `multiple`. An `unknown` place renders as
    "location genuinely unknown — no coordinates", never as a guessed pin
    and never as 0,0.
  - Journey output opens with: "one commonly proposed reconstruction
    (source: …)" plus dating, before the ordered stops.
- Word-study lines: `position. surface — lemma (transliteration, strongs_id,
  morph) — gloss`, one token per line; an untagged token renders
  `position. surface — [untagged]`. The upstream tokens payload carries no
  verse labels; verse boundaries are detected by `position` resets. When the
  requested reference expands to an explicit verse list whose length equals
  the block count, blocks are labeled with their verses; on any mismatch
  (token-less verse, whole-chapter or cross-chapter span) blocks render
  unlabeled, separated by blank lines — never best-effort labels. Output is
  capped at 10 verse blocks: "showing first 10 of {n} verses — request a
  narrower range".
- Cross-reference lines carry the target reference (ranges included), the
  community vote count verbatim (`Romans 5:8 (KJV) [votes 968] — …`), and —
  with `include_text` — the target's opening verse only, stated in the header.
- Strong's entries render lemma, transliteration, language (Greek/Hebrew),
  gloss, full definition, and the lexicon `source` attribution verbatim;
  occurrence lists are ordinary tagged verse lines with a true total.
- Topic output opens `Topic: {NAME} (Nave's Topical Bible) — {total} verses:`;
  "See X" redirects are followed one hop and labeled as such; ambiguous names
  return the candidate list (ids included) instead of verses.

## 6. Resources

Slice 5 registers two read-only MCP resources so clients can show what's
loaded without spending a tool call:

- `concord://translations` — the loaded translations with metadata.
- `concord://books` — the 66-book catalog.

## 7. Configuration

Every setting has a default; none are required for `http` mode against a
local Concord.

| Variable | Default | Meaning |
|---|---|---|
| `CONCORD_MCP_BACKEND` | `http` | `http` or `inprocess`. |
| `CONCORD_URL` | `http://localhost:8000` | Concord base URL (`http` mode). |
| `CONCORD_MCP_DEFAULT_TRANSLATION` | `KJV` | Used when the caller omits a translation. Mirrors Concord's default. Always sent explicitly to the semantic-search endpoint, which would otherwise default to WEB. |
| `CONCORD_MCP_TIMEOUT_S` | `10` | Per-request timeout (`http` mode). Aligned with Concord's semantic deadline. |
| `CONCORD_MCP_MAX_RESULTS` | `25` | Server-side clamp on any `limit`. |
| `BIBLE_DB_PATH` | `data/concord/bible.db` | Path to `bible.db` (`inprocess` mode). Matches the `make get-db` output (ADR 0004). |
| `CONCORD_SEMANTIC_ASSETS` | `data/concord/semantic` | Directory of semantic artifacts (`inprocess` mode): `model/` (tokenizer.json + `onnx/*.onnx`) and `embeddings.db`, as extracted by `make get-db` (ADR 0004). Relative paths resolve against the working directory. |

## 8. Errors

Errors are written for the model to self-correct from:

- Invalid reference → echo Concord's 4xx detail and restate the expected
  format with an example.
- Concord unreachable (`http` mode) → "Concord isn't reachable at {url}.
  Is it running? (docker compose up in the concord folder, or check
  CONCORD_URL.)"
- `503` + `Retry-After` from semantic search → surface as "Concord is busy;
  retry in {n}s" and honor one polite retry; no retry storms.
- Unknown or malformed Strong's id → echo Concord's detail and restate the
  id format with examples (`G26`, `H7225`) and where to find ids
  (`word_study`).
- Unknown topic id → restate that Nave's indexes classic subjects and point
  free-form ideas at `search_by_meaning`.
- Missing semantic artifacts (`inprocess`) → name the two fixes: switch to
  `http` mode, or run the acquisition steps (ADR 0004).
- Missing `bible.db` (`inprocess`) → name both fixes: run `make get-db`, or
  set `BIBLE_DB_PATH` (or switch to `http` mode). Affects both tools; the
  server still starts and answers with this error rather than crashing.

## 9. Testing

- **Unit (CI):** `respx`-mocked httpx against hand-written synthetic
  fixtures in `tests/fixtures/` whose shapes are transcribed from Concord's
  `docs/API.md`. Render-layer tests assert the format rules in §5,
  including the honesty passthrough lines. The MCP layer is exercised via
  the SDK's in-memory client session where the current SDK supports it.
- **Integration (local only):** `pytest -m integration` against a live
  `CONCORD_URL`; skipped unless the env var is set. The verification gate
  pulls the published GHCR image — never a source build.
- **Manual harness:** MCP Inspector
  (`npx @modelcontextprotocol/inspector uv run concord-mcp`).
- **CI:** ruff + unit tests only. Hermetic.

## 10. Security & privacy posture

Read-only by construction; every tool annotated accordingly. stdio transport
means the server is only reachable by the local client that spawned it. No
secrets, no auth tokens, no telemetry, no analytics. The only outbound
traffic is to `CONCORD_URL`, only in `http` mode. Logging stays local and
never leaves the machine.

## 11. Slice plan

One PR per slice; each lands green and reviewable on its own.

| # | Branch | Scope | Acceptance |
|---|---|---|---|
| S1 | `feat/http-skeleton` | FastMCP stdio server; backend protocol + `HttpBackend`; tools `lookup_verse` + `search_by_meaning` with full descriptions; config (§7); error rendering (§8); unit tests + fixtures; README quickstart with Claude Desktop and Claude Code config snippets. | Both tools answer correctly via MCP Inspector against a live Concord (Bobby-verified, draft PR until checked); CI green. |
| S2 | `feat/inprocess-backend` | `InProcessBackend` importing `bible-core` (+ optional `bible-semantic`); `make get-db` acquisition per ADR 0004; graceful semantic degradation. | Same two tools pass with no Concord container running; acquisition steps reproduced from scratch by Bobby. |
| S3 | `feat/study-tools` | `cross_references`, `word_study`, `strongs_entry`, `topic_verses` — both backends. | Unit-tested; Inspector spot-check on John 21:15-17 word study. |
| S4 | `feat/geo-journeys` | `places_for_passage`, `journeys`, `random_verse`. | Honesty lines verified against a known `unknown` place (land of Nod) and a journey's source attribution. |
| S5 | `feat/resources-polish` | MCP resources (§6); `evals/concord-mcp-evals.xml` — 10 read-only, multi-tool, verifiable QA pairs; README demo; CHANGELOG; release-prep. | Eval answers verified by hand; v1.0.0 tagged after explicit authorization (two-stop gate). |

## 12. Deferred (post-v1)

Streamable-HTTP transport for a LAN-served MCP endpoint; tools over
operator-supplied translator's notes; a `study_passage` MCP prompt that
orchestrates word study + cross-references + places; publishing
`bible-core` to PyPI; MCP registry listing.
