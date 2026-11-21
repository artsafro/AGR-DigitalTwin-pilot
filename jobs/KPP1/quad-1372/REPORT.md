# KPP1 quad editable master from R1 — #1372 (F26), master `quad-v002`

**Кратко (RU).** Собран полностью квадовый редактируемый мастер KPP1 `v002` из утверждённого R1 (`r1-v002`). R1 не
изменён, новая версия лежит рядом. По решению Артёма D289 перекрытия R1 до 5 мм объединены: 13 зон на 4 фасадных
плоскостях. Вершины прижаты к одной плоскости (≤ 5.0 мм), выполнено точное объединение, удалён скрытый двойной слой
(244 грани, 0.91 м²) и висящий лоскут R1 (19.5 см²). Каждое изменение перечислено в `quad-build-v002.json`.

Результаты:
- V003 «master quads» — **pass**: 61 839 + 252 квада, 0 треугольников, T-junction 0.
- xView — **0 / 0** и на мастере, и на производной NPM (было 166 / 169 пар).
- NPM: 124 182 tris (≤ 150k, D010).
- `agr vpm-to-npm` и чтение в новом процессе проходят.
- Поверхность вне зон совпадает с R1: p95 0.5 мкм, max 5.0 мм — это прижатая ступень 5 мм.

Не закрыто:
- шаг упаковки ждёт #1361 (`agr package-npm` ещё не в main);
- ручные V004/V015/V017 — как у R1.

Лист «до/после» (одни и те же камеры) лежит в evidence. Вопрос Артёму: открывать мастер в Max 2026 (вид квадов) для
приёмки? Путь: `G:/Мой диск/AGR-evidence/1372-kpp1-quad-master/v002/SM_Kpp_1.quad-v002.fbx`.

## Inputs (copies only, hashed)

| Input | SHA-256 | Where |
|---|---|---|
| R1 master `SM_Kpp_1.fbx` (r1-v002) | `1f46b0dd…b676` (checked by both scripts) | `G:/Мой диск/AGR-evidence/1230-kpp1-r1/r1-v002/`; copy in packet `source/` |
| #1318 packet `packet-r1-v002` (spec, recipes, R1 adapter) | `packet-r1-v002.SHA256SUMS.txt` | `C:/x/bench-npm-kpp1/packet-r1-v002`, copied, never written |
| R1 albedo `T_Kpp_1_001_Main_d_1.png` (renders only) | in evidence `SHA256SUMS.txt` | `C:/x/quad-1372/input/` |
| Zone plan `union-zones.json` (generated from R1) | `47c7fa97…46f6` | packet + evidence; `union-zones-v002.json` here is the same JSON with git LF line ends (other hash) |
| Packet `packet-quad-v002-r6` | `packet-quad-v002-r6.SHA256SUMS.txt` (30 files) | `C:/x/quad-1372/packet-quad-v002-r6` |

The v005 look renders, the delivered reference #1371, R6 (#1352) and the window generator (#1345) were not applied.
The look is checked against R1 with the same cameras; R6 and #1345 stay options and would change the approved look.

## Route (program per step)

