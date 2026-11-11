# PDF album -> dimensions, finishes and schedules: measured research (#1228)

## Verdict

**PARTIAL, not an unattended modelling pipeline.** Use **reference-first staged album intake**:
text/index first, routed table extraction second, OCR plus targeted visual verification for
outlined/scanned regions, and CAD conversion only when editable linework is actually needed.
Do **not** make PDF -> DWG the default. It recovered no extra semantic dimensions in this corpus.

Three real albums, three issuers, 53 physical PDF pages were exercised with A, C and OCR D
on **every page**. Headless AutoCAD B was exercised on four selected pages across all three
albums; native vision reviewed each album. An additional outlined PSU275 drawing was rendered,
OCRed and inspected by ROI. No production code, customer source, live Max or job procedure changed.

This is a deliberately small **audit sample**, not an accuracy estimate for all dimensions in
all albums. Dimension/level/RAL scores below mean **exact labelled-text recall**, not correct
axis, opening, elevation-view or facade-region association. Table scores require key and value
in the same extracted row. Model-scaled geometry accuracy remains **not measured**: no route
established an independently checked model calibration. Unknown is not 100% and not a pass.

## Corpus, authority and reproducibility

Working copies: `C:/x/pdf-album-research/t_5b23c219/`. Original files were read-only.
Committed observations and audit references: [`tools/research/pdf_album/`](../../tools/research/pdf_album/).
Full raw results, PDFs, DWGs/DXFs and renders are external evidence (seal below).
Physical PDF pages are 1-based; a printed sheet is a separate field, never assumed equal.

| Album | Issuer and source locator | Pages | PDF SHA-256 |
|---|---|---:|---|
| ELV shopping centre | Tempro; `jobs/elv-tc-vpm/TASK.md` inputs, `Dima_Andrew/3_sreda/for_ai/ЭЛВ_ИД_АГР_45-4-25-С_Буклет АГР от 27.01.2025 (1) (1).pdf` | 42 | `49c105275ea56f16f9f281b3586876818215d99544d82644a5aab8e1cfba9545` |
| COD20207 lighting package | The Light (equipment specification p5); existing `NTR/22_COD/Исходные данные/001 - Исходные данные/Альбом/20207_ЦОД_свет_задание.pdf`, same project as `jobs/COD-20207` | 5 | `3398c18864b0ef46b3cb59d43c34e8e3a7707172ee372545861ff8a672bb87ce` |
| TEC26 / PSU275 visualization booklet | Mosenergoproekt (МЭП); `docs/sources/psu275.md` S1; `Dima_Andrew/2_kotelnya/ИД/26.pdf` | 6 | `ab4339496166779b2989a42bdbf88072bf8267a6a30ad748da544bf48ed3f997` |

The COD lighting PDF was discovered in that project's existing source folder; it is **not**
the ground-model DWG in `jobs/COD-20207/parts.json`. Neither is substituted for the other.
ELV material bindings have earlier job approval (`TASK.md` D01/D03/D06 and pilot parts).
Dimensions, levels and schedule sample rows were transcribed from rendered drawings as audit
references; they are **not independently surveyed/as-built measurements or new customer approvals**.
The distinction is retained in `reference.json` and `vision-observations.json`.

KPP1's manifest names AS.03 DWGs and a PPTX, **not a PDF**. Its named original source folder
currently contains a PLN and no AS.03 PDF. No PDF was manufactured from its DWG to inflate this
benchmark. The open KPP1 source-authority discrepancy in its manifest is not decided here.
Vatutino's available project sources are DWGs; its found `verona.pdf` is a furniture catalogue,
not a building album. The three albums above satisfy the cross-author comparison without that substitution.

Environment actually exercised: Windows 11 build 26200, AMD64 Family 25 Model 33;
PyMuPDF 1.28.2, pdfplumber 0.11.10/pdfminer-six 20260107, ezdxf 1.4.3,
RapidOCR 3.10.0 / ONNX Runtime CPU 1.31.1, NumPy 2.5.3; AutoCAD 2025 Core 25.0,
V.72.0.0. Dependencies were transient `uv --with` packages; no production dependency changes.
Timings are wall time within the script, excluding package installation and terminal launch;
AutoCAD timings include core startup. Concurrent research passes mean these are observations,
not isolated performance benchmarks. Default OCR models were bundled; no remote OCR API used.

## One comparison table

