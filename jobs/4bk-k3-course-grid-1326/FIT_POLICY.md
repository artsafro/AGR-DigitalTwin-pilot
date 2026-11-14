# One-tile fit checkpoint — #1326, v005

Historical v005 status: **bounded mask-aware one-tile strategies rejected**.
The cut-versus-budget question below was answered by Artem on 2026-11-14:
`geometry-cut-approval.json` authorizes a separate-copy cut experiment, not extra
UDIMs. Current textured candidate and unresolved QA: `CUT_RESULT.md`.
`pilot_passed=false`. This is not a proof of global one-tile impossibility, an
accepted UV layout, a textured result, or a final delivery. No scene/UV/map/geometry
was saved; daytime Max and source/delivery files remain untouched.

## Settled scope

`cap-base-seam-approval.json` records the 2026-11-14 answer and standing rule:
existing-edge breaks on caps, plinths, thin ends, reveals and stair parts need no
further question; enumerate them. The cohort remains 771 existing ID1 faces;
1,244 other-finish faces stay protected. Prior cohort, stair, ring and cap questions
are answered and must not be reopened. No new geometry cuts or extra UDIMs have
been authorized. Main-wall courses and the 38-course / 3.15 m contract remain fixed.

The approved complete chart now lists **295 existing seam edges**, **835 continuous
edges**, all **771 faces**, and maximum wrapped complete-edge residual
**0.005616646064 px**. This is source-chart evidence, not fresh exported UV QA.

## Fresh experiment and actual outcomes

Backend: Blender **5.1.2 background** on the hash-identical source copy, metric
scale 1.0. The v005 readback has **2,015 faces / 771 target / 1,244 protected**;
XYZ, topology, UV and IDs equal v004 exactly. Source/map hashes **10/10 unchanged**.

New reusable `tools/materials/course_grid_fit.py` consumes the chart produced
around `uvlayout_core` / `facadeatlas_core`. Only full Bricks1-repeat translations
are allowed; no rotation, reflection, density search, normalization, mesh cut or
unreported drop. Joint convention remains **10 mm inside the owner, centre 5 mm
inward**. No final replacement masks have been produced.

| Strategy | Measured result | What it establishes |
|---|---|---|
| Full-repeat canonical brick field, 4096, 512 px/m, 32 px tile border | **771/771 contained** | The plain brick field fits; bounding-box overflow is NOT the current blocker. |
| Joint-mask-compatible lattice copies, sample-count order / descending area / deterministic shuffle seed 1326 | **345 / 355 / 347 placed**, **426 / 416 / 424 unplaced** | These bounded placements fail the necessary required-versus-forbidden joint condition. Not a proof against arbitrary patch layouts. |
| Disjoint per-face cropped patches, existing `atlas_core._shelf`, 32 px unique gap, usable side 4032 px | **False**, 8 rectangles placed before first overflow; padded bounding-box area / usable area **14.980638650** | Conservative independent fallback fails too; this is not a minimum-area theorem and does not disallow compatible overlaps. |

Mask evidence: **3,242,148** source-texture-derived binary samples over all 771
faces; **67,131** ambiguous transition samples excluded, never treated as passing
coverage. The existing source Diffuse is classified near the known panel-joint
colour `(40,32,32)`; Bricks1's closest source colour has L1 distance 35, outside
the positive threshold. This is a necessary Diffuse-mask condition only, not
D/ERM/N equivalence, full path coverage, raster-width QA or mip approval.

Concrete best-run witness: `K3_StylobateWalls.001` face **1410** requires a panel
joint at candidate pixel **(1812,1860)**, while placed
`K3_StylobateStair.001` face **475** requires plain field there. Overwriting either
signature is rejected. All 416 unplaced face keys and conflicting owners are in
`fit-audit-v005.json` / `fit-1-with-owners.json`.

Canonical candidate polygon union: **50.219871374%** of the tile; with 16 px
per-side buffers, **52.065137539%**. Computed with Shapely polygon union, not summed
stacked faces or rectangles. These are **candidate-only** numbers: occupied UV
area alone does not prove appearance-equivalent reuse or unique-image padding.
A dry repeated-canvas alternative is retained in `dry-extra-canvases.json`, but
is deliberately NOT a minimum tile count, final budget or extra-tile export.

## One model-choice question

**Permit a geometry-cut experiment on a separate copy to isolate the painted
10 mm panel-joint zones, or change the one-tile budget?**

Recommended next experiment: keep one tile and authorize minimal planar loop cuts
at the inner boundaries of the painted joint zones, so narrow joint strips can
sample joint masters and the remaining brick can sample the shared repeat field.
Keep main-wall courses, physical density, XYZ surface, protected finishes and
source-face-to-output traceability; enumerate actual cut paths before applying.
This changes topology, so the existing-edge UV permission alone is not authority.
No fit success or painless topology outcome is promised before the experiment.

Alternative: authorize an extra-tile budget experiment without cutting geometry.
The required final tile count is **not established**; do not call the sparse greedy
canvas count a delivery requirement or assume that a second tile suffices.
Neither option has been executed. No density reduction or main-wall phase waiver
is proposed. The recommendation is an experiment requiring Artem's word, not a
production fallback selected by the agent.

## Picture and remaining metrics

Full diagnostic sheet:
`G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/fit-v005/fit-diagnostic-sheet.png`.
It shows real source geometry: **green = best candidate placements**, **red =
rejected placements**, **grey = protected finishes**. These colours are temporary
render-only classifications, not a finish change or a brick acceptance image.
A small source-geometry thumbnail is attached to the card. Three attempted
close-up framings were uninformative and are excluded, not called acceptance.

Research section 5 on a **new exported/reimported result** remains unmeasured:
course/bond completeness, D/ERM/N joint centres and widths, directional density
spread/anisotropy, accepted unique/padded usage, output UV islands/reuse and
unique-image padding/orientation. There is no new export, no Artem visual verdict
and no replication. The report lists these gates explicitly rather than filling
them with historical or source-chart numbers.

## Verification and handoff

- RED fold API: **17b45d43**, missing module; GREEN **15 passed**.
- RED mask API: **91250f09**, missing function; GREEN **21 passed**.
- Hostile new regression: outside-face samples were accepted and conflicting-owner
  IDs absent: **2 failed / 21 passed**. Repair: vectorized polygon coverage check
  and explicit source owner; **23 passed**. Generated preservation probe adds one
  test: **100/100** translated faces, seed 1326, no mutation or silent drops.
- Final affected command:
  `uv run pytest -q tests/test_course_grid_fit.py tests/test_course_grid_general_fans.py tests/test_course_grid_chart.py tests/test_course_grid_audit.py tests/test_decisions.py tests/max_tools/test_agr_tools_vpm_layout.py -p no:cacheprovider --basetemp=C:/x/t_d517d7c6-affected-v005`
  -> **165 passed / 1 deselected / 0 failed**.
- Drive evidence has **24/24** verified SHA-256 entries: raw fresh readback, chart,
  masks, three fit orders, owner witnesses, dry alternative, code snapshots, sheet,
  excluded renders and report. `SHA256SUMS.txt` is the external seal.
- Full suite, regression eval receipts, completed production adapter/export and
  one PR remain due after the model-choice gate; no first review has been requested.
- Do not run immutable v005 generation scripts into the same paths. Use a new
  version and preserve the original evidence; output writers use exclusive creation.
- Opening preference unchanged: separate versioned Max 2026 quads copy only,
  absolute path, open only after Artem says **«открой»**; never switch his scene.
