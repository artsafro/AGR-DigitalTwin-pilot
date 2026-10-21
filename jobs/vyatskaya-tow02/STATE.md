# vyatskaya-tow02 (Башня TOW02, ул. Вятская вл. 47–49) - mid-poly master → NPM-OKS, 2026-10-20

Pipeline status: draft
Status: mid-poly master accepted by the user as "4+" (2026-10-20); textured master build-v015 (module atlas, OKS 013
[D156]) waiting for the user's review; NPM derivation next
Context: GLOSSARY.md (Body, NPM, Level contour), docs/domain/geometry.md (project modeling rules),
docs/HARNESS_PLAN.md §3–4, §14–16, docs/backlog.md EG1, EG2, EG4, EG6, docs/domain/patterns/wall-from-contour.md,
terrace.md, facade-decor-inset.md.

## Requirement

> Я открою Blender, подгружу туда модель. Ты из него возьмешь эту модель и начнешь работать в Blender, в котором
> тебе удобно. Нужно проанализировать корпус, который я тебе дам. Соответственно, определить декор-элементы,
> бадик-элементы, стекла, проемы и так далее, как обычно мы работаем. Вот, и попробовать смоделировать модель под
> Медполе с последующим переводом в NPM. Если проще проемы делать плейном, то тогда делаем проемы с плейном. Если
> проще окошки поставить, поставим окошки. Тут смотри сам. (user, 2026-10-20; voice input: «Медполе» = mid-poly,
> «бадик» = body)

- Profile: mid-poly master (`mid`), then NPM-OKS.
- Acceptance (compared 2026-10-20 at handover; master = `outputs/build-v013/tow02_master.blend`):
  - [x] Body, decor (bands, fins), glass and openings separated as logical groups — met: TOW02_body, *_glass,
    fins F01–F26, ac_baskets, louvre, coping, top, soffit (Build log build-v013).
  - [x] Every level from the user's helpers built: colonnade, bend, typical, top storey, superstructures 1 and 2 —
    met (`cmp_all` elevation vs source, Build log build-v009/v013).
  - [x] Openings as planes (or windows where simpler), chosen per facade — met: ribbon planes at mid reveal,
    glass faces on the outline above 64.7 (decision 2026-10-20).
  - [ ] Mid-poly rules of docs/domain/geometry.md (quads, < 3.8 m, no doubles/T-junctions, normals) — mostly met,
    not fully: 64 triangles (soffit slab 57, top 6, body 1) and 44 faces with a side < 2 cm kept as listed
    exceptions; no independent-checker run yet; user verdict "4+", detailed look pending.
  - [ ] NPM derived from the master — not met: next stage (texturing → NPM).
- Later decisions:
  - 2026-10-20: levels (helpers `Empty`…`Empty.007`, z 0.04 / 6.906 / 31.367 / 65.405 / 69.456 / 72.201 / 76.25 /
    79.237): 0.04–6.9 colonnade (model it), 6.9–31.37 bend, 31.37–65.4 typical, 65.4–69.46 parapet storey,
    69.46–76.25 superstructure 1, 76.25–79.24 superstructure 2. Stylobate is in another file, out of scope.
  - 2026-10-20 (answer "ок" to the build defaults): ribbon glazing as planes at mid reveal, mullions in texture;
    floors 31.4 and 34.8 built as bend variants, typical module from ring 37.5; fins: outside part only, embed
    >= 10 mm, profile change A↔B kept, 1.6° axis skew kept; steps < 0.15 m dropped; AC baskets one-sided planes
    with opacity; railings single glass planes; `#199` bands opaque; louvre slot = opacity plane per floor + plates.
  - 2026-10-20: route = hybrid. Body by the engine (object.json → `dt spec extract` → `from_spec`); rounded corners /
    corner ribbons, curved fins and glass railings as EG6 scripts (docs/backlog.md).
  - 2026-10-20 (user "да"): engine route dropped for this source. Panelised run (slabs as body, frame rotZ −62°,
    22 levels): 20 min, 889 openings all unsized (questions), 0 decor, wrong terrace parapets; engine build
    BuildError on 2D plan weld (3.6 mm > weld_m 3 mm); stopped after 64 min (`pipeline/spec-v002.*`,
    `outputs/spec-v001/engine-v001.log`).
    Route = direct "Lego" build from measurements: body rings → opening planes → decor → top volumes, one object
    per part, then assembly and check. Scripts under EG6 (extended).

