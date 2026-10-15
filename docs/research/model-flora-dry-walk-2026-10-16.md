# model-flora skill — dry walk-through on one bush and one tree

Date: 2026-10-16. Card: pilot #188. Skill: [`.agents/skills/model-flora/SKILL.md`](../../.agents/skills/model-flora/SKILL.md).
A dry walk: each step is read against real inputs and the tools of this workstation; no Flora is produced (out of
scope), no library is audited (#189), nothing binary is committed. This is not delivery validation and claims no
acceptance.

## Inputs (copies in `C:/x/t_090bef2a/`, originals unchanged)

| Input | Original | SHA-256 before = after |
|---|---|---|
| Planting schedule, sheet 6 «Озеленение» (Silikatniy UVK, PDF, 1 page) | `Desktop/!3D viz/!Weltbau/Silikatniy_UVK/СИЛ13-УВК-АГР-ПД-ПЗУ_лист 6_Озеленение.pdf` | `103b8155…d18` = `103b8155…d18` |
| Greening DWG of the same project (SPOZU points) | `…/Silikatniy_UVK/dwg_green.dwg` (213 044 B) | `a981af8e…8f2` = `a981af8e…8f2` |
| Flora library scene | `Desktop/!Models & Textures/AGR_Model's/FLORA_Union_v1/FLORA_Union_v1.max` | `30d7fc32…416` = `30d7fc32…416` |

Chosen pair: **bush** = schedule pos. 5 «Гортензия древовидная» (*Hydrangea arborescens*), **tree** = pos. 3
«Клен остролистный» (*Acer platanoides*).

## Commands run

```text
uv run --offline --extra pdf-review python pdf.py              -> 1 page, 2384 x 1684 pt, 6826 chars of text layer
python hermes_kanban/scripts/dcc_batch.py acad --dwg green_copy.dwg --file dxfout.scr
                                                               -> status ok, exit 0, 1.4 s, AGR_DXFOUT_DONE, 1.64 MB DXF
uv run --offline --extra cad python probe.py                   -> $INSUNITS 4 (mm), 19 layers, model space:
                                                                  152 INSERT, 1 HATCH, 1 LWPOLYLINE; 0 TEXT/MTEXT;
                                                                  152 inserts, 0 with non-zero rotation
python hermes_kanban/scripts/dcc_batch.py max --scene flora_union_copy.max --file texts.ms
                                                               -> 320 Text objects, 185 geometry objects (TSV);
                                                                  wrapper status error, native exit 4294967166 =
                                                                  the known polyunwrapper_autoload.mse startup error
                                                                  (first attempt failed on my script: top-level `local`)
```

## Step by step

| Step | Bush: *Hydrangea arborescens* | Tree: *Acer platanoides* | Route used / automatable today |
|---|---|---|---|
| 1 Schedule + SPOZU points | pos. 5, 58 pcs, note «h свыше 0,9м», no crown | pos. 3, 6 pcs, «h свыше 5м», stem d 7 cm, root ball 1.5×1.5×0.65 | PyMuPDF text layer + core console DXFOUT + ezdxf: yes (headless). Block `Гортензия древовидная Annabelle_127_М5.1` × 58 = schedule count; block `Клен остролистный_22_М5` × 6 = schedule count; no rotation on any insert |
| 2 Flower beds | schedule pos. 10 «Цветник из многолетников (Ирис гибридный, хоста голубая, герань многолетняя)», 21.3 m² — plants listed -> models [D101], split into 3 species rows (iris, hosta, geranium) with the 21.3 m² area; no planting rate in the schedule -> `review`; pos. 11–12 lawns -> Ground texture, no Flora tile | — | wording read headless. The 3 bed species enter steps 3–8 like point plants: the library has no «ирис»/«хоста»/«герань» label (only «Гейхера» and other perennials) -> step 5 texture route; scattered in step 8, so they get atlas tiles in step 9 |
| 3 Library | Text label «Гортензия древовидная», `80 Tris`, `LP -> HP`, `v1`; mesh `Gortenziya_drevovidnaya_LP`; cultivar variants «баунти» (88 tris, two sizes) | label «Клен остролистный» v1 `1070 Tris` `LP -> HP` (mesh `Klen_ostrolistniy_LP`), v2 `10 Tris` `LP` (mesh `КЛЕН_LP`) | 3ds Max batch on a copy: yes for reading; pairing labels with meshes by position is manual here (labels at y 7.5 / 8.75, meshes at y 10). The DWG names cultivar «Annabelle», the library has «баунти»: human |
| 4 Check ±20 % | band for 0.9 m: 0.72–1.08 m. Heights (bbox Z): LP 0.553 (−39 %, fail), «баунти» 1.407 (+56 %, fail), «баунти_02» 1.124 (+25 %, fail); no crown in schedule -> `review` | band for 5 m: 4.0–6.0 m. v1 5.675 (+13.5 %, pass), v2 4.538 (−9.2 %, pass); crown 4.7–4.96 / 6.57–6.75 m, no target -> `review` | numbers headless from step 3. «h свыше» is a lower bound: whether the band centres on it is `review` for the user. Uniform scale LP bush ×1.63 to 0.9 m would make its crown 1.65 m — human |
| 5 Texture route | not needed if the library maps are usable; otherwise new species via `dt_ai.materials.flora` + review | same | route exists (#190 merged; 3 species approved: Betula pendula, Pinus sylvestris, Spiraea japonica — neither of ours); needs the user's review |
| 6 NPM star / VPM shell | library bushes: LP 9–80 tris (e.g. Spiraea japonica LP 20 tris, HP 160 tris PolyMesh, same height 0.553) — the LP is the star, the HP a denser shell. `LP -> HP` on our bush suggests one model serves both | — | no reviewed star builder; reading the library is headless. Mapping `LP`/`HP` -> NPM/VPM is #189's audit, not assumed |
| 7 Trees | — | v2 `10 Tris` (6.75 × 6.57 × 4.54 m) is a minimal stand-in, star or hull not inspected; v1 1070 tris is the detailed one; which serves NPM/VPM is #189's audit | library copy via 3ds Max batch; new trees would need SpeedTree only with the user's consent |
| 8 Placement + bed scatter | 58 points, mm units (scale 0.001 to m), Z rotation and scale random with seed | 6 points. Base +13.5 %: with scale ±10 % the top reaches 5.675 × 1.1 = 6.24 m (+24.9 %), outside the band, so the scale range narrows to 0.90–1.057 (1.2 / 1.135) | pos. 10 bed: iris/hosta/geranium scattered over its 21.3 m² area (which DWG entity bounds it is not checked here) at the rate the user gives (`review`); no reviewed placement or scatter script; Ground projection depends on `model-ground` |
| 9 Atlas | bush tile from its diffuse + opacity; tiles for the 3 bed species (already placed in step 8) | tree tile | no tool yet (#217 open); `tools/materials/atlas_maf.py` is a 512 MAF packer only |
| 10 Checks | — | — | `validate_package.py` subsets (V003, V004, V006, V013) headless; FLO-specific checks wait for #191; visual review human |

## What the walk found

- **Schedule vs DWG names differ for 3 of 6 positions while counts match:** pos. 1 «Пихта одноцветная» (1) vs block
  «Ель колючая» (1); pos. 2 «Сосна горная "Мопс"» (44) vs «Виноград амурский» (44, own layer); pos. 6 «Чубушник
  венечный» (28) vs «Ирга Канадская» (28). Step 1's `human` marker covers this; the agent must not pick one.
- **DWG units are millimetres** (`$INSUNITS 4`): placement converts to metres (FLO-17 transforms).
- **The library labels say `LP` / `HP` / `LP -> HP`, not NPM / VPM.** The skill reads them as labels only and leaves
  the mapping to #189.
- **The bush fails the ±20 % band in every library variant** against «h свыше 0,9м»; the tree passes. Lower-bound
  notes («свыше») make the band ambiguous: a `review` question for the user, recorded in step 3, not decided here.
- **±10 % clone scale can push a valid model out of the ±20 % band**; step 8 narrows the range (tree example above).
- **The modelled bed (pos. 10) has an area, not points.** Classified as the last step after the atlas (round 1 of PR
  #237), its species would have been scattered after the atlas was packed and had no tiles; the beds step now comes
  second, so its species go through the library, the texture review and the scatter before the one atlas.

Summary: of 10 steps, 4 run end-to-end headless today (1, 2 classification, 3 reading, 4 numbers), 2 have a merged
tool that needs the user's review (5) or covers only a subset (10), 4 have a route but no reviewed tool (6, 7 for new
species, 8 placement and bed scatter, 9). Every gap matches an open issue (#189, #191, #216, #217) or is marked
`no tool yet` in the skill.
