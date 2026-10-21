# EngiWorld benchmark fit for the AGR-DigitalTwin pipeline

Status: research report (no code changed)
Date: 2026-10-21
Sources: arXiv:2609.37686 (v2), https://engiworld.github.io, GitHub `Hongcheng-Gao/EngiWorld`,
Hugging Face `HongchengGao/EngiWorld-Tasks` / `EngiWorld-Images`. All links verified on this run.

## TL;DR

EngiWorld is fully public (MIT): all **1,301 tasks, their per-task graders (`eval.py`), and the GUI/CLI
evaluation runtime** are on GitHub and Hugging Face. It evaluates agents **artifact-centrically**: each
grader re-opens the submitted file and programmatically checks geometry, topology, entities and rule
compliance — exactly the "re-open, don't trust `done`" discipline our checkers use. The subset that maps
to our pipeline (BIM + 3D modelling/export) is **~365 tasks**. Our toolchain can run a meaningful slice
of it **without their Docker/VM harness**, by re-using their public verifiers against our own outputs:
the **Blender** and **IFC/Bonsai** graders are standalone `bpy`/`ifcopenshell` scripts, and **Revit 2025
is the exact version EngiWorld uses**. Recommendation: **adopt ~20 verifiers** (Blender CLI + Bonsai IFC +
Revit IFC) as a public external eval next to #391, not the full 1,301-task suite.

## 1. What is public

| Item | Public? | Where |
|---|---|---|
| Paper (v2) | yes | https://arxiv.org/abs/2609.37686 |
| Project page | yes | https://engiworld.github.io |
| Code + runtime (engine, verifiers, scheduler) | yes, MIT | https://github.com/Hongcheng-Gao/EngiWorld (`runtime/`) |
| All 1,301 task definitions (`task-*.json`) | yes, MIT | GitHub `task/` + HF `EngiWorld-Tasks` |
| Per-task graders (`eval.py` + `ground_truth/` + `init_file/`) | yes | GitHub `task/` (drawings/init files included) |
| Complete task data (all 1,301 incl. large resources) | yes | HF `EngiWorld-Tasks`, ModelScope mirror |
| Environment images (15 VMs, ~98 GB compressed `.qcow2`) | yes | HF `EngiWorld-Images`, ModelScope |
| Licence | MIT (code/tasks); component licences in `THIRD_PARTY_NOTICES.md` | repo |
| Paper licence | arXiv non-exclusive-distrib 1.0 (not open-source) | arxiv abs page |

The main-experiment subset is **306 tasks** (158 CLI + 148 GUI) listed in `task/splits/main-306.txt`.
Full counts per task type: Single-Software Execution **931**, Software Selection **140**, Vision-Guided
Modeling **120**, Design Optimization **40**, Cross-Software Coordination **60**, Open-Environment
Engineering **10** (= 1,301). Interfaces: **691 CLI + 610 GUI**.

### Required software (26 applications, 6 domains)

| Domain | Software (version) | OS | Interface |
|---|---|---|---|
| CAD (7) | FreeCAD 0.21.2, AutoCAD 2024, SolidWorks 2025, BRL-CAD 7.32.2, OpenSCAD 2021.01, LibreCAD 2.2.0.2, SolveSpace 3.1 | Ubuntu / Windows | CLI / GUI |
| CAE (7) | ANSYS 2026 R1, Abaqus 2025 LE, OpenFOAM 11, FEniCS, CalculiX 2.21, FLORIS 4.6.4, OpenFAST 5.0.0 | Ubuntu / Windows | CLI / GUI |
| CAM (2) | FreeCAD Path 0.21.2, SolidCAM 2025 | Ubuntu / Windows | CLI / GUI |
| **BIM (4)** | **Revit 2025** (Win, CLI/GUI), **Archicad 27** (Win, CLI/GUI), **Bonsai 0.8.5** (Ubuntu, CLI/GUI), **OpenStudio 1.11.0** (Ubuntu, CLI/GUI) | — | — |
| EDA (4) | Cadence OrCAD 24.1, EAGLE 7.7.0, Altium Designer 17, KiCad 10.0.2 | Ubuntu / Windows | CLI / GUI |
| **DCC (2)** | **Blender 4.2.3** (Ubuntu, CLI/GUI), **ZBrush 2025** (Win, GUI) | — | — |

