# Blender: headless bpy automation and geometry checks

Research snapshot: 2026-10-15. Repository: `artsafro/AGR-DigitalTwin-pilot`, inspected at
`a1052e3d3a3c5ef096028fb68982e1337da4eba4`; branch `docs/research-blender-bpy-automation`.

## Summary

- Keep the existing external Python orchestrator → isolated `blender -b --python` → JSON evidence boundary; it already fits the project's separation of geometry logic and DCC I/O.
- Blender officially supports both command-line scripting and a pip-distributed `bpy` module, but their startup, executable-path and failure-handling behavior differ.[1][2]
- A `bpy` wheel is not a drop-in dependency for this worktree: the inspected 5.1.2/5.2.2 Windows wheels require Python 3.13, whereas this test run used Python 3.14.7.[23][24]
- Prefer the current subprocess-based pytest integration tests; consider wheel-based tests only in a separate, pinned environment after an approved compatibility experiment.
- BMesh supplies connectivity and winding facts, not the project's definition of an allowed open roof joint or architectural outward direction.[3] Keep those interpretations in `twinqa` and the domain patterns.
- Treat BVH intersection results as geometric evidence requiring adjacency, coplanarity, containment and intentional-embed classification, not an automatic delivery verdict.[4] The existing mesh audit explicitly does not certify intersections.
- Reuse the current spec-driven walls/openings/inset-roof implementation instead of replacing it with generic Boolean or building-generator defaults.
- Verified here: source/code inspection, PyPI metadata, GitHub code search, and non-DCC tests (1328 passed, 2 skipped, 11 deselected); no Blender installation, import of `bpy`, DCC execution or production-model acceptance occurred.

## Scope and evidence labels

Initial estimate: 40–55 minutes, one Markdown report, no production assets or code changes.
The bounded task fits: inspect representative integration/checker paths, retrieve primary documentation,
sample each requested community channel, write recommendations and validate the documentation-only diff.

- **Local/code verified:** read in this worktree; does not mean the Blender path was executed.
- **Metadata verified:** retrieved structured upstream metadata or source text, without installing/running it.
- **Source claim:** published documentation, discussion or presentation; not independently runtime-tested here.
- **Proposal:** recommended follow-up, not an implemented capability or a new modelling rule.

Project constraints read first: `AGENTS.md`, `docs/PROJECT_STATE.md`,
`docs/domain/{geometry,validation,conflicts}.md`, `docs/agents/WORKFLOW.md`, and the
`research` / `blender-mcp` project skills. This card is the background research worker envisaged by
the research skill; no further writing agent was started. Unresolved C23 (Shell) and C25 (infill recess)
remain unresolved; this report neither selects a thickness policy nor changes the window model.

## Findings

### 1. Headless execution: keep the process boundary, strengthen the contract

**Source claim.** `--background` / `-b` runs without the normal UI; `--python` runs a script,
`--` terminates Blender option parsing and leaves following arguments in `sys.argv`.
Arguments execute in order. `--python-exit-code 1` makes exceptions in command-line scripts produce
a nonzero exit; zero disables that behavior. `--factory-startup` skips the user's startup file,
and `--disable-autoexec` disables automatic drivers/startup-script execution, not the deliberately
supplied `--python` script.[1]

**Proposal, not executed here:** an existing read-only entry point can be invoked from Git Bash with
an explicit native Windows executable path:

```bash
"$DT_BLENDER" --background --factory-startup --disable-autoexec \
  --python-exit-code 1 --python tools/blender/fbx_readback.py -- \
  "C:/approved-input/model.fbx" "C:/new-version/readback.json"
```

The paths are placeholders, not known files. Use a new output path even where a legacy script itself
allows overwrite. For `.blend` inputs, load before executing code that depends on the scene, or let the
script explicitly open the file; do not load another file after building the result.[1]

**Local/code verified:** `src/dt_ai/core/build.py::run_blender` already uses an argument list,
factory startup, exception exit code, a 180-second timeout, captured UTF-8 logs, and a required result
JSON. It does not include `--disable-autoexec`; the exporter and spec-measurement documented commands
do. `adapters/blender/bridge.py` clears the scene and emits version/hash facts. It is a synthetic
vertical-slice bridge, not the general `from_spec` engine.

