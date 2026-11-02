# Windows / doors — L1 requirement sheet

**Area and profiles:** windows, doors, curtain walls and balcony doors of an OKS, NPM and VPM:
the opening in the body, the opening plane, frames, glazing objects and materials, glass UV
and the GeoJSON glass description. `npm_min` / `mid` are engine profiles, not interchangeable
delivery certificates. Out of scope: the body shell around the opening (see [BODY](body.md)),
facade decor, atlas/UDIM production in general, terrace glass railings ([D087]) and UCX.

**Readiness:** [roadmap §4 and §7.2](../../research/capability-roadmap.md#4-coverage-matrix-upstream-main-ea7ecce)
records Windows / doors at **L1-partial**: an opening-plane pattern and choice pages exist; a
sheet, a skill (T-WIN-2, blocked by the window type library #4), a window benchmark (T-WIN-3)
and an area acceptance (T-WIN-4) are missing. This sheet is T-WIN-1, the L1 index; it does not
build, certify or accept a window. KPP1/PSU275 windows were accepted only as part of whole models.

**Reading:** the table is an index, not replacement rule text; short cues route to **Detail in**.
`reg p.N` is the one-based physical page of
[the supplied regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf);
`§S.I` is the table section number printed in the left column of that page, then the item
(e.g. reg p.32 §8.3 = section 8, item 3). Decisions are indexed in [docs/decisions.md](../../decisions.md).
`L2 coverage` names implemented checks only, with their limits; `none` means no automatic check
for the complete row today (a manual gate is not L2). The conflicts C23, C25 and C35 are pointed
to, not decided here.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| WIN-01 — Glazing is a flat surface | reg p.8 §3.10; reg p.32 §8.3 | Window-type glazing (windows, curtain walls, balcony doors) not seen from behind: no thickness, one flat surface | Window glazing not seen from behind: no thickness, one flat surface | Read back glazing and reject thickness or back shells; the plane checker sees spec openings only | `src/twinqa/geometry/checks.py:check_opening_planes` (partial: facing, seat and cover of spec opening planes; not thickness) | [Geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [opening plane](../patterns/opening-plane.md) |
| WIN-02 — Opening is the hole in the body | [D026]; [D029]; [D025] | Spec opening = the hole with its frame; the anchor is the body hole for any source, a plane or glass only gives `window_type`; a door recess from the floor (>= 1.9 m high, 0.7-3 m wide, one straight mouth) is an opening | Same spec basis | Extractor tests on synthetic sources; real-source classification is still reviewed | `tests/test_spec_openings.py`, `tests/test_spec_doors.py` (partial: spec extraction only) | [Wall from contour](../patterns/wall-from-contour.md), [opening plane](../patterns/opening-plane.md) |
| WIN-03 — NPM window is an opening plane with an atlas ID | reg p.7 §3.1; [D037]; [D048]; [D030] | `npm_min`: one plane per opening at the full opening depth (default 0.4 m), facing out; the window look is the atlas region of its type ID (group `opening`, 11-15) | No transferred rule; engine profile `mid` seats the plane at half depth as the base of a detailed window | Plane seat, facing and cover against the spec; atlas region per type by eye | `check_opening_planes`; `tests/qa/test_from_spec.py::test_checker_wants_the_plane_at_the_profiles_seat`, `::test_plane_seat_follows_the_profile` (synthetic specs) | [Opening plane](../patterns/opening-plane.md), [C24 / D037](../conflicts.md#c-between-local-sources-project-decisionslessons), [ADR-0001](../../adr/0001-material-ids-are-a-reading-scheme.md) |
| WIN-04 — Plane closes its reveal | reg p.8 §3.8; reg p.29 §3.15 | No physically missing polygon in view, including through translucent parts: the plane meets the reveal end, edges taken from wall faces | Same visibility rule, including through translucent constructions | Cover per opening; visual check for slits at the reveal | `check_opening_planes` (partial: cover >= 0.95, a project proposal); `tests/qa/test_geometry_checks.py::test_missing_opening_plane_fails_cover_and_leaves_a_hole` | [Opening plane traps](../patterns/opening-plane.md), [lessons](../geometry.md#job-level-rules-and-lessons-jobs-mostly-one-project-each) |
| WIN-05 — NPM frames as texture | reg p.7 §3.1 | Minor constructive and decorative elements that do not change the overall look are an image on the atlas; the project applies this to frames, mullions and sashes (`npm_min` = plane only) | See WIN-06 | V015 manual: atlas frame drawing against approved facades | none | [Geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [opening plane](../patterns/opening-plane.md) |
| WIN-06 — VPM frames: geometry or baked / C35 | reg p.32 §7; [D010] | See WIN-05 | Details recessed into or protruding from the main building geometry up to 5 cm are baked into the texture (kerbs excepted); `mid` library frames, mullions and infill recess are geometry; whether a frame in a reveal is such a detail is C35, open | Measure frame and infill relief against 5 cm; manual until C35 is decided | none | [C35](../conflicts.md#c-between-local-sources-project-decisionslessons), [C25 choice](../conflict-choices-2026-10-09.md#c25--infill-recess-behind-the-frame-mid), [library rule](../geometry.md#job-level-rules-and-lessons-jobs-mostly-one-project-each) |
| WIN-07 — Triangle fallback: windows to atlas planes | reg p.7 §3.6; reg p.28 §3.9; [D010] | <= 150 000 triangles per OKS FBX, windows included | Project target <= 150 000; above it windows become atlas textures on planes before geometry is added; hard limit 1 000 000 | Count triangles after export readback; above target is review, not fail | V003 (`src/twinqa/scene.py:scene_findings`, partial: counts only, not the window fallback); `tests/qa/test_scene.py::test_vpm_oks_triangles_project_target_and_hard_limit_conflict_1` | [Budgets](../npm-vpm.md#vpm-appendix-2), [C1 / D010](../conflicts.md#a-inside-the-regulation) |
| WIN-08 — NPM opaque glass in the atlas | reg p.10 §7.1; reg p.9 §5.10 | Glass is not a separate object; roughness and metallic maps are mandatory; glass white on Diffuse and Metallic, black on Roughness; no opacity map, or the glass UVs white on it | Not among the VPM glass rules (reg p.32 §8); VPM glazing is WIN-11 | Sample atlas pixels at glass UVs; the NPM PNG helper does not sample glass regions | none | [NPM textures](../uv-textures.md#npm-textures-app1), [materials](../materials.md#npm) |
| WIN-09 — NPM translucent glass objects | reg p.10 §7.2; reg p.6 §1.4; reg p.7 §2.3; reg p.11-12 §10.3.3 | Translucent glass is a separate `SM_{Address}_{NNN}_MainGlass` object with a special material; <= 20 translucent objects, no texture sets; split together with the OKS FBX | No transferred rule; VPM glazing is WIN-11 | Object inventory and names after readback | none | [NPM naming](../geometry.md#naming---npm-reg-p10-13), [NPM package](../npm-vpm.md#npm-appendix-1) |
| WIN-10 — NPM translucent material | reg p.8 §4.2-4.3; reg p.9 §4.6; reg p.13 §10.3.5 | No texture maps; colour only through material parameters; transparency 50 %; <= 7 materials named `M_Glass_01`..`07` project-wide | No transferred rule; VPM glass materials are WIN-11 and WIN-15 | Inspect materials after readback; V005 is unimplemented | none | [NPM materials](../materials.md#npm), [C17](../conflicts.md#b-regulation-vs-local-yaml--docs) |
| WIN-11 — VPM glazing is one object | reg p.28 §3.4; reg p.32 §8.1-8.2; reg p.30 §4.4 | n/a; NPM glass is WIN-08 to WIN-10 | All glazing of one model is one object separate from facades, with a special material and no texture maps; different physical or visual glass = different materials, <= 7; `*_MainGlass` never grouped with `*_Main` under one parent material | Read back object and material graph | none | [VPM materials](../materials.md#vpm), [geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| WIN-12 — Glass UV in UDIM 1001 | reg p.31 §5.2.2.1-5.2.2.2; [D030] | n/a: NPM glass has no texture sets | All `*_MainGlass` UVs inside tile 1001, maximum fill, margin from the tile border, overlaps allowed, one channel; glass goes to 1001 whatever its working material ID | V008 scene readback | V008 (`src/twinqa/scene.py:scene_findings`, partial: meshes named `*MainGlass` only); `tests/qa/test_scene.py::test_glass_outside_1001_and_split_pivot_fail` | [VPM UV](../uv-textures.md#vpm-uv--udim), [ADR-0001](../../adr/0001-material-ids-are-a-reading-scheme.md), [V008 limits](../validation.md#implementation-status-inventory-static-audit) |
| WIN-13 — VPM glass names | reg p.33 §10.4.2; reg p.34 §10.4.4 | NPM names are in WIN-09 and WIN-10 | Object `SM_{Address}_MainGlass` (when glazing exists); materials `M_{Address}_MainGlass_{SlotNumber}` | Inspect internal names after readback; V012 does not read mesh or material names | none | [VPM naming](../geometry.md#naming---vpm-reg-p33-36), [V012 limits](../validation.md#implementation-status-inventory-static-audit) |
| WIN-14 — VPM glass pivot | reg p.33 §9.5; [D018] | No glass-specific pivot rule | The glass model's pivot has the same coordinates as the OKS pivot | V013 shared pivot after readback | V013 (`src/twinqa/scene.py:_pivot_findings`); `tests/qa/test_scene.py::test_glass_outside_1001_and_split_pivot_fail` | [Pivots](../geometry.md#units-coordinates-pivots), [C19 / D018](../conflicts.md#b-regulation-vs-local-yaml--docs) |
| WIN-15 — Glasses in GeoJSON | reg p.55 §22; [D016] | n/a: NPM has no GeoJSON | `[]` without glass; else entries keyed by `M_{Address}_MainGlass_1`..`7` with color_RGB 0-255, transparency 0-1 (0 = fully transparent), refraction 1-3, roughness 0-1, metallicity 0-1 | V011 on the package GeoJSON | V011 (`src/twinqa/geojson.py:_glasses`); `tests/qa/test_validator.py::test_glasses_follow_checker_conflict_13` | [GeoJSON](../npm-vpm.md#geojson-vpm-only-app3), [C13 / D016](../conflicts.md#a-inside-the-regulation) |
| WIN-16 — Interior behind glazing / C23 | reg p.8 §3.12; reg p.29 §3.12 | Simplified interior walls, ceiling and floor only where seen through translucent parts | Interiors replaced by solid walls and slabs; wall thickness >= 10 cm | Sightline inspection through glazing; the shell policy C23 stays with the user | none | [BODY-L](body.md), [C23](../conflicts.md#c-between-local-sources-project-decisionslessons) |
| WIN-17 — Window types match the design / C25 | reg p.4 §1.3; reg p.24 §1.3 | Window type per opening from the source; one atlas region per type | Same types; `mid` library type with an infill recess behind the frame, C25 open | V015 manual (window types); the type library #4 waits for the user | none | [Window types](../../../library/windows/window_types.json), [C25](../conflicts.md#c-between-local-sources-project-decisionslessons), [V015](../validation.md#implementation-status-inventory-static-audit) |

Glass quad layout [D172]: a flat window with no bend is one quad (4 points); a bend keeps its segments; a 90 deg corner is one element of two quads sharing an edge (6 points). This note is not an extra requirement row. Detail in [geometry](../geometry.md) and [the decision log](../../decisions.md).

## Image verification and review evidence

The supplied PDF has 56 physical pages. Rendered with PyMuPDF 1.28.2 at scale 1.5 and visually
inspected: pages 4, 6, 7, 8, 9, 10, 11, 12, 13, 24, 28, 29, 30, 31, 32, 33, 34, 36 and 55
(every page the table cites; p.36 §12 was read to confirm alpha cut-outs are not a glazing rule). Renders stay local
(`C:/x/l1-evidence/windows/`, never committed). Reproduction:
`uv run --extra pdf-review python -c "import pymupdf; d=pymupdf.open('standards/source/Rasporyajenies19012026trebovaniya(2).pdf'); d[31].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save('win-p32.png')"`.

The table has **17 requirement rows**. Every regulation number printed in it (5 cm, 50 %, 7,
20, 1001, 10 cm, 150 000, 1 000 000, GeoJSON ranges) was read on the page images, not from OCR.
Project numbers (0.4 m default depth, 0.95 cover, door recess sizes) come from the linked decisions
and patterns, not from the PDF. Five evidence samples (short quotes transcribed from the rendered pages):

- **WIN-01** — reg p.8 §3.10: «Светопрозрачные конструкции оконного типа (окна, витражи, балконные двери и т.д.), не просматриваемые с обратной стороны, должны создаваться без толщины — в виде плоской поверхности».
- **WIN-06** — reg p.32 §7: «Декоративные элементы, мелкие детали, вдавленные или выступающие за основную геометрию здания до 5 см, запекаются в текстурную карту».
- **WIN-08** — reg p.9 §5.10: «месторасположение стекол представить на картах диффузного цвета и картах металличности белым цветом, на карте шероховатости – черным».
- **WIN-10** — reg p.8 §4.3: «Параметр прозрачности должен соответствовать 50%»; reg p.9 §4.6: «не должно превышать 7».
- **WIN-12** — reg p.31 §5.2.2.1: «UV-развертку всей геометрии светопрозрачных конструкций необходимо производить в пределах 1001 UDIM-плитки с максимальным заполнением».

C35 is new in this change: reg p.32 §7 (bake relief up to 5 cm) against the `mid` library frames
and the C25 infill recess (30 or 35 mm, both under 5 cm). It is recorded in
[conflicts.md](../conflicts.md#c-between-local-sources-project-decisionslessons), not decided.
C23 and C25 keep their status; C24 is decided [D037].

## L2 gaps

Rows with `none` (9):

- **WIN-05** — NPM atlas frame drawing against approved facades (manual V015 today).
- **WIN-06** — frame and infill relief against the 5 cm baking threshold; waits for C35.
- **WIN-08** — opaque-glass pixel rule at glass UVs on Diffuse, Metallic and Roughness.
- **WIN-09** — NPM translucent object count, texture-set absence and `MainGlass` names.
- **WIN-10** — NPM translucent material: no maps, 50 % transparency, `M_Glass_01..07`.
- **WIN-11** — VPM single glazing object, no maps, <= 7 materials, no parent grouping with Main.
- **WIN-13** — VPM internal glass object and material names.
- **WIN-16** — interior visible through glazing and minimum wall thickness; retain C23.
- **WIN-17** — window types against the approved design; waits for the type library #4 and C25.

These are L2 ticket candidates, not filed tickets. Partial checks in WIN-01/02/03/04/07/12 run on
synthetic specs or name-based readback; they do not close a window benchmark (T-WIN-3) or an
accepted real-object window case (T-WIN-4). No model, DCC session or delivery validation ran here.
