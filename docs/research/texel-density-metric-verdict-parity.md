# Texel density: do area means, edge samples and directional bounds agree on verdicts?

Research card t_3821f703 (no GitHub issue). Read-only: no implementation, tests, standards, thresholds, gates,
dependencies, CI, `data/`, DCC or atlas outputs. The #546/#548 files are untouched. Metric policy and adoption
stay with the user; `delivery_passed=false`. C36 (520 vs 512 lower bound) is not decided here.

## Summary

- On one valid planar affine polygon the three metric families can give different verdicts under the same band. **Verified by probe**, 96 rows (8 cases x tri/quad x 6 variants), 0 exceptions.
- Order of strictness is a theorem and held in all 96 rows: with singular values s_min <= s_max of the metre->pixel map, every edge sample lies in [s_min, s_max] and the area density is sqrt(s_min*s_max). So *directional pass => edge pass and area pass*; the converse fails. No row had edge or area stricter than directional.
- Divergent rows (band 10..40, S=2048): 0.1 x 10 m witness (area 35 passes, edges 3.5/350 and sigma 3.5/350 fail); shear (area 16 and edges 16/39.4 pass, sigma 6.08/42.08 fails); rectangle rotated 45 deg against the principal axes of sigma 5/45 (area 15 and edges 32.0/32.0 pass, sigma fails).
- Changing only the polygon direction changes the edge extrema (5/45 -> 27.3/36.1 -> 32.0/32.0 -> 5/45 at 0, 36.87, 45, 90 deg) while sigma 5/45 and area 15 stay fixed. The edge verdict flips; a rotated rectangle gives a *false pass*, observed.
- Pins: #595 `texel_density_readout` (area, `ground_cake.texel_density`) and the `twinqa` edge helper agree with the oracle on numbers (max relative deviation 2.3e-15) but their verdicts differ; #590 `_face_texel` is the only directional one and equals the oracle sigma.
- Production consequence: `V008` (twinqa edge samples, VPM band) is the only one wired into an exported-package check; the others are helpers/CLI/packer. **No observed production delivery failure**: this is a hypothetical comparison on constructed polygons. The recorded 0.1 x 10 m witness was a round-1 packer output that #590 repaired (test docstring), not a delivered package.
- Which metric the regulation requires is not decided here (see Open questions).

## Pins

| item | commit / sha256 (first 16) |
|---|---|
| main | `891df7b2ea26c9754c4572e9b27523ef25a947eb` |
| #590 head (open, not merged) | `639861e592fc11f280b18e99f8c93fd5f3011669`, `tools/materials/npm_atlas_udim.py` sha256 `ba234fce617e89a1` |
| #595 head (open, not merged) | `c409408f2b0ec64d4538ae2cb0683537497106c9`, `src/dt_ai/ops/texel_density_readout.py` sha256 `ff148c9d6195d5fa` |
| main sources (sha256 first 16) | `twinqa/uv.py` 52537081648a720a, `dt_ai/geometry/ground_cake.py` 614c0ca0674d2162, `dt_ai/geometry/uv.py` 259a15fe300ca535, `dt_ai/validate/bundle.py` f02a83cd99bbca43, `twinqa/scene.py` 1363906b62fcce12 |
| probe | `texel_parity_probe.py` sha256 `da944951f167eea7` (below), output JSON sha256 `9bd9f50ebb92c374` (117 568 bytes, kept in `C:/x/`, not committed) |

Neither `npm_atlas_udim.py` nor `texel_density_readout.py` exists on main yet. Both were loaded from the exact PR head
commits with `git show`, not from a checkout. If a PR merges with a different diff, re-run the probe.

## Metrics, as implemented (verified by reading the code)

| name | what it measures | file:line |
|---|---|---|
| edge samples | per ring edge `size * |duv| / |dxyz|`; min compared with the lower bound, max with the upper (inclusive); a degenerate edge raises | main `src/twinqa/uv.py:95-141` (`density_findings`), `:144-` (`edge_densities`); copy without finiteness checks in `src/dt_ai/geometry/uv.py:30` |
| area mean (per triangle) | `tex_px * sqrt(uv_area / world_area)` = geometric mean of sigma; NaN for degenerate | main `src/dt_ai/geometry/ground_cake.py:1168-1177` |
| area mean (polygon, readout) | same function applied to an equal-area triangle built from Newell world area and shoelace UV area (`px_per_m`), faces and materials classified on the locked band, drops listed | #595 `texel_density_readout.py:119-132` (`px_per_m`), `:254-292` (`_measure`), `:348-` (`readout`) |
| directional bounds | per fan triangle `svd(Q * G^-1)`: sigma_min and sigma_max of the affine metre->pixel map; planner needs sigma_min*1.03 >= 10 and sigma_max*0.97 <= 40 with one uniform scale; the read-back is inclusive with EPS 1e-6 | #590 `npm_atlas_udim.py:112-129` (`_face_texel`), `:488-499` (`bounds`), `:594-647` (`measure`, `texel_in_band` at `:630-631`) |

