"""Render Concord's /v1 payloads as compact, citable plain text (SPEC §5).

Every verse line carries `Book C:V (TRANSLATION)` — that tag is what lets
the model cite verifiably, and it is non-negotiable.
"""

from functools import lru_cache
from typing import Any

from bible_core.parser import ParseError, parse_reference
from bible_core.resolver import DictBookResolver
from bible_core.seed import load_canonical_books_text, parse_canonical_books

NOT_AVAILABLE = "[not available in this translation]"

# Word-study output is capped at this many verse blocks (SPEC §5).
MAX_WORD_STUDY_VERSES = 10

LANGUAGE_NAMES = {"grc": "Greek", "hbo": "Hebrew"}


def render_verses(payload: dict[str, Any]) -> str:
    """Parallel-format /v1/verses/{ref} → one line per translation per verse."""
    lines = []
    for verse in payload["verses"]:
        for translation in payload["translations"]:
            text = verse["text"].get(translation) or NOT_AVAILABLE
            lines.append(f"{verse['reference']} ({translation}) — {text}")
    return "\n".join(lines)


def render_semantic(payload: dict[str, Any], limit: int) -> str:
    """/v1/semantic-search → ranked, scored verse lines with a §5 header."""
    query = payload["query"]
    if not payload["results"]:
        return f'No verses matched "{query}" — try rephrasing the idea.'

    lines = [f'Top {payload["count"]} verses for "{query}" ({payload["translation"]}):']
    for result in payload["results"]:
        text = result["text"] or NOT_AVAILABLE
        lines.append(
            f"{result['reference']} ({payload['translation']})"
            f" [score {result['score']:.2f}] — {text}"
        )
    if payload["count"] == limit:
        # Semantic search reports no true total (SPEC §5, amended).
        lines.append(
            f"Top {limit} matches shown — raise limit (max 25) or add"
            " min_score to narrow."
        )
    return "\n".join(lines)


def _true_total_truncation(shown: int, total: int) -> str | None:
    """The §5 truncation line for families that report a true total."""
    if shown < total:
        return f"Showing {shown} of {total} — raise limit (max 25) for more."
    return None


def render_cross_references(payload: dict[str, Any]) -> str:
    """/v1/cross-references/{ref} → ranked, voted, tagged target lines."""
    reference = payload["reference"]
    if not payload["cross_references"]:
        return f"No cross-references recorded for {reference}."

    translation = payload["translation"]
    header = f"Cross-references for {reference} ({payload['total']} total"
    header += ", text shows each link's opening verse):" if translation else "):"
    lines = [header]
    for entry in payload["cross_references"]:
        line = entry["to"]["reference"]
        if translation:
            text = entry["text"] or NOT_AVAILABLE
            line += f" ({translation}) [votes {entry['votes']}] — {text}"
        else:
            line += f" [votes {entry['votes']}]"
        lines.append(line)
    truncation = _true_total_truncation(
        len(payload["cross_references"]), payload["total"]
    )
    if truncation:
        lines.append(truncation)
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _static_resolver() -> DictBookResolver:
    """A DB-free book resolver from bible-core's packaged canonical data —
    works identically in http and inprocess modes."""
    books = parse_canonical_books(load_canonical_books_text())
    return DictBookResolver.from_books((b.id, b.name, b.aliases) for b in books)


def verse_labels(reference: str) -> list[str] | None:
    """The explicit verse list a reference expands to, or None.

    None means the expansion isn't fully determined without verse-count data
    (whole-chapter or cross-chapter spans) or the reference didn't parse —
    callers must then render word-study blocks unlabeled. Never guesses.
    """
    try:
        parsed = parse_reference(reference, _static_resolver())
    except ParseError:
        return None
    labels: list[str] = []
    for span in parsed.spans:
        if (
            span.start_verse is None
            or span.end_verse is None
            or span.start_chapter != span.end_chapter
        ):
            return None
        labels += [
            f"{parsed.book_name} {span.start_chapter}:{v}"
            for v in range(span.start_verse, span.end_verse + 1)
        ]
    return labels


def _token_line(token: dict[str, Any]) -> str:
    if token["strongs_id"] is None:
        return f"{token['position']}. {token['surface_form']} — [untagged]"
    details = ", ".join(
        part
        for part in (
            token["transliteration"],
            token["strongs_id"],
            token["morph_code"],
        )
        if part
    )
    line = f"{token['position']}. {token['surface_form']}"
    if token["lemma"]:
        line += f" — {token['lemma']} ({details})"
    else:
        line += f" — ({details})"
    if token["gloss"]:
        line += f" — {token['gloss']}"
    return line


