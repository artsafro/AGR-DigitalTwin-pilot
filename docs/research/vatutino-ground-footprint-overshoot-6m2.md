# Research: where the +6.18 m² of Vatutino VPM ground footprint coverage come from (V003, PR #1153)

## Summary

The VPM `--scene` check with `--ground-area-m2 16743.96` reports *ground footprint coverage* fail:
**16,750.142879 vs 16,743.96 m², difference +6.182879 m²** (tolerance 0.25 m²). I read the run
`C:/x/t_5e2eb833/v009/` read-only and re-measured the FBX readback with the repo's own `shapely`
pipeline. The ground surface itself is **correct**: its top-down union is **16,743.843911 m²**, i.e.
*0.12 m² under* the reference (stair footprints replaced by stair solids), within tolerance. The entire
+6.18 m² is **MAF + Flora geometry merged into the same `SM_Vatutino_Ground.fbx`** (23 materials: 13
ground + 10 flora + 1 MAF) whose canopies/objects **overhang the site boundary by 6.30 m²**. The check
(`src/twinqa/scene.py` `_ground_footprint_findings`) unions every non-UCX render face, so it cannot
distinguish the ground surface from MAF/Flora. It is *not* a skirt, *not* vertical-face projection,
*not* overlapping duplicates, and *not* a real overshoot of the ground outline.

## Findings

All numbers below were measured by me (`python .venv` + `shapely 2.1.2` on
`C:/x/t_5e2eb833/v009/readback-vpm.json`), except where a source file is cited.

### 1. The reference area 16,743.96 m² = site − building footprint

- `jobs/VATUTINO-SITE/ground-build-v011.md:29` — *"GND-06 area and limit | S_ter 25,854.04 − S_pz
  9,110.08 = 16,743.96 m²"*.
- `jobs/VATUTINO-SITE/build_ground.py:253-257` computes it: `S_ter_m2 = round(boundary.area, 2)`,
  `S_pz_m2 = round(s_pz, 2)` (sum of `plan.holes` areas), `gnd06_vpm_limit = gnd06_limit(boundary.area - s_pz)`.
- So **16,743.96 = S_ter (site polygon) − S_pz (building footprint holes)**, both rounded to 2 dp.
  The building holes *are* cut into the ground surface (`plan.surface = boundary − holes − stairs`,
  `build_ground.py:185,197-204`).

### 2. What the check actually measures

- `src/twinqa/scene.py:941-946` `_ground_footprint_findings`: `geometry = [mesh for mesh in meshes if
  mesh not in ucx]` — **all** non-UCX render meshes, no material/object filter.
- `scene.py:801-806` `_topdown_area_m2` = `shapely` **union** of the XY projections of every face ring
  ("stacked coverings count once"). Vertical faces project to zero area; overlapping coplanar faces
  count once.
- Tolerance `GROUND_AREA_TOL_M2 = 0.25` m² (`scene.py:93`); pass requires `|measured − ref| < 0.25`.

### 3. The VPM Ground FBX is not ground-only

The readback `readback-vpm.json` has **728 meshes: 1 render mesh `SM_Vatutino_Ground` + 727 UCX**. The
render mesh holds **559,442 triangles** mapped to **23 materials** — 13 ground (`M_Vatutino_Ground_*`)
plus **10 flora species** (`Amelanchier_lamarckii_ID105`, `Tilia_cordata_ID101`, …) plus
**`M_Vatutino_Ground_MAF`**. The job-local drivers that assemble it (`prepare_assembly.py`,
`assemble_delivery.py`) are in the PR #1153 branch (invoked in `C:/x/t_5e2eb833/v009/commands.json`),
not yet on `main`.

### 4. Decomposition of the measured 16,750.14 m² (my measurement)

| Set | faces | top-down union (m²) |
|---|---|---|
| All faces (exactly reproduces validator) | 559,442 | **16,750.142879** |
| Ground materials only | 46,479 | **16,743.843911** (−0.116 vs ref) |
| MAF + Flora | 512,963 | 2,545.023539 |
| MAF + Flora **outside** the ground outline | — | **6.298967** |

Identity: `16,743.843911 + 6.298967 = 16,750.142878`, and
`6.298967 − 0.116089 = 6.182878` = the validator's `difference_m2`. The ground surface is *not*
overshooting; it is slightly *under* the reference (stairs), and the whole positive residual is MAF+Flora.

### 5. What the +6.30 m² of overhang is (per material, union area outside the ground outline)

| material | area outside (m²) | kind |
|---|---|---|
| `Amelanchier_lamarckii_ID105` (tree) | 4.2209 | canopy overhang |
| `Stephanandra_incisa_Crispa_ID223` (shrub) | 1.0185 | shrub overhang |
| `Physocarpus_opulifolius_Diabolo_ID205` (shrub) | 0.4677 | shrub overhang |
| `M_Vatutino_Ground_MAF` | 0.4323 | MAF piece overhang |
| `Crataegus_mollis_ID103` (tree) | 0.0911 | canopy overhang |
| `Sorbaria_sorbifolia_ID212` (shrub) | 0.0684 | shrub overhang |
| total (56 blobs) | **6.298967** | — |