**Proposal:** consolidate launch policy without conflating these entry points: explicit executable,
version/build identity, isolated configuration, immutable inputs, per-run output directory, timeout,
return code, output existence/schema/hash, and a separate verdict. Reject stale pre-existing evidence;
a log marker such as `DT_BLENDER_OK` is not sufficient. Record import/export arguments alongside results.
Factory startup is reproducibility support, not an OS sandbox; scripts still require review.

### 2. `pip install bpy`: real option, separate compatibility lane

**Source claim.** The API docs link to a precompiled `bpy` package on PyPI. Module use is broadly like
background Blender, but `bpy.app.binary_path` initially is empty; import `bpy` before bundled modules
such as `mathutils`; normal CLI controls are not all available. Startup/preferences are ignored,
but a default cube/camera/light still exist until reset. Module reload is unsupported, only one
blend file can be edited per instance, and Blender's usual crash/signal handlers are not initialized.[2]

**Metadata verified, not installation:** fetched PyPI JSON with `urllib.request` and inspected
`requires_python` and wheel filenames:

| Package snapshot | Python requirement | Windows wheel tags observed | Evidence |
|---|---|---|---|
| `bpy==4.5.3` | `==3.11.*` | `cp311-cp311-win_amd64`, `cp311-cp311-win_arm64` | [22] |
| `bpy==5.1.2` | `==3.13.*` | `cp313-cp313-win_amd64`, `cp313-cp313-win_arm64` | [23] |
| `bpy==5.2.2` | `==3.13.*` | `cp313-cp313-win_amd64`, `cp313-cp313-win_arm64` | [24] |

The unversioned endpoint reported 5.2.2 as latest at retrieval; this is a dated metadata observation,
not a recommendation to upgrade.[20] The fetched `latest` manual identifies itself as Blender 5.2 LTS;
project `docs/agents/CAPABILITIES.md` records a previous fixture run on 5.1.2. Do not infer local
installation/version from either document.[1]

**Local/code verified:** `pyproject.toml` allows Python `>=3.12`, pins the core/test dependencies,
and has no `bpy` dependency. `uv run` selected CPython 3.14.7 in this worktree. Thus the inspected
4.5.3 wheel does not fit the project's Python floor, and the inspected 5.x wheels do not fit this
interpreter. The project's pinned NumPy and other native dependencies also need an explicit solver
check against any proposed wheel environment; compatibility was not tested here.

**Proposal:** retain executable-based Blender 5.1.2 compatibility as the documented baseline to
reverify, not as a newly certified runtime. If useful, create a separate Python-3.13 wheel spike pinned
to the same Blender patch and compare geometry/FBX behavior. Do not add `bpy` to core requirements,
upgrade the DCC, or change the lockfile in a documentation card.

### 3. Testing bpy code with pytest: distinguish three levels

1. **Pure Python (current default lane):** spec interpretation, NumPy/Shapely geometry, tolerance
   rules and report grading outside Blender. Local examples: `tests/qa/test_from_spec.py`,
   `src/dt_ai/geometry/from_spec.py`, and `src/twinqa/geometry/checks.py`.
2. **Host pytest → Blender subprocess (current integration lane):** pytest creates a synthetic
   fixture, calls an explicit Blender executable, then asserts saved/reopened/exported evidence.
   Examples: `tests/integration/test_pipeline.py`, `tests/qa/test_from_spec.py`,
   `tests/qa/test_clearance.py`; markers `dcc` and `blender` are declared in `pyproject.toml`.
3. **pytest inside Blender / wheel Python (optional):** the `pytest-blender` project documents
   launching tests in Blender's bundled Python; dependencies must be available in that interpreter.[6]
   Its fetched `run_pytest.py` calls `pytest.main(...)` and returns the status through
   `SystemExit(main())`. Its add-on installation/cleanup helpers can save preferences and uninstall
   add-ons, so enabling those helpers against a user's normal configuration would need isolation.[13]

**Local/code verified:** `tests/dcc/connect_readback.py` is a standalone Blender script, not a normal
pytest test module. It asserts coordinates, quads, face attributes and normals after `.blend` reopen,
and explicitly reports `delivery_passed=False`. Do not replace that evidence with a mocked `bpy` pass.

