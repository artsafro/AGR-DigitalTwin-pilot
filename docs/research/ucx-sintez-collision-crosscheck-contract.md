# UCX parity cross-check contract: what a real SINTEZ collision comparison must measure

Pinned pilot SHA: `766d3f6442ca29eaecabb10b66c973038a09c4d8` (== `origin/main` at research time).
Vendor source (read-only, installed): `C:/x/sintez/v1.6.1`, `blender_manifest.toml` `version = "1.6.1"`,
`id = "sintez_agr_checker"`. File hashes recorded in "Findings" below.

## Summary

SINTEZ 1.6.1 measures exactly three of our four req-2.13.4 finding classes. `compute_ucx_collision_errors`
(`check_utils.py:1716`) reports `intersect` and `nested` (both req 2.13.4) and `gap` = "зазор меньше
допуска" (`gap < 0.2 mm`, req 2.13.4) — the vendor-side twin of our `too_close`. It has **no** upper-band
check: the D098 2 mm–1 cm band is a project rule the vendor does not implement, so our `gap_out_of_band`
finding has no vendor equivalent and must be compared as **vendor `not_measured`, never agreement**.
Our fourth class `too_close` maps to vendor `gap`; `intersect` and `nested` map 1:1. Closure / convexity /
non-manifold are a *prerequisite* reported under req **2.13.1**, not a 2.13.4 finding, and the vendor's
pairwise pass runs in a **local (origin-relative) float32 frame** — a live comparison is only well-defined
on a corpus near the origin whose meshes carry the `UCX_`-style names the vendor selects. The cross-check
is against `ucx_audit.pair_findings` (audit findings), not `scene.py`'s advisory gap report.

## Findings

### 1. The four classes vs what SINTEZ actually reports (source-justified)

| twinqa class (`ucx_audit.pair_findings`) | req | Vendor twin | Vendor req | Verdict to compare |
|---|---|---|---|---|
| `too_close` (gap < `TOUCH_M` 0.2 mm) | 2.13.4 | `gap` "Зазор меньше допуска" | 2.13.4 | agreement measurable |
| `gap_out_of_band` (outside D098 2 mm–1 cm) | 2.13.4 | **none** — SINTEZ has no upper band | — | **vendor `not_measured`, never agreement** |
| `intersect` (penetration > 0.01 mm) | 2.13.4 | `intersect` "Пересечение коллизий" | 2.13.4 | agreement measurable |
| `nested` (one hull inside another) | 2.13.4 | `nested` "Коллизия … целиком внутри …" | 2.13.4 | agreement measurable |

Prerequisites (reported separately, **never** folded into a 2.13.4 agreement):

| Vendor finding | Vendor req | twinqa | twinqa req |
|---|---|---|---|
| `unclosed` (Euler `V-E+F != 2`) | 2.13.1 | `not_run` `open` | 2.13.4 |
| `nonmanifold` | 2.13.1 | `not_run` `open` | 2.13.4 |
| `nonconvex` (angle > 0.1°) | 2.13.1 | `not_run` `non-convex` | 2.13.4 |

Sources: `check_utils.py:1763-1799` (per-object closure/manifold/convexity), `:1809-1885` (pairwise
intersect/nested/gap), `hp_checks.py:1062-1097` (`_check_collision` wires check1=2.13.1, check3=2.10.4.2,
check4=intersections, check5=gaps); `ucx_audit.py:397-461`.

### 2. Object selection, coordinates, units, topology prerequisites

- **Object selection**: vendor `ucx_objs = [o for o in fbx.meshes if o.type == "MESH" and "UCX" in o.name]`
  (`hp_checks.py:1084`) — substring `"UCX" in name`, not the `UCX_SM_{addr}_{Main|Ground}_{NNN}` mask.
  Pairs are checked **only within one FBX group** (one `_hp_fbx_files` entry); UCX from different FBX are
  never compared. List is sorted by `obj.name` (`check_utils.py:1747`); pair text addresses use the last
  three name chars, the `NNN` index (`obj.name[-3:]`, `check_utils.py:1766,1817`).