Geometric mean vs min/max stretch: for the map A (metre -> pixel) with singular values s1 >= s2, `area density = S*sqrt(|det M|) = sqrt(s1*s2)`. It is blind to the *ratio* s1/s2. Edge samples are `|A e|/|e|` and always lie in [s2, s1], but reach the extremes only when an edge lies along a principal direction. Directional bounds are the exact extrema. The #590 planner can place one uniform scale only if `s1/s2 <= 40*0.97/(10*1.03) = 3.767` (derived from the code at `:488-499`, not executed); the probe cases have ratios 100 (witness), 6.92 (shear), 9 (rectangles).

## Probe: frozen inputs and method

Cases (world polygon in the z=0 plane, UV = M p + t, atlas side S px, px/m = S*|A e|/|e|). Exact raw polygon and UV
of every row are in the JSON written by the reproducer (the script prints them; `world`, `uv`). Examples:

- witness quad (S=2048, base): world `[[0,0],[0.1,0],[0.1,10],[0,10]]`, uv `[[0,0],[0.01708984375,0],[0.01708984375,0.01708984375],[0,0.01708984375]]` (35 atlas px square).
- shear tri (S=2048, base): world `[[0,0],[64,0],[0,64]]`, uv `[[0,0],[0.5,0],[1.125,0.5]]`, M = (1/128) [[1, 2.25], [0, 1]]. All dyadic.
- rect_rot45 quad: world 64x16 m rectangle rotated by `sqrt(0.5)` (not dyadic, floats recorded in the JSON), M = diag(5/2048, 45/2048).

| case | map M (rows) | polygons |
|---|---|---|
| iso | I/128 | 64 m square; right triangle |
| witness_0.1x10 | diag(35/2048/0.1, 35/2048/10) | 0.1 x 10 m rectangle; its half triangle |
| shear | (1/128)[[1,2.25],[0,1]] | 64 m unit-square shear |
| shear_rot | R_u M R_w^T, R_w=(0.6,-0.8;0.8,0.6), R_u=(0.8,0.6;-0.6,0.8), polygon rotated by R_w | same shear, world and UV rotated (isometric: expected identical) |
| rect_aligned / rot36.87 / rot45 / rot90 | diag(5,45)/2048 | 64x16 m rectangle (and half triangle), rotated by 0, (0.6,0.8), 45, 90 deg relative to the map's principal axes |

Variants per case and representation: `base`; `cyclic1` (ring start moved by one); `reversed` (both rings reversed);
`translated` (world +(1024, 2048, 0) and uv +(1, 2), both exactly representable); `S4096` (doubled assigned map size);
`band_B_x64` (M x 64, S=2048, band 512..1706). Oracle: independent 2x2 closed form `s^2 = (T +- sqrt(D^2+4P^2))/2`
(T = trace of A^T A, D, P its diagonal difference and off-diagonal), area = `S*sqrt|det M|`, edge scalars with plain `math.hypot`.
No production SVD/area helper is used as an oracle. Verdict is computed per metric on a **common illustrative band, closed
interval**: band A = 10..40 (the NPM Ground band, applies to the Ground relief only [D097], OKS/MAF/Flora exempt:
`docs/domain/uv-textures.md:19-20`); band B = 512..1706 (VPM Diffuse, `standards/VPM_STANDARD.yaml:84`; lower bound 512 vs 520 is
C36, not decided here, 512 is only the value the code uses). The Ground band is not transferred to OKS or MAF.

API adapters: `twinqa.uv.density_findings(xyz, uv, S, min_px_per_m=lo, max_px_per_m=hi)` (both finding statuses must pass);
`ground_cake.texel_density` on the fan triangles of the polygon (a quad has no native entry: this is a fan of two calls;
per-triangle values, all must be in band); `texel_density_readout.readout` with profile NPM / VPM (locked bands);
`_face_texel(pts, uv*S)` (a per-face packer helper measurement, **not** a `pack()` or publication result; V flip is irrelevant
to singular values). An exception would be listed as `exception`, not as a verdict: there were none.