**Proposal:** keep separate unit, native integration and export-readback results. A future Blender-side
pytest wrapper must explicitly propagate the pytest return code; failing tests need not raise an
uncaught Python exception. Use synthetic negative cases: reversed face, inverted disconnected shell,
missing face, wire edge, vertex-only bow tie, transverse crossing, coplanar duplicate, concave quad,
negative/nonuniform scale, stale JSON, missing output and corrupt FBX. Expected allowed cases include
an inset-roof joint, intended bottom ring, valid adjacent faces and a labelled embed.

**Source claim / video coverage:** Andreas Gajdosik's BCON 2023 talk, *Test, Build, Release:
Streamlining Add-On Development with Automation*, describes headless Docker testing and automated
build/release workflows; the official abstract and YouTube page description were retrieved.[11][21]
Only page text/description and an indexed transcript excerpt were inspected, not the complete video
or its demonstrations. Its useful transfer is version-matrix and integration-test organization,
not proof that the project's Windows/FBX paths work.

### 4. BMesh topology: measure first, classify with project rules

**Source claim.** BMesh exposes connectivity, `BMEdge.is_boundary`, `is_wire`, `is_manifold`,
`is_contiguous`, linked faces and vertex manifoldness. Face/edge indexes may become dirty after edits;
`index_update()` updates index values and `ensure_lookup_table()` enables indexed sequence access.
`normal_update()` refreshes normal values, while `calc_volume(signed=True)` permits signed volume.[3]
A Python-owned BMesh can be populated from a mesh, inspected without writing it back, then explicitly
freed. Edit-mode meshes instead use `from_edit_mesh` and `update_edit_mesh`; the ownership models
must not be mixed.[16]

**Proposal:** a read-only adapter should record, separately:

| Observation | Suggested measurement | Why a single “non-manifold” count is insufficient |
|---|---|---|
| Wire / loose elements | Edges with no linked faces; unused vertices | Not the same defect as an open shell |
| Open edges | One linked face; assemble boundary cycles | Roof and base loops can be intentional |
| Multi-face edges | More than two linked faces | Detects branches/internal mating faces |
| Vertex singularities | Manifoldness / connected face fans at a vertex | Edge-only counts miss point-touching shells |
| Inconsistent winding | Two-face edge with incompatible winding (`is_contiguous`) | Consistency does not establish outward direction |
| Degeneracy and master face shape | Area, edge lengths, face degree, planarity and projected self-crossing | `Mesh.validate()` is not an architectural QA checklist |

The API says `Mesh.validate()` returns true when invalid geometry was corrected/removed.[19]
**Inference:** call it on a disposable copy if an audit must preserve the inspected datablock; do not
silently repair the very evidence being measured. The exporter already treats repairs as failure.

**Local/code verified:** `technical_library/mesh_audit/core.py::inspect_mesh` counts incidence,
components, rounded duplicate vertices, duplicate vertex-set faces, fan area and loose elements.
It sets `intersection_test_performed=False`, `delivery_passed=False`. Its Blender front end explicitly
limits scope to raw saved meshes and checks source-file hash stability. In contrast,
`src/twinqa/geometry/checks.py::check_mesh` welds a dump using its configured tolerance, detects vertex
fans, classifies allowed loops and checks inset slab parameters; these are different measurement
policies, not interchangeable counts.

The mandatory paired inset-slab loops in `docs/domain/patterns/roof-inset-plane.md` are a direct reason
not to require zero boundary edges everywhere. Keep raw and tolerance-welded counts distinguishable;
never “fix” the model by globally welding at the rule-check tolerance.

### 5. Normals: winding, outwardness and shading are different checks

**Source claim.** `normal_update()` recomputes normals from geometry; BMesh also offers
`recalc_face_normals`, a geometry-changing operation rather than a read-only diagnostic.[3][25]
The mesh API distinguishes face/vertex data from corner normals affected by sharp/custom-normal
settings.[19]

**Proposal:** measure unchanged geometry first. Check winding along shared edges, then classify
orientation per connected component using the expected facade/roof/opening directions from the spec.
For a demonstrably closed, consistently oriented, non-self-intersecting component, signed volume is
a useful additional signal, not a universal test for open facade sheets. Never use one summed volume
for unrelated components: it can hide an inverted small component behind a positive larger one.
Recompute geometric normals from transformed triangle coordinates to handle reflection/nonuniform
scale; test a mirrored fixture explicitly. Record shading/custom-normal concerns separately from
face winding. These are design recommendations, not a Blender run result.

