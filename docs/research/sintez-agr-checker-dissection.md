# SINTEZ AGR Checker 1.6.1 — every check, threshold and requirement table vs our checkers

Dissection of the third-party Blender extension `sintez_agr_checker` 1.6.1 (read-only copies
`C:/x/sintez/v1.6.1`, `C:/x/sintez/v1.5.0`). No SINTEZ source is committed; only short excerpts
are quoted here. Machine-readable inventory: `docs/agr/sintez_checks_1.6.1.json`.

## Summary

SINTEZ AGR Checker 1.6.1 is a Blender add-on (46 `.py`, ~29.8k lines) that checks a delivered
AG R project package against the 2026 Moscow NPM/VPM requirement tables and offers one-click
auto-fixers. It runs 36 automated check groups — 17 NPM (LP) and 19 VPM (HP) — covering FBX
header/units, archive structure and digital signatures, naming masks (`SM_`/`M_`/`T_`/`UCX_`),
transforms/pivot, polycount (NPM 150k, VPM 1M), doubles (2 mm), texel density (NPM 10–40,
VPM 512–1706 px/m), UV/UDIM, materials, UCX collision (closure/convexity/intersection/nesting/gap),
GeoJSON properties, lights and PNG. Our `src/twinqa/*` covers ~55 % of this (FBX header, naming,
pivot, polycount, doubles, UCX, GeoJSON, PNG) with the same thresholds; the rest (archives,
signatures, district code, elevation 110–250 m, texel density, lights, glass UV, color attributes)
is missing. The 2026 tables renumber most of the geometry/texture/collision/lighting rows vs V4 —
that is the current regulation context our agents lack. Four thresholds conflict with our
`docs/decisions.md` and are listed for Artem, not resolved here.

## Findings

### 1. Inventory of every check (id → what → threshold → req → file:function)

Complete machine-readable list in `docs/agr/sintez_checks_1.6.1.json` (`checks[]`, 36 entries).
Checks are declared on methods of `LowpolyChecks` / `HighpolyChecks` with
`@refreshable([req_nums], label)` / `@not_refreshable([req_nums], reason)` decorators
(`scripts/autochecks/refresh_registry.py`); free functions in `CheckUtils` write to the same
req nums. Thresholds live in `scripts/constants.py` and the check bodies.

**NPM (LP) — 17 groups** (`scripts/autochecks/lp_checks.py`, `check_utils.py`):

| req | check | threshold | our equivalent |
|---|---|---|---|
| 1.1.1 / 2.9.1 | FBX 7.4 binary, units | version 7400; unit_scale ∈ {1.0, 100.0} | `src/twinqa/fbx_header.py` (7400) — same |
| 2.1.1 / 2.1.2 / 2.10.1-2 | files: archive ≤1 GB (LP/ground) or 500 MB, FBX 2..21, PNG 3..2100, symbol/length | `check_files` | missing |
| 2.1.1 | archive structure, unsupported archives | ZIP only (`.rar/.7z/.tar`… rejected) | missing |
| 2.1.1 | digital signature (УКЭП) | detached-sig digest/subject/dates | missing |
| 2.10.3.1–.5 | naming masks + slot sequences | `SM_<addr>_<NNN>_Main`, `M_…_N`, `T_…_d/m/r/o/n_N`, `UCX_…` | `src/twinqa/naming.py` — same |
| 2.3.14 | transforms applied | loc<1e-4 m, rot<1e-3, scale=1 | `src/twinqa/scene.py` — same |
| 4.1.5 | origin XY | pivot at 0,0 | `src/twinqa/scene.py` — same |
| 2.3.6 / 2.3.11 | polycount + triangulation | NPM ≤ 150 000 | `scene.py PROJECT_TRIANGLE_TARGET=150000` — same |
| 2.3.7 | doubles / loose | merge 2 mm | `src/twinqa/geometry/topology.py` — same |
| 2.6.1 | texel density | NPM 10–40 px/m | missing (D097 has the values, no checker) |
| 2.1.2–2.1.6 / 2.3.5 | FBX object composition (Ground, Main/Glass) | — | partial (`scene.py`) |
| 2.4.2/.3/.6 / 2.5.11–.13 | materials (glass color, alpha, GroundEl ≤512 px, Flora) | — | partial (`geometry/checks.py`) |
| 2.4.5 | texture sets (1 OKS = 1 set) | `d/m/r/o/n` per slot | partial (`png.py`) |
| 4.1.3 | unwrapped polygons | UV area > 0 | `src/twinqa/uv.py` — same |
| 2.10.3.1 | district code vs coordinates | even-odd point-in-polygon (`geo_utils`) | missing |
| 4.1.4 | elevation | Moscow 110–250 m | missing |
| 4.1.1 | color attributes | present | missing |