## Sources
- User scene (Blender 4.4 file, opened in 5.1, read only):
  `C:/Users/artsafro/Desktop/!3D viz/NTR/26_Vyatskoe/001 - Моделирование НПМ с нуля/001 - Моделирование НПМ с нуля/Untitled.blend`
  (72 299 258 bytes). Siblings: `0200_Vyatskaya_Vl_47_49_0{1,2}.fbx`, `2026-08-26_ARCH_A+C.fbx`, `.max` scenes.
- Objects (from 3ds Max, all triangles, scale ±0.01 + rotation not applied): `RC_TOW_02` (facade, 604k tris,
  z 6.9–79.25), `RC_TOW_Lapatki_02` (fins, 81k tris, z 0–72.2), `SLAB_TOW_02` (24 slabs, reference only).
- Building-local frame: world rotated 56.7° about Z (`scripts/inspect_sections.py`).

## Outputs
- `outputs/build-v001/tow02_master_work.blend` — work copy (source objects untouched so far).
- `outputs/measure-v001/` — source arrays, overview images; `typical/` (typical floor, fins) and `bend_top/`
  (bend floors, top volumes, soffit) measurements with their scripts.

## Build log
- build-v002 (`outputs/build-v002/tow02_master.blend`, collection `TOW02_master`): `TOW02_body_typical` — 8 typical
  rings z 37.5–64.7 from the 44-vertex outline, 27 ribbon runs per storey, reveal 0.12 m, 2 424 quads, no
  non-manifold edges; `TOW02_body_typical_glass` — 376 planes at mid reveal (+10 mm overlap). Check vs source
  (BVH nearest): body facade to source #210 median 0 / max 17 mm; glass plane to source glass median 60 mm (= mid
  reveal as designed), max 109 mm at faceted corners. Script `scripts/build_body_blender.py` (EG6).
- build-v004 (`outputs/build-v004/tow02_master.blend`): `TOW02_body` replaces the typical-only body — 17 rings
  z 6.9–64.7 (9 bend rings from `outputs/measure-v002/bend_rings/bend_rings.json` + 8 typical), step soffits
  between rings (688 quads, chains 43→17, 19→25, 31→41 cut into strips so walls and soffits share vertices),
  14 928 faces, 0 non-manifold, 0 open edges besides stack top/bottom and reveal backs. Tolerances: user
  2026-10-20 "все что в 1 см погрешность мы пропускаем" → column/vertex merge 1 cm; fixed-edge lines snapped to
  the reference ring (max 0.5 mm). Exceptions: 1 triangle (T-junction where ring 34.5 meets typical, edge 7,
  15 cm) and 1 added quad (collapsed jog at 10.3); 44 faces with a side < 2 cm. Check vs source (BVH): walls
  median 0 / p95 5 mm / max 70 mm (chamfered source corner at vertices 0/20); glass planes median 61 mm behind
  source glass (= mid reveal). `TOW02_body_glass`: 2 761 planes.
- build-v007 (`outputs/build-v007/tow02_master.blend`): + 26 fins `TOW02_fin_F01..F26` imported from
  `outputs/build-v003-fins/fins.obj` (`scripts/build_fins.py`, EG6): 8 458 quads, closed, outward normals;
  outside part only, embed ≥ 10 mm (vs source body); full profile below 7.31 (colonnade) and on F01/F14/F25;
  tops lowered 6 mm (72.194 / 65.394) against coplanar roof faces. Outer faces vs source fins median 0.2 mm.
- build-v008 (`outputs/build-v008/tow02_master.blend`): + decor from `scripts/build_decor_blender.py` (EG6, test
  run `outputs/build-v006-decor/`): `TOW02_ac_baskets` 37 units, one-sided planes, 655 quads (vs source #217
  p95 19 mm); `TOW02_ac_railing_glass` 333 quads (p95 11 mm); `TOW02_louvre` 18 opacity planes + `TOW02_louvre_plates`
  19 levels; `TOW02_soffit` over the colonnade closes the body bottom loop (257/257 vertices, 0 T-junctions),
  1 211 quads + 57 triangles in the 7.3 slab fill (odd boundary count). The 20 "balconies" of bend.json are AC
  units 0–19 (no separate object). Opacity materials are placeholders (no node setup yet). Open: AC unit 36 and
  the louvre screen above 64.7 wait for the top walls; bottom louvre plate 7.083 shows under the 7.3 slab (as source).
