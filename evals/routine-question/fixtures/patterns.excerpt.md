EXCERPT of `docs/domain/patterns/INDEX.md` (its header and 7 real rows, copied 2026-10-15): the reference
evidence of this task, so a reference verdict does not change when a pattern is added. The real run reads the
whole file.

| Name | Slug | What it does | Status |
|---|---|---|---|
| Walls from a level contour | `wall-from-contour` | builds the exterior walls of one level from its contour points | draft |
| Opening plane with window ID | `opening-plane` | recessed plane in the opening with the type ID; base for the atlas and detailed windows | draft |
| Typical floor — build once, repeat | `typical-floor-repeat` | builds a floor once and copies it by `repeat_to` | draft |
| Parapet | `parapet` | roof edge along the contour of the top level | draft |
| Inset slab | `roof-inset-plane` | every slab (roof in a parapet, terrace walkable) is a separate plate embedded into the faces around its hole, +2-10 mm: no height; its joint = two open loops (hole A, plate B), required (user 2026-10-10 [D038]) | proven on benchmark (B01, B02, B02t) |
| Floor step | `floor-step` | a contour per floor; at the step a ledge (up, roof ID) or a soffit (down, facade ID) | draft |
| Primitive first | `primitive-first` | reduction, not reproduction: parts listed and confirmed first (build_as box / plane / frame / shell / profile-extrude / instance, joints), one primitive per element, profile steps < 7 cm collapse, silhouette test 0.07 m, nothing of the source dropped, instances for repeats, two deliveries (modules / npm), blocking `complexity` check (user 2026-10-14 [D080]) | draft |
