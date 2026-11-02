# FBX polygon-stream consumption boundary

## Summary

Research only. `delivery_passed=false`. No production repair, no parser policy, no historical report recomputed.

Pinned `origin/main` is `148bab1187bb844d89f9914349eb3eeea88f3087`. PR #609 is open: head `601bd72c3711d203f78c550576153404e4e84c15` on `origin/improve/hyp-603` (commits `a8d407f`, then `601bd72`). The historical reader blob is the same on both pins: `experiments/tow02-hand-finish-face-diff/face_diff.py` = `4f77d9c169b9638f5161c23f17570e609377bf3b`.

#609's final helper (`audit_correspondence.py` blob `58217a078c12975c6919a03828e2f882eb2b2eb9`) reads that decoder and refuses a `PolygonVertexIndex` stream that is not entirely closed polygons with in-range vertex ids. The historical mesh assembler and every current caller of `face_diff.mesh` still return closed polygons only, so a trailing unclosed run is omitted from face counts. The historical report driver walks UV corners by those closed faces only: a short `UVIndex` raises `IndexError`, and a longer `UVIndex` is partly unused, with a centroid still produced.

No `src/` or `tools/` caller imports this decoder. BODY triangle and topology verdicts go through Blender readback. Production gate, `mesh_report`, job state and `delivery_passed` are unexposed.

Measurements below are synthetic. The node-tree half is an in-process double of `read_fbx` and does not verify binary parsing. The binary half uses the #609 test writer on tiny synthetic files only. Real TOW02 FBX files were not opened.

## Findings

### Layers

