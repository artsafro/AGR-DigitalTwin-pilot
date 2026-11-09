# Pattern registry

A pattern is a portable rule for one building node, not a project story: a building name in a
pattern is a review error. File format `<slug>.md`, 20-40 lines: signs in the spec; how to build
it with engine functions; differences per profile (`npm_min` / `mid`); which checker confirms
it; traps, one line each. Historical source: `archive/2026-11:docs/HARNESS_PLAN.md` §7. Current registry: this file.

Status: draft / proven on benchmark / in work. A pattern changes only with the user's approval.

| Name | Slug | What it does | Status |
|---|---|---|---|
| Walls from a level contour | [`wall-from-contour`](wall-from-contour.md) | builds the exterior walls of one level from its contour points | draft |
| Opening plane with window ID | [`opening-plane`](opening-plane.md) | recessed plane in the opening with the type ID; base for the atlas and detailed windows | draft |
| Typical floor — build once, repeat | [`typical-floor-repeat`](typical-floor-repeat.md) | builds a floor once and copies it by `repeat_to` | draft |
| Corner that is not 90° | [`non-90-corner`](non-90-corner.md) | joins two walls at any angle without breaking the mesh | draft |
| Niche in the contour | [`contour-niche`](contour-niche.md) | facade recess given by contour points | draft |
| Parapet | [`parapet`](parapet.md) | roof edge along the contour of the top level | draft |
| Vent grille | [`vent-grille`](vent-grille.md) | inset grille: an opening of kind `grille`; texture in `npm_min`, geometry in `mid` | draft |
| Inset slab | [`roof-inset-plane`](roof-inset-plane.md) | every slab (roof in a parapet, terrace walkable) is a separate plate embedded into the faces around its hole, + more than `weld_m` (3 mm, user 2026-10-13 [D068]) up to 10 mm: no height; its joint = two open loops (hole A, plate B), required (user 2026-10-10 [D038]) | proven on benchmark (B01, B02, B02t) |
| Roof screen enclosure | [`roof-screen-enclosure`](roof-screen-enclosure.md) | screens round roof equipment (marked `roof_screens`): npm_min planes on their outer outline up to their top, no bottom, roof ids; mid / VPM a closed shell of the screen thickness inward (#91); spec v0.7 `roof_structures` (user 2026-10-13 [D067]) | draft (OBJ03) |
| Floor step | [`floor-step`](floor-step.md) | a contour per floor; at the step a ledge (up, roof ID) or a soffit (down, facade ID) | draft |
| Terrace | [`terrace`](terrace.md) | a floor-step ledge with a parapet from the spec (`terraces`, v0.4): outer face, inner face, cap, walkable part | proven on benchmark (`bench-b02t-terrace`, user 2026-10-10 [D042]) |
| Markup helpers | [`markup-helpers`](markup-helpers.md) | levels from `LEVEL_<name>` helpers only (name rule, no copy suffixes, once each); per-source routes: Max Point, Blender Empty (MH1), Revit Levels (MH2) | draft |
| Attached decor | [`attached-decor`](attached-decor.md) | host-derived railing/basket glass placement, >=10 mm per-vertex parallel clearance, rigid neighbour-closure repair with xView postcondition (#531) | draft |
| Primitive first | [`primitive-first`](primitive-first.md) | reduction, not reproduction: parts listed and confirmed first (build_as box / plane / frame / shell / profile-extrude / instance, joints), one primitive per element, profile steps < 7 cm collapse, silhouette test 0.07 m, nothing of the source dropped, instances for repeats, two deliveries (modules / npm), blocking `complexity` check (user 2026-10-14 [D080]) | draft |
| Facade decor inset | [`facade-decor-inset`](facade-decor-inset.md) | one simple solid per decor element, embedded 0.02 m with the inner face deleted, body not cut, 5 mm off openings, ids 26-30; 0.10 m or less is texture (user 2026-10-11 [D051]); by source modules: real sections, one mesh per run, piers run through and are never cut, storey bands as frames on the contour cut where they show without a source band, other bands stop 0.02 m inside piers, inset dark panels (user 2026-10-14 [D080], pattern `primitive-first`) | draft |

## Decision keywords

Grep lines for dated decisions that are not a building-node pattern. The quote and the rule text are in `docs/decisions.md`. A building name does not belong here.

- flat window glass quad, 4 points, 90 deg corner, two quads, 6 points: [D172]
- xView overlapping vertices 0.002 m, overlapping faces 0.005 m, 5 mm, 2 mm: [D173], same thresholds as [D152]
- embed or move a mesh to clear an overlap, 6 mm, do not cut: [D174]
- weld coincident seam (needs user confirmation): [D175]
- F8 option A, align the upper wall to the lower wall and split both walls so they share points: [D176]
- convert to mesh and weld 0.002 m before export, no poly round trip: [D177]
- weld fixes vertices, not faces: [D178]
- step strips narrower than 1 cm, remedy not decided: [D179]
