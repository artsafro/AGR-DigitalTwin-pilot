# DRAFT issue (not filed, not done) - waits-artem

Title: AC08 kernel: repair operation (flip back faces / close open borders) on the source baseline

Labels: waits-artem, level:hard

Context: [D197] (#968) judges the kernel invariants relative to the source. AC08's source keeps its pre-existing
violators as a recorded baseline: 3107 back-face pixels (direction (-0.58, -0.58, 0.58)) and 20 open border edges not
hidden (AC08_body 16, AC08_plate 4). D197 says a repair op is a separate later item and must not change the accepted
geometry now.

Question for Artem before any code: may a repair op change the accepted AC08 geometry (pilot-v010), and which one -
(a) flip the faces whose back side is seen, (b) close the open borders with caps, (c) both? Who accepts the result
(album slide 49, SINTEZ, delivered compare)?

Acceptance (proposal):
- [ ] a `repair` op in the kernel menu: flips / caps named elements, reports every element it touched;
- [ ] after it, the AC08 baseline drops (back faces < 3107 px, borders < 20) and no op adds new violators;
- [ ] UV and material ids preserved on flipped faces; caps get a named material, never a default;
- [ ] delivered compare, album and SINTEZ rerun with numbers before/after.

Related kernel finding from #968: `open_borders_hidden` treats a border as hidden only inside ANOTHER part, so
`join_parts` / `simplify_part` expose the knob's borders that stay inside the joined solid (+12 new on ops 14, 16, 17).
