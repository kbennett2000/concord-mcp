"""The §5 format rules, asserted line by line."""

from concord_mcp.render import render_semantic, render_verses


def test_verse_line_has_tag_emdash_text(fixture):
    out = render_verses(fixture("verses_john316_kjv_web"))
    assert "John 3:16 (KJV) — For God so loved the world," in out


def test_multi_translation_emits_one_line_per_translation(fixture):
    out = render_verses(fixture("verses_john316_kjv_web"))
    assert out.count("John 3:16 (KJV) —") == 1
    assert out.count("John 3:16 (WEB) —") == 1


def test_range_emits_every_verse_with_its_own_tag(fixture):
    out = render_verses(fixture("verses_psalm23_range"))
    for v in (1, 2, 3):
        assert f"Psalm 23:{v} (KJV) — " in out


def test_null_text_renders_as_not_available_never_fabricated(fixture):
    out = render_verses(fixture("verses_psalm23_range"))
    assert "Psalm 23:1 (YLT) — [not available in this translation]" in out


def test_semantic_lines_carry_tag_score_and_rank_order(fixture):
    out = render_semantic(fixture("semantic_anxious"), limit=10)
    lines = out.splitlines()
    assert lines[0] == 'Top 3 verses for "do not be anxious" (KJV):'
    assert lines[1].startswith("Philippians 4:6 (KJV) [score 0.93] — Be careful")
    assert lines[2].startswith("Matthew 6:25 (KJV) [score 0.90] — ")
    assert lines[3].startswith("1 Peter 5:7 (KJV) [score 0.88] — ")


def test_semantic_truncation_line_when_results_hit_limit(fixture):
    out = render_semantic(fixture("semantic_anxious"), limit=3)
    assert out.splitlines()[-1] == (
        "Top 3 matches shown — raise limit (max 25) or add min_score to narrow."
    )


def test_semantic_no_truncation_line_below_limit(fixture):
    out = render_semantic(fixture("semantic_anxious"), limit=10)
    assert "raise limit" not in out


def test_semantic_empty_results(fixture):
    out = render_semantic(fixture("semantic_empty"), limit=10)
    assert (
        out == 'No verses matched "quantum chromodynamics" — try rephrasing the idea.'
    )
