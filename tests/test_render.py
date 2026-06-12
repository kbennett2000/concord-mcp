"""The §5 format rules, asserted line by line."""

from concord_mcp.render import (
    _place_line,
    render_books,
    render_search,
    render_translations,
    render_cross_references,
    render_journey_detail,
    render_journeys_list,
    render_places,
    render_random,
    render_semantic,
    render_strongs,
    render_topic_candidates,
    render_topic_verses,
    render_verses,
    render_word_study,
    topic_zero_match,
    verse_labels,
)


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
        assert f"Psalms 23:{v} (KJV) — " in out


def test_null_text_renders_as_not_available_never_fabricated(fixture):
    out = render_verses(fixture("verses_psalm23_range"))
    assert "Psalms 23:1 (YLT) — [not available in this translation]" in out


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


# --- cross_references (§5) -----------------------------------------------------


def test_xref_lines_without_text_carry_votes_only(fixture):
    out = render_cross_references(fixture("xrefs_john316"))
    lines = out.splitlines()
    assert lines[0] == "Cross-references for John 3:16 (3 total):"
    assert lines[1] == "Romans 5:8 [votes 968]"
    assert lines[2] == "1 John 4:9-10 [votes 601]"  # range target


def test_xref_hydrated_lines_state_opening_verse_rule(fixture):
    out = render_cross_references(fixture("xrefs_john316_text"))
    assert "text shows each link's opening verse" in out.splitlines()[0]
    assert "Romans 5:8 (KJV) [votes 968] — But God commendeth" in out


def test_xref_null_text_is_honest(fixture):
    out = render_cross_references(fixture("xrefs_john316_text_web"))
    assert "Romans 5:8 (WEB) [votes 968] — [not available in this translation]" in out


def test_xref_truncation_uses_true_total(fixture):
    payload = fixture("xrefs_john316")
    payload["total"] = 23
    out = render_cross_references(payload)
    assert out.splitlines()[-1] == "Showing 3 of 23 — raise limit (max 25) for more."


# --- word_study (§5) -------------------------------------------------------------


def test_word_study_single_verse_lines(fixture):
    out = render_word_study(fixture("words_john2115"), "John 21:15")
    lines = out.splitlines()
    assert lines[0] == "Original-language words of John 21:15 (SBLGNT, 3 words):"
    assert lines[1] == "John 21:15:"
    assert lines[2] == "1. ἀγαπᾷς — ἀγαπάω (agapaō, G25, V-PAI-2S) — to love"
    assert lines[3] == "2. καί — [untagged]"


def test_word_study_multi_verse_blocks_are_labeled_when_counts_match(fixture):
    out = render_word_study(fixture("words_john211517"), "John 21:15-17")
    assert "John 21:15:" in out
    assert "John 21:16:" in out
    assert "John 21:17:" in out
    blocks = out.split("\n\n")
    assert len(blocks) == 3
    # The G25/G5368 contrast: verse 17's block has no agapaō at all.
    assert "G25" in blocks[0] and "G25" in blocks[1]
    assert "G25" not in blocks[2] and "G5368" in blocks[2]


def test_word_study_count_mismatch_falls_back_to_unlabeled(fixture):
    # John 21:18 has no tokens: 4 expected verses, 3 blocks — never guess.
    out = render_word_study(fixture("words_john211518"), "John 21:15-18")
    assert "John 21:15:" not in out
    assert len(out.split("\n\n")) == 3


def test_word_study_whole_chapter_reference_is_unlabeled(fixture):
    payload = fixture("words_john211517")
    payload["reference"] = "John 21"
    out = render_word_study(payload, "John 21")
    assert "John 21:15:" not in out


def test_word_study_caps_at_ten_verse_blocks(fixture):
    token = fixture("words_john2115")["tokens"][0]
    payload = {
        "reference": "John 21:1-12",
        "text_id": "SBLGNT",
        "total": 12,
        "tokens": [dict(token, position=1) for _ in range(12)],
    }
    out = render_word_study(payload, "John 21:1-12")
    assert out.splitlines()[-1] == (
        "Showing first 10 of 12 verses — request a narrower range."
    )
    assert out.count("1. ἀγαπᾷς") == 10


