# PDF album binding 2b: source-bound follow-up (#1254)

## Result and boundary

The requested binding increment is measured on the **same KPP1 L01 PDF and ELV
pages as #1249**, plus two **native AutoCAD-plotted dimension sheets**. The
second sheet was found locally under [D266]; the conditional two-L03-viewport
fallback was **not used**, and acceptance was not narrowed.

- KPP1 L01 axes: **8/8 correct, 0 wrong**, formerly 0/8.
- KPP1 L01 levels: **94/97 correct, 0 wrong**, formerly 43/97.
- ELV levels: **60/65 correct, 0 wrong**: 35 elevation-line marks and 25 boxed
  plan spot-height tags. Recall **0.9231**; KPP1 recall **0.9691**; combined
  **154/162 = 0.9506**. The five ELV misses remain explicit below.
- Semantic dimension binding: L03 **7/7 correct predictions**, recall **7/82**;
  KNS section **4/4 correct predictions**, recall **4/12**. Precision **1.0 on
  both sheets**. This is intentionally low-recall, conservative binding, **not
  recovery of every dimension or a calibrated measurement certificate**.

All results retain `passed: false`. No model anchors were supplied, scales stay
`unknown`, and dimension `measured_mm` stays null. A source axis-pair/value
identity can be scored independently while its geometric measurement remains
unresolved. OCR, schedules, materials and customer/model geometry were not changed.

## What changed

1. PyMuPDF already applies nested Form/XObject transforms. The missing bubbles
   were **two source ARC halves inside INSERTs**, tessellated by the old plotter
   into a closed 16-edge loop inside a compound path. Recognize complete circular
   subloops, not the compound path's global bbox. Native AutoCAD PDFs additionally
   split a circle into two separately stroked Bezier semicircles; join only a
   connected, closed circular loop. Synthetic nested-XObject rotations exercise
   transformed positions/orientations. Open/elliptic/ambiguous-label loops refuse.
2. Level symbols may have a stem in either direction; their arrow arms can exceed
   the old fixed 15 pt limit after plotting at a larger paper scale. Require the
   actual shelf-to-tip stem and correctly facing arms, retaining shared-tip,
   ambiguity and value-consistency refusals. Never choose a nearest unrelated line.
3. Roof-plan levels are a different symbol: a tight closed rectangular tag around
   one level string. Emit **`spot_level` with `spot_bbox` and null `level_y`**.
   They never feed vertical `level_pair`, elevation-line fitting or model scale.
4. Native dimension lines contain short collinear connector strokes around ticks.
   Include those strokes before merging line intervals, otherwise real chains
   break and tick endpoints move. Semantic binding rules and calibration gates
   are unchanged.

## Per-sheet observations

`found` means a positive semantic binding, not a numeric token. KPP1 truth comes
from the independent DWG/DXF, using the original #1249 plot transforms (not given
to the binder). ELV is an **agent visual audit, not independent expert/as-built
truth or customer approval**: all 65 native level strings were counted; red text
and blue predicted symbol overlays on p18/19/23/31 were visually inspected. This
includes the plan tags rather than silently excluding the difficult page.

| Source / physical PDF page | Class | Found | Correct | Wrong | Missed | Truth |
|---|---|---:|---:|---:|---:|---:|
| KPP1 L01 / 1 | axes | 2 | 2 | 0 | 0 | 2 |
| KPP1 L01 / 2 | axes | 2 | 2 | 0 | 0 | 2 |
| KPP1 L01 / 3 | axes | 2 | 2 | 0 | 0 | 2 |
| KPP1 L01 / 4 | axes | 2 | 2 | 0 | 0 | 2 |
| KPP1 L01 / 1 | levels | 29 | 29 | 0 | 1 | 30 |
| KPP1 L01 / 2 | levels | 25 | 25 | 0 | 1 | 26 |
| KPP1 L01 / 3 | levels | 19 | 19 | 0 | 0 | 19 |
| KPP1 L01 / 4 | levels | 21 | 21 | 0 | 1 | 22 |
| ELV / 18 | levels | 18 | 18 | 0 | 0 | 18 |
| ELV / 19 | levels | 16 | 16 | 0 | 0 | 16 |
| ELV / 23 | levels | 1 | 1 | 0 | 0 | 1 |
| ELV / 26 | levels | 0 | 0 | 0 | 1 | 1 |
| ELV / 31 | plan spot levels | 25 | 25 | 0 | 4 | 29 |
| KPP1 L03 / 1 (native) | dimensions | 7 | 7 | 0 | 75 | 82 |
| KNS V1 section / 1 (native) | dimensions | 4 | 4 | 0 | 8 | 12 |