def render_word_study(payload: dict[str, Any], reference: str) -> str:
    """/v1/verses/{ref}/words → token lines, grouped into verse blocks.

    The payload is flat: tokens carry no verse fields, and the only boundary
    signal is `position` resetting to 1 (upstream enhancement request:
    https://github.com/kbennett2000/concord/issues/69). Blocks are labeled
    with their verses only when the requested reference expands to exactly
    as many verses as there are blocks — otherwise they render unlabeled.
    """
    echo = payload["reference"]
    if not payload["tokens"]:
        return (
            f"No tagged words for {echo} ({payload['text_id']}) — the tagged"
            " text may not cover this passage."
        )

    blocks: list[list[dict[str, Any]]] = []
    previous_position = None
    for token in payload["tokens"]:
        if previous_position is None or token["position"] <= previous_position:
            blocks.append([])
        blocks[-1].append(token)
        previous_position = token["position"]

    labels = verse_labels(reference)
    if labels is not None and len(labels) != len(blocks):
        labels = None  # count mismatch (e.g. a token-less verse) — never guess

    shown = blocks[:MAX_WORD_STUDY_VERSES]
    lines = [
        f"Original-language words of {echo} ({payload['text_id']},"
        f" {payload['total']} words):"
    ]
    for index, block in enumerate(shown):
        if index:
            lines.append("")
        if labels is not None:
            lines.append(f"{labels[index]}:")
        lines += [_token_line(token) for token in block]
    if len(blocks) > MAX_WORD_STUDY_VERSES:
        lines.append("")
        lines.append(
            f"Showing first {MAX_WORD_STUDY_VERSES} of {len(blocks)} verses"
            " — request a narrower range."
        )
    return "\n".join(lines)


def render_strongs(entry: dict[str, Any], verses_payload: dict[str, Any] | None) -> str:
    """/v1/strongs/{id} (+ optional /verses) → entry block + occurrences."""
    language = LANGUAGE_NAMES.get(entry["language"], entry["language"])
    lines = [
        f"{entry['strongs_id']} — {entry['lemma']}"
        f" ({entry['transliteration']}), {language} — {entry['gloss']}",
        f"Definition: {entry['definition']}",
        f"Source: {entry['source']}",
    ]
    if verses_payload is not None:
        total = verses_payload["total"]
        shown = verses_payload["verses"]
        translation = verses_payload["translation"]
        lines.append(
            f"Occurs in {total} verses ({verses_payload['text_id']})."
            f" Showing {len(shown)}:"
        )
        for verse in shown:
            text = verse["text"] or NOT_AVAILABLE
            lines.append(f"{verse['reference']} ({translation}) — {text}")
        truncation = _true_total_truncation(len(shown), total)
        if truncation:
            lines.append(truncation)
    return "\n".join(lines)


def render_topic_verses(
    payload: dict[str, Any], topic_name: str, redirect_note: str | None = None
) -> str:
    """/v1/topics/{id}/verses → header + tagged verse lines."""
    lines = []
    if redirect_note:
        lines.append(redirect_note)
    lines.append(
        f"Topic: {topic_name} (Nave's Topical Bible) — {payload['total']} verses:"
    )
    translation = payload["translation"]
    for verse in payload["verses"]:
        if translation:
            text = verse["text"] or NOT_AVAILABLE
            lines.append(f"{verse['reference']} ({translation}) — {text}")
        else:
            lines.append(verse["reference"])
    truncation = _true_total_truncation(len(payload["verses"]), payload["total"])
    if truncation:
        lines.append(truncation)
    return "\n".join(lines)


def render_topic_candidates(query: str, payload: dict[str, Any]) -> str:
    """Several index entries match — the model picks an id and calls again."""
    options = ", ".join(
        f"{t['id']} ({t['name']})"
        + (f" — see {t['see_also']}" if t["see_also"] else "")
        for t in payload["topics"]
    )
    line = (
        f'Several topical-Bible entries match "{query}" — call topic_verses'
        f" again with one of: {options}."
    )
    if payload["total"] > len(payload["topics"]):
        line += f" [showing {len(payload['topics'])} of {payload['total']} matches]"
    return line


def topic_zero_match(query: str) -> str:
    return (
        f'No topical-Bible entry matches "{query}". Nave\'s indexes classic'
        " study subjects; for ideas in your own words, use search_by_meaning."
    )
