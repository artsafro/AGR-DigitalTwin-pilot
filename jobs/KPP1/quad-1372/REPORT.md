# KPP1 quad editable master from R1 — #1372 (F26), run `quad-v001` — NOT PASSED, needs Artem

**Кратко (RU).** Собран полностью квадовый мастер KPP1 из утверждённого R1 (`r1-v002`), R1 не тронут.
V003 «master quads» теперь **pass** (61 602 + 252 квада, 0 треугольников), поверхность совпадает с R1
(p95 < 1 мкм, max 0.29 мм Main / 1.25 мм стекло). Но два критерия не выполнены и требуют решения Артёма:
1) xView мастера = 0 недостижим без правки утверждённой геометрии R1 — в самом R1 уже 166 пар перекрытий
   (112 граней); разбиение квадов в этих зонах дало 24 T-junction и 20 пар вершин;
2) всеквадовый мастер стоит треугольников: NPM 123 701 tris (R1: 30 666), бюджет 150k [D010] соблюдён.

## Inputs (copies only)

| Input | SHA-256 | Where |
|---|---|---|
| R1 master `SM_Kpp_1.fbx` (r1-v002) | `1f46b0dd…b676` | `G:/Мой диск/AGR-evidence/1230-kpp1-r1/r1-v002/`, copy in packet `source/` |
| #1318 packet `packet-r1-v002` (spec, recipes, R1 adapter) | manifest kept as `packet-r1-v002.SHA256SUMS.txt` | `C:/x/bench-npm-kpp1/packet-r1-v002` (copied, never written) |
| New packet `packet-quad-v001` | `SHA256SUMS.txt` (29 files) | `C:/x/quad-1372/packet-quad-v001` |

Not used in this run (time-boxed, see open items): delivered reference #1371, v005 look renders, R6 (#1352), window
generator (#1345) — all listed as options only.

## Route (program per step)

| Step | Program | Why |
|---|---|---|
| T-junction weld, pairing, split | Blender 5.1.2 headless (`build_quad_master.py`) | owned, scriptable bmesh, exact same-surface ops; Max not needed for a topology-only step |
| Readback, xView, derive NPM, validate | Blender + `dt qa xview`, `agr vpm-to-npm`, `agr validate` (`run_checks.py`) | same toolchain as #1318, so numbers compare 1:1 |

Algorithm: (1) 7 T-junction vertices (20 µm, [D200]) welded into the long edge and the face re-triangulated;
(2) maximum-ish matching of coplanar (10 µm), strictly convex, UV-continuous, same-material, consistently wound
triangle pairs → 12 426 quads; 5 324 triangles stay unpaired, lower bound 5 205 (odd planar patches), so the
matching is within 2% of optimal; (3) every unpaired triangle → 3 quads via edge midpoints + centroid, marks closed
over quads (0 / 2 opposite / 4 edges) so each split edge is split on both sides.

## Results (`run-quad-v002`, packet unchanged = true)

| Check | R1 (#1318 run-r1-v003) | Quad master v001 | Status |
|---|---|---|---|
| V003 master quads | fail: 30 162 + 504 tris | **pass**: Main 61 602 quads, Glass 252 quads, 0 tris (UCX tris excluded by rule) | pass |
| Quad share | 0 % | 100 % (render meshes) | pass |
| Edge loop continuity (validator, FBX readback) | 8 T-junctions | **24** T-junctions | review — worse |
| Distance new→R1 Main (1 232 040 samples) | — | max 0.293 mm, p95 0.48 µm | ≤ 2 mm tolerance: pass |
| Distance R1→new Main (301 620) | — | max 0.042 mm, p95 0.48 µm | pass |
| Distance Glass both ways (5 040) | — | max 1.25 mm, p95 0.24 µm | pass (needle 10 mm × 5.23 m strip) |
| xView master (2/5 mm) | 0 v / 112 f, 166 pairs | 38 v (20 pairs) / 231 f, 330 pairs, 2 bow-tie pairs | **fail** |
| xView derived NPM | 0 v / 116 f, 169 pairs | 38 v / 425 f, 749 pairs | **fail** |
| NPM triangles [D010 ≤150k] | 30 666 | 123 701 | pass (4.0× R1) |
| `agr vpm-to-npm` from new master | exit 0 | exit 0 | pass |
| Fresh-process FBX readback (master + NPM) | — | exit 0 / exit 0 | pass |
| Package #1361 (`agr package-npm`) | — | not_run: #1361 open, no command on main | not_run |
| Before/After sheet | — | not made | open |

Distances are float32 BVH with every sample above 1 µm rechecked in float64 (`float64_rechecked` in `quad-build.json`).
UV: per-corner interpolation, seams kept; material index and finish (UDIM tile) copied to every child face;
custom split normals are dropped (flat-shaded faces, `use_smooth` copied).

## Why not passed — decisions for Artem

1. **xView 0 on the master needs a geometry change of approved R1 [D254].** R1 itself has 166 face pairs
   (contact 67, area 23, area+contact 76). A same-surface quad master inherits them; the midpoint splits inside those
   overlap zones add vertex pairs and T-junctions (24 vs 8). Clearing them means deleting/merging overlapping member
   faces of R1. Recommendation: allow it as a separate, distance-bounded step (≤ 5 mm) before quadification.
2. **Triangle cost of a 100 %-quad master.** NPM goes 30 666 → 123 701 tris (within 150k). Alternatives: accept; or
   permit a quad-dominant master (V003 rule change, ~19 k quads + 5.3 k tris, NPM ≈ 30.7 k).

## Evidence

`G:/Мой диск/AGR-evidence/1372-kpp1-quad-master/v001/` + `EVIDENCE-SHA256SUMS.txt`:
`master-quad-v001.blend` `5368925f…`, `SM_Kpp_1.quad-v001.fbx` `714084a6…`, `quad-build.json` `c518028f…`,
`run-quad-v002/{run,master-readback,readback,master-xview,export-xview}.json`, `validate.log`, NPM `0000_Kpp_1_01.fbx` `f9664f41…`.

Reproduce (new destinations only; outputs that exist fail the run):

```bash
cp -r C:/x/bench-npm-kpp1/packet-r1-v002 <new-packet>   # then rehash after the build (pyc reseeded on first derive)
blender -b --factory-startup --python jobs/KPP1/quad-1372/build_quad_master.py -- <new-packet>
uv run python jobs/KPP1/quad-1372/run_checks.py <new-packet> <new-run-dir>
```

Auto-open in Max 2026 (quads view): not asked in this headless run; path for Artem:
`G:/Мой диск/AGR-evidence/1372-kpp1-quad-master/v001/SM_Kpp_1.quad-v001.fbx`.
