# VATUTINO-SITE — job lessons and Artem's preferences

Job-local preferences and lessons (not D-rows).

- 2026-11-09, Artem, on overview-v003 + contact sheet: the colour zones of the 13 Vatutino MAF positions are
  accepted as the library baseline («более-менее норм»). In a real project the library MAF colours are compared
  with that project's specification; where they differ, the library entry is updated toward the spec. No
  per-project colour forks. Route step: `docs/plans/425-maf-route-2026-11.md` step 2.

- Flora star planes: crop the plane to the plant's opaque bbox + small margin, not the whole map; a
  whole-image plane makes the readback bbox (FLO-04 height/crown) larger than the plant. (#1146)
- One 2048 map per species cannot meet VPM texel 520–1706 px/m for every plant size: trees above
  ~3.9 m fall below 520, bushes below ~1.2 m exceed 1706. Measure VPM texel in the final atlas/UDIM, and
  ask before upscaling (LANCZOS adds no detail). (#1146)
- The species sheet is generated (`flora_species.py --check`): totals are asserted (4,915 plants), so a
  wrong row count fails instead of silently changing the placement. (#1146)
- Image generation is an external handoff (`dt_ai.materials.flora plan`); a worker without the tool stops
  at the step-2 gate with the plan file and the review sheet, it never fills gaps with proxies on its own. (#1146)
- A second map source exists besides the generated 54 approved pairs: the A101 Flora library on the Drive
  (`G:/Мой диск/AGR-assets/flora/a101/`), 180 cut-out RGBA 2048² PNGs named `<species>_t<N>_h<cm>_{high,low}.png`
  in transliterated Russian (e.g. `el_nidiformis` = Picea abies 'Nidiformis', `puzyreplodnik_kalinolistnyj` =
  Physocarpus opulifolius). Match by Latin genus/species, exact species only; a generic genus file (яблоня/дёрен/
  боярышник) is not an exact match. Copy read-only + sha256, never edit the Drive originals. (#1146)
- A species match is not enough: measure the map's colour before labelling it. `puzyreplodnik_kalinolistnyj`
  `t1/t2/t3` are three colour forms of the exact species (t1 yellow 139/123/6, t2 dark red 97/67/65, t3 yellow-green
  170/180/68), not "the plain green form" — t2 is the red-leaved form for 'Lady in Red'. Record the mean RGB of opaque
  pixels (alpha ≥ 128) per variant, bound to the copied file's sha256, and assert the label against the measurement. (#1146)
- Ground v015 VPM is a single UDIM tile 1001 (D209 numbers each mesh from 1001; `ground-build-v006.md` readback
  `tiles [1001]`), so Flora/MAF VPM start at 1002 [D210]. Small bushes cannot hit VPM texel 520–1706 px/m on their
  own 2K map; measure texel in the final atlas, no upscaling (Artem «мерить»). (#1146)
