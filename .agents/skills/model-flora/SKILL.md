---
name: model-flora
description: 'Produce Flora (trees, bushes, modelled flower beds) from the planting schedule and the SPOZU points: library species or a new one, NPM star / VPM shell, placement, one 2048 Flora atlas, checks. Use when: «сделай Флору по ведомости озеленения», «расставь кусты и деревья по СПОЗУ», «новый вид растения для библиотеки».'
---

# Model Flora from the planting schedule

The user's Flora practice (Flora grilling, [D099], [D100], [D101], [D102]) as a procedure. The rules live in the
[Flora sheet](../../../docs/domain/areas/flora.md) (rows `FLO-01`..`FLO-17` and its
[Project practice](../../../docs/domain/areas/flora.md#project-practice) section) and in
[the decision log](../../../docs/decisions.md); each step names the rows it must satisfy instead of restating them.
Open conflicts that touch Flora (C7, C8, C18, C21 in [conflicts.md](../../../docs/domain/conflicts.md)) end as
`review`; never pick a side.

Order: the library comes first, single NPM plants are placed next, and the one Flora atlas is built last, from the
placed scene ([#216](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/216),
[#217](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/217)). An atlas packed in advance from a species
list is not used, and a second Flora atlas is never made: tiles are scaled down instead.

Out of scope here: Ground relief and lawn texture (`model-ground`), MAF ([sheet](../../../docs/domain/areas/groundel-maf.md)),
the library audit itself ([#189](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/189)).

## Route markers

Every step carries three lines:

- `Route:` the tool route that exists today ([CAPABILITIES](../../../docs/agents/CAPABILITIES.md), headless smoke
  table). PDF schedules through PyMuPDF (`uv run --extra pdf-review`); DWG through the AutoCAD 2025 core console
  (`dcc_batch.py acad`, `DXFOUT`) plus `ezdxf` (`uv run --extra cad`); scenes through 3ds Max batch
  (`dcc_batch.py max`, on a copy; the startup `polyunwrapper_autoload.mse` error is known, read the log) or Blender
  headless (`blender --background --factory-startup`). Live programs only through `max_exec.py` / `blender_exec.py`
  after a `--ping` (COORDINATION_RULES 22; the 3ds Max bridge runs in safe mode, so library reads go headless);
  before any DCC write apply the [DCC gate](../../../docs/agents/WORKFLOW.md#gate-dcc-authorization).
- `Needs:` `headless` (an agent runs it today), `live` (the program open by the user), `human` (a user decision or
  a visual look). `no tool yet` means the route exists but no reviewed script does the step.
- `Done when:` the evidence that closes the step.

Work on copies of the user's scenes and drawings (hash the original before and after); every output goes to a new
versioned path outside git (`C:/x/<card>/` or `jobs/<JOB>/outputs/`, both untracked). No PNG, MAX or FBX is
committed.

## Steps

### Step 1 — Planting schedule and SPOZU points

Read the planting schedule (the «Ведомость элементов озеленения» table of the greening sheet): position, Russian
name, group (trees, bushes, hedges, flower beds, lawn), count, unit and the size note (height, crown or root-ball
diameter). Add the Latin name for each species. Read the SPOZU drawing: one insertion point per plant, grouped by
position number; hedges are lines or areas with a planting rate, flower beds are areas. Points carry no rotation.

- Route: PDF text layer with PyMuPDF (`uv run --extra pdf-review python`; check numbers on a rendered page image,
  the text layer can be broken); DWG copy -> `dcc_batch.py acad` (`DXFOUT`) -> `ezdxf` (block inserts by layer or
  block name, nested inserts included).
- Needs: headless; human when the schedule is a scan, a species name is ambiguous, or the point layer cannot be
  matched to the positions.
- Done when: a table position -> species (Russian + Latin) -> count -> size note, and per position the number of
  SPOZU points equals the scheduled count (differences listed for the user).

### Step 2 — Pick the species from the library

Match every position by Latin name in the Flora library. Once
[#216](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/216) is merged, the catalogue
`library/flora/catalogue.json` is the entry point (Latin name, type, NPM/VPM availability, sizes, triangles, map
paths, material ID). Until then read a copy of the user's library scene: every plant is labelled on its left by
Text objects (Russian name, `<N> Tris`, version, `LP` / `HP` / `LP -> HP`); the mapping of `LP`/`HP` to NPM/VPM is
an audit result of [#189](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/189), not an assumption.
Triangle counts per plant come from the library, never invented.

- Route: catalogue lookup (after #216); today `dcc_batch.py max --scene <copy>.max --file <read-labels>.ms`
  writing Text objects and mesh bounding boxes to a TSV.
- Needs: headless; human when one species has several variants (`v1`, `v2`, cultivars) and the schedule does not
  say which.
- Done when: every position has a library object (name, variant, triangles, bounding box) or is listed as a new
  species for step 4.

### Step 3 — Check against the schedule

Compare the measured model with the schedule ([FLO-04](../../../docs/domain/areas/flora.md), [D099]): height and
crown diameter within ±20 % of the scheduled value, leaf and flower colour as the specification shows it, otherwise
as photos of the species show it. A schedule that gives only a lower bound («h свыше 0,9 м») or no crown is
recorded as `review` with the numbers; the user says which target applies. A model outside the band is scaled
uniformly into it only when the silhouette stays plausible; otherwise it goes to step 4 as a new variant.

- Route: bounding box from step 2 (3ds Max batch readback) against the step 1 table, in a script or by hand.
- Needs: headless for the numbers; human for colour and for every `review` row.
- Done when: per position measured height and crown, the band, the verdict (`pass` / `fail` / `review`) and the
  scale applied, if any.

### Step 4 — New species: texture route

A species missing from the library, or without usable maps, gets its diffuse and opacity maps through the Flora
texture route ([pipeline](../../../docs/pipeline-flora-textures.md)): reference picture -> generated 2K front view on
white, no shadows -> white-key cut-out -> black-and-white opacity -> per-species library maps. Every new texture is
shown to the user on the review sheet and enters the library only with the user's explicit approval; an agent never
writes an approval record.

- Route: `uv run python -m dt_ai.materials.flora plan` -> image generation on a dt profile -> `flora upscale` (only
  for 1254 px sources) -> `flora prepare` (review sheet) -> `flora library` (after approval).
- Needs: human (texture review, every new species); headless for the commands.
- Done when: the species folder holds `diffuse-v<NNN>.png` and `opacity-v<NNN>.png` listed in the library manifest
  with the approval record, or the species is listed as waiting for review.

### Step 5 — NPM bush star and VPM shell

NPM bush: a star — one vertical plane carrying the species' diffuse and opacity, copied and rotated around the
plant's vertical axis; size from the schedule band. The library's NPM bushes show the scale of it (tens of
triangles per bush). VPM bush: by default the shell of that star; a detailed bush only when the user asks for one
([FLO-10](../../../docs/domain/areas/flora.md), [D102]). Before building a new one, open the library's VPM bushes
and follow their construction; record what was learned. Opacity and two-sided planes differ between the profiles
([FLO-11](../../../docs/domain/areas/flora.md), C7, C8): build each profile's version on its own. Give every face
of the species its library material ID (bushes 201-299, hedges 301-399, flowers 401-499; #216).

- Route: 3ds Max batch (`dcc_batch.py max`) or Blender headless; library objects are copied, not rebuilt, when
  they exist.
- Needs: headless, no tool yet (no reviewed star builder); live 3ds Max when the user wants to see the bush.
- Done when: an NPM star and a VPM shell per new bush species, triangles counted, size inside the step 3 band,
  one material ID on all faces.

### Step 6 — Trees from the library

Trees follow steps 2-5 the same way: the library tree of the species, sized into the band of step 3, a new tree
species through step 4. A VPM tree stays realistic: trunk and main branches as geometry, small twigs and leaves as
planes with cut-out ([FLO-10](../../../docs/domain/areas/flora.md)). Tree material IDs are 101-199 (#216).

- Route: library copy via 3ds Max batch; for a tree that the library lacks, SpeedTree export through the
  `speedtree-mcp` skill, then FBX readback (backlog P11) — only after the user agrees to that source.
- Needs: headless, no tool yet for a new tree; human to accept a SpeedTree or new-tree source.
- Done when: an NPM and a VPM tree per species with triangles, size verdict and material ID recorded.

### Step 7 — Placement on SPOZU points

Place one instance per SPOZU point ([FLO-17](../../../docs/domain/areas/flora.md), [D100], same seating as MAF
[D095]): pivot on the point and raised above the plant's lowest point so the plant ends 10 cm below the Ground
surface after projection; each copy gets a random rotation about Z and a uniform random scale within ±10 %, and
the result must still fall inside the ±20 % band of step 3, so narrow the scale range for a model already near
the band edge. Use a fixed random seed and store it. Place single NPM
plants of every species first; the atlas of step 8 is built from this scene. Hedges: plants along the line at the
scheduled rate, or a hedge object when the library has one.

- Route: 3ds Max batch or Blender headless reading the step 1 point table; projection onto the Ground relief
  from `model-ground`.
- Needs: headless, no tool yet (no reviewed placement script); live when the user checks the scene.
- Done when: instance count per position equals the point count, seating depth 10 cm measured on a sample, the
  seed and the per-instance rotation and scale written to the run record.

### Step 8 — One 2048 Flora atlas from the placed scene

From the placed scene list the species actually used, take each one's diffuse and opacity map and pack them into
one atlas pair of at most 2048 × 2048 for all Flora ([FLO-08](../../../docs/domain/areas/flora.md)): diffuse
without alpha, opacity as a separate map in NPM ([D020]). When the tiles do not fit, scale every tile by the same factor
instead of starting a second atlas. Remap each plant's UVs into its tile and keep its material ID on every face.

- Route: `atlas_maf.py` packing code in `tools/materials/` (512 MAF packer) extended by the tool of
  [#217](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/217) (not merged yet); the user's `FloraAtlas.ms`
  only with the fixes listed in [max-scripts](../../../docs/tools/max-scripts.md) (RGBA output, 2 px padding, size
  above 2048, names).
- Needs: headless, no tool yet; human for the visual check of the atlas.
- Done when: one diffuse and one opacity map at most 2048 px, the report species -> tile -> material ID, scale
  factor, and no second Flora atlas.

### Step 9 — Flower beds: texture or models

Apply [D101] ([FLO-02](../../../docs/domain/areas/flora.md)): a schedule row that only says flower bed or small
greenery stays in the Ground texture (hand it to `model-ground`); a row that lists the plants in the bed is
modelled with those plants (library or step 4) scattered over the bed area; big bushes are always models. Lawn
rows are Ground texture ([FLO-01](../../../docs/domain/areas/flora.md)).

- Route: the step 1 table wording; bed areas from the SPOZU DWG via `ezdxf`; scatter via 3ds Max batch or
  Blender headless.
- Needs: headless for the classification; human when the wording is unclear; no tool yet for the scatter.
- Done when: every bed and lawn row has a verdict texture / models with the wording that decided it.

### Step 10 — Checks before handover

Read back the exported Ground FBX, not the working scene, and go through the Flora sheet rows: membership and
completeness against the schedule in both profiles (FLO-01, FLO-03), the NPM vegetation object and its single
texture set (FLO-05, FLO-08), triangles against the NPM Ground total and the planning split of [D097] (FLO-06) and
the VPM Ground limit (FLO-07), names of meshes, maps and materials (FLO-12, FLO-13), embedding (FLO-14), no
collision on plants (FLO-15), triangulation (FLO-16), transforms and seating (FLO-17). Each row ends as `pass`,
`fail`, `review: <conflict or reason>` or `not checked: <reason>`.

- Route: `validate_package.py` (V003 triangles and triangulation, V004 rotation and scale, V006 embedding, V013
  pivot) through the `validate-delivery` skill; Blender headless readback for counts and renders; Flora-specific
  checks of [#191](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/191) when merged.
- Needs: headless for the machine checks; human for colour, silhouette and the visual review.
- Done when: a report with every FLO row, the evidence per row and the user's sign-off for the manual rows;
  `passed` only when nothing is `fail`, `review` or `not checked`.

## Report

Per step: the route actually used, inputs with hashes, counts, and what is left for the user. A dry walk of this
procedure on one bush and one tree: [model-flora dry walk](../../../docs/research/model-flora-dry-walk-2026-10-16.md).