**VPM (HP) — 19 groups** (`scripts/autochecks/hp_checks.py`, `check_utils.py`):

| req | check | threshold | our equivalent |
|---|---|---|---|
| 2.5.1.1 | embedded images | none (paths only) | missing |
| 2.5.1.2/.3 / 2.5.2.1.3 | UDIM resolutions / ERM·Normal≤Diffuse / no gaps | 2048/4096 only | partial (`uv.py`) |
| 2.3.18 / 2.9.3 | transforms | as LP | `scene.py` — same |
| 2.13.7 / 2.3.17 / 2.3.9 | polycount + triangulation | VPM ≤ 1 000 000 | **we are stricter** (D010 target 150k) |
| 2.3.11 | doubles / loose | 2 mm | `topology.py` — same |
| 2.5.1.4/.8 / 2.5.2.1.2/.5 / 2.6.2 | texel + UDIM margin | VPM 512–1706 px/m; margin 1/256 | missing (**conflict**: D097 says 520) |
| 2.10.1 / 2.10.2 | symbols / length | whitelist | `naming.py` — same |
| 1.3.6/.7 / 2.10.4.1–.6 | naming masks (incl. `_Light.fbx`) | `SM_`/`M_`/`UCX_` | `naming.py` — same |
| 2.13.3 / 2.3.1а / 2.3.2 / 2.3.8 / 2.8.1 | objects / hierarchy | single collection, no hierarchy | partial |
| 2.5.2.2.1а | glass UV fill | glass occupies tile | missing |
| 2.13.1 / 2.4.3/.5 / 2.5.2.1.1 / 2.5.2.2.2 / 2.8.2 | materials / ≤100 textures / ≤7 materials | — | partial |
| 2.4.2 | material-texture links | no texture paths | missing |
| 2.15.2/.4/.5/.8/.9 | lights | ≤250 sources, point/spot, distance | partial (D017 lights only in `_Light.fbx`) |
| 2.10.4.2 / 2.13.1 / 2.13.4 | UCX collision | closure tol 0.2 mm, convex 0.1°, intersect/nested/gap | `ucx_audit.py` (**conflict**, see §6) |
| 2.5.2.1.4/.4б / 4.1.3 | flipped UV / flipped-on-opacity / unwrapped | — | partial (`uv.py`) |
| 4.1.4 | elevation from geojson | h_relief 110–250 m | missing |
| 2.2.1/.3/.5/.6/.7 / 1.3.6 | GeoJSON properties | cadNum format, cross-file equality | `geojson.py` — same |
| 2.9.4а / 2.9.5 | pivot | origin 0,0,0; bbox centre ≤10 % | `scene.py` — same |
| 2.5.1.6/.9 / 2.5.3.1/.3/.4 / 4.1.2 | PNG (alpha, 256 px placeholders, one-color, mode) | — | `png.py` — same |

Requirement rows: `documents/lp_requirements_2026.csv` (80 rows, 44 automated),
`documents/hp_requirements_2026.csv` (154 rows, 67 automated, 34 recommendations). The CSV
`Пункт требований` column is the canonical req_num; `Авто`=1 marks the rows the add-on
automates.

### 2. Our equivalent per check (module / function / test)

- **Same threshold** (13 groups): FBX header (`fbx_header.py`), naming (`naming.py`), transforms
  and scale (`scene.py`), NPM polycount 150k (`scene.py`), doubles 2 mm (`topology.py`),
  pivot (`scene.py _pivot_findings`), UV unwrapped (`uv.py`), GeoJSON (`geojson.py`),
  PNG VPM (`png.py`).
- **We are stricter** (1): VPM polycount — SINTEZ allows 1 000 000, our D010 sets a 150 000
  project target per OKS FBX.