**Local/code verified:** `_Mesh.quad(..., facing)` in `src/dt_ai/geometry/from_spec.py` selects winding
with a cross-product dot expected direction. The Connect readback fixture checks `normal.z > 0` for
its horizontal synthetic faces only. Neither proves arbitrary imported decor is outward-facing.
`docs/PROJECT_STATE.md` still requires normals, topology on every mesh including decor, independent
checking and user visual review before a new model is reported passing.

### 6. Self-intersections: BVH helps, but no one-call delivery certificate

**Source claim.** `BVHTree.FromBMesh`, `FromPolygons`, `overlap`, `ray_cast` and nearest queries are
available; `overlap` returns index pairs, and `epsilon` enlarges the hit threshold.[4]
A Blender StackExchange example fixes incorrect cross-object comparisons by transforming each
BMesh with its object's `matrix_world`. The page includes old Blender code and discussion of
edge/vertex contacts; it is a cautionary example, not a current-version test.[5]

**Proposal:** triangulate an audit copy (preserve triangle → original polygon/object IDs), express
all compared geometry in one coordinate frame and use BVH results as candidate evidence. For a
self-query, normalize/deduplicate pairs and ignore identity pairs; classify same-source-polygon
triangles and shared-edge/vertex contacts rather than treating them as collisions. Do not discard
all adjacent pairs indiscriminately: adjacent faces may fold through one another away from their
shared boundary. Measure noncoplanar interior intersections separately from coplanar projected-area
overlaps and near-parallel clearance. Test containment separately for UCX: a wholly nested closed
volume need not have a surface-crossing pair. A zero hit count is not a containment verdict.

**Local/code verified:** the inspected `check_mesh` overlap path calls `near_parallel_overlaps`, not
a general transverse triangle-intersection test. `docs/domain/validation.md` explicitly distinguishes
coplanar area, nonparallel crossings and allowed embeds; `technical_library/mesh_audit/blender.py`
explicitly excludes intersection certification. A general all-mesh intersection/winding checker is
therefore a follow-up, not a capability established by the current structural FBX readback.

Do not reuse `weld_m`, BVH epsilon, regulatory duplicate distance, minimum clearance and embed depth
as one tolerance: they answer different questions. Acceptance thresholds remain in the project's
profiles/patterns; no new universal tolerance is proposed here.

### 7. Procedural walls, openings and roofs: retain the spec engine

**Metadata/code verified upstream:** `ranjian0/building_tools` advertises floorplans, floors,
doors, windows and roofs.[12] Its window code subdivides a wall face, builds an inset frame,
adds depth/material groups and eventually calls global `remove_doubles(..., dist=0.0001)`.[15]
Its roof code includes flat/gable/hip branches, extrude/inset operations and a straight-skeleton
route; it explicitly handles some concave-outset failures by showing a “Roof Intersection Detected”
message and continuing.[14] These are implementation ideas, not AGR-compliant defaults.

GitHub search was exercised: `gh search code` returned empty results even for known repositories;
`gh api -X GET search/code -f q='extrude_face_region repo:ranjian0/building_tools'` returned nine hits,
including `btools/utils/util_mesh.py`, `btools/building/frame.py` and `btools/building/arch.py`.
Repository trees and the window/roof source were then read directly. Upstream heads observed:
`building_tools` `0216534645b15b3f8aac0bd1d7e6674e2972b9b3`;
`pytest-blender` `2f1355473c60c73d24616b6081352fc05fd3e741`.
The cited `master` source URLs can move; these SHAs identify the inspected snapshot.

**Source claim.** Blender's Boolean manual warns that proper results are guaranteed only for manifold
meshes; solver choices have different support/performance properties, and the Manifold solver does
not generally accept non-manifold input. Exact has self-intersection/hole-tolerance options.[18]
**Inference/proposal:** a Boolean cut is not a guarantee of the project's all-quad editable master,
correct material provenance, stable opening IDs or allowed seam layout. Do not route the project's
intentionally open shell through a closed-solid assumption merely because a tutorial uses it.

