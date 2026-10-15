# Ground surface — requirement sheet

**Area and profiles:** Ground surface (благоустройство relief/plane: zones, parking spaces,
lawn-level greenery, tree grates, road markings), NPM and VPM. In scope: relief/plane geometry,
perimeter extrusion, Ground triangle budgets, relief texture density and UV, Ground naming,
Ground collision surface, placement. Out of scope: GroundEl/MAF (see `groundel-maf.md`), Flora,
OKS and usable-roof landscaping, Ground textures production (roadmap §7.10), package production;
UCX construction details are in `ucx.md`.

**Readiness:** [roadmap §7.9](../../research/capability-roadmap.md#79-ground-surface--l1-partial)
records L1-partial. This sheet is T-GND-1's rule index. There is no skill, no `dt ground` tool
(T-GND-3), and no benchmark (T-GND-4). v008 awaits the user's review (T-GND-2). This is not a
delivery acceptance; no L2 or L3 is claimed.

**Reading:** the table is an index, not replacement rule text. `reg p.N` is the one-based
physical PDF page of [the supplied regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf).
`[D<n>]` is [the decision log](../../decisions.md). `L2 coverage` names implemented checks
only (with limits); `none` means manual today. Coverage was checked against
[the implementation inventory](../validation.md#implementation-status-inventory-static-audit)
and [`scene_findings`](../../../src/twinqa/scene.py).

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| GND-01 — Area membership and bounds | reg p.1–2 §2; reg p.21 §2 | Relief surface or plane inside the plot with a texture showing landscaping/transport zones, parking spaces, lawn-level greenery, tree grates and road markings; bounds = whole land plot when the project covers the whole development territory, else the boundary of the construction stage; nothing outside the current stage; usable-roof landscaping belongs to the OKS | Same bounds and the same exclusion of usable-roof landscaping | Manual overlay of the model outline on the designed-plot boundary layer of the SPOZU plan (see Project practice) | none | [Profile terms](../npm-vpm.md#terms) |
| GND-02 — Ground FBX and surface texture sets | reg p.6 §1.2; reg p.6–7 §1.5 | One Ground FBX is mandatory in the ZIP; Ground FBX holds up to 22 texture sets, of which the Ground surface max 20 sets, also limited by texel density (GND-08); GroundGlass without texture sets | VPM texture contract instead (UDIM, GND-09); Ground FBX mandatory, see the NPM/VPM profile file | Manual count of Ground surface texture sets in the exported FBX | none | [NPM structure](../npm-vpm.md#npm-appendix-1) |
| GND-03 — Perimeter extrusion ≥ 1 m | reg p.7 §3.4; reg p.28 §3.7; reg p.10 §6.2; reg p.31 §3.1–3.4 | Perimeter polygons of the Ground geometry extruded down by at least 1 m; texel density does not apply to them | Perimeter polygons extruded down by at least 1 m, textured with placeholders of the averaged colour of the source polygons (VPM placeholder 256×256 px, one colour, no alpha) | Manual readback: lowest perimeter Z versus the surface edge, placeholder material on the skirt | none | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| GND-04 — NPM shared triangle budget | reg p.7 §3.6; [D097] | Ground + GroundEl + Flora ≤ 180 000 triangles in total; starting split surface 50k / MAF 60k / Flora 70k, corrected per project [D097]; the split is project practice, not a regulation limit | See GND-06; the NPM ceiling is not reused | Sum of exported non-UCX triangles of the complete Ground FBX | V003 — `scene_findings`, NPM `role=ground` total only | [Profile budgets](../npm-vpm.md#npm-appendix-1), [implementation](../../../src/twinqa/scene.py) |
| GND-05 — NPM surface as a height field (project decision) | [D097]; reg p.7 §3.1 | Ground surface ≤ 50 000 polygons (project decision), quads of about 3 m, finer at material contours and slope breaks; minimum triangles for the silhouette (reg p.7 §3.1); smoothing parameters of GROUND-PROJECTION are one-site values, not accepted | One Ground master derived to both profiles (project practice); no separate VPM surface cap, the hard limit is GND-06 | Manual: count surface polygons separately from GroundEl/Flora; compare relief with the vertical-planning elevations | none | [Ground modelling](../geometry.md#ground-modeling-npm-project), [C36, open](../conflicts.md#c-between-local-sources-project-decisionslessons) |
| GND-06 — VPM Ground triangle table | reg p.28 §3.10; reg p.29 §3.10; [D010] | See GND-04 | Limit of the whole Ground FBX excluding collision depends on (S_ter - S_pz), site area minus OKS footprint: up to 0.05 ha 300 000; 0.05–0.1 ha 705 000; 0.1–0.25 ha 1 125 000; 0.25–0.5 ha 1 650 000; 0.5–0.75 ha 1 950 000; 0.75–1 ha 2 625 000; 1–1.5 ha 3 150 000; more than 1.5 ha 4 500 000; the table is the hard limit, not figure 2.1 (reg p.40, 3 000 000) | Manual site-area minus footprint calculation and whole-Ground non-UCX triangle sum; V003 returns `review` for this limit | none | [VPM budget](../npm-vpm.md#vpm-appendix-2), [C1, decided by the user](../conflicts.md#a-inside-the-regulation) |
| GND-07 — Silhouette economy and small relief elements | reg p.7 §3.1; reg p.28 §3.3; reg p.32 §7 | Minimum triangles for the shape; curbs, steps, ramps and retaining walls are Ground geometry (project practice) | Same; the 5 cm baking rule names building details and excepts curb projections («Исключение: бордюрные выступы»), so curbs stay geometry | Manual comparison with the SPOZU plan and vertical planning | none | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| GND-08 — NPM relief texel density | reg p.10 §6.1–6.2; [D097] | Applies only to the relief surface within the plot: 10–40 px per linear metre (the text says «на кв.метр»; the user decided the linear unit [D097]); example 2048×2048 ↔ 204×204 m square; not applied to the perimeter extrusion, Flora, OKS, GroundEl; project textures 2K | See GND-09 | Manual metric UV measurement on the export; no implemented NPM density check | none | [NPM density](../uv-textures.md#npm-textures-app1), [C4, decided by the user](../conflicts.md#a-inside-the-regulation) |
| GND-09 — VPM UV and density | reg p.31 §2.1.1–2.1.6; reg p.32 §6.2; [D097] | NPM atlas contract, see GND-08 | `*_Ground`: UDIM only, one UV set on one channel; split geometry larger than one tile at the required density; tiles from 1001 strictly sequential; no mirrored islands; no visible seams; Diffuse 512–1706 px/m (project band 520–1706 px/m with 4K textures [D097]) | Exported UV readback plus archive tile sequence; density and seams manual | V008 — `scene_findings` UV channel/mirroring; `uv.sequential_tiles` filename sequence; density (V009) unimplemented | [VPM UV](../uv-textures.md#vpm-uv--udim), [UV implementation](../../../src/twinqa/uv.py) |
| GND-10 — Ground surface collision | reg p.36 §13.1–13.5; [D098] | n/a — no UCX in NPM | Collision built for the Ground surface (MAF, lighting and vegetation excluded); pieces convex and closed; shape tolerance ≤ 10 cm, especially on the perimeter; gap between pieces 2 mm – 1 cm [D098] | UCX triangle budget by readback; shape, coverage and gaps manual | V010 — `scene_findings` UCX triangle budget only | [UCX sheet](ucx.md), [C15, decided by the user](../conflicts.md#a-inside-the-regulation) |
| GND-11 — Ground names | reg p.11 §3.2; reg p.12 §3.3–3.4; reg p.33 §4.1–4.2; reg p.34 §4.2–4.4 | FBX `prefix_Address_Ground`; objects `SM_Address_Ground`, `SM_Address_GroundGlass`; textures `T_Address_Ground_{map}_{Slot}.png`; ≤ 254 characters, Latin/digits/underscore | FBX/GeoJSON/ZIP `SM_Address_Ground`; objects `SM_Address_Ground`, `SM_Address_GroundGlass`; collision `UCX_SM_Address_Ground_001..999`; textures `T_Address_Ground_{Type}_{Slot}.{UDIM}.png`; materials `M_Address_Ground_{Slot}`, `M_Address_GroundGlass_{Slot}` | Manual internal-name inventory; package-level name checks do not cover mesh masks | none | [NPM names](../geometry.md#naming---npm-reg-p10-13), [VPM names](../geometry.md#naming---vpm-reg-p33-36) |
| GND-12 — Placement and pivot | reg p.10 §8.1–8.2; reg p.32–33 §9.1–9.5; [D018] | Moscow coordinate system and heights, rotation as in the plan | Origin at world 0; Ground pivot at the geometric centre in X/Y, Z = project zero; all meshes in the FBX share the pivot (GroundGlass = Ground); rotation 0 after reset | Readback of origin, shared pivot and rotation; survey/project-zero truth manual | V013 — `_pivot_findings`, local/shared/centre subset only; V014 unimplemented | [Placement](../geometry.md#units-coordinates-pivots), [C19, decided by the user](../conflicts.md#b-regulation-vs-local-yaml--docs) |

## Project practice

Project practice from Artem's Ground grilling, rounds 1-3 (notes: hermes_kanban docs/grill/ground-2026-10-15.md). **This is project practice, not regulation**; it does not override the table.

- Source: the SPOZU DWG. Take the coverings sheet (or model space), hide everything else; needed: coverings, plant planting points, MAF placement points, plant and MAF specifications. Hatches -> contours (take existing contours); export contours per covering type, one DWG each.
- Boundary: the Ground boundary is the designed-plot boundary, an AutoCAD layer named like «граница проектируемого участка» / «граница ГП» (feeds GND-01).
- Methods in 3ds Max (all three used): A stitch + subdivide (planes per covering welded, Subdivide 3 m, split by material ID); B ShapeMerge onto a plane pre-cut into ~3×3 m polygons with stacked tiling UVs, or Boolean/Conform projection; C "layered cake" — the **default**: a base plane of the plot for the largest covering (e.g. tile) with equal stacked polygons for tiling, every other covering a separate plane inset on top with a 6 mm step, no overlap stitching, subdivide and unwrap each layer. Note: 6 mm lies inside the regulation's 5 mm – 2 cm spacing for co-directional overlapping polygons (reg p.29 §3.13).
- Flat first, then relief: the flat, textured Ground is always built first (most near-term projects are flat); heights come from the SPOZU vertical-planning sheet — elevation points -> relief surface — and the flat Ground is projected onto it; level differences and unevenness are worked separately afterwards.
- Curbs, steps, ramps and retaining walls are usually modelled as Ground geometry (GND-07); curbs stay geometry. The GROUND-PROJECTION "smooth < 20 cm, geometry ≥ 30 cm" rule is NOT a general rule; the user said that case was not done well (C36).
- Coverings: no fixed catalogue; usually ~18 materials (tile in different RAL/shades, water, asphalt, rubber, mulch, gravel, grass, wood decks/bridges, concrete); the 18 of GROUND-PROJECTION are a reasonable starting set.
- Textures and density: VPM 4K, NPM 2K; texel density in pixels per linear metre: NPM 10–40, VPM 520–1706 [D097].
- Budget split: one Ground master derived to both profiles; NPM 180 000 is met by NPM plants (single-sided polygons) and NPM MAF; starting split surface ≤ 50k / MAF ≤ 60k / Flora ≤ 70k, corrected per project [D097]; VPM usually fits, plants are replaced by VPM plants and MAF may be more detailed.
- Typical rejections (Ground-related): texture seams after unwrap (tiling broken); Ground collisions not convex, missing spacing between pieces or wrong Ground–collision distance; gaps; open polygons in VPM; flipped normals in VPM. MAF and Flora rejections are in their sheets.

## Source-image evidence

All numbers, units and limits in the table were visually checked on PyMuPDF 1.28.2
renders (matrix 1.6, no alpha) of physical pages 1, 2, 6, 7, 10, 11, 12, 21, 28, 29, 31, 32, 33, 34, 36, 40.
Renders kept locally under `C:/x/l1-evidence/ground-surface/` (outside the repository, not committed).
Reproduce with `uv run --extra pdf-review python` (the repository declares `pdf-review` as an optional extra):

```python
from pathlib import Path
import pymupdf

out = Path("tmp/l1-evidence/ground-surface")
out.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open("standards/source/Rasporyajenies19012026trebovaniya(2).pdf")
for number in (1, 2, 6, 7, 10, 11, 12, 21, 28, 29, 31, 32, 33, 34, 36, 40):
    page = doc[number - 1]
    page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False).save(str(out / f"p{number:02}.png"))
```

- **GND-01 — reg p.2:** «если проект относится к отдельному этапу строительства — благоустройство выполняется в пределах границ соответствующего этапа».
- **GND-03 — reg p.7 §3.4:** «Полигоны по периметру объекта геометрии благоустройства должны быть выдавлены вниз на расстояние не менее 1 метра».
- **GND-04 — reg p.7 §3.6:** «для благоустройства, его элементов и элементов растительности в сумме – 180 000».
- **GND-06 — reg p.29 §3.10:** «от 1 Га до 1,5 Га»; «до 3 150 000 треугольных полигонов»; «более 1,5 Га»; «до 4 500 000 треугольных полигонов».
- **GND-08 — reg p.10 §6.1:** «не меньше 10 пикселей на кв.метр, что при текстуре 2048×2048 соответствует квадрату со сторонами 204 на 204 метров, но не более 40 пикселей на кв.метр».

Conflicts are only pointed to via [the conflict register](../conflicts.md) (C1/[D010], C4/[D097], C15/[D098], C19/[D018], new open C36); none is decided here.

## L2 gaps

The table contains **12 requirement rows**: **8** with `none` and **4** with partial coverage.

- **GND-01:** boundary-layer overlay and stage membership.
- **GND-02:** surface texture-set count.
- **GND-03:** perimeter skirt depth and VPM placeholder.
- **GND-05:** surface-only polygon count and relief fidelity.
- **GND-06:** site-area minus footprint and hard table limit.
- **GND-07:** curb/step/ramp/wall presence and silhouette economy.
- **GND-08:** NPM linear density on the relief.
- **GND-11:** internal Ground name masks.

Partial rows GND-04/09/10/12 still leave work (surface-only share of the 180k, V009 density and seams, UCX shape/gap band, V014 and survey alignment). Candidates, not filed tickets; T-GND-3/4 remain.

## Documentation regression

`tests/test_area_requirement_sheet.py` discovers the sheet.
`tests/test_ground_surface_requirement_sheet.py` pins row IDs, sources, the VPM table numbers, the five anchors, the Project practice marker and the gap list, with generated negative probes.

RED: with the test committed first and this sheet and the C36 entry absent, the Ground test file gave
**11 failed**. GREEN: the area contract, Ground, MAF and Decor sheet tests give **80 passed**. Generated
negative probes rejected **104/104** column mutations, **24/24** source-cell mutations and **21/21** gap
mutations (generic contract), plus **14/14** required-source, **19/19** number/unit, **8/8** gap-bullet and
**10/10** practice-token/heading-order mutations (Ground test). These are documentation checks, not
geometry validators or delivery acceptance.