- **Partial** (9): FBX objects, materials, texture sets, UDIM resolution, lights, UV flipped,
  UCX (see conflicts).
- **Missing** (13): archive structure/size/signatures, file counts, district code vs coordinates,
  elevation 110–250 m, texel density (both sides), embedded images, glass UV, material-texture
  links, color attributes.

Our checkers live in `src/twinqa/*` (FBX header, GeoJSON, PNG, naming, UV, scene, UCX audit,
geometry checks, clearance), driven by `src/dt_ai/procedure.py` (gates: inputs, parts, operations,
budgets, export_readback, report, visual, checker) and `jobs/KPP1/scripts/run_agr_checker.py`,
which shells the add-on (`bl_ext.user_default.sintez_agr_checker`) headlessly and dumps the
checklist. `tools/check_profile_agr.py` loads the native add-on record + bundled Pillow and
compares a profile. There is **no** `src/twinqa` parity test that asserts "our checker flags
what SINTEZ flags" for the shared thresholds.

### 3. Requirement tables 2026 vs V4 — the regulation context the agents lack

The V4→2026 diff is already materialised inside the 2026 CSVs (columns
`Сравнение с новой редакцией`, `Наименование краткое (старая)`, `Описание (старая)`) and the
`*_V4_compare_with_new.xlsx` files. Extracted:

- **NPM (LP): 36 of 80 rows changed.** Mostly renumbering: 2.3.x shifted
  (2.3.9→2.3.10→2.3.11→…, "перенесли X"), 2.5.x shifted (2.5.4→2.5.3, 2.5.9→2.5.7, 2.5.10→2.5.8,
  2.5.11→2.5.9), a new 2.5.13, 2.8.2 gained "из 2.8.3", 1.1.2 merged ("лицензионное ПО +
  вредоносное ПО"), 1.1.4 "доп из 2.1.6".
- **VPM (HP): 88 of 154 rows changed — a near-total renumber**, not just edits:
  - 2.1.1: ZIP ≤ 0.5–1 GB **+ УКЭП (electronic signature)** — new.
  - 2.3.x renumbered: new "ОКС поликаунт ≤ 1 млн", "Ground поликаунт 300к–4,5 млн",
    "Сонаправленные 5–20 мм", "Группы сглаживания".
  - 2.4.3: UDIM ≤ 100 textures / ≤ 7 materials.
  - 2.5.1.2: resolutions **2048/4096 only** (256 dropped from V4's 256/2048/4096).
  - 2.5.1.3: ERM/Normal resolution ≤ Diffuse.
  - 2.5.1.5: texture margin 16–32 px (was 32 px).
  - 2.13.x: collision tolerance ≤10 cm (ground)/≤30 cm (OKS 1st floor)/≤1 m (OKS); stairs as
    truncated pyramids; polycount ≤5 % / ≤15 000 folded into "поликаунт доп".
  - 2.15.x: lighting ≤250 sources (was ≤50), point/spot only, source distances, "привязаны к корню".

**Where it should live in `docs/domain/` (proposal, not edited here):**
- `docs/domain/npm-vpm.md` — the NPM/VPM 2026 table extract (polycount, texel, naming, texture
  resolutions) so every checker/agent reads one source.
- `docs/domain/validation.md` — the automated check list and the four conflicts (§6).
- A new `docs/domain/requirements-2026.md` (or `docs/agr/requirements-2026/`) holding the
  full LP+HP tables as the machine-readable regulation context, generated from the two CSVs
  (they are third-party but are the public requirement text, not code).

### 4. Fixers / automation vs what our agents do by hand (ADR-0004 reuse-vs-rewrite)

| SINTEZ tool | automates | our agents today | verdict |
|---|---|---|---|
| `fix_operators.py` (15 operators) | triangulate, glass alpha/textures, origin XY, pivot Z, one-color plugs, alpha, doubles/loose, color attributes, image mode, texture-node naming, UV-map name, extra UV maps, plug resize, UCX convex/gap | one-off `tools/*_blender.py` + `jobs/KPP1/scripts/*` | **reuse via headless run** (D104 already shells the add-on); do not rewrite |
| `name_fixer/` (naming_core + plan/apply) | bulk rename files/meshes/materials/textures/UCX to masks | agents rename by hand per object | reuse (highest-value adapter) |
| `png_compressor/` | find >3 MB textures, compress, re-pack NPM | manual | reuse |
| `fbx_material_sync.py` | sync material links FBX↔scene | manual | reuse |
| `model_exporter/` | FBX export + ZIP pack | `jobs/*/export_*.py` | ours already covers; reuse only the ZIP/signature part |
| `hash_compare/` (MD5) | compare files/archives | `tools/check_profile_agr.py sha256` | ours is SHA-256; keep ours, add MD5 parity if UKEP requires |
| `ghost_compare/` | phantom A/B overlay + deviation map (NPM↔VPM visual) | manual visual compare (D104) | reuse (fills the "Соответствие НПМ и ВПМ" subitem) |
| `geojson_editor/` | edit/validate/replace geojson in zip, linked fields | `src/twinqa/geojson.py` (read-only) | reuse for edits; our reader stays the checker |
| `collision_select/` + `texel_density/` + `uv_tools/` | select UCX/texel/UV error faces | `ucx_audit.py` reports only (no selection) | reuse selectors for authoring UX |

Per ADR-0004 the default is **reuse the installed toolchain**, not re-implement: the adapters we
already have (`run_agr_checker.py`, `check_profile_agr.py`) are the seam; new parity work should
call the add-on headlessly and diff against `src/twinqa`, not port SINTEZ logic into Python.

### 5. 1.5.0 → 1.6.1 diff — what the vendor tightened

New files in 1.6.1: `refresh_registry.py`, `core_utils/cms.py`, `core_utils/path_utils.py`,
`fbx_material_sync.py`, `ghost_compare/*`, `hash_compare/*`, `hp_scene_state.py`,
`install_state.py`, `name_fixer/*` (bulk rename — new). Line growth: `check_utils.py` 1655→2469,
`fix_operators.py` 305→1161, `fbx_header.py` 239→584, `archive_preflight.py` 427→640.

Tightening / additions:
1. New check **2.5.2.1.4б** — flipped UV islands on opacity tiles (split out of the plain
   flipped check; `AGR_UV_FLIPPED_OPACITY_FACES`).
2. **Ground polycount limits** (VPM 3.10) — area-banded table 300k…4.5M triangles
   (`GROUND_POLYCOUNT_LIMITS`).
3. **Digital-signature checks** (`check_signatures`: digest/subject/dates) — new.
4. **UCX collision expansion** (`compute_ucx_collision_errors`): nested + intersect + gap in
   addition to unclosed/nonmanifold/nonconvex.
5. **Declarative recheck registry** replaced the hand-kept `REFRESH_GROUPS`.
6. NPM/HP subitem split (LP loses "ТЭП", HP gains "Соответствие НПМ и ВПМ").

### 6. Conflicts with `docs/decisions.md` / `docs/domain` (listed, NOT resolved — for Artem)

1. **Texel density VPM lower bound: SINTEZ 512 px/m vs our D097 "520–1706 px/m".**
   `check_utils.py:1525` sets `texel_min, texel_max = 512, 1706`; `docs/decisions.md` D097 records
   "VPM 520–1706". The upper bound and the NPM 10–40 agree; the lower bound differs by 8 px/m.
2. **VPM polycount: SINTEZ 1 000 000 vs our D010 target 150 000.** SINTEZ `hp_checks.py:296`
   passes `max_polycount=1000000`; D010 sets the project budget at 150 000 per OKS FBX. We are
   deliberately stricter; worth confirming the 1M is the 2026 regulation ceiling the project
   chooses to undercut.
3. **UCX gap semantics: SINTEZ flags "gap < 0.2 mm" (practically touching), D098 requires a
   2 mm–1 cm band.** SINTEZ `compute_ucx_collision_errors` uses `tolerance=0.0002` and reports
   "зазор меньше допуска" (too close); D098 ("reg p.36 §13.4 0.02–1 cm is a typo; 2 mm–1 cm
   inclusive") adds the *upper* bound SINTEZ does not check. Our `ucx_audit.py GAP_BAND_M=(0.002,
   0.01)` checks the band; SINTEZ checks only the "too close" side.
4. **VPM texture resolutions: SINTEZ 2048/4096 only vs our VPM placeholder 256×256 (D013).**
   SINTEZ `HP_PLUG_TEXTURE_SIZE=256` and `_udim_numbers_check` allow 256 only as a *placeholder*
   (excluded from density); D013 records the VPM placeholder 256×256. Consistent, but the 2026
   table dropped 256 from the *texture-map* resolutions (V4 had 256/2048/4096) — confirm the
   placeholder exception is still valid under the 2026 wording.

## How it applies to this repository

- **`src/twinqa/`** — the 13 "same" checks confirm our thresholds; the 13 "missing" checks are the
  parity backlog. Add: archive/signature check, district-code-vs-coordinates, elevation 110–250 m,
  texel density (both sides), lights, glass UV, color attributes, embedded-images, material links.
- **`jobs/KPP1/scripts/run_agr_checker.py`** — already the headless seam; extend to diff SINTEZ
  findings against `src/twinqa` findings (parity harness).
- **`tools/check_profile_agr.py`** — already loads the native record; add the 2026 requirement
  tables so the profile check asserts "checker flags all `Авто=1` rows".
- **`src/dt_ai/procedure.py`** — the `checker` gate (D104/D125) should name SINTEZ as the last
  gate; the report maps its 36 groups onto our gates.
- **`docs/decisions.md`** — the four conflicts (§6) are candidates for a new decision once Artem
  resolves them; do not change them here.

## Proposed next tasks (value/effort, `Advances #N`)

1. **Parity harness: "our `src/twinqa` flags what SINTEZ flags" for the 13 shared thresholds.**
   Run `run_agr_checker.py` headlessly on a synthetic fixture and diff SINTEZ findings vs
   `src/twinqa` per req_num; turn each shared check into a regression test. Value/effort **M**.
   `Advances #149` (capability roadmap L2 self-checks / L3 verify).
2. **Requirement-table context docs from the 2026 CSVs.** Generate `docs/domain/requirements-2026`
   (LP+HP tables + the 36/88 changed rows) and link it from `npm-vpm.md` / `validation.md` so
   agents stop reasoning against V4 numbering. Value/effort **S**.
   `Advances #149` (L1 sheets) and `#353` (first real building through the new kernel).
3. **Fill the 13 missing checks in `src/twinqa`** (archives+signature, district code, elevation,
   texel density, lights, glass UV, color attributes, embedded images, material links), reusing
   the SINTEZ thresholds from `sintez_checks_1.6.1.json`. Value/effort **L** (split per check).
   `Advances #149`.
4. **Name-fixer adapter:** wrap `name_fixer/naming_core` so an agent can plan+apply bulk renames
   from a JSON plan, replacing hand renaming. Value/effort **M**. `Advances #353`.
5. **UCX parity:** reconcile our `ucx_audit.py` gap band with SINTEZ `compute_ucx_collision_errors`
   (add intersect/nested, keep the D098 upper bound) and add a cross-check test. Value/effort **M**.
   `Advances #298` (L2 + SINTEZ verify on Vatutino).

Testable hypotheses for the hypothesizer:
- H1: "A fixture that passes all 13 shared `src/twinqa` checks also passes the corresponding
  SINTEZ groups" (expected true — validates parity; rejection = a threshold drift).
- H2: "The VPM texel lower bound 512 (SINTEZ) vs 520 (D097) flips no real fixture" (expected true —
  the 8 px/m delta is below float noise for real models; rejection = a fixture sits in the band).
- H3: "SINTEZ VPM polycount 1M vs our 150k never disagree on delivered OKS" (expected true, we are
  stricter; rejection = a delivered FBX exceeds 150k).

## Open questions for the user

1. VPM texel lower bound: 512 (SINTEZ 1.6.1) or 520 (D097)? (§6.1)
2. Confirm VPM 1 000 000 is the 2026 ceiling the project deliberately undercuts to 150 000 (D010). (§6.2)
3. Does the project adopt the 2026 UCX "too close <0.2 mm" check *in addition to* the D098 2 mm–1 cm
   band, or only the band? (§6.3)
4. UKEP digital-signature checks (new in 2.1.1) — do we need to verify signatures, or is that the
   applicant's responsibility? (§3)
5. Where should the 2026 tables live: a new `docs/domain/requirements-2026.md`, or inline in
   `npm-vpm.md` + `validation.md`? (§3)
