# UCX: coordinate precision budget after rejected #281

`delivery_passed=false`. Research only; no adoption, tolerance/gate change, or export-coordinate convention decision. All #281 geometry is synthetic, not a surveyed object. Intended PR destination: **artsafro/AGR-DigitalTwin-pilot only**; no PR was created here.

## Answer and evidence status

**The first precision-losing representation boundary in this code path is the conversion of Python dump coordinates into Blender mesh-local vertex storage at `Mesh.from_pydata`.** The driver has already baked rotation and survey translation into those coordinates. They are therefore numerically large even though Blender calls them *local*. Blender's vertex-coordinate implementation uses C `float`, not Python's binary64 arithmetic [B1–B3]. Converting them back to Python floats cannot restore the discarded bits.

**Observed endpoint evidence:** the committed imported *pair distances* agree with a source-vertex binary32 quantization diagnostic to at most **6.019490461639521e-16 m**, across 54 measurements. This is strong consistency evidence for that boundary, **not a stage-by-stage observation proving “not FBX.”** There are no committed pre-FBX mesh-coordinate snapshots or parsed FBX numeric arrays in the results. Exporter transformations, FBX encoding, importer conversions, and final mesh storage are not separately isolated. Equal scalar distances also do not establish equal vertices.

Evidence revisions:

- Experiment ref `origin/experiment/hyp-281`, resolved to `1a39f94cdbe0e244e89716ac38096ec8f550daff` (abbreviated **E** below). Repository citations `E:path:line` refer to this immutable revision, available with `git show E:path`.
- Current read-only production inspection: `8e539b9a2a020fcf045eb9445e5940a3d87977c7` (**P** below).
- [Committed experiment report](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/1a39f94cdbe0e244e89716ac38096ec8f550daff/docs/experiments/hyp-281.md), especially lines 34–69. The report distinguishes neither first storage conversion from later conversions nor endpoint agreement from causal exclusion; this note does.

## Representation trace

| Boundary | Repository evidence | Precision interpretation / what was observed |
|---|---|---|
| Analytic boxes → rotated, translated coordinates | `E:experiments/hyp-281/driver.py:33–51` | Python arithmetic builds `Rz(angle)*p+t`; both rotation and translation are baked into each vertex. There is no local-origin/object-translation variant in this experiment. |
| Coordinates → JSON dump → Python values | `E:experiments/hyp-281/driver.py:74–78`; `P:tools/export/export_mesh_blender.py:25` | `json.dumps`/`json.loads` bridge Python floats. No explicit binary32 conversion occurs here. The baseline is measured from `src`, not a separately reloaded dump (`driver.py:112–116`), so the recorded baseline is not a direct JSON roundtrip measurement. |
| Python values → Blender mesh-local vertices | `P:tools/export/export_mesh_blender.py:73–74` | `from_pydata` receives the baked coordinates unchanged. API: vertices are coordinate triples [B1]; vertex storage accesses C `float*` [B3]. This is the first identifiable binary32 storage boundary. Mesh validation/update at lines 82–84 does not restore precision. No native coordinate snapshot was recorded here. |
| Mesh-local coordinates → object transform | `P:tools/export/export_mesh_blender.py:85–90` | New mesh objects are linked without assigning location/rotation/scale; only helper empties get locations. Thus large coordinates remain in the mesh, not an object translation. `Object.matrix_world` is the world-space transform [B4]. |
| Blender scene → FBX | `P:tools/export/export_mesh_blender.py:67–69,94–96` | Metric scene, scale 1; FBX export uses `apply_unit_scale=True`, `use_mesh_modifiers=False`. These options do not specify a numeric error budget. No raw FBX arrays were inspected in #281. “Float32 FBX coordinates” is an audit comment, not proof of the FBX file's numeric encoding. |
| FBX → fresh Blender mesh and matrix | `E:experiments/hyp-281/readback.py:18–27` | Fresh import, then mesh coordinates and matrix elements promoted individually to Python floats. The imported mesh again has Blender float vertex storage; lost detail could not be recovered even from a wider on-disk representation. |
| Imported local vertices + matrix → independent world reconstruction | `E:experiments/hyp-281/readback.py:25–32` | Each world component is computed with Python scalar products/sums, **not** `mathutils.Matrix @ Vector`. This retains binary64 during reconstruction, but only for already-rounded inputs. Raw/world/matrix are written to temporary readback JSON; committed `results.json` retains measurements and metadata, not these arrays. |
| Reconstructed geometry → measured gap | `E:experiments/hyp-281/driver.py:98–110,112–125`; `P:src/twinqa/geometry/ucx_audit.py:42–57,149–173,219–256` | Imported geometry is welded at 1e-5 m; source diagnostic is not welded. SAT chooses relation, then vertex–triangle and edge–edge minima measure surface distance. This is more than subtracting two coordinate values. |

