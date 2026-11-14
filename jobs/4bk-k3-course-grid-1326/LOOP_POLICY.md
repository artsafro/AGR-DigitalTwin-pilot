# Main-wall ring closure checkpoint — #1326

Status: **ANSWERED — Artem approved both recommended terminations on 2026-11-14**.
Exact answer and source-edge scope: `main-wall-seam-approval.json`. Keep horizontal courses
continuous; no new geometry cuts. The question below is historical, not pending.
`pilot_passed=false`. This checkpoint is not a tile-capacity failure, a new unwrap,
or a textured acceptance result.

## Already settled — do not ask these again

- Only the 771 existing ID1 faces: 705 walls + 66 stair; 1,244 protected faces unchanged.
- Artem's 2026-11-13 **yes** authorizes pattern breaks on existing thin end / bottom
  edges of the stair wall. Exact answer: `seam-approval.json`. The earlier question in
  `CHART_POLICY.md` is answered. No authorized break has been applied yet.
- Open only a separate versioned Max 2026 copy after **«открой»**; daytime Max untouched.
- [D293]: 38 courses / 3.15 m, Bricks1 unchanged, one-tile target, fixed physical scale,
  10 mm owner-inside joint with centre 5 mm inward, no density reduction or geometry cuts.

## One remaining question, with recommendation

**May horizontal bond/pattern phase terminate inside one existing vertical panel joint
on each of the two closed main-wall rings, keeping the vertical course height/phase
continuous, with <=0.1 px course/bond matching on the other main-wall joins?**

Recommended: **yes**, at the two existing corners marked red in the diagnostic:

| Object | Adjacent source faces | Existing source edge vertices | Edge XYZ endpoints, metres |
|---|---|---|---|
| K3_StylobateWalls.001 | 0 / 54 | 254 / 1364 | See `ring-audit-v003.json`, `candidate_main_wall_terminations` |
| K3_StylobateWalls.001 | 1344 / 1398 | 2 / 1419 | See the same source-bound endpoint table |

All indices are **0-based source mesh indices**, not material IDs. This asks for
**two declared pattern-phase terminations**, not geometry changes, extra tiles or
material reassignment. The stair-only yes does not silently authorize main-wall bond
exceptions. If these corners are unsuitable, Artem should name the desired existing
joint on each ring. A different brick-scale/appearance-equivalence policy is a user
choice, not an automatic repair.

## Fresh measurement and its exact limits

A new Blender **5.1.2 background** process loaded the hash-identical source copy,
asserted metric scale 1.0, and exported XYZ / source topology / UV / material IDs.
It saved **no scene**. Fresh readback: **2,015 faces, 771 ID1**, all fields exactly
identical to the earlier intake readback; the ten original scene/map hashes and
copied blend hash still match. The diagnostic is a plan projection of actual source
edges, not reconstructed or synthetic building data.

`audit_vertical_cycles` in `tools/materials/course_grid_audit.py` now complements the
trihedral audit, reusing its source validation and `uvlayout_core.tri_normal`.
It solves additive U offsets along a spanning forest of complete shared vertical
source edges. Each fundamental cycle measures the circulation of the fixed-scale,
outward-horizontal U chart. An all-edge repeating chart requires that circulation
to be an integer full appearance repeat. Vertex-only contacts, partial edges and
nonvertical faces are explicitly **not** certified.

For the #1314 chart, `P = 48 * 3.15 / 38 = 3.978947368421052 m` is the full Bricks1
repeat; `512 px/m` is the compact sampling target, not a different brick size.

| Ring | Faces | Absolute circulation, m | Nearest full repeats | Wrapped closure residual at 512 px/m |
|---|---:|---:|---:|---:|
| Main walls, first | 65 | 86.234795 | 22 | 666.648052 px |
| Main walls, second | 65 | 89.641967 | 23 | 959.396989 px |
| Stair | 22 | 31.929994 | 8 | 50.388560 px |

The stair cycle is reported for coverage; it is **not another request** to undo its
approved end/bottom exceptions. Those exceptions must be enumerated when applied.
The two main rings do not use the stair, so stair-only exceptions cannot open them.

These are **conditional fixed-chart closure residuals**, not residuals measured on
an exported pilot, and not proof that every possible texture strategy is impossible.
They must not be quoted as a certified 1-UDIM overflow. In particular, reducing the
full bitmap repeat to an assumed single-brick repeat is not demonstrated appearance
equivalence across D/ERM/N. Unique baking, different U scale, a different repeat
lattice or approved terminations are different strategies; this checkpoint selects
none silently. The audit never returns `passed=true`, even for an exactly closing or
open loop. It does not replace joint-mask classification, packing or output QA.

## Durable evidence

`G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/ring-policy-v003/`

- `main-wall-rings-labelled.png`: both actual rings, proposed terminations in red;
  visually inspected for legibility. **Not** viewport/brick acceptance evidence.
- `1326_faces_v003.json` + readback script: full fresh source readback.
- `vertical-cycles.json`: every measured cycle, ordered faces, existing source-edge
  indices and midpoint XYZ; 430 complete shared vertical edges, 684 vertical faces.
- `course_grid_audit.py`: exact measurement code snapshot.
- `SHA256SUMS.txt`: immutable versioned evidence hashes; all original inputs unchanged.
- Tracked small summary and candidate edge endpoints: `ring-audit-v003.json`.

Reproduce the public read-only CLI (choose a new output path):

```text
uv run python -m tools.materials.course_grid_audit tmp/1326_faces_v003.json tmp/ring-audit-new.json --material-id 1 --repeat-m 3.978947368421052 --texel-px-m 512
```

Exit **1** means incomplete/needs policy, not success. Malformed input or existing /
aliased output exits **2** without overwriting/deleting an input. No predictable
`.partial` file is created. Old trihedral flags in the combined diagnostic are raw
geometry findings; the tool does not read or override Artem's scoped permission.

## Tests and handoff

- Before (RED): **05fc8fe4**, missing `audit_vertical_cycles` import, one collection
  error in `tests/test_course_grid_audit.py`.
- After (GREEN): **43 passed** in that file. New regression: a closed synthetic
  four-wall ring has no trihedral fan but cannot close at the supplied 3 m repeat.
- Affected suite: `uv run pytest -q tests/test_course_grid_audit.py tests/test_decisions.py tests/max_tools/test_agr_tools_vpm_layout.py -p no:cacheprovider --basetemp=C:/x/t_d517d7c6-affected-rings`
  -> **101 passed, 1 deselected, 0 failed**.
- Generated cycle invariance probe: **20/20** rigid XY rotations/translations and
  reversed row orders preserve the known residual. Existing corner probe: **20/20**.
- Open vs exact-repeat loops remain non-passing/incomplete; inclusive phase boundary,
  NaN/inf/empty/partial/duplicate input, nonmanifold edges, independent objects and
  fresh-process non-passing CLI have regression coverage. Existing input/output alias
  and hardlink safety regressions still pass.
- No full suite/PR yet: incomplete model-policy gate, not review-ready. The one full
  suite remains due on the finished implementation before its first review request.

Next after the answer: freeze all explicit allowed existing-edge phase breaks ->
common chart with preserved horizontal courses -> joint-mask/appearance classes ->
fixed-density one-tile fit -> new versioned export and fresh readback -> section 5
metrics + stage close-ups -> Artem's visual verdict -> full suite and one PR.
No sources, UVs, maps, geometry or daytime Max have been changed. No replication.