- **Coordinates**: pairwise geometry is computed **relative to a group origin** =
  `ucx_objs[0].matrix_world.translation` (`check_utils.py:1807`), stored in **float32** (`array('f')`,
  bmesh/BVHTree are float32). The comment at `:1801-1806` and `get_collision_data:1659-1669` states this is
  a correctness requirement: at geojson/MSK offsets the float32 step (~1 mm at 10 km) is ~5× coarser than
  the 0.2 mm gap tolerance, so world-frame runs produce different verdicts. A live comparison must present
  the corpus in local coordinates or subtract the same origin.
- **Units**: metres throughout; `ucx_gap_tolerance` is a scene property in **mm** divided by 1000
  (`hp_checks.py:1065`, `properties.py:375`, default `0.2`, min 0.1 max 2.0). `ucx_convex_angle` in
  **degrees** (`properties.py:367`, default `0.1`, min 0.01 max 2.0).
- **Topology prerequisites**: `unclosed` and `nonmanifold` objects are excluded from pairwise (`continue`,
  `check_utils.py:1781,1789`). `nonconvex` appends a finding but does **not** `continue` (`:1791-1798`) — a
  non-convex hull still participates in pairwise intersect/nested/gap, because the penetration test does not
  need convexity (`real_face_overlaps` docstring, `blender_utils.py:1047-1050`). This is a real semantic
  gap: twinqa `_unmeasurable` returns `"non-convex"` and *excludes* the hull, so a non-convex pair is
  `not_run` for us but measurable for the vendor. The corpus's one unsupported entry is therefore an **open**
  hull (both sides exclude it), not a non-convex one.

### 3. Recommendation / fail encoding and the raw checklist shape

- Every collision geometry finding is an **error** (hard fail): `check_closure.add_error(...)`,
  `check_intersect.add_error(...)` for both `intersections` and `nested`, `check_gaps.add_error(...)`
  (`check_utils.py:1912-1944`). There is **no recommendation** in the collision path — unlike UV/transforms,
  `compute_ucx_collision_errors` never writes to `recommendations`. Numbering (`check_sequence`, check3,
  req 2.10.4.2) is a separate non-geometry item.
- `run_agr_checker.py` (`jobs/KPP1/scripts/run_agr_checker.py:47-55`) dumps per-item
  `{category, req_num, name, state, auto, errors_count, errors, recommendations_count, recommendations}`,
  where `errors` is the **collapsed** Russian text ("Пересечение коллизий. N шт., номера коллизий - (004 и
  015)"). The **structured** per-finding list (`{"kind","req_num","objects","text"}`, returned by
  `compute_ucx_collision_errors:1733-1740`) is **not captured** by the current harness. The only machine
  addressable per-pair evidence is `ucx_fingerprint.txt` (`log_ucx_fingerprint:1332-1388`, path
  `os_utils.py:45`, `AGRChecker_data/ucx_fingerprint.txt`), whose row carries `объектов`, `пар_проверено`,
  `geo`/`world` md5(12), `origin`, the two tolerances, `незамкнутых/nonmanifold/невыпуклых`, and the full
  `пересечения(N): (004 и 015)` / `зазоры(N): …` pair lists.

### 4. Boundary-semantics mismatches a fair comparison must not paper over

1. **Gap measurement**: vendor gap is **vertex-to-surface proximity**
   (`bvh.find_nearest(v, tolerance)` per vertex, `check_utils.py:1868-1878`); twinqa `surface_distance`
   (`ucx_audit.py:265-279`) is the exact minimum (vertex-triangle both ways + edge-edge). They agree for the
   axis-aligned face-to-face boxes of this corpus, and that is a deliberate restriction — edge-edge/corner
   near-contact is out of corpus scope.
