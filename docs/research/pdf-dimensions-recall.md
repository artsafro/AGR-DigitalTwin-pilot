# PDF dimension recall and tool study (#1302)

## Result and limits

Native AutoCAD plots from #1290, physical PDF page 1, copies only; no DCC launch,
source save, guessed calibration, model build, full-corpus run or dependency change.
The accepted **measured-ceiling alternative** is used for L03, not a claim of 60% recall.
All output still has `passed=false`, unknown scale and null `measured_mm`.

| Sheet | Before correct / truth | After correct / truth | Before / after precision | Ceiling/blocker |
|---|---:|---:|---:|---|
| KPP1 L03 | 7/82 (0.0854) | 7/82 (0.0854) | 7/7 / 7/7 (1.0) | Only seven source dimensions currently have provable semantic endpoints; 75 have no source-axis pair |
| KNS V1 section | 4/12 (0.3333) | 8/12 (0.6667) | 4/4 / 8/8 (1.0) | Four new level-pair bindings; short displaced labels and an unnamed level endpoint remain |
| KNS V1 floor plan (additional) | 0/6 (0.0) | 0/6 (0.0) | unknown / unknown | All six DIMENSION directions are non-cardinal: 339.0761 or 69.0761 degrees |

These are **semantic bindings, not calibrated geometry or customer approval**.
L03's ceiling is the current endpoint-identity contract, not an intrinsic information
limit of PDF. Recovering interior wall-face identities needs a separate proven source
graph; selecting the nearest wall or promoting a raw tick span would invent identity.
Even perfect text/line recovery cannot supply that missing proof. No denominator is
reduced to the seven convenient inter-axis dimensions.

## Complete miss accounting

[Per-handle before/after CSV](../../tools/research/pdf_album/dimension-recall-results/miss-classes.csv)
has every one of the 82 + 12 native modelspace DIMENSION handles, including successes.
[Summary](../../tools/research/pdf_album/dimension-recall-results/summary.json) binds
metrics to the source hashes and evaluator-only registration. Classes are mutually
exclusive **first blocking causes**, not overlapping symptom counts.

| Primary class | L03 before | L03 after | KNS before | KNS after |
|---|---:|---:|---:|---:|
| Text not found | 0 | 0 | 0 | 0 |
| Text found but not bound to its own tick span (displaced/short labels) | 36 | 36 | 3 | 3 |
| Line split into strokes under inline text | 0 | 0 | 5 | 0 |
| Unsupported arrow/tick type as first blocker | 0 | 0 | 0 | 0 |
| Rotated/stacked text as first blocker | 0 | 0 | 0 | 0 |
| Override/display rounding disagrees with native measurement | 3 | 3 | 0 | 0 |
| Extension-line gaps as first blocker | 0 | 0 | 0 | 0 |
| Filtered by fail-closed endpoint-identity rule, own span recovered | 36 | 36 | 0 | 1 |
| **Missed** | **75** | **75** | **8** | **4** |
| Correct semantic binding | 7 | 7 | 4 | 8 |
| **All native dimensions** | **82** | **82** | **12** | **12** |

- All **94/94 native displayed labels** exist in the PyMuPDF text layer at their
  source-registered positions. Native dimension-block MTEXT, not a guessed numeric
  token elsewhere, provides displayed text. A unique exact text within 3 pt of the
  projected native text midpoint locates each label, including repeated `120`/`200`.
- L03's 36 text/span misses: `120` x19, `100` x8, `200` x4, `540` x2,
  `420`, `260`, `1500` x1. The native render visibly places short labels outside
  their tiny spans. Do not associate them with a neighbouring chain by proximity.
  Twelve are rotated; the other 24 are horizontal. Rotation alone is not the cause.
- L03 `1C66`, `1C9E`, `23BE`: native 2355/4715/1515 mm becomes
  2360/4720/1520. `text` override is absent, `DIMRND=10`, `DIMDEC=0` in
  all three. The mismatch remains explicit; no rounded value becomes ground truth.
- L03's other 36 have the right text **and** their own native tick span, but no
  proven pair of axes/opening edges/level lines. Sixteen are rotated, 20 horizontal.
- KNS inline misses `3418/3419/341B/341D/341F` are all rotated text: native CAD
  knocks out the line beneath the label. Restoring those five paper spans gives
  four independently source-matched level pairs: 600, 4520, 7650, 4700.
  `341F` (680) still has no two named level endpoints. Short displaced
  `341A/341C/341E` (200/250/200) remain unresolved, not attached to nearby text.
- The extra plan's six native handles and all hashes are in
  [third-sheet.json](../../tools/research/pdf_album/dimension-recall-results/third-sheet.json).
  Its zero recall is measured, not omitted in favour of another easier sheet.

### Scoring boundary (important)

