# Running the evals

Ten questions, all ten tools, every answer verified against the data the
Concord image bakes. This is a **manual protocol** — it doubles as the
v1.0.0 acceptance demo. (An automated harness is deferred; see SPEC §12.)

## Protocol

1. Connect concord-mcp to Claude Desktop per the repo README (http mode
   against a live Concord).
2. For each `<qa_pair>` in `concord-mcp-evals.xml`, open a **fresh
   conversation** and ask the `<question>` verbatim.
3. Watch the tool-call panel: the calls should match the tools named in the
   pair's comment (the chains route across families — that's the point).
4. Verify the `<answer>`'s facts **appear** in the reply. This is
   fact-presence, not string equality: the model may phrase freely, but the
   reference tags, names, numbers, and quoted text must be there and be
   right. Pairs 8 and 9 carry design notes for their non-deterministic
   parts.
5. Record pass/fail below.

## Results

| # | Question (short) | Pass/Fail | Notes |
|---|---|---|---|
| 1 | John 21 love verbs | | |
| 2 | Nave's CARE first verse | | |
| 3 | John 3:16 top cross-reference | | |
| 4 | Land of Nod | | |
| 5 | Paul's first journey final stop | | |
| 6 | Strong's G26 in 1 Cor 13:1 | | |
| 7 | "still waters" exact phrase | | |
| 8 | Anxiety + Philippians 4:6 | | |
| 9 | Random Psalms verse | | |
| 10 | ACCOMPLICE redirect | | |