- build-v009 (`outputs/build-v009/tow02_master.blend`) — full mid-poly master: + `TOW02_top` (3 483 faces: walls,
  reveals, caps, copings, cap-band protrusion 71.5–72.2 with own outline, boxes), `TOW02_top_glass` (509: glass
  faces on the outline + mid-reveal planes), `TOW02_railing_glass` (66; frames folded into the plane) from
  `scripts/build_top_blender.py` (EG6, test `outputs/build-v005-top/`). Top 64.7 row = body top loop 328/328
  vertices, 0 T-junctions; outer faces vs source median 0.1 mm / p95 1.9 cm / max 14 cm (copings); 6 triangles.
  Louvre above 64.7 extended to the top walls in the GUI (plane 5.4 cm, plate 69.5 4.2 cm gap → 1 cm embed;
  manual bmesh fix, not in build_decor_blender.py yet).
  Totals: 32 518 faces, 64 triangles (body 1, soffit 57, top 6), 0 n-gons; ~65 k triangles when triangulated.
- 2026-10-20 user review (helpers 01–04 saved by the user into build-v009): (1) AC baskets get a floor polygon;
  (2) fin tops +8 mm above the roof/ledge (72.208 / 65.408); (3) roof copings = one mesh, one rectangular section,
  no stepped transitions; (4) louvre as geometry instead of opacity planes.
- build-v013 (`outputs/build-v013/tow02_master.blend`, from build-v009 + the 4 edits): fins regenerated
  (`build_fins.py build-v012-fins`, CAP_DROP −0.008); decor rebuilt (`outputs/build-v010-decor/` test):
  37 basket floors (`TOW02_ac_floor`), `TOW02_louvre` 267 blade boxes (1 666 quads, 15/floor, 0.268 × 0.051 m,
  pitch 0.153; vs source median 0 / p95 26 mm), plates 19 boxes, ends embedded 12 mm into body/top (louvre hand
  patch superseded); top rebuilt (`outputs/build-v011-top/` test): `TOW02_coping` 238 quads, section 0.83 × 0.16 m
  (0.10 out + 0.73 in, 10 mm sunk), mitred, NW open with capped ends, roof closed ring; 10 cm jogs and two ~13 cm
  steps dropped. Totals 34 074 faces, 64 triangles. User helper empties 01–04 still in the scene.
- Texturing reference (2026-10-20, read only): accepted NPM `0200_Vyatskaya_Vl_47_49_02.fbx` next to the source,
  `SM_..._013_Main` (73.46 m; 014 is its mirrored twin, same mesh and UV). Its `atlas_2048_1` = four baked
  orthographic elevations A–D (~17.2 px/m, one planar island per facade plane) + dark / grey / glass swatches for
  everything else; m/r binary (glass m1 r0). Not reusable 1:1: TOW02 has ~2 storeys more and its top starts ~5.8 m
  higher (window ribbons vs atlas rows IoU 0.57–0.70). Analysis: `outputs/uvref-v001/ref013_uv_analysis.json`,
  `ref013_uv_overlay_by_category.png`, `ref013_atlas_contact_sheet.png`.
- build-v014 (`outputs/build-v014/`, superseded): first run of `scripts/texture_atlas_blender.py` with one tile per
  (height, n panes) per glass face; 2 383 of 2 761 body glass faces are < 0.5 m (ribbons are cut by body columns into
  runs of 8–15 faces: 458 m narrow vs 637 m wide), so most glass got no mullions.
