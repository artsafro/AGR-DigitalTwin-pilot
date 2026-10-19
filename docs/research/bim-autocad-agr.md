# AutoCAD for AGR: choose the route by task, not by API inventory

Research card `t_c4f3e061`; scope estimate: 30–40 minutes. Repository snapshot:
`9675514` on `docs/research-bim-autocad-agr`. The orchestrator narrowed this card to
core-console scripts/AutoLISP, offline ezdxf and the repository multiCAD route;
.NET, standalone COM and ODA are brief boundary notes only.

## Summary

- Prefer offline ezdxf for deterministic plan-DXF interchange and regression checks; retain native AutoCAD for optional DWG output and a second parser.
- Use multiCAD for authorized inspection of a particular live drawing, not unattended CI or a substitute for a typed architectural extractor.
- Merged pilot PR #60 already measured serialization of B01/B02/B02t proxies; repeating its speed comparison adds little value.
- Its 21 entities preserve contours, opening rectangles and levels, not terrace geometry, arbitrary DWG semantics or a full twin.
- Highest-value next measurements are frame recovery, detection of silently omitted CAD content, and drawings independently derived from twin geometry.
- AutoCAD layers are interchange metadata, not permission to add layers/helpers to an AGR delivery mesh.
- None of these routes supplies missing MSK-77 control points, opening semantics, official acceptance or a compliant FBX package.
- This research ran only offline tests and project checks; no DCC application, MCP session or converter was launched or installed.

## Findings

### Evidence and what is new

**R — read/verified in this card:** repository code, tracked experiment evidence,
benchmark definitions and selected job states; GitHub confirmed pilot PR #60 is
merged. **H — historical execution:** measurements and live checks recorded by
previous workers, not rerun here. **D — documentation:** retrieved first-party
pages, not local runtime proof. **P — proposed:** decisions and experiments below,
not implemented capabilities. External facts use numbered sources; repository
facts name paths. This report extends, rather than replaces:

- `docs/experiments/acad-coreconsole-agr-plans.md` and
  `experiments/acad-coreconsole-agr-plans/evidence/measurements.json` (R/H).
- `docs/research/mcp-dcc-bridges.md` and
  `docs/experiments/mcp-dcc-bridges.md`: their concurrency measurements concern
  Blender, not multiCAD; do not transfer their numerical results to AutoCAD (R).
- `docs/research/revit-api-automation.md`: native Revit extraction is a separate
  route; AutoCAD interchange does not replace its model semantics (R).

**The existing measurement answers serialization, not architectural intake.**
The three fixtures are etalon-derived `spec.json` proxies. `etalon.json` stores
provenance/hashes, not vertices; #60 did not independently measure MAX/FBX etalons.
Tracked accepted evidence reports three repetitions, each with 6 closed floor
contours, 6 closed wall-plane opening rectangles and 9 level points: 21 entities,
69 coordinate records. Offline write/read median is 0.019248 s with zero deviation
against the rounded serialization input. Native write plus DWG reopen median is
3.374867 s. The separate unrounded-spec check reports maximum opening deviation
3.01824e-7 mm for B02/B02t. These are historical small-fixture observations, not
current performance guarantees or a like-for-like kernel speedup (R/H).

### Three routes and their actual boundaries

| Route | What exists here | Appropriate role | Boundary / failure mode |
|---|---|---|---|
| Core console: headless native AutoCAD 2025, SCR + core AutoLISP | External `C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad`; repository prototype emits entities with `entmake`, enumerates with `entget` | Batch copied DWGs, native save/export, independent native readback | GUI commands unavailable; ActiveX unavailable; scripts must not depend on COM `vla-*` functions.[1] Wrapper lock serializes participating batch callers only (R). |
| ezdxf: offline Python library | #60's isolated `write_dxf` / `read_dxf`, pinned at 1.4.3; not a production adapter | DXF regression files, inspect explicit entities, transform/geometry checks without AutoCAD | A DXF library, not an AutoCAD command engine.[2][8] No native DWG implementation in this prototype; the documented DWG bridge is an external ODA converter.[2] |
| multiCAD: live MCP over installed COM adapter | `tools/mcp/multicad_stdio.py`, `multicad_compat.py`, `probe_multicad_readonly.py`, `.agents/skills/autocad-mcp/SKILL.md` | Human-supervised source census, layer/block/attribute investigation, explicitly authorized versioned DWG/DXF saves | `ThreadPoolExecutor(max_workers=1)` serializes calls within one server, not across independent servers or a whole workflow (R). Exported JSON is a property summary, not complete topology (repository skill, H). |