**Local/code verified:** `src/dt_ai/geometry/from_spec.py` already builds contour walls, recessed
opening planes/reveals, parapets, floor steps, terraces and inset slabs outside Blender; its header
lists supported geometry and explicit `BuildError` stops. Its later `_Mesh.tri` support also means
“all generated output is always quads” would be too broad a claim. Export is a separate operation.
The pattern documents govern seat depth and inset joints; generic window-generator depths or roof
outsets cannot override them. C23 remains open: do not add automatic Shell/Solidify. C25 remains
open: do not select a detailed infill recess from a third-party example.

### 8. Windows and context pitfalls

- **Source claim:** operators consume Blender context and may fail `poll()` because of mode,
  selection, active object or editor requirements.[9] **Proposal:** prefer data API/BMesh for mesh
  construction; retain operators for file I/O with explicitly tested context. A viewport-area
  override is not an option when no such UI exists.
- **Source claim:** Python integration is not thread-safe; persistent Python threads can crash
  Blender, and independent work should use separate processes instead.[10] **Proposal:** parallelize
  independent Blender processes, never concurrent mutations of one scene via threads/MCP.
- **Source claim:** evaluated dependency-graph objects include modifiers/constraints; temporary
  `to_mesh()` results require `to_mesh_clear()`.[17] **Local/code verified:**
  `tools/source/measure_spec_blender.py` follows that evaluation/cleanup route;
  `technical_library/mesh_audit/blender.py` deliberately reads raw `obj.data` instead. Label which
  representation an audit covers; modifiers and instances require explicit scope.
- **Source claim:** the pip module uses a different interpreter/configuration boundary than an
  installed executable.[2] **Local observation:** do not assume the host `pip`, `python`, `uv`
  interpreter or Blender's bundled Python are identical. This worktree's test runtime was 3.14.7;
  wheel requirements are listed above, not experimentally resolved.
- **Local observation:** Git Bash/native Windows path conversion mattered even without Blender.
  Inherited `MSYS_NO_PATHCONV=1` / `MSYS2_ARG_CONV_EXCL=*` caused native Python to receive `/c/...`
  fixture paths as `C:\c\...`. Removing only those variables for the pytest invocation fixed the
  four shell-double failures. Do not extrapolate that workaround to all launchers: native Python
  subprocess argument lists should continue to use `C:/...` paths; quote executable paths with spaces.
- **Source coverage / community:** the fetched r/blender thread contains conflicting advice about
  external scripting and module use; current official API documentation, not a commenter, establishes
  the supported pip module.[7][2] The r/blenderhelp search snippet reports background GPU selection
  trouble; full extraction returned empty and direct Reddit JSON returned HTTP 403.[8] This is only
  a search-snippet anecdote, not verified device behavior or a recommended GPU fix. Geometry QA
  should not grow a rendering dependency on that basis.

## How it applies to this repository

All observations below are from code/document reads, not new DCC execution.

