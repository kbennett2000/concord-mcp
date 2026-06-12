"""Render Concord's /v1 payloads as compact, citable plain text (SPEC §5).

Every verse line carries `Book C:V (TRANSLATION)` — that tag is what lets
the model cite verifiably, and it is non-negotiable.
"""

from typing import Any

NOT_AVAILABLE = "[not available in this translation]"


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
