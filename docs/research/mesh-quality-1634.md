# G22 delivered NPM calibration (#1634)

Кратко для Артёма: эталон правильный. Raw score ошибочно сравнивал треугольный
экспорт G22 с quad-мастерами: **63.234 / 64.558**. Явная диагностическая сшивка
прямоугольных копланарных пар, как в #1618, даёт **92.315 / 92.060** — выше KPP1
v003 whole на **14.969 / 14.714**, выше отклонённых углов на **15.631 / 15.376**.
PSU275 остаётся выше: **99.593**. Веса, core и обычный режим не изменены; исходники,
UV, материалы и сданные пакеты не перезаписывались. D338 остаётся WARN-only:
доля квадов достаточна во всех трёх мешах, щепки корпусов 002/003 дают предупреждение.

## Scope and representation correction

The score is an editable-master diagnostic, not delivery acceptance. G22 inputs are
**already triangulated delivery FBX**. Raw `tri_share=1`, `irregular_area_share=1` and
`pole_share=0.995/0.977` measure export diagonals, not Artem's accepted grid.

Correction: explicit `--rejoin-rectangles`, off by default. On evaluated temporary
meshes only, Blender `bmesh.ops.join_triangles` uses face/shape limits of 1 degree,
matching [#1618's census](body-modelling.md#2-эталон-g22-измерения).
Material boundaries are preserved; UV/seam/sharp delimiters are ignored for this
**geometry-only diagnostic**, never for an export. No mesh is saved. The report
records normalization mode, per-object before/after face counts, Blender version
and the unchanged source hash. Recorded JSON inputs cannot request native rejoining.
Quad-only inputs bypass BMesh entirely, preserving their measurements exactly.
This is reconstructed topology, **not proof of the original editable topology**.

No component weights, thresholds, default raw behavior or acceptance rules changed.
We do not suppress remaining cap/entrance triangles (BM-04), infer glass from the
single atlas, or exempt arbitrary regions to increase scores. Texture-only openings
explain why the body-face split differs from PSU275; the residual penalty is reported,
not a reason to alter the etalon. A cross-profile universal score is not claimed.

## Inputs and evidence

Copies only, SHA256 checked against `C:/x/body-training/SHA256SUMS.txt` before the
first run and against every CLI report afterwards:

| File | SHA256 | Measured mesh objects |
|---|---|---|
| `0707_Garibaldi_22_01.fbx` | `d60d92677671bba0b5fca40e7344f6d581e23706c0880ca2484126132adee7b6` | `SM_Garibaldi_22_001_Main` |
| `0707_Garibaldi_22_02.fbx` | `f4023d6611e8f775f5971593f7f39641f3a36e493732093018b98ed563999c67` | `SM_Garibaldi_22_002_Main`, `SM_Garibaldi_22_003_Main` |

**The _02 row scores the whole file, both objects, not just corpus 002.** No object
was silently dropped. Units: metre world coordinates, Blender FBX importer applies
the FBX unit transform; census thresholds use metres. Blender 5.1.2, isolated
factory-startup/disable-autoexec process; no live scene or delivery output touched.

Evidence: `G:/Мой диск/AGR-evidence/1634-g22-calibration/`:
- `r1/g22-01.json`, `r1/g22-02.json`: original raw CLI runs.
- `r1/*-rejoined.json`: initial diagnostic experiment; retained, not reused as final.
- `r2/`: final normalized G22 runs, six previous calibration rows rerun both raw and
  normalized (12 CLI runs), native #1618 dumps and fresh per-band censuses.
- `SHA256SUMS.txt`: 27 evidence files, manifest SHA256
  `bf25840b4a0c42d039c19adde35d67eb6bd59227b481d83f6fdede8bdb98a7a3`.

No customer geometry, atlas, binary or polygon dump is committed. Small aggregate
measurements are in [calibration.json](mesh-quality-1616/calibration.json).
Historical #1616 evidence and loop logs remain unchanged.

## Before / after: all components

Shares, not percentage points. `body` is the raw body-face share, not its rescaled
penalty (`max(0,body-0.5)/0.5`). `irr` is irregular **area** share. G22 row labels
`raw`/`rejoined` explicitly distinguish the two representations.

| Row | Score before | Score after | tri | ngon | sliver | pole | body | weld | long | irr | seam |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KPP1 v002 whole | 77.341 | 77.341 | 0 | 0 | .232562 | .168938 | .999305 | .093254 | .000097 | .223801 | 0 |
| KPP1 v002 corners | 76.423 | 76.423 | 0 | 0 | .224302 | .169538 | .997735 | .098477 | 0 | .296645 | 0 |
| KPP1 v003 whole | 77.346 | 77.346 | 0 | 0 | .233161 | .169463 | .999170 | .092521 | .000097 | .223231 | 0 |
| KPP1 v003 corners (rejected) | 76.684 | 76.684 | 0 | 0 | .221020 | .174416 | .997589 | .091474 | 0 | .282978 | 0 |
| KPP1 v003 rest (accepted) | 77.402 | 77.402 | 0 | 0 | .234426 | .168265 | .999335 | .092406 | .000107 | .218385 | 0 |
| PSU275 Main+MainGlass | 99.593 | 99.593 | 0 | 0 | .007129 | .002201 | .371950 | .032154 | 0 | .004191 | 0 |
| G22 _01 raw | 63.234 | — | 1 | 0 | .386103 | .994820 | .552596 | .153613 | .016209 | 1 | .000009 |
| G22 _01 rejoined | — | 92.315 | .183661 | 0 | .113869 | .014274 | .509015 | .229069 | .020494 | .182298 | .000012 |
| G22 _02 raw | 64.558 | — | 1 | 0 | .220583 | .977106 | .604530 | .116852 | .008373 | 1 | .000156 |
| G22 _02 rejoined | — | 92.060 | .233947 | 0 | .100243 | .052610 | .558189 | .171862 | .009848 | .104797 | .000217 |

All nine components of every previous row are unchanged, raw and normalized (12/12
reports checked). G22 is 7.278/7.533 below PSU275, but at least **14.714 points above
KPP1 v003 whole**; regression floor is an explicitly stated 10-point clear margin.
Remaining G22 costs include cap/entrance triangles, their irregular-area and sliver
contributions, concave body creases and, for _02, body-face share. Whole-object
sliver shares are not D338's typical-facade shares and use a different definition.

## D338: typical facade, WARN-only

Fresh run of the unchanged #1618 `dump_mesh.py` + `band_census.py`: face centres
6.5 m above bottom through 4 m below top; facade `abs(normal.z)<0.2`.
Sliver = triangle minimum angle <5 degrees (#1618), not the score core's <10 degree
triangles / <30 degree quads. Denominator is reconstructed nonzero-area faces.
Do not reinterpret a WARN as rejection of the accepted etalon.

| Object | Faces | Triangles | Quads | Quad share (>=95%) | Slivers | Sliver share (<=0.5%) | Observation |
|---|---:|---:|---:|---:|---:|---:|---|
| G22 001 | 40192 | 983 | 39209 | 97.5542% | 103 | 0.2563% | no warning |
| G22 002 | 19210 | 756 | 18454 | 96.0645% | 125 | 0.6507% | sliver WARN |
| G22 003 (also in _02) | 15538 | 276 | 15262 | 98.2237% | 99 | 0.6371% | sliver WARN |

## Reproduce and verify

Create a **new** evidence directory first; the CLI refuses existing report paths.

```bash
uv run python tools/qa/mesh_quality_score.py C:/x/body-training/garibaldi/npm_etalon/0707_Garibaldi_22_01.fbx --out NEW/g22-01-raw.json
uv run python tools/qa/mesh_quality_score.py C:/x/body-training/garibaldi/npm_etalon/0707_Garibaldi_22_01.fbx --rejoin-rectangles --out NEW/g22-01-rejoined.json
```

Repeat for `_02`; the fixture records every previous input and its zones/exclusions.
For each row rerun raw and `--rejoin-rectangles` with those same zones. For D338,
run the existing #1618 dump through `dt_ai.core.blender_runner.run_blender`, then
`uv run python docs/research/body-modelling-1618/band_census.py DUMP.npz --out NEW/bands.json`.
Source hashes must still match; no rerun grants model acceptance.

Regression RED: tests-first commit `944c6238`, 3 failed / 154 deselected (missing
opt-in argument and G22 fixture). Affected tests and final head receipts are in the PR.
Full suite: deferred to merge batch (rule 68).