| Current path | Observed role / limitation | Action suggested by the findings |
|---|---|---|
| `src/dt_ai/core/build.py`, `adapters/blender/bridge.py` | Synthetic bundle launcher/export/audit; process and JSON boundary already present | Add explicit launch/isolation/version/evidence contract, preserving synthetic scope |
| `tools/blender/fbx_readback.py` | Structural FBX counts, transforms, UV/image facts; reports scope, not verdict | Keep structural facts separate; add topology/orientation evidence via a distinct checker |
| `tools/blender/export_faces.py`, `src/twinqa/clearance.py`, `tests/qa/test_clearance.py` | Face/clearance route; synthetic 3 mm FBX test exists | Preserve parallel-clearance tests; add transverse and containment cases separately |
| `technical_library/mesh_audit/{blender,core}.py` | Read-only raw-mesh inventory, source hash check, intersections explicitly not certified | Extend evidence schema without changing legacy counts into a blanket pass |
| `tools/source/measure_spec_blender.py` | Evaluated mesh dump, world coordinates, polygon sizes, material/UDIM facts | Version the representation contract; consider original polygon IDs/instance provenance |
| `src/dt_ai/geometry/from_spec.py` | Existing pure geometry engine; explicit unsupported-case stops | Reuse walls/openings/slabs; do not introduce a competing generic generator |
| `tools/export/export_mesh_blender.py` | Versioned diagnostic mesh/.blend/FBX export, material validation; includes LEVEL empties | Do not confuse benchmark exchange with final mesh-only triangulated delivery |
| `src/twinqa/geometry/checks.py`, `tools/qa/check_geometry.py` | Pattern-aware mesh grading, loops, welded fans, near-parallel overlaps | Add independent normal/transverse checks without relaxing existing inset rules |
| `tools/body_shell_blender.py`, `tests/dcc/connect_readback.py` | Saved/reopened synthetic topology/provenance assertions | Reuse fixture style; do not apply Shell policy from a fixture to an unresolved building |
| `tests/qa/test_from_spec.py`, `tests/integration/test_pipeline.py`, `pyproject.toml` | Pure and explicitly marked native integration lanes | Keep separate result totals; require a native lane for claims about Blender behavior |
| `docs/domain/patterns/{wall-from-contour,opening-plane,roof-inset-plane}.md` | Architectural contract, plane seat, mandatory slab seam | Pattern rules outrank tutorial defaults; allowed openings need semantic classification |
| `docs/domain/{geometry,validation,conflicts}.md`, `docs/PROJECT_STATE.md` | Scope/tolerances, readback/manual gates, open C23/C25, no official passed delivery | Keep `not_run`/review states; no new delivery acceptance in this research |
| `docs/agents/CAPABILITIES.md`, `.agents/skills/blender-mcp/SKILL.md` | Historical 5.1.2 MCP fixture coverage; CLI/rendering not established by it | Do not launch MCP/CLI under this card or promote historical coverage to current proof |

## Proposed next tasks

No issues or follow-up cards were created. Sizes below are relative planning estimates, not time promises.

### A. Unify isolated Blender launch and evidence contracts — value L / effort M

Inventory current launchers and introduce one reviewed subprocess policy with explicit executable/version,
configuration isolation, autoexec disabled, timeout/log retention, immutable source and fresh output checks.
Add pure subprocess-double tests for missing/stale JSON, nonzero exit, exception and timeout, plus an
opt-in synthetic native smoke test on the approved Blender version. Preserve each entry point's scope.

### B. Close all-mesh orientation and topology blind spots — value L / effort M

Extend the independent geometry QA lane to cover body and decor with stable object/polygon IDs,
raw versus welded counts, face-fan singularities, component winding and spec-facing normals. Include
reversed decor, point-touching shells and intentionally open roof/base fixtures; fail the defect cases
before implementing the checker and verify native readback separately. Coordinate with the existing
#117/#126 blind-spot work rather than duplicate it.

### C. Classify transverse intersections, coplanar overlaps and containment — value L / effort L

Add a candidate-search plus narrow-classification checker preserving source face IDs and measured units.
Cover self/inter-object crossings, same-polygon triangulation, adjacent folded faces, exact contacts,
intentional embeds, concave polygons and nested UCX volumes. Report each category separately with
configurable existing profile tolerances; do not convert BVH overlap counts directly into compliance.

### D. Establish a pinned Windows native QA matrix — value L / effort M

On explicit authorization to execute Blender, verify the documented baseline and one proposed target
version with the same synthetic save/reopen, material/UV/normal and FBX roundtrip fixtures. Capture
executable/build/Python versions, arguments, logs, output hashes and skipped checks. Include spaces in
paths and native versus Git Bash launchers. Keep rendering/GPU tests a separate optional lane.

### E. Evaluate a separate bpy-wheel testing environment — value M / effort S

Resolve a disposable Python-3.13 environment against an exact matching 5.x wheel, inspect native
NumPy/dependency compatibility, and compare a minimal geometry/readback fixture with the executable.
Check FBX operator availability rather than assume parity. Produce a go/no-go recommendation; do not
modify the main Python floor or core dependency graph until the user accepts the result.

### F. Extend procedural geometry only through accepted patterns — value M / effort M

Choose one actually blocking unsupported contour/opening/roof case, identify its existing benchmark
and pattern contract, and implement a pure geometry fixture before adding a Blender readback check.
Use Building Tools as algorithm reading material only; do not adopt its global weld or roof failure
behavior. Work requiring Shell or detailed infill recess stays blocked pending C23/C25 decisions.

