# Form check v1 (`tools/qa/form_check/`) — OBSERVE only

Measures body form of a candidate FBX against a held-out key and Artem's recorded verdicts. It reports; it never
gates delivery, never refuses a model and never edits a body (card t_73d7ece4, autoresearch #40–#57).

| Part | File | Source round |
|---|---|---|
| Scene readback (sections, back-rim loops) | `extract_blender.py` | frozen `extract.py` of t_563a40f7 (+ label z map, object filter, offset) |
| Detector: contour, opening presence/edges/sill-head, extra gaps | `detector.py` | frozen `score_heldout.py` of t_563a40f7, tolerances verbatim |
| C1 band contour (0.05 m also at the opening sections) | `detector.py` | #43 (8/12 → 10/12) |
| Rim-loop fallback | `detector.py` | #53 (not measured 28 → 0 of 60) |
| Reveal depth from the candidate's own facade flanks at the observed gap edges | `detector.py` | #54–#56 (0 false depths) |
| Source-wall gap amendment (key ring wrong there) | `detector.py`, `pairs_v1.json` | #52 |
| Artem's rules: NARROW (window cut into the accepted opening), accepted deviations with citation (D341, D378) | `rules.py` | Artem 2026-11-20 (63B stage 2), #57, D378 |
| Pair judge: Claude + Codex, both orders, order-consistent only; #49 equivalence + extra-recess question | `judge.py` | #41, #45, #47, #49 |
| Neutral renders + 2×2 judge composites | `render_blender.py`, `pairs.compose` | #41 rig look |
| Pair registry with pinned bytes and Artem's verdicts | `pairs_v1.json` | — |
| Table + Russian summary sheet | `report.py`, `pairs.py table` | — |

Statuses: `pass` / `fail` / `expected` (a fail Artem accepted, with the measured number and the citation) /
`not_measured` (never counted as success). Judges never see depth or ~10 cm chamfers; depth comes only from the
detector. Judges are never asked "matches the drawing".

```
uv run python -m tools.qa.form_check.pairs detect --out C:/x/form-check-v1/run01
uv run python -m tools.qa.form_check.pairs render --out C:/x/form-check-v1/run01
uv run python -m tools.qa.form_check.pairs judge  --out C:/x/form-check-v1/run01 --workers 4
uv run python -m tools.qa.form_check.pairs table  --out C:/x/form-check-v1/run01 --png <sheet.png> --notes <notes_ru.txt>
```
Fixtures are outside git (`C:/x`, Google Drive) and pinned by SHA-256 prefix; hidden keys are never copied to git.
Blender 5.1 headless through `dt_ai.core.blender_runner.run_blender`; 3ds Max is not used.

Not measured by v1: corners on real pairs (no Artem-labelled corner pair; chamfer ≤ 0.05 m is inside tolerance;
judges miss a 0.10 m chamfer, #49), 63B reveal depth (reference open, #53), C1 where the key band is a bare ring
(63B, KPP1), KPP1 back reveals (contour A does not encode them), Sokolniki scene geometry (no key; the t_57b332a4
`compare.json` findings are used as the known-defect ledger).