Note: EngiWorld's DCC domain is **Blender + ZBrush only — 3ds Max is absent**. The full runtime launches
Windows/Ubuntu **VMs through Docker on an x86_64 Linux host** (Python 3.10, Docker Engine, `zstd`, optional
KVM); GUI tasks are driven by mouse/keyboard + screenshots, CLI tasks by terminal commands.

## 2. How tasks are verified (artifact-centric)

From the paper §3.4 and Appendix 7.1:

> Each verifier reopens the submitted files, extracts the properties required by the task, and checks them
> against structural requirements or tolerance-bounded numerical criteria. The checks cover geometric
> dimensions and topology, simulation quantities, schematic connectivity, building-model entities and
> relationships, and 3D scene structure. … Missing, invalid, or unreadable files fail the corresponding
> criteria. Neutral formats such as STEP, DXF, and IFC are re-imported, so export errors affect the result.

Key properties:

- **Binary tasks** (all but Design Optimization): task *i* has *K_i* acceptance criteria, each a binary
  indicator φ ∈ {0,1}; the task passes **only if every criterion passes** (product of indicators).
- **Design Optimization** (40 tasks): two-stage — first all hard feasibility constraints ψ must hold, then a
  task-specific quality score q ∈ [0,1] (normalized between a baseline and a reference solution). Infeasible
  outputs score 0.
- **Verifier parsers** (the "re-open" mechanism): CadQuery/OCCT (solids), **ezdxf (drawings)**, **IfcOpenShell
  (building models)**, **FreeCAD and Blender APIs**, Abaqus ODB API (simulation), SQLite (EnergyPlus/OpenStudio).
- **Integrity guards**: designated input files are protected; GUI tasks completed by script instead of the GUI
  are detected and rejected.
- **Verifier validation**: each verifier is validated in its target software — the reference solution must pass,
  intentionally flawed submissions must be rejected, and alternative valid solutions must pass; 96 sampled
  references were audited (all pass after review).

The grader is **decoupled from the harness**: an `eval.py` is a standalone Python script that runs *inside the
VM* after the agent finishes, opens the artifact, and prints `True`/`False`. This is what makes the graders
reusable against our own pipeline outputs without their VM environment.

## 3. Subset relevant to us (BIM, 3D modelling, export)