Autodesk documents `/i`, `/s`, `/l`, `/readonly` and `/p`, core AutoLISP and
UI-independent managed/ObjectARX programs; many commands work but not all.[1]
The local wrapper constructs `/s <script> /l en-US` and optional `/i <drawing>`;
it does **not** expose `/readonly`, `/p` or `/isolate` as flags (R). Therefore use
copies, not an invented wrapper option. Its lock is
`%LOCALAPPDATA%/Temp/agr-autocad-session.lock`; it does not fence multiCAD or GUI
users. Do not run core console and live edits concurrently on the same artifact
or assume this lock owns a live document (R/P).

**Fail closed:** #60's deliberate undefined AutoLISP function returned native
exit 0 and wrapper `ok`, but an error log and no completion marker. Another SCR
produced valid files and a marker before timing out because of a trailing blank
command. Require wrapper return code, JSON status/native code, no timeout,
operation-specific marker and independent readback; file existence alone fails
these probes (R/H). Autodesk also requires robust error reporting and trusted
locations for externally loaded programs.[1] Do not disable security globally or
edit the user's profile to make an experiment pass (P).

**Do not confuse OCS, UCS, WCS and drawing units.** The ezdxf documentation says
OCS conversion is the application's responsibility and distinguishes command UCS
from stored WCS/OCS coordinates.[6] It describes `$INSUNITS` and explicit block
scales; changing a unit label is not numerical rescaling, and its broader CAD
unit explanations are explicitly based on BricsCAD experiments.[7] Here the
serializer numerically converts metres to millimetres and sets INSUNITS=4 (R).
Production source units require independent control distances, not a header-only
inference (P).

Deferred alternatives (documentation only, not evaluated implementations):

- **.NET:** a UI-independent core-console plug-in is possible; check installed update compatibility before choosing a runtime, since Autodesk's current 2025 table distinguishes .NET 8 through Update 1.3 from .NET 10 at Update 1.4+.[1][3]
- **Standalone COM:** ActiveX automation is a Windows AutoCAD interface, but is unavailable inside core console; multiCAD already wraps this live route, so another controller is not justified by current evidence.[4][1]
- **ODA:** File Converter offers CLI DWG/DXF version conversion; it is an external executable, not ezdxf's own DWG parser, and was absent in #60's historical installation check, not freshly checked here.[5][2]

### AGR task → route → evidence → open risks

Recommendations in this matrix are **P**; cited capabilities are R/H/D as marked.

