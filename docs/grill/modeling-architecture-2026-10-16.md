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

**Q1 What is "done" for the whole project?** [D104] — agreed.
User: NPM and VPM fully match the source, pass the SINTEZ AGR Checker, and visually match the source.
Acceptance order: geometry first, by a human, visual and mathematical; SINTEZ last.

**Q2 How does pilot work reach the real repository?** [D105] — agreed (the proposal below).
User: the pilot is a sandbox so the clean original is not broken; undecided whether the pilot becomes the main
repository or core functions are carried over later.
Proposed: decide at a fixed point, not by feel - the pilot becomes main when the first vertical slice
(Ground + MAF + Flora site) is delivered; until then only `src/`, `standards/`, `docs/domain/` count as portable.

**Q3 What did autoresearch and hypotheses give?** [D106] — agreed (the proposal below).
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

**Q5 Line A (spec -> engine) or line B (reduce the source mesh)?** [D107] — agreed (the proposal below); user keeps testing approaches.
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

**Q8 The operation menu.** [D108] — agreed by the user ("I accept"), detail pending.

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

**Q10 What turns a part into an opacity plane in NPM?** [D109] — agreed.
User: repeating vertical or horizontal see-through elements - railings, metal rod / bar ladders, rods - geometry that
must stay see-through and costs many polygons because it is built from boxes.
Agreed rule: (a) + (b). The master marks such parts as opacity candidates by type (railing, rod ladder, bar screen /
grille, AC screen, fence); NPM derivation swaps candidates for opacity planes, largest triangle saving first, until
the NPM fits its budget; candidates not needed for the budget stay geometry; the report lists every swap and the
triangles saved. Open: whether VPM ever uses opacity for them (asked, not answered).

**Q11 Which DCC executes the operation library (the build kernel)?** [D110] — agreed (recommendation accepted, 2026-10-18).
Blender headless (bpy + bmesh) is the kernel: every operation and its before/after invariants run there, and each
operation is unit-tested on synthetic inputs in the cloud and CI (bpy as a Python package, `docs/research/bpy-wheel-viability.md`:
conditional GO), so workers can grow the library without the user's PC. 3ds Max stays for what already lives in it:
reading `.max` sources, the MAF and Flora libraries, and the final xView review where the team needs it. The two
exchange FBX with the mandatory readback. Open: whether the final delivery must pass through Max or only the FBX/ZIP
output counts (asked, not answered).

**Q12 Which sources arrive and how decomposition reads them?** [D111] — answered; recommendation revised, pending.
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

**Q14 The drawing album as an input.** [D127] — answered (sample sheet), recommendation pending.
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

**Q14a Who wins when the album and the 3D model disagree?** [D112] — answered.
User: in such cases the user asks the architect which is the source of truth; most often it is the album.
Consequence: the agent never resolves such a conflict. It works provisionally from the album (marked
"provisional, by album"), collects every discrepancy above tolerance into a list of questions for the architect
(value in album, value in model, place, picture), and the user forwards them.