- build-v015 (`outputs/build-v015/tow02_tex.blend`, textures `outputs/build-v015/textures/T_Vyatskaya_Vl_47_49_013_Main_{d,m,r}_1.png`,
  layout `atlas_layout.json`) [D156]: `scripts/texture_atlas_blender.py` on build-v013 (input not saved). One material
  `M_Vyatskaya_Vl_47_49_013_Main_1`, UV `UV`, 200 px/m. Window strips of 7 panes: storey 2.7 m (frame 0.05, vision
  to 2.15, transom 2.15–2.20, fanlight 2.20–2.65), storey 3.5 m (transom 2.95–3.00, ASSUMPTION), band 0.7 m; mullion
  0.055, pitch 1.0. Glass runs (faces joined by shared vertical edges) split into round(L / 1.0) equal panes, each face
  takes its pane range shifted by an integer (mullions continuous across faces, geometry not cut). 13 solid swatches
  (wall, reveal, band199, soffit, fin_main, fin_narrow_dark, fin_narrow_light, louvre, roof, coping, ac_perforated,
  ac_floor, glass_solid); face int attribute `tow02_finish` keeps the finish. Readback: 37 objects, 34 074 faces,
  all with UV in 0–1, 0 zero-area UV faces, one material; glass: 3 186 faces on window strips, 483 on glass_solid
  (railings 399, top slivers 84). Renders `outputs/build-v015/chk_*.png`. Helper empties 01–04 still present.
- Review 2026-10-21 (user, 3ds Max side by side with the source; `outputs/review-v001/`: `max/` pairs, `windows/`
  per-run source window layout, `decor/` baskets and louvre): no uniform mullion pitch in the source (fixed panes
  0.335–1.465 m + an openable sash with its own 5 cm frame, almost always the rightmost pane; 49 run types; typical
  floors identical); top ring 65.40–68.90 and superstructure glass 72.2–75.7 are full-height panes without transoms
  (the 3.5 m transom of build-v015 was wrong); baskets have a 50 mm coping and 4 posts at the bends; the louvre has no
  plates but 1 crossbar per storey at the mouth and 15 rails 0.051 × 0.183 running 6 m into the recess.
- build-v016 (`outputs/build-v016/`, `scripts/build_review_fixes_blender.py` on build-v013): new `TOW02_ac_coping`
  (coping 50 mm + 4 posts per unit, 1 628 quads), `TOW02_ac_railing_glass` shell 20 mm (333 → 666, no caps, 5 mm into
  floor and coping), `TOW02_louvre` rebuilt (271 continuous blades, 18 crossbars, 286 rails; 1 666 → 3 698),
  `TOW02_louvre_plates` deleted; roof boxes: the source is hollow too (rim 76.25–79.25, slab 78.75), so only the box roof
  faces got `TOW02_shaft_cap` (light; user 2026-10-21: keep the boxes hollow as in the source); ledge 72.2 exists in the source and is dark → `TOW02_ledge_dark`. Distances to
  the source: coping/posts median ≤ 0.2 mm, p95 ≤ 2 mm; louvre median 0.3 mm. Open: top wall at the louvre screen
  ~12 cm short of the source (`TOW02_top`).
- build-v017 (`outputs/build-v017/`, `scripts/clean_glass_blender.py` on build-v016) — user rule 2026-10-21, shown by
  hand in 3ds Max: flat window = one quad (4 points), bends keep their segments, 90° corner = two quads on one shared
  edge (6 points). body_glass 2 761 → 787 quads (447 elements: 379 single quads, 34 corners, 34 bends), top_glass
  509 → 86. Matches the user's manual result (816 quads) within 1 cm; the difference is coplanar pieces the user left
  split. Tests: `outputs/glassclean-test-v00{1,2,3}/`; user's export `outputs/max-v001/TOW02_*_glass.json`.
- build-v018 (`outputs/build-v018/`): build-v017 textured by the rewritten `scripts/texture_atlas_blender.py` —
  windows as source run strips (user 2026-10-21 "ленты как в источнике"): 31 strips, 77.25 px/m, 873 window faces
  matched by geometry; ray-cast check vs the source ≤ 1 cm except run B088 (1.5 cm, measurement gap).
- QA 2026-10-21 (user: only Overlapping Faces 5 mm and Overlapping Vertices 2 mm matter; `outputs/xview-v001..v003/`):
  xView tolerances cannot be set from script (dialog only, default 0.01 m) and xView computes only from a Max startup
  script (`scripts/xview_check.ms`), so the two checks were computed in Blender (`outputs/xview-v002/scripts/`).
  Found: all 6 418 TOW02_reveal faces wound into the wall (since build-v013; Max split 6 298 edges on import),
  2 548 overlapping face pairs, 977 coincident/near vertex pairs (`outputs/xview-v002/findings.json`).
