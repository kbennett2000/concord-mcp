# concord-mcp for developers

Everything technical lives here. The [README](../README.md) is written for the
non-technical reader; this page is the developer front door. The full design is
in [docs/v1/SPEC.md](v1/SPEC.md), the architectural decisions in
[docs/adr/](adr/), the verified eval set in [evals/](../evals/), and the
release history in [CHANGELOG.md](../CHANGELOG.md).

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
it call `lookup_verse` instead of reciting from memory. The server also exposes two
resources — `concord://translations` and `concord://books` — so the client can show
what's loaded without spending a tool call.

### Claude Code

```bash
claude mcp add concord --env CONCORD_URL=http://<your-concord-host>:port-number \
  -- uv run --directory /path/to/concord-mcp concord-mcp
```

### MCP Inspector (manual harness)

```bash
npx @modelcontextprotocol/inspector -e CONCORD_URL=http://<your-concord-host>:port-number uv run concord-mcp
```

## Run without a Concord container

In-process mode imports Concord's engine (`bible-core` + `bible-semantic`)
directly — one Python process, everything from local disk, fully offline once
set up. Fetch the data first (needs Docker once, for extraction only — nothing
runs in a container afterward; ~400 MB total for the database, embedding
model, and verse vectors):

```bash
make get-db
```

That fills `data/concord/` with `bible.db` and `semantic/` (the embedding
model + `embeddings.db`), which is where the defaults point — so the only
setting you need is the backend switch:

```bash
npx @modelcontextprotocol/inspector -e CONCORD_MCP_BACKEND=inprocess uv run concord-mcp
```

Claude Desktop, same idea:

```json
{
  "mcpServers": {
    "concord": {
      "command": "uv",
      "args": ["--directory", "/path/to/concord-mcp", "run", "concord-mcp"],
      "env": { "CONCORD_MCP_BACKEND": "inprocess" }
    }
  }
}
```

(`--directory` makes the repo the working directory, which is what the
relative `data/concord/` defaults resolve against. Custom locations:
`BIBLE_DB_PATH` and `CONCORD_SEMANTIC_ASSETS`.)

If the semantic artifacts are missing, `search_by_meaning` says so and names
the fixes; `lookup_verse` keeps working from `bible.db` alone.

In-process mode is also the fully private setup: with Claude Desktop the
conversation still travels to Anthropic, but a local MCP client pointed at
this server in `inprocess` mode touches no network at all.

**Developer alternative** (hacking on Concord and concord-mcp together):
build the artifacts from a local Concord checkout — `make build-db`, then
`python scripts/fetch_model.py` and `python scripts/build_embeddings.py` —
and point `BIBLE_DB_PATH` / `CONCORD_SEMANTIC_ASSETS` at the outputs. This
repo's `make get-db` never builds Concord from source, deliberately (ADR 0004).

## Tools

- `lookup_verse` — exact text of a verse, range, list, or chapter, in one or more
  translations. `John 3:16`, `Genesis 1:1-5`, `Psalm 23`.
- `search_keyword` — verses containing an exact word or phrase ("still waters"),
  with side-by-side translation comparison.
- `search_by_meaning` — verses by idea or theme ("verses about anxiety"), ranked by
  closeness of meaning, even when they don't contain the words.
- `cross_references` — the passages traditionally linked to a verse, ranked by
  community votes.
- `word_study` — the original-language words behind a passage; `John 21:15-17`
  shows the famous two-words-for-love exchange.
- `strongs_entry` — a Strong's lexicon entry (`G26`, `H7225`) with definition and,
  optionally, where the word occurs.
- `topic_verses` — a Nave's Topical Bible subject's curated verses, with "did you
  mean" candidates and labeled "See X" redirects.
- `places_for_passage` — the places a passage names, with coordinates only where
  the identification is confident; land of Nod stays honestly unmapped.
- `journeys` — the curated journeys (`paul-first`, `exodus`, …) and their ordered,
  source-attributed stops.
- `random_verse` — one random verse, optionally filtered by book or testament.

Every verse comes back tagged `Book Chapter:Verse (TRANSLATION)`, so citations are
verifiable. The full contract lives in [SPEC §4](v1/SPEC.md#4-tool-surface-the-contract);
the verified ten-question eval set is in [evals/](../evals/).

## Working on this repo

```bash
uv sync                                          # install
uv run pytest                                    # unit tests (CI-equivalent)
uv run pytest -m integration                     # live tests (local only)
uv run ruff check . && uv run ruff format --check .   # lint gate
npx @modelcontextprotocol/inspector uv run concord-mcp  # manual harness
```

Read [CLAUDE.md](../CLAUDE.md) and [docs/v1/SPEC.md](v1/SPEC.md) before any
change; the spec is the source of truth and ADRs 0001–0004 are binding.
