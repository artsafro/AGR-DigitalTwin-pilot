# Ground v015 — final authorised coarsening session (rejected)

Issue #371, card `t_eb1c51ca`. **Not a delivery, not acceptance, no PR.**

## Authority and immutable checkpoint

- Continued `8612bcc68a26450a73b35a98ee97db5203270d17` on the same branch.
  `git fetch origin` confirmed main remains `6e9f3fa`; it does not deliver v015.
- Card decision, Artem 2026-10-20 16:05: one additional contour-first/layer-aware
  coarsening session, **surface <=50,000 unchanged**. No cap increase, no third
  mesher attempt. D129 remains mandatory. D150 must be remeasured, not inherited.
- Baseline layer-local diagnostic from the earlier checkpoint: 51,160 surface
  quads, 191 centroid samples below 5 mm, minimum -5.8623 mm; not accepted.
- `uv sync`: resolved 23 packages, audited 22. No dependency/lockfile change.
- No production code, source, gate, material, exception or DCC scene changed in
  this session. Only this evidence report was added to the branch.

## Bounded experiment

Started from the same layer-local plate plan, with the same stair footprints
removed. Each plate is built separately using `build_flat(sampler=sampler,
cell=4/5/6, snap=.003, tol=.01)` and the existing conforming quad primitive.

**Important difference from the earlier 51,160-quads diagnostic:** this experiment
pairs/remeshes the *flat* seed before Z projection, rather than remeshing the
projected, raised triangles. This is a candidate construction change, not a
measurement that the earlier geometry can simply be coarsened without loss.
Planar seed pairing can erase a TIN break when the new quad uses another diagonal.
All new quad vertices are sampled on the TIN, but that does NOT prove whole-face
relief fidelity. The unchanged whole-face 10 mm test rejects this shortcut.

For measurement only, each quad is split deterministically on diagonal 0-2.
A prototype Z-only raiser measures lower-face-normal gaps at upper triangle
centres AND near corners (the existing 0.999 corner + 0.001 centre convention),
raising the lowest failing level first toward 5.5 mm. This removes the previous
missing-centre correction, but is **not** integrated or claimed to preserve all
other geometry requirements. Quads can become nonplanar after projection/lift;
other exporter diagonal choices have not been validated.

## Actual results, per coarsening step

All counts below concern surface plates only, before skirt/details/UCX.
The full previous checkpoint's detail inventory is not silently discarded.

| Cell m | Surface quads | Centre <5 mm | Corner <5 mm | Centre >20 mm | Corner >20 mm | Max extra lift mm | Exact relief loss mm | Triangles >10 mm relief | Same-level overlap m2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 43,741 | 0 | 0 | 41 | 167 | 83.191835 | 135.361096 | 108 | 0.071450381 |
| 5 | 38,908 | 0 | 0 | 38 | 141 | 83.191835 | 135.361096 | 134 | 0.076997536 |
| 6 | 30,016 | 0 | 0 | 128 | 484 | 105.506664 | 531.567495 | 214 | 0.068180403 |

These are diagnostic counts, NOT accepted D150 exceptions. The >20 mm figures
are sample records, not unique exception points. The gap helper uses its existing
10 micrometre comparison margin; actual minimum centre gaps are 5.491144,
5.493906 and 5.491634 mm, respectively, so none relies on that margin to clear
5 mm. Corner counts were also recomputed from the saved candidate arrays.

Relief loss here removes both nominal layer offset and the experimental
per-vertex lift before comparing each tessellated surface triangle with the
original TIN. Thus even this favourable separation of deliberate gap corrections
from interpolation error exceeds the unchanged 10 mm bound. An independent
local-coordinate plane/intersection oracle confirms the worst error; a merely
numerically unstable world-plane fit is not the explanation.

The world-intercept sampler differs from the local oracle on some very thin
triangles. The table uses the independent local oracle's counts (not the lower
sampler counts of 133 and 211 for 5 and 6 m). No shared checker was changed.

## Concrete independent failure witnesses

### 4 m and 5 m: same lost TileRed slope break

