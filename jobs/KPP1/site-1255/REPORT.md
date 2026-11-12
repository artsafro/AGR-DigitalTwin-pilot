# KPP1 R1 site placement #1255 — approximate, NOT PASSED

Cells: `oks-vpm`, `oks-npm`. Offline placement/readback only; no Max session touched.
Decision: Artem, 2026-11-12, Kanban t_cd0d8792 USER DECISION 11:38, [D260].
This supersedes the historical STOP in `RUN-LOG.md`, not the measured fit diagnostics.

**approximate, ±0.1 m, fitted to customer NPM 0607_77_05_0009005_117_02; entrance orientation not independently confirmed**

The quoted ±0.1 m is the accepted approximate-placement label, NOT a certified maximum
error. Median 0.099439679 m, p90 0.262005882 m, max 0.721108073 m; only
25.104651% of contour points are within 0.05 m. The alternative at 173.888557 degrees
has median 0.121721781 m. `fit_ok=false`, `unique=false` remain unchanged.
No SPOZU/DWG alignment, entrance-direction verification or V017 sign-off is claimed.

## Coordinate and zero-mark sources

| Role | File / sheet / source | SHA-256 | Interpretation |
|---|---|---|---|
| Accepted MSK-77 reference | `C:/Users/artsafro/Downloads/Telegram Desktop/0607_77_05_0009005_117_02.zip`, member `0607_77_05_0009005_117_02.fbx`; no drawing sheet | ZIP `219524eae5acec4f58fbc4b683400512ec53578dcc865c646fba9cc65280376f`; FBX `fc08774a30058de2b2da296306946b1b60b65612ca73b7af563218a0c7b50b51` | Customer's delivered NPM, author/version not independently established; accepted instead of missing plan by [D260] |
| Zero mark | `26_КПП1_АР_МЭП_RVT22.rvt`, level `отм. 0,000`; cached read-only Revit observation in `jobs/KPP1/object.json` | RVT unavailable in source store: hash not measured; cached JSON `a34cc18038e9440e164518523c39b25be0e7d82e0582348e4411b0763bcd020c` | 0.000 = absolute 171.050 m; explicitly chosen by Artem over customer spreadsheet 169.65 |
| Customer properties | `C:/Users/artsafro/Downloads/Telegram Desktop/geojson ТЭЦ 26.xlsx`, sheet `Данные GEOJSON`, column `Центральная проходная` | `30a9c143d0241b3a06a604a8f296ce9630776122f7460124cfce33265576c598` | Address, okrug, rajon, developer, designer, cadNum, ZU_area; coordinates empty |
| L01 facades | `22Е56-АР2-1002-АС.03-R1_L01_без подписей.dwg`, L01 | `cb74ba142142e9181dfc14e235f94aed7eabec597e746760e5a972427f0f3648` | Relative levels only, not a placement plan |
| L02 colour facades | `22Е56-АР2-1002-АС.03-R1_L02_без подписей.dwg`, L02 | `428426002f2642d29e97a8db34053546dc1e427bdff8aeef9ad1c81005b73cb2` | Not a placement plan |
| L03 local plan | `22Е56-АР2-1002-АС.03-R1_L03_без подписей.dwg`, L03 at 0.000 | `ad1de2b203bd4394bd3604642cd41bd8f3b2427ec23b900413bd396612624469` | Local millimetres, no survey coordinates |
| Album | `G:/Мой диск/AGR-assets/tec26/album/TEC26_na_RR_1.pptx`, slide 2 situation plan | `74e50277df5e2dfde3ba7ab945eb6bab45a8fa8c0207d7aca3a136d9656b78ac` | Raster, cadastral plot but no MSK-77 coordinate grid |

