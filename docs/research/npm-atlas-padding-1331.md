# NPM atlas padding: measured AC08 reproduction (#1331)

## Scope and decision

Level: **full**, cell: `oks-npm`. [D278] records Artem's 2026-11-13 «лучше 16 пикселей»
(issue #1331, AI Council Slack thread `1794549017.241049`). Only the shared generator
`tools/derive/npm_atlas.py` changes; job-local historical generators and deliveries remain untouched.

`PAD=16` means **16 pixels on each side of a region**, extruded with that region's edge colour.
It is not a 16-pixel total inter-region gap. Adjacent occupied cells have **32 pixels between
UV region boundaries**, with **at least 16 pixels between a UV region and the atlas outer edge**.
Regulation p.9 §5.4 requires **8 pixels between unique-image islands**; the old PAD=6 meant
12 pixels between adjacent regions, not 6. The new setting is the user's stricter policy, not a
claim that the old 12-pixel inter-island gap violated that floor.

## Layout and area

2048 x 2048 RGB PNG, 409-pixel cells, 5 columns x 4 rows, capacity 20 finishes, unchanged.
`5 * 409 = 2045 <= 2048`; `4 * 409 = 1636 <= 2048`. Region side decreases from
`409 - 2*6 = 397` to `409 - 2*16 = 377` pixels; no packing overflow or finish drop.

| Metric | PAD=6 | PAD=16 |
|---|---:|---:|
| Single usable region, px² | 157609 | 142129 |
| Full 20-region grid usable area, px² | 3152180 | 2842580 |
| AC08 5-region usable area, px² | 788045 | 710645 |
| Per-side padding, px | 6 | 16 |
| Adjacent region gap, px | 12 | 32 |

Relative loss of **usable region area**: `100*(397²-377²)/397² = 9.8217741373%`.
This is not a 9.82 percentage-point loss of the whole atlas. Full-grid atlas occupancy loses
**7.3814392090 percentage points**; the actual five-region AC08 loses **1.8453598022 points**.

## Density applicability (do not transfer the Ground band)

Both patterned AC08 finishes span the same `S=4.096 m` as before. Independent calculation:
`397/4.096 = 96.923828125 px/m` before, `377/4.096 = 92.041015625 px/m` after;
exported display values are 96.9 and 92.0. Placeholder finishes remain exempt (`px_per_m=null`).
**NPM OKS has no regulatory density band** (p.10 §6.2, UV-07, conflict C22 resolved locally).
The Ground 10–40 px/m band and VPM 512–1706 px/m band do not apply to this NPM OKS atlas.
Thus no applicable band is violated; it would be false to claim this atlas is within Ground 10–40.
VPM input density stays 4096/4.096 = 1000 px/m, within its 512–1706 band; no VPM input changes.
The existing joint rule automatically widens the half joint to `ceil(750*4.096/377)=9 mm`:
18 mm occupies about 1.657 pixels, preserving the >=1.5 px recipe floor.

## Real reproduction and final-path readback

Authority: `jobs/TEC26-OKS/AC08/vpm_textures.json`, SHA-256
`3329bff4bf8e431f1cad2a31a5f2c637f7083d61e8b093c50bd1fd6e8e425722`.
This is the accepted-panel AC08 pilot recipe, **not a claim that every old model gate was approved**
(see `jobs/TEC26-OKS/STATE.md` and `AC08/PILOT_REPORT.md`). Source panel PNG was hash-verified:
`2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece`.

Generation: `uv run python tools/derive/npm_atlas.py jobs/TEC26-OKS/AC08/vpm_textures.json tmp/tec26-ac08-padding-v001`.
Published by exclusive creation, never replacing an old output:
`G:/Мой диск/AGR-evidence/1331-npm-atlas-padding/tec26-ac08-v001/`.

| File | SHA-256 |
|---|---|
| `T_Nku_1_001_Main_d_1.png` | `f25dcf3cfebcce677f43abaf20f5ac469d62d8e3bf6b75df6e1ce4149c4661f9` |
| `T_Nku_1_001_Main_o_1.png` | `c7d7c5f378d70acd58dccd3352883f1a16d227e14acbe3a43846b580186f81ee` |
| `npm_atlas.json` | `50d18fbdb4c636a4c8c6327b8c3d3dc80d3cc1daa9e2e2a197fdbb3af18215c6` |
| `readback.json` | `6650f956a0c2d7e46d58b22688f9d387e929b877012e7fe956709e0900b81ef2` |
| `SHA256SUMS.txt` | `7e61d0a356244884e8b1815cf2737a8fec9bf6def3ed6b444ec5ea00d9624301` |

Final-path decoded PNG + UV-layout readback: **5 regions, edge margin 16 px,
per-side padding 16 px, minimum region gap 32 px, usable area 710645 px²,
edge-extrusion checked in both RGB PNGs**. Visual inspection showed the expected two blue
patterned regions, grey plinth, blue frame and grey door; no obvious image corruption.
This is atlas validation, not FBX geometry/UV certification or renewed human acceptance.

The old pilot `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v010/` atlas/layout/ZIP and
final `tec26-oks/FINAL-2026-10-22/AC08_NKU/NPM/0000_Nku_1.zip` were read-only, with identical
before/after hashes recorded in `readback.json`. Both original ZIPs hash to
`8f0cb8b7e922850eab15198d0bd40cf2ca1e2bfed12e9c4912173b4aef565ab3`.
No binary or LFS object is committed.

## Validator boundary and regression evidence

`uv run python tools/derive/npm_atlas.py --check <npm_atlas.json> <diffuse.png> <opacity.png>`
is read-only and returns nonzero on failure. It measures exported UV bounds against decoded PNG
size, cell-side clearances and pairwise rectangle distances; it does **not trust `pad` metadata**.
It verifies complete edge extrusion in occupied cells in both PNGs. Colours alone cannot identify
islands (flat/identical colours are legitimate), so the exported layout is a necessary input.
It is deliberately limited to this generator's axis-aligned square regions, not arbitrary FBX UVs.
A valid single-region atlas reports no pair gap (`null`), not a fabricated gap measurement.

Tests-first commit `d1a47918`: **1 failed** (6 != 16), then passed after setting PAD=16.
Validator introduction: **5 failed / 1 passed** (missing measurement), then **6 passed**.
Fresh-process CLI: **1 failed / 23 passed** before `--check`, then passed.
Hostile output-hardlink probes: **3 failed** before exclusive output creation; then passed.
Affected checks before final freeze: **131 passed / 0 failed** (padding, shared tools, decisions).
Generated padding sweep covers every integer 0..32: below 16 refused, 16..32 accepted with measured
2*pad gap. Exactly 16 is inclusive, as required by the user's minimum.

## Other constants: findings only, unchanged

| Location | Existing value / semantics | Recommendation |
|---|---|---|
| `adapters/max/agr_tools/atlas_core.py` | `PADDING_MIN_PX=8`; pack, flora_layout, rigid_plan defaults | Keep regulatory minimum; consider an explicit per-tool 16 px production preference separately, after density/packing probes. |
| `adapters/max/agr_tools/npm_core.py` | `options.pad` defaults to atlas_core minimum 8 | Same recommendation; facade route inherits this option. |
| `adapters/max/agr_tools/facadeatlas_core.py` | No independent padding constant: delegates to npm_core; doc says >=8, historical pilot 16 | Do not confuse historical 16 with current default; evaluate facade-specific shared policy separately. |
| `tools/materials/npm_atlas_udim.py` | `PADDING_MIN_PX=8`, CLI `--padding` default 8; `_cell` uses `pad+1` guard; measured gap >=2*pad | Keep Ground 10–40 density gates; test 16 as an explicit option before any default change. Its “script uses 6” comment refers to legacy VPM_to_NPM script, not this shared generator. |
| `adapters/max/agr_tools/dilate_core.py` | `DEFAULT_PADDING['npm']=8`; VPM size/128 (16 at 2K, 32 at 4K) | Keep profile-specific rules; do not change VPM. |
| `adapters/max/agr_tools/checks_core.py` | `NPM_PADDING_PX=8`, `VPM_PADDING_PX={2048:16,4096:32}` | Regulatory checker floor must remain separate from this generator's stricter preference. |
| `adapters/max/agr_tools/uvtile_core.py` | `PAD_MIN_PX=8` | Preserve separate VPM/tile applicability; do not blanket-replace. |
| `adapters/max/agr_tools/runtime.py`, `flora_atlas_max.py` | explicit `pad=8` Ground/Flora calls | Consider independent regeneration/density tests before changing. |
| `tools/materials/atlas_maf.py` | `MIN_PADDING=DEFAULT_PADDING=8`; regulated API requires even >=8, low-level uniform packing allows 0 | Keep GroundEl/Flora acceptance independent of OKS. |
| `tools/library/maf_atlas_layout.py`, `flora_atlas_from_scene.py` | reuse atlas_maf minimum 8; scaled profiles must keep >=8 | Check smallest atlas budgets before selecting 16. |
| `jobs/{KPP1,TEC26-OKS,PSU275}/scripts/make_npm_atlas.py` | historical `PAD=6`, 397 px region, 12 px region gap | Historical delivery scripts intentionally untouched; use the shared tool for a new version, never overwrite old evidence. |
| `jobs/vyatskaya-tow02/scripts/texture_atlas_blender.py` | `PAD=8` | Job-local policy; do not alter approved artifacts here. |

No new conflict resolution or blanket Ground/MAF policy follows from [D278].