`D/L/R/S` = dimension text / level text / RAL code / structured schedule sample rows.
A/C/D denominators: ELV **4/4/3/3**, COD **3/2/3/1**; TEC26 has **no applicable denominator**.
All scored strings must occur on their reference page; neighboring pages do not rescue a miss.
Exact-token scoring is stricter than the interior of the requested 1 mm text tolerance;
no borderline numerical result is accepted. The prototype's strict threshold controls are
not a replacement for calibrated geometry scoring at 0.5%.

| Album | Route and pages actually processed | D/L/R/S correct/reference | Measured minutes | Manual work remaining |
|---|---|---|---:|---|
| ELV | A: existing reader, all 42 | 4/4, 4/4, 3/3, 0/3 **raw text**; 0 sampled typed dimensions/levels | 1.930 | Associate dimensions to axes/views; reconstruct multi-line finish descriptions; verify openings |
| ELV | B: AutoCAD PDFIMPORT p18 -> DWG -> DXF | 3/3, 4/4, 3/3, not tested on p27; **0 DIMENSION** | 0.338 for p18 only | Model scale, region binding, schedule structure; no full-album CAD timing claimed |
| ELV | C: PyMuPDF + pdfplumber, all 42 | 2/4, 0/4, 0/3, **3/3** | 5.041 | Reject facade grids found as tables; label merged/header/category/total rows |
| ELV | D: OCR all 42 at 150 dpi + native vision spot checks | **4/4, 4/4**, 1/3, 0/3 | 4.510 OCR; 6.44 s/page mean | Cyrillic material text poor; numbers need diagram association; cropped vision checks |
| COD | A: all 5 | **0/3, 0/2, 0/3**, 0/1 | 0.013 | Facade dimensions/legend are largely outlines despite a searchable page header |
| COD | B: PDFIMPORT p1 and p5 -> DWG/DXF | 0/3, 0/2, 0/3, 0/1 structured | 0.177 for two pages | Outlined annotations stay splines; equipment text remains unstructured MTEXT |
| COD | C: all 5 | 0/3, 0/2, 0/3, **1/1** | 0.030 | Quantity/unit and equipment-length semantics still need checking |
| COD | D: OCR all 5 + native vision p1/p5 | **3/3, 2/2, 3/3**, 0/1 | 0.587 OCR; 7.05 s/page mean | Resolve printed chain discrepancy; Cyrillic descriptions unreliable; visual table row check |
| TEC26 | A: all 6 | n/a: no dimension/level/finish/table source content | **3.911** | Reject unsuitable source; request actual drawings instead of guessing from renders |
| TEC26 | B: PDFIMPORT p3 -> DWG/DXF | n/a; 2 MTEXT + 2 SOLID, **0 DIMENSION** | 0.080 for p3 only | No missing dimensional information can be recovered from this visualization |
| TEC26 | C: all 6 | n/a; no schedule denominator | 0.643 | Do not mislabel a failed search as complete dimensional intake |
| TEC26 | D: OCR all 6 + native vision p3 | n/a; confirms visualization-only page | 0.370 OCR; 3.70 s/page mean | Obtain dimensioned source/BIM; perspective render is not a scale anchor |

The full A pass found **one other dimension candidate** on ELV p26 (`1685`) and two level
candidates on p31 (`+12.210`, `+13.690`), all with **unknown scale**. They are not part of the
frozen sample and were not validated as correct geometry. The sampled facade pages p18/p19
have axes (12 and 5) but **zero typed dimensions and zero typed levels**. Raw text recall must
not hide this failure. The reader's own validation tolerance is `max(10 mm, 0.5%)`, not the
requested 1 mm text benchmark; none of its `ok` statuses is used as a 1 mm accuracy certificate.

No precision score, all-row table recall, fully automated finish-region assignment or validated
opening inventory can honestly be inferred from these tiny samples. Those remain follow-up gates.

## Ground-truth comparisons and semantic traps

Each value below has a physical page and printed-sheet locator; raw extracted bboxes and route
receipts are in the sealed `*-A/C/D-all-v001/result.json`. `results/*.json` records individual hits/misses.

