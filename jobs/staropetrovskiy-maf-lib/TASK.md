# Staropetrovskiy ZU_7_A MAF → MAF library (NPM + VPM)

Level: `standard` (library addition, not a customer delivery). Decisions: [D357], [D358].
Job work root (outside git): `C:/x/staropetrovskiy-maf-claude/`. Staging (outside git, not the library):
`C:/x/maf-library/staropetrovskiy/{npm,vpm,maps,preview,readback}/`. The library entry is made only by the
`library-publish` skeleton (#1743) into `G:/Мой диск/AGR-assets/maf/` as `draft` until Artem's «ок».

## Requirement

Artem, 2026-11-21: «добавить МАФ этой работы в нашу библиотеку МАФ (`library/maf/`) как NPM и VPM версии для
переиспользования». Intake answers: «Да, все» (all five recommendations below accepted).

## Scope

- 51 codes from the layer `MAF_Library` = `max/staropetrovskiy_maf_library_v003.max` (Artem's edits):
  T01–T23, I01–I19 + I10a, I04a, I04b, I05a, A01, A02, X01, X02, X05. All modelled by us; none taken from the old
  library. Vendor-geometry codes (T07, T09, T13–T15, T18, T19, T22, T23, X01) get `vendor-derived` + source.
- NPM for all 51. VPM for the 46 placed codes; I04a, I04b, I05a, T23, X05 are NPM-only.

## Не трогать

- Geometry, topology, UV, material IDs of the accepted masters (accepted geometry = freeze).
- The source scenes and delivered packages in `C:/x/staropetrovskiy-maf-claude/` (read copies only).
- Library material IDs 1–33 (v007), old catalogue entries, atlas 512 v007.

## How (numbers)

- NPM: one FBX per master exported from a copy of `library_v003.max`; pivot as the master: Z = 0 = ground level (as the master and A101), embedment below zero stays (T01 post 0.4 m);
  never lift a master to put its bottom on Z = 0; smoothing
  hard edges by 51° as in `site4/package_v015`; UV stays on the job atlas 512 v002 (tile 1001); maps
  `site4/maps_npm/*_GroundEl_{d,o,r,m}_1.png` copied next to the entries. Readback: tris = master tris, dims, IDs,
  UV in 0–1; xView clean.
- VPM: one instance per code cut from `site5/vpm_v007.blend` GroundEl (segments doubled on round parts, 181,694 tris
  total), moved to master local frame (inverse of the placement matrix), UDIM tiles renumbered 1032→1001 onward;
  maps from `site5/vpm_maps_v004/` (4K atlas, oversize 4K, 256 solid placeholders; normal + ERM placeholders).
- Material IDs 34–39 → `material_ids_v008` + a new `materials_v003.json` (v001 is released, never changes); ID 36 =
  #9E5A47 as in the delivered maps [D358].
- Texture links: none in either FBX (MAF-15); maps travel next to the model.
- Report per code: tris below Z = 0 (invisible embedment) vs total, so the NPM budget is not eaten by it.
- Registration: through #1743 `agr library publish` (library names, cards, SHA-256, `draft`); no own catalogue writer,
  no `catalogue.json["generated"]` rows from this job. Until #1743 lands the batch waits in staging.

## Pilot and acceptance

Pilot T01 end to end (NPM FBX + VPM FBX + maps + readback + preview), picture to Artem; his «да» → the other 50 in
parallel. Accepted by: per-code preview sheet NPM vs VPM and the catalogue rows.

## Batch result (2026-11-21) [D359]

- NPM: 51/51 match the masters (independent check). VPM registered for 12 codes: A01, A02, I07, I08, I17, I18, T01,
  T15, T16, T17, T22, X02. The other 39 are NPM-only: 34 until the VPM rebuild from masters (separate task), 5 by spec. Manifest for #1743: `C:/x/maf-library/staropetrovskiy/readback/summary_v002.json`.
- xView flags (accepted masters, not edited): I07, I08, I19, T20 → overlap spots list for Artem.
- Loose vertices removed in library copies: I01, I03, I04b.
- Registration: #1743 (`agr library publish|accept|reject`) is on main, but do NOT publish this batch until #1755
  (abandoned versions left on Drive after a failed batch) and #1756 (MAF folder with `_high`/`_low` refused as
  ambiguous, lone `_low` checked as VPM) are merged — Artem says when (2026-11-21).
- Follow-up (own task, not started): VPM rebuild of the 34 placed codes without VPM from the NPM masters — segment doubling only on
  round parts, flat parts untouched, ≤ 1 cm both ways, UV anew on tiles 1001-1017, pilot T02 first, using the
  conclusions of the MAF NPM→VPM skeleton #1745 (PR #1754: one atlas vs several atlases vs UDIM) — no second scheme. Old
  `site5/work/maf_vpm_segments.py` deformed flat parts (T02 +14 cm, I10/I10a +19 cm): reference only.

## Fallback

A master whose VPM instance cannot be matched to it by tris/dims → NPM-only with a review line, never a guess.
