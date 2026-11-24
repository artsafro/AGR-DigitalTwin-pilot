# Standing #65 — does the V006 "UV atlas padding" check see AC08 texture defects? (OBSERVE)

## Frozen before implementation and measurement

Focus (Artem 2026-11-24): NPM/VPM texture and atlas quality. #58–#64 measured the AC08 seam/phase signal through
renders and the slide-49 joint oracle (`research/autoresearch-standing-63@9fe65a62`: oracle catches a native NPM-only
U drift from 1 px). Nobody has run the **production** padding check — `twinqa.npm_uv` (#1580, V006 "UV atlas
padding", 8 px between islands, reg p.9 §5.4) — on a labelled real package. This round calibrates that existing
checker on the only labelled NPM pair before anyone treats it as a texture-defect signal. No new checker, no gate.

H65 (one hypothesis, three frozen parts):
- (a) applicability: the unchanged `npm_uv_findings(readback, npm_atlas.json)` gives a face-based result (not a
  format/precondition failure) on both AC08 NPM packages;
- (b) calibration: on the face-based measurement the rejected v007 scores worse than the accepted v010
  (`B65(v007) > B65(v010)`);
- (c) sensitivity: a U shift of PanelVJ30 faces on v010 is flagged by the checker exactly when a corner leaves
  the finish region (`> m` px, `m` = clean margin of those faces to the region's U-max edge), and not below.

- Fixture (pinned, full SHA-256 preflight before and after): AC08 `SM_Nku_1.zip` + `npm_atlas.json` of
  `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v007/` (rejected for visible seams, #559 comment 6341991856)
  and `...-v010/` (accepted visual reference, #559 comment 6345392389); ZIP hashes equal the #58 pins
  (v007 `271ee11b…`, v010 `2fe98379…`). Blender 5.1.2 exe SHA-256 `1e6624af…71c58fa5`, headless.
- Checker: `src/twinqa/npm_uv.py` and `tools/blender/fbx_readback.py` at origin/main `d1e98aab`, imported
  unchanged; their file hashes are recorded in the receipt.
- Measured variant (exact):
  1. `U` (unchanged): `npm_uv_findings(rb, atlas)` on a fresh `twinqa.scene.readback` of the extracted FBX.
  2. `F` (UDIM fold, research wrapper only): npm_atlas.json here tags each finish with `udim`; the unchanged
     `check_meshes` is called once per UDIM tile with (i) only the regions of that tile and (ii) the faces whose
     UV centroid lies in that tile, folded by `(u - floor(cu), v - floor(cv))`; tile `t = 1001 + floor(cu) +
     10·floor(cv)`. The embedded-image precondition is replaced by: every tile used by a region has a
     `T_*_Diffuse_*.<tile>.png` of `atlas × atlas` px in the same ZIP. `B65` = total `bad` faces of `F`;
     faces in a tile without regions count as bad (`no region tile`).
- Single number: `B65` per state, median of 3 fresh readbacks; spread must be 0.
- Perturbations (v010 only, applied to the fresh readback's `polygon_uv` of faces whose folded centroid is in
  region `PanelVJ30_RAL5015`, all their corners shifted by `+s/2048` in U): `s ∈ {+1, +5, m+1, m+pad+1}` with
  `m = ceil(clean U-max margin of those faces in px)`, `pad` = 6 from npm_atlas.json. Expected: `+1` (oracle
  detects it, #63) and `+5` give `B65 = 0` if `m ≥ 5`; `m+1` → bad with reason `padding band`; `m+pad+1` →
  reason `crosses cell` or `outside every atlas cell`. Changed faces per state are recorded; a state with 0
  changed faces is `not_exercised` and makes the run inconclusive. Positive trigger witness: `m+1`.
  Accepted control on which the rule fires: v010 itself under `m+1`.
- Verdict: `confirmed` if (a), (b) and (c) all hold; `refuted` if a valid run (preflight ok, spread 0, witness
  fired) breaks (a) or (b) or (c); `inconclusive` on preflight/hash failure, spread > 0, witness not firing,
  `not_exercised`, timeout or budget stop. (a) and (b) are reported separately whatever the verdict.
- Budget: 3 fresh rounds × 2 readbacks; perturbations are pure Python on each fresh readback. First round
  ≤ 120 s; total cap 480 s; after round 1 require remaining ≥ 2 × round 1 + 15 s, else `budget_stop` →
  inconclusive, replay the same command in a fresh directory. Zero candidate-code rounds: no production change.
- Forbidden: editing `npm_uv.py`/readback or the packages; changing grid, tile rule, labels or tolerances after
  seeing results; deselecting tests; rescoring a frozen dump as stability evidence.
- Not measured here: VPM 32 px padding, texel density, MAF/KPP1/Staropetrovskiy (no labelled pair), negative
  shifts (checker is symmetric by construction; not run), V shifts, rendered bleed.
- Not taken (owners): form check v1 (closed), G22 atlas #1649, KPP1 #1817/#1818, Staropetrovskiy #1500,
  MAF numbering #1809. Readiness 2026-11-24 13:45 (areas 4/11).

Replay: `uv run --frozen python docs/research/atlas-padding-v006-r65/run65.py tmp/r65-run-NEW` (Windows, pinned
Blender, Drive ZIPs; replay limited to readers with `G:/Мой диск/AGR-evidence/559-*`).

## R0 — inconclusive (OBSERVE); part (a) does not hold

**Итог (рус.):** штатная проверка V006 «UV atlas padding» (`twinqa.npm_uv`, #1580) **не применима** к реальным
НПМ-пакетам АС.08: на обоих (v007 отклонён, v010 принят) она падает одинаково по формальной причине — «нет
встроенного атласа 2048×2048» (FBX без встроенных картинок), до проверки граней. Значит, отличить отклонённый
пакет от принятого она не может, а на любом UDIM-пакете НПМ даст ложный fail. Причина глубже: `npm_atlas.json`
описывает один атлас 2048 px с ячейками 409/397/6 px, а в поставке — UDIM-тайлы по одному материалу на тайл
(Diffuse 4096 px у текстурных, 256 px у одноцветных), UV лежат на весь тайл (например, тайл 1001: u 0,04–0,75).
Заранее замороженный UDIM-вариант `F` требовал тайлы 2048 px и поэтому **не измерен**; чувствительность к сдвигу и
калибровка v007/v010 по отступам — **не измерены**. Производство и пакеты не менялись.

Run R0a (`tmp/r65-run-001`, harness `4baf2042`): stopped at the frozen `F` precondition before recording `U`;
receipt `atlas-padding-v006-r65/receipt-r0.json` (committed LF SHA-256 `8832705f9d90114ac97a169295fc5e4b203e44d544882e7e08e213004703464c`). The driver was then changed only
to record `U` and mark `F` as `not_measured` instead of aborting (no rule, grid, label or tolerance changed).

Run R0b (`tmp/r65-run-002`, harness at the commit of this section): status `completed`, hypothesis
**inconclusive** (frozen rule: `F` precondition failed, witness `m+1` not measured). Wall 9.545 s; rounds
3.204 / 2.978 / 3.088 s; 3 fresh Blender readbacks per package; `stable: true`; inputs equal before/after.

| Check | v007 (rejected) | v010 (accepted) | Status |
|---|---|---|---|
| `U` unchanged `npm_uv_findings` | fail: no embedded 2048 px atlas (images []) | same | measured ×3, identical; face check never reached |
| Diffuse tile px (ZIP PNG headers) | 1001: 4096; 1002–1004: 256 | 1001–1002: 4096; 1003–1005: 256 | measured |
| `F` UDIM fold, `B65` | — | — | **not measured** (frozen 2048 px tile precondition fails) |
| shift sensitivity `+1/+5/m+1/m+pad+1` | — | — | **not measured** |

Diagnostic only (one readback, not stability evidence): per-tile UV bbox of `SM_Nku_1_Main` — v010 tile 1001
u 0.0418–0.6676 / v 0.0276–0.5857 (30 faces), 1002 u 0.0455–0.5912 (8 faces), solid tiles 0.05–0.95; v007
similar. Nearest corner to a tile edge ≈ 0.0276 × 4096 ≈ 113 px on the 4096 tiles, so with one finish per tile
the 8 px inter-finish padding class has no exercised case on AC08.

Hypothesis result: **inconclusive**; part (a) applicability **does not hold** (measured, 3/3); (b), (c) not measured.
Would change (OBSERVE, not applied; needs its own issue + review): make V006 UDIM-aware — read the tile resolution
from the delivered Diffuse PNGs and the layout from the exported UDIM tiles (`npm_atlas_udim`), not from the
2048 px planning atlas; until then V006 on a UDIM NPM is a false fail, not a texture signal.

Receipt: `atlas-padding-v006-r65/receipt.json` SHA-256 as committed (LF) `8c8b2fb75d8cd43c1a9160d67ae6d7dcdf35b206ca5cfaed60b37954da880741` (raw CRLF run output `fc211371…cbbd1`).
No large evidence (only JSON receipts; inputs are the pinned Drive ZIPs). Replay limited to readers of
`G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v00{7,10}/`.

Affected tests: `uv run --frozen pytest -q -o addopts= docs/research/atlas-padding-v006-r65/test_r65.py tests/test_npm_atlas_padding.py tests/qa/test_npm_uv_1580.py` — 121 passed, 1 warning. The synthetic test first failed (test fixture put two finishes in one 2048 cell, rejected by the unchanged `load_layout`), then passed after moving the second finish to its own cell.

`bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — 553 passed, `repo_guards: GREEN`.

Full suite: deferred to merge batch (rule 68)