KPP1 L01 has zero DIMENSION entities; dimension precision there is **unknown**,
not perfect. ELV has no independently authorized DWG dimension/axis oracle in this
card; those classes remain **not measured**, rather than inventing correct/wrong
counts. Native L03/KNS grids are explicitly identified by source entity handles
in `L03-grids.json` / `KNS-grids.json`; semantic dimensions are checked against
those independent source grids. KPP1's pre-existing +3,000 source discrepancy and
other ambiguous/inconsistent marks remain unresolved, not silently corrected.

Machine-readable table and source hashes:
[`binding-2b-results/`](../../tools/research/pdf_album/binding-2b-results/).

## Native dimension oracle (no token-only credit)

AutoCAD **2025 Core 25.0 / V.72.0.0**, source `INSUNITS=4`, headless through the
serialized `dcc_batch.py acad` wrapper, **hashed copies only**. Plot uses Model,
`DWG To PDF.pc3`, A3 full bleed, Extents, Fit, Center. Fit is a plotting operation,
**never an inferred model calibration**. PDFs were opened with PyMuPDF and rendered;
DXFs were opened with ezdxf 1.4.3. Native exit 0 alone was not accepted as evidence.

| Sheet | Original DWG SHA256 | Native DXF SHA256 | Model/all DIMENSION |
|---|---|---|---:|
| KPP1 L03 | `ad1de2b203bd4394bd3604642cd41bd8f3b2427ec23b900413bd396612624469` | `6d0c646023967e294c586e3c3b51e7a6090dd3831dcc5f58fd7d32128ea30371` | 82/82 |
| KNS V1 section | `a9e057e8845c92ca4af9ea7d6e3da2bdde818e9e90b31dfaaa375f3205e2b91f` | `58c60ab10c3942e4001b5b3de191b41e0d26f6e97eac044d1d15ac9abfc9f0f6` | 12/12 |

Second original: `B:/Backup/Desktop/!3D viz/!KNKO/KNS_STOLBOVO/РР1/2. КНС
СТОЛБОВО_РР1_DWG И EXCEL/DWG/ВАРИАНТ 1/KNS_STOLBOVO_V1_РАЗРЕЗ.dwg`.
Original and working-copy SHA256 were checked equal after native execution.
Full PDF hashes are in `input-hashes.json`.

`binding_2b_eval.py` reads **every modelspace DIMENSION**, projects extension
points onto the dimension direction and matches them to the independently
transcribed source grid identities. It compares the predicted value (integer-mm
rounding tolerance strictly < 0.5 mm) **and both source axis labels**. A raw number
or an unbound chain gets no positive credit. All 82/12 entities, including
unsupported/unbound source spans, stay in the recall denominator. Matching is
one-to-one; duplicate predictions cannot multiply a hit; ambiguous matches refuse.
The tool emits stdout only, never writes source/report/temp paths. Changed DXF
bytes during extraction raise an error; the source hash belongs to the parsed
snapshot, not a later reread.

