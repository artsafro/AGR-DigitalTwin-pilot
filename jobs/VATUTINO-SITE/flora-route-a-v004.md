# Vatutino Flora route A — run v004 status (#1146, [D232], [D245], [D246])

Rework after Artem's visual gate of run v003 (`flora-route-a-v003.md`). Status: **waiting for Artem's visual gate**;
`passed=false`. Same inputs, same placement seed, script `jobs/VATUTINO-SITE/flora_route_a.py all --run <dir>`.
Evidence (outside git, rule 57): `G:/Мой диск/AGR-evidence/1146-flora-star/run-v004/` + `SHA256SUMS.txt`
(256 files, list sha256 `21a13860…1d75ae2`). Local copy `C:/x/ev_t_c9ff2af1/run-v004/` (+ `run-v004.log`).

## Pale crossing plane (gate defect)

Cause, measured on the species renders (band = luminance of the near edge-on plane / rest of the plant):

| Variant | pos09 | pos10 | pos16 | pos06 |
|---|---|---|---|---|
| v003 | 1.157 | 1.095 | 1.150 | 1.049 |
| v004 (colour bleed + no grazing specular) | 1.053 | 1.065 | 1.098 | 1.052 |
| v004 + sun shadows off (experiment only) | 1.011 | 1.043 | 1.077 | 1.047 |
| v004 + sun off (experiment only) | — | 0.979 | — | — |

1. **Fixed (texture, affects the delivery):** the source maps carry white RGB (252) under opacity 0. The atlas downscale
   (LANCZOS), filtering and mipmaps mixed it into the leaves; a plane seen at a grazing angle or from afar went pale.
   `bleed_rgb` now fills every transparent pixel with the nearby plant colour before the atlas (plant pixels unchanged).
2. **Fixed (review render):** Principled specular at grazing angles washed the near edge-on plane out; the review
   material has `Specular IOR Level` 0.
3. **Not changed, inherent to the star [D102]:** sun self-shadowing between the crossing planes and the compressed
   texture of the near edge-on plane (the sheet camera is at 20° yaw, so one bush plane sits at 80°). It is 1–8 % in
   luminance. Custom up-normals were tried and made it worse (back faces flip the normal down).

Site views, plant pixels that changed (oblique SW / NE / eye level): HSV saturation 28.7 → 43.8 / 28.7 → 43.6 /
77.0 → 107.8, value 143 → 136 / 140 → 132 / 109 → 103, so the plants are greener and less whitish. Comparison sheets:
`compare/cmp-site-SW-v003-left-v004-right.png`, `compare/cmp-species-v003-v004.png`. The remaining light hedges are
mostly map content: 13 Hippophae (1,059 plants, grey Salix stand-in map), 11 Sorbaria (866, white panicles), and
15 Stephanandra (1,002).

## VPM own 4096 atlas [D246]

NPM: one 2048 atlas `M_VATUTINO_Flora_1`, scale 0.2160, fill 77.4 % (unchanged). VPM: its own 4096 atlas (same names
inside the VPM package, `atlas-vpm/`), scale 0.4369, fill 79.2 %, opacity mismatch at cell resolution 0.0 %.
The VPM star FBX embed the 4096 maps.

VPM texel (px/m; range 520–1706 [D097]): pos01 165 · 02 168 · 03 208 · 04 206 · 05 250 · 06 368 · 07 368 · 08 369 ·
09 285 · 10 528 · 11 529 · 12 528 · 13 541 · 14 952 · 15 **2,098** · 16 401 · 17 1,016 · Ива 1,099.
7/18 are in range. **Below (accepted [D246]):** pos01–09, 16. **Above (open, not covered by [D246]):** pos15
Stephanandra (20–60 cm, the smallest plant: one uniform atlas scale doubles its 1,038 to 2,098).

## Run v004 checks

| Step | Result | Status |
|---|---|---|
| Maps | 18 pairs, bled, sha256 in `maps/maps.json` | done |
| Atlas | NPM 2048 + VPM 4096, worst opacity mismatch at cell resolution 0.0 % | done |
| Stars | 18/18 geometry_passed, FBX readback tris = built, 1 material | done |
| Placement v007 | 4,915/4,915 placed, 0 failed, 0 mismatches, sink 0.0999–0.1000 m, scene QA pass (NPM and VPM) | done |
| FBX readback | NPM 29,700 tris (≤ 70,000 [D097]), VPM 178,200; 4,915 objects, 18 meshes, 1 material, 0 UV outside 1001 / 1002 | done |
| Site package + SINTEZ | not run | waits-max |
| Visual gate | `sheet/sheet-species-v007.png`, `sheet/sheet-site-v007.png`, `sheet/texel-vpm.md` | **waiting for Artem** |

Ива height 60–100 cm accepted as assumed [D246].