| AGR task | Automation route (headless / live / offline) | Evidence | Open risks / completion criterion |
|---|---|---|---|
| Plan intake: census source layers, blocks, attributes and dimensions (IN5) | Live multiCAD for source inspection; headless core console for a repeatable copied-DWG census; offline ezdxf only after DXF conversion | `docs/HARNESS_PLAN.md` IN5 and `docs/backlog.md`; multiCAD skill lists verified inspection operations (R/H); native API boundary [1] | No production DWG-to-Spec extractor. A layer name or dimension label is not proof of an exterior wall, level or opening. Require handle/path provenance and explicit unsupported-entity inventory. |
| Closed building contours, niches and oblique corners | Offline ezdxf as initial interchange; headless native parser as compatibility gate | #60 B01/B02 contour readbacks and area comparison (R/H) | Curves, holes, disconnected rings, self-intersections and nesting were not measured. `read_dxf` consumes straight XY vertices and ignores bulge; a curved contour could be silently straightened (R). Experiment E2 targets this. |
| Level heights / source zero | Offline explicit level points and source-frame sidecar; headless DWG enumeration; live inspection of source annotations | #60 stores nine level points, including roof (R/H). KPP1 state lists 0/+3.900/+7.700/+8.650; PSU275 state separates relative zero from 169.65 absolute (R) | Parsing a number from TEXT is not level recognition. Preserve relative vs absolute elevation and source identity; do not borrow a zero mark from another job. |
| Openings on an oblique facade | Offline 3D wall-plane rectangles; headless DWG/DXF conformance; multiCAD only for inspection/context | #60 `opening_rectangle()` uses wall direction, sill and height (R/H). `jobs/REVIT-OPENINGS/STATE.md` records approximate assignments and depth/orientation problems (R) | Rectangle serialization does not determine reveal depth, family type, outward normal or whether a block is a door swing. Follow current decisions D037/D048; historical per-job examples are not a new general rule. |
| Ground / site material boundaries and placement | Headless native DWG inspection → offline normalized contours with reversible transform; live source check if ambiguities need context | `docs/domain/geometry.md` units/coordinates; `jobs/GROUND-PROJECTION/STATE.md` preserves material contours and has limited user acceptance (R) | Large offsets, OCS, nested INSERT transforms, source scale and real MSK-77 anchors. CAD conversion cannot supply missing survey/georeferencing. E1 tests synthetic frame reversibility, not geodetic validity. |
| Export review drawings from the twin | Offline DXF contour/elevation writer; headless AutoCAD for optional native DWG conversion/readback | #60 proves only Spec-derived wire serialization (R/H); ezdxf creates/reads DXF [2] | Not yet twin/mesh section extraction, a dimensioned sheet, hidden-line drawing or terrace export. E3 adds an independent mesh reference and a B02t discriminator. |
| Layouts / PDF drawing publication | Headless command/plot workflow is a candidate; live review for sheet appearance; offline rendering is a separate candidate | `multicad_compat.save()` explicitly rejects PDF (R); ezdxf documents a rendering add-on [2] | No verified project layout, font, scale, CTB or PDF plotting workflow. Do not advertise a successful SaveAs as PDF publication. Defer until a drawing deliverable is requested. |
| NPM/VPM meshes, materials, UCX and final delivery | None of these CAD routes is the delivery pipeline; keep existing mesh/FBX validators | `docs/domain/export-import.md`, `geometry.md`, `benchmark/README.md`, `docs/PROJECT_STATE.md` (R) | DXF audits and contour accuracy do not prove normals, topology, UV, FBX units, GeoJSON or manual V015–V017 gates. KPP1/PSU275 remain not officially delivered. |

## How it applies to this repository

- `src/dt_ai/intake/model.py` names DWG/DXF as intake formats; that is not an
  implemented parser. Inspection found no production CAD serializer in `src/`.
- `src/dt_ai/spec/model.py` and `Spec.expanded_floors()` supply the proxy input;
  `src/dt_ai/geometry/from_spec.py` is the mesh engine, not a drawing writer.
- `experiments/acad-coreconsole-agr-plans/experiment.py` is reusable scaffolding,
  not a proposed wholesale production dependency. Its `_as_wcs` handles some OCS
  conversion, but `read_dxf` skips unrecognized entity types and does not recurse
  INSERTs. Its native `agr-emit` reader has no general entity-frame normalization.
- The same prototype hardcodes old card id `t_3d8b70a4` in native calls. Future
  experiments must pass their own card id through the wrapper rather than reuse
  the old ownership label; do not change this on a research branch.
- `tools/mcp/multicad_compat.py` verifies save path, nonempty file, extension,
  header and hash; `open_drawing` checks active full path. These checks do not
  compare complete geometry. A hung COM call cannot be interrupted by its
  single worker; after an uncertain result re-identify the drawing, not blind replay.
- `benchmark/README.md` requires etalon → extractor → Spec, never a hand-written
  Spec presented as ground truth. E1/E2 synthetic variants must be labelled as
  such; E3 needs copied etalon geometry rather than circular writer/readback tests.
- `tools/source/measure_spec_blender.py` is a possible independent measurement
  reference for E3; do not substitute a build from Spec for the user's etalon.
