# Context-diet baseline

`AGENTS.md.before` and `CLAUDE.md.before` are verbatim UTF-8 snapshots from pilot
`origin/main` at `18c6d80` (the same instruction blobs as branch start `fa4640e`).
They are test data, not instructions to load at startup.

`test_context_diet.py` checks headings, decision IDs, prose rules and complete
bullets against AGENTS.md / CLAUDE.md and their directly linked docs. The only
intentional operation change is the C7 replacement of manual PROJECT_STATE
section edits with generation; all its safety qualifiers remain mandatory.

Size comparisons use raw decoded characters (including checkout line endings),
not bytes; the tokenizer-free token proxy is characters / 4. The generated
budget checker conservatively rejects exactly 40,000 characters, and the state
writer conservatively rejects exactly 80 lines, as the card's edge policy asks.