The unchanged #1290 `binding_2b_eval.py` only credits **axis_pair**. It cannot score
new **level_pair** results and would label the four correct KNS additions as wrong.
The table above uses a separate, explicitly named **source-location comparator**:
integer-mm difference strictly <0.5 mm, both projected source extension ends and
native dimension-line coordinate strictly <0.5 pt, and one-to-one native handles.
It counts **every positive prediction**, including unsupported/duplicate/wrong ones.
L03 stays identical to historical scoring. KNS positive identities are four original
axis pairs and four new level pairs; no raw/unbound line is scored as a positive.

Registration is **evaluator-only**: L03 uses native source grid coordinates and their
plotted positions; KNS uses its native horizontal source grids plus the observed
3414 dimension-line y=785.7 pt. Uniform native plotting maps `(x,y)` to
`(s*x+ox, -s*y+oy)`; the exact coefficients are in summary.json. This is not supplied
to `bind_album`, is not derived from a written dimension value and never calibrates
production output. Three-point label-location search tolerance is not the tighter
endpoint scoring tolerance. These agent-made source registrations are not expert approval.

## Minimal production fix

`binding._chains` can join an interruption only when **one** parallel numeric text
box crosses the line and explains **both** retained stroke ends. Ink/knockout mismatch
must be strictly below 1/8 em, capped at 1 pt; exact boundaries, nonfinite evidence,
non-numeric or ambiguous labels and unexplained gaps refuse. It does not extrapolate
to displaced labels or change semantic binding/calibration rules.

Tests-first commit `39a317d9`: synthetic horizontal and rotated inline cases plus
real hash-bound KNS replay **3 failed / 2 passed**. First implementation recovered four
spans but missed 7650 because its CAD knockout differs from the font bbox by 0.60 pt;
the font-relative bounded repair recovers it. The initial real fixture also expected
all five spans to remain unbound; source inspection proved four valid level pairs,
so the corrected test asserts their values and exact positive count, not that false
expectation. Final focused and full-suite numbers are in the PR, tied to its head.

The generated seed1302 probe varies nested-PDF scale/orientation on 40 synthetic
pages: labels/spans are retained, no wrong axis labels, no guessed scale and never
`passed=true`. At large paper separations the existing view partition can refuse
axis identity; that is not converted into success. A separate hostile replay checks
19 controls including exact new gap limits, NaN/inf, duplicates, aliases, second
writer, captured-input snapshot and pre-existing `.partial` preservation.

## Tools: observed fit, licence, decision

Read-only snapshots, hashes, raw library receipts and commands are sealed with evidence.
No neural model/framework/weights or new project dependencies were installed.

