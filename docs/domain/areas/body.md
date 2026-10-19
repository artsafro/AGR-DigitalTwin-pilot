# OKS BODY — L1 requirement sheet

Area: exterior surface, roof, terraces, parapets and inset slabs. Profiles: NPM / VPM;
`npm_min` / `mid` are engine profiles, not interchangeable delivery certificates.
Out: window/door construction, decor, UV/atlas and texture production, UCX construction,
Ground, derivation and packaging. Their interfaces appear only where they constrain BODY.

Readiness: [roadmap §4 and §7.1](../../research/capability-roadmap.md#4-coverage-matrix-upstream-main-ea7ecce)
records BODY at **L3** through user-accepted cases, not official AGR acceptance. L0 means no
operational coverage; L1 is rule knowledge, L2 is self-checking, L3 is user acceptance on a real
object ([definitions](../../research/capability-roadmap.md#3-readiness-levels-and-the-definition-of-done)).
This sheet adds the missing L1 index; it does not complete the BODY skill or close L2 gaps.
B01/B02/B02t cover bounded etalons; K01 remains partial. See [cases](../../cases.md) and
[current state](../../PROJECT_STATE.md). No model is built or certified here.

This is an index, not a replacement rulebook: short profile cues below route to the authoritative
text in **Detail in**. Sources use physical PDF pages, counted from one, in the
[regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf).
Project decisions are indexed in [docs/decisions.md](../../decisions.md); the task's
`docs/domain/decisions.md` does not exist. `L2 coverage` names implemented checks, not merely
planned validator stages. `none` means the complete row has no automatic check today;
manual gates remain required. Partial coverage is explicitly qualified.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| BODY-A — Architectural fidelity | reg p.4 §1.3; reg p.24 §1.3 | Approved source controls exterior | Same source and composition | Source overlays and signed V015; benchmark comparisons are not architectural sign-off | none | [Profile baseline](../npm-vpm.md#common-to-both), [manual gates](../validation.md) |
| BODY-B — Exterior scope | reg p.6 §1.3; reg p.28 §3.1; reg p.29 §3.12; [D028] | Exterior shell; visible-interior exception in BODY-L | Exterior with simplified enclosing walls/floors | Compare source inventory with output; exclude internal services and unrelated objects | none | [Geometry scope](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [Body](../../../GLOSSARY.md#body) |
| BODY-C — Usable roof belongs to OKS | reg p.7 §1.5, §3.2; reg p.28 §3.5 | Keep with owning OKS, not Ground | Keep with owning OKS | Review roof/terrace ownership and assembly before export | none | [Profile terms](../npm-vpm.md#terms), [geometry assembly](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| BODY-D — Physical scale | reg p.4 §2.1, §4; reg p.24 §2.1, §4 | 1 unit = 1 m; 1:1 | 1 unit = 1 m; 1:1 | V002 scene readback checks declared system units (UnitScaleFactor 100) and local and effective (inherited) import scale 1:1; compare source control dimensions manually | V002 (`src/twinqa/scene.py:scene_findings`, requires scene readback; source control dimensions stay manual) | [Units](../geometry.md#units-coordinates-pivots), [V002 status](../validation.md#implementation-status-inventory-static-audit) |
| BODY-E — Silhouette economy | reg p.7 §3.1; reg p.28 §3.3 | Silhouette first; atlas for minor detail | Silhouette first; allow UV-driven splits | Compare silhouette to etalon; minimality still needs manual review | `src/twinqa/geometry/checks.py:check_silhouettes` (partial: shape only), B01/B02 | [Geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [benchmarks](../../../benchmark/README.md) |
| BODY-F — Regulatory triangle budget | reg p.7 §3.6; reg p.28 §3.9; [D010] | ≤ 150 000 per OKS FBX including usable roof | ≤ 1 000 000 per OKS FBX including usable roof, excluding UCX | Count triangles after export readback; C1 table/figure discrepancy already decided by the user [D010] | V003 (`src/twinqa/scene.py:scene_findings`, requires scene readback) | [Budgets](../npm-vpm.md#vpm-appendix-2), [C1](../conflicts.md#a-inside-the-regulation) |
| BODY-G — Shared project target (mid-poly master) | [D010]; reg p.7 §3.6 | Mid-poly master ≤ 150 000 triangles per OKS FBX (user 2026-10-15, [D010]); NPM derived from it keeps ≤ 150 000 (regulatory) | VPM derived from the same master stays ≤ 150 000 by project target; 1 000 000 is the regulatory hard limit | VPM above target but within hard limit is review, not fail; follow linked fallback | V003; `tests/qa/test_scene.py::test_vpm_oks_triangles_project_target_and_hard_limit_conflict_1` | [D010 / C1, decided by the user](../conflicts.md#a-inside-the-regulation) |
| BODY-H — Perimeter below terrain | reg p.28 §3.6 | No transferred VPM OKS mandate | OKS perimeter extended down ≥ 1 m | Inspect exported perimeter against Ground; no general automatic extension check | none | [Perimeter rule](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| BODY-I — Visible faces and normals | reg p.8 §3.8; reg p.29 §3.15 | Outward, complete visible exterior | Same | Orientation checker plus reachable-view inspection; horizontal faces on closed welded components only [D133] (render-mesh partition ignored; decor isolated); open parts explicitly not checked (pilot #314), never judged with a neighbour; geometry alone cannot certify all views | `src/twinqa/geometry/checks.py:check_orientation`, `check_horizontal_faces` (partial); `tests/qa/test_orientation.py`, `tests/qa/test_horizontal_faces.py` | [Visibility](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [QA](../validation.md#general-qa-procedure-project) |
| BODY-J — Topological defect ceiling | reg p.8 §3.7; reg p.29 §3.11 | ≤ 100 duplicates/self-intersections at 0.002 m; no isolated elements or zero edges | Same | Counted per mesh after FBX readback: duplicates/self-intersections at 0.002 m against the profile limit, isolated vertices/edges/polygons and zero-length edges must be 0; definitions in the module docstring | V004 (`src/twinqa/scene.py:scene_findings` via `src/twinqa/geometry/topology.py:count_defects`, requires scene readback); `tests/qa/test_topology.py` | [Topology](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [V004 limits](../validation.md#implementation-status-inventory-static-audit) |
| BODY-K — Co-directional face clearance | reg p.8 §3.9; reg p.29 §3.13 | 5 mm–2 cm | 5 mm–2 cm | FBX readback: co-directional overlapping faces, distance distribution | V004 (`src/twinqa/scene.py:scene_findings`, "co-directional clearance": fail < 5 mm, review > 2 cm, no distance cutoff); `tests/qa/test_scene_clearance.py` | [Clearance rule](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [QA caveats](../validation.md#general-qa-procedure-project) |
| BODY-L — Interior visibility and wall thickness | reg p.8 §3.12; reg p.29 §3.12 | Simplified interior only where seen through translucent parts | Simplified walls/floors; wall thickness ≥ 10 cm | Inspect sightlines and sections; C23 shell-policy disagreement remains for the user, not resolved here | none | [Interior rule](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [C23](../conflicts.md#c-between-local-sources-project-decisionslessons) |
| BODY-M — Smoothing | reg p.8 §3.15; reg p.29 §3.14 | Project-controlled polygon smoothing | Same | Inspect normals/shading against real angles after readback | none | [Smoothing](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| BODY-N — Export triangulation | reg p.8 §3.11; reg p.29 §3.17 | Triangulated export | Triangulated export | Read back exported polygon degrees, not editable-master topology | V003 (`src/twinqa/scene.py:scene_findings`) | [Export geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [export/import](../export-import.md) |
| BODY-O — Applied transforms | reg p.8 §3.14; reg p.29 §3.18 | Applied; placement follows NPM rules | Applied; placement follows VPM rules | Readback rotation/scale checks; georeferencing is a separate manual gate | V004 (`src/twinqa/scene.py:scene_findings`, transforms only) | [Units and placement](../geometry.md#units-coordinates-pivots), [profile placement](../npm-vpm.md) |
| BODY-P — Geometry assembly | reg p.7 §3.3, §3.5; reg p.28 §3.8 | Indivisible OKS units remain separate; no geometry hierarchy | No geometry hierarchy | Inspect object graph and object ownership; type checking alone is insufficient | none | [Assembly rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| BODY-Q — Walls follow level contours | [D023]; [D028] | Use full-storey exterior contour | Same contour basis | Compare storey sections, areas and silhouettes; source classification still needs review | `src/twinqa/geometry/checks.py:check_floor_areas`, `check_silhouettes` (partial); B01/B02 | [Wall](../patterns/wall-from-contour.md), [niche](../patterns/contour-niche.md), [pattern index](../patterns/INDEX.md) |
| BODY-R — Roof plane and parapet | [D024] | Roof datum and parapet read from source | Same datum; attachments carry detail | Extractor roof confirmation; compare levels and roof/parapet to etalon | `src/dt_ai/spec/mesh.py`; `src/twinqa/geometry/checks.py:check_levels`; B01/B02 (bounded coverage) | [Parapet](../patterns/parapet.md) |
| BODY-S — Floor steps and soffits | [D043] | Build actual ledges/soffits | Same | Per-storey area, silhouette and mesh checks; preserve exterior overhang undersides | `src/twinqa/geometry/checks.py:check_floor_areas`, `check_silhouettes`, `check_mesh`; `check_horizontal_faces` only for closed welded components [D133], detached/open soffits not checked (pilot #314); `tests/qa/test_horizontal_faces.py`; B02 | [Floor step](../patterns/floor-step.md), [slab-soffit lesson](../geometry.md#job-level-rules-and-lessons-jobs-mostly-one-project-each) |
| BODY-T — Terrace and parapet | [D041]; [D042] | Spec-driven ledge, parapet and walkable part | Same | Compare walkable/cap area, silhouette and mesh to terrace etalon | `src/twinqa/geometry/checks.py:check_floor_areas`, `check_silhouettes`, `check_mesh`; B02t | [Terrace](../patterns/terrace.md), [B02t](../../../benchmark/bench-b02t-terrace/README.md) |
| BODY-U — Inset slabs | [D038]; [D039]; [D068] | Required inset joint where surrounded; solid roof exception without parapet | Same | Match hole/plate loops and spec gap/embed; reject missing joints, invalid loops and off-spec plates | `src/twinqa/geometry/checks.py:check_mesh` (`slabs_not_inset`, `plates_off_spec`); B01/B02/B02t | [Inset slab](../patterns/roof-inset-plane.md) |
| BODY-V — Opacity-plane interface / C7 | reg p.8 §3.13; reg p.36 §12.3; [D019] | No opacity-plane thickness or offset duplicate | For both-side visibility: flipped duplicate offset 0.003–0.01 m | Inspect profile-derived plane geometry; C7 shared-tool policy awaits user confirmation, not chosen here | none | [Geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [C7 — user decision pending](../conflicts.md#a-inside-the-regulation), [open choice](../conflict-choices-2026-10-09.md#c7--two-sided-alpha-planes) |
| BODY-W — Alpha interface / C8 | reg p.9 §5.5, §5.8; reg p.30 §5.1.4, §5.1.6; reg p.36 §12.2; [D020] | Separate opacity map, no image alpha | Cut-out mask in Diffuse alpha; no ERM/Normal alpha | Inspect material/plane pairing; PNG helpers alone cannot verify the complete interface; C8 confirmation stays with user | none | [UV/textures](../uv-textures.md), [C8 / C21](../conflicts.md), [open C8 choice](../conflict-choices-2026-10-09.md#c8--alpha-in-textures) |
| BODY-X — UV-driven BODY splits / C10 | reg p.31 §2.1.2; reg p.32 §6.2; [D021] | Follow NPM OKS atlas rules, not VPM density | Density-driven cuts; formula discrepancy is C10 | Compare to page image; V009 general delivery density is unimplemented; C10 remains a user decision | none | [UV rules](../uv-textures.md), [C10 — user decision pending](../conflicts.md#a-inside-the-regulation), [open choice](../conflict-choices-2026-10-09.md#c10--texel-density-formula), [cut policy](../geometry.md#project-modeling-rules-user-decisions-not-regulation) |
| BODY-Y — Scene collection ceiling | reg p.28 §3.2 | No transferred VPM layer mandate; cleanup under BODY-B | At most 1 default layer/collection | Inspect source scene collections; FBX mesh-only checks do not establish the source layer count | none | [Scene organization](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| BODY-Z — Roof screen enclosure | [D067]; [D086] | Silhouette enclosure via the linked pattern; source-module top follows source | Shell route remains blocked, not a completed capability | Check marked screen outline, roof boundary classification and unsupported-profile stop; no general VPM check | `tests/test_spec_extract.py` (screen extraction); `src/twinqa/geometry/checks.py:check_mesh` (partial: enclosure boundary classification) | [Roof screen enclosure](../patterns/roof-screen-enclosure.md) |

## Image verification and review evidence

The supplied PDF has 56 physical pages. Rendered with PyMuPDF 1.28.2 at scale 1.5 and
visually inspected: pages 4, 6, 7, 8, 9, 24, 28, 29, 30, 31, 32, 36 and 40. Reproduction:
`uv run --extra pdf-review python -c "import pymupdf; d=pymupdf.open('standards/source/Rasporyajenies19012026trebovaniya(2).pdf'); d[27].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save('body-p28.png')"`.
The repository declares `pdf-review` as an optional extra, not a dependency group;
`--group pdf-review` fails before rendering. Use the equivalent declared extra above.

The table has **26 requirement rows**. All physical quantities and the layer-count ceiling
printed in it were checked on those images, not inferred from OCR. Project-only slab dimensions and roof-classification thresholds are deliberately left
in their linked decisions/patterns: they are not numbers prescribed by the PDF.
Five numeric evidence samples (short primary-source quotes transcribed from the rendered pages,
not copied from existing rule files):

- **BODY-D**, reg p.24 §2.1: “одна условная единица измерения соответствует одному метру”; §4: “в масштабе 1:1”.
- **BODY-F**, reg p.7 §3.6: “модели ОКС и его эксплуатируемой кровли ... 150 000”; reg p.28 §3.9: “не включая объекты геометрии коллизии ... 1 000 000 треугольных полигонов”. Page 40's conflicting figure was also inspected; C1/[D010], not this sheet, selects the table.
- **BODY-H**, reg p.28 §3.6: “выдавлены вниз на расстояние не менее 1 метра”.
- **BODY-K**, reg p.29 §3.13: “не менее 5 мм и не более 2 см”.
- **BODY-L**, reg p.29 §3.12: “Толщина стен зданий должна составлять минимум 10 см”.

C10 evidence: page 32's rendered formula visibly uses division, while the OCR discrepancy is
recorded in C10. This observation does not fill the still-empty user decision in the choices
file. Likewise C7/C8 remain profile-interface references, not newly approved shared-tool policies.
No new conflict entry was needed; C1 and C23 also remain linked with their existing statuses.

## L2 gaps

Rows with `none` (11):

- **BODY-A** — approved-source architectural comparison (manual V015 today).
- **BODY-B** — complete semantic exterior/interior inventory.
- **BODY-C** — roof/terrace ownership and correct assembly with the OKS.
- **BODY-H** — OKS perimeter extension measurement.
- **BODY-L** — visible-interior scope and minimum wall thickness; retain C23.
- **BODY-M** — project-correct smoothing and shading.
- **BODY-P** — object hierarchy and indivisible-unit ownership.
- **BODY-V** — profile-aware opacity-plane geometry; retain C7.
- **BODY-W** — end-to-end alpha/material/plane pairing; retain C8.
- **BODY-X** — general delivery density and split checks; retain C10.
- **BODY-Y** — source-scene default layer/collection ceiling.

These are L2 ticket candidates, not filed tickets. Partial checks in BODY-E/I/Q/R and the
bounded B01/B02/B02t coverage do not close their manual/generalisation gaps or K01's open checks.
BODY-Z has only partial NPM coverage; its VPM shell route is still blocked by the existing issue #91.
A source-level tool inventory is not a new benchmark run or an official validation pass.

## Documentation regression check

No code or persistent test is added: this issue changes an index, not engine behavior. On the
inherited draft, the existing scene/decision/roof tests passed (67 passed, 2 deselected);
there was no honest code-test RED. An inline document probe passed 6/8 checks before edits
(after correcting a separator-count bug in the probe itself):
exactly one table with the required header, seven columns per row, sources per row, complete
`none` gap listing, existing detail-link paths, distinct hard limit/target; it failed the
roof-screen pattern/decision index and VPM layer-ceiling index. Rechecking those same eight
properties after edits passed **8/8**. Exhaustive row probes: seven columns **26/26**,
source citation **26/26**, nonempty L2 coverage **26/26**, exact `none`/gap-list match **14/14**.
This does not test model compliance.

Affected tests, before and after: `tests/qa/test_scene.py tests/test_decisions.py tests/test_spec_roof.py`
— **67 passed, 2 deselected** each time. Full suite run once with
`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_e0346c5c`:
**2708 passed, 9 skipped, 13 deselected, 48 warnings in 303.95s (0:05:03)**.
Independent docs review and user calibration acceptance remain pending.
Numeric limits, prohibitions and required joints remain requirements for future model checks,
not new guarantees implemented by this documentation-only change.
