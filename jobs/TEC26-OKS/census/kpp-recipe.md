# KPP1 etalon recipe — measured inventory, not a delivery certificate

Authority: accepted KPP1 v005 case (`jobs/KPP1/REPORT.md`, `STATE.md`), source scripts and the hash-pinned copied Max scene/maps. Base main: `442f0b695a91f9abc180783c26978fbe85fefcf9`. The historical acceptance is approximately 90%, not an approved complete AGR package.

## VPM

- The native Max copy has VPM Main 24912 triangles / 12456 quads and Glass 76 triangles / 38 quads; NPM Main 24876 triangles / 12438 quads and Glass 76 triangles. 33 UCX-named meshes remain separate. These agree with the v005 report, not the older v002/v003 counts.
- 19 tiles, 1001–1019. Native preview is a Blend containing a Multi/Sub of `UDIM_1001` ... `UDIM_1019`, plus a MultiTile preview. `kpp-tiles.md` matches every native preview ID to tile and source finish. **This relationship is specific to this KPP preview, not a general MatID-to-UDIM rule.** Do not transfer its ID numbers to the new buildings.
- Full Diffuse tiles are 4096²; smooth placeholders are 256². Normal is 4096² on textured finishes and 256² on smooth/alpha-only finishes. The copied `maps_kpp` actually contains 19 Diffuse + 19 Normal + two NPM maps, **no ERM files**. The source recipe generates ERM, but its presence in the delivered folder is not established. Do not call that folder a complete VPM set.
- Full tile spans 4.096 m: nominal 1000 px/m; historical v005 measured density 995–1005 px/m is a report citation, not a new UV-density measurement. Source padding 0.04 m = 40 pixels at nominal density. Preserve world phase when shifting UVs by complete pattern periods. Read `vpm_uv.py` before a new unwrap; UV presence here is not unwrap approval.
- Blue cassette `Cassette_RAL5015`: module 0.6 × 0.55 m, phase `[0.27,0.5]`; world row anchor +2.70 per KPP report. Grey `Cassette_RAL7047` and top blue band: vertical joints only. Cassette joint width 8 mm, height recess 3 mm, joint RGB multiplier 0.35; source `make_textures.py:79–89`. **The cassette module was scale-read, not dimension-confirmed; do not assume this module fits AC.04–09 without their drawings.**
- Plinth RAL7004 uses 300 mm tiles and 4 mm joints (`make_textures.py:64–73`). Perforated RAL9016: 0.6 m module, 50 mm holes at 120 mm pitch, 8 mm joints; visual dark recess, not true alpha holes (`:90–101`).
- Railing, ladder and cage use Diffuse alpha; handrail/top RAL1021. Railing posts 0.9 m, 1.2 m high; ladder rung period 0.372 m; cage ties 0.46 m / hoops 0.833 m. These are KPP geometry-specific patterns, not generic assets for all buildings.
- RAL sRGB triples are approximate values in `vpm_textures.json`, not calibrated colour measurements. Retain the same site palette only where a building drawing establishes the RAL. Roughness/metallicity remain the KPP proposals. ERM channels = Emissive / Roughness / Metallic, DirectX Normal. ERM is not displayed by the historical Max UDIM preview.

## NPM

- `make_npm_atlas.py`: one RGB 2048² Diffuse `T_Kpp_1_001_Main_d_1.png` and separate RGB 2048² opacity `T_Kpp_1_001_Main_o_1.png`. Both copied headers confirmed. No image alpha; no normal; no metallic/roughness in this KPP recipe. Opacity is white=solid/black=void for railings/ladder/cage, not separate translucent glass.
- Grid 5 columns × 4 rows; 409 px cells; 6 px edge padding; 397 px useful square per finish. Inter-region padding 12 px exceeds 8 px NPM minimum. Same 4.096 m physical period gives 96.923828125 px/m for full finishes, not an NPM OKS density requirement.
- UV remap = region origin + VPM tile-local UV × useful region size. Rasterise joints at least 1.5 px (source increases joint half-width to 8 mm). Opacity downsamples BOX then thresholds 128; diffuse LANCZOS, void colour filled with mean solid colour, edge padding extended.
- `export_npm.py` removes VPM back copies on alpha strips, remaps to the atlas and embeds the maps; separate glass uses the glass material. `export_vpm.py` keeps external triplets. Review Max scenes are untriangulated previews, not automatically compliant final exports.

## Reuse boundary

Use the recipe and palette, not the existing KPP atlas/IDs as a building template. For each building: resolve its source material IDs against drawing evidence first, retain unknown as `?`, make explicit finish→tile/region mapping, preserve physical pattern scale between NPM/VPM, then perform new export readback and QA. Do not import KPP's unresolved coordinates, address token `Kpp_1`, missing ERM folder contents or historical manual-gate status as approved delivery data.