## Findings

### Result table, band A 10..40, S=2048 (P pass, F fail; oracle A/E/D = area / edge / directional)

| case | rep | sigma min/max | area mean | edge min/max | oracle area/edge/dir | twinqa density_findings | ground_cake texel_density (fan) | readout #595 | npm #590 `_face_texel` min/max |
|---|---|---|---|---|---|---|---|---|---|
| iso | quad | 16/16 | 16 | 16/16 | P/P/P | P (16/16) | P (16/16) | P (16) | P (16/16) |
| iso | tri | 16/16 | 16 | 16/16 | P/P/P | P (16/16) | P (16/16) | P (16) | P (16/16) |
| witness_0.1x10 | quad | 3.5/350 | 35 | 3.5/350 | P/F/F | F (3.5/350) | P (35/35) | P (35) | F (3.5/350) |
| witness_0.1x10 | tri | 3.5/350 | 35 | 3.5/350 | P/F/F | F (3.5/350) | P (35/35) | P (35) | F (3.5/350) |
| shear | quad | 6.083/42.08 | 16 | 16/39.4 | P/P/F | P (16/39.4) | P (16/16) | P (16) | F (6.083/42.08) |
| shear | tri | 6.083/42.08 | 16 | 16/39.4 | P/P/F | P (16/39.4) | P (16/16) | P (16) | F (6.083/42.08) |
| shear_rot | quad | 6.083/42.08 | 16 | 16/39.4 | P/P/F | P (16/39.4) | P (16/16) | P (16) | F (6.083/42.08) |
| shear_rot | tri | 6.083/42.08 | 16 | 16/39.4 | P/P/F | P (16/39.4) | P (16/16) | P (16) | F (6.083/42.08) |
| rect_aligned | quad | 5/45 | 15 | 5/45 | P/F/F | F (5/45) | P (15/15) | P (15) | F (5/45) |
| rect_aligned | tri | 5/45 | 15 | 5/45 | P/F/F | F (5/45) | P (15/15) | P (15) | F (5/45) |
| rect_rot36.87 | quad | 5/45 | 15 | 27.29/36.12 | P/P/F | P (27.29/36.12) | P (15/15) | P (15) | F (5/45) |
| rect_rot36.87 | tri | 5/45 | 15 | 27.29/36.12 | P/P/F | P (27.29/36.12) | P (15/15) | P (15) | F (5/45) |
| rect_rot45 | quad | 5/45 | 15 | 32.02/32.02 | P/P/F | P (32.02/32.02) | P (15/15) | P (15) | F (5/45) |
| rect_rot45 | tri | 5/45 | 15 | 23.55/32.02 | P/P/F | P (23.55/32.02) | P (15/15) | P (15) | F (5/45) |
| rect_rot90 | quad | 5/45 | 15 | 5/45 | P/F/F | F (5/45) | P (15/15) | P (15) | F (5/45) |
| rect_rot90 | tri | 5/45 | 15 | 5/45 | P/F/F | F (5/45) | P (15/15) | P (15) | F (5/45) |

Band B rows (M x 64) repeat the pattern with the band 512..1706:

| case | rep | sigma min/max | area | edge min/max | oracle A/E/D | tw | gc | ro | np |
|---|---|---|---|---|---|---|---|---|---|
| iso | quad | 1024/1024 | 1024 | 1024/1024 | P/P/P | P | P | P | P |
| iso | tri | 1024/1024 | 1024 | 1024/1024 | P/P/P | P | P | P | P |
| witness_0.1x10 | quad | 224/2.24e+04 | 2240 | 224/2.24e+04 | F/F/F | F | F | F | F |
| witness_0.1x10 | tri | 224/2.24e+04 | 2240 | 224/2.24e+04 | F/F/F | F | F | F | F |
| shear | quad | 389.3/2693 | 1024 | 1024/2521 | P/F/F | F | P | P | F |
| shear | tri | 389.3/2693 | 1024 | 1024/2521 | P/F/F | F | P | P | F |
| shear_rot | quad | 389.3/2693 | 1024 | 1024/2521 | P/F/F | F | P | P | F |
| shear_rot | tri | 389.3/2693 | 1024 | 1024/2521 | P/F/F | F | P | P | F |
| rect_aligned | quad | 320/2880 | 960 | 320/2880 | P/F/F | F | P | P | F |
| rect_aligned | tri | 320/2880 | 960 | 320/2880 | P/F/F | F | P | P | F |
| rect_rot36.87 | quad | 320/2880 | 960 | 1747/2312 | P/F/F | F | P | P | F |
| rect_rot36.87 | tri | 320/2880 | 960 | 1747/2312 | P/F/F | F | P | P | F |
| rect_rot45 | quad | 320/2880 | 960 | 2049/2049 | P/F/F | F | P | P | F |
| rect_rot45 | tri | 320/2880 | 960 | 1507/2049 | P/F/F | F | P | P | F |
| rect_rot90 | quad | 320/2880 | 960 | 320/2880 | P/F/F | F | P | P | F |
| rect_rot90 | tri | 320/2880 | 960 | 320/2880 | P/F/F | F | P | P | F |