def test_word_study_empty_tokens(fixture):
    payload = {"reference": "Genesis 1:1", "text_id": "OSHB", "total": 0, "tokens": []}
    out = render_word_study(payload, "Genesis 1:1")
    assert "No tagged words for Genesis 1:1 (OSHB)" in out


def test_verse_labels_expansion_rules():
    assert verse_labels("John 21:15-17") == [
        "John 21:15",
        "John 21:16",
        "John 21:17",
    ]
    assert verse_labels("Romans 3:23,25") == ["Romans 3:23", "Romans 3:25"]
    assert verse_labels("Psalm 23") is None  # whole chapter — verse count unknown
    assert verse_labels("not a reference !!") is None


# --- strongs_entry (§5) -----------------------------------------------------------


def test_strongs_entry_block(fixture):
    out = render_strongs(fixture("strongs_g26"), None)
    lines = out.splitlines()
    assert lines[0] == "G26 — ἀγάπη (agapē), Greek — love"
    assert lines[1].startswith("Definition: ἀγάπη, -ης, ἡ")
    assert lines[2] == "Source: STEP Bible (Tyndale House)"
    assert "Occurs in" not in out


def test_strongs_occurrences_with_true_total(fixture):
    out = render_strongs(fixture("strongs_g26"), fixture("strongs_g5368_verses_p2"))
    assert "Occurs in 3 verses (SBLGNT). Showing 2:" in out
    assert "John 21:15 (KJV) — So when they had dined" in out
    assert out.splitlines()[-1] == "Showing 2 of 3 — raise limit (max 25) for more."


# --- topic_verses (§5) --------------------------------------------------------------


def test_topic_verses_header_and_lines(fixture):
    out = render_topic_verses(fixture("topic_care_verses"), "CARE")
    lines = out.splitlines()
    assert lines[0] == "Topic: CARE (Nave's Topical Bible) — 4 verses:"
    assert lines[1].startswith("Psalms 37:5 (KJV) — Commit thy way")


def test_topic_verses_redirect_note_comes_first(fixture):
    out = render_topic_verses(
        fixture("topic_care_verses"),
        "CARE",
        redirect_note='Nave\'s lists "KINDNESS" as "See CARE" — showing CARE.',
    )
    assert out.splitlines()[0].startswith('Nave\'s lists "KINDNESS"')


def test_topic_candidates_list_ids(fixture):
    out = render_topic_candidates("faith", fixture("topics_q_faith"))
    assert 'Several topical-Bible entries match "faith"' in out
    assert "faith (FAITH)" in out
    assert "faithfulness (FAITHFULNESS)" in out


def test_topic_zero_match_points_at_search_by_meaning():
    out = topic_zero_match("zzgrindset")
    assert "search_by_meaning" in out


# --- geography + journeys + random (§5, S4) ----------------------------------------


def test_place_lines_per_status(fixture):
    out = render_places(fixture("places_john2116"))
    lines = out.splitlines()
    assert lines[0] == "Places named in John 21:16 (5):"
    assert lines[1] == (
        "Aenon (settlement) — disputed (identification contested)"
        " — 32.0500°N, 35.4500°E (confidence medium)"
    )
    assert lines[2] == (
        "Amphipolis (settlement) — identified — 40.8202°N, 23.8472°E (confidence high)"
    )
    assert lines[3] == (
        "Holy Place (special) — multiple — several locations across history,"
        " no single pin"
    )
    assert (
        lines[4]
        == "Nod (region) — unknown — location genuinely unknown, no coordinates"
    )
    assert lines[5] == (
        "Valley of Hamon-gog (valley) — symbolic — a symbolic name,"
        " not a mappable location"
    )


def test_no_coordinates_ever_for_null_statuses(fixture):
    # The coordinate hard line: no digit-pair leaks on unknown/symbolic/multiple
    # lines — anywhere, journey stops included.
    import re

    coord = re.compile(r"\d+\.\d+°")
    for line in render_places(fixture("places_john2116")).splitlines():
        if any(
            s in line for s in (" — unknown — ", " — symbolic — ", " — multiple — ")
        ):
            assert not coord.search(line)
    for line in render_journey_detail(fixture("journey_galilee_loop")).splitlines():
        if " — unknown — " in line:
            assert not coord.search(line)


def test_places_empty_passage(fixture):
    assert render_places(fixture("places_empty")) == "No places are named in John 3:16."


