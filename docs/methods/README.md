# Methods catalog

Several ways to solve each modelling, texturing and source task, measured on the same fixed objects, with a
short guide saying when each way is better. Judged by numbers, not by eye (requirement of issue #706).

- One folder per task class: `docs/methods/<class>/`.
- `VARIANTS.md`: each variant's idea, tool (3ds Max / pymxs, Blender / bpy or geometry nodes, our kernel,
  Revit export clean-up), inputs, steps, script path and limits.
- `results.jsonl`: one measured JSON row per (variant, benchmark object), appended by
  `tools/methods/run_variant.py`. Rows are never edited; a re-measurement is a new row.
- `RESULTS.md`: the comparison table, generated from `results.jsonl` by `tools/methods/results_md.py`.
  Do not edit it by hand. Its row ids (R1, R2, ...) are the line numbers of `results.jsonl`.
- `WHEN.md`: decision guide, at most 15 rules "use A when ..., B when ...". Every rule cites at least
  one RESULTS row id. A rule without a measured row is not written.

Our own code only: team scripts and plugins are described by their logic in `docs/research/`
(team-scripts-audit, team-plugins-audit, 3dsmax-scripting); their text is never copied (public repo).

## Classes

| Class | Status | What a variant produces |
|---|---|---|
| [building-body](building-body/VARIANTS.md) | stub | OKS body mesh (walls, slabs, roof, decor) from the sources |
| [windows-glazing](windows-glazing/VARIANTS.md) | stub | windows, frames and glass (geometry or atlas planes) |
| [ground-terrain](ground-terrain/VARIANTS.md) | stub | Ground surface: relief, paving, kerbs, layers |
| [ucx-collisions](ucx-collisions/VARIANTS.md) | **measured** (5 variants x 3 objects) | VPM UCX collision pieces |
| [texturing-by-drawings](texturing-by-drawings/VARIANTS.md) | stub | UV + textures from the drawings (unique unwrap / trim sheet / procedural joints, then UDIM -> atlas) |
| [sources](sources/VARIANTS.md) | stub | clean input: Revit -> FBX, DWG -> model, supplied-FBX repair |

## Benchmark set

`benchmark/methods/benchmarks.json`: KPP1 (VPM v005), TEC26 AC08 (pilot v010), TOW02 (export-v005),
Vatutino Ground v014, with the classes that apply to each. The model files are private: only their
sha256, the local copy path under `C:/x/methods/src/` and how to fetch them are committed.
The runner refuses a class that is not listed for the object.

## Measuring one variant output

```
uv run python tools/methods/run_variant.py <output .fbx|.zip> --bench <id> --class <class> --variant <name> \
    [--variant-report <out>.variant.json | --wall-time-s S] [--render <view>=<png> ...]
```

Exit 0 appends one row; 2 = measurement error, nothing appended; 4 = refused (unknown benchmark or class,
results path aliasing an input, bad wall time). The results file is rewritten through a `.partial` copy.

## Row fields

| Field | Meaning | Null when |
|---|---|---|
| `wall_time_s` | variant build time from its report (after import, up to the end of the export) | no report / time given |
| `triangles` | `model` = all non-UCX triangles, `ucx` = all UCX triangles | - |
| `objects` | meshes, model meshes, UCX meshes, non-mesh objects | - |
| `xview` | Overlapping Vertices / Faces over every non-UCX mesh, shared thresholds 2 mm / 5 mm / cos 0.9999 (0.81 deg) from `src/dt_ai/ops/inv_xview.py`, never changed here | no model mesh |
| `ucx` | V010 (present, slots, budget [D012], intersections, coverage, advisory gap, shape) and V012 UCX names from `twinqa.scene`; `status` fail = a gating check fails, pass = all pass, open = no fail but a gating check is not_run / review; plus closed-convex count | - (no UCX = fail) |
| `texel` | min / median px/m over every polygon edge (`twinqa.uv.edge_densities`); texture side from the readback, or per UDIM tile from the package's diffuse PNGs | no texture size, no UV, a UV tile without a diffuse PNG |
| `file_size_bytes` | size of the measured output (FBX or ZIP) | - |
| `matid` | material-slot integrity: every used material index has a non-empty slot, no unused slot, no slot on UCX; `material_ids` = indices used | no extra readback |
| `render_score` | SSIM, luma, 7x7 window, on aligned renders of the benchmark's reference views (same size, no resampling); mean over the views | the benchmark has no reference picture, or no render was given; a partial or mismatched set is an error, never a score |
| `class_metrics.ucx_fit` | one-sided model -> UCX deviation [D134] (max, p95, share over 0.1 / 0.3 / 1 m) on surface samples; voxel UCX volume, model envelope (closing 1 m), UCX outside the envelope, envelope left uncovered | no UCX piece |

The shares over 0.1 / 0.3 / 1 m are measurements only: no Ground / pedestrian / other-OKS zoning is done, so
they are not the R11-R13 verdict.

## Adding a class or a variant

1. Write the variant into the class `VARIANTS.md` (idea, tool, inputs, steps, script path, limits).
2. Its script writes the output to a new path (never the source) and a `<out>.variant.json` with `ok` and
   `wall_time_s`.
3. Measure with `run_variant.py` on every benchmark object the class applies to; regenerate RESULTS.md.
4. Update WHEN.md only from rows; each rule cites its rows.