Counts are exact (enumerated from the GitHub git tree, `task-*.json` files). "BIM" = Revit/Archicad/Bonsai/
OpenStudio; "DCC" = Blender/ZBrush (EngiWorld's 3D modelling/export domain).

| Subset | Tasks | Notes |
|---|---:|---|
| BIM single-software | 140 | Revit 20, Archicad 40, Bonsai 40, OpenStudio 40 |
| BIM design-optimization | 10 | Bonsai 5 (GUI), OpenStudio 5 (CLI) |
| BIM cross-software | 20 | Archicad→OpenStudio 10, Revit→ArchiCAD→OpenStudio 10 (both CLI, Windows) |
| BIM software-selection | 40 | Revit–ArchiCAD–Abaqus 40 (CLI+GUI) |
| **BIM subtotal** | **210** | |
| DCC single-software | 120 | Blender 90 (40 GUI + 50 CLI), ZBrush 30 (GUI) |
| DCC design-optimization | 5 | ZBrush 5 |
| DCC vision-guided-modeling | 10 | Blender 10 |
| DCC cross-software | 20 | two EDA/CAD+Blender chains × 10 |
| **DCC subtotal** | **155** | |
| **Combined (BIM + DCC)** | **365** | ~20 are multi-domain (Blender chains) and 40 are BIM+CAE selection |

Of these, the ones that map to our *specific* toolchain (Blender, Revit, IFC):

- **Blender (DCC)**: 90 single-software + 10 vision-guided + 20 cross = 120 — but 20 cross are EDA/CAD-led.
- **Revit (BIM)**: 20 single + 10 cross + 40 selection = 70 (Windows, Revit 2025).
- **Bonsai (BIM, IFC-native on Blender)**: 40 single + 5 design-opt = 45.
- **Archicad / OpenStudio / ZBrush**: no local counterpart.

## 4. Five concrete tasks vs. our toolchain

Toolchain verified on this host: **3ds Max 2026** (also 2024 + SDK), **Blender 5.1.2** (also 4.4, 5.1),
**Revit 2025** (exact EngiWorld version), IFC via `ifcopenshell` (not a default dependency — used transiently,
`uv --with`). **No Bonsai/BlenderBIM addon, no Archicad, no OpenStudio, no EnergyPlus, no ZBrush installed.**

| # | Task (id) | What it asks | Grader re-opens | Run on this host? | Missing / effort |
|---|---|---|---|---|---|
| 1 | `single-software-execution--cli--revit--task-01--windows` | Convert a storage room to a print room in Revit, export `result.ifc` as IFC4 | IFC via `ifcopenshell` + `ifcopenshell.geom`: exact entity counts (`IfcSpace`=3, `IfcWall`=6, forbidden `IfcRoof/IfcColumn/…`), space name tokens, bbox spans (m), preserved wall/slab geometry, space volume ratio 0.84–1.02, overlap/z-level checks, `ApplicationIdentifier` must say "revit" | **Yes, in principle.** Revit 2025 matches; grader needs only `ifcopenshell` (transient). Driving Revit headlessly uses our Revit bridge (not EngiWorld's `BimBridge.dll`) | Medium: adapt the harness to our bridge; ~0.5–1 day |
| 2 | `single-software-execution--cli--blender--task-01--ubuntu` | Geometry-Nodes cable with sag between two empties, save `answer.blend` | `bpy` via `blender --background --factory-startup --python`: modifier present, ≥240 verts (÷6), ring centroids within 0.01 BU, sag depth within 5 %, 2-face manifold interior edges, 6 verts/ring | **Yes.** Blender 5.1.2 headless (our `blender_exec.py`); GN API stable 4.2→5.1 | Low: rewrite Ubuntu paths (`/opt/blender/blender`, `/home/user/Desktop`) to Windows; ~0.5 day |
| 3 | `single-software-execution--cli--bonsai--task-01--ubuntu` | In Bonsai/Blender: turn a room shell into an "intentional" office package (named walls, slab assembly, revision `BONSAI-CLI-01`), save `result.ifc` | IFC via `ifcopenshell`: entity counts, forbidden entities, wall/slab names+thickness (tol 0.06 / 0.035), space/storey names, schema IFC4 | **Partial.** Grader runs with `ifcopenshell` alone, but the *task* needs the Bonsai addon (`bpy.ops.bim.*`), which is not installed; Bonsai 0.8.5 targets Blender 4.x, our target is 5.1.2 (version compat unverified) | Medium-high: install Bonsai into Blender 5.1.2 and verify compat; ~1 day + risk |
| 4 | `cross-software-coordination--cli--revit--archicad--openstudio--task-01--windows` | Revit → Archicad 27 → OpenStudio 3.10 + EnergyPlus 25.1 energy workflow (14 artifacts incl. `eplusout.sql`) | IFC + Archicad JEMI + OSM/IDF + EnergyPlus SQLite tables | **No.** Missing Archicad 27, OpenStudio, EnergyPlus; and it is an energy-simulation workflow, outside our 3D modelling/export scope | n/a — out of scope |
| 5 | `vision-guided-modeling--cli--blender--task-01--ubuntu` | Reconstruct a 64×64 terrain surface from a PNG + `geometry_report.csv` as one mesh `Terrain`, save `answer.blend` | `bpy`: mesh name, grid extents/relief/connectivity vs the CSV | **Yes.** Blender 5.1.2 headless; pure bpy reconstruction + CSV readback | Low-medium: harness path adaptation; ~0.5 day |

Summary of the gap: the *graders* are cheap to reuse (they need only `ifcopenshell` and `bpy`, both local),
but the *tasks* split three ways — runnable (Blender), runnable-with-bridge (Revit), and blocked-by-software
(Bonsai addon, Archicad, OpenStudio, ZBrush). 3ds Max plays no role: EngiWorld has no 3ds Max tasks.

## 5. Recommendation

**Adopt a small external eval of ~20 verifiers, not the full benchmark — and adopt the graders, not their
Docker/VM harness.**

- **What**: 10–15 Blender single-software CLI tasks (DCC/3D modelling + export) + ~5 Bonsai/Revit IFC tasks.
  Concretely the `blender` CLI tasks and the IFC-exporter BIM tasks, whose `eval.py` + `init_file` +
  `ground_truth` are public under MIT and run with `bpy`/`ifcopenshell` alone.
- **Why adopt at all**: EngiWorld is the published, peer-shaped version of exactly what we build — checkers
  that **re-open the artifact** (geometry/topology/entities) instead of trusting "done", and score the artifact
  not the transcript. It gives us a **public, externally-maintained vocabulary and a fixed 0–100 scale** to
  quote (best frontier agent 44.7/100; only 3.6 % of cross-software runs succeed) and a second, open data point
  next to our closed internal eval B (#391). It is not a substitute for #391: #391 measures *our agents on our
  own closed tickets and pipeline*; EngiWorld would measure the *same verify-before-complete discipline on a
  public, reproducible task set* that we do not have to author or maintain.
- **Why not the full suite**: the complete harness needs a Linux host + Docker + KVM + ~98 GB of VM images and
  paid software (Revit, Archicad, SolidWorks, ZBrush …). That is out of scope for this card and redundant with
  our own DCC toolchain. We only need the per-task graders, which are self-contained.
- **Cost estimate per run** (running the adopted graders against our pipeline outputs, agent-side):
  the paper's measured per-task API cost is **$0.44–$18.78** depending on model (DeepSeek ≈ $0.80, Claude
  Opus 5 ≈ $18.78). For a **20-task Blender+Bonsai+Revit-IFC subset** this is roughly **$10–$40 per run on a
  cheap model and ~$350 on a frontier model**, plus local DCC machine time. The grader itself (re-opening and
  checking) is effectively free (local `ifcopenshell`/`bpy`).
- **Effort to adopt**: ~1–2 days to port the 20 `eval.py` + `init_file` pairs into a thin runner that points
  the Blender/IFC verifiers at our outputs (adapt Ubuntu→Windows paths, pin Blender 5.1.2, use `ifcopenshell`
  transiently), plus one-off Bonsai-install verification if we include Bonsai tasks.

## Open questions / caveats

- The card and the first digest quote "best frontier agent **44.3**/100"; the paper abstract and the README
  table both say **44.7/100** (Claude Opus 5). This report uses **44.7** (paper/README are authoritative).
- Version skew: EngiWorld pins **Blender 4.2.3 / Ubuntu**; our target is **5.1.2 / Windows**. GN and bpy
  graders are expected to be portable, but a small number of version-sensitive tasks must be re-checked before
  adoption. Bonsai 0.8.5 targets Blender 4.x — the biggest version risk if we include Bonsai tasks.
- No 3ds Max coverage in EngiWorld at all, so it cannot validate the 3ds Max leg of our pipeline.