2. **Intersect epsilon**: vendor `polygons_intersect`/`real_face_overlaps` (`blender_utils.py:1017-1055`) is
   genuine triangle penetration (coplanar contact excluded, any real penetration counts); twinqa uses
   `sep < -OVERLAP_EPS_M` = penetration > 1e-5 m (0.01 mm). Penetrations in `(0, 0.01 mm]` are `intersect`
   for the vendor but `touch`/`too_close` for twinqa. The corpus's partial-overlap entry uses a 0.5 m
   overlap to stay far from this edge; the exact too-close boundary tests are separately queued (#480/#462)
   and are intentionally untouched here.
3. **Nested tolerance**: vendor `_is_inside_convex(tolerance=0.0001)` (0.1 mm, `check_utils.py:1708` /
   `blender_utils.py:979`); twinqa `inside_convex(tol=0.0)` (`ucx_audit.py:308`). The corpus's nested entry
   is strictly interior (4…5 vs 0…10), so no boundary issue.
4. **0.2 mm exactly**: twinqa's `1.0 + 0.0002` float64 construction measures "1 ulp under `TOUCH_M`" and is
   classified `too_close` (see `tests/qa/test_ucx_parity.py:100-103`); `0.000201` is the first constructed
   gap that measures ≥ 0.2 mm and lands `below_band`. The vendor's float32 vertex at the same nominal 0.2 mm
   reads ~0.00019999 < 0.0002 and is a `gap` finding. Both lanes therefore agree at the nominal 0.2 mm edge,
   but the agreement rests on float representation, not on a shared inclusive/exclusive convention — the
   corpus pins this entry as an exactly-at-threshold probe, not a guaranteed bit-for-bit match.

### 5. Vendor source hashes (read-only inspection, recorded for future pinning)

```
check_utils.py   00ff3f967595cd7831b428abbdc46202f79af1e71922a59ed8221d762fc9e5c2
hp_checks.py     bc9ddcf709e718ccf6e7ae5878235aabcc4abdafd4434e4744f84e79e268457d
blender_utils.py aaa7aac6525cc6ad8b543a2b53d8f4a36b4366c030d77c0099d899bbfa7808f6
properties.py    88ce0427b9083e9aed1bdae6747245aed2b6316ee09f9d1ff19fc2b5a8d385e2
```

Key `file:line`: `compute_ucx_collision_errors` check_utils.py:1716 · `get_collision_data` :1652 ·
`_is_inside_convex` :1708 · `log_ucx_fingerprint` :1332 · `check_mesh_convex` :933 · `_check_collision`
hp_checks.py:1062 · `aabb_overlap` blender_utils.py:967 · `is_inside_convex` :979 · `polygons_intersect`
:1017 · `real_face_overlaps` :1035 · `ucx_convex_angle` properties.py:367 · `ucx_gap_tolerance` :375.

## How it applies to this repository

- `src/twinqa/geometry/ucx_audit.py` — the four findings to cross-check live in `pair_findings` /
  `collision_findings` (`REQ_COLLISION = "2.13.4"`, `TOUCH_M = 0.0002`, `GAP_BAND_M = (0.002, 0.01)`,
  `OVERLAP_EPS_M = 1e-5`, `NEIGHBOUR_M = 0.10`). This is the **audit** lane of the comparison.
- `src/twinqa/scene.py::_ucx_pair_findings` (`:216-279`) — the **scene advisory** lane ("UCX intersections"
  fail, "UCX piece gap (advisory)" review, never fail). Not vendor-comparable for the gap: the advisory is
  the D098 band report and must be kept out of the too-close/intersect/nested cross-check.
- `tools/sintez_parity.py` — the parity harness (#432) has 15 non-collision groups (`CASES`, `:16-32`); the
  collision cross-check is the #451 / `test_ucx_parity.py:5-6` TODO this contract scopes.
- `jobs/KPP1/scripts/run_agr_checker.py` — the vendor seam; its `dump()` (`:47-55`) currently drops the
  structured `findings` list, so a live comparison needs a thin wrapper that calls
  `compute_ucx_collision_errors` and captures its return value (or parses `ucx_fingerprint.txt`).
- `docs/agr/sintez_checks_1.6.1.json` — `hp_collision` (id, req_nums 2.10.4.2 / 2.13.1 / 2.13.4,
  `our_equiv` `ucx_audit.py`, `status: conflict`) and `thresholds.ucx_collision` (`closure_tolerance_m:
  0.0002`, `convex_angle_deg: 0.1`) are the machine-readable version of Findings §1–2.
- `docs/research/sintez-agr-checker-dissection.md` §6.3 — the already-listed conflict "UCX gap semantics"
  (SINTEZ < 0.2 mm only vs our D098 band) is the reason `gap_out_of_band` is vendor `not_measured`.

## Proposed frozen corpus

All entries are axis-aligned closed convex boxes as `(verts, tris)` in **local metres near the origin**
(one FBX, meshes named `UCX_SM_Synthetic_{Main|Ground}_{NNN}` with a three-digit index so the vendor's
`name[-3:]` pair addressing is stable). `twinqa` column is the actual `pair_findings(a, b)` outcome on the
current code (verified against `tests/qa/test_ucx_parity.py` acceptance table and constants). "Vendor" is
justified by source inspection (§1–3), else `NOT MEASURED`.

| # | Entry (analytic geometry) | twinqa `pair_findings` | Vendor `compute_ucx_collision_errors` (source-justified) | Agreement |
|---|---|---|---|---|
| 1 | Touching: `[0,0,0]..[1,1,1]` vs `[1,0,0]..[2,1,1]`, gap 0 | `too_close` + `gap_out_of_band` | `gap` "Зазор меньше допуска" (coplanar contact ≠ intersect) | `too_close`↔`gap` yes; `gap_out_of_band` NOT MEASURED |
| 2 | 0.1 mm gap: `[0,0,0]..[1,1,1]` vs `[1.0001,0,0]..[2.0001,1,1]` | `too_close` + `gap_out_of_band` | `gap` (0.1 mm < 0.2 mm) | `too_close`↔`gap` yes |
| 3 | 0.2 mm gap (exact edge): `[1.0002,0,0]..[2.0002,1,1]` | `too_close` + `gap_out_of_band` (1 ulp under `TOUCH_M`) | `gap` (float32 ≈0.19999 mm < 0.2 mm) | `too_close`↔`gap` yes (float-representation dependent) |
| 4 | 1 mm gap: `[1.001,0,0]..[2.001,1,1]` | `gap_out_of_band` (below band) | **NOT MEASURED** (no upper band; 1 mm > 0.2 mm → clean) | disagreement preserved |
| 5 | 5 mm gap: `[1.005,0,0]..[2.005,1,1]` | `[]` (in band) | **no finding** (clean) | both clean (absence, not band parity) |
| 6 | 20 mm gap: `[1.02,0,0]..[2.02,1,1]` | `gap_out_of_band` (wide, neighbour) | **NOT MEASURED** (AABB broad-phase skips, tolerance 0.2 mm) | disagreement preserved |
| 7 | Partial overlap: `[0,0,0]..[1,1,1]` vs `[0.5,0,0]..[1.5,1,1]` (0.5 m overlap) | `intersect` | `intersect` "Пересечение коллизий" | yes |
| 8 | Nested: `[0,0,0]..[10,10,10]` vs `[4,4,4]..[5,5,5]` | `nested` | `nested` "Коллизия … целиком внутри …" | yes |
| 9 | Unsupported open hull (box with 2 tris removed) + `[0,0,0]..[1,1,1]` vs `[1.0001,0,0]..[2.0001,1,1]` | `not_run` `open` (drop) + `too_close`/`gap_out_of_band` for the valid pair | `unclosed` (2.13.1, excluded from pairwise) + `gap` for the valid pair | prerequisite mapped 2.13.1↔`not_run open`, **not** a 2.13.4 agreement |

`gap_out_of_band` (entries 1, 2, 3, 4, 6) is the D098 2 mm–1 cm band (project rule) and has **no vendor
equivalent** — the comparison must record vendor `not_measured` for it and never claim agreement. Entries
4 and 6 are the pure "vendor not_measured" probes; entry 5 is the in-band "both silent" probe.

### Raw readback / checklist fields a future live comparison must retain

Per fixture, in addition to what `tools/sintez_parity.py` already keeps (seed, readback, raw checklist,
commands/exit codes, ZIP SHA-256 before/after, logs):

- **Vendor lane** (structured, captured by a thin wrapper calling `compute_ucx_collision_errors` directly):
  `findings[]` → `{kind ∈ unclosed|nonmanifold|nonconvex|intersect|nested|gap, req_num, objects[], text}`;
  `ucx_fingerprint.txt` row → `объектов`, `пар_проверено`, `geo`/`world` md5, `origin`, `допуски`
  (зазор mm / выпуклость °), `незамкнутых/nonmanifold/невыпуклых`, `пересечения(N): pairs`, `зазоры(N):
  pairs`. Checklist rows for req 2.13.1 / 2.13.4 / 2.10.4.2 with `state`, `auto`, `errors_count`, `errors`,
  `recommendations_count`, `recommendations`.
- **twinqa lane**: per-pair `{type, req, gap_m, penetration_m, a, b}` and per-hull `not_run` drops
  `{type, req, reason, hull, index}`.
- **Provenance / frame**: Blender `5.1.2`, extension `1.6.1`, the four vendor file hashes (§5), the FBX
  readback mesh names and local verts/tris, and the group `origin` (first UCX world translation) so the
  coordinate frame is pinned and reproducible.

## Proposed next tasks

1. **Extend `tools/sintez_parity.py` with a `ucx_collision` group over this frozen 9-entry corpus.** Add a
   collision group (req 2.13.4) that builds the corpus as UCX meshes, exports/reads back in local
   coordinates, runs the Python lane against `ucx_audit.pair_findings` and the vendor lane through a thin
   `compute_ucx_collision_errors` wrapper, and compares the mapped classes. Concrete input → expected
   output: **Python-only run** (`--dcc` absent) → `vendor not_measured` for every entry, never agreement;
   **missing req_num/checklist or the open hull** → explicit `unmeasured`/`error`, never pass; **complete
   live run** → `too_close`↔`gap`, `intersect`↔`intersect`, `nested`↔`nested` agree, `gap_out_of_band` (and
   the 1 mm / 20 mm entries) reported `vendor not_measured` with the disagreement preserved. Value/effort
   **M**. `Advances #298`.
2. **Standalone SINTEZ seam probe (no harness edit, no pytest).** A small Blender-side script that constructs
   the corpus, calls `CheckUtils.compute_ucx_collision_errors` directly, and dumps the structured
   `findings[]` list plus the `ucx_fingerprint.txt` row, pinning vendor version/hash/`file:line`. Concrete
   input → expected output: each of the 9 entries yields the exact structured kind list (`gap`/`intersect`/
   `nested`/`unclosed`) with req 2.13.4 for pair findings and 2.13.1 for closure, proving the structured
   seam exists before the harness invests in it. Value/effort **S**. `Advances #298`.

## Open questions for the user

1. Should `too_close` (< 0.2 mm) be a hard failure in the project, or only the D098 band? (dissection §6.3,
   still unresolved) — this decides whether the `too_close`↔`gap` agreement is a fail↔fail or fail↔advisory
   comparison.
2. Corpus frame: is a local (origin-relative) corpus acceptable, or must a geojson/MSK-world-frame corpus be
   included (which requires replicating the vendor's `origin = first UCX world translation` subtraction to
   keep float32 parity)?
3. Structured seam: is a thin Blender wrapper that captures `compute_ucx_collision_errors`'s returned
   `findings[]` acceptable, or must the comparison stay limited to parsing `run_agr_checker.py`'s collapsed
   checklist `errors_text`?
4. Vendor gap is vertex-to-surface proximity, twinqa is exact min distance — should the cross-check scope to
   axis-aligned boxes (as here), or must edge-edge / corner near-contact configurations be added to the
   corpus, accepting that the two measurements can legitimately diverge there?
