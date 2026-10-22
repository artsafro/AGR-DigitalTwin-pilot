# TEC26-OKS / AC04 (Локальные очистные сооружения дождевых стоков) - VPM + NPM build-v003

Card #561 (build), branch `job/tec26-oks-ac04-build`. Recipe: AC08 pilot-v010 (PR #574, `ed743ab`), which Artem
accepted as the visual reference on 2026-10-22 («Да, похоже»). Run: `C:/x/tec26-oks/AC04/build-v003/`.
Drive: `G:/Мой диск/AGR-evidence/tec26-oks/AC04/build-v003/` (23 files + `SHA256SUMS.txt`, verified 23/23;
copy in `build-v003/DRIVE-SHA256SUMS.txt`). This is technical QA, not acceptance: `passed=true` is not claimed.

## Sources

| Input | Value |
|---|---|
| Max scene copy | `C:/x/tec26-oks/sources-v001/Vlad_OKS/04-09 Geometry Final.max`, SHA256 `eb0cffed…7852bd`, Max 2026.3, metres |
| Layer 004 dump | `max-dump-004.json` (`dump_max_poly.py`, headless `dcc_batch.py max`): mesh `АС.04` handle 174, 2462 v / 2552 polygons, IDs 1-5 (6-10 empty), 17 collision boxes `Colizii_047…063` |
| Authority | presentation slide 31 (`deck.pptx` `ppt/media/image57.png`, SHA256 `fa8e2380…0ce269`) + binding legend [D171]; frame band blue [D170]; Gate-1 approval of #561 (roof RAL 7004, drop = wall colour plain, glass as KPP) |

## What the build does

- Colour only. Geometry, UCX and multisub IDs as in the source; three ring cuts at joints of the long container fields
  (faces 7.84 m / 5.54 m do not fit a 4.096 m tile): 2552 -> 2617 polygons, +70 vertices on source edges, 5136 tris.
- Each container panel field is its own facade field (`facades.*.span`): the long facades carry two containers with
  a frame between them; the short walls are split into one-panel fields at the existing face edges.
- ID1: roof decks (up-facing, z >= 3.2 m, 91 faces) RAL 7004; the rest of ID1 (frame band, edging, drop below
  ±0.000 to -2.003 m) blue RAL 5015 plain. ID2 ribbed sandwich RAL 5015 (Artem's joint texture, 1000 px/m).
  ID3 two panes -> `SM_Los_1_MainGlass` (KPP glass). ID4 door/small frames RAL 7004. ID5 railings/ladder RAL 1021.

## Acceptance table (technical)

| Facade | Slide 31 joints (counted on the slide) | VPM render | NPM render | Contract | Compare |
|---|---|---|---|---|---|
| А-В (+x) | 5 + 9 | 5 + 9 | 5 + 9 | 5 + 9 | `compare_east_А-В.png` match |
| В-А (-x) | 9 + 5 | 9 + 5 | 9 + 5 | 9 + 5 | `compare_west_В-А.png` match |
| 1-2 (-y, door) | 2 (door edges) | 2 | 2 | 2 | `compare_south_1-2.png` match |
| 2-1 (+y, ladder) | 1 (+2 ladder stringers in front) | 1 | 1 | 1 | `compare_north_2-1.png` match |

Mesh path (`qa_packages.facade_joints_*`, UV -> delivered tile/atlas): every field ok on both rows, position error
<= 0.6 mm VPM / 0.9 mm NPM, no horizontal joints. `qa_packages.py`: **90/90** (glass object, twisted-quad ownership
and inherited near-vertex pairs included). Perimeter drop 4/4 walls. Texel 1000 px/m on all 62 patterned tris.

Joint contrast on the compare images (darkest / median panel luminance, long facades): slide 0.20-0.28, VPM/NPM
0.44-0.45 - the same as the accepted AC08 v010 reference (0.36-0.50, slide 0.17-0.18). The joints are Artem's 8 mm
texture joints; making them as dark as the 1-px slide lines at 200 px/m would need a joint colour/width the texture
does not have.

## Findings (reported, not fixed - colour-only scope)

1. 26 tiny ID4 quads are twisted 0.2-0.7 mm in the source; QA owns their triangles by their own corners.
2. 6 near vertex pairs 0.8-1.9 mm (inv_xview) exist in the source; QA passes them only because the source has the
   same pairs (`inherited_from_source`).
3. UCX boxes are quads (as in AC08; SINTEZ 2.3.17 wants them triangulated) - same open question as AC08.
4. Address `Los_1` and NPM prefix `0000` are placeholders, as in AC08.

## Open questions for Artem (only if the picture is not accepted)

1. Large container: the slide draws 3 narrow panels at the container junction and a narrow one at the far end;
   the build spreads the same 9 joints evenly (AC08 layout). Count equal, positions differ by up to ~0.2 m.
2. 2-1: the slide shows one joint 0.54 m from the -x corner; the build puts it on the existing face edge 0.66 m
   from the corner (no geometry cut). 1-2 matches the slide positions (door edges).
3. Roof RAL 7004 per Gate-1 (not visible on the slide).

## How to repeat

```
TEC26_LAYER=004 TEC26_OUT=<new>.json python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max \
    --file jobs/TEC26-OKS/scripts/dump_max_poly.py --scene "<Max copy>"
bash jobs/TEC26-OKS/scripts/run_building.sh jobs/TEC26-OKS/AC04 C:/x/tec26-oks/AC04/build-vNNN
blender ... render_facades.py -- jobs/TEC26-OKS/AC04/vpm_textures.json <vpm.fbx> <textures-vpm> <npm.fbx> <out>/renders
uv run python jobs/TEC26-OKS/scripts/compare_facades.py jobs/TEC26-OKS/AC04/vpm_textures.json \
    jobs/TEC26-OKS/AC04/sheet-facades.json <out>/renders <out>/readback/vpm.readback.json <out>/compare \
    --dump jobs/TEC26-OKS/AC04/max-dump-004.json            # exit 1 on any mismatch
```