Reproduce from this worktree (the sealed scripts retain native command transcripts):

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad --dwg C:/x/t_85bcc27a/oracle-v001/L03.dwg --file C:/x/t_85bcc27a/native-v002/L03-plot.scr --card t_85bcc27a --out NEW-L03-console.json
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad --dwg C:/x/t_85bcc27a/native-v004/candidate2.dwg --file C:/x/t_85bcc27a/native-v004/candidate2.scr --card t_85bcc27a --out NEW-KNS-console.json
uv run --extra pdf-review --with ezdxf python -m tools.research.pdf_album.binding_2b_eval C:/x/t_85bcc27a/oracle-v001/L03.dxf tools/research/pdf_album/binding-2b-results/L03-grids.json C:/x/t_85bcc27a/native-v002/L03.pdf
uv run --extra pdf-review --with ezdxf python -m tools.research.pdf_album.binding_2b_eval C:/x/t_85bcc27a/native-v004/candidate2.dxf tools/research/pdf_album/binding-2b-results/KNS-grids.json C:/x/t_85bcc27a/native-v004/KNS-section.pdf
```

**Do not rerun a native script over an existing export**: copy the script and
change its embedded PDF/DXF output to a fresh version first. The last two commands
are read-only and print the complete oracle and metrics. L03 matched handles
`19A9/19C5/19DF/19F9/1A13/1A2D/1A4A`; KNS `3414/3415/3416/3417`.

## Search and failed attempts (retained, not hidden)

[D266] search script `search_cad.py` and streaming `cad-search-v002.jsonl` are
sealed with evidence. Command: `uv run python search_cad.py`. Walk B:/, D:/,
G:/Мой диск and C:/, looking for `.dwg`/`.dxf`; skip system, `.git`, `.worktrees`,
`.venv`, node_modules and AppData. Also searched AGR-assets, Drive А101,
D:/DigitalTwinProject and C:/Users/artsafro directly (`cad-priority.json`).
The inventory referenced in open PR #1282 was contextual routing only; no code or
unmerged result from that PR was copied into this branch.

| Root | Located CAD paths | Coverage |
|---|---:|---|
| G:/Мой диск | 22 | completed accessible walk, including AGR-assets/project folders |
| B:/ | 834 | completed accessible walk, including delivered 3DVis projects |
| D:/ | 1981 | completed accessible walk |
| C:/ | 32219 | bounded partial walk, stopped after the second oracle was verified |

707 filesystem access errors are retained as error rows, not a claim that all
system directories were searched. Paths include duplicate/archive/derived files;
they are **not counts of unique suitable sheets**. Repository/test-generated
DXFs were not treated as real-project truth.

| Candidate | DIMENSION / observation | Disposition |
|---|---|---|
| KPP1 AS.03 L01/L02/L03 | 0/0/82 | L03 selected; empty L01/L02 not counted as dimension evidence |
| four existing delivered-project DXFs (Butovskaya x2, Magistralnaya, COD Ground) | 0 each | not suitable |
| KNS V1 first-floor plan | 6, native plot succeeds | rotated drawing, extra exploded dimensions; retain failed read, do not tune truth to it |
| Vatutinki `Планы_recover.dwg` | AutoCAD ErrorStatus=190, no DXF | retained native failure; switched source, no repair/source save |
| TEC26 AC08 | 48 after ezdxf recovery (native DXF missing ENDSEC); PDF only 2 text chars | no readable dimension text; not substituted as a successful sheet |
| Donskoy DON_5_280726_dwg | 0 | not suitable |
| KNS V1 section | 12 | **selected independent second sheet** |
| Vatutinki AGR_MKA 5.09.25 | 989 | found, not needed after section succeeds |

## Evidence and verification

Mounted-Drive copy was byte-verified:
`G:/Мой диск/AGR-evidence/1254-pdf-binding/evidence-v001/` (82 members).
Fallback: `C:/x/t_85bcc27a/evidence-v001/`.
SHA256 of `SHA256SUMS.txt`:
`289e4acab0ccb2dabdc92d29608970fc22749121e911871d7a86049e658ce2a4`.
Cloud-sync completion is **not measured**. Includes copied DWGs/DXFs/native PDFs,
native .scr/console logs, source-search inventory, KPP1 transform/truth/reader
outputs, ELV per-mark overlays. No binary is committed.

Tests-first commit `150ae5ca`: 10 failed, 2 passed before polygon/level fixes.
Short-connector RED: 1 failed on `12b7af0a`; boxed-spot RED: 1 failed/13 passed.
Corrected open-semicircle fixture also fails on detached `bff41871` (1 failed;
resolved `reader.__file__` points into that detached source), then passes here.
Oracle RED: missing module on `d1d32c18`; stale-source witness separately failed
before the hash-bound extraction check. Affected verification: **276 passed,
18 skipped, 3 deselected** (all album tests, decisions and project hygiene).
Final full-suite exact-head receipt and author/eval/probe receipts are published
in the PR, not committed after the tested head. Existing approvals, calibration
and architect questions remain open regardless of these technical metrics.
