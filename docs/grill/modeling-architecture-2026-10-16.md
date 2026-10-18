# Grilling: modeling architecture and system direction, 2026-10-16

Session: cloud Claude Code, read-only study of the pilot and `artsafro/hermes_kanban`, then grilling with the user
(board paused, no DCC). One question at a time; each has the agent's recommendation and the user's answer.
Status per item: **agreed** (user accepted), **proposed** (agent's recommendation, not yet accepted), **open**.
Nothing here is a `D<n>` decision yet: agreed items move to `docs/decisions.md` and issues at the end of the session.

## Facts gathered before the grilling

- 2026-10-13..16: 547 commits, about 160 merged PRs, 198 done board cards, 9 worker profiles on 5 providers.
- Size: `src/` 16.5k lines, `tools/` 18.6k, `tests/` 35.5k, Markdown docs 22k; 4446 tests, 347 s (non-DCC only).
- Merged PRs by branch prefix: improve 76, docs 28, experiment 22, harness 19, fix 9, extractor 6, job 2, library 1.
- Product: no official delivery has passed (`docs/PROJECT_STATE.md`); KPP1 and PSU275 accepted as reviewed (~90 %);
  OBJ03 unsuccessful (D079); Ground + MAF + Flora site not built yet.
- The Codex reviewer found real defects (cloned VPM, lost stable ids, MAF bottom deleted over a Ground hole).
- CI is off (billing); all green results are local runs.
- Autoresearch results: #116 tests wall time INCONCLUSIVE; #117 grader mutation score 50/55 -> 55/55 (system, not
  product); #118 Butovskaya NPM: experiment, `delivery_passed=false`, metric `silhouette_err_m2`.
- SINTEZ AGR Checker is a Blender extension (`sintez_agr_checker`, readable Python) and already runs headless:
  `jobs/KPP1/scripts/run_agr_checker.py` (KPP1 v005: VPM 64 pass / 3 fail, NPM 38 / 5, all deferred or out of scope).
  `docs/pipeline.md` stage 16 "AGR Checker pass: missing" is stale.
- Pattern `primitive-first` (D080-D084) already says: parts list first, `build_as` per part, silhouette test 0.07 m,
  user confirms the list. OBJ03 still failed under it, so the gap is execution, not the written rule.

## Round 1

**Q1 What is "done" for the whole project?** — agreed.
User: NPM and VPM fully match the source, pass the SINTEZ AGR Checker, and visually match the source.
Acceptance order: geometry first, by a human, visual and mathematical; SINTEZ last.

**Q2 How does pilot work reach the real repository?** — agreed (the proposal below).
User: the pilot is a sandbox so the clean original is not broken; undecided whether the pilot becomes the main
repository or core functions are carried over later.
Proposed: decide at a fixed point, not by feel - the pilot becomes main when the first vertical slice
(Ground + MAF + Flora site) is delivered; until then only `src/`, `standards/`, `docs/domain/` count as portable.

**Q3 What did autoresearch and hypotheses give?** — agreed (the proposal below).
User: unknown yet; needs reading and evaluation. Intent: find more efficient paths for workers and for the system,
teach agents the math and keep requirements in context.
Proposed: autoresearch pays only where evaluation is automatic and cheap; geometry is still judged by the user's
eyes, so keep it off until the first site is delivered or a trusted geometry metric exists.

**Q4 SINTEZ reports as a calibration set.** — agreed (with limits).
User: SINTEZ is a Blender plugin that loads a finished NPM/VPM archive and lists errors. It misses things: UCX gaps
above the upper bound, open polygons, flipped normals. Many reports exist, but of fixed models; no failing ones.
User will start keeping failing projects (archive + report).
Proposed: read the extension's source, list every automatic check (what, threshold, regulation item), map it to
V001-V017 (both / SINTEZ only / ours only); a report is useful only together with its archive.

