# ADR 0003 — Curated tool surface, not 1:1 endpoint mapping

Status: accepted · 2026-06-12

## Context

Concord exposes 27 endpoints. An LLM chooses tools by reading their
descriptions inside a finite context budget; 27 near-overlapping options
degrade tool selection and burn tokens. MCP general guidance favors broad API
coverage, but Concord's surface contains several endpoint families that are
really one question each (topics browse/detail/verses; strongs
browse/detail/verses; journeys list/detail).

## Decision

**Ten curated tools** (SPEC §4), each collapsing an endpoint family into the
question a study assistant actually asks. Three commitments come with this:

1. **Descriptions are the product.** Model-facing, imperative,
   example-bearing, with explicit disambiguation between the three search
   tools. Editing a description is a reviewed change with rationale.
2. **Responses are compact tagged text.** Every verse carries
   `Book C:V (TRANSLATION)` so citations are verifiable; default limits are
   small and clamped server-side.
3. **Honesty passthrough.** Place `status` values and journey `source`
   attributions pass through verbatim; `unknown` places state plainly that
   no coordinates exist. The assistant inherits Concord's epistemics — that
   is the differentiating feature, not an implementation detail.

Excluded from v1: the notes endpoints (stock image ships zero notes) and
headings (low standalone value for an assistant; revisit on demand).

## Consequences

- Adding, removing, or renaming a tool is an ADR-worthy contract change.
- The curated layer owns small orchestration (e.g. `topic_verses` resolves a
  name to an id, then fetches verses) — kept trivial and readable.
- If real usage shows the model wanting finer-grained access, we widen
  deliberately rather than defaulting to 1:1.
