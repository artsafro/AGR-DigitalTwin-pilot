# Ground v015 final authorized xView session — #371

**Parked, not delivered. No PR, .max/FBX, review-queue entry or acceptance receipt.**
The user's final one-session authorization requires parking #371 if xView remains
unclean; #298 must use v014. No additional session is requested or authorized here.

## Scope and production change

Merged `origin/main` at `c990e93` without conflicts before changes. Main does not
contain a v015 delivery. The selected path remains D157 option (a), not the rejected
Steiner/90k route: surface cap 50,000, whole NPM 180,000 triangle-equivalent,
10 mm relief, D150 and fixed texture IDs remain unchanged.

Production commit `a621607` changes only `_stairs_solid` in `ground_details.py`:
all vertical stair walls share the complete set of tread elevation cuts. Previously
the lower tread/riser terminated inside its taller neighbour's side-wall edge,
leaving T-junctions and eight Stairs/Stairs xView pairs on the recorded construction
candidate. Horizontal strips preserve the wall's original geometric extent and
stair heights; neither the footprint nor the bottom datum is moved.

Tests-first commit `c379d73`: **1 failed** on the missing shared-edge topology.
After the fix: **7 passed** (first tracer + detail tests). Generated controls cover
four ascending/descending/nonmonotonic/equal height sequences, each at 0/27 degrees
and local/world-size offsets: **16/16 passed**. Each checks closed edge incidence,
zero OV and zero OF after pairing. Detail + review-r2 selection: **25 passed**.
Final focused run: **174 passed / 0 failed in 10.27 s**:

```text
uv run pytest -q tests/test_ground_xview_construction.py tests/test_ground_pairing.py tests/test_ground_quads.py tests/test_ground_v015_budget_decision.py tests/test_ground_surface_requirement_sheet.py tests/test_ground_cake.py tests/test_ground_details.py tests/test_ground_cleanup.py tests/test_ground_review_r1.py tests/test_ground_review_r2.py tests/test_ground_gap_exceptions.py -p no:cacheprovider --basetemp=C:/x/t_eb1c51ca/final-session-focused
```

## Real-size diagnostics (both rejected)

`ground-v015-final-xview-evidence.json` embeds the complete programs, input hashes,
raw xView reports, all face-corner coordinates and the complete fan-displacement
list. Its source is the same immutable v014 rebuild used by the preceding session.
The diagnostic uses the original cake/skirt plus rebuilt details, not a newly
certified complete production build. Native Max is **not** the source of these
measurements.

1. Reuse the preceding diagnostic skirt clipping and rebuild curbs with **12 mm**
   XY stair clearance instead of 6 mm (margin for noding/welding), plus the new
   production stair fix. Result: **0 OV / 13 OF**, with **59 bow-tie vertices** still
   present. Stairs/Stairs is now zero; Curb/Stairs falls from four to one.
2. Diagnostic-only separation of each edge-connected fan by **3.5 mm** into an
   existing incident triangle, rejecting inverted incident triangles. All 59
   bow-ties disappear, but two new near-duplicate vertex pairs appear:
   **2 OV / 13 OF**. No inversion alone is insufficient to prove relief, coverage,
   gap, UV or silhouette preservation. This candidate is rejected, not integrated.

| Candidate | Quads | Triangles | Triangle share | Surface polygons | Triangle-equivalent | Ours OV / OF |
|---|---:|---:|---:|---:|---:|---:|
| Stair fix + 12 mm clearance + old skirt clipping | 19,242 | 7,996 | 29.356% | 20,152 | 46,480 | 0 / 13 |
| Diagnostic fan displacement on that candidate | 19,245 | 7,990 | 29.337% | 20,149 | 46,480 | 2 / 13 |

The budget columns exclude separately placed MAF/Flora and do not certify a complete
Ground delivery. The 12 mm clearance, old skirt clipping and fan displacement are
**not production changes**. `build_ground.py`, `add_skirt`, `clean_topology`, the D150
manifest and the v014 source assets were not changed in this session.

## Remaining exact witnesses

