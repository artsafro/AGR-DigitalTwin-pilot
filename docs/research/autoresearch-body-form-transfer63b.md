# Autoresearch #51 — body form transfer to a second building (63B), source-only key (OBSERVE)

Card t_fb3a0b98 (standing #51). Contract frozen in this commit BEFORE any variant is measured.

## Why this target

Rounds #40–#50 measured the frozen form detector of t_563a40f7 on ONE fragment (G22 k2 SE), with a key partly
derived from the accepted body (retrospective, #40). Every round since lists the same open gap: "second accepted
fragment of another builder" and "exact human-verdict body pairs" (#43, #47, #49, #50). KPP1 NW / Sokolniki still
have no exact accepted/rejected body bytes (#49/#50). 63B does: accepted v007 (Artem «принимаю» 2026-11-20) and
rejected v002–v006, each with an evidence `SHA256SUMS.txt` (same bytes as `autoresearch-body-mesh-grid-harness/grid.json`).
Not taken: Ground (#1738/#1816 fix first), building cards #1770/#1784/#1818, cold delivery #1315, atlas #1649,
suite #1615, judges #41/#45/#47/#49 (render lane), section-conflict observer #48/#50 (G22-only data mutations).

## Hypothesis H51

With a key built ONLY from the source (`tower-B/v002/source_sections_and_openings.json`, no body bytes) and the
t_563a40f7 `extract.py` + `score_heldout.py` byte-identical, the form checks transfer to 63B:
(a) accepted v007 has F = 0 form failures; (b) both planted witnesses on a v007 copy fire (F ≥ 1 on the planted item);
(c) no rejected variant scores better than v007 (F_rej ≥ F_v007); (d) spread across 3 fresh imports = 0.

- confirmed: (a)–(d) all hold. refuted: (a) or (c) fails with v007 not frame-shifted. inconclusive: frame mismatch
  (v007 contour deviation > 0.5 m at both contour sections), a witness moves 0 vertices or does not fire, not-measured
  share of v007 F-items > 10 %, preflight/postflight hash mismatch, or budget stop.
- Calibration note (card rule 3): v002–v006 were rejected mostly for MESH defects (REPORT: triangles, T-junctions,
  stacked faces, wedges; v006 photos «column_frame_gap», «pilaster_wedge»). A strict form separation is NOT expected;
  (c) is non-strict on purpose. Bias: v002–v006 were built from this same source JSON, v007 by a different chain
  (`floor_from_dump`), so the key favours the REJECTED variants — this works against H51.

## Metric and command

- F = number of `fail` items among {contour@16.85, contour@19.8, per key opening `present` / `edges` / `sill_head`,
  `openings:no_extra_in_box`} = 18 items for 5 key openings. Lower is better. Median of 3 fresh Blender imports.
- Reported apart, not in F: `reveal_depth` (frozen scorer only reads jamb points with |d| ≤ 0.6 m; 63B window depth
  is 0.71 m, so a fail is expected by construction = detector limit, not a form signal), `scope:no_fills_stage1`.
- Replay: `python docs/research/autoresearch-body-form-r51/make_key63b.py "<EV>/v002/source_sections_and_openings.json" C:/x/t_fb3a0b98-r51/key`
  then `python docs/research/autoresearch-body-form-r51/run51.py C:/x/t_fb3a0b98-r51/run1` (new dir each run).
- Fixture: 63B floor +7.80..+10.95 (type A, sill +8.48, head +10.45), ring arc 22.6–40.3 m (end of seg 15, window on
  seg 16, corner 16-17-18, 4 windows on the 15 m facade seg 18), box `[80.684, 13.215, 94.588, 25.707]`, ring 12..19,
  5 key openings (widths 2.30/1.71/1.71/1.00/1.00 m, depth 0.71/0.713), no curtain inside (asserted), no negatives.
  Chosen from the source only (contiguous window+curtain pairs on seg 18 end / seg 31 / seg 59 excluded: one wall gap
  for two key openings is the #48 conflict case, not this test).
- Adapter (not a detector change): the frozen scorer hard-codes G22 labels; real z = label − 8.82
  (8.03 / 8.98 / 9.38 / 10.98 m), loops z + 8.82 so the sill +8.48 lands in the frozen 17.0–17.6 band.
  `extract.py` and `score_heldout.py` hashes are checked against `C:/x/t_563a40f7/SHA256SUMS.txt`.

## Pinned inputs (SHA-256)

| input | sha256 |
|---|---|
| source_sections_and_openings.json | f1865bdde9ca0b3553777cf6e1d71cd8aee915998d342ec789bfc4fd6cdf47a2 |
| key heldout-key-v001.json | 67a1ae5b88beec6eefc51d51ccdab496daa256709ec484793caee4097f6b6b14 |
| key heldout-sections-v001.json | 07ce9a5bff8a9e4e82bf8346daef191ca5e0ba626ccd900aaca290a29fb698b6 |
| extract.py / score_heldout.py | ee50925b… / e9d6f65b… (t_563a40f7 SHA256SUMS) |
| v007 (accepted) | 53189b830418a328f3159172c5c1c7eff826c5a9eff568cad0b9187b63332bd7 |
| v002 / v003 / v004 | a57cb3fb… / 83f3289c… / 6d22c572… |
| v005 / v006 | a387a459… / b2b26d44… |

`C:/x/review-63B/63B_Stage1_v007.fbx` (4e9f584c…) differs from the evidence bytes and is NOT used.

## Witnesses, expected direction, bounds

- W_shift_opening (v007 copy): window 6189f94 jambs +0.10 m along seg 18 → expect its `edges` fail (0.10 > 0.03),
  F ≥ F_v007 + 1. W_shift_wall: seg 18 plane +0.10 m outward → expect both `contour@` fail (0.10 > 0.05).
- Moved-vertex counts are recorded; 0 moved = `not_exercised`, reported as not measured.
- Accepted control on which a rule fires: none (no candidate rule in this round; OBSERVE only).

## Budget, stop, forbidden

- One round, no candidate: confirm budget = the 3×(6 variants + 2 witnesses) series; new-candidate budget = 0.
  Wall cap 3600 s inside run51.py (budget stop = inconclusive, replay unchanged in a new dir).
- Forbidden: editing the detector, tolerances, key after the first run, delivered packages, evidence bytes,
  other cards' files; 3ds Max; choosing the fixture from body bytes. Any key change = v002 with a reason.
- OBSERVE: nothing is wired into production; findings go to the round log below.

## Round log

- R0 (run1, wall 26.9 s, complete, hashes OK): v007 F = 4, v002–v006 F = 0, spread 0 everywhere; W_shift_opening
  fired (+1), W_shift_wall masked (not measured). **H51 = inconclusive** (frozen rules: v007 contour > 0.5 m at both
  sections, not-measured 3/18 > 10 %, one witness not exercised). Post-hoc: the key ring closes a source recess
  [3.414, 4.718] m that v007 keeps (gap [3.444, 4.715]) — the key, not the accepted body, is off. No candidate, no
  keep. Details: [r51/REPORT.md](autoresearch-body-form-r51/REPORT.md).