- `docs/domain/conflicts.md` contains unresolved choices unrelated to CAD
  serialization. This report selects none; it does not authorize editing
  `jobs/OBJ03` or restarting its rejected `from_source` work.

### Verification performed in this research card

No DCC/native probe was executed. Local commands actually returned:

```text
uv run --with ezdxf==1.4.3 pytest -q experiments/acad-coreconsole-agr-plans --basetemp=C:/x/t_c4f3e061-tests
11 passed in 0.61s
uv run dt profiles check
OK: 3 profiles, source hash, traceability pages
uv run dt schemas --check
OK: 11 schemas
```

A separate **synthetic offline adversarial probe** wrote one closed square
LWPOLYLINE, changed its first bulge to 0.5 and added one SPLINE, then called the
existing `read_dxf` and `compare_features` against the original straight square.
Actual result: **2 model-space entities → 1 reader entity; comparator `ok=True`**.
This directly confirms both silent curve loss and skipped unsupported content in
the prototype, not in a production adapter. The temporary DXF was removed; no DCC
was involved. E2 turns this observation into a scoped experiment, not a fix here.

These are current offline harness checks, not a new native benchmark. No product
code changed, so a fail-before/fix-after regression is not applicable. The full
repository/DCC suite was not rerun; no delivery gate is claimed green.

## Proposed next tasks

The three experiments below extend #60 rather than rerun its latency contest.
They are specifications for the experimenter, **not scripts delivered by this
research**. Each requires an isolated harness plus tests; only existing wrapper
commands are shown, with generated script paths supplied by that harness.
Value/effort use S/M/L. Do not create issues from these proposals automatically.

### E1 — Recover source frames before accepting CAD contours

**Scope; value L / effort M.** Copy `object.json`, `etalon.json`, `spec.json` and
`tolerances.json` from B01/B02/B02t into a fresh per-card scratch tree. Keep originals
and copied baseline inputs hashed; generate explicitly synthetic derived CAD
variants, not edited benchmark Specs. For each fixture compare the baseline with
four variants: metre drawing instead of mm, a known 30° rigid transform with a
large synthetic offset (1,000,000 m / 2,000,000 m), a rotated UCS retaining WCS
geometry, and a non-default OCS entity normal. Record the full forward/inverse
matrix and at least three non-collinear control points. Run offline ezdxf
normalization against headless AutoLISP `trans`-based enumeration through
`dcc_batch.py acad`; no COM. Perform three repetitions per case, batching a case's
entities into one DWG. **Acceptance:** every expected contour/opening/level matched
exactly once; local coordinate and inverse-transform residual ≤0.01 mm; unchanged
closure and units after explicit rescaling; no reflection; all baseline hashes
unchanged. Include missing-unit and wrong-matrix negative controls that must reject,
not guess. Record startup-inclusive native and in-process offline times separately.
This is a synthetic precision test, not proof of MSK-77 placement.

### E2 — Detect silent geometry loss in the existing plan reader

**Scope; value L / effort M.** Starting from copies of B02/B02t contours, make six
labelled synthetic variants: one bulged segment, one ring with a hole, one nested
rotated/scaled INSERT, an unexpanded xref, a mixed supported+SPLINE drawing, and an
open contour. First demonstrate that the present narrow reader can miss content
or curvature; do not call its 21-entity baseline coverage sufficient. Compare a
raw native entity inventory (core-console SCR) with an offline inventory and a
normalized feature result. Three repetitions; preserve handles, parent chain,
entity types and explicit unsupported reasons. **Acceptance:** no unsupported
content omitted without a diagnostic; all six adversarial cases either normalize
with an independently checked shape or explicitly reject, and all three unchanged
baseline fixtures still match at ≤0.01 mm. For any supported curve approximation,
measure Hausdorff error ≤0.1 mm and area error ≤0.0001 m² against an analytic
reference; these are proposed experiment budgets, not project tolerances. Missing
xref must fail explicitly. This tests extraction robustness rather than more
native DWG save throughput.

### E3 — Distinguish actual twin-derived drawings from Spec echo