**Q5 Line A (spec -> engine) or line B (reduce the source mesh)?** — agreed (the proposal below); user keeps testing approaches.
User: KPP1 and PSU275 (simple architecture) were modelled by Claude almost perfectly. OBJ03 and the school failed
(complex, multi-part). The engine did not give the agent an idea of what the geometry looks like; reduction with
visual inspection and sections worked better.
Proposed: B is how to build (look at views and sections, reduce, build in DCC); A becomes how to measure (spec
extractor sections, contours, openings, levels as numeric acceptance against the source); `from_spec` stays a
generator for simple boxes and benchmarks.

**Q6 Where did Claude break on OBJ03 / the school?** — answered.
User: everything - did not understand the parts, topology, silhouette, openings, decor; geometry broken. Often the
agent deletes polygons: holes, flipped faces, "as if gnawed". (Before the new harness and the board.)

**Q7 How the user models (the target behaviour).** — answered.
Take the source apart like a machine: what each part is, what it means, how much it affects the silhouette, its
section (multi-part, multi-segment, many-sided); then either remodel it at the needed detail or reduce it to
primitives. Pull out the body, decor, windows (remodel with own ones). Per part: keep as is, simplify, take only the
contours and rebuild (extrude, shell, cut), or detach one polygon and build from it.

**Q8 The operation menu.** — agreed by the user ("I accept"), detail pending.

| Decision per part | When | How it is built |
|---|---|---|
| Keep as is | simple, already clean and closed | copy + checks |
| Simplify to a primitive | a box / cylinder / plane holds the silhouette | fit the primitive to bbox and section |
| Rebuild by contour | complex mesh, clean section | contour -> extrude, shell or cut |
| Build from a face | the part is essentially one surface | detach the polygon -> build |
| Replace with own | windows, doors, typical elements | from the library |
| Change detail per profile | see Q9 | see Q9 |
| To texture | under 0.07-0.10 m | not geometry |

Agreed: the agent never edits the delivery mesh freehand; it only applies operations from
this menu, each a tool with invariants checked before and after (closed, no open edges, normals out, no
non-manifold); a broken invariant rolls back and stops with a question. Each part is built and checked alone;
assembly takes only checked parts. Plus a decomposition etalon: the user takes one complex object apart once, and
every approach is compared with that parts list before any build.

**Q9 "Remodel with detail" = detail per profile.** — answered.
The team models a mid-poly master aimed at VPM and derives NPM from it. After the VPM is modelled it becomes clear
that multi-part elements (railings: box after box with a box handrail, dense pickets; AC screens; vent ladders;
fences on Ground) cost many polygons; in NPM they become a plane with opacity. Sometimes detail is added, sometimes
removed. Round elements: VPM may have ~30 segments to avoid smoothing trouble, NPM ~9; so columns are modelled with
9-12 segments around from the start.

## Round 2

The user accepts every recommendation of round 1 (Q2, Q3, Q5, Q8: "proposed" -> "agreed") and comments per question
so the agent can refine it.

**Q10 What turns a part into an opacity plane in NPM?** — agreed.
User: repeating vertical or horizontal see-through elements - railings, metal rod / bar ladders, rods - geometry that
must stay see-through and costs many polygons because it is built from boxes.
Agreed rule: (a) + (b). The master marks such parts as opacity candidates by type (railing, rod ladder, bar screen /
grille, AC screen, fence); NPM derivation swaps candidates for opacity planes, largest triangle saving first, until
the NPM fits its budget; candidates not needed for the budget stay geometry; the report lists every swap and the
triangles saved. Open: whether VPM ever uses opacity for them (asked, not answered).

**Q11 Which DCC executes the operation library (the build kernel)?** — agreed (recommendation accepted, 2026-10-18).
Blender headless (bpy + bmesh) is the kernel: every operation and its before/after invariants run there, and each
operation is unit-tested on synthetic inputs in the cloud and CI (bpy as a Python package, `docs/research/bpy-wheel-viability.md`:
conditional GO), so workers can grow the library without the user's PC. 3ds Max stays for what already lives in it:
reading `.max` sources, the MAF and Flora libraries, and the final xView review where the team needs it. The two
exchange FBX with the mandatory readback. Open: whether the final delivery must pass through Max or only the FBX/ZIP
output counts (asked, not answered).

