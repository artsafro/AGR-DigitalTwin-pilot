# silikatniy-uvk-pzu — visualization ground from the PZU DWG

Branch `job/silikatniy-uvk-pzu-viz`. Started 2026-11-04.

## Requirement

User (2026-11-04), verbatim excerpt: «взять этот ДВГ, и подготовить его для визуализации ... определить штриховки,
определить поверхности, какую поверхность, какой материал, соответственно, подготовить мультисаб ... все арочные и
закругленные формы были не такие угловатые, как в ДВГ, а более аккуратные ... разметка, она находится на слое
255_краска ... сделал сплайнами в Максе, потом бы задал бы этим сплайнам толщину ... они должны быть плавные ...
на одном изгибе 8 сегментов, а на другом 6 ... выправлять, спаивать, чтобы все было как бы сшито, раскинуто на ID ...
отдельные сплайны ... enable in viewport, enable in render, и с какой-то толщиной впаиваться в наши поверхности».

## Source

`C:/Users/artsafro/Desktop/!3D viz/!Weltbau/Silikatniy_UVK/pravki/for_ai/СИЛ13-УВК-ПД-ПЗУ_.dwg` (read only;
work on a copy, DXF via AutoCAD 2025 core console). INSUNITS 6 (metres). Boundary layer `1.1_Граница_ГПЗУ`.

## Decisions (user «да, по рекомендациям», 2026-11-04)

1. Scope: the whole site inside the GPZU boundary, building excluded; pilot = one playground first.
2. 3ds Max 2026, one scene; one welded mesh with a Multi/Sub, one ID per covering and per rubber colour;
   placeholder materials coloured from the DWG, named from the legend.
3. Flat, Z = 0. Curbs: separate objects, garden 0.05 m, road 0.15 m.
4. Arcs re-tessellated with one rule (<= 5 deg per segment) so shared edges carry identical vertices.
   Paint: splines, rectangular render section 50 mm x 3 mm, bottom 1 mm below the surface; circles are rings.
5. Outputs: new versioned files next to the source (`for_ai/SIL13_PZU_viz_v001.max`), never overwrite.

## Not to touch

The source DWG and the user's open AutoCAD document.

## Status

- Intake done (layer, hatch and paint inventory).
- Pilot built 2026-11-04: top playground inside garden curb `33FBCE0`, `for_ai/SIL13_PZU_viz_pilot_v001.max`
  (3ds Max 2026 batch, saved as 2024; the user's open Max 2024 scene was not touched). Readback: PZU_Ground
  Editable Poly 1576 faces / 795 verts, open edges 12 (outer contour only), mesh area 597.671 m2 = contour area,
  IDs 1/2/5/8; PZU_Paint 48 splines, render mesh z -1..+2 mm; PZU_Curb_Garden +-5 cm. Waiting for the user's look.
- Pilot findings: the pilot's DWG arcs are exact tangent arcs (angularity comes from import tessellation);
  equipment pad `ФВ-2` (24.7 m2) has no covering hatch -> neighbour Rubber_Black.
- Pilot v002 (user check of the circles, 2026-11-04): circles are islands of the track rubber (holes in the base
  rubber, filled islands of the track hatch) -> Rubber_Grey, no separate ID; paint rings: big circles r 0.5/0.75/1.0,
  small r 0.5; a paint circle belongs to the area of its centre. `for_ai/SIL13_PZU_viz_pilot_v002.max`, readback:
  IDs 1/2/7, open edges 12 (outer contour), 10 paint circles.
- Pilot v003: white joint paint where two different rubbers meet (user 2026-11-04); stretches already carried
  by a DWG line along the joint (>= 0.20 m) are skipped, crossings are not. Paint gets `Paint_White`.
- Site v001 2026-11-04: clip = closed polyline `участки зоны` 33FBCEF (12958.744 m2; the GPZU boundary layer holds
  only legend samples). `for_ai/SIL13_PZU_viz_v001.max`, readback: PZU_Ground 30335 faces / 15181 verts, mesh area
  = clip area, open edges 27 (3 inside the clip, polygonize cut 1 / dangles 2: not located yet), IDs 1-8, 10-12;
  ID 12 `Undefined` = building footprint 3298 m2; PZU_Paint 328 splines (15 joint lines), render z -2.2..+3.2 mm
  at sharp corners; curbs garden 52 / small 4 / road 1. Paint source is tangent-continuous everywhere except
  8 court corners and 2 cusps; covering boundaries clean except the `ГП_Цветник` flower symbol (120 rings of
  0.01 m2, treated as a drawing symbol, not a covering).
- Site v002 2026-11-04 (user: Corona; «разбить по оттенкам как в двг»): coverings split by the hatch background
  colour (the shade AutoCAD shows), else the hatch colour; `ФВ-2` equipment pads get their own ID. One Multi/Sub
  `PZU_Multi`, 16 CoronaPhysicalMtl (base colour = DWG shade) shared by ground, paint (ID 15) and curbs (ID 16);
  renderer Corona. Built with 3ds Max 2024 batch: `for_ai/SIL13_PZU_viz_v002.max`. Readback: 12829 faces,
  IDs 1-14 on the ground, open edges 27 (3 inside), Corona check render matches the DWG shades.
- Open for the user: building footprint ID, the flower symbol, one tile material for both legend tile types,
  joint paint only between rubbers.
- Scripts: `scripts/build_ground.py` (DXF -> ground.json), `scripts/write_ms.py` (-> MAXScript), `scripts/readback.ms`.