DWG/album hashes and authority are recorded in `../cold-run-1172/inputs-manifest.json`;
coordinate-search observations are historical evidence in the card comments and `RUN-LOG.md`.
The missing file was a SPOZU/general-plan DWG of plot `77:05:0009005:117` showing the
Central checkpoint's MSK-77 tie and absolute 0.000. Artem explicitly confirmed it will
not arrive (Ground by another person) and accepted the reference-NPM fit instead.
The original six fit evidence files were independently re-hashed: **6/6 match**.

## Applied transform and readback

`fit-npm-r1-v002.json` is immutable historical diagnostic input:

- theta = **-6.053044176714781 degrees**, NOT the 180-degree alternative;
- origin = **[8056.143933445407, -9581.26989822931, 171.050]**;
- axes: Blender X = MSK east/y, Blender Y = MSK north/x, Z = absolute height,
  following the customer convention studied by #1123 / [D220]; no axis swap;
- VPM: `p = Rz(theta) * p_R1`, origin/pivot remains [0,0,0], Z remains relative;
- GeoJSON insertion point = **[8056.144, -9581.270]**, rounded to 3 decimal places;
- NPM: `p = Rz(theta) * p_R1 + origin`, including absolute zero mark;
- plan rotation baked into vertices; transforms reset; metres preserved.

`place_package.py` pins the three R1 source hashes from
`../rerun-1230/evidence-r1-v002-SHA256SUMS.txt`, checks them before and after placement,
exclusively creates a new output directory and never replaces an input/output version.
Blender **5.1.2**, private `--background --factory-startup` process, no shared live scene.

Fresh-process imports of BOTH source and published output (4 separate Blender runs):
`dump_vertices.py` -> every output vertex compared to an independently calculated rigid
transform, exact triangle index arrays preserved. `readback-parity.json` records **8/8
objects**, no drops (6 VPM including 4 UCX; 2 NPM), maximum VPM error **0.000003420 m**,
maximum NPM error **0.000386318 m** (float32 global-position storage). UV and material
binding evidence is in `readback-attributes.json`. All **21/21 PNGs** in the VPM ZIP are
byte-identical to R1. No remeshing, UV edits, geometry cleanup or UCX edits were performed.
The 256x256 JPG is a real render of the placed model, not a synthetic customer image.

## GeoJSON and placeholders

`SM_Kpp_1.geojson` uses the existing `adapters/max/agr_tools/package_core.py`
`geojson_document` / `glasses_entry` functions, as studied by #1123; exact App.3
FeatureCollection/ObjectFeature/Point/properties/Glasses structure. Glass values are
read from the imported R1 material (not copied from another building).

- territorial code **0000 is a placeholder**, not a confirmed territorial classifier;
- **FNO_code="", FNO_name="" are placeholders** awaiting SINTEZ at upload
  [D220], [D235], [D260]. Do not use the spreadsheet's `013 006` as confirmed KPP1 FNO;
- ZU_area 6.48824 ha -> **6.4882 ha** per [D223] (4 decimals);
- heights describe the R1 model: h_relief 171.05, h_otn 8.65, h_abs 179.70.
  Spreadsheet 169.65/8.95/178.60 is not silently mixed with the accepted Revit zero;
- `s_obsh`, `s_naz`, `s_podz`, `spp_gns` remain empty/unconfirmed: the spreadsheet
  repeats 27124.36/28480.578 for all nine buildings, not a KPP1-specific area schedule,
  and basement area is empty. Unknown values are not guessed as zero. These are V011
  failures, not deferred checks or evidence of a delivery-ready customer passport;
- no signature, no upload, no cadastral authenticity or architectural approval claimed.

## Published artifacts and validator receipts

Durable directory: **`G:/Мой диск/AGR-evidence/1255-kpp1-msk77/site-v003/`**.
`evidence-SHA256SUMS.txt` binds final FBX, ZIP, GeoJSON, actual render and receipt bytes.
Small GeoJSON/export/validation/parity receipts are also committed here; large binaries
and NPZ dumps stay outside Git (no LFS).

