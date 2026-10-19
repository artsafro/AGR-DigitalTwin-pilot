# UCX L1 calibration — review / PR body evidence (#131)

## Acceptance

| Acceptance item | Evidence / status |
|---|---|
| One sheet, one table, exact seven columns | [ucx.md](../ucx.md): 18 requirement rows, R01–R18; documentation regression test |
| Every row sourced; profile placement explicit | All 18 source cells cite reg page/section or decision; all NPM cells are n/a |
| Numbers/units verified on rendered PDF images | Pages 29, 33, 34, 36, 37 rendered with PyMuPDF and opened as images; verification notes below |
| L2 coverage and gaps | Four validator-covered rows, two job-local covered rows, 12 rows with none; every none row listed under L2 gaps |
| Existing rules linked, not replaced | Compact requirement index links geometry, validation, npm-vpm and conflicts; C3 / D012 and C15 retained; no new conflict entries |
| Short area/profile/readiness header | OKS L2-partial / Ground UCX L0; adds requirement index only, no readiness promotion |
| Pipeline discrepancy recorded, not edited | Sheet Current limitations cites stage #10 and both building scripts |
| Scope | No production code, tool, benchmark, DCC execution, other area, data write or existing rule-file edit |

## Render provenance and image inspection

Source: `standards/source/Rasporyajenies19012026trebovaniya(2).pdf`,
56 PDF pages, numbered from one (not appendix-local numbers). The original five direct
page renders (including the source PDF's highlights, no OCR reconstruction) were opened
with the image reader and the rule cells visually inspected. After the LFS delivery
failure, renders are retained outside the repository at `C:/x/l1-evidence/ucx/` (not shipped).
Page numbers and verbatim quotes below are portable evidence; no PNG is required by
the sheet or tests. Tests cannot replace human image verification. `.gitattributes`
is unchanged.

The issue's example `--group pdf-review` does not work in this checkout: pdf-review
is an optional extra in pyproject.toml, not a dependency group. Successful render command:

```bash
uv run --extra pdf-review python -c 'import fitz; from pathlib import Path; d=fitz.open("standards/source/Rasporyajenies19012026trebovaniya(2).pdf"); out=Path("tmp/ucx-evidence"); out.mkdir(parents=True, exist_ok=True); [(d[n-1].get_pixmap(matrix=fitz.Matrix(1.6,1.6)).save(str(out / f"reg-p{n}.png"))) for n in (29,33,34,36,37)]; print("Rendered pages 29, 33, 34, 36, 37; pages:",len(d))'
```

For the requested literal `--group pdf-review` form, use an isolated local project
(no changes to the repository's dependency declarations). From the repository root:

```bash
python -c 'from pathlib import Path; p=Path("tmp/ucx-pdf-review/pyproject.toml"); p.parent.mkdir(parents=True, exist_ok=True); p.write_text("[project]\nname = \"ucx-pdf-review-local\"\nversion = \"0.0.0\"\n[dependency-groups]\npdf-review = [\"PyMuPDF==1.28.2\"]\n", encoding="utf-8")'
uv run --project tmp/ucx-pdf-review --group pdf-review python -c 'import fitz; from pathlib import Path; d=fitz.open("standards/source/Rasporyajenies19012026trebovaniya(2).pdf"); out=Path("tmp/ucx-evidence"); out.mkdir(parents=True, exist_ok=True); [(d[n-1].get_pixmap(matrix=fitz.Matrix(1.6,1.6)).save(str(out / f"reg-p{n}.png"))) for n in (29,33,34,36,37)]; print("Rendered pages 29, 33, 34, 36, 37; pages:",len(d))'
```

Repair rerun of the group form succeeded: `Rendered pages 29, 33, 34, 36, 37; pages: 56`.
Both forms keep all generated assets inside ignored `tmp/`.

### Five numeric rows for reviewer spot checks

Quotes below were transcribed by looking at the images, not copied from the text layer.

- **R04 — reg p.36 §13.2**, middle-page quote: “Для козырьков, заборов и ограждений, не превышающих в толщине 5 см, коллизия не строится.” Confirms inclusive <= 5 cm and limited exception scope.
- **R08 — reg p.34 §4.2**, top-of-page quote: `UCX_SM_Address_Main_Number`, `UCX_SM_Address_Ground_Number`; “число от 001 до 999”. Confirms both targets and index endpoints; it does not mandate a new sequential-numbering rule.
- **R11 — reg p.36 §13.5**, lower-page quote: “благоустройства, особенно по периметру – до 10 см”. Confirms <= 10 cm for Ground, not NPM.
- **R12 — reg p.36 §13.5**, lower-page quote: “ОКС на нижних этажах, куда, без применения спецсредств, может подойти гипотетический пешеход – до 30 см”. Confirms <= 30 cm, with stylobate/bridge/platform examples in the following lines.
- **R15 — reg pp.36–37 §13.7–13.8**, page 36 threshold and page 37 formula/cap quotes: “менее, чем 50 000 … 15 000”; image formula `n_max = n_model × 0,05`; worked example rounds `62 168,7` upward to `62 169`; §13.8 says “до 100 000”. The unconditional capped checker interpretation is **[D012] / C3**, not a claim that §13.8 alone says the same thing. Historical ADR-0002 §2 remains linked, not silently adopted over D012.

### Remaining numeric / unit checks

- R10: p.36 §13.4 visibly says “рекомендуется” and “0,02 - 1 см”: recommendation, not mandatory separation. Conversion to a tool's default is intentionally not put in the sheet.
- R13: p.36 §13.5 last bullet says “остальной геометрии ОКС – до 1 м”; distinct from centimetre limits above.
- R16/R18: reg p.29 (render inspected), §3.18 explicitly includes collision in applied transforms; §3.17 requires triangulation before FBX export. No tool epsilon is presented as a regulatory number.
- R17: reg p.33 (render inspected), continuation of §9.4: “Расположение точек отсчета объектов геометрии коллизии не имеет значения.” D018 supplies the checker exemption; no general Main-pivot limits are imported into this UCX sheet.
- R01–R07/R09/R14: p.36 image confirms targets, non-lighting per-FBX ownership, convex closed meshes without holes/material slots, mandatory non-intersection and the truncated-pyramid stair form.

## L2 follow-up inputs

12 uncovered rows: R01 target completeness; R02 Ground coverage; R03 exclusions;
R04 thin-element classification; R05 per-FBX presence; R07 slot absence; R08 internal
names; R10 advisory gap measurement; R11 Ground deviation; R12 pedestrian-zone deviation;
R13 other OKS deviation; R14 stairs. Full list is in the sheet, not newly filed tickets.
R06/R09 job-local checks need shared readback and benchmark work (T-UCX-2/3).
No new conflict entries. No open conflict decided. Pipeline status correction deferred
as requested to T-UCX-2. User calibration review and independent five-row image review
remain open; no model or official AGR acceptance is claimed.

## Test evidence

Continuation baseline (existing partial work, before edits):
`tests/test_ucx_requirement_sheet.py`: **3 passed**. Production code is unchanged.

Reproduced RED: added generated duplicate-gap probes before tightening the contract;
`tests/test_ucx_requirement_sheet.py tests/qa/test_scene.py -k ucx`:
**1 failed, 8 passed, 21 deselected** (`DID NOT RAISE AssertionError` for a duplicated
L2 gap). GREEN with the same command after requiring exactly one gap per uncovered row:
**9 passed, 21 deselected**. This is a documentation-contract regression, not a
claim of a production geometry defect. Earlier partial-work notes reported missing-sheet
RED; that run was not replayed and is not used as current evidence.

Test seam: the requested Markdown artifact, not generated collision geometry.
Generated/brute-force probes reject an absent source per row (18/18), UCX rules placed
in NPM per row (18/18), removal of each uncovered-row gap (12/12), duplication of each uncovered-row gap
(12/12), duplicate requirement table (1/1), and corruption of each numeric contract
(7/7). Together: **68/68** negative
probes. Numeric checks cover thin-element thickness, name endpoints, recommended gap,
all three deviation limits and D012's threshold/share/cap formula. They guarantee the
index's transcription, not geometric compliance of any real model.

Commands use the harness-mandated `--basetemp=C:/x/pi-t_a7553ece` rather than the
issue's alternate scratch path. Full-suite results are recorded below after execution.
Full suite (one run):
`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_a7553ece`

Final line: **2711 passed, 9 skipped, 13 deselected, 48 warnings in 304.96s (0:05:04)**.

## LFS repair verification

The five tracked PNG paths are removed from branch content; local copies remain in
ignored `tmp/ucx-evidence/`. The driver must commit deletions as a follow-up to 5c4364b.
No index mutation, commit or history rewrite was run.

Repair baseline: **3 passed**. New binary-independent evidence regression before
repair: **1 failed, 3 passed** (PNG still in the delivery directory).
Repair GREEN: **4 passed in 0.07s** with the affected-test command above.
Five generated restoration probes reject each PNG individually (5/5); existing
68/68 sheet probes remain unchanged.

Repair full suite (one invocation, same harness command above, timeout 400 seconds):
**timed out after 400 seconds**, last displayed completed marker **60%** followed by
65 passing-test dots; eight skip markers were displayed, no failure markers.
There is no final pytest summary or reliable completed-test count for this repair run;
the earlier 2711-pass result above is historical, not this repair's result. Full-suite
completion remains outstanding; no second full-suite run was started.

Only read-only git status/diff inspection was used; no git mutation or gh
operation was performed. The driver owns the PR; use this file's Acceptance table and
evidence in its body.