| Step | Program | Why |
|---|---|---|
| Zone plan | `uv run` + `tools/blender/xview_dump.py` + `xview_gate.part_gate` (`plan_union_zones.py`) | Same kernel as `dt qa xview`, so the plan addresses the faces the gate counts |
| Union, T-junctions, pairing, split | Blender 5.1.2 headless (`build_quad_master.py … v002 <plan>`) | Owned exact boolean and bmesh; every operation is scriptable and logged. Max is not needed for a topology-only step |
| Checks | `run_checks.py … v002` (`dt qa xview`, `agr vpm-to-npm`, `agr validate`, readback) | Same toolchain as #1318 and v001, so numbers compare 1:1 |
| Before/After | Blender Workbench (`render_before_after.py`), PIL (`make_sheet.py`) | Fixed world cameras shared by Before and After (#1360 rule) |

## Algorithm v002 (step 0 is new, steps 1–3 as v001)

0. **Union of R1 overlaps (D289).**
   - **Plan.** R1 xView face pairs, taken up to 5.1 mm so that a pair at exactly 5.000 mm is not left to float rounding.
     They form 13 zones (130 faces), each on one axis plane, with a spread of ≤ 5 mm from the plane.
   - **Snap.** 159 vertices are moved onto the exact plane value. 156 moves are ≤ 0.78 mm; 3 vertices of the 5.000 mm
     step at x = 12.415 m move 5.000 mm.
   - **Union.** Blender EXACT boolean (self-union) of the loose parts that own zone faces: the main shell and the
     north-facade panel. The other parts are appended back unchanged; this is checked on UV, positions and material.
   - **Double layer.** The coincident opposite double layer is deleted: 244 faces, 0.913 m² for both sides.
   - **Weld.** The boolean created 51 new vertices; 7 of them are welded within ≤ 1.18 mm.
   - **Flap.** One dangling flap inside a zone is deleted: an R1 triangle with 2 open edges at (-6.255, 5.70, 3.32),
     1 949 mm².
1. T-junctions: 0 found after the union. R1 had 7 at 20 µm, measured by the validator kernel on R1.
2. Coplanar same-UV pairing produces 12 410 quads; 5 395 triangles stay unpaired.
3. Every unpaired triangle becomes 3 quads through its edge midpoints. Marks propagate through quads, so 61 839 quads
   result. The fan centres are new in v002: each one is kept > 2.1 mm from every vertex inside the midpoint polygon,
   which keeps the fan quads convex. 11 centres moved; 44 lie in faces with a straight source corner; 0 are below the
   clearance.

## Results (`run-quad-v002-r6b`, code `f3e7a71f`, packet unchanged = true)

| Check | R1 (#1318 run-r1-v003) | v001 (blocked) | **v002** | Status |
|---|---|---|---|---|
| V003 master quads (validator) | fail: 30 162 + 504 tris | review | **pass**: all quads, no T-junctions | pass |
| Quad share (render meshes) | 0 % | 100 % | **100 %** (Main 61 839, Glass 252) | pass |
| T-junctions (validator, 20 µm) | 8 (FBX) / 7 (m) | 24 | **0** | pass |
| xView master (2 mm / 5 mm) | 0 v / 166 face pairs | 20 v / 330 | **0 / 0**, bow-tie 0 | pass |
| xView derived NPM | 0 v / 169 | 20 v / 749 | **0 / 0**, bow-tie 0 | pass |
| NPM triangles [D010 ≤ 150k] | 30 666 | 123 701 | **124 182** (Main 123 678 + Glass 504) | pass, accepted D289 |
| `agr vpm-to-npm` from the new master | exit 0 | exit 0 | exit 0 | pass |
| Fresh-process FBX readback (master / NPM) | — | 0 / 0 | 0 / 0 | pass |
| `agr validate` other stages | V002, V005, V006, V012 pass; V004 review | same | same (V004 review: 399 co-directional pairs 10–20 mm, manual) | same |
| Package #1361 (`agr package-npm`) | — | not_run | **pending**: #1361 open, no command on main (D289) | not_run |
| Open edges (Main) | 19 edges, 9.015 m | — | 26 edges, 8.890 m (only the R1 sheet at x = -6.255; flap removed) | no new hole |
| Non-manifold edges (Main) | valence 3: 1 (88 mm); valence 4: 1 (6.4 mm at 12.42, 0.82, 3.9) | — | valence 4: 8 edges, 0.608 m on the line x 12.415, z 3.9, y 0.82–1.42 | review (see below) |

### Distance to R1 (two-way, float64 rechecked)

| Mesh / direction | Samples | max | p95 | Note |
|---|---|---|---|---|
| Main new → R1, outside zones | 1 226 426 | 4.753 mm | 0.48 µm | max on the snapped 5 mm step |
| Main R1 → new, outside zones | 299 390 | 5.000 mm | 0.48 µm | the 5.000 mm step |
| Main new → R1, inside zones | 10 354 | 5.000 mm | 0.648 mm | snap moves |
| Main R1 → new, inside zones | 2 230 | 65.0 mm | 48.8 mm | R1 points on the deleted hidden double layer: no surface there on purpose |
| Glass both ways | 5 040 | 1.25 mm | 0.24 µm | needle strip, unchanged from v001 |

UV and material: corner UVs are interpolated per corner and seams are kept. Material index and finish (UDIM tile) are
copied to every child face. Finish faces: Plinth 8 973, Cassette RAL7047 12 696, Cassette RAL5015 16 751, Membrane
2 008, Frame 17 674, Door 2 571, Grille 1 166. Untouched loose parts keep UV, position and material (equal to 7 decimals, checked in the build).

### Review item: kissing edge at the merged 5 mm step

R1 has a 5.000 mm step between the faces at x = 12.415 and x = 12.42 above z = 3.9. xView flags faces at ≤ 5 mm. The R1
master passed only through float32 rounding, and its NPM failed (R1 NPM: 3 of its 169 pairs; v002-r3: 10 contacts).
Under D289 the step was merged onto x = 12.415. The two solids now meet along one edge line. That line is 0.61 m of
valence-4 edges and extends the 6.4 mm valence-4 edge R1 already has there. It is not a hole, not a bow-tie and not an
xView overlap. Splitting it would create zero-distance vertex pairs. Alternative, if Artem prefers: keep the step and
move one face ≥ 0.1 mm away from the threshold. That needs a new decision, because it is a nudge, not a delete or merge.

## Evidence

`G:/Мой диск/AGR-evidence/1372-kpp1-quad-master/v002/` + `SHA256SUMS.txt`, also committed as
`evidence-v002-SHA256SUMS.txt`:
- master: `master-quad-v002.blend` `fb566ff5…53bb`, `SM_Kpp_1.quad-v002.fbx` `7a95e9ca…43c6`;
- build record: `quad-build-v002.json` `fd8ae20d…5041` (union record, snap log, deleted faces, welds, flaps, distances);
- plan: `union-zones.json`;
- run: `run-quad-v002-r6b/{run,master-readback,readback,master-xview,export-xview}.json`, `validate.log`;
- NPM: `0000_Kpp_1_01.fbx` `903f9fb5…b86c`;
- renders: `before-after/sheet-before-after-{tex,wire}.png` and 20 single renders.

Earlier scratch attempts (`packet-quad-v002`, `-r2`…`-r5`) stay in `C:/x/quad-1372/`. They were superseded:
- r1 had 12 vertex pairs from fan centres;
- r2 hit a straight source corner;
- r3 had 10 NPM contacts at the 5.000 mm threshold;
- r5 ran on uncommitted code.

Reproduce (new destinations only; existing outputs fail the run):

```bash
uv run python jobs/KPP1/quad-1372/plan_union_zones.py <R1 SM_Kpp_1.fbx> <new>/union-zones.json
cp -r C:/x/bench-npm-kpp1/packet-r1-v002 <packet> && cp <new>/union-zones.json <packet>/
blender -b --factory-startup --python jobs/KPP1/quad-1372/build_quad_master.py -- <packet> v002 <packet>/union-zones.json
# rehash <packet>/SHA256SUMS.txt; the first derive reseeds a recipe .pyc, so rehash once more after a first check run
uv run python jobs/KPP1/quad-1372/run_checks.py <packet> <new-run-dir> v002
blender -b --factory-startup --python jobs/KPP1/quad-1372/render_before_after.py -- <fbx> <albedo.png> <dir> after
uv run python jobs/KPP1/quad-1372/make_sheet.py <dir> <dir>/sheet.png tex
```

## History: v001 (blocked, kept)

v001 (`99bb5a94`) was the plain quadification of R1. V003 passed, but xView reported 20 vertex pairs and 330 face
pairs, and the validator found 24 T-junctions. All of these came from R1's own overlap zones. The block asked Artem two
questions, and he answered them in D289. Evidence: `G:/Мой диск/AGR-evidence/1372-kpp1-quad-master/v001/` +
`evidence-SHA256SUMS.txt`.