Commands (exit **1** for each validator; expected exact remaining failures):

```bash
uv run python tools/qa/validate_package.py "G:/Мой диск/AGR-evidence/1255-kpp1-msk77/site-v003/SM_Kpp_1.zip" --profile vpm --scene --json
uv run python tools/qa/validate_package.py "G:/Мой диск/AGR-evidence/1255-kpp1-msk77/site-v003/0000_Kpp_1.zip" --profile npm --scene --json
```

| Stage | VPM | NPM | Exact boundary |
|---|---|---|---|
| V001 | **pass** | **fail** | NPM FBX count 1 (requires 2..21), missing `0000_Kpp_1_Ground.fbx`; no Ground invented |
| V011 | **fail** | n/a | Six mandatory empty fields: FNO_code, FNO_name, s_obsh, s_naz, s_podz, spp_gns |
| V013 | **not_run** | n/a | Local-origin/geometric-centre/shared-pivot findings pass; survey MSK-77 point subset unimplemented, not promoted to pass by fit |
| V014 | n/a | **not_run** | NPM survey position/angles stage unimplemented; numeric absolute-coordinate readback above is separate evidence |

### Complete non-pass stage list (nothing deferred into a pass)

VPM: **V003 not_run** (quad master not supplied), **V004 review** (co-directional
clearance: 0 below 5 mm, 166 in band, 107934 above 20 mm), **V010 not_run** (UCX coverage
and offsets not implemented), **V011 fail** (six fields above), **V012 review** (archive
building-index naming), **V013 not_run** (survey check), **V015/V016/V017 not_run** (manual).
V001/V002/V005/V007/V008/V009 pass in this run; these stage passes cover implemented
subsets only. NPM: **V001 fail**, **V003 not_run** (master), **V004 review** (0 below
5 mm, 108 in band, 20266 above 20 mm), **V014/V015/V017 not_run**.

The clearance pair counts differ after arbitrary plan rotation; the current checker is
orientation-sensitive. We do not transfer the 98/52 source-hash-bound [D256] pair waiver
to these new lists or claim xView is fixed. #1244's xView source residuals (112 VPM / 12 NPM)
are not waived by this placement. Final AGR Tools check waits for Max [D255]; visual,
SINTEZ and manual approvals remain open. **passed=false**, for both packages and delivery.

## Reproduction and tests

```bash
# Always a NEW output directory; source R1 stays unchanged.
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python-exit-code 1 --python jobs/KPP1/site-1255/place_package.py -- "G:/Мой диск/AGR-evidence/1230-kpp1-r1/r1-v002" "<new-version-directory>"
# In 4 separate processes: source/output x VPM/NPM, new dump names each time.
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python-exit-code 1 --python jobs/KPP1/site-1255/dump_vertices.py -- "<fbx>" "<new.npz>" "<new.json>"
uv run pytest -q -p no:cacheprovider tests/jobs/test_kpp1_site_1255.py tests/test_decisions.py tests/qa/test_geojson_d220_customer_convention.py
```

RED: `5234b8e5` tests-first commit, 1 failed (producer missing), then 1 passed.
Focused verification before evidence-pinning tests: **59 passed / 0 failed**.
Generated rigid-distance probe: seed 1255, 100 point pairs/profile, **200/200**.
Fail-closed: empty/partial/wrong-source hashes, alternative orientation, unsupported
profile, nonfinite point/angle/origin/zero (12 cases), output-input resolved alias,
existing directory with `.partial` sentinel, fresh-process alias refusal.
Native initial regression: factory-empty `scene.world=None` failed thumbnail in v001;
explicit World creation fixed it, v002/v003 exited 0. Failed v001 log retained in evidence.
An initial diagnostic dump used MSYS `$PWD` and failed with `\\c\\Users...`; rerun used
native/relative paths (environment-only repair, no source changes).
Full-suite exact-head receipt and final affected counts are in the PR Author receipts.
