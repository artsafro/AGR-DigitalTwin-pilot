# #155 — View -> face by the keyplan arrow on untitled sheets (Sokolniki template), OBSERVE

## Кратко для Артёма

(заполняется после измерения)

## Frozen contract (committed before any reader score was computed)

Card t_436d52d6 (standing #155), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki is held out and was not
opened. Rounds #139-#154 measured content cues (edges, raster, finish partition D, keyplan red lines on a
registered vector situation plan); none was measured on the **untitled raster sheet template** that the
Sokolniki cold run (#2001 STOP 04) has to read. This round measures the cheapest cue that template carries.

**Fixture (never used by #139-#154).** Savelovskaya UVK1000 (Weltbau, same template as Sokolniki): 4 issued
albums (В3 «Береста», В4-1 «Цветные арки», В4-2 «Белые арки», «вариант 3»), each a 2-3 page raster-printed
Revit PDF with 4 untitled elevations and per view a keyplan icon (grey plan with a courtyard notch, a red
triangle arrow and a thin red line), plus each album's own Revit FBX (1.0-2.0 M tris). Paths and SHA-256 in
[`fixture.json`](autoresearch-view-face-arrow/fixture.json) (owner's PC, `!Weltbau/8_Савеловская/`). 16 arrows =
16 views; the 4 albums repeat one building, so the rows are 4 re-issues of 4 faces, not 16 independent faces.

- **GT** (independent of the keyplan): each view was matched by eye to Workbench orthographic renders of its
  own album FBX (az 0/90/180/270) by geometry and finish features only (curved corner elements, ornament /
  arch positions, low framed block, the big-window short face). All 16 agree with layout; az = outward normal,
  0 = +X, 90 = +Y.
- **Reader R (the candidate; frozen params in the fixture).** Page raster at zoom 3. Red triangle = pure-red
  component with area/fill/aspect bounds; arrow direction = base -> apex (the narrower end). Keyplan icon = the
  nearest uniform-grey component (R 190-225, chroma <= 6, >= 3000 px) whose centre lies ahead of the arrow.
  Red line = thin red component between arrow and icon, perpendicular to the arrow (optional; its midpoint is
  the ray origin, else the arrow apex). Model footprint = heightmap of the FBX triangles at 0.25 m, cells
  >= 3.0 m above the ground level (median height of the 2 m border ring). Registration = 8 dihedral transforms
  of the icon mask, aspect within x1.2 of the footprint, resized to the footprint grid, IoU. Each transform
  yields an az (arrow direction mapped through it; outward normal = minus viewing direction). Answer = az of
  the best transform if IoU >= 0.75 and IoU margin to the best transform with a **different az** >= 0.05,
  else abstain. Wall = march from the ray origin along the viewing direction to the first footprint cell;
  depth below the footprint bbox side; `outer` if depth <= 2.0 m.
- **States (per arrow, all from the same page raster).** `clean`; `rotated` (keyplan patch = icon + arrow +
  line rotated 90 deg onto a blank canvas — expected: same GT az, registration must recover the rotation);
  `mirrored` (patch flipped left-right — expected: same GT az through a reflection); `symmetric` (icon
  replaced by its filled bbox rectangle — expected: **abstain**, positive abstention witness);
  `no_icon` (icon erased — expected abstain); `inner` (only arrows on the notch side: arrow + line moved over the
  notch columns of the icon — expected: same az, wall inner at the notch depth measured on the footprint,
  +-2.0 m). Changed-pixel counts per state are recorded; a state with 0 changed pixels is `not_exercised`.
- **Control (other template).** Olimpijsky AR.2 p5-p8 (vector, situation plan with red line, no triangle
  arrows): R must answer nothing (abstain 4/4); this is a no-trigger control, not an accuracy result.
- **Primary metric.** correct / wrong / abstain of az on the 16 real views (`clean`). Secondary: wall outer /
  inner identity; per-state tallies.
- **Acceptance H155 (frozen).** clean wrong 0 and correct >= 14/16; rotated wrong 0, correct >= 14; mirrored
  wrong 0, correct >= 14; symmetric wrong 0 (abstain on every exercised row); no_icon abstain 16/16; inner: wrong
  az 0, wall-correct >= 75 % of exercised rows; clean wall `outer` on >= 14/16; control abstain 4/4.
  Witnesses: positive trigger = `B3 p1 upper long` clean must answer 270; abstention = every `symmetric` row.
- **Stability / replay.** `uv run --offline --locked --extra pdf-review python
  docs/research/autoresearch-view-face-arrow/run.py C:/x/ar155/<fresh>` (pilot host; Blender 4.4 for the FBX
  triangle dump). Three fresh runs, each re-exports the FBX triangles and re-reads every PDF; row JSON must be
  byte-identical; median / spread wall time reported. Invariance: reversed component order must change 0 rows.
- **Budget / stop.** One candidate (R), no retuning after the first score; a failed row is reported, not
  fixed. Stop `inconclusive` if elapsed + 1.15 x first-run s x remaining runs > 3600 s or on parity failure;
  timing stop and hypothesis verdict are reported separately.
- **Forbidden.** Changing params, GT, arrow keys or states after a score; opening Sokolniki outputs; editing
  source drawings, models, deliveries, production `src/` or other cards' files; weakening guards.
- **Pre-score amendment A1** (code review of the runner, before any real run): the ground level is the 5th
  percentile of occupied heightmap cells (`fp_ground_pct` 5), not the median of the 2 m border ring — on an FBX
  without a site slab the building itself touches the bbox ring, so the ring median would be the roof level.
- **Not measured (declared up front).** Real untitled **partial** views (Savelovskaya has none; `inner` is
  injected), arrow -> view association (GT per arrow, by layout), notch side walls (az 0/180 inner), rotated
  keyplans on a real sheet, other templates with arrows, Sokolniki transfer (held out).