def test_southern_western_hemispheres():
    line = _place_line("Somewhere", "settlement", "identified", -33.86, -151.2, "low")
    assert "33.8600°S, 151.2000°W" in line


def test_journeys_list_teaches_the_id_call(fixture):
    out = render_journeys_list(fixture("journeys_list"))
    lines = out.splitlines()
    assert lines[0] == "Curated journeys (1):"
    assert lines[1] == (
        "galilee-loop — A Galilean Loop (John 21; c. AD 30 (conventional); 4 stops)"
    )
    assert lines[-1] == "Call journeys with a journey_id for the ordered stops."


def test_journey_detail_attribution_header_first(fixture):
    out = render_journey_detail(fixture("journey_galilee_loop"))
    lines = out.splitlines()
    assert lines[0] == (
        "A Galilean Loop (galilee-loop) — John 21, dating: c. AD 30 (conventional)"
    )
    assert lines[1] == (
        "One commonly proposed reconstruction assembled for the test suite."
        " (source: Synthetic itinerary for tests.)"
    )
    assert lines[2].startswith("1. Amphipolis — identified — 40.8202°N")
    assert lines[2].endswith("— John 21:15")
    assert "3. Nod — unknown — location genuinely unknown, no coordinates" in lines[4]
    assert lines[5].startswith("4. Amphipolis")  # the revisit repeats


def test_journey_detail_null_dating_omits_the_clause(fixture):
    payload = fixture("journey_galilee_loop")
    payload["dating"] = None
    out = render_journey_detail(payload)
    assert "dating:" not in out.splitlines()[0]


def test_random_render(fixture):
    out = render_random(fixture("random_gen_ylt"))
    assert out.splitlines()[0] == "Random verse (YLT, book GEN):"
    assert out.splitlines()[1] == "Genesis 1:1 (YLT) — In the beginning…"


# --- keyword search + resources (§5, S5a) -------------------------------------------


def test_search_strips_marks_and_full_verse_has_no_excerpt_marker(fixture):
    out = render_search(fixture("search_shepherd"))
    lines = out.splitlines()
    assert lines[0] == 'Verses containing "shepherd" (KJV) — 1 match:'
    assert lines[1] == "Psalms 23:1 (KJV) — The LORD is my shepherd; I shall not want."
    assert "<mark>" not in out
    assert "[excerpt]" not in out


def test_search_ellipsized_snippet_is_marked_excerpt_with_footer(fixture):
    out = render_search(fixture("search_grieved"))
    lines = out.splitlines()
    assert lines[1].startswith("John 21:17 (KJV) [excerpt] — ")
    assert lines[-1] == (
        "Lines marked [excerpt] are partial — use lookup_verse for the full verse."
    )


def test_search_multi_renders_one_line_per_matching_translation(fixture):
    out = render_search(fixture("search_loved_multi"))
    lines = out.splitlines()
    assert lines[0] == 'Verses containing "loved" (KJV, WEB) — 1 match:'
    assert lines[1].startswith("John 3:16 (KJV) — For God so loved the world,")
    assert lines[2].startswith("John 3:16 (WEB) — For God so loved the world,")


def test_search_zero_hits_route_to_search_by_meaning(fixture):
    out = render_search(fixture("search_zero"))
    assert out == (
        'No verses contain "zebra" in KJV — for ideas or themes rather than'
        " exact wording, try search_by_meaning."
    )


def test_search_truncation_uses_true_total(fixture):
    payload = fixture("search_shepherd")
    payload["total"] = 14
    out = render_search(payload)
    assert "Showing 1 of 14 — raise limit (max 25) for more." in out


def test_render_translations_lines(fixture):
    out = render_translations(fixture("resource_translations"))
    lines = out.splitlines()
    assert lines[0] == "Loaded translations:"
    assert lines[1] == "KJV — KJV (synthetic) (en) — Public domain."
    assert len(lines) == 5


def test_render_books_lines(fixture):
    out = render_books(fixture("resource_books"))
    lines = out.splitlines()
    assert lines[1] == "GEN — Genesis (OT, 1 chapter)"
    assert "EXO — Exodus (OT)" in lines[2]  # no loaded chapters -> no count
    assert len(lines) == 67