| Source reference | Reference value and authority | Observed comparison |
|---|---|---|
| ELV PDF p18 / sheet 18, И-А facade chain | 52,600 mm total; 8,400 mm repeated spacing; 5,300 mm ends, printed dimensions | A raw text and D OCR recover all three exactly; A typed dimensions 0 |
| ELV PDF p19 / sheet 19, 1-12 facade | 84,000 mm total, printed dimension | A raw text and D OCR match; B was not run on p19 and receives no credit |
| ELV PDF p18 / sheet 18 | +0.000 / +4.720 / +13.920 / +16.220 m | A raw text/B MTEXT/D OCR match; typed level binding is absent |
| ELV PDF p18 / sheet 18 finish legend | RAL 1001 wood/pine panels; RAL 7021 metal panels; RAL 5024 stemalit; prior `TASK.md`/pilot parts bindings | A/B codes 3/3, OCR 1/3; codes alone do not map polygons to finishes |
| ELV PDF p27 / sheet 27, first three data rows | `1.D.17` = 10.77 m²; `1.D.18` = 11.54 m²; `1.O.01` = 15.65 m², rendered schedule | Both table tools agree on these rows, 3/3; category and total rows are not data |
| COD PDF p1 / printed sheet 12 | 69,600 / 17,800 / 87,450 mm; +0.000 / +35.800 m, rendered labels | A/B lose outlined text; OCR matches. **69,600 + 17,800 = 87,400**, not 87,450: preserve 50 mm discrepancy as open, never silently change total |
| COD PDF p5 / unnumbered specification dated 20.07.2026 | INTILED `LACE RGBW Custom`, quantity **1**, length **5,505 m**, section **16x15 mm** | Both table tools keep these in one row; vision confirms. Quantity 1 is not a length of 1 m; sheet itself requires final length/section approval |
| ELV PDF p23 / sheet 23, signage detail | **1,180 mm is a sign-letter width** | Visual check rejects interpreting this token as a window dimension. Openings require view/element association, not numeric regexes |
| TEC26 PDF p3 / unnumbered visualization 1 | no dimensional/finish schedule values (`docs/sources/psu275.md` S1 also calls this appearance-only) | Empty denominator, not 0% failure or 100% recovery; no values borrowed from the project's Revit/DWG |

## What PDF -> DWG really preserves

Authorized headless AutoCAD 2025 ran through `dcc_batch.py`, one process at a time, blank
document, `INSUNITS=4`, insertion 0,0, scale 1, rotation 0; sources were copied PDFs only.
All produced DXFs were opened with ezdxf, not merely checked for file existence:

- ELV p18: **27,280 entities** = 23,484 LWPOLYLINE + 1,856 SOLID + 1,791 HATCH + 149 MTEXT.
  Five layers: `0`, `PDF_Geometry`, `PDF_Solid Fills`, `PDF_Text`, `Defpoints`; **0 DIMENSION**.
- COD p1: 84 HATCH + 19 SOLID + **2,495 SPLINE** + 2 LWPOLYLINE + 6 MTEXT;
  p5: 24 SOLID + 43 MTEXT. Both have 0 DIMENSION. Outline text is not restored to readable text.
- TEC26 p3: 2 SOLID + 2 MTEXT, 0 DIMENSION. Importing a visualization adds no object measurements.
- ELV p18's two `5300` labels give a PDF-point/import-unit X-distance ratio of
  **72.0001765**, consistent with paper-inch coordinates, even though `$INSUNITS` says 4.
  This is a **paper-coordinate consistency probe**, not the independent model-size check.
  Assigning `INSUNITS=4` did not make the 16.535-unit page width a model dimension in mm.
  No scale should be guessed from the import settings or the sheet's nominal 1:200 alone.
- Initial experiment: `-SAVEAS` is unsupported in this core session. Wrapper exit code was 0,
  but log said `Unknown command` and no DXF existed. `SAVEAS` + `DXFOUT` succeeded on the next
  versioned output; this is why the wrapper's exit code is insufficient evidence.

**Alternate free converter actually tried:** `free_dxf.py`, PyMuPDF -> ezdxf, same ELV p18,
COD p5 and TEC26 p3. It uses unitless paper points, source/page XDATA and explicit loss/drop
reporting; it is not a separate independent PDF parsing engine. Readback results:
ELV 45,833 entities / 33.269 s; COD 72 / 0.188 s; TEC26 10 / 0.110 s; **0 DIMENSION each**.
It drops fills/clips/images/fonts/dashes/text rotation by design and does not improve semantics.
It is a disposable comparator, **not recommended production CAD conversion**. Inkscape and
Tesseract executables were not installed at their standard paths/on PATH; no global install.
A commercial converter's advertised fidelity was not substituted for an executed experiment.

## Tables, OCR/vision and other formats

PyMuPDF `find_tables` and pdfplumber `extract_tables` both preserve the sampled schedule rows.
ELV p18 alone produces 4 vs 6 candidate tables from facade/legend linework: **candidate count is
not schedule count**. Extract only classified schedule/legend regions; preserve columns, merged
cells, units, page/bbox and row type. Export one CSV per table, not a lossy album-wide text dump.

