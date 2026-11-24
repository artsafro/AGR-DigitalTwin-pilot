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