Primary references (retrieved for this research):

- **[B1]** Blender API [`Mesh.from_pydata`](https://docs.blender.org/api/current/bpy.types.Mesh.html#bpy.types.Mesh.from_pydata): constructs a mesh from vertices, edges and faces; coordinates are float triples. API's word “float” alone is not a binary32 storage guarantee.
- **[B2]** Blender API [`MeshVertex.co`](https://docs.blender.org/api/current/bpy.types.MeshVertex.html#bpy.types.MeshVertex.co): vertex coordinate, three-component `mathutils.Vector`.
- **[B3]** Version-pinned Blender **v5.1.2** implementation [`rna_mesh.cc:400–409`](https://github.com/blender/blender/blob/v5.1.2/source/blender/makesrna/intern/rna_mesh.cc#L400-L409): coordinate getter/setter copy three values through `float*` / `const float*`. This supplies the storage-width evidence absent from the high-level API wording.
- **[B4]** Blender API [`Object.matrix_world`](https://docs.blender.org/api/current/bpy.types.Object.html#bpy.types.Object.matrix_world), [`Object.location`](https://docs.blender.org/api/current/bpy.types.Object.html#bpy.types.Object.location): world-space transformation matrix and object location; these are distinct from mesh vertex coordinates. Current API pages are navigational references, not a claim that their current release equals the experiment's 5.1.2 build.
- **[S1]** Python [`struct` format notes](https://docs.python.org/3/library/struct.html#format-characters): `f` packs IEEE 754 binary32, `d` binary64 regardless of platform floating-point representation. Python [`float`](https://docs.python.org/3/library/stdtypes.html#numeric-types-int-float-complex) is usually implemented as C double, consistent with the recorded CPython environment.

## Conditional coordinate budget (not a delivery guarantee)

For finite normal binary32 values within a binade `[2^e,2^(e+1))`, spacing is `ULP = 2^(e-23)` m. Under round-to-nearest, a **single coordinate conversion** has absolute error at most half that spacing. At powers of two spacing changes; use the largest spacing encountered by the actual coordinates, not an object's translation alone. This is not a bound for repeated matrix arithmetic, exporter/importer scaling, overflow, or a changed mesh.

All table numbers are **millimetres**, per component. “Local” is explicitly a 10 m representative coordinate, not zero (zero has no single scene-wide ULP).

| Representative absolute coordinate | ULP (mm) | Half-ULP (mm) | Status |
|---|---:|---:|---|
| Local: 10 m (binade 8–16 m) | 0.00095367431640625 | 0.000476837158203125 | Analytic; also bounds each conversion for the experiment's local-sized coordinates below 16 m |
| 100 m | 0.00762939453125 | 0.003814697265625 | Analytic; nearby coordinates occur in recorded scenes |
| 1 km = 1,000 m | 0.06103515625 | 0.030517578125 | Analytic only; no 1 km native case |
| 1,170 m (stress-scene X magnitude) | 0.1220703125 | 0.06103515625 | Analytic |
| 14.2 km = 14,200 m | 0.9765625 | 0.48828125 | Analytic; stress-scene Y magnitude |
| Full-grid illustrative X: 500,000 m | 31.25 | 15.625 | Synthetic MSK-like example, not a declared project origin |
| Full-grid illustrative Y: 2,200,000 m | 250 | 125 | Synthetic MSK-like example, not measured in #281 |

“MSK-like” does not identify one numerical magnitude: zone, false origin and coordinate convention matter. These last two rows illustrate full survey-grid component sizes, not an adopted CRS or a result for a real site. No full-grid export was executed in #281.

### Self-contained binary32 reproduction (stdlib only; not executed here)

This reproduces the spacing and axis-aligned quantization mechanism and exposes independently rounded facing corners for all recorded angles. It deliberately does **not** label a corner separation as the minimum surface gap. The measured rotated gaps below come from committed results, not this snippet.

```python
import math
import struct


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def ulp32(x):
    # Positive finite normal representatives only; next binary32 value.
    q = f32(x)
    bits = struct.unpack("<I", struct.pack("<f", q))[0]
    nxt = struct.unpack("<f", struct.pack("<I", bits + 1))[0]
    return nxt - q


for x in (10.0, 100.0, 1000.0, 1170.0, 14200.0, 500000.0, 2200000.0):
    u = ulp32(x)
    print("m / ULP_mm / half_ULP_mm", x, u * 1000, u * 500)

translations = ((0.0, 0.0), (100.0, 100.0), (-1170.0, -14200.0))
for tx, ty in translations:
    # At angle zero, facing faces have constant X: this IS the box gap.
    print("axis gaps mm", tx,
          [1000 * (f32(tx + 2 + g) - f32(tx + 2))
           for g in (0.003, 0.004, 0.006)])
    for angle in (0, 37, 89):
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        for k, g in enumerate((0.003, 0.004, 0.006)):
            # Both corners along each facing edge, as in driver.scene.
            for y in (4 * k, 4 * k + 1):
                a = (2 * c - y * s + tx, 2 * s + y * c + ty)
                b = ((2 + g) * c - y * s + tx,
                     (2 + g) * s + y * c + ty)
                qa, qb = tuple(map(f32, a)), tuple(map(f32, b))
                # Subtraction remains binary64; no second f32 conversion.
                print(angle, k, y, "rounded XY", qa, qb,
                      "corner-distance mm", 1000 * math.dist(qa, qb))
```

For example, the axis-gap line at X = -1170 m gives approximately `3.0517578125 / 4.0283203125 / 5.9814453125` mm. This needs neither FBX nor Blender to explain the observed axis-aligned quantization signature.

## Recorded measured versus quantized surface gaps

Primary committed artifacts: [driver](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/1a39f94cdbe0e244e89716ac38096ec8f550daff/experiments/hyp-281/driver.py#L111-L129), [readback](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/1a39f94cdbe0e244e89716ac38096ec8f550daff/experiments/hyp-281/readback.py#L18-L32), and [results](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/1a39f94cdbe0e244e89716ac38096ec8f550daff/experiments/hyp-281/results.json#L3).

Each cell is **imported / f32_diag**, in mm, nominal gaps ordered 3 / 4 / 6 mm. Nine decimal places are for comparison, not an accuracy claim. Repetition 1 is shown; repetition 2 has identical measured gaps. Source: `E:experiments/hyp-281/results.json`, `rows` 0–26 (zero-based); fields `angle`, `t`, `gap_nominal_m`, `imported.gap_m`, `f32_diag.gap_m`. First record starts at line 3; driver generation and measurement are at `driver.py:111–129`.

| Angle | Translation (m) | Nominal 3 mm: measured / quantized | Nominal 4 mm: measured / quantized | Nominal 6 mm: measured / quantized |
|---|---|---|---|---|
| 0° | (0,0,0) | 3.000020981 / 3.000020981 | 3.999948502 / 3.999948502 | 6.000041962 / 6.000041962 |
| 0° | (100,100,0) | 2.998352051 / 2.998352051 | 3.997802734 / 3.997802734 | 5.996704102 / 5.996704102 |
| 0° | (-1170,-14200,0) | 3.051757812 / 3.051757812 | 4.028320312 / 4.028320312 | 5.981445312 / 5.981445312 |
| 37° | (0,0,0) | 3.000052409 / 3.000052409 | 4.000197721 / 4.000197721 | 5.999770925 / 5.999770925 |
| 37° | (100,100,0) | 3.001416870 / 3.001416870 | 3.999328705 / 3.999328705 | 5.998242238 / 5.998242238 |
| 37° | (-1170,-14200,0) | **2.440089510 / 2.440089510** | 3.710194718 / 3.710194718 | 5.565292077 / 5.565292077 |
| 89° | (0,0,0) | 2.999881897 / 2.999881897 | 4.000077531 / 4.000077531 | 5.999988783 / 5.999988783 |
| 89° | (100,100,0) | 2.998827450 / 2.998827450 | 3.998392207 / 3.998392207 | 5.997521763 / 5.997521763 |
| 89° | (-1170,-14200,0) | 2.929234871 / 2.929234871 | 3.907792193 / 3.907792193 | 5.860615441 / 5.860615441 |

**Observed rejection:** 37°, stress translation, nominal 3 mm gives 2.440089510 mm, an error of about **0.559910490 mm**, above the frozen 0.5 mm limit twice. The report records 54/54 `in_band`, zero penetration; 108/108 boxes retain closure/convexity and expected structure; 36/36 native calls return zero (`E:docs/experiments/hyp-281.md:34–42`). These are experiment checks, not production delivery acceptance.

**Claims requiring qualification:**

- “The cause is float32 vertex storage, not FBX” (`E:docs/experiments/hyp-281.md:56–57`) combines a supported storage mechanism with an unisolated causal exclusion. Endpoint scalar agreement supports the mechanism, not an assertion that every intermediate stage is harmless.
- Rotated-corner rounding can change face normals and which triangle/edge pair realizes the minimum. The endpoint data are compatible with this; no intermediate face-normal measurements were committed.
- “The transform is rigid, so the gaps are not affected” (`report:68–69`) is stronger than the metadata. `driver.py:100–106` records maximum elementwise deviation from identity (about 1.6292e-7), **not** orthogonality, singular values, determinant, or a rigidity proof. The binary64 reconstruction avoids an extra binary32 world-vector conversion, but does not prove the imported matrix is exactly rigid.
- The report's suggestion about a **2 mm** gap (`report:65`) is a prediction, not an observation. Frozen inputs contain only 3/4/6 mm (`E:experiments/hyp-281/predictions.json:5`). This research makes **no inference about an unexecuted 2 mm result**, its class, or a threshold crossing.
- `P:src/twinqa/geometry/ucx_audit.py:15` comments that modelled 2.000 mm reads back within 0.01 mm. #281 does not test that nominal gap, and its coordinate budget is not universal. The comment and `BAND_TOL_M` remain unchanged.

## Why component bounds are not arbitrary gap or whole-surface safety

Half-ULP bounds one rounded scalar. A point's displacement is at most `sqrt(bx²+by²+bz²)` if its component bounds are `bx,by,bz`. For **specified corresponding point pairs**, reverse triangle inequality bounds distance change by the sum of the two displacement norms, not by one half-ULP. Rotation and independent rounding affect all participating components; errors need not cancel.

For illustration only: around (-1170,-14200,0), using X half-ULP 0.06103515625 mm, Y 0.48828125 mm, and Z below 4 m half-ULP at most 0.00011920929 mm, the per-vertex displacement bound is about 0.4921 mm; twice that is about 0.9842 mm. Thus a 0.5599 mm pair-gap error is compatible with the component budget. This is **not** a newly verified end-to-end bound.

A conditional surface-distance bound can be derived if the *same* triangles retain vertex correspondence and each displacement is bounded: barycentric interpolation bounds every corresponding surface point, giving a Hausdorff bound per surface; the change in minimum surface distance is bounded by the sum of the two surface bounds. Coordinate bounds **alone** do not establish these hypotheses through validation, triangulation, welding, degenerate-face handling, arbitrary transforms, or importer/exporter processing. SAT classification and floating-point distance evaluation require their own analysis too.

Finally, a **minimum** pair gap says nothing about the maximum gap over facing surfaces, target completeness, deviation of model surfaces from UCX, closure of arbitrary hulls, or preservation of openings. The area sheet `docs/domain/areas/ucx.md` R09–R13 separates intersections, gap advisory, and whole-target surface deviations. Neither the table nor the 54 box measurements closes those gates.

## Local vertices + translation versus baked world vertices (conceptual only)

For a rigid rotation `R`, translation `T`, and local point `p`, the current path stores approximately `Q32(R*p + T)` as the mesh coordinate, with an initially identity object matrix. Large `T` determines vertex spacing. Subtracting the origin **after** this conversion cannot recover the gap detail.

An alternative representation could store `Q32(p)` with an object matrix containing `R,T`, or store `Q32(R*p)` with translation alone in the matrix. Independent readback would promote **each stored matrix element and local component first**, then compute `M*p` in binary64 as #281 already does. It must not perform a binary32 world-space `mathutils` multiplication and promote only its result.

This can preserve local detail longer; it does not establish that an FBX exporter/importer keeps that decomposition. Translation and matrix elements also have finite precision. A common translation may cancel in pair distances under binary64 reconstruction, while independently rounded object origins may introduce differential errors. Baking transforms later can reintroduce the large-coordinate mesh boundary. No variant was measured in #281, and choosing one would require coordinate/transform policy review outside this research.

## At most two follow-up proposals (not executed or adopted)

1. **S — boundary snapshots, fixed original matrix.** Input: exact #281 six-box scenes, angles 0/37/89°, three original translations, 3/4/6 mm gaps; unchanged production exporter/auditor. Instrument a separate experimental copy to capture coordinates immediately after `from_pydata`, before export, parsed FBX vertices/transforms, and imported raw coordinates/matrices. Frozen expected measurement pair: **input vertex `v` → post-`from_pydata` coordinate `Q32(v)` componentwise**; **37°/stress/3 mm scene → imported gap 2.440089510 mm within 1e-6 mm**. Compare each later stage against its immediately preceding reconstructed geometry, with explicit unit/axis mappings; no presumed FBX encoding or expected zero intermediate drift. Missing snapshots make causal isolation inconclusive, not successful.
2. **M — representation A/B with independent reconstruction.** Input: same boxes and original angle/translation/gap matrix, one baked arm and one experimental arm retaining local vertices plus a *shared identical* object `R,T`; no 2 mm case. Freeze before native runs: **baked stress 37°/3 mm → 2.440089510 mm within 1e-6 mm**; **local arm reconstructed before FBX in binary64 → each nominal 3/4/6 mm gap within 0.001 mm**, with identical matrix elements for both boxes and no world-vector binary32 conversion. Record the post-FBX difference from that arm's pre-FBX geometry as the experimental outcome, not a promised improvement. Log raw vertices/matrices and coordinate-error maxima so a gap match cannot hide a different representation. No output becomes a delivery or policy recommendation automatically.

## Open questions and research-run receipt

- Where, if anywhere, does the actual FBX exporter bake/rescale these vertices, and what numeric arrays does it write? Which conversion happens on import before Blender mesh storage?
- Do imported raw coordinates equal the source binary32 diagnostic componentwise, and is the residual matrix an orthogonal transform within a quantified bound? The committed scalar results cannot answer either question.
- Would an object-local representation survive this exact FBX roundtrip without later world-coordinate baking? Separate origins, full-grid magnitudes, other rotations and arbitrary hulls remain unmeasured.
- What end-to-end bound survives topology processing and the actual coordinate convention? This note deliberately does not choose that convention or authorize a tolerance change.

Only this document was authored; production files were read-only. No native/live DCC, experiment driver, reproduction snippet, new export, or data-directory write was performed. Reading committed JSON and calculating the displayed comparison are evidence extraction, not a new geometry experiment.

The card's appended RED/fix/regression instructions do not identify a production defect to fix and conflict with its research-only scope: **RED/GREEN and invariant→probe N/N are not applicable; no regression test was added.** A harness instruction nevertheless required one full-suite attempt on unchanged code:

`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_7eea804d`

The command **timed out after 400 seconds**, with **one visible failure** and progress last showing **29%**. There is **no pytest final summary line or reliable passed/failed total**; the harness's final line was `Command timed out after 400 seconds`. No second suite run was made, and the failure was not investigated in this research-only task. Full-suite completion and RED/GREEN remain undone; no test-pass claim is made. `delivery_passed=false`.