- Level 1; measurement triangles 72501 (4 m) and 64129 (5 m).
- Triangle, with nominal offset and corrective lift removed:
  `[-7598.814, -15380.46, 145.50000342990901]`,
  `[-7598.826, -15380.061, 145.51114261501758]`,
  `[-7599.429, -15380.061, 145.2184632315686]`.
- Intersection witness XY: `[-7599.0968015617755, -15380.276523864799]`.
- Candidate plane Z `145.370540002603`; original TIN Z `145.50590109844765`.
- Absolute error **135.361095844644 mm**, independently reproduced for both cells.

### 6 m: additional lost TileLight slope break

- Level 0; measurement triangle 21179.
- Triangle: `[-7600.782, -15379.26, 144.72500335457894]`,
  `[-7602.0, -15383.04, 145.455870859107]`,
  `[-7599.399, -15380.52, 145.49997850053376]`.
- Intersection witness XY: `[-7601.187677777778, -15380.519]`.
- Candidate plane Z `144.96843250489655`; original TIN Z `145.5`.
- Absolute error **531.567495103445 mm**.

## Commands, evidence and hashes

Raw evidence remains under this card's ignored `tmp/` directory. The compressed
source/log/JSON bundle is retained at `tmp/ground-v015-coarsening-evidence.zip`;
it does not contain a delivery or claim user acceptance. Candidate arrays remain locally
in `tmp/coarser-layer-{4.0,5.0,6.0}.npz` and can be regenerated from the scripts.

```text
uv run python tmp/coarser-layer-probe.py 4 5 6 > tmp/coarser-layer-probe-v2.log 2>&1
uv run python tmp/verify-coarsening.py > tmp/coarsening-verified.log 2>&1
```

Both completed with exit 0. This means experiments/measurements ran, **not** that
the candidates passed. Machine evidence assertions checked all three rows:
`surface_quads <= 50000`, zero lower-band corner/centre counts, and
`independent_relief.local_max_mm > 10`: **3/3 rejected, 0 accepted**.

| Evidence | SHA-256 |
|---|---|
| `C:/x/t_d94665f2/paving_ground_inputs_v4.json` | `3b6b433d718c0292f472293849f3363fd2ae90d4892e598efca52be44cd9d502` |
| `src/dt_ai/geometry/ground_quads.py` (unchanged) | `c5a451d050523f34ab08e92260869875ffd8c913c5f0357dc915bbaddc302d56` |
| `tmp/coarser-layer-probe.py` | `9c06e29b38fa01b152bcbdad5e714b5c2ef6913efddc91163e479cede86e6e5f` |
| `tmp/verify-coarsening.py` | `65c366a83d842bfe24e12f258e5c4b5ad98c1c2a5ff8e5b55ad7ebd2e4d1849b` |
| `tmp/coarsening-verified.json` | `60a313cbd91f2fa98d4e286497c9778ea93dc316321d8218eeeac73433bbe526` |

A first probe invocation failed on an indexing typo in the diagnostic's final
error measurement. Corrected `verts[faces,:,:2]` to `verts[faces][:,:,:2]` and
reran; no model-policy or tolerance change. The retained `-v2.log` is the complete
successful measurement run, not a fabricated continuation of the failed log.

## Verification limits and stop

- Prior checkpoint: 218 focused tests passed (43 quad tests); see the earlier
  checkpoint report for the actual command and RED history. Not rerun or claimed
  as new tests of this throwaway prototype. No production changes in this session.
- No full suite: reserved for the first review head; no review/PR is requested.
- No Max/Blender writes, DCC tests, material-ID/FBX/readback receipts, xView-clean
  claim, v014-to-v015 silhouette acceptance, UCX rebuild, review publication or
  coordinate-pinned exception decision. These acceptance items remain **open**.
- All experiment subprocesses exited. No source or accepted version overwritten.
- The bounded coarsening experiment failed relief fidelity at every step and
  retained same-level overlaps. This is not an accepted v015 despite satisfying
  the isolated polygon and lower-gap counts. Stop at the authorised session limit;
  do not run a third mesher, raise D097, accept the new >20 mm samples, or reopen
  option (a) without a new explicit user decision.