## Open questions for the user

These do not block publishing this research; they gate optional future execution/model changes.

1. Which exact executable/build should the next native QA task certify: reverify the documented 5.1.2
   baseline only, or also evaluate a 5.2.x target? No installed version was checked or changed here.
2. Is a separate `bpy` wheel compatibility experiment worth maintaining, or should the executable-only
   route remain the sole supported native test environment?
3. For future Shell or detailed-window work, resolve C23 and C25 in the existing decision process;
   this report proposes no thickness/recess value and does not reopen the already decided C24 seat.

## Verification performed and remaining limits

- Read representative integration, export/readback, procedural-engine, mesh-audit and checker files;
  searched `blender` / `bpy` throughout the tracked code/docs. The search is discovery, not an audit
  of every legacy object script. `docs/agr/` originals were not opened directly.
- Retrieved official manual/API pages, PyPI JSON, two upstream repositories' source and head SHAs,
  StackExchange discussion, r/blender text and BCON/YouTube page text. r/blenderhelp full-text access
  failed (empty extraction, then HTTP 403); only the labelled snippet is used.
- Ran non-DCC verification, deliberately excluding both native markers so automatic executable
  discovery cannot launch Blender:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL \
  uv run pytest -q -m 'not blender and not dcc' \
  --basetemp 'C:/Users/artsafro/.hermes/profiles/dt-worker-codex/cache/scratch/pytest-bpy-research'
uv run dt profiles check
uv run dt schemas --check
```

Result: **1328 passed, 2 skipped, 11 deselected**, one expected duplicate-ZIP-member warning,
118.64 seconds; **3 profiles** and **11 schemas** checked successfully. The initial invocation under
inherited path-conversion suppression returned 4 failed / 1324 passed / 2 skipped / 11 deselected;
the corrected invocation passed without code changes. This is an environment correction, not a
red/green code-regression claim; this research changes no implementation and adds no regression test.
An unrestricted `uv run pytest -q` was intentionally not used because it can launch Blender on discovery.

No Blender executable, pip `bpy`, MCP scene, export/import or rendering path was run. No official
model/delivery, performance number or Windows GPU configuration is certified. A later native task
must supply that evidence; a green non-DCC suite cannot supply it.

## Sources

[1] https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html
[2] https://docs.blender.org/api/current/info_advanced_blender_as_bpy.html
[3] https://docs.blender.org/api/current/bmesh.types.html
[4] https://docs.blender.org/api/current/mathutils.bvhtree.html
[5] https://blender.stackexchange.com/questions/71289/using-overlap-to-check-if-two-meshes-are-intersecting
[6] https://github.com/mondeja/pytest-blender
[7] https://www.reddit.com/r/blender/comments/1c00dda/can_blender_be_scripted_from_the_outside
[8] https://www.reddit.com/r/blenderhelp/comments/y0bifz/background_render_not_utilizing_gpu
[9] https://docs.blender.org/api/current/info_gotchas_operators.html
[10] https://docs.blender.org/api/current/info_gotchas_threading.html
[11] https://conference.blender.org/2023/presentations/1873
[12] https://github.com/ranjian0/building_tools
[13] https://raw.githubusercontent.com/mondeja/pytest-blender/master/pytest_blender/run_pytest.py
[14] https://raw.githubusercontent.com/ranjian0/building_tools/master/btools/building/roof/roof_types.py
[15] https://raw.githubusercontent.com/ranjian0/building_tools/master/btools/building/window/window_types.py
[16] https://docs.blender.org/api/current/bmesh.html
[17] https://docs.blender.org/api/current/bpy.types.Depsgraph.html
[18] https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/booleans.html
[19] https://docs.blender.org/api/current/bpy.types.Mesh.html
[20] https://pypi.org/pypi/bpy/json
[21] https://www.youtube.com/watch?v=5n1_6SvU-_E
[22] https://pypi.org/pypi/bpy/4.5.3/json
[23] https://pypi.org/pypi/bpy/5.1.2/json
[24] https://pypi.org/pypi/bpy/5.2.2/json
[25] https://docs.blender.org/api/current/bmesh.ops.html