Default RapidOCR recovers numeric strings on outlined COD facades but often drops/substitutes
Cyrillic letters; a Cyrillic-language model was **not** calibrated. ELV full OCR ranges 3.10–22.19
s/page; COD 3.66–9.80; TEC26 2.49–5.92 (150 dpi; model initialization in album totals).
Local OCR has no metered API charge; electricity/hardware cost not measured. Native vision was
actually used for all three albums, but its image-loader tool exposes **neither inference-only
latency nor image-token billing**. Vision per-page price/time are therefore **not measured**,
not invented or claimed free. `vision-observations.json` records exactly what was seen.

An additional real AS.02 PSU275 facade (`psu275-sheet1.pdf`, original `22E56.pdf` in the
TEC26 graphical source package) has **zero text characters**, **1,267,920 paths** and 459 image
references. Whole-page OCR ran in **18.061 s** including setup. Whole-page vision was too small
to read; ROI `[2500,1900,3140,2640]` in the 80-dpi render made the finish table legible:
wall panels RAL 5015/7047, 120 mm; decorative cassettes 9016; plinth 7004; stair rail 1021;
chimney signal red 3020. This addendum proves the **ROI requirement**, not fourth-album coverage.

No OCG/layers or embedded BIM files were found in the three primary PDFs (`get_ocgs`,
`embfile_names`). The packages do contain other source classes: ELV's Revit FBX, KPP1's
RVT/DWG/PPTX and TEC26's original graphical sheets. Inventory those first; a PDF does not
become a BIM model because its authoring application was Archicad/Revit. No IFC was extracted
from these PDFs. Prefer an authorized existing BIM/dimensioned DWG as independent geometry
cross-check, while retaining the PDF's finish/specification authority and open discrepancies.

## Recommended pipeline and outputs (proposed, not production changes)

1. **Freeze and preflight.** Copy/hash each source; record page count, metadata, embedded files,
   OCG, text/raster/outline indicators. Index physical pages and verify printed sheet/title on
   representative renders. Mixed pages need region-level routing: COD headers are searchable
   while the important facade labels are outlines. Zero text is not the only OCR trigger.
2. **Reference-first reading.** Read text with coordinates, then A on dimensioned plan/facade/
   section regions. Build axis/dimension/level candidates **per drawing view**, including
   vertical chains and openings; keep strings and units. Never accept text recall as binding.
3. **Tables only where needed.** Route schedule/legend pages or ROIs to C; reconcile two engines
   for suspect cells; preserve header/category/data/total row types and units. Do not run table
   detection on every facade as the default.
4. **Fallback by budget.** Outline/scanned regions -> render + Cyrillic-capable OCR, then vision
   ROI to verify critical figures, material descriptions, boundaries and conflicts. Stop vector
   work early on dense irrelevant maps: TEC26 p2 took A **233.328 s** (125,918 paths), while
   the entire booklet's OCR took 22.193 s and still correctly supplied no building dimensions.
5. **Optional CAD.** B only for editing/tracing or cross-format inspection; read exported DXF
   entities, layers, text and units back. Require two independent model anchors and test scale
   residuals before measuring geometry. If unavailable, output `scale: unknown`.
6. **Reconcile/report.** Compare to authorized ground truth, attach every discrepancy to its
   page/bbox/view and raise architect questions. A human/vision check is still required for
   opening identity, finish-region application, multiple scales/views and ambiguous table units.

Proposed artifact contract per album:

| File | Minimum contents |
|---|---|
| `album_index.json` | source/hash; PDF page; printed sheet/title or null; plan/facade/section/schedule/3D/unknown; regions and routing reasons |
| `dimensions.json` | raw/normalized value/unit; axis pair or opening id; view id; page/sheet/bbox; method; scale anchors/residuals; confidence and unresolved status |
| `materials.json` | original label and RAL/finish code; legend symbol; element/region binding; page/sheet/bbox; authority and conflict links; no default material |
| `schedules/*.csv` + sidecar | exact cells, row type, unit, table/row id; source page/sheet/bbox/hash; merged-cell provenance and suspect-cell list |
| `questions.json`, `manifest.json` | missing references, disagreements, source hashes, tool/model versions, timings and explicit partial/failed coverage |

Measured conservative **A+C full-album acquisition**: ELV **6.97 min**, COD **0.043 min**,
TEC26 **4.55 min**. Adding full OCR gives **11.48 / 0.63 / 4.92 min** respectively; these are
sums of measured stages, not end-to-end approval times. The staged recommendation can avoid
most of this waste: ELV A + C on p7/22/27/29 totals **122.315 s (2.04 min)**; COD A+C+D full
passes total **37.805 s (0.63 min)**; TEC26's OCR-only source rejection is **22.193 s (0.37 min)**.
These are **measured component budgets**, not a measured implementation of the future router.
Human/vision approval time is additional and was not timed. Do not promise unattended acceptance.

