# vyatskaya-tow02 (Башня TOW02, ул. Вятская вл. 47–49) - mid-poly master → NPM-OKS, 2026-10-20

Pipeline status: closed at the review stage (2026-10-22, [D185])
Status: mid-poly master accepted ("4+", 2026-10-20); after the user's 3ds Max review (2026-10-21): geometry review fixes,
glass cleanup, run-strip atlas OKS 013 [D156], overlap fixes and the 3 decisions of 2026-10-21 (F8 option A in the body
builder, basket posts kept, 65.4 point contacts not welded) -> build-v030 / export-v005; real 3ds Max xView at 5 mm /
2 mm: Overlapping Faces 185 faces, Overlapping Vertices 0 (the builder's own check said 0 / 0). The user then finished
the model by hand in 3ds Max (2026-10-21, `outputs/xview-v005/tow02_ovl23_v001.max`) and accepted the base: "ты неплохо
справился с задачей, с этим можно работать". Review #514 done 2026-10-21 (`REVIEW-514.md`, PR #525). Job closed
2026-10-22 [D185]: the user's `for_placement/0213_Vyatskaya_Vl_47_49_05.fbx` stays as delivered; validate-delivery
not passed (`docs/deliveries/vyatskaya-tow02-npm-user-v05-2026-10-21.md`), zero-UV agreed, texture findings disputed
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
- Acceptance (compared 2026-10-21 at handover; master = `outputs/build-v025/tow02_tex.blend`, joined
  `outputs/export-v004/`; mid-poly line updated for build-v030 / export-v005):
  - [x] Body, decor (bands, fins), glass and openings separated as logical groups — met: TOW02_body, *_glass,
    fins F01–F26, ac_baskets, louvre, coping, top, soffit (Build log build-v013).
  - [x] Every level from the user's helpers built: colonnade, bend, typical, top storey, superstructures 1 and 2 —
    met (`cmp_all` elevation vs source, Build log build-v009/v013).
  - [x] Openings as planes (or windows where simpler), chosen per facade — met: ribbon planes at mid reveal,
    glass faces on the outline above 64.7 (decision 2026-10-20).
  - [ ] Mid-poly rules of docs/domain/geometry.md (quads, < 3.8 m, no doubles/T-junctions, normals) — mostly met,
    not fully: export-v005: 0 mismatched winding, Overlapping Vertices 2 mm = 0, Overlapping Faces 5 mm = 0, F8
    T-junctions gone (QA "same object, other" T-vertices 134 -> 0); 136 triangles (112 before + 24 net from the F8
    cuts); 304 boundary-on-boundary T-vertices remain at part contacts that are not welded by design (glass edges on
    walls/caps, reveal backs); evidence `outputs/xview-v004/qa_summary.json`. Not met in 3ds Max: xView 2026-10-21
    at 5 mm finds 185 overlapping faces on export-v005 (`outputs/xview-v005/xview_tol_report.jsonl`); the user fixed
    them by hand (top floors under-cut, extra edges, balcony glass railings) — see Build log "User finish".
    2026-10-22: met by the user's hand finish only (xView 0 / 0 after Mesh + Weld 0.002 m, `REVIEW-514.md` §2);
    our export-v005 stays not met.
  - [ ] NPM derived from the master — not met: textured (build-v025, [D156]) and joined into
    `SM_Vyatskaya_Vl_47_49_013_Main` (export-v004, quads); NPM naming/transform reset/triangulation/validate-delivery
    not done. Changed by [D185] (2026-10-22): the NPM is the user's hand-finished `_05.fbx`, derived from our
    export-v005; validate-delivery on it: not passed (6 fails: FBX 180 244 > 150 000 tris, 014/015 transforms,
    3 314 zero-area UV tris, xView vertices 10 before the weld, 013 set named 014, a 0.4 mm pair on 012/015);
    the user keeps the file as is, agrees on the zero-UV finding, disputes the texture findings.
- Later decisions:
  - 2026-10-21 quotes logged in `docs/decisions.md` (#534): glass quads [D172]; xView vertices 0.002 m and faces 0.005 m [D173] (same numbers as [D152]); embed or move, including the agreed 6 mm shifts [D174]; weld wording [D175] (needs user confirmation); F8 option A [D176] (align the upper wall to the lower wall and split both walls so they share points; baskets kept); Mesh then Weld 0.002 m before export, no Poly round trip [D177]; weld fixes vertices, not faces [D178]; step strips narrower than 1 cm, remedy not decided [D179]. A general skip of anything within 1 cm is not a logged decision.
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
- build-v017 (`outputs/build-v017/`, `scripts/clean_glass_blender.py` on build-v016) — user rule 2026-10-21 [D172], shown by
  hand in 3ds Max: flat window = one quad (4 points), bends keep their segments, 90° corner = two quads on one shared
  edge (6 points). body_glass 2 761 → 787 quads (447 elements: 379 single quads, 34 corners, 34 bends), top_glass
  509 → 86. Matches the user's manual result (816 quads) within 1 cm; the difference is coplanar pieces the user left
  split. Tests: `outputs/glassclean-test-v00{1,2,3}/`; user's export `outputs/max-v001/TOW02_*_glass.json`.
- build-v018 (`outputs/build-v018/`): build-v017 textured by the rewritten `scripts/texture_atlas_blender.py` —
  windows as source run strips (user 2026-10-21 "ленты как в источнике"): 31 strips, 77.25 px/m, 873 window faces
  matched by geometry; ray-cast check vs the source ≤ 1 cm except run B088 (1.5 cm, measurement gap).
- QA 2026-10-21 (user: only Overlapping Faces 5 mm and Overlapping Vertices 2 mm matter [D173], same thresholds as [D152]; `outputs/xview-v001..v003/`):
  xView tolerances cannot be set from script (dialog only, default 0.01 m) and xView computes only from a Max startup
  script (`scripts/xview_check.ms`), so the two checks were computed in Blender (`outputs/xview-v002/scripts/`).
  Found: all 6 418 TOW02_reveal faces wound into the wall (since build-v013; Max split 6 298 edges on import),
  2 548 overlapping face pairs, 977 coincident/near vertex pairs (`outputs/xview-v002/findings.json`).
- Fix chain (user rules 2026-10-21: no deleting, prefer no cutting — embed or move so parallel faces are ≥ 6 mm apart [D174];
  weld only coincident seams [D175], needs user confirmation): `build_review_fixes_blender.py` → build-v019, `fix_overlaps_blender.py` → build-v023,
  clean_glass → v024, texture → v025, `join_export_blender.py` (welds only seams body/top 64.7, body/soffit 6.9,
  top/top_glass; 675 pairs) → `outputs/export-v004/` (35 480 faces, 35 368 quads + 112 tris, 44 073 verts). Result:
  Overlapping Vertices 2 mm = 0, Overlapping Faces 5 mm = 121 pairs, all group F8; 0 mismatched winding (verified by
  the main session). Moves: AC baskets −6.6 mm, railings 0–12 mm, soffit steps into fins ≤ 22.7 mm, fins ≤ 2 mm.
  Superseded first run: build-v020..v022, export-v003 (`superseded.json`).
- Open after the fix chain (answered by the user 2026-10-21): (1) F8 -> option A [D176] (align the upper wall to the lower wall and split both walls so they share points) in `build_stack` (below; the post-hoc
  test `outputs/xview-v003/f8/option_a_body.blend` failed: it looked for wall points within 6 mm across the strip, but the
  strip corners slide 5-50 cm along the wall, so 0 points merged); (2) basket posts stay hidden 7 mm behind the glass;
  (3) 65.4 bow-ties -> not welded, moved apart (below); (4) builder root causes for the backlog: agent report (build_stack
  winding/offset_points/steps, top caps and railings, build_ac floor, build_soffit, build_fins).
- Chain check 2026-10-21: build-v013 -> v019 -> v023 -> v024 -> v025 rerun from the scripts in scratch is identical
  (geometry, UV, materials of all 37 objects); the build-v004 body (= build-v013 body) is reproduced exactly by
  `build_body_blender.build` with snap_m 0.03, collapse_shift_m 0.3 (now `CFG_TOW02`). So F8 is fixed in the builder and
  the chain is rerun from build-v013 instead of patching build-v025.
- build-v026 (`blender -b outputs/build-v013/tow02_master.blend --python scripts/build_body_blender.py -- outputs/build-v026`):
  TOW02_body rebuilt with the sliding-wall fix of `build_stack` (F8 option A): 6 bend side walls (edges 1 3 5 7 21 23)
  keep their line within <= 1.4 mm while their ends slide 5-50 cm per storey; at 8 joins (10.3-30.7, 37.5) the upper
  wall's bottom points are snapped onto the lower wall's line (max 1.38 mm), no step strip is built, and walls and steps
  are cut where they share points (`resolve_tjunctions`: 99 points, 18 wall cuts, 41 coplanar joins, split into quads +
  25 triangles, min angle 2.15 deg); 2 strip fractions that gave 4 mm strips at 23.9 dropped. Body 14 928 -> 14 855
  faces (14 830 quads + 25 tris); step strips < 6 mm 69 -> 0; new T-vertices 0 (134 old ones gone); 0 non-manifold,
  0 mismatched winding; loops 6.9 (257) and 64.7 (177) identical to build-v013, so soffit and top are untouched;
  TOW02_body_glass identical. vs build-v013 body: max 1.385 mm, 84 of 17 982 vertices moved (median 0.14 mm).
- build-v027 (review fixes on v026), build-v028 (`fix_overlaps_blender.py`; BODY_SLIVERS flip now only when the body
  still has step strips < 6 mm: 0 flipped here; on the old v019 it still gives v023 identically), build-v029
  (clean_glass: 787 / 86 quads as before), build-v030 (`tow02_tex.blend`, texture: same mapping numbers as v025) — all
  with the same commands as the fix chain (logs `run.log` / `texture_run.log` in each folder).
- export-v005 (`join_export_blender.py` on build-v030): 35 407 faces (35 271 quads + 136 tris), 44 000 verts, one
  material; seams welded body/top 328, body/soffit 257, top/top_glass 78; the 12 top_glass corners that would touch the
  top only at a point (bow-ties at 65.4/68.9 and 72.2/75.7, 6 corners) are not welded and moved 3 mm into the wall /
  behind the corner (`skip_point_contacts`).
- QA xview-v004 (FBX read back into an empty scene; scripts `outputs/xview-v004/scripts/`, table `qa_summary.json`):
  Overlapping Faces 5 mm 121 -> 0, Overlapping Vertices 2 mm 0, mismatched winding 0, non-manifold edges 0, bow-tie
  vertices 0, F8 strips 0, UV in 0-1 (0 outside), 0 zero-area faces / UV faces, readback vs joined max 0.07 mm, body
  vs build-v025 max 1.385 mm; window UVs identical on 863 of 873 faces (10 = glass faces with a moved corner). Technical
  QA only, and its Overlapping Faces check did not match 3ds Max (next two entries).
- Independent check 2026-10-21 (independent-checker agent, export-v005 FBX only, own method: parallel <= 1 deg, gap
  < 5 mm over the overlap region, area > 1e-6 m2): 23 overlapping face pairs (4 at z 14.2/17.6 gap 4.1 mm; 16 coplanar
  at the soffit z 6.9; 3 opposite pairs at 69.52 / 76.32), and 158 on export-v004 where the builder QA said 121. All
  other checks equal to the builder QA. Markers: `outputs/xview-v005/ovl_pairs_blender.py` -> `ovl_pairs.json`,
  `tow02_ovl_pairs.fbx` (23 + 58 tiny contact slivers < 1.1e-5 m2 at 69.175 / 75.975).
- xView 2026-10-21 in a separate 3ds Max 2024 (`outputs/xview-v005/`): default tolerance 0.01 m (`run.ms` ->
  `xview_report.jsonl`): Overlapping Faces 3 105, Overlapping Vertices 1 210; at the user's tolerances set through
  `OverlappingFaces.tolerance = 0.005` / `OverlappingVertices.tolerance = 0.002` (the checker interfaces do expose
  them; earlier note "dialog only" was wrong) in `open_ovl.ms` -> `xview_tol_report.jsonl`: Overlapping Vertices 0,
  **Overlapping Faces 185 faces**. The face list was not exported (the user stopped the runs to fix by hand).
- User finish 2026-10-21 (3ds Max 2024, by hand, saved into `outputs/xview-v005/tow02_ovl23_v001.max`, SHA-256
  1c4c3a8e…01fddf; it replaced our marker scene of the same name): top floors had under-cut geometry and extra edges
  (overlaps there), edges removed; balcony glass railings rebuilt so they look right and do not overlap; texture
  slightly re-unwrapped, colours changed; our windows and main geometry kept. User verdict: "ты неплохо справился с
  задачей, с этим можно работать ... базу и большую часть работы ты выполнил". **Final (user 2026-10-21):**
  `C:/Users/artsafro/Desktop/!3D viz/NTR/26_Vyatskoe/001 - Моделирование НПМ с нуля/001 - Моделирование НПМ с нуля/for_placement/0213_Vyatskaya_Vl_47_49_05.fbx`,
  object `SM_..._013_Main` (FBX 6 302 640 bytes, 17:29, SHA-256 2fd80081…71da68; package prefix 0213, files
  _01.._05 next to it). The .max above is an intermediate save. Comparison with export-v005: open (issue #514).
- build-fins-fix (PR #392 P1, 2026-10-20): `scripts/build_fins.py` now refuses an existing, non-empty
  `build-vNNN-fins` output version (clear error naming the next free version, e.g. `build-v014-fins`) instead of
  re-creating it with `mkdir(exist_ok=True)` and truncating `fins.obj`/`fins.mtl`; a fresh or empty directory is
  still created as before.
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
- Tolerance note in this job file: anything within 1 cm is skipped (weld, snap, column merge). Not a logged decision. The only logged step quote is strips narrower than 1 cm, remedy not decided [D179]; whether overlaps below 1 cm are skipped is open in `docs/domain/conflicts.md`. [D153] is Ground relief, a different rule.
- 2026-10-21 Max export prep [D177] [D178]: convert to Mesh and Weld at 0.002 m before export; do not round-trip through Poly; the weld fixes vertices, not faces.
- 2026-10-21: record the cfg of every builder run (the body cfg had to be reconstructed by matching build-v004; now
  `CFG_TOW02`); first check that the chain reproduces the current version bit-for-bit — then a builder fix plus a
  chain rerun is cheaper and cleaner than patching the finished master.
- 2026-10-21: an own "Overlapping Faces" in Blender is not xView. The builder's check said 0 while xView at the same
  5 mm said 185 faces and an independent method 23 pairs; only 3ds Max xView with `OverlappingFaces.tolerance` set by
  script counts for this user. The logged thresholds are [D173], the same numbers as [D152]. Run it (`outputs/xview-v005/open_ovl.ms`, ~2.5 min on 35k faces) before reporting.
- 2026-10-21, review #514 (`REVIEW-514.md`): the repository already had an xView-exact checker, `dt_ai.ops.inv_xview`
  (185/185 on export-v005, 52 s, no DCC), merged on main the first day of this job; the job branch never synced with
  main until the end. Sync the job branch with main at every session start; use `inv_xview` (local coordinates) as
  the overlap gate during the build loop and xView (`scripts/xview_review.ms`) as the final confirmation.
- Weld at export fixes Overlapping Vertices only; contacts of separate parts in one mesh (T-vertices, edge on edge,
  bow-tie corners) are Overlapping Faces and must be removed in the build. A welded mesh converted back to Editable
  Poly re-splits non-manifold vertices (user, 2026-10-21). Moving a contact apart by less than the 5 mm face
  tolerance (`skip_point_contacts`, 3 mm) does not remove it. Root causes per part (coincident constants, two
  separately simplified envelopes, one level reused for two parallel faces, a one-sided seam simplification in
  `clean_glass`): `REVIEW-514.md` §7.
- Inputs of the builders that live in ignored `outputs/`: `measure-v001/typical/typical_floor.json`,
  `fins.json`; `measure-v002/bend_rings/bend_rings.json`; `measure-v002/top_parts/top_parts.json`; their
  measurement scripts sit next to them (`outputs/measure-v00N/*/scripts/`).

## Open
- 2026-10-20: two stale copies `scripts/measure_bend.py`, `scripts/measure_soffit.py` deleted (user "да"); the
  working versions are in `outputs/measure-v001/bend_top/scripts/`.

## Next
Job closed at the review stage [D185]. Nothing left in this job. Follow-ups run on the board: #527-#535
(overlap gate, xView runner, branch freshness, engine join, decor placement, EG6 analysis, intake, decisions
backfill, fast checks); texture rules for NPM validation: backlog Q8.