These are one-based polygon IDs in the **second diagnostic**. The coordinate
column is the centroid of face A for navigation, not the measured closest-point
location. Full corners of both faces are frozen in the evidence JSON.

| Face A / B | Slots | Gap mm / contact | Face-A centroid XYZ m |
|---|---|---:|---|
| 1769 / 24245 | Mulch / CurbGarden | 3.992 | -7520.993250, -15341.499750, 146.907995 |
| 2783 / 23770 | Mulch / CurbGarden | 3.996 | -7645.658250, -15334.303500, 149.718987 |
| 2785 / 23770 | Mulch / CurbGarden | 3.996 | -7646.444000, -15332.968000, 149.723242 |
| 11497 / 24629 | LawnReinforced / CurbGarden | 4.842 | -7574.121750, -15298.350000, 150.484260 |
| 11501 / 24629 | LawnReinforced / CurbGarden | 3.059 | -7575.699750, -15299.350500, 150.477951 |
| 11507 / 24629 | LawnReinforced / CurbGarden | 3.059 | -7574.916000, -15298.621500, 150.487120 |
| 20608 / 20611 | Skirt / Skirt | 2.731 | -7548.166500, -15354.724500, 146.218919 |
| 20748 / 20749 | Skirt / Skirt | contact | -7634.559000, -15378.661500, 145.271199 |
| 20749 / 20752 | Skirt / Skirt | contact | -7634.556000, -15379.060500, 145.263101 |
| 21775 / 21779 | Skirt / Skirt | 2.855 | -7691.118000, -15248.344500, 151.507283 |
| 21777 / 21778 | Skirt / Skirt | 0.000 | -7691.328000, -15247.693500, 151.487586 |
| 21777 / 21779 | Skirt / Skirt | contact | -7691.328000, -15247.693500, 151.487586 |
| 22099 / 26065 | Stairs / CurbGarden | 0.000 | -7542.122245, -15335.849852, 149.086635 |

Remaining classes: **6 Skirt/Skirt, 1 Curb/Stairs, 3 Curb/Mulch,
3 Curb/LawnReinforced**. Skirt defects originate in the near-coincident base-outline
curtains; curb/raised-cake defects retain the fixed bottom-datum versus locally
raised cake mismatch. Increasing only XY stair clearance does not address those
vertical support gaps, and still leaves one Curb/Stairs overlap. Those changes are
not represented as a successful construction fix.

New vertex pairs after diagnostic fan separation:

- v8908/v27420, **1.599359 mm**:
  `(-7539.999, -15344.079, 147.83734)` /
  `(-7540.0004619704805, -15344.078851140503, 147.83797121410774)`.
- v27424/v27425, **1.452322 mm**:
  `(-7578.5587747193495, -15322.731298946668, 150.08450336517188)` /
  `(-7578.55786986434, -15322.73243493217, 150.08450704187143)`.

## Reproduction and stop

Extract the three `programs[*].utf8` values from the evidence into the corresponding
ignored `tmp/` paths. On production commit `a621607` (or this documentation head):

```text
uv run python tmp/xview-final-session-probe.py
```

This intentionally reuses the prior **diagnostic** construction program. Outputs
are ignored scratch arrays/reports, never a delivery. The final-session command
completed **exit 0**; the child is stopped. Independent evidence assertions checked
actual counts, corner-derived vertex distances, triangle-equivalent arithmetic,
unchanged budget bounds, triangle share and zero remaining Stairs/Stairs pairs.
A missing numpy in the tool kernel was repaired by running the freeze script in
`uv run`; a report-shape mismatch (counts are integers, not pair arrays) was corrected
before freezing evidence. Neither issue reran the geometry experiment.

No native Max/Blender export/readback or DCC tests were run: the prerequisite ours
xView gate fails. No full suite was consumed for an explicitly rejected candidate;
the first-review full-suite receipt is absent, not green. Relief/gap/coverage after
fan displacement, D150 re-pin, final UV/material IDs, UCX/placement compatibility
and review publication remain unmeasured/incomplete. No PR or review is requested.

**Disposition: park #371; continue #298 on v014 under the user's recorded decision.
Do not auto-retry this card or start another mesher/xView repair session.**