The overhang is **56 disconnected blobs** spread around the site perimeter (e.g. blob centroids
(73.7,−52.7), (−77.6,−29.2), (27.8,0.8), (47.7,−21.1), …) — trees/shrubs planted along the boundary
whose crowns extend beyond the plot, plus a few MAF pieces. `M_Vatutino_Ground_Skirt` (3,685 faces)
projects to **0.0003 m²** (vertical faces), so the skirt is *not* the cause.

### 6. Classification

- ✗ **skirt / vertical faces** — skirt projects to 0.0003 m².
- ✗ **overlapping duplicate faces** — union counts stacked coverings once; duplicates sit on the
  ground, inside the outline.
- ✗ **real overshoot of the ground reference outline** — ground surface is 16,743.84 m², *under* ref.
- ✓ **MAF + Flora objects overhanging the site boundary**, included because the slice merges them into
  the Ground FBX and the check unions all non-UCX faces.

### 7. Same outline (holes, buildings cut)?

Yes for the ground itself: the ground surface uses the same outline as the reference (16,743.84 vs
16,743.96, −0.12 m² = stair footprints supplied as solids). The measured value diverges *only* because
the check unions the MAF/Flora overhang. Note: the run did **not** pass `--footprint-holes`, so
`ground footprint hole coverage` is `not_run` (`validate-scene-vpm-area.stdout:185-202`) — the hole-cut
claim rests on the scalar area match, not on an explicit hole-coverage check.

## How it applies to this repository

- `src/twinqa/scene.py` — `_ground_footprint_findings` (line 941), `_ground_area_finding` (864),
  `_topdown_area_m2` (801). The footprint check has no ground-vs-other filter; it trusts "Ground FBX =
  ground only", which the site slice violates.
- `jobs/VATUTINO-SITE/assemble_delivery.py` + `prepare_assembly.py` (PR #1153 branch) — merge
  Ground + MAF + Flora into one `SM_Vatutino_Ground.fbx`. This also drives the V008 fails (at most
  7 materials per object, 32,801 mirrored islands) and the 23-material single mesh.
- `jobs/VATUTINO-SITE/build_ground.py:253-257` — source of the reference (S_ter − S_pz).
- Evidence PNG: `G:/Мой диск/AGR-evidence/298-footprint/vatutino-ground-footprint-overhang.png`
  (SHA-256 in `SHA256SUMS.txt` next to it).

## Proposed next tasks

1. **S — Make the Ground footprint-coverage check measure ground only** (touches
   `src/twinqa/scene.py`). Add a ground-material filter to `_ground_footprint_findings` (or accept a
   `--ground-materials` allow-list) so MAF/Flora faces are excluded from `_ground_area_finding` and the
   hole check. Value/effort **S**: one-line geometry filter; turns the +6.18 false-fail into a pass
   (ground = 16,743.84 m², within 0.25). **Advances #298**.

2. **S — Emit MAF and Flora as separate FBX/packages in the site slice** (touches
   `jobs/VATUTINO-SITE/assemble_delivery.py`). Keep `SM_Vatutino_Ground.fbx` ground-only per the
   regulation (reg p.28 §3.9/3.10, `SM_{Address}_Ground` grammar) instead of one 23-material mesh.
   Value/effort **S**: reuses the NPM split (surface / MAF / Flora already tracked separately); also
   clears V008 material-count and mirrored-island fails. **Advances #298** and unblocks **#425** / **#426**.

3. **M — Clip MAF/Flora placement at the site boundary so crowns/objects do not overhang the plot**
   (touches `jobs/VATUTINO-SITE/place_site.py` / `src/dt_ai/placement/engine.py`). The 6.30 m² overhang
   is a genuine (small) placement defect — tree/shrub crowns and a few MAF pieces cross the boundary.
   Value/effort **M**: adds a boundary-containment post-step; fixes the residual even after fixes 1-2.
   **Advances #425** (MAF placement) / **#426** (Flora placement).

## Open questions for the user

1. Is the single `SM_Vatutino_Ground.fbx` containing MAF + Flora intentional for this *site slice*
   (#298), or a temporary assembly? A regulation-correct VPM Ground package should be ground-only, with
   MAF and Flora in their own packages — which of the two fixes (check filter vs separate FBX) do you
   want first?
2. Should the footprint check tolerate a documented MAF/Flora overhang (raise tolerance), or must the
   placement actually clip crowns at the boundary (fix 3)?
3. The reference 16,743.96 uses `round(..., 2)` on S_ter and S_pz separately; the true
   `boundary.area − s_pz` may differ from 16,743.96 by up to ±0.01 m². Worth pinning the reference to
   the unrounded value in the delivery driver?

## Agent trace

- Agent: Hermes dt-worker-deepseek, card t_8961e2f5
- Read-only: run `C:/x/t_5e2eb833/v009/` (commands.json, readback-vpm.json, validate-scene-vpm-area.stdout)
- Re-measured: `.venv/Scripts/python.exe` + `shapely 2.1.2` on `readback-vpm.json` (union of 559,442 face rings)
- Evidence: `G:/Мой диск/AGR-evidence/298-footprint/vatutino-ground-footprint-overhang.png` (+ SHA256SUMS.txt)
- No code changes outside `docs/research/`
