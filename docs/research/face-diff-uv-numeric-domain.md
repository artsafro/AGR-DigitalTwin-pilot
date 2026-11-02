# Face diff: non-finite UVs and ordinary part labels

Pinned source: PR #616 head `cfe6fa55d7334d58627d674d0293d18a5dc1ea2d` (short `cfe6fa55`), read-only tree `C:/x/t_97fb6446/src616`. The driver records that #616 is unmerged. The worktree pin from `C:/x/t_97fb6446/sha.txt` is `acdbec25649a1f059f40f4a44800f7939254a514`. `git rev-parse` was not run. `delivery_passed=false`. Historical TOW02 face counts were not recomputed and the report files that publish them were not edited.

## Summary

A complete in-range UV inventory on `cfe6fa55` still finishes as an ordinary part label when a referenced component is NaN, +inf or -inf, when finite `1e308` values overflow the centroid sum, or when finite centroid `1e307` overflows `u * size`. `check_uv` returns `None`. `main` writes all four artifacts and raises nothing. At z = 0 (below `Z_TOP` 64.7) the TSV row is `0	body	unchanged	0.0000	0.3333	0.3333	0.0000`; stdout is only the status counter `{"unchanged": 1, "unchanged_tri": 1}`.
The same `body` row is what finite out-of-swatch UVs write, including `(2, 2)`. The in-swatch control writes `fins`. An unreferenced `(NaN, NaN)` pair stays `fins`; those doubles survive FBX 7400 type `d` and the centroid walk never reads them.
Observers of the label are `main`'s files, `compare_readers.py` (calls `main`) and `part_truth.py` (reads the TSV). `hyp-603/run.py` and the worktree helper `audit_correspondence.load_mesh` keep vertices and polygons and emit no such label. No `src/` or `tools/` importer was found. Real TOW02 files were not opened. `delivery_passed=false`.

## Findings

Evidence labels: **Verified by run** = CPython 3.14.7, `uv run python C:/x/t_97fb6446/probe_uv_numeric.py`, results `C:/x/t_97fb6446/probe_results.json`. **Source** = read from the pinned file, not executed as a separate failing case. Pytest was not run.

### Pins and how the worktree copy differs

**Verified by run.** `inspect.getsource` on the two `face_diff.py` files: `classify` text is equal, `read_fbx` text is equal, `mesh` text is not equal, `check_uv` exists only on `cfe6fa55`. The #616 `mesh` raises `ValueError` on an unclosed `PolygonVertexIndex` tail (`face_diff.py:81-84`). The worktree `mesh` (`face_diff.py:76-81` at `acdbec25`) returns after the closing-index loop. Every triangle in this probe is the closed index list `[0, 1, -3]`, so both `main` functions ran to completion. The worktree has no `check_uv`, and its `main` still wrote the same part string and the same four filenames for all 13 inventories below.

Line numbers below are the #616 file unless a worktree path is named. Worktree counterparts of the same `classify` body are `face_diff.py:112-133`; the centroid walk is `face_diff.py:157-162`; the writes are `face_diff.py:224-234`.

### Frozen fixture

**Verified by run.** One triangle, vertices `(0,0,0), (1,0,0), (0,1,0)`, polygon `[0, 1, 2]` from FBX indices `[0, 1, -3]`. Geometry centroid `(1/3, 1/3, 0)`. `Z_TOP` is 64.7 (`face_diff.py:15`). Atlas, literal:

```json
{"size": 100, "swatches": {"fin_a": {"rect": [20, 50, 30, 30]}}, "strips": []}
```

In-swatch UV `[0, 0, 1, 0, 0, 1]`, `UVIndex` `[0, 1, 2]`. Independent centroid `(1/3, 1/3)`, pixel `(100/3, 200/3)` ≈ `(33.333, 66.667)`, inside `fin_a` under the `±1` px pad. Target mesh is the same triangle with that finite UV. Overlap file: one pair `{"a": 0, "b": 0, "group": "g"}`. Two orchestrations per case on `cfe6fa55`: an in-memory node-tree double installed in place of `read_fbx`, and a real `read_fbx`/`mesh` on a synthetic FBX 7400 binary whose UV array type is `d` (IEEE double, encoding 0). The 13 worktree runs used the double only. Binary and double agreed on `check_uv`, the direct `classify` label, the TSV row, the summary part key, stdout, and the decoded finiteness flags. SHA-256 of the source FBX, target FBX, atlas JSON and overlap JSON was unchanged after every `main`. The in-memory tree snapshot was unchanged. No case raised.

