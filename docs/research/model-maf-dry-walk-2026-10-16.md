# model-maf skill — dry walk-through on one urn

Card: pilot #182. A dry walk: each step was read against real inputs on this workstation. No MAF was produced, the library was not audited, and nothing binary was committed. This is not delivery validation and it claims no acceptance.

Inputs were copies in `C:/x/t_15fd4d0c/`. The originals were unchanged.

| Input | Original | SHA-256 before = after |
|---|---|---|
| SPOZU MAF drawing (Silikatniy UVK) | `Desktop/!3D viz/!Weltbau/Silikatniy_UVK/dwg_maf.dwg` (1 912 490 B) | `95c338d1…ee645` = `95c338d1…ee645` |
| MAF library scene | `Desktop/!Models & Textures/AGR_Model's/МАФы_Union_ALLin/МАФы_Union_ALLin.max` (319.5 MB) | `beeef9d4…50109` = `beeef9d4…50109` |
| Audited catalogue | `library/maf/catalogue.json` (#183, in git) | — |

Specification: catalogue `spec_matches` row 4 of `maf_spec_vedomost_3.xlsx` (the copy used by #183): «Урна «Стеллар Вуд» круглая с крышкой», type Урна, «есть ВПМ и НПМ версии», L 0.40 W 0.40 H 0.94 m. This specification belongs to another project than the Silikatniy drawing: the pairing is illustrative for the walk.

Commands run:

```text
python hermes_kanban/scripts/dcc_batch.py acad --dwg maf_copy.dwg --file dxfout.scr  -> status ok, exit 0, 2.3 s, AGR_DXFOUT_DONE, 11.7 MB DXF
uv run --offline --extra cad python probe.py   -> $INSUNITS 4 (mm), 11 layers, layouts Layout1/Layout2/Model; model space 161 INSERT, 128 MULTILEADER, 17 LWPOLYLINE, 0 TEXT/MTEXT; 28 distinct (block, layer)
   urna: block «урна» x 17 on layer Ю_маф, rotation 0 on all, z 0, scale 1; block = 1 CIRCLE + 1 HATCH, extents 0.4 x 0.4
   model-space extents 151.4 x 176.4 (metres by magnitude although $INSUNITS says mm); insert e.g. (57.553, 109.911)
   other MAF blocks carry rotation (e.g. «инфо столб косма» 67.1/298.5/323.3, «8003R нд» 118.8/298.8, block 2.0 x 0.6)
   lamps: block «1x18_2» x 35 on ЭН_Светильники with block scale 0.003
python hermes_kanban/scripts/dcc_batch.py max --scene maf_lib_copy.max --file lib.ms -> 76.1 s, AGR_LIB_DONE units=#meters scale=1.0; 996 objects (945 geometry, 22 Text); wrapper status ok, native exit 4294967166 = the known polyunwrapper_autoload.mse startup error; Cyrillic Text contents came out as '?' (the MAXScript file stream was not UTF-8) — names are read from the catalogue instead
```

Catalogue facts (`library/maf/catalogue.json`): spec row 4 has 12 dimension candidates. Best: MAF_0236 `Cube.001` (152 tris, 0.402 x 0.402 x 0.941, npm_matches ['Cube.001']), MAF_0694 `M_Urn_006` (154 tris, 0.402 x 0.402 x 0.941), MAF_0689 `M_Urn_001` (1596 tris, 0.395 x 0.395 x 0.936), MAF_0244 `Circle.028` (824 tris, 0.405 x 0.406 x 0.960, mat IDs 1,2, npm_matches Circle.020/Circle.028), MAF_0693 `M_Urn_005` (1818 tris, 0.405 x 0.406 x 0.960).

Previews (outside git, `C:/x/t_3e6ff1b3/library/preview/`): MAF_0236 and MAF_0694 are square box bins with an open slot under a top plate (no round body); MAF_0689 is a round slatted cylinder (vertical slats) with a slanted top and no visible lid; MAF_0244 and MAF_0693 are the same design: a round urn of vertical slats on a base ring with a raised round lid on posts (two material IDs: slats and frame). Their NPM counterpart in `МАФЫ_НПМ.blend` (#183 `blend_inventory.json`, outside git): `Circle.028`, collection `НПМ`, 824 tris, 0.405 x 0.406 x 0.960.

## Steps on the urn

| Step | Urn input | Route used / automatable today |
|---|---|---|
| 1 | Spec row 4 paired, illustratively, with Silikatniy block «урна» x 17, rotation 0, scale 1, extents 0.4 x 0.4; `$INSUNITS` 4 | `dcc_batch.py acad` DXFOUT (exit 0, 2.3 s) + `ezdxf`. Headless with existing tools. Units disagree with the coordinate magnitude: human. |
| 2 | 12 dimension candidates; previews of MAF_0236, MAF_0694, MAF_0689, MAF_0244, MAF_0693 | Catalogue lookup headless. Library scene read headless (`dcc_batch.py max`, 76.1 s, known startup exit). Visual choice of construction is human. |
| 3 | Not taken: the round urn with a lid is in the library (MAF_0693 / MAF_0244), not a missing or individually made MAF | Human when a row is missing. No model was built. |
| 4 | Catalogue `dims_m`: MAF_0693 / MAF_0244 0.405 x 0.406 x 0.960 against 0.40 x 0.40 x 0.94 (max deviation 0.02 m, H): pass; MAF_0689 0.395 x 0.395 x 0.936 (0.005 m): pass on numbers | Numbers from the catalogue, headless. Colour, wood slats and the lid are human. |
| 5 | MAF_0693 1818 tris (no `npm_matches`) vs MAF_0244 824 tris (`npm_matches` Circle.028 in the NPM collection), 17 inserts | No tool yet. The triangle sum is arithmetic on the catalogue, not a built light mesh. |
| 6 | Materials implied by «Вуд» (wood slats, metal, a grey body) were not packed in this walk | Packer `atlas_maf.py` exists. UV remap has no reviewed tool. Human for the look. |
| 7 | Slatted cylinder; segment count of the light version is not chosen | Route (Smooth / `shade_smooth_by_angle`) without a reviewed tool. Human for facets. |
| 8 | 17 inserts, rotation 0, z 0 on every urn insert; no Ground relief in this drawing | No tool yet. Sinking on a slope is the test probe, not this drawing. |
| 9 | No Ground FBX was exported | `validate-delivery` / `validate_package.py` exist. Not run. Not a delivery check. |

## What the walk found

- Best dimension candidates (MAF_0236, MAF_0694, deviation <= 2 mm) fail the construction check: square, the spec says round with a lid. That is Step 2's rule that a dimension candidate is not a match. MAF_0689 is round and within 5 mm but shows no lid. MAF_0693 and MAF_0244 match the construction (round, slats, lid) and are within 2 cm (Step 4 pass on numbers); whether this is «Стеллар Вуд» and its colours (wood slats per «Вуд») is the user's visual call (human): the catalogue is a technical audit, not identification.
- Light version: MAF_0693 1818 tris x 17 urns = 30 906 tris = 51.5 % of the 60 000 MAF planning share [D097] for urns alone. The library already holds the light version of the same urn: MAF_0244 / NPM `Circle.028`, 824 tris (45 % of 1818), 17 x 824 = 14 008 tris = 23.3 %. Step 5 therefore takes the existing `npm_matches` candidate instead of building one; it still goes back through Step 4 (same dims) and Step 7 (fewer slats/segments shade differently).
- SPOZU units: `$INSUNITS` says mm while coordinates and block sizes read as metres. Step 1 stays a human check.
- Urn inserts have rotation 0 (round urn). Other MAF blocks do carry rotations, so Step 8 applies the insert rotation.
- Lamps are on a lighting layer with block scale 0.003. That is MAF-24 / human, not placed as urns.
- Step 8 sinking on relief: the Silikatniy drawing has z 0 everywhere (no Ground relief in it). The slope case is covered by the test probe (bench 2 m on slope 0.15 exposes a bottom, 0.05 does not), not by this drawing.
- Of 9 steps: Step 1 is headless with existing tools; Step 2 is partly automatable (catalogue lookup headless, visual choice human); Step 3 is human; Step 4 is partly automatable; Step 5 has no tool yet; Step 6 is partly automatable (the packer exists, UV remap has no tool); Step 7 is a route without a reviewed tool; Step 8 has no tool yet; Step 9 is partly automatable.