| Tool | Verdict | Licence | Evidence and fit |
|---|---|---|---|
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) 1.28.2 | **use** (existing optional reader) | AGPL-3.0 / commercial dual licensing; existing project dependency, not a new licence clearance | Current reader uses `get_drawings()` and text dicts, not `get_texttrace`. Inline-gap fix needs existing primitives, not a new reader. `get_texttrace` exposes per-glyph origins/bboxes, `dir`, `wmode`, bidi, rendering type, opacity, layer, `seqno`; useful for fragmented/rotated text and hidden/overpainted evidence. Extended drawings expose clipping/group hierarchy, and sequence numbers can relate strokes to text. Those visibility/grouping checks are future work, not implemented here. |
| [pdfplumber](https://github.com/jsvine/pdfplumber) 0.11.10 | **cross-check only** | MIT ([licence](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt)) | Independent pdfminer reader: exact label text + centre difference <1 pt agrees **82/82 L03 and 12/12 KNS (100% each)**, one-to-one. Largest delta 0.2166 / 0.0758 pt. Default rotated order reverses 4520→0254; use `line_dir_rotated='ltr', char_dir_rotated='btt'`. Text/coordinate agreement is not semantic correctness. |
| [OpenCV](https://github.com/opencv/opencv) 5.0.0 | **raster only** | Apache-2.0 ([licence](https://github.com/opencv/opencv/blob/4.x/LICENSE)) | Measured Canny/HoughP and LSD on five actually image-backed #1274 pages below. Produces line/tick **proposals**, not text, endpoint identity or scale. Vector oracle pages were not rasterized to manufacture recall. No raster tick oracle exists here: tick precision/recall is explicitly unknown. |
| [CubiCasa5K](https://github.com/CubiCasa/CubiCasa5k) | **ideas only** | **CC BY-NC 4.0**, confirmed by LICENSE; GitHub's “Other” is not permission | Residential raster floor plans/room and icon labels, not vector GOST dimensions, sections, facades or site plans. Borrow multi-task topology/room-junction evaluation ideas, not code/data/weights for a commercial workflow. No install or training. |
| Floorplan Auto-Labeler / [current author repository: floor-plan-tracer](https://github.com/yapicialiekrem/floor-plan-tracer) | **ideas only** | **PolyForm Noncommercial 1.0.0** code; derived docs CC BY-NC 4.0; third-party scans not relicensed | The requested `Floorplan-Auto-Labeler` path returns 404; author repository discovery finds this current floor-plan project, not proof of historical rename. README: scanned plans + world-file affine, U-Net++/EfficientNet-B3, eight classes, geometric regularization, reviewable GeoJSON; Turkish OCR dependency. Raster wall/opening domain is adjacent, but pretrained data/weights are not shipped and GOST vector dimension binding is not its evaluated task. Borrow explicit affine provenance, boundary/instance metrics and human-review separation. |
| [OpenLintel](https://github.com/sohampawar1866/openlintel) | **skip** for recall; ideas only for UI/audit architecture | **AGPL-3.0-or-later**, LICENSE (README badge is less precise) | Interior photo/design/BOM platform and advertised AI/VLM digitization, not source-DWG dimension-oracle validation. No evidence of GOST facade/section/site recall or fail-closed metric calibration in the inspected README. Borrow staged provenance/review concepts only; model/API claims are not measured performance. No install or API call. |

Primary-source repository snapshots: CubiCasa `c34440266665a11f4484eb06cd2e4b7d72ad76c1`,
tracer `2776f181ca882b78ccd4cff52c7a3f41e8cfc679`,
OpenLintel `e1184b9a7c63da355e290586565dba1e4df132a3`.
Official PyMuPDF docs HTML returned HTTP403; fallback read the project's own
`docs/page.rst` and `docs/functions.rst` on GitHub (observed main
`67fe11524c2ce7f6662a36f18c5345936964d96c`) and checked runtime keys on both sheets:
405/56 trace spans, 6256/26644 extended drawing records, types `clip/fs/s`.

### Bounded raster inventory probe (not a corpus parse)

#1274 CSV SHA256 `0812da67891ebf93c7623d89dc1b755c6c58ed3dcc2dda9f488744c14119b3e3`:
645 unique readable PDFs, **158 no-text proxies**, not 158 confirmed scans. A textless
page can contain outlined vector text. Deterministic sample: first ten unique A101
`text_layer=no` paths lexicographically; **only physical page 1** of each. Five were
image-backed (image-area sum >=0.8 page, <20 vector paths), five vector/mixed and
excluded from OpenCV. This does not estimate the corpus-wide raster percentage.

| Project / sampled page | HoughP lines | LSD lines | HoughP / LSD seconds |
|---|---:|---:|---:|
| A101/18 VTNK-07_PP_AGR_pravki p1 | 416 | 2532 | 0.1012 / 0.2366 |
| A101/19 lighting plan p1 | 320 | 3035 | 0.0759 / 0.2747 |
| A101/19 site improvement scheme p1 | 621 | 5922 | 0.1283 / 0.3163 |
| A101/20 PRKS_7.2 facades p1 | 390 | 8235 | 0.1325 / 0.3063 |
| A101/28 Vatutino lighting plan p1 | 417 | 3518 | 0.0982 / 0.3929 |

Gray render <=2000 px long side (max 2x PDF points); Canny50/150;
HoughP rho1, theta pi/180, threshold40, minLineLength30, maxLineGap3; default LSD.
Line counts include hatching, landscaping, symbols and text strokes; they must not
be reported as recovered dimensions. Source paths/page hashes, sizes and timings
are in `tool-comparison.json`, not fabricated raster truth.

## Reproduction and evidence

Upstream native extraction commands and original DWG/DXF/PDF hashes:
[original evidence note](pdf-album-binding-2b.md#native-dimension-oracle-no-token-only-credit).
This run re-hashed both DXFs and plotted PDFs before scoring; no source was rewritten.
Third native DWG/DXF/PDF hashes are in third-sheet.json. No PDF/DWG/PNG is committed.

Sealed evidence: `G:/Мой диск/AGR-evidence/1302-pdf-dimensions-recall/evidence-v001/`;
fallback task-local directory `tmp/evidence-v001/`. Its manifest digest is recorded
in `dimension-recall-results/evidence.json`. Mounted-Drive bytes are verified;
cloud-sync completion is not measured. Drivers, frozen pre-fix binder, per-label
native data/registration, full before/after tables, tool sources/licences/receipts,
rendered page checks and hostile-probe receipt are included.

From this worktree, restore the sealed drivers/registration files to ignored `tmp/`
if needed; use the unchanged #1290 source copies or change only their location after
verifying hashes. Reproduction commands (observed library versions above):

```bash
# Frozen baseline captured before production edits:
git show 39a317d9:src/dt_ai/album/binding.py > tmp/baseline_binding.py
uv run --extra pdf-review python -m tmp.inspect_dims
uv run --extra pdf-review python -m tmp.map_oracles
uv run --extra pdf-review python -m tmp.recall_audit
uv run --extra pdf-review --with pdfplumber==0.11.10 --with opencv-python-headless==5.0.0.93 python -m tmp.probe_tools
uv run --extra pdf-review python -m tmp.hostile_probe
```

`recall_audit.py` refuses changed DXF/PDF hashes and ambiguous/missing source labels;
all 94 input dimensions end in a reported success or named miss. Original axis-only
oracle command remains unchanged; do not interpret its unsupported level-pair score
as four new false positives. No calibration anchors are supplied by any replay.
