# Ground v015 — mesher checkpoint, not a delivery

Issue #371. User decision on the card, 2026-10-20: option (b), a real quad mesher;
re-measure junction gaps and replace D150 for v015 with a coordinate-pinned list.
That decision remains in force. No request to relax it is made here.

## Status

**Blocked technical checkpoint; no v015 model accepted or exported.** The new
`src/dt_ai/geometry/ground_quads.py` primitive is NOT integrated into
`build_ground.py`. No old gate, exception, material, asset or source was changed.
No PR/review is requested for this incomplete acceptance. The non-DCC full suite
is deliberately deferred to the eventual first-review head, per coordination rule 49.

Branch base refreshed from origin/main `6e9f3fa`. Rule 29 check: main still has the
v014 triangle builder, not a v015 artifact meeting this issue.

## Implemented primitive

- Convex, coplanar, same-slot/level triangle patches become quads only with shared
  UV continuity and affine-compatible corner UVs. Tolerances are 10 micrometres
  for serialized geometric planarity and 2e-6 UV units for UV affinity.
- Remaining constrained triangles receive three Steiner quads; shared edges get
  one shared midpoint. Parity closure creates two/four-quad transition patches
  rather than simply accepting the original unpaired triangles.
- Per-polygon source triangle inventory, texture slot and layer are retained.
- Empty, nonfinite, degenerate, duplicate, missing-slot, bad-UV and nonmanifold-edge
  inputs fail closed. The primitive has no path/IO surface.
- This is not a contour-first production mesher, budget proof, xView cleaner or
  exported-file validator. A conforming input topology is required; arbitrary
  pre-existing geometric T-junctions and bow-tie vertices are not repaired here.

## Tests actually executed

- Tests-first commit `28a5bb4`: 1 RED failure (`ModuleNotFoundError` for the missing
  mesher). Subsequent vertical slices each observed RED before implementation:
  grid preservation, local transition, serialization noise, eight invalid-input
  cases and a nonmanifold-edge case.
- Final focused command:

  ```text
  env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q tests/test_ground_quads.py tests/ops/test_inv_quads.py tests/test_ground_cake.py tests/test_ground_cleanup.py tests/test_ground_details.py tests/test_ground_gap_exceptions.py tests/test_ground_review_r1.py tests/test_ground_review_r2.py -p no:cacheprovider --basetemp=C:/x/t_eb1c51ca/pytest-checkpoint-green2
  ```

  **218 passed**, exit 0 (11.08 s). Includes **43 new tests**, of which 30 are
  generated convex-contour seeds (0..29): independent Shapely union/summed-area
  oracle, source inventory, UV identity, input immutability and VPM quad invariant.
- SELF-FIX: an earlier focused run had 26 fixture setup errors because the parent
  `C:/x/t_eb1c51ca` did not exist. Created that parent and reran with the prescribed
  MSYS environment removal. This was not a geometry regression or a RED receipt.

## Real-input experiments — rejected, not acceptance

Inputs: typed SPOZU v4 JSON
`C:/x/t_d94665f2/paving_ground_inputs_v4.json`; reference triangle rebuild at
`C:/x/ev_t_eb1c51ca/v014_rebuild/ground_master_vpm.json`.
Original user DWGs were not opened or modified. Probe scripts and raw logs are in
this task's evidence attachment and in the ignored `tmp/` directory.

| Attempt | Measured result | Rejection |
|---|---|---|
| Conforming Steiner/transition primitive on v014, with serialized-noise tolerance | 121,233 quads total; 87,917 surface quads; 242,466 triangle-equivalent total | Surface >50,000 polygons; master >150,000 triangles. Per-slot quad invariant passes, but this does NOT waive either budget. |
| Independent Gmsh 4.15.2 all-quad recombination on the shared contour/TIN partition | 8,351 surfaces, 11,673 points, 20,007 edges; 56,293 quads + 1,094 triangles before layer repetition; 88,104 layered surface faces | Surface >50,000; not actually all-quad. No DCC/readback/triangle-reason acceptance measured. |
| Diagnostic layer-local partitions, existing gap raiser, then the primitive | 19,114 surface seed triangles; 67,117 quads total, 51,160 surface quads; 134,234 triangle-equivalent total | Surface still >50,000; 191 face-centre gaps below 5 mm (minimum -5.8623 mm); 7 face-centres and 26 corner sample records above 20 mm. Cannot replace D150 or publish this geometry. |

Gmsh was loaded transiently with `uv run --with gmsh`; project dependencies and
machine-wide configuration were not changed. The first Gmsh attempt stopped at
`1D mesh cannot be divided by 2`; setting each shared line to three nodes repaired
that precondition. The resulting measured mesh above still failed acceptance.
Additional parity/near-planar diagnostics in `tmp/quad-*-probe.py` were also
rejected; none was installed in production or used to rewrite a gate.

## DCC / external state

`max_exec.py --ping` reached live 3ds Max 2024 with safeMode=true. No document,
unit setting or scene was changed; no xView measurement is claimed for v015.
Blender/Max export/readback and DCC tests have NOT been run for a new model.
PR #373 / issue #348 was still open when context was read; its unmerged code was
not borrowed. Review-scene queue publication is still outstanding.

## Continuation

The two independent meshing routes exceeded the unchanged budget; stopped under
the card's two-failure rule rather than retrying indefinitely. No further model
policy decision is inferred, and option (b) is not reopened.

1. Replace/extend the contour partition strategy, not merely v014's triangle
   pairing. A layer-local route reduces seed count but requires a shared relief
   representation or new point-and-centre gap correction before it is viable.
2. Prove surface <=50,000 polygons and total <=150,000 triangle-equivalent;
   quad invariant must pass without inventing triangle allowances.
3. Resolve near-vertex/face xView offenders at construction time, including
   bow-ties; remeshing adds short edges, so rerun OV at 2 mm after quad generation.
4. Re-measure steep/flatter junctions by world coordinates and measured gaps;
   reserve a new decision ID against main AND open PRs before replacing D150.
   No ID has been reserved by this checkpoint.
5. Then integrate fixed material IDs, polygon-preserving FBX and Editable Poly
   Max output, UCX, Max/Blender readback, silhouette/deviation evidence and review
   publication. Run DCC tests and the one slotted full suite only on that final
   integrated head, then open the single authorized PR and request dt-reviewer.

The earlier card comments retain v014's xView offender classification; this
checkpoint has not fixed or re-certified those offenders.