`check_uv` (`face_diff.py:141-153`) checks a non-empty polygon list, an even UV length, `len(UVIndex) ==` corner count, and `0 <= index < len(UV)//2`. It does not read the float values. The centroid (`face_diff.py:178-179`) is the mean of the referenced pairs. `classify` (`face_diff.py:117-138`) sets `x = u * size` and `y = (1 - v) * size`, tests swatch rectangles, and on a miss returns `body` when `z < Z_TOP`. This atlas has an empty `strips` list, so the measured `body` rows are that miss return. The `z >= Z_TOP` arm of the same return, which yields the string `TOW02_top`, was not executed.

### Matrix

**Verified by run.** "Raw" is the three referenced `(u, v)` pairs. "Centroid" and "pixel" are the derived pair. `check_uv` is `pass` when the function returns `None`. Part is both the direct `classify(..., z=0, atlas)` result and the TSV / summary / overlap part. Files means all four artifacts were created. Exception means `main` raised.

| Case | Raw referenced | Centroid finite | Pixel finite | check_uv | Part | Files | Exception |
|---|---|---|---|---|---|---|---|
| control_in_swatch `[0,0, 1,0, 0,1]` | finite | yes, yes | yes `(33.333, 66.667)` | pass | `fins` | yes | none |
| nan_u `[NaN,0, 1,0, 0,1]` | u0 NaN | no, yes | no, yes | pass | `body` | yes | none |
| nan_v `[0,NaN, 1,0, 0,1]` | v0 NaN | yes, no | yes, no | pass | `body` | yes | none |
| posinf_u | u0 +inf | no, yes | no, yes | pass | `body` | yes | none |
| posinf_v | v0 +inf | yes, no | yes, no | pass | `body` | yes | none |
| neginf_u | u0 -inf | no, yes | no, yes | pass | `body` | yes | none |
| neginf_v | v0 -inf | yes, no | yes, no | pass | `body` | yes | none |
| unreferenced_nan_pair: control plus a 4th pair `(NaN, NaN)`, index still `[0,1,2]` | finite | yes `(1/3, 1/3)` | yes | pass | `fins` | yes | none |
| sum_overflow_u: u = `1e308` three times, v = `[0,0,1]` | finite (`1e308` itself is finite) | no, yes | no, yes | pass | `body` | yes | none |
| sum_overflow_v: v = `1e308` three times, u = `[0,1,0]` | finite | yes, no | yes, no | pass | `body` | yes | none |
| mul_overflow_u: u = `1e307` three times, v = `[0,0,1]`, size 100 | finite | yes (`1e307`), yes | no, yes | pass | `body` | yes | none |
| out_of_swatch_finite_unit: six zeros | finite | yes `(0, 0)` | yes `(0, 100)` | pass | `body` | yes | none |
| out_of_swatch_finite_outside_unit: six `2.0` | finite | yes `(2, 2)` | yes `(200, -100)` | pass | `body` | yes | none |

Arithmetic precondition, same interpreter: `1e308 + 1e308 + 1e308` is non-finite; `(1e307 + 1e307 + 1e307) / 3` is finite; that quotient times `100` is non-finite. For `nan_v` and `posinf_v` the finite pixel x ≈ 33.333 lies in the `fin_a` x-interval, and the label is still `body` because the y comparison fails. Summary key is `part:fins` or `part:body` with `{"unchanged": 1, "unchanged_tri": 1}`. `ovl_pairs_status.json` has two rows (pair sides `a` and `b`), both `part` equal to that label, `status` `unchanged`, `z` 0.0. `added_user_tris.tsv` is the header only. Stdout is the same status object for `fins` and for `body`.