| Layer | Where | What it does with the index stream |
|---|---|---|
| Raw binary decoder | `face_diff.read_fbx` (`face_diff.py:18`) | Returns the node tree. On the synthetic binaries below, `PolygonVertexIndex` came back equal to the bytes that were written. |
| Mesh assembler | `face_diff.mesh` (`face_diff.py:65-81`) | Closes a polygon on each negative index (`:75-79`) and returns `UV` and `UVIndex` unchanged (`:81`). A trailing run with no negative index is left in a local list and is absent from the returned faces. There is no consumed-corners == raw-corners test. |
| Historical report driver | `face_diff.main` (`face_diff.py:136-158`) | Calls `mesh` at `:138-139`. The UV walk at `:156-158` advances by `len(p)` of each returned face. It does not compare that count with `len(UVIndex)` or with the raw index stream. |
| Repaired helper (#609, control) | `audit_correspondence.load_mesh` at head `601bd72` (`:131` calls `fd.read_fbx`; `:152` range; `:156-160` trailing run and `sum(map(len, polys)) != len(raw)`) | Refuses an incomplete or out-of-range stream with `AuditError` before any audit counts. It does not read `LayerElementUV`. |

Commit `a8d407f` on the same PR called `fd.mesh` at `audit_correspondence.py:157-158`. Commit `601bd72` replaced that with `load_mesh`. The message is `Adopt #603 review R1/R2: unique exclusive temp output, fail closed on incomplete PolygonVertexIndex`. The test module blob is `7ae4fdf5bb5ed3d50f11f414bb8eec3643873840`; its section comment says `R1/R2 (PR #609 review round 1)`.

`experiments/hyp-603/run.py` is on `148bab11` and is absent from tree `601bd72`. `face_diff.py`, `compare_readers.py` and `part_truth.py` are on both pins; the three-dot diff `148bab11...601bd72` does not change them.

### Verified-by-me: node-tree double of the assembler

CPython 3.14.7. Probe `C:/x/t_220f5cbc/probe_fbx_consumption.py`, results `C:/x/t_220f5cbc/probe_results.json`. `face_diff.read_fbx` was replaced in-process. Input label: **synthetic node-tree double, not a binary FBX**. Three vertices `(0,0,0), (1,0,0), (0,1,0)`. UV pairs `(0,0), (1,0), (0,1)` (`UV` length 6). Model name `SM_Vyatskaya_Vl_47_49_013_Main`. `mesh()` was called with `face_diff.OBJ`.

The UV-walk column is the loop copied from `face_diff.main:156-158`, run on the arrays `mesh()` returned. An exception is recorded as an exception, not as a pass or fail verdict. `full poly` means returned corner count equals `len(PolygonVertexIndex)`.

| Case | PolygonVertexIndex | UVIndex | mesh() | verts | faces | face ids | UV len | UVIndex len | consumed / raw poly | UV walk |
|---|---|---|---|---:|---:|---|---:|---:|---|---|
| a complete | `[0,1,-3]` | `[0,1,2]` | returns | 3 | 1 | `[[0,1,2]]` | 6 | 3 | 3 / 3 | consumes 3 / 3; centroid `(1/3, 1/3)` |
| b closed triangle plus unfinished | `[0,1,-3,0,1]` | `[0,1,2,0,1]` | returns | 3 | 1 | `[[0,1,2]]` | 6 | 5 | 3 / 5 (2 omitted) | consumes 3 / 5; same centroid; 2 UV corners unused |
| c suffix only | `[0,1]` | `[0,1]` | returns | 3 | 0 | `[]` | 6 | 2 | 0 / 2 (2 omitted) | consumes 0 / 2; no centroid |
| d out-of-range closed face | `[0,1,-4]` | `[0,1,2]` | returns | 3 | 1 | `[[0,1,3]]` | 6 | 3 | 3 / 3 | consumes 3 / 3; same centroid. `face_diff.tri` then raises `IndexError: list index out of range` |
| e short UVIndex | `[0,1,-3]` | `[0,1]` | returns | 3 | 1 | `[[0,1,2]]` | 6 | 2 | 3 / 3 | `IndexError: list index out of range` |
| f excess UVIndex | `[0,1,-3]` | `[0,1,2,0,1]` | returns | 3 | 1 | `[[0,1,2]]` | 6 | 5 | 3 / 3 | consumes 3 / 5; same centroid; 2 UV corners unused |

Negative indices decode with Python `~i`: `-3` → vertex 2, `-4` → vertex 3. Case d's face id 3 is outside the three vertices. `mesh()` still returns. The `IndexError` appears at the first vertex lookup (`tri`), which is the report driver's later step, and it carries no polygon-stream diagnostic.

Case e's `IndexError` is the UV walk, after `mesh()` has already returned a complete face. Case f produces the centroid and leaves two `UVIndex` entries unused. Case b omits two polygon corners and, because this double's `UVIndex` was sized to the raw polygon stream, also leaves two UV corners unused. Case c returns an empty face list and no exception.

### Verified-by-me: synthetic binary pair through the real decoder

The writer is `_prop` / `_node` / `_fbx` taken verbatim from `601bd72:tests/test_tow02_face_correspondence_audit.py` (extracted under `C:/x/t_220f5cbc/`, not copied into the repo). Its `UVIndex` is fixed at `[0,1,2]` and its `UV` array is the same six doubles. That schedule is separate from cases b, c, e and f above. Files are synthetic, version 7400, not a real object. `face_diff.read_fbx` then `face_diff.mesh` ran on the bytes. `load_mesh` from the pinned helper was the control.

| Case | File bytes | SHA-256 | `read_fbx` indices | `mesh()` faces | consumed / raw poly | UV walk vs this file's UVIndex (always length 3) | helper `load_mesh` |
|---|---:|---|---|---|---|---|---|
| complete `[0,1,-3]` | 882 | `967bd294c256eea9356d1aee629b56919d6963da2c36f701d5717adadf60707b` | `[0,1,-3]` equal to input | `[[0,1,2]]` | 3 / 3 | 3 / 3 | returns the same one face |
| suffix only `[0,1]` | 878 | `d1dfb607b4074d69b2b6d28ad3453c9b656417a2959576aa2671c1df8d46ef23` | `[0,1]` equal to input | `[]` | 0 / 2 | 0 / 3 | `AuditError`: `incomplete polygon data: 2 trailing PolygonVertexIndex entries [0, 1] without a closing negative index` |
| closed plus unfinished `[0,1,-3,0,1]` | 890 | `2939986382ba3a7b2b2b078c9655a2f9f8e10887b9f7bcd028f5fe38b1aaf1bb` | equal to input | `[[0,1,2]]` | 3 / 5 | 3 / 3 (UV walk matches the fixed UVIndex; the two omitted polygon corners are invisible to that UV count) | `AuditError` with the same incomplete-polygon text, trailing `[0, 1]` |
| out-of-range `[0,1,-4]` | 882 | `27050098556db93c9a6dc6bd49c427ca9f4ed852d1765424e1b35ffad1750246` | equal to input | `[[0,1,3]]` | 3 / 3 | 3 / 3 | `AuditError`: `PolygonVertexIndex[2]=-4 names vertex 3 of 3` |

The decoder reproduced the raw index list on these four files. The assembler then dropped unclosed tails. The helper refused the two unclosed streams and the out-of-range closed face. On the unfinished binary, a UV check that only compares consumed UV corners with `len(UVIndex)` sees 3 == 3 while two polygon indices are already gone.

### Reported-by-reviewer / reported-by-experiment (not remeasured here)

Pytest was not run. The adopted tests at head `601bd72` state, as their own assertions: a synthetic complete pair `[0,1,-3]` exits 0 with `(source_faces, target_tris, accepted, over_limit) == (1, 1, 1, 0)`; `[0,1,-3,0,1]` on either side exits 2 with `incomplete polygon data` in stderr and writes no JSON; `[0,1,-4]` exits 2 with `names vertex 3 of 3`. The same strings were observed above by calling `load_mesh` directly; the CLI exit codes and the "no JSON written" claims were not re-executed.

`docs/experiments/hyp-603.md` on `148bab11` and the optional-audit section added on `601bd72` in `docs/experiments/tow02-hand-finish-face-diff.md` report 33,251 / 33,256 unchanged faces (99.985%), five residuals, and input hashes beginning `ff8994dc` and `2fd80081`. Those numbers were produced through `face_diff.mesh` (the hypothesis driver) or are restated from that report. This card did not open those FBX files and does not recompute them. The exit-2 sentence in that PR doc lists missing files, triangulation, n-gons, NaN/inf, output-path alias and input mutation. The helper source at `:156-160` also rejects an unclosed `PolygonVertexIndex`.

### Callers on main `148bab11`

Static search of `src/`, `tools/`, `experiments/` and `tests/` for `read_fbx`, `PolygonVertexIndex` and `face_diff`. Line numbers are this worktree, which matches `148bab11` for these files. "Full-consumption check" means an explicit consumed-corners == raw-corners test before numbers are produced.

| Caller | Call | Full-consumption check before numbers | Polygon omission | UV-corner inventory | Needs assets (not run) |
|---|---|---|---|---|---|
| `face_diff.mesh` `:67` | `read_fbx` | no | returns closed faces only (`:75-79`) | returns raw `UV` and `UVIndex` (`:81`) | no, for the synthetic double |
| `face_diff.main` `:138-139`, UV walk `:156-158` | `mesh` | no | inherits `mesh` | walk uses closed-face lengths; short `UVIndex` raises `IndexError`; excess `UVIndex` is unused while a centroid is kept | yes: default paths `V5`, `USER`, `ATLAS`, `OVL` at `:9-13` |
| `compare_readers.py:20` | `fd.mesh`, UV discarded | no | face count `raw_f` is the closed-face count | this call discards both UV arrays | yes: tmpdir with `v005.fbx`, `user05.fbx`, Blender dumps |
| `compare_readers.py:34` | `fd.main` | no | inherits `mesh` via `main` | inherits the `:156-158` walk | same tmpdir |
| `compare_readers.py:51-52` | replaces `fd.mesh` with Blender JSON, then `fd.main` | no (substituted reader) | Blender polygon list, not `PolygonVertexIndex` | `bl_mesh` builds `UVIndex` as `range(len(uv)//2)` (`:46`) | same tmpdir |
| `part_truth.py:19` | `fd.mesh`, UV discarded | no | centroids and the confusion matrix use the closed-face list (`:23-35`) | this call does not read `UVIndex` | yes: `bl_parts.json`, `v005.fbx`, `out_raw/*.tsv` |
| `hyp-603/run.py:70-71` | `fd.mesh`, UV discarded | no | accepted-face counts are counts of closed faces | this call does not read `UVIndex` | yes: the two TOW02 FBX paths and the SHA-256 constants at `:11-12` |
| `audit_correspondence.load_mesh` (not on `148bab11`; head `601bd72:131-160`) | `fd.read_fbx` plus its own loop | yes (`:156-160`), and vertex ids must exist (`:152`) | unclosed tail raises `AuditError` | UV nodes are unread | synthetic binary measured above; real TOW02 test in the PR file is asset-gated and was not run |

`compare_readers.py:52` is a different reader substituted under the name `mesh`. It is listed so the `fd.main` call is not mistaken for a second historical-decoder path.

`experiments/max-headless-agr-roundtrip/offline.py:11` is another `read_fbx`, found by the same search, and it is not a caller of `face_diff.read_fbx`. Its polygon loop (`:101-107`) also keeps a polygon only after a negative index, and the function never reads `UVIndex`. Callers: `analyze.py:70` and `test_experiment.py:32`, `:39`, `:54`. The real-file test skips without native benches. Those paths were not run. `offline.py` states it is not a delivery validator.

`tests/` on `148bab11` has no `face_diff` import. The PR test module calls the helper CLI. It does not call `face_diff.mesh`.

### Production verdict paths

Unexposed.

- `src/` and `tools/` have no import of `face_diff`, `audit_correspondence` or `PolygonVertexIndex`.
- BODY-F / BODY-N triangle counts are V003 via `src/twinqa/scene.py:scene_findings`, and `scene.py:59` reads a Blender readback (`tools/blender/fbx_readback.py`). `docs/domain/areas/body.md` rows BODY-F and BODY-N name that readback.
- `src/twinqa/fbx_header.py:fbx_units` walks to `UnitScaleFactor`. Array properties are skipped (`:87-92` stores `None`).
- `src/dt_ai/validate/bundle.py:138-139` checks the Kaydara magic and version 7400, then a Blender audit.
- `src/dt_ai/ops/inv_xview.py:566` `mesh_report` takes vertices and faces that the caller already built.
- `delivery_passed` in `src/dt_ai/core/adapter_report.py:28` and `src/dt_ai/cli/main.py:272` is the constant `False` on those reports. `hyp-603/run.py:96` and the #609 helper write `delivery_passed: false` in their own JSON. Neither value is job state or a delivery gate fed by this decoder.

## How it applies to this repository

The omission sits in the research reader `experiments/tow02-hand-finish-face-diff/face_diff.py`, which `experiments/tow02-hand-finish-face-diff/compare_readers.py`, `experiments/tow02-hand-finish-face-diff/part_truth.py` and `experiments/hyp-603/run.py` call through `mesh()`. After #609, `experiments/tow02-hand-finish-face-diff/audit_correspondence.py` is the one consumer of `read_fbx` that rejects an unclosed stream, and it is still an optional research helper (`delivery_passed` stays false). A UV length mismatch is invisible to that helper and to the three callers that discard the UV pair. It becomes an `IndexError` or a silent leftover only in `face_diff.main`.

Published TOW02 face counts in `docs/research/tow02-hand-finish-face-diff.md` and `docs/experiments/hyp-603.md` are counts of faces `mesh()` returned. This card does not change those files or those numbers.

## Proposed next tasks

### 1. Fail closed in `face_diff.mesh` when polygon corners are left over

Add one check inside `face_diff.mesh`, before the return, so `main`, `compare_readers.py:20`, `part_truth.py:19` and `hyp-603/run.py:70-71` all stop on the same condition. Leave `audit_correspondence.load_mesh` as it is on `601bd72`. Malformed synthetic input `PolygonVertexIndex = [0,1,-3,0,1]` with the three vertices above must raise a diagnostic that names the two trailing entries `[0, 1]` and must not return a one-face mesh. Clean pair `PolygonVertexIndex = [0,1,-3]` and `UVIndex = [0,1,2]` must still return vertices 3, faces `[[0,1,2]]`, `UV` length 6, `UVIndex` length 3, consumed corners 3. Value: research face counts stop treating an unclosed tail as a smaller mesh. Effort: S.

Archive: no roadmap link

### 2. Require the UV walk in `face_diff.main` to consume `UVIndex` exactly

After the closed-face walk at `face_diff.py:156-158`, require `consumed UV corners == len(UVIndex)` and require every `UVIndex` value to address a pair inside `UV`, and write no `summary.json` otherwise. Malformed synthetic input: complete `[0,1,-3]` with `UVIndex = [0,1,2,0,1]` must report that 5 UV corners were supplied for 3 polygon corners, and must not keep the centroid. The short pair `UVIndex = [0,1]` must report length 2 against 3 corners (today that walk raises `IndexError: list index out of range`, which is not that diagnostic). Clean pair: `[0,1,-3]` with `UVIndex = [0,1,2]` must still yield centroid `(1/3, 1/3)` and consumed 3 / 3. This check sees case f, which the polygon check accepts. It does not replace task 1: on the #609 writer's unfinished file, `UVIndex` stays length 3 while the raw polygon list has length 5, so a UV-only comparison against the closed face still sees 3 == 3. Value: part labels in the historical driver stop being emitted from a partial UV inventory. Effort: S.

Archive: no roadmap link

## Open questions for the user

1. The two real TOW02 FBX paths in `face_diff.py:9-11` were not opened. A later card could hash them and report whether each `PolygonVertexIndex` is fully closed, without rewriting `docs/research/tow02-hand-finish-face-diff.md`.
2. `experiments/max-headless-agr-roundtrip/offline.py` drops an unclosed tail in its own reader and never sees `UVIndex`. Say if that reader should get its own bounded card; it is outside the two tasks above.
3. The exit-2 sentence added on `601bd72` in `docs/experiments/tow02-hand-finish-face-diff.md` does not name the incomplete-polygon `AuditError` that `load_mesh` raises. Say if that sentence should be corrected when #609 merges.

`delivery_passed=false`
