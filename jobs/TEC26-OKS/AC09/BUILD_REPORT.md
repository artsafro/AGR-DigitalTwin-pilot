# AC09 / SAKV — VPM + NPM build-v001

Main at start: `442f0b695a91f9abc180783c26978fbe85fefcf9`.
Inputs: accepted AC08-v010 recipe `ed743ab`, approved AC09 Gate 1 `5b66b49`.
Production authority: presentation slide53, latest orchestrator instructions on card #566.
Historical Gate-1 assignments in MATERIALS.md remain provenance, not the current facade override.

## Deliverables

`G:/Мой диск/AGR-evidence/tec26-oks/AC09/build-v001/`

- `SM_Sakv_1.zip`: VPM FBX + nine Diffuse/ERM/Normal UDIM sets. Four ribbed finishes have 4096px Diffuse/Normal at 1000px/m; constant placeholders follow the AC08-v010 recipe.
- `0000_Sakv_1.zip`: NPM FBX with embedded 2048 diffuse + separate opacity atlas, generated from the same VPM finish recipe; separate map-free KPP glass.
- Four `compare_*.png`: slide53 | exported VPM | exported NPM, same 200px/m scale, actual measured counts printed below each image.
- Local working files: `C:/x/tec26-oks/AC09/build-v001/`.

The two ZIPs and four compares were copied to Drive and all six destination files read back identically. No binary files or LFS in Git.

## Binding legend and overrides

| Hatch / region | Material | RAL | Texture | Source IDs |
|---|---|---|---|---|
| Blue vertical field | Sandwich panel | 5015, KPP RGB 34/113/179 | Accepted AC08-v010 vertical-joint profile, own facade pitch | 2 |
| Blue surround | Wall edging / roof surround | 5015 | Plain | 1 above zero |
| Grey door / plinth | Door and plinth | 7004, KPP RGB 150/153/146 | Plain | 4; 1 at/below zero |
| White window outlines and reveals | Frame | 9016, KPP RGB 246/246/246 | Plain | 3,5 |
| Interior, not a facade hatch | KPP Interior | No invented RAL | Plain KPP RGB 25/25/28 | 7 |
| Glazing | KPP glass | No RAL | Map-free, alpha0.5 | 6, separate object |

Latest slide/legend overrides historical Gate-1 grey edging and blue plinth.
No 7047 field occurs on slide53. Empty slots8–10 stay empty.

## Facade counts measured from the slide and exported renders

| Facade | Source normal | Slide joints / ribs | VPM joints | NPM joints |
|---|---|---|---|---|
| А-Б | -Y | 11 / 12 | 11 | 11 |
| Б-А | +Y | 10 / 11 | 10 | 10 |
| 1-2 | -X | 13 / 14 | 13 | 13 |
| 2-1 | +X | 13 / 14 | 13 | 13 |

Closest slide reading retained: А-Б has an extra stroke close to its right outline, unlike Б-А; counts are independent, not copied from AC08. The clear strip above windows is used (slide row97/508; render at99% of the panel field). Initial95% sampling crossed the source window frame (+2.3845m), falsely counting7/10 instead of11/13; the failed `compare/` remains local, final output is `compare-v002/`. Lower rows retain the visible occlusion diagnostics; they are not asserted to have unobstructed full-grid counts.

## Source geometry and limitations

Max2026.3, metres×1, staged copy only, layer009: Main handle173, glass369, collision342. Startup PolyUnwrapper warning occurred but the complete dump and expected nodes were read back. A separate live Max2024 was reachable but not touched.

- Main: 347 source polygons, 682 delivered triangles in both packages.
- Glass: 4 source polygons, 8 delivered triangles in both packages.
- UCX: 6 source quads, 12 delivered triangles (export-copy triangulation only), absent from NPM.
- Five source/readback comparisons: no missing source vertices, no added/moved coordinates within the inherited geometry-report tolerance. No ring cuts needed. Source material IDs preserved in the master; delivery is the one-material UV recipe.
- UV overflow0; panel density1000px/m; perimeter drop reaches below−1m on all four sides.
- Existing source findings retained: 12 nonquads, 54 uncovered Main edges, normal probes2 flipped/14 occluded. This is recolouring, not topology repair or whole-site compliance certification.
- Source top+2.56748m versus slide+2.450m: the source elevation discrepancy is shown, not silently fixed; geometry is unchanged. Rendered glass uses KPP pale tint rather than painting the slide's illustrative reflection.
- Address `Sakv_1`, district `0000`, georeferencing, GeoJSON, signatures, Ground and final delivery acceptance remain outside this per-building colouring preview. `passed=true` is not claimed.

## Repeat

```bash
bash jobs/TEC26-OKS/AC09/run_building.sh jobs/TEC26-OKS/AC09 C:/x/tec26-oks/AC09/build-vNNN
# Blender: recipe_adapter.py -- render_facades.py <spec> <VPM readback FBX> <VPM textures> <NPM readback FBX> <new renders>
uv run python jobs/TEC26-OKS/AC09/recipe_adapter.py compare_facades.py jobs/TEC26-OKS/AC09/vpm_textures.json jobs/TEC26-OKS/AC09/sheet-facades.json <renders> <vpm.readback.json> <new compare>
```

The adapter is AC09-only: exact KPP Interior exception, separate map-free glass, UCX export triangulation, Main-only UDIM preview binding, and sampling above the source window frame. Shared scripts are untouched. `sheet-facades.json` is slide-based comparison framing, not an AC09 DWG extraction receipt.
