# Pattern: roof-screen-enclosure (draft)

Status: draft (user decision 2026-10-13 [D067], OBJ03). Spec v0.7 `roof_structures`.

## Signs in the source

- On the roof: screens (louvres, mesh fences) round roof equipment, standing above the roof level; the
  equipment blocks stand inside them. OBJ03: `RailClone2142` up to 102.56 m over the roof at 96.55 m.
- The marking is the human's: `object.json` → `roof_screens: [mesh names]`, as with `slabs`. The extractor does
  not guess which meshes are screens.

## The rule (user, 2026-10-13 [D067])

1. The enclosure is part of the body's silhouette (an exit to the roof), not an attachment.
2. `npm_min`: planes on the screens' outer outline, from the roof level up to their top, facing out, and a top
   plane at the top - a box with no bottom and no thickness. The equipment blocks inside are not modelled.
   A build by source modules follows the source: screens with no top get no top plane (OBJ03, user 2026-10-14 [D086]);
   the checker allows the open ring on the outline at the top then.
   Ids: the roof group (21-25).
3. `mid` / VPM: the same planes as a shell (the screen's thickness) set inward, as a Shell modifier makes it
   (issue #91): the outer walls and top as in `npm_min`, inner walls on the outline set in by the thickness (mitred)
   up to a ceiling one thickness under the top, and the rim between them on the roof level - one closed solid,
   roof ids. Thickness as the parapet's rule 4 ([D061]): the spec's `thickness_m` (measured from the source, else the
   object's `parapet_thickness_default_m`), else the build input's parapet thickness, else a `BuildError`; a thickness
   that leaves no single hollow in plan or none under the top is a `BuildError`, and so is one not over two steps of
   the 1 µm output grid (`SHELL_MIN_M` = 2e-6 m) or any shell that the grid collapses (a face with repeated vertices
   or no area, not closed, no volume) - never clamped (review of PR #500). Two mid shells that touch, overlap or lie
   within `SHELL_MIN_M` of each other in plan are a `BuildError` naming both (their shells would weld into a
   non-manifold mesh), and the merged mesh is checked closed once more after every weld (review 2 of PR #500).
   The blocks inside are decided
   later (not built).
4. What lies under the outline - the equipment, the screens, their steep parts - is no roof question: the roof
   check keeps only the flat roof at the level there, and the enclosure closes the roof from above.

## Spec

`roof_structures: [{kind: "screen", outline: [[x, y], …], z_top_m, thickness_m?}]` (spec v0.7). The extractor reads the
outline as the outer line of the screens' plan (their faces projected, joints up to 0.10 m closed,
Douglas–Peucker 0.10 m) and the top as their highest point. A name not in the source, a screen not above the
roof or a plan that does not close is a stop. A group of screens must enclose exactly one space (a hole of
its plan not capped by the screens above and below - a thick screen's own inside is capped twice): none is an
open screen, two or more (enclosures sharing screens) is a stop too - their tops cannot be told apart.
A screen's own inside is capped at the screens' foot and above it; an enclosure's space is open to the roof at the
foot (a shell's hollow under its ceiling too). A ring of screens in a group's space with screen between them at
the foot (the inner face of a screen thicker than 0.10 m) is one group with it.
`thickness_m` (issue #91): the faces of the screens' section at mid height that are screen (an odd number of caps
above them) make one ring on the outline whose inner line is the outer one set in by one thickness (mitred,
0.005 m), measured at the inner edges' midpoints; else the object's `parapet_thickness_default_m`; the report marks
`thickness.by` (`measured`, `parapet thickness by default`, `not read, no default`) and `why`. Planes have no ring.

## Check

- The enclosure's wall bottom is a flat closed open loop at the roof level on the spec's outline: allowed
  (`roof-structure`), it takes no part in the slab joints of `roof-inset-plane`.

## Traps

- An unmarked enclosure is read as roof structure: steep equipment tops stop the roof ("a pitched roof").