The TSV columns `x,y,z` are the geometry centroid (`face_diff.py:249-250` on #616). They stay `0.3333, 0.3333, 0.0000` for every case, including the non-finite UV cases. The non-finite values are absent from the written JSON and TSV.

### Decoder

**Verified by run.** For every binary case, `mesh()` on the synthetic file returned 3 vertices, polygon `[[0, 1, 2]]`, and UV finiteness flags equal to the flags that were packed, including NaN, +inf, -inf, `1e308` and `1e307`. The unreferenced NaN pair was present in the decoded UV array (length 8) and the index list was `[0, 1, 2]`. Version word at offset 23 is 7400, so `read_fbx` uses the 32-bit node header (`face_diff.py:21`, `face_diff.py:36`). The UV property type byte is `d`.

### Who can observe the label

**Verified by run** for `main` itself. **Source** for the other callers (they were not executed; `compare_readers.py` and `hyp-603/run.py` name the real TOW02 paths).

| Caller on `cfe6fa55` | What it does with UV | Can it show this part label? |
|---|---|---|
| `face_diff.main` | `check_uv` on the source (`:159`), centroid (`:178-179`), `classify` (`:183`), writes (`:245-255`). Target UV is unpacked away (`:160`, `_, _`). | Yes. The part is in `summary.json` (`part:*`), `faces_v005.tsv` and `ovl_pairs_status.json`. Stdout is the status counter only. |
| `compare_readers.py:34` and `:52` | Calls `fd.main`. An earlier mesh call at `:20` discards UV (`_, _`) for the reader-diff report. | Yes, because it calls `main`, which writes the four files. |
| `part_truth.py:19` | `fd.mesh` discards UV. `:37-41` reads `faces_v005.tsv` column `part` and prints a confusion count. | It prints a label `main` already wrote. It does not recompute a centroid. |
| `experiments/hyp-603/run.py:70-71` | `fd.mesh` discards UV. `replay` (`:25-51`) records geometry matches and calls neither `classify` nor `main`. | No part label. |
| `tests/test_face_diff_stream_completeness.py` | Loads `face_diff.py` and drives `mesh` / `main`. The module docstring and the parametrized cases name polygon tails, UVIndex lengths and index range. The file contains no `nan`, `inf`, `1e308` or `1e307` literal. | Not run here. **Source:** the locked acceptance is length and index range. |

**Source, worktree `acdbec25`.** `experiments/tow02-hand-finish-face-diff/audit_correspondence.py` is the corner-audit helper. `load_mesh` (`:125-161`) reads `Vertices` and `PolygonVertexIndex` and returns `verts, polys`. It has no `LayerElementUV` read. `_points` (`:34`) rejects a non-finite vertex coordinate; that predicate is on geometry corners. The #616 tree has no `audit_correspondence.py`. A static search of `src/` and `tools/` on both trees found no `import face_diff` and no path reference to `tow02-hand-finish-face-diff`.

This card did not open the hardcoded paths at `face_diff.py:9-13` and does not say whether those files contain a non-finite UV. It does not rerun the polygon-stream inventory.

### Domain sheets

**Source.** There is no `docs/domain/areas/` file for face-diff. `docs/domain/areas/uv-atlas.md` indexes delivery UV rules (texture-set counts, UDIM, padding, glass tile). `docs/domain/areas/body.md` indexes OKS shell requirements. Neither sheet defines this swatch rectangle test or a finite-UV predicate for `face_diff.classify`. The strings `body`, `fins` and `TOW02_top` in this script are research part labels. `docs/PROJECT_STATE.md` in this worktree does not state a numeric-UV rule for this script.

The #616 test docstring (**source**, not run) says a malformed `main` writes nothing into a fresh output directory. The writes in `main` sit after `check_uv`. This probe did not re-execute a short `UVIndex`, so the empty-directory claim for a future `ValueError` is source structure, not a measurement from this run. Every numeric case in this run completed and wrote files.

## How it applies to this repository

- Label path, probed: `C:/x/t_97fb6446/src616/experiments/tow02-hand-finish-face-diff/face_diff.py` (`check_uv` `:141-153`, call `:159`, centroid `:178-179`, `classify` `:117-138` and `:183`, writes `:245-255`).
- Same label function on the worktree pin: `experiments/tow02-hand-finish-face-diff/face_diff.py:112-133` and `:157-162`, writes `:224-234`. No `check_uv`. `mesh` lacks the unclosed-tail `ValueError`.
- Callers that can persist or reprint the label: `experiments/tow02-hand-finish-face-diff/compare_readers.py`, `experiments/tow02-hand-finish-face-diff/part_truth.py`.
- UV-discarding corner path: `experiments/hyp-603/run.py:70-71` on the #616 tree; `experiments/tow02-hand-finish-face-diff/audit_correspondence.py:125-161` on the worktree only.
- Domain index that does not govern this predicate: `docs/domain/areas/uv-atlas.md`, `docs/domain/areas/body.md`.

## Reproduction

Probe and raw JSON stay outside the repo: `C:/x/t_97fb6446/probe_uv_numeric.py`, `C:/x/t_97fb6446/probe_results.json`. The snippet below is the double path plus one binary round-trip. It points `V5`, `USER`, `ATLAS` and `OVL` at temporary files before `main`, so the hardcoded asset paths are not opened.

```python
import hashlib, importlib.util, json, math, os, struct, sys

FD = r"C:\x\t_97fb6446\src616\experiments\tow02-hand-finish-face-diff\face_diff.py"
spec = importlib.util.spec_from_file_location("face_diff_probe", FD)
fd = importlib.util.module_from_spec(spec); spec.loader.exec_module(fd)

ATLAS = {"size": 100, "swatches": {"fin_a": {"rect": [20, 50, 30, 30]}}, "strips": []}
CTRL = [0.0, 0.0, 1.0, 0.0, 0.0, 1.0]
VERTS = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
PVI = [0, 1, -3]
NAN = float("nan")

def tree(uv, uvi=(0, 1, 2)):
    geo = ("Geometry", [10, "Geometry::g\x00\x01Geometry", "Mesh"], [
        ("Vertices", [list(VERTS)], []),
        ("PolygonVertexIndex", [list(PVI)], []),
        ("LayerElementUV", [0], [("UV", [list(uv)], []), ("UVIndex", [list(uvi)], [])]),
    ])
    model = ("Model", [20, "SM_Vyatskaya_Vl_47_49_013_Main\x00\x01Model", "Mesh"], [])
    return [("Objects", [], [geo, model]), ("Connections", [], [("C", ["OO", 10, 20], [])])]

def run_double(uv, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    src, tgt = tree(uv), tree(CTRL)
    snap = json.dumps(src, default=str)
    paths = {k: os.path.join(out_dir, k) for k in ("src.fbx", "tgt.fbx", "atlas.json", "ovl.json")}
    open(paths["src.fbx"], "wb").write(b"unread-double")
    open(paths["tgt.fbx"], "wb").write(b"unread-double")
    open(paths["atlas.json"], "w", encoding="utf-8").write(json.dumps(ATLAS))
    open(paths["ovl.json"], "w", encoding="utf-8").write(json.dumps({"pairs": [{"a": 0, "b": 0, "group": "g"}]}))
    before = {k: hashlib.sha256(open(p, "rb").read()).hexdigest() for k, p in paths.items()}
    fd.read_fbx = lambda path: src if path == paths["src.fbx"] else tgt
    fd.V5, fd.USER = paths["src.fbx"], paths["tgt.fbx"]
    fd.ATLAS, fd.OVL = paths["atlas.json"], paths["ovl.json"]
    v, p, duv, duvi = fd.mesh(fd.V5, fd.OBJ)
    fd.check_uv(fd.V5, p, duv, duvi)  # returns None for every inventory in the matrix
    n = 3
    uvc = (sum(uv[2 * duvi[i]] for i in range(n)) / n, sum(uv[2 * duvi[i] + 1] for i in range(n)) / n)
    print("classify", fd.classify(uvc, 0.0, ATLAS), "centroid_finite", all(math.isfinite(x) for x in uvc))
    sub = os.path.join(out_dir, "out"); os.makedirs(sub, exist_ok=True)
    fd.main(sub)
    after = {k: hashlib.sha256(open(p, "rb").read()).hexdigest() for k, p in paths.items()}
    assert before == after and json.dumps(src, default=str) == snap
    print(open(os.path.join(sub, "faces_v005.tsv"), encoding="utf-8").read())

# run_double(CTRL, r"C:\x\t_97fb6446\repro-control")                 # part fins
# run_double([NAN, 0.0, 1.0, 0.0, 0.0, 1.0], r"C:\x\t_97fb6446\repro-nan-u")  # part body, no exception
# run_double([1e307, 0.0, 1e307, 0.0, 1e307, 1.0], r"C:\x\t_97fb6446\repro-mul")  # centroid finite, pixel x non-finite, part body

def p_str(s):
    b = s.encode("utf-8"); return b"S" + struct.pack("<I", len(b)) + b
def p_i64(v):
    return b"L" + struct.pack("<q", v)
def p_i32(v):
    return b"I" + struct.pack("<i", v)
def p_arr(code, fmt, values):
    raw = struct.pack("<" + fmt * len(values), *values)
    return bytes([ord(code)]) + struct.pack("<III", len(values), 0, len(raw)) + raw
def encode_node(start, name, props, children):
    name_b = name.encode("ascii"); props_blob = b"".join(props)
    cursor = start + 13 + len(name_b) + len(props_blob)
    blobs = []
    for cn, cp, cc in children:
        blob, cursor = encode_node(cursor, cn, cp, cc); blobs.append(blob)
    end = cursor + 13
    blob = struct.pack("<III", end, len(props), len(props_blob)) + bytes([len(name_b)]) + name_b + props_blob + b"".join(blobs) + b"\x00" * 13
    return blob, end
def fbx_bytes(uv, uvi=(0, 1, 2)):
    header = b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", 7400)
    geo = ("Geometry", [p_i64(10), p_str("Geometry::g\x00\x01Geometry"), p_str("Mesh")], [
        ("Vertices", [p_arr("d", "d", VERTS)], []),
        ("PolygonVertexIndex", [p_arr("i", "i", PVI)], []),
        ("LayerElementUV", [p_i32(0)], [
            ("UV", [p_arr("d", "d", uv)], []),
            ("UVIndex", [p_arr("i", "i", list(uvi))], []),
        ]),
    ])
    model = ("Model", [p_i64(20), p_str("SM_Vyatskaya_Vl_47_49_013_Main\x00\x01Model"), p_str("Mesh")], [])
    conn = ("Connections", [], [("C", [p_str("OO"), p_i64(10), p_i64(20)], [])])
    pos, blobs = 27, []
    for node in (("Objects", [], [geo, model]), conn):
        blob, pos = encode_node(pos, *node); blobs.append(blob)
    return header + b"".join(blobs) + struct.pack("<III", 0, 0, 0) + b"\x00" + b"\x00" * 400

# Binary witness (NaN survives type 'd'): write fbx_bytes([NAN, 0.0, 1.0, 0.0, 0.0, 1.0]) and call fd.mesh
# without replacing read_fbx. Measured decoded flags: nan, finite, finite, finite, finite, finite.
```

## Proposed next tasks

### 1. Reject a non-finite referenced UV component before `main` writes a part

Scope: extend `check_uv` so each UV pair named by `UVIndex` has finite components, and raise `ValueError` before the centroid walk. Witnesses, same triangle, atlas and z = 0 as above: UV `[NaN, 0, 1, 0, 0, 1]`, `[0, NaN, 1, 0, 0, 1]`, and the four `+inf`/`-inf` substitutions of that single component, must raise and leave a fresh output directory empty. Control UV `[0, 0, 1, 0, 0, 1]` must still write part `fins`, status `unchanged`. Finite miss controls `[0,0,0,0,0,0]` and `[2,2,2,2,2,2]` must still write part `body` and the four files. Three finite `1e308` or `1e307` components stay out of this task. Value: a NaN or infinity in a corner that the label actually reads can no longer be stored as ordinary `body`. Effort: S. Advances #425

### 2. Reject a non-finite centroid or pixel coordinate after the sums and the atlas multiply

Scope: after the sums at the centroid walk and the products `u * size` and `(1 - v) * size`, raise `ValueError` and write no part file when the centroid or either pixel coordinate is non-finite. Witness sum overflow: UV `[1e308, 0, 1e308, 0, 1e308, 1]` (each raw component finite, the u sum non-finite) must raise and leave the output directory empty. Witness multiply overflow: UV `[1e307, 0, 1e307, 0, 1e307, 1]` with atlas size 100 (centroid u = `1e307` finite, `1e307 * 100` non-finite) must raise and leave the output directory empty. The in-swatch control must still write `fins`. The two finite miss controls must still write `body`. This task does not change swatch rectangles, does not clamp, and does not treat a finite coordinate outside 0–1 as an error. Value: ordinary `body` stops covering derived overflow of values that are finite in the file. Effort: S. Advances #425

## Open questions for the user

1. The unreferenced `(NaN, NaN)` pair kept the in-swatch label `fins`. Should a later check reject any non-finite float in the UV array, or only pairs that `UVIndex` names?
2. Finite UV `(0, 0)` and finite UV `(2, 2)` both write ordinary `body`. Confirm that a follow-up must keep those two results, including coordinates outside the unit square, as written labels.
3. The real paths in `face_diff.py:9-13` were not opened. Should a later card report only whether any referenced UV component in those two files is non-finite, without rewriting the published TOW02 counts?