### Fail-closed rules

- Unknown scale/units or an unbound dimension is unresolved, never measured geometry. Do not use
  door-size guesses, render perspective, nominal print scale or `$INSUNITS` as calibration.
- Missing dimensions/material/rows remain missing; no neighboring row, first material slot or
  similarly named job supplies a default. Every source page/row is retained or explicitly excluded.
- Preserve original labels and disagreements; never silently correct the 50 mm COD chain issue.
  D112 puts album/model discrepancies before the architect. D108 concerns invariant-checked
  operations, not a new general PDF-accuracy rule; this proposal applies analogous stop-on-failure
  discipline without changing either decision.
- Empty/outline/raster/corrupt/encrypted inputs, incomplete pages and failed receipts are not a
  certificate. No `passed=true` while binding, calibration, expert ground truth or approval is open.
- Unsupported/NaN/inf/boundary values are not passing checks. Input/output/report/temp paths
  must be distinct; never overwrite inputs or another run. The throwaway runner reserves a new
  directory, refuses aliases/reused paths and verifies input hashes before/after extraction.

## Proposed follow-up issues — NOT filed

| Title | Level | Files / bounded deliverable |
|---|---|---|
| Budgeted PDF album index and region router with complete page accounting | hard | `src/dt_ai/album/`, new index/router tests; page/sheet distinction, dense-map cutoff, deterministic partial coverage |
| Dimension/level/opening binding across multiple views and independently calibrated scales | hard | `src/dt_ai/album/reader.py`, album schemas/tests; vertical chains, view-local scale anchors, independent DWG/BIM reference set |
| Page-referenced schedule/legend normalization and typed CSV export | medium | `src/dt_ai/album/`, `schemas/`, tests; merged/header/category/total rows, quantities vs length, RAL application bindings |
| Cyrillic OCR + ROI vision evaluation on a larger frozen real-source corpus | hard | album fallback adapter and benchmark fixtures/receipts; calibrated OCR model, token billing, latency, independent expert row/element labels |

## Execution, evidence and limitations

Exact commands and output locations: [`commands.md`](../../tools/research/pdf_album/commands.md).
Small per-album summaries: [`results/`](../../tools/research/pdf_album/results/).
All heavy evidence is outside git. Verified mounted-Drive copy:
`G:/Мой диск/AGR-evidence/pdf-album-research/t_5b23c219-v001/`;
77 members, 111,402,879 bytes excluding the manifest. `SHA256SUMS.txt` SHA-256:
`085698eb98e77636fdf85aca48e53a2d59d35b41f71873752b44ebdf41246bfb`.
[`evidence.json`](../../tools/research/pdf_album/evidence.json) is the machine-readable receipt.
Drive cloud-sync completion was not independently queried. Sources are not LFS assets.

Regression controls were tested first: commit `3402bbb1`, 18 failed because the prototype did
not exist; implemented runner, 18 passed. A later scorer witness (`цвет сосна, RAL 1001`)
exposed a punctuation-boundary miss: 1 failed/30 passed before separating code/numeric boundaries,
31 passed after. A hostile row-key probe then found substring matches (`1.D.170` counted as
`1.D.17`): 2 failed/2 passed; exact-cell comparison repaired both, with unchanged real-corpus
scores. Final affected/hostile controls: **42 passed** (including fresh-process CLI rejections
and actual synthetic-source mutation); no passing certificate is emitted.
The raw extraction runs are unchanged; only scoring summaries were regenerated.
The report does not claim full opening reconstruction, independent as-built truth, all-row recall,
calibrated model geometry or separately metered vision performance. These are explicitly not
certified by this research; proposed follow-ups address them rather than production changes here.

Primary references actually inspected: repository `src/dt_ai/album/reader.py` docstring and
implementation; AutoCAD console command transcripts and ezdxf readback; PyMuPDF
[`docs/page.rst`](https://github.com/pymupdf/PyMuPDF/blob/main/docs/page.rst) (`find_tables`,
`get_drawings`, `get_textpage_ocr`); pdfplumber's
[README](https://github.com/jsvine/pdfplumber) (machine-generated vs scanned limitations and
row/cell API); [RapidOCR](https://github.com/RapidAI/RapidOCR) README (ONNX CPU route).
An initial PyMuPDF documentation fetch returned 403 and a moved OCR page returned 404;
raw upstream `page.rst` and the two READMEs were fetched successfully and archived. No failed
web response is treated as vendor documentation or evidence of converter capabilities.