### What the 96 rows show (verified)

1. **Numbers agree, verdicts do not.** All production numbers match the oracle (max relative deviation 2.3e-15 over the dyadic and rotated cases; `translated` 9.1e-13 for the non-dyadic rotated coordinates). `twinqa` verdict == oracle *edge* verdict, `ground_cake` and `readout` == oracle *area* verdict, `_face_texel` == oracle *directional* verdict, in all 96 rows.
2. Verdict patterns (oracle area/edge/dir -> twinqa, ground_cake, readout, npm): PPP -> PPPP (12 rows); PPF -> PPPF (32); PFF -> FPPF (48); FFF -> FFFF (4). Edge or area never stricter than directional (0 rows).
3. Where edge and directional agree: any polygon with an edge along a principal axis (witness, aligned and 90-deg rectangles). There edge samples catch the 0.1 x 10 m witness (3.5/350) while the area readout passes it (35).
4. Where they differ: shear (edges 16/39.4 pass against sigma 6.08/42.08) and rotated rectangles (edges 27.3/36.1 and 32.0/32.0 pass against sigma 5/45). Changing the sampled directions changes the edge extrema; sigma and the area mean do not move. This is a measured **false pass of the edge metric**, not a hypothetical one.
5. Representation: triangle and quad give the same sigma and area. Edge extrema differ with the ring (rect_rot45 quad 32.02/32.02, its half triangle 23.55/32.02) because a triangle has a different edge set.
6. Invariances: cyclic start, reversed winding and exactly representable translation changed no verdict and no number beyond 9.1e-13 relative; `shear_rot` equals `shear` to 2.3e-15 (rotating both frames is isometric, so this case checks the oracle and the APIs, not a divergence). Doubling the assigned map size (`S4096`) doubled every number exactly (relative deviation 0.0) and changed 10 of 16 verdict tuples: for the witness (2 rows) `ground_cake` and `readout` flip pass -> fail (area 35 -> 70); for shear, shear_rot, rot36.87 and rot45 (8 rows) `twinqa` flips pass -> fail (edge max 39.4 -> 78.8 and similar) while the area verdicts stay pass (16 -> 32). The map size moves each metric's verdict through its own scale; the metrics keep their different strictness.

### Callers and what each result reaches (read-only inventory on main + PR heads)

| result | callers | kind |
|---|---|---|
| `twinqa.uv.edge_densities` | `twinqa/scene.py:575` (inside `_texel_density_findings`, `:536`, called at `:691` as V008); `tools/evals_geometry_mutation.py:221` (eval: `min(densities) >= 512`, comment "metric helper + eval threshold, NOT V009") | V008: **actual exported-package check** via `tools/qa/validate_package.py:170` and `tools/sintez_parity.py:214` (`scene_findings`), non-UCX meshes, band 512..1706, edge samples only |
| `twinqa.uv.density_findings` | no caller in `src/` or `tools/` (tests only: `tests/qa/test_uv.py`, `test_finding_numeric_margin.py`) | pure helper, polygon-level min and max findings |
| `dt_ai.geometry.uv.edge_densities` | `dt_ai/validate/bundle.py:123` (C003, VPM rectangular surfaces from `layout.json`, all edges against 512..1706 inclusive) | **package check** (`dt-ai validate`), edge samples; the copy has no finiteness checks |
| `ground_cake.texel_density` | `fix_density` (`:1186`) and `side_project_uv` (`:1203`) in the same file, which have no callers in `src/` or `tools/` (tests `tests/test_ground_*.py`); #595 readout | pure helper (per triangle area density); `fix_density` rescales UV to a target on area density |
| #595 `texel_density_readout` | `python -m dt_ai.ops.texel_density_readout --input faces.json --output ... --report ...`; no other caller | CLI report, not in an exported-package check; passes area density against the locked NPM 10..40 / VPM 512..1706 |
| #590 `_face_texel` | `analyze()` (planning, `:412`), `measure()` (read-back, `:613`), inside `pack()`; CLI `main()` returns 1 when `meas["passed"]` is false | planner and read-back inside the packer tool; its report is `texel_in_band` per material, **not** a validator input |