**Q15 Order after the pause: the site slice or the operation kernel?** [D113] — agreed.
Two lines split by where they run: locally on the board after resume, the Ground + MAF + Flora site (handoff chain
#216 -> #282 -> #195 -> placement -> #217 -> verify); in the cloud, without the user's PC or DCC limits, the kernel
foundation as small tested PRs (`parts.json` format; first operations "keep", "primitive", "rebuild by contour",
"to opacity plane" with invariants; vector PDF facade reading: marks, axes, legend). Timing (user): grill every area
first, then build.

**Q16 Which object for the decomposition etalon?** [D114] — answered, changes the plan.
Candidates: OBJ03, the Butovskaya school, the 16-storey building of the sample sheet. User: all three already have
human-made deliveries that passed the checkers and were handed over.
Consequence (proposed): each object is a triple - source (3D, album, RVT where present) + delivered NPM/VPM made by
people. That is a real benchmark per object (the human delivery is the etalon, D040: never from the engine, the
README names the author). The decision etalon need not be written from scratch: the agent matches delivered parts
to source parts and proposes, per part, what the people did (kept, simplified to a primitive, rebuilt by contour,
opacity plane, texture, dropped); the user only reviews that table. Agent runs are then scored against the
delivery: silhouette and sections, triangle budget, per-part decision agreement, SINTEZ result.

**Q17 The benchmark triples: formats.** [D128] — partly answered.
User: both the delivered ZIPs and the working 3ds Max scenes exist. Open: author of each delivery (D040), where the
files live. Starting object: the 16-storey building of the sample sheet (proposed), OBJ03 second as the hard test.

**Q18 Per-operation invariants: what counts as broken geometry?** [D115] — answered, first proposal rejected.
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

**Q19 Visual acceptance.** [D125] — answered (how the user reviews); two-gate proposal not objected to.
User reviews by: Blender Face Orientation (normals); 3ds Max visual pass; each facade compared with the album;
when an FBX source exists, model vs FBX by geometry and materials, and both vs the album.
Proposed, mapped one-to-one onto that routine: gate 1 = the parts list before the build (source facade with
coloured parts, table part -> album legend item -> operation -> triangle budget, questions incl. for the
architect); between the gates only automatic checks; gate 2 = one acceptance sheet after the build: Face
Orientation renders of every view with the back-face (red) pixel count, model facades over the album sheets,
model vs source FBX overlays with the difference highlighted, a material-id render against the album legend,
sections at every level mark, a deviation table, the SINTEZ report. The user opens Max only where the sheet flags.

**Q20 Windows: library or remodel?** [D116] — agreed.
Windows are never taken from the source as is: the agent measures each opening (position, size, depth, mullion
layout) and picks a library type ("replace with own" from the menu; `opening-plane`, `library/windows/window_types.json`).
Types come from the album (legend items such as PVC / aluminium frames, the layout visible on the facade); a typical
storey reuses its types as instances. A window not in the library is a question to the user with a picture, never
a new type invented by the agent.

**Q21 Where each material's texture comes from.** [D117] — agreed.
User: yes - RAL colour plus the panel grid; the panel module is shown by the texture (joints are texture, not
geometry). Agreed: a material library by finish type (porcelain stoneware panels, plaster, painted metal, glass,
PVC frame) with procedural recipes (`technical_library/texture_tiles`: colour, panel size and joint in metres); the
agent only fills the parameters from the album (RAL, module from the facade grid); atlas / UDIM are assembled
automatically per profile (NPM embedded atlas <= 2048 without normal map [D014]; VPM UDIM 4K Diffuse + ERM + Normal);
unique finishes (mosaic, panels with artwork, printed facades) are a question to the user.

**Q22 Missing stages: UCX, lights, GeoJSON, MSK-77.** [D126] — answered.
User: UCX is made by hand, covering the model with boxes. MSK-77 coordinates come from the SPOZU: it carries the
site (GP) boundary and the drawing is in those coordinates. Lights were required: on the facade when the album shows
them, and street lamps when the site plan (GP) has them.
Proposed: these stages are code, not agent judgement. UCX: boxes / convex pieces generated per part from
`parts.json` (gap 2 mm..1 cm [D098], budget by the checker formula [D012]); the agent only confirms which parts get a
collision. MSK-77: register the model plan outline to the building footprint on the SPOZU (translation + rotation
fit), height from the album zero mark (+-0.000 = absolute mark); ties to SPOZU inventory #194 and CAD adapter #195.
Lights: facade lights from the album legend and callouts, street lamps from SPOZU points / blocks (placed like
MAF); separate light FBX with the regulation names [D017]. GeoJSON: filled from `object.json` and the album, empty
fields stay empty [D011].

**Q23 Board size, providers, budget.** [D118] — answered; recommendation revised.
First proposal: shrink to Claude / Codex implementers, Pi cheap lane, Codex reviewer; drop Cursor and Antigravity.
User: the Cursor and Antigravity subscriptions are paid; Cursor codes well, Antigravity suits documents and
summaries; not using them would be wasteful; lower the driver models so driving does not burn tokens.
Revised (agreed direction): keep the CLIs, make their drivers thin. `hermes_kanban/profiles/models.yaml` today:
Cursor lane driven by `claude-opus-5-5`, Antigravity lane by `gpt-6.1-sol`; the Pi lane already runs a thin driver
(`gpt-6-luna`, toolsets terminal + file only, project discovery off, base prompt 13.3k -> 5.6k tokens). Apply the
same pattern to the Cursor and Antigravity lanes (a small model as driver, same thin toolsets and prompt) and
measure driver vs CLI tokens per card before and after. Routing by the evaluator's per-kind table: Cursor for pure
code (tools, tests, refactors), Claude for geometry logic, procedures and Blender operations, Antigravity and Pi for
documents, decisions and summaries, Codex for code and as the reviewer. Experimenter / hypothesizer /
prompt-engineer / daily evaluator stay off until the benchmark triples exist (Q16). Budget ceiling: not asked yet.

**Q24 How questions and pictures reach the user.** [D119] — agreed: through the board dashboard.
One entry for every question: a card in "Needs you" with the short question, the options and a link to the HTML
page with pictures (parts sheet, acceptance sheet); the answer is given on the card, the agent moves it to
`docs/decisions.md` and continues; Telegram only notifies; questions for the architect are collected in one
document per object.

**Q25 Autoresearch and hypotheses: when and how.** [D120] — agreed (filter and 70/30 split accepted).
Agent proposal was an optimisation loop on the benchmark triples (one composite metric with an invariant guard,
one knob per experiment, fixed budget, no automatic merge, hypotheses only from failures, only after one triple
passes the chain by hand).
User: the point is for agents to think and propose hypotheses on how to do a task or a module better, and to
study the harness and the system as independent outside experts: "what if we come at it from this side, how do
others do it, how could we apply it here".
Proposed filter so the expert role does not feed itself (the 160-PR pattern): two separate things.
(1) Outside-expert research: output is a proposal document, not a PR; capped (e.g. top 3 proposals per area per
week); each proposal names the product number it should move (a benchmark-triple score, time per delivery, tokens
per card) and how to test it; external sources cited; the user picks on the dashboard which become cards.
Antigravity / Pi fit this lane (documents, summaries). Split proposed ~70 % product methods (modelling, decomposition,
operations, textures) / ~30 % harness and system.
(2) Experiments: only a hypothesis the user picked, tested on the benchmark triples with the loop above.

**Q26 Docs and state sprawl; context per card.** [D121] — agreed.
Measured: `hermes_kanban/profiles/COORDINATION_RULES.md` 27 KB / 40 rules (~7k tokens) read by every worker before
every card; `docs/agents/WORKFLOW.md` 29 KB, `docs/agents/CAPABILITIES.md` 46 KB, `docs/HARNESS_PLAN.md` 70 KB (Russian,
against D088); `docs/PROJECT_STATE.md` stale since 2026-10-15; STATE / HANDOFF / decisions duplicated in both repos.
Agreed: COORDINATION_RULES cut to one page of rules, incident history moved to a file workers do not read; a worker
reads AGENTS.md + its area file + the card body, the rest by link when needed; PROJECT_STATE / STATE generated by a
script from the board and git, only "next step" written by hand; finished HARNESS_PLAN sections archived, the live
plan short and in English; target base context per card <= 10k tokens, measured before and after.

**Q27 CI.** [D122] — agreed: no paid CI; local CI receipt as the merge gate; workflow switched to manual trigger.
Facts: GitHub Actions is locked for billing (every `build` on this PR fails before any step); `python-app.yml` is
broken anyway (pip + missing `requirements.txt`, Python 3.10; the project uses uv and 3.13).
Proposed: no paid CI. The merge gate is a local CI receipt: one script on the user's PC (uv sync, `uv run pytest -q
-n auto`, `dt profiles check`, `dt schemas --check`, plus the DCC tests when the change touches Max / Blender) writes
commit SHA, commands, counts and duration; the receipt goes into the PR (the board's `local-only` completion
contract already works this way). The broken workflow is switched to manual trigger (`workflow_dispatch`) so
PRs stop showing a red check that everyone learns to ignore. No self-hosted runner on a public repository.

## Last round (agent's list of what is still missing, 2026-10-18)

The user asked the agent to name what is left. Still open: (a) the baseline - how long people take per building
today, so the system's gain can be measured; (b) what happens to the 13 open PRs under the new direction;
(c) where the benchmark triples live and what the cloud can reach (it cannot reach `C:/x`); (d) workers still use
the user's own `gh` token (merge forbidden by policy only); (e) who besides the user works with the system.
Ground / MAF / Flora were grilled on 2026-10-15 (`hermes_kanban/docs/grill/`, D094-D102) and are not repeated;
Unreal and IFC stay out of scope for now.

**Q28 Baseline: how long people take per building.** [D129] — answered (no number), critical path named.
User: KPP1 was given entirely to Claude before the harness and the geometry logic were finished; Claude still
produced almost the full model (stairs not quite, some small details missed) and saved several days of work.
That is why the user builds this: tune the logic, scripts, algorithms and pipeline so an agent in a precise context
can do any of the tasks - MAF and Flora modelling, SPOZU placement, coordinates, export / import, the checker run and
fixing its errors, atlas / UDIM / texture / UV edits. The longest part by far is raising clean geometry: closed
where needed, embedded where needed, no overlaps, no gaps, no triangles where they are not needed, neat, on quads,
ready for texel density - a finished mid-poly model; atlas or UDIMs are quick after that.
Consequences: the kernel (Q8, Q11, Q18) is the critical path. The operation invariants also include quad-dominance
(no triangles where not needed) and texel readiness (quad size limits per profile, D021). Baseline to record as
"days per building by stage", approximate; the first number to collect is the time of the next real building.

**Q29 The 13 open PRs.** [D123] — agreed (first local card after resume, with live head checks).
Site line now: #273 (fix its P1 on the same branch), #239, #238 (merge main in, then merge). Checks that become
kernel invariants: #226 (co-directional clearance = z-fighting), #248 (horizontal face orientation), #228 / #230 /
#231 (UCX, mesh names) - re-check heads, merge main in, one batch with a local CI receipt. Parked, branches kept:
#279, #260, #252. Docs: #266 merge if clean; #280 merge as a record or close.

**Q29a (user's addition) The approach depends on how complete the sources are.** — recorded.
User: with Revit the agent can take the modules and the basic understanding straight away; with only an FBX it is
harder to tell what is in front of it - which part is decor, whether to detach it. Revit or FBX may hold decor in
great detail while only its silhouette, as it shapes the facade, is needed. People do not always know either: it is
analysis of the geometry - taking the dimensions and data needed so the model can then be built from them without
trouble. Without visual comparison and screenshots that is missing context: by colour and look the agent can tell
what to embed and what to make one mesh. People also decide visually, per joint, what to embed and what to merge
into one mesh, and how to make a joint so later edits stay easy.
Consequences: (1) a source tier sets the route - A: Revit + album; B: structured FBX / SKP + album; C: mesh soup +
album (split by material id, Q13); (2) an explicit analysis stage before modelling produces a measurement sheet
(sections, levels, profiles of silhouette-relevant decor, opening sizes) - the spec extractor used as the measuring
tool (Q5); (3) screenshots are a required input of decomposition, not an extra; (4) every joint in `parts.json`
carries a decision - one mesh (weld) or embed 10-20 mm - with the reason, shown at gate 1.

**Q30 Weld (one mesh) or embed, per joint.** [D124] — answered; the criterion is mesh cost.
User: decided by what welding would cost. Multi-part decor with many loops / rings would have to be stitched to the
body, cutting the body and adding edges to fit; embedding the decor into the wall avoids cutting either element and
adds no extra edges. Tile seams in geometry: usually one mesh so it unwraps together - a convenience, not a rule; an
agent may unwrap each mesh separately. A simple grid that needs no heavy cutting can be one mesh. When one mesh would
need many extra edges to keep modelling from it, that is the problem: tedious, and the mesh gets dense and hard.
Rule for the agent (proposed from this): per joint compute the extra vertices / edge loops that welding would insert
into either mesh to match the other's boundary; zero or a few on a simple grid -> one mesh (weld); more -> embed
10-20 mm and delete the hidden faces (Q18). Unwrap convenience is not a reason by itself. The count is reported per
joint at gate 1.

**Q31 Benchmark triples logistics.** — partly answered.
User: the user is the author of all three deliveries (D040 README author). Files will be given later. The user
offered to start working with the models in a cloud session.
Notes for that: the pilot repository is public, so deliveries never go into it; a cloud session can take files from
a private place (a private repository without LFS - files under 100 MB each, or a private storage the session can
download from). The cloud has no 3ds Max; Blender runs headless through the `bpy` wheel (Python 3.13 only, own
venv, `docs/research/bpy-wheel-viability.md`: FBX import / export identical to `blender.exe`, measured on Windows;
the Linux wheel is to be checked at the start). `.max` scenes cannot be opened in the cloud: they need an FBX export.

**Q32 Worker token and team.** — answered.
Only the user works with the system (no roles or separate access needed). A separate fine-grained token for the
workers is deferred.

Grilling closed on 2026-10-18 after Q32. Next: agreed items become `docs/decisions.md` lines and a card plan.

## Proposals confirmed at the end of the grilling

The proposals of Q14, Q17, Q19, Q22 and Q28 that were not explicitly accepted during the rounds were confirmed at
the end: [D125, D126, D127, D128, D129].

## Card plan (from D104-D129)

Cloud line - no DCC, no user files; each card a small PR with tests:
1. C1 Check that the `bpy` wheel works headless on Linux in a separate Python 3.13 venv (FBX import / export
   round trip, as `docs/research/bpy-wheel-viability.md` did on Windows) [D110].
2. C2 `parts.json` schema in `schemas/` (part id, source refs, class, album legend item, operation, joint
   decisions with the weld / embed reason and extra-edge count, triangle budget) [D111, D124].
3. C3 Invariant checks on synthetic meshes: open border hidden in a neighbour / below Ground / opacity plane,
   no see-through hole, no overlapping faces closer than 5 mm (reuse #226), back-face count [D115].
4. C4 First operations in bpy with C3 before / after: keep, primitive, rebuild by contour, embed into neighbour,
   to opacity plane [D108, D109, D115].
5. C5 Vector PDF facade reader on a synthetic PDF: level marks, axes and dimensions, legend items [D112].
6. C6 Local CI receipt script; GitHub workflow to manual trigger [D122].
7. C7 Context diet on the pilot side (AGENTS.md reading list, generated PROJECT_STATE) [D121]; the
   COORDINATION_RULES cut belongs to `hermes_kanban` and needs push access there.

Local line - after an explicit resume, on the user's PC:
1. L1 Open PRs by the groups of D123, live head checks, one local CI receipt per batch.
2. L2 Site chain: #273 P1 fix -> #282 rebind maps -> #195 CAD adapter -> placement -> #217 atlas -> verify [D113].
3. L3 Thin drivers for the Cursor and Antigravity lanes, tokens per card before / after [D118].
4. L4 First triple: export the working `.max` to FBX, put source FBX + delivered FBX + album PDF in a private place
   the cloud can reach (never the public pilot) [D114].
5. L5 Time the next real building by stage (the baseline, Q28).

Triple line - cloud, once L4 is done: inventory the triple; match delivered parts to source parts and propose the
per-part decision table; the user reviews it on the dashboard [D114, D119].

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
- Wrap-up: decisions D104+ and the card plan.