**Scope; value L / effort L.** Copy the B01/B02/B02t etalon FBX files named by
`etalon.json` into scratch, verify their hashes, and stop if unavailable rather
than manufacture etalons. Obtain an independent contour/section dump from those
copies with the existing Blender measurement approach, using only the authorized
`blender_exec.py` session wrapper on a dedicated disposable scene. Confirm Blender
5.1.2, document and units before calls; reserve the session and restore its prior
state without deleting unrelated datablocks. Project the measured level contours,
opening outlines and a labelled terrace/roof detail to DXF with ezdxf; use
`dcc_batch.py acad` to convert to a new DWG, reopen and enumerate. Compare against
the independently measured mesh sections, not only the writer's own data.
Three repetitions. **Acceptance:** B02t's terrace parapet and inset slab are
explicitly distinguishable from B02; correct opening count, orientation and
levels; section/outline errors within each fixture's copied `tolerances.json`,
serialization residual ≤0.01 mm, and no changed input hashes or residual experiment
objects. Report extraction fidelity and CAD serialization fidelity separately.
No PDF, production twin edit or official AGR delivery is included.

### Execution contract for the experimenter

Use a new card-specific absolute scratch path for every run, never `data/`, a
source DWG or an accepted output; retain a hash manifest, generated scripts, full
wrapper JSON, entity inventory, comparisons and elapsed samples. The paths below
are examples to be generated by the future harness, not existing executables:

```bash
# E1/E2/E3: one owned native stage; absolute copied input and generated SCR.
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad \
  --card <EXPERIMENT_CARD_ID> --file <SCRATCH>/read-or-convert.scr \
  --dwg <SCRATCH>/input-copy.dwg --timeout 60 --wait 30 \
  --out <SCRATCH>/native-result.json
# A separate new SCR/native invocation must reopen the NEW output for readback.
# E3 only: inspect schema, then measure via the existing live-session lock.
python C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py --help
python C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py \
  --card <EXPERIMENT_CARD_ID> --file <SCRATCH>/measure-copied-etalon.py \
  --port <CONFIRMED_AHUJASID_BRIDGE_PORT> --out <SCRATCH>/mesh-result.json
```

The offline stages use pinned ezdxf 1.4.3 as #60's baseline; fetched stable docs
identify 1.4.4, which is **not** a measured upgrade here.[2] Do not use
`blender_exec.py` to drive AutoCAD or invent an `acad` mode for it. E1/E2 need no
Blender calls. E3 additionally requires explicit authorization for opening a
fixture in the live session; unattended scene switching is not implicitly safe.
Stop after two failures of the same cause and preserve both observations.

## Open questions for the user

No answer is required to publish this research; these are future adoption gates:

1. When IN5 resumes, which real facade DWG and its known units, project zero and
   control points may be copied for validation? Synthetic experiments cannot
   approve a real MSK-77 transform.
2. Is the desired drawing output a geometry-review DXF/DWG, or a dimensioned,
   styled drawing/PDF with sheets? The latter needs separate acceptance fixtures
   for fonts, plot scale and presentation.
3. Should supported incoming curves/blocks be normalized with measured error, or
   rejected initially? E2 measures both options without silently choosing a
   production simplification policy.
4. Can E3 obtain the referenced etalon FBX copies and an exclusively owned
   disposable Blender session? If not, defer E3; do not replace etalons with an
   engine-generated reference.

## Sources

[1] https://help.autodesk.com/view/OARX/2025/ENU/?guid=AUTOCAD_CORE_CONSOLE
[2] https://ezdxf.readthedocs.io
[3] https://help.autodesk.com/cloudhelp/2025/ENU/AutoCAD-Customization/files/GUID-A6C680F2-DE2E-418A-A182-E4884073338A.htm
[4] https://help.autodesk.com/cloudhelp/2025/ENU/AutoCAD-Customization/files/GUID-E6429154-36DF-4D84-8ABC-9FCA15B66158.htm
[5] https://www.opendesign.com/guestfiles/oda_file_converter
[6] https://ezdxf.readthedocs.io/en/stable/concepts/coordinates.html
[7] https://ezdxf.readthedocs.io/en/stable/concepts/units.html
[8] https://ezdxf.readthedocs.io/en/stable/faq.html
