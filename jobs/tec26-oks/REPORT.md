# TEC26 OKS 3 truba — v003 source-colour VPM / NPM

**Drive:** `G:/Мой диск/AGR-evidence/560-tec26-oks3-truba/v003/`.
Local: `C:/x/tec26-oks/truba-build-v003/`. Older unversioned/v001 packages are superseded.

## Delivered

- `VPM/SM_Truba_1.zip`: one FBX with 60 original UCX; 18 Diffuse/ERM/Normal PNGs,
  UDIM 1001–1006; no manifest/foreign file. Separate `VPM/UCX_SM_Truba_1_Main.fbx`.
- `NPM/0000_Truba_1.zip`: **only `0000_Truba_1_03.fbx`**, one atlas material,
  embedded `T_Truba_1_003_Main_d_1.png` + `_o_1.png`, both 2048² RGB. Editable maps
  are outside the ZIP in `NPM/maps/`. No NPM normal or optional R/M pair.
- `compare/slide57_VPM_NPM_front.png`, `_angle.png`, original slide57; four renders.

Artem's 18:45–18:46 card instructions govern: preserve original maps_truba RGB
and red–blue–red/grey layout. No KPP repaint or inferred RAL. Slide57 is monochrome;
legacy `RAL` keys in materials.json are identifiers, not assigned paint colours.
VPM solid Diffuse/ERM/Normal are 256² RGB placeholders; railing Diffuse retains
original 4096² RGBA (despite its filename saying 2048). The one 2048 NPM atlas is
derived from those VPM tiles, with separate RGB opacity and 8 px edge padding.

## Executed checks (on ZIP-extracted exports)

Blender 5.1.2: **2/2 readbacks**, 18/18 VPM map sizes/modes/bytes verified; 2/2
embedded NPM PNGs extracted from FBX Content, verified 2048² RGB and byte-identical
to the atlas. Original polygon indices/winding/world vertices match exactly:
**0.0 m maximum delta**, **24,372 vertices / 25,128 quads / 50,256 triangles**
in each visual; one named material and one UV layer. All **60 UCX unchanged**.
Railing pixel registration is preserved by tile translation / atlas affine map.

Max 2026.3, metres, source copy opened read-only; source/VPM/NPM each report:
**0 overlapping vertices (0.002 m), 0 overlapping faces (0.005 m), 0 inconsistent
winding edges, 0 non-manifold edges; 756 unchanged open edges; outside rays
90 front / 0 back / 6 miss of 96**. Mesh min Z **−1.4456 m**, UCX **−1.4660 m**.
No geometry, topology, perimeter drop or UCX was repaired/removed. Max's existing
polyunwrapper startup warning did not prevent successful measured imports.
Native receipt: `scripts/qa-receipt.json`; full readback JSONs accompany Drive files.

Source assignment stays on `SOURCE_Tuba` in local `build/Truba_1_master.blend`;
export copies retain a `source_material_id` FACE attribute. Source ID counts:
1=180, 2=36, 3=36, 5=126, 6=24462, 7=288; IDs 4/8/9/10 empty. Export shaders are
consolidated into one UDIM/atlas material without repainting source face regions.

Operational regression: old ZIP -> **exit 1**, foreign `manifest.json`; v003
ZIP/readback -> **exit 0**. No new unit/full-suite run per production instruction;
previous suite results are not presented as a current green run.

`validate_package.py --profile npm|vpm --json` actually returns **exit 1**:
NPM only `V001` site-wide FBX count / missing Ground; `V012` filenames now pass.
VPM missing deferred GeoJSON (`V001`); `V012` address correspondence remains review,
`V013`/`V014` lack placement data. Non-`--scene` not_run findings are not passes.
No stale-texture, six-set NPM, manifest or archive-name failure remains.

## Pictures / scope limits

Comparison: slide57 | exported VPM | exported NPM, same VPM/NPM camera/scale,
UCX hidden, red ±0.000 bar. Existing **slide top +64 m versus source top +69.384 m**
is annotated, not remodelled. Both exported colour layouts visually agree.
Deferred: whole-site Ground/archive integration, GeoJSON, MSK-77/district/address,
SINTEZ, УКЭП and human V015–V017 acceptance. **No publication pass is claimed.**

## Reproduce (new versioned build only)

1. `TEC26_BUILD=<new-build> dcc_batch.py max --file jobs/tec26-oks/scripts/export_source_max.py --scene C:/x/tec26-oks/max-copy/truba.max`.
2. `uv run python jobs/tec26-oks/make_textures.py --src C:/x/tec26-oks/max-copy/maps_truba --out <build>/textures-vpm-source --sums <build>/SHA256SUMS-textures.txt`.
3. `uv run python jobs/tec26-oks/scripts/make_delivery_maps.py <build>`.
4. Blender 5.1 `--background --factory-startup --python-exit-code 1 --python jobs/tec26-oks/scripts/build_delivery_blender.py -- <build>`; then `readback_delivery_blender.py`.
5. Native `readback_max.py`, same TEC26_BUILD and untouched source copy.
6. `uv run python jobs/tec26-oks/scripts/make_compare.py <build> <slide57.png>`.
The retired v001 exporter refuses before writes. Do not use its old packages.

Transcript: Hermes session `local-ea1006365802885a8cab37a076271abb73cba39fbc0db368cdf360d03adfd8d5`.
