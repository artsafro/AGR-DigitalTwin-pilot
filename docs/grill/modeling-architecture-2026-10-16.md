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

## Open questions (queue)

- Which object for the decomposition etalon: OBJ03 or the Butovskaya school; 1-2 hours of the user's time.
- Q10 follow-up: opacity in VPM for the same parts.
- Branch rename `research/grill-modeling-architecture` (NAMING.md, D078): not confirmed.
- Q11 follow-up: must the final delivery pass through Max.
- Next: Q13 how much structure a typical architect FBX / SKP keeps.