**Q12 Which sources arrive and how decomposition reads them?** — answered; recommendation revised, pending.
User: Revit ~30 %, FBX ~50 %, SketchUp ~20 %. The team does not work in Revit: a Revit model is exported to FBX
and then to 3ds Max. The Revit model is usually complete, or at least something can be pulled out of it.
First recommendation (Revit adapter first) is revised: about 80 % of inputs (and, through the team's export, the
Revit 30 % as well) reach the team as FBX/SKP mesh with whatever structure the export kept. Proposed: one
intermediate format (`parts.json` + one mesh per part) fed by a structure reader for FBX/SKP that uses every
signal the file carries (object names and hierarchy, layers / SketchUp tags, components and instances, materials,
connectivity, sections); the agent proposes the split with pictures, the user confirms (D080). When the RVT exists
the agent also reads it directly (TwinPack element meshes with categories), as enrichment of the same parts list,
even though the team itself does not work in Revit.

**Q13 How much structure does a typical architect FBX / SKP keep?** — answered.
User: usually (a) objects per element with meaningful names, or (b) objects per material or storey with everything
merged inside. In case (c) (one or two big meshes) the team detaches by material id / material and looks at the
drawing album to see what is where.
Consequence: the structure reader classifies (a)/(b) parts; for (c) its first step is a split by material id and
material, then the album is the reference for what each piece is.

**Q14 The drawing album as an input.** — answered (sample sheet), recommendation pending.
User showed a typical facade sheet ("Корпус 1. Фасад в осях 1.2-1.52", sheet 11): storey level marks for every floor,
parapet and roof-structure marks, axes with dimensions, a numbered legend of finishes with RAL colours and callouts
on the facade, a key plan. More exact than reading the picture: load the PDF into AutoCAD and take dimensions in CAD.
What this one sheet gives the agent:
- level marks: +0.000 = 212.63 absolute (zero mark for heights, pipeline stage 12); ground floor 4.5 m, typical
  storey 3.0 m (+4.500 ... +46.500, floors 2-16); parapet +53.200; roof structures +54.530, +55.200, +56.200;
- plan length: 122 129 mm between axes 1.2 and 1.52 (26 369 + 23 340 + 240 + 36 090 + 36 090);
- the legend is a parts-and-materials list: 1-5 porcelain stoneware facade panels (RAL 8022 / 7040 / 7037 / 7024 /
  8023), 6 PVC window frames, 7 aluminium frames, 8 and 16 AC baskets (16 = KORBAS KDK 3, 900 x 1200 x 610 mm),
  9 metal roof railing, 10 metal ladder, 11 triplex canopy on hangers, 12 vent grille, 13 painted plaster,
  14 metal parapet cap, 15 vent hood;
- the callouts (numbers in diamonds) place each legend item on the facade.
Proposed: (1) the legend becomes the job's material list and part classes (and Q10 opacity candidates: 9, 10, 8/16,
12); (2) a vector PDF is read directly with PyMuPDF (already an optional dependency, `pdf-review` extra): lines,
text and marks with coordinates, scaled by a known axis dimension, no AutoCAD and runs in the cloud; AutoCAD
(PDFIMPORT through the existing AutoCAD route) is the fallback for scanned or broken PDFs; (3) album marks and
dimensions become control points of the mathematical acceptance; (4) parts are labelled by rendering the model
facade in the sheet's view and scale and matching the callouts, shown to the user for confirmation.

**Q14a Who wins when the album and the 3D model disagree?** — answered.
User: in such cases the user asks the architect which is the source of truth; most often it is the album.
Consequence: the agent never resolves such a conflict. It works provisionally from the album (marked
"provisional, by album"), collects every discrepancy above tolerance into a list of questions for the architect
(value in album, value in model, place, picture), and the user forwards them.

