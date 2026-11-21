# KPP1 R1 — cold-entry contract

Cells: `oks-vpm`, then derived `oks-npm`. This is an index of existing answers,
not a new Gate 1 approval or permission to rebuild. Delivery is **not passed**.
Read [STATE.md](STATE.md) and [job.yaml](job.yaml) for the current run and open gates.
Historical build/spec results below the STATE header are not the current delivery.

## Sources and accepted answers

- [sources.json](sources.json): hashed customer АС.03 R1 DWGs in the asset store
  and ИД album; `repo_inputs` records [object.json](object.json), the cached Revit
  levels/frame authority. The original RVT hash is unavailable; do not claim a fresh read.
- [D238](../../docs/decisions.md): L0 0.000–3.900 uses L03 exterior hatch with
  0.70 m entrance-frame bumps; L1 3.900–7.909 uses the Revit plain rectangle
  27.66 x 11.66 m, not a repeated L03 footprint. Frame tops/opening dimensions
  come from L01; cut openings, do not leave a closed wall behind frames.
  VPM first, NPM derived. Per-part budgets are allocations, not extra FBX ceilings;
  follow the current BODY budget rules and PartsList contract.
- [D249](../../docs/decisions.md) was provisional; [D254](../../docs/decisions.md)
  supersedes it for R1: parapet thickness 0.35 m, slab 7.700–7.909 and levels
  3.900/7.909 are FINAL for R1. Architect feedback would create R2, not block R1.
- [D256](../../docs/decisions.md): only the enumerated 98 VPM / 52 NPM source-bound
  clearance pairs in [rerun-1244](rerun-1244/RUN-LOG.md) are accepted. No general
  xView waiver; do not transfer this exception to changed/placed pair inventories.
- [D262](../../docs/decisions.md): [site-1255](site-1255/REPORT.md) uses the best
  rigid fit without the 180-degree alternative to customer NPM
  `0607_77_05_0009005_117_02`: approximate, ±0.1 m; entrance orientation not
  independently confirmed. This label is not a maximum-error guarantee.
  Revit project zero is 171.050 m. Territorial code `0000`, FNO and missing
  object-specific areas remain placeholders, not confirmed attributes.
- [D279](../../docs/decisions.md): keep project zero, ground mark and unknown
  height system separate; [height-datum.json](site-1255/height-datum.json).

## Route, gates and protected scope

Do not change accepted geometry, topology, UV, material IDs, source bytes, source-bound
exceptions or placement while repairing job documentation. Ground (another author),
GroundEl and Flora are separate deliverables; do not fabricate missing Ground for NPM.

Standard BODY/windows/roof route is AGR Tools in Max. The recorded offline build is
`path: deviation` [D250]; Blender fallback [D255] does not complete Max-only AGR Tools.
All eight gates in [TASK_TO_MODEL](../../docs/procedure/TASK_TO_MODEL.md) still apply.
A new PartsList needs its own hash-bound Gate 1; this summary does not approve it.
Visual, manual checks, SINTEZ and final AGR Tools acceptance remain open; see the
current validator receipts in site-1255. Benchmark/window experiments are not delivery approval.

[questions.md](questions.md) is historical contour-question accounting (`gone` rows),
not a substitute for these answers. For L03 commands and frame mapping use
[REPRODUCE.md](../../docs/methods/building-body/kpp1-drawing/REPRODUCE.md).
