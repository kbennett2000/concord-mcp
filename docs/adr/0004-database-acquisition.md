# ADR 0004 — In-process data acquisition: extract from the published image

Status: accepted · 2026-06-12

## Context

In-process mode needs `bible.db` and, for semantic search, the embedding
model + precomputed verse vectors. Concord bakes all three into its Docker
image at build time; none live in the git tree, and `bible-core` is not on
PyPI. Building Concord from source to produce them takes 20–30 minutes on a
good machine and has previously wedged a modest one.

## Decision

Acquisition is **extraction from the published GHCR image**, wrapped in a
make target:

- `make get-db` — `docker create` a container from
  `ghcr.io/kbennett2000/concord:<pinned tag>`, `docker cp` the database and
  semantic asset paths out, `docker rm` the container. Never `docker build`.
- The **exact in-image paths** for the model and vector artifacts are read
  from Concord's `Dockerfile` and source at slice 2 implementation time —
  per the read-the-source rule — not guessed here. The pinned tag is recorded
  in the Makefile and bumped deliberately.
- Developer alternative (documented, not the default): `make build-db` in a
  local Concord checkout for someone hacking on both repos.
- This repo never commits the database, the model, or any large binary;
  the acquisition outputs land in gitignored paths.

## Consequences

- In-process setup requires Docker once, for extraction only — nothing runs
  in a container afterward.
- Version skew is explicit: the pinned image tag is the in-process data
  version, reviewable in diffs.
- If concord-mcp gains real external traction, publishing `bible-core` to
  PyPI becomes the cleaner path for code (not data) — recorded as deferred
  in SPEC §12, not a prerequisite.
