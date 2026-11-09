# VATUTINO-SITE — job lessons

Job-local preferences and lessons (not D-rows).

- Flora star planes: crop the plane to the plant's opaque bbox + small margin, not the whole map; a
  whole-image plane makes the readback bbox (FLO-04 height/crown) larger than the plant. (#1146)
- One 2048 map per species cannot meet VPM texel 520–1706 px/m for every plant size: trees above
  ~3.9 m fall below 520, bushes below ~1.2 m exceed 1706. Measure VPM texel in the final atlas/UDIM, and
  ask before upscaling (LANCZOS adds no detail). (#1146)
- The species sheet is generated (`flora_species.py --check`): totals are asserted (4,915 plants), so a
  wrong row count fails instead of silently changing the placement. (#1146)
- Image generation is an external handoff (`dt_ai.materials.flora plan`); a worker without the tool stops
  at the step-2 gate with the plan file and the review sheet, it never fills gaps with proxies on its own. (#1146)
