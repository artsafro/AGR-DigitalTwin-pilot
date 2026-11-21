# PDF/model audit mode A — KPP1 prototype (#1304)

## Contract and trust hierarchy

[D274]: neither source is absolute truth. Materials/RAL/finishes follow PDF
schedules checked against facade marks; dimensions compare PDF and model;
geometry follows the model checked against PDF; levels/storeys follow PDF checked
in 3D; counts follow PDF schedules counted in the model; names/marks follow PDF
matched to the model. Conflicts are reported, not repaired. `passed=false` always:
this is an audit, not architectural, delivery or publication approval.

Reusable entry: `dt_ai.album.compare.compare(bundle)` and:

```bash
uv run python -m dt_ai.album.compare --input jobs/KPP1/audit-1304/input-final.json --output-dir tmp/audit-new
```

The output directory must be NEW and its parent must exist. Exit **0** means all
provided facts have measured matches, **1** means discrepancies exist, **2** means
manual checks without measured mismatches, **3** means invalid/stale input or
publication failure. Exit 0 is NOT delivery acceptance. Never interpret a retained
old report as the result of a failed invocation.

This normalized-observation CLI is the reusable seam for future `agr compare`
(#1296), **not a universal raw PDF/FBX semantic extractor**. Feed it extracted
observations from the existing PDF binder/OCR and native model readback. The
schema and complete synthetic example are in `tests/test_album_compare.py`.

Facts carry category, literal/audit mark, facade, independently documented local
query position `[u,z]` or null, value or null, units, verification/calibration
flags, tolerance and source evidence. PDF evidence includes physical page,
sheet, PDF-point bbox (top-left origin), method, path and SHA256. Model evidence
includes object id/name, raw observation locator, method, path and SHA256.
`verified` attests upstream extraction/correspondence, never architect approval.
Unknown positions/values remain null, not zero. Do not use the compared value
itself to discover an otherwise unidentified counterpart.

A candidate must share category + facade + mark and be strictly within the stated
local query-position tolerance. Zero or multiple candidates -> manual, never the
first item. Unverified sources, missing values and uncalibrated opening sizes ->
manual. Metric differences use full precision and **abs(delta) < tolerance**;
exact equality to the limit fails. Counts use exact integer equality, finish/mark
strings exact equality (no fuzzy RAL mapping). Every PDF fact yields one row per
model; unused model observations retain their complete evidence and a reason.
Repeated PDF pages may reference ONE physical model observation.

Malformed/duplicate IDs, duplicate JSON keys, unknown categories/units/keys,
missing evidence and NaN/inf are rejected. File-backed CLI evidence is hashed
before comparison and immediately before publication. Existing/aliased outputs
and competing writers are refused by exclusive creation; inputs are never
replaced or deleted. No predictable `.partial` files are used. This is a
single-process before/after snapshot contract, not an immutable-filesystem or
malicious concurrent edit-and-restore guarantee.

## Sources and actual execution

Final inputs/report: [`input-final.json`](../../jobs/KPP1/audit-1304/input-final.json),
[`report.json`](../../jobs/KPP1/audit-1304/report-final/report.json),
[`report.md`](../../jobs/KPP1/audit-1304/report-final/report.md),
[`evidence manifest`](../../jobs/KPP1/audit-1304/evidence-final.json).
Large raw evidence, immutable model copies, images, OCR line boxes/confidence,
NPZ meshes, raw face/UDIM census and reproducer:
`G:/Мой диск/AGR-evidence/1304-kpp1-mode-a/evidence-v003/` + `SHA256SUMS.txt`.
No LFS. Earlier failed/diagnostic attempts remain separate; v003 is the final
raw evidence, not a silent overwrite of v001/v002.

- Original album specified by Artem: read-only copy
  `C:/x/kpp1-finishes/ТЭЦ26 на РР.pdf`, SHA256
  `ca9bfc120179395d4be1d423468d1970f803fd50ea26fdec97ae9c4cef2afd6e`,
  **59** pages. Scope: south facade on p25, finish schedules on p25–26 only.
- Deterministic text/vector extraction FIRST: both pages have **zero vector
  paths** and only title text. The actual facades/schedules are raster images.
  RapidOCR 3.10.0 Cyrillic PP-OCRv5 mobile recovered **10 RAL rows on each page**;
  literal OCR values/boxes retained. Agent visual interpretation matches the
  schedule rows; this is **not independent expert ground truth**.
- Existing source-bound four-page DWG plot `KPP1-L01-pr1249.pdf`, SHA256
  `5232d5fa43e781b6c13445d2743b099d389bf32b4e7f87677d5ef60b6daace37`:
  **only page 1**, the same south facade, supplements vector levels/axes. It is
  labelled a derived DWG plot, NOT misrepresented as the original album.
  `bind_album(..., pages=[1])` retains 31 level tokens (including unresolved)
  and two axes. Full-album/other-facade comparison is out of scope.
- Fresh **Blender 5.1.2**, headless factory-startup, copies only: source
  `D:/DigitalTwinProject/KPP1/source/v001/KPP1_ext_src_v001.fbx` -> **1647** mesh
  readbacks; R1 `.../1230-kpp1-r1/r1-v002/SM_Kpp_1.fbx` -> **6** meshes including
  four excluded UCX meshes. Logs, raw geometry and source/copy hashes retained.
  Source FBX imports without material slots and emits invalid-material-index
  warnings: its Revit-export sidecar is separately labelled **metadata**, not a
  successful FBX shader readback. No live scene or model was changed.
- R1 face census: **30666** render faces; UV tiles identify **declared** finish
  labels through the pinned `textures.json`, not inverse RGB->RAL guesses or a
  physical colour-fidelity certificate.

Historical measurement commands (successful files were read back; these are
records, not executable safety templates):

```text
uv run --extra pdf-review python ... bind_album(..., pages=[1])
Blender 5.1.2 --background --factory-startup --python jobs/KPP1/site-1255/dump_vertices.py -- <copied.fbx> <new.npz> <new.json>
Blender 5.1.2 --background --factory-startup --python tmp/readback_finishes.py
uv run --python 3.13 --extra pdf-review --with rapidocr==3.10.0 --with onnxruntime python ... RapidCyrillicOCR ...
uv run --with numpy python tmp/build_audit_evidence.py
uv run python -m dt_ai.album.compare --input jobs/KPP1/audit-1304/input-final.json --output-dir jobs/KPP1/audit-1304/report-final
```

The complete evidence driver and readback helper are frozen in v003. Its original
reserved trust identifier is historical: final input/report metadata was
reallocated to [D274] after an earlier unpublished reservation was discovered.
`decision-renumber-v001/` preserves the old normalized input/report; all 112
observation rows and the comparator executable AST are unchanged. On a fresh
reproduction use the final normalized manifest, or apply that citation-only
renumber after the historical driver, use a new version directory and add
`--python-exit-code 1` to Blender
invocations; inspect the produced measurements as well as process exit.

## Placement and tolerances

[D262] is preserved, not refitted. Invert the common accepted site placement and
compare locally: source/Revit coordinates = R1 local + `[14.655,5.355,0]` m.
The unchanged common site transform uses rotation **-6.053044176714781 deg** and
origin `[8056.143933445407,-9581.26989822931,171.050]`; no 180-degree alternative.
The accepted approximate ±0.1 m label is NOT a maximum survey error certificate;
entrance orientation remains not independently confirmed. No survey pass claimed.

Numeric checks use **0.010 m**; local region matching uses **0.100 m**. Counts
and RAL labels are exact. These local comparison budgets do not improve D262's
survey accuracy. Schedule row 8 is interpreted as the external east stair and
matched to its physical query region `u=29,z=2` m, not a fictitious schedule-space
coordinate. Other unlocated finish rows are manual. Axis labels are preserved,
but neither model has proven labelled grid geometry; no position is invented.

## Results — 112 evidence rows, not 112 unique physical defects

| Model | Match | Mismatch | Manual |
|---|---:|---:|---:|
| Source / Revit-derived | 4 | 1 | 51 |
| Our R1 v002 | 2 | 3 | 51 |
| Total | 6 | 4 | 102 |

| Category | Match | Mismatch | Manual |
|---|---:|---:|---:|
| Levels | 3 | 1 | 58 |
| Axes | 0 | 0 | 4 |
| Clear-sash count | 1 | 1 | 0 |
| Declared finishes | 2 | 2 | 36 |
| Opening marks | 0 | 0 | 2 |
| Opening sizes | 0 | 0 | 2 |

Concrete discrepancies, retained for review, never auto-fixed:

1. PDF parapet datum **8.650 m** vs source flashing-cap endpoint
   **8.679433696441208 m**: delta **0.029433696441207857 m**, tolerance 0.010 m.
   Source object `o1101`, `Парапетный нащельник Парапет_6582fcd`.
   A cap/detail datum distinction is for the architect, not a silent correction.
   R1 top **8.650000544734358 m** matches the written datum locally.
2. South facade has **12** clear sash symbols in the explicit image-region
   inventory; source has **12** `MEP_Окно_Витражное` instances at y≈0. R1 has
   **21** connected glass patches on that facade: delta **9**. Extra patches
   occupy perforated/opaque/grille-looking regions. This is a conservative
   semantic diagnostic requiring inspection, not a claim that 21 is an official
   window schedule count. Image inventory is agent-made, not independent truth.
3. External stair schedule row **8**, **RAL 5015**, vs emitted R1 stair-region
   UV tile **1007**, declared **Grille_RAL7004**. Source Revit instance **1728448**
   declares RAL 5015. The same schedule occurs on p25 and p26, so this ONE finish
   discrepancy contributes TWO evidence mismatch rows, not two physical defects.

No original opening marks or calibrated dimensions are fabricated. Sizes remain
pending **#1302** (OPEN at measurement time); no size is measured from a single
axis span or nominal scale. The comparator supports all six categories (including
real-valued axes and calibrated sizes) in synthetic tests, while real unsupported
counterparts are explicitly manual. Thirty-six finish rows do NOT have a proven
surface/mark correspondence; tile presence alone is not promoted to a match.

## Verification and retained attempts

- Tests-first commit `72e3a2e1`: initial missing comparator test failed (1 RED).
  Category/uncertainty slice then failed 2 tests before implementation; validation
  and CLI slice failed 31 tests before repair. These are development RED slices,
  not hidden runtime failures.
- Evidence attempt 1: an empty recessed-door selection failed closed; preserve
  raw v001. Attempt 2: duplicate model observations for repeated schedule pages
  and disconnected blue parapet strip made correspondence manual; preserve v002
  plus the first diagnostic report. Final v003 retains both PDF pages but ONE
  physical model observation and selects the lowest independent blue wall band.
- Empty/partial/unsupported/NaN/inf, exact boundaries, duplicate IDs/JSON keys,
  stale hashes, input aliases/hardlinks, state change, competing writer, preseeded
  `.partial`, fresh CLI exits and old-output refusal have explicit tests.
- Generated binary-exact boundary matrix: 3 metric categories × 65 deltas,
  **195/195** comparisons; strict boundary and full-precision differences.
- `test_real_kpp1_receipt_keeps_manual_gates_and_evidence` independently recomputes
  every saved row/count from the committed normalized bundle, without requiring
  a workstation-only source path during the normal suite.
- Full-suite and eval receipts belong to the PR body at its frozen commit, not a
  hand-edited claim of architectural acceptance here.