- Fix chain (user rules 2026-10-21: no deleting, prefer no cutting — embed or move so parallel faces are ≥ 6 mm apart;
  weld only coincident seams): `build_review_fixes_blender.py` → build-v019, `fix_overlaps_blender.py` → build-v023,
  clean_glass → v024, texture → v025, `join_export_blender.py` (welds only seams body/top 64.7, body/soffit 6.9,
  top/top_glass; 675 pairs) → `outputs/export-v004/` (35 480 faces, 35 368 quads + 112 tris, 44 073 verts). Result:
  Overlapping Vertices 2 mm = 0, Overlapping Faces 5 mm = 121 pairs, all group F8; 0 mismatched winding (verified by
  the main session). Moves: AC baskets −6.6 mm, railings 0–12 mm, soffit steps into fins ≤ 22.7 mm, fins ≤ 2 mm.
  Superseded first run: build-v020..v022, export-v003 (`superseded.json`).
- Open after the fix chain: (1) F8 step strips at 8 ring joins (69 strips < 6 mm): option A = snap + cut walls so they
  share points (needs a proper implementation in `build_stack`; the automatic test `outputs/xview-v003/f8/option_a_body.blend`
  failed, do not use), option B = 6.5 mm ledge (not recommended); (2) basket posts are now 7 mm behind the glass outer
  face and hidden by it — alternative: glass ~13 mm inward so posts show; (3) 12 bowtie vertices from the
  top/top_glass seam weld at 65.4 (Max will split them → coincident vertices); (4) builder root causes for the backlog
  are listed in the agent report (build_stack winding/offset_points/steps, top caps and railings, build_ac floor,
  build_soffit, build_fins).
- Was in progress (agents): top above 64.7 (`scripts/build_top_blender.py` → `outputs/build-v005-top/`; decision:
  cap-band protrusion 71.5–72.2 up to 0.12 m modelled with its own outline); facade decor — AC baskets, louvre,
  balconies, soffit over the colonnade (`scripts/build_decor_blender.py` → `outputs/build-v006-decor/`).
- Done earlier (data agents): bend ring outlines (`outputs/measure-v002/bend_rings/`), top parts
  (`outputs/measure-v002/top_parts/`), fins generator (`scripts/build_fins.py` → `outputs/build-v003-fins/`).

## Lessons (2026-10-20)
- User verdict on the mid-poly master: "4+", accuracy and geometry fine, but too slow ("раньше было быстрее").
- Time sinks: the engine route (~1.5 h: extractor 20 min, stuck build 64 min) on a source it cannot read;
  measurement agents 35–55 min each; three rewrites of the ring-stack step logic (T-junctions at differing storeys).
- For a panelised curtain-wall source: check the source class first (connected parts vs area of the largest);
  if there is no shell, go straight to measurements → Lego build, do not start the extractor.
- Tolerance rule from the user: anything within 1 cm is skipped (weld, snap, column merge).
- Inputs of the builders that live in ignored `outputs/`: `measure-v001/typical/typical_floor.json`,
  `fins.json`; `measure-v002/bend_rings/bend_rings.json`; `measure-v002/top_parts/top_parts.json`; their
  measurement scripts sit next to them (`outputs/measure-v00N/*/scripts/`).

## Open
- 2026-10-20: two stale copies `scripts/measure_bend.py`, `scripts/measure_soffit.py` deleted (user "да"); the
  working versions are in `outputs/measure-v001/bend_top/scripts/`.

## Next
1. Mid-poly modelling closed by the user 2026-10-20 ("по моделингу мы закончили", 4+); master = build-v013.
2. Texturing done in build-v015 (module atlas, OKS 013 [D156]); waiting for the user's review (3.5 m window layout
   is an assumption). Then NPM derivation: join TOW02_* into `SM_Vyatskaya_Vl_47_49_013_Main` (prefix
   `0200_Vyatskaya_Vl_47_49`), remove helper empties, triangulate, FBX export, validate-delivery.
3. Optional: independent check of the master (independent-checker) before NPM.