So three result families are exposed by three different callers and none of them calls another: V008/C003 (edge) is the
only exported-package check; area density is a helper and a CLI report; directional bounds exist only inside the #590 packer
and its read-back. A face like the shear or the rotated rectangle above would pass V008/C003 and the #595 CLI and fail the #590 packer read-back.
Observed vs hypothetical: no real report was found that disagrees; the disagreement is shown on constructed polygons.
The only recorded real instance is the packer's own round-1 output for the 0.1 x 10 m quad (UV 350 x 3.5 px/m, area mean 35),
which #590 changed to directional bounds (`tests/test_npm_atlas_udim.py::test_measure_reports_directional_extrema` on the PR head).

## How it applies to this repository

- `src/twinqa/uv.py`, `src/twinqa/scene.py` (V008), `src/dt_ai/validate/bundle.py` (C003): edge samples; a polygon whose edges are not along principal directions can pass while a principal direction is outside the band.
- `src/dt_ai/geometry/ground_cake.py`, #595: area mean; cannot see anisotropy at all (the 0.1 x 10 m witness passes at 35).
- `tools/materials/npm_atlas_udim.py` (#590): directional bounds, stricter than both and the only one that refuses the shear and rotated cases (ratio > 3.767).
- The regulation text (`docs/domain/areas/uv-atlas.md` UV-06; `uv-textures.md:19,51`) states a *density* (px per linear metre `rho = L_t / L_p`) without a direction rule; it is not decided here which of the three is "the" regulation metric. NPM applies to Ground relief; OKS and MAF are exempt (OKS: key criterion is physical material size; px/m only diagnostic).

## Proposed next tasks

1. **Pin the verdict-parity probe as a test** (S). Add the frozen cases (witness, shear, rect_rot45) as a test asserting each API's number against the closed-form oracle and *documenting* current verdicts. Input -> expected: shear tri `world [[0,0],[64,0],[0,64]]`, `uv [[0,0],[0.5,0],[1.125,0.5]]`, S=2048, band 10..40 -> oracle sigma 6.083/42.08, area 16, edges 16/39.4 (twinqa pass; readout pass; npm `_face_texel` (6.083, 42.08)); rect_rot45 quad -> edges 32.02/32.02 pass, sigma 5/45. Value: keeps three-way divergence visible when any of #590/#595/V008 changes. Advances #149.
2. **Decision sheet for the user: which metric a Ground density verdict means** (S). One page with the table above, three options (edge samples, area mean, directional bounds), what each passes/fails, and the effect on V008, C003, #595 and #590; no code. Value: unblocks a gate decision without an implementation guess. Advances #149.

## Open questions for the user

1. Which statistic defines a Ground (NPM) or Diffuse (VPM) density verdict: edge samples, area mean, or directional bounds? (Metric policy; C36 unaffected.)
2. If the user chooses directional bounds, should the V008/C003 checks keep edge samples as a fast screen only?
3. Should the #595 report state its metric (area mean) in its output, so a reader does not take `status: pass` as a directional pass?

## Reproducer

Self-contained: `git fetch origin pull/590/head pull/595/head` in the repo checkout of main `891df7b`, save the script, run
`uv run python texel_parity_probe.py . > probe.json`. It needs only numpy and the repository; reads the two PR files by `git show`; writes nothing into the repository.

```python
#!/usr/bin/env python
"""Texel-density verdict parity probe (research, read-only). No pytest, no files written to the repo.

Run from a checkout of main 891df7b (src/ importable) with PR heads fetched:
  git fetch origin pull/590/head pull/595/head
  uv run python texel_parity_probe.py [REPO_DIR] > probe.json
Production code is imported, never edited. The oracle below uses only math (2x2 closed form).
"""
import hashlib, importlib.util, json, math, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
P590 = "639861e592fc11f280b18e99f8c93fd5f3011669"
P595 = "c409408f2b0ec64d4538ae2cb0683537497106c9"
sys.path.insert(0, str(REPO / "src"))
tmp = Path(tempfile.mkdtemp())


def load(sha, path, name):
    raw = subprocess.check_output(["git", "-C", str(REPO), "show", f"{sha}:{path}"])
    f = tmp / Path(path).name
    f.write_bytes(raw)
    spec = importlib.util.spec_from_file_location(name, f)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod, hashlib.sha256(raw).hexdigest()


from twinqa.uv import density_findings, edge_densities            # main
from dt_ai.geometry.ground_cake import texel_density              # main
ro, ro_sha = load(P595, "src/dt_ai/ops/texel_density_readout.py", "texel_readout_595")
npm, npm_sha = load(P590, "tools/materials/npm_atlas_udim.py", "npm_atlas_590")
EPS = 1e-6  # npm_atlas_udim.measure() float-noise slack


# ---------------------------------------------------------------- independent oracle
def sv2(M):
    (a, b), (c, d) = M
    t = a * a + b * b + c * c + d * d
    r = math.sqrt((a * a + c * c - b * b - d * d) ** 2 + 4 * (a * b + c * d) ** 2)
    return math.sqrt(max((t - r) / 2, 0.0)), math.sqrt((t + r) / 2)


def oracle(poly, M, S):
    lo, hi = sv2(M)
    det = abs(M[0][0] * M[1][1] - M[0][1] * M[1][0])
    ed = []
    for i in range(len(poly)):
        ex = poly[(i + 1) % len(poly)][0] - poly[i][0]
        ey = poly[(i + 1) % len(poly)][1] - poly[i][1]
        ux, uy = M[0][0] * ex + M[0][1] * ey, M[1][0] * ex + M[1][1] * ey
        ed.append(S * math.hypot(ux, uy) / math.hypot(ex, ey))
    return {"sv_min": S * lo, "sv_max": S * hi, "area": S * math.sqrt(det), "edge_min": min(ed), "edge_max": max(ed)}


def inside(v, lo, hi):
    return lo <= v <= hi


def verdicts(o, lo, hi):
    return {"area": inside(o["area"], lo, hi),
            "edge": inside(o["edge_min"], lo, hi) and inside(o["edge_max"], lo, hi),
            "dir": inside(o["sv_min"], lo, hi) and inside(o["sv_max"], lo, hi)}


# ---------------------------------------------------------------- frozen cases
R = lambda c, s: [[c, -s], [s, c]]
mm = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
tr = lambda A: [[A[0][0], A[1][0]], [A[0][1], A[1][1]]]
rot = lambda poly, Rm: [(Rm[0][0] * x + Rm[0][1] * y, Rm[1][0] * x + Rm[1][1] * y) for x, y in poly]
SQ = [(0.0, 0.0), (64.0, 0.0), (64.0, 64.0), (0.0, 64.0)]
TRI = [(0.0, 0.0), (64.0, 0.0), (0.0, 64.0)]
RECT = [(0.0, 0.0), (64.0, 0.0), (64.0, 16.0), (0.0, 16.0)]
RTRI = [(0.0, 0.0), (64.0, 0.0), (0.0, 16.0)]
W = [(0.0, 0.0), (0.1, 0.0), (0.1, 10.0), (0.0, 10.0)]
WTRI = [(0.0, 0.0), (0.1, 0.0), (0.1, 10.0)]
ISO = [[1 / 128, 0.0], [0.0, 1 / 128]]
SHEAR = [[1 / 128, 2.25 / 128], [0.0, 1 / 128]]
Rw, Ru = R(0.6, 0.8), R(0.8, -0.6)          # 3-4-5 rotations (not dyadic: recorded as-is)
SHEAR_ROT = mm(Ru, mm(SHEAR, tr(Rw)))
PRIN = [[5 / 2048, 0.0], [0.0, 45 / 2048]]  # principal directions = world axes; sigma = 5, 45 px/m at S=2048
R45 = R(math.sqrt(0.5), math.sqrt(0.5))
R90 = R(0.0, 1.0)
WIT = [[35 / 2048 / 0.1, 0.0], [0.0, 35 / 2048 / 10.0]]
CASES = [
    ("iso", SQ, TRI, ISO), ("witness_0.1x10", W, WTRI, WIT), ("shear", SQ, TRI, SHEAR),
    ("shear_rot", rot(SQ, Rw), rot(TRI, Rw), SHEAR_ROT),
    ("rect_aligned", RECT, RTRI, PRIN), ("rect_rot36.87", rot(RECT, Rw), rot(RTRI, Rw), PRIN),
    ("rect_rot45", rot(RECT, R45), rot(RTRI, R45), PRIN), ("rect_rot90", rot(RECT, R90), rot(RTRI, R90), PRIN),
]


def uv_of(poly, M, t=(0.0, 0.0)):
    return [(M[0][0] * x + M[0][1] * y + t[0], M[1][0] * x + M[1][1] * y + t[1]) for x, y in poly]


def call(fn):
    try:
        return fn()
    except Exception as e:  # recorded, never counted as a rejection verdict
        return {"exception": f"{type(e).__name__}: {e}"}


def measure_apis(poly, uv, S, lo, hi, profile):
    xyz = [(x, y, 0.0) for x, y in poly]
    out = {}
    def tw():
        f = density_findings(xyz, uv, S, min_px_per_m=lo, max_px_per_m=hi)
        e = edge_densities(xyz, uv, S)
        return {"edge_min": min(e), "edge_max": max(e), "status": [x.status for x in f], "verdict": all(x.status == "pass" for x in f)}
    def gc():
        faces = np.array([[0, i, i + 1] for i in range(1, len(poly) - 1)], dtype=np.int64)
        d = texel_density(np.array(xyz), faces, np.array(uv)[faces], S)
        return {"min": float(d.min()), "max": float(d.max()), "verdict": bool(np.all((d >= lo) & (d <= hi)))}
    def rd():
        r = ro.readout({"profile": profile, "materials": [{"name": "M", "map_px": S}],
                        "faces": [{"id": "f", "material": "M", "xyz": [list(p) for p in xyz], "uv": [list(p) for p in uv]}]})
        return {"px_per_m": r["faces"][0]["px_per_m"] if r["faces"] else None, "status": r["status"],
                "dropped": [d["reason"] for d in r["dropped"]], "verdict": r["passed"]}
    def nm():
        a, b = npm._face_texel(np.array(xyz), np.array(uv) * S)
        return {"min": a, "max": b, "verdict": bool(npm.GROUND_MIN - EPS <= a and b <= npm.GROUND_MAX + EPS)} if (lo, hi) == (10, 40) else \
               {"min": a, "max": b, "verdict": bool(lo <= a and b <= hi), "note": "same inclusive test on band B; npm module itself only knows 10..40"}
    out["twinqa"], out["ground_cake"], out["readout595"], out["npm590"] = call(tw), call(gc), call(rd), call(nm)
    return out


rows = []
for name, quad, tri, M in CASES:
    for rep, poly in (("quad", quad), ("tri", tri)):
        for var in ("base", "cyclic1", "reversed", "translated", "S4096", "band_B_x64"):
            S, k, (lo, hi), prof = 2048, 1.0, (10, 40), "NPM"
            p = list(poly)
            Mv = M
            t = (0.0, 0.0)
            uv = uv_of(p, Mv)
            if var == "cyclic1":
                p, uv = p[1:] + p[:1], uv[1:] + uv[:1]
            elif var == "reversed":
                p, uv = p[::-1], uv[::-1]
            elif var == "translated":
                uv = uv_of(p, Mv, (1.0, 2.0))
                p = [(x + 1024.0, y + 2048.0) for x, y in p]
            elif var == "S4096":
                S = 4096
            elif var == "band_B_x64":
                Mv = [[v * 64 for v in r] for r in M]
                uv = uv_of(p, Mv)
                (lo, hi), prof = (512, 1706), "VPM"
            o = oracle(p, Mv, S)
            rows.append({"case": name, "rep": rep, "variant": var, "S": S, "band": [lo, hi], "world": p, "uv": uv,
                         "oracle": o, "oracle_verdict": verdicts(o, lo, hi), "api": measure_apis(p, uv, S, lo, hi, prof)})

json.dump({"main": subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"]).decode().strip(),
           "pr590": P590, "pr595": P595, "sha256_texel_density_readout.py": ro_sha, "sha256_npm_atlas_udim.py": npm_sha,
           "rows": rows}, sys.stdout, indent=1)
```
