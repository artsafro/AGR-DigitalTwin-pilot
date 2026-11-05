# AC08 (TEC26) L4 end to end through the kernel (#753)

Technical QA only, not acceptance: `passed=true` is not claimed. Generated numbers: `evidence/e2e.md` / `e2e.json`
(`run_e2e.py`), `evidence/album_compare.json`, `evidence/sintez_summary.json`. Binaries (source FBX, 16 kernel-state
FBX, silhouettes, album compare PNG, SINTEZ JSON): `G:/Мой диск/AGR-evidence/753-ac08-l4-e2e/` + `SHA256SUMS.txt`
(33 files, `sha256sum -c` OK; copy `evidence/DRIVE-SHA256SUMS.txt`).

## Inputs (paths found by the orchestrator, issue comment 2026-11-04)

| input | path | sha256 |
|---|---|---|
| source scene | `C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/2_kotelnya/Vlad_OKS/04-09 Geometry Final.max` (copy staged, never saved) | `eb0cffed…7852bd` (unchanged after the run) |
| source FBX (new) | `AC08_source_geomfinal.fbx`: 3ds Max 2026.3 batch (`dcc_batch.py max --version 2026`), nodes `АС.08` (180 polys) + `Colizii_044` (6), `export_geomfinal_fbx.ms` | in Drive SHA256SUMS |
| 08.max | `.../2_kotelnya/08.max`, also exported (`export_source_08max_fbx.ms`) | `595c393f…ee99c4` |
| delivered | pilot-v010 `package-vpm/SM_Nku_1/SM_Nku_1.fbx` + `export_meta.json` (Drive `559-tec26-oks-ac08-pilot-v010/`) | zip `2fe98379…8013bb` = Drive |
| album | no AC08 PDF album exists; slide 49 of `ТЭЦ26 на РР (1).pptx` (D171) + sheet `22Е56-АР2-1002-АС.08` (`sheet-facades.json`) | slide `256f32da…08a8fd` |

`08.max` is an earlier stage: DWG-linked spline layers, two DWG polymesh layers (91 + 9 polys) and `Box001`
(110 polys, no materials, no UV). The delivered pilot and #752 were built from node `АС.08` of
`04-09 Geometry Final.max` (the pinned `max-dump-008.json`), so that node is the source of this run.

## Gates

| # | gate | result | numbers |
|---|---|---|---|
| 1 | source FBX = pinned Max dump (positions per polygon corner, UV, material ids, UCX) | pass | 180/180 polygons, 193 vertices, max corner dev 5.7e-7 m, UV dev 4.9e-7, UCX 6.0e-7 m; FBX material names -> ids `Material #2/#4/#5 -> 1/2/3` = dump multisub |
| 2 | kernel invariants on the source (`invariants.py`) | FAIL | `no_visible_back_faces` 3107 px, open borders not hidden 16 (body) + 4 (plate), close overlaps 0 |
| 3 | kernel ops (#752 set: keep, primitive_box, embed, opacity plane, contour, join, simplify, move_rigid) | FAIL: 0/19 applied | every op is rolled back or refused; the same 19 verdicts as #752 (two offender counts differ, see below) |
| 4 | export -> readback parity of every candidate state | FAIL 13/17 | S15 not exported (material merge), S16/S17 lose UV on export (168/170 faces), S09 `bounds_m` 36.60343 vs 36.60342 (5-decimal rounding flip of a 1e-5 m float32 difference; #752 had 14/17 on the dump) |
| 5 | kernel output vs delivered pilot-v010 VPM FBX (pivot from `export_meta.json`: -33.9534, -0.1134, 0) | pass | surface distance 1.53e-5 m both ways (tol 1 mm), area 97.5350 = 97.5350 m², bounds 1.3e-5 m, UCX 1.5e-5 m, silhouette IoU N/S/W/E 1.00000, top 0.99592 (> 0.995) |
| 6 | album: slide 49 vs VPM / NPM renders, rib count per facade (`compare_facades.py`, rerun) | pass 4/4 | 1-2: 29/29/29, 2-1: 29/29/29, А-Б: 11/11/11, Б-А: 11/11/11 joints (slide / VPM / NPM), scale 0.997–1.005 |
| 7 | SINTEZ AGR Checker on the delivered ZIPs (rerun) | FAIL (known) | VPM 62 verified / 4 failed / 54 undefined: 2.1.1, 2.2.1, 2.3.17 (UCX not triangulated), 2.10.4.1; NPM 38 / 5 / 29: 2.1.1, 2.1.2, 2.1.6, 2.10.3.1, 4.1.4. Same as pilot-v010 |

Top-view IoU 0.99592 is below 1 only because edge-on wall triangles rasterise as 1 px lines differently in the
180-polygon source and the 386-triangle delivered mesh. Surface distance 1.5e-5 m shows that the surfaces coincide.

## #752 before/after table repeated on the FBX source

The before metrics equal #752 exactly (body 143f/152v open 16, knob 24f/25v open 12 with 12 triangles, plate
13f/16v open 4). All 19 verdicts are the same: ops 1-5, 8, 9, 11-19 are rolled back by `check_operation`, and ops
6, 7 and 10 are refused before any geometry change. Two offender counts differ. Op 15 (simplify body) has 45 open
borders against 65 in #752. Op 17 (simplify plate) has 3107 back-face pixels against 3108. The cause is that the
FBX starts 103 of the 180 polygons at a different corner, and that changes the fan triangulation and the
simplifier input. Full table: `evidence/e2e.md`.

## What this means

The new kernel does not change AC08. The source already breaks two of the kernel's absolute invariants:
3107 back-face pixels from direction (-0.58, -0.58, 0.58), plus open borders that stay visible. As a result,
every operation, `keep` included, is rolled back. The kernel output is therefore the source. It is the same
geometry as the delivered pilot-v010 within 1.5e-5 m, and the delivered package keeps its album (4/4) and SINTEZ
results.

The real-building barrier at tier 75 needs one of two things. Either the kernel judges invariants relative to the
source (no new offenders), or a repair operation (flip or close) runs first. That is a model/kernel decision for
Artem, together with the three open points of `../PILOT_REPORT.md` (roof colour, outer outline, UCX triangulation:
SINTEZ 2.3.17).

## Repeat

```
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --version 2026 --scene <copy of 04-09 Geometry Final.max> \
    --file jobs/TEC26-OKS/AC08/l4-e2e-v001/export_geomfinal_fbx.ms --card <card>        # output path inside the .ms
uv run python jobs/TEC26-OKS/AC08/l4-e2e-v001/run_e2e.py --source-fbx <AC08_source_geomfinal.fbx> \
    --delivered-fbx C:/x/tec26-oks/AC08/pilot-v010/package-vpm/SM_Nku_1/SM_Nku_1.fbx --work <new dir> --evidence <new dir>
uv run python jobs/TEC26-OKS/scripts/compare_facades.py jobs/TEC26-OKS/AC08/vpm_textures.json \
    jobs/TEC26-OKS/AC08/sheet-facades.json C:/x/tec26-oks/AC08/pilot-v010/renders \
    C:/x/tec26-oks/AC08/pilot-v010/readback/vpm.readback.json <new dir>
blender --background --factory-startup --python-exit-code 1 --python jobs/TEC26-OKS/scripts/run_agr_checker.py -- <dir with both zips> <out.json>
```