**Q15 Order after the pause: the site slice or the operation kernel?** — agreed.
Two lines split by where they run: locally on the board after resume, the Ground + MAF + Flora site (handoff chain
#216 -> #282 -> #195 -> placement -> #217 -> verify); in the cloud, without the user's PC or DCC limits, the kernel
foundation as small tested PRs (`parts.json` format; first operations "keep", "primitive", "rebuild by contour",
"to opacity plane" with invariants; vector PDF facade reading: marks, axes, legend). Timing (user): grill every area
first, then build.

**Q16 Which object for the decomposition etalon?** — answered, changes the plan.
Candidates: OBJ03, the Butovskaya school, the 16-storey building of the sample sheet. User: all three already have
human-made deliveries that passed the checkers and were handed over.
Consequence (proposed): each object is a triple - source (3D, album, RVT where present) + delivered NPM/VPM made by
people. That is a real benchmark per object (the human delivery is the etalon, D040: never from the engine, the
README names the author). The decision etalon need not be written from scratch: the agent matches delivered parts
to source parts and proposes, per part, what the people did (kept, simplified to a primitive, rebuilt by contour,
opacity plane, texture, dropped); the user only reviews that table. Agent runs are then scored against the
delivery: silhouette and sections, triangle budget, per-part decision agreement, SINTEZ result.

**Q17 The benchmark triples: formats.** — partly answered.
User: both the delivered ZIPs and the working 3ds Max scenes exist. Open: author of each delivery (D040), where the
files live. Starting object: the 16-storey building of the sample sheet (proposed), OBJ03 second as the hard test.

**Q18 Per-operation invariants: what counts as broken geometry?** — answered, first proposal rejected.
Proposal was closure classes per part (`closed`, `open_bottom`, `plane`, `two_sided`). User: not a good option.
When one mesh is embedded into another, the face sunk into the neighbouring mesh is hidden from the viewer and is
deleted; the embedding itself exists so the border at the joint is never seen and no overlap / z-fighting appears.
So open borders are normal at every joint. The rules already exist in `docs/domain/geometry.md`: per joint either
weld (match the boundary, delete inner mating faces) or embed >= 10 mm (embed depth, not a weld tolerance), no
duplicate or coplanar overlapping faces after attach, co-directional overlapping faces 5 mm..2 cm apart
(reg p.8 §3.9, p.29 §3.13). They are written but not enforced per operation.
Revised proposal: the invariant is visibility, not closure. After each operation: (1) every open border edge lies
inside a neighbouring part (embedded >= 10 mm), below the Ground, or belongs to an opacity / glass plane;
(2) a deleted face was fully covered by a neighbour (no see-through hole: renders from many directions show no
background through the model); (3) no coplanar or near-coplanar overlapping faces closer than 5 mm (z-fighting).
"Embed into neighbour" (sink by the depth, delete the faces inside) becomes an operation of the menu with exactly
these checks. This is also the "gnawed geometry" guard: a face deleted as "hidden" that is not hidden fails at once.

**Q18a Embed depth and exceptions.** — answered.
Embed depth 10-20 mm; usually no joint where hidden faces must stay. The "embed into neighbour" operation takes a
depth in 10-20 mm and always deletes the faces it hides.

## Remaining grilling map (2026-10-18)

Modeling core: per-operation invariants and allowed exceptions; visual acceptance (what the user wants to see, where
the gate sits); windows (library vs remodel, atlas); textures / UV / atlases per profile; the missing pipeline
stages (UCX, lights, GeoJSON, MSK-77 placement). System and board: board size and providers, budget; how questions
and pictures reach the user; autoresearch on the benchmark triples; docs and state sprawl across two repositories;
CI (unlock or replace). Logistics: the rest of Q17.

## Open questions (queue)

- Q10 follow-up: opacity in VPM for the same parts.
- Branch rename `research/grill-modeling-architecture` (NAMING.md, D078): not confirmed.
- Q11 follow-up: must the final delivery pass through Max.
- Q17 rest: authors of the deliveries, where the files live.
- Next: Q19 visual acceptance - what the user looks at and where the human gates sit.
