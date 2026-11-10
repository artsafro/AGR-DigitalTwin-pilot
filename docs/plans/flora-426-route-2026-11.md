# Block #426 Flora — route, 2026-11 (route A chosen, recorded [D232])

Artem 2026-11-09 «давай блоки продолжим». Route **A is chosen** (Artem 2026-11-09 «принимаю рекомендации»,
recorded [D232]): new NPM "star" objects [D102] from approved / new map pairs for the 17 Vatutino positions + Ива,
VPM = shell of the star, one 2048 site atlas, placement v007, all 4,915 plants (~30k tris). The implementation goes
to the follow-up issue the orchestrator opens, not here. The MAF gaps from the 2026-11-07 audit (no NPM-light, no UV
transfer to the atlas, site package not accepted) belong to block #425 and are only a dependency here (step 8).

## Where Flora stands (numbers from the repo)

| Fact | Number | Source |
|---|---|---|
| Library v003 species / shared stand-in gaps | 61 / 15 | `library/flora/catalogue.json`, `jobs/VATUTINO-SITE/site-parts.md` |
| Library objects with broken map↔UV binding (#377 diagnosis, merged, **not accepted by Artem**) | 99/99 → routes 24 restore atlas, 12 fix UV, 2 refine, 7 remap star, 54 rebuild NPM star | PR #377, D155 |
| Approved diffuse+opacity map pairs (batch 2, «Карты одобряю») | 54 species | #217/#216 comment |
| Vatutino schedule positions / with a library object / exact species | 17 / 11 / 3 (Sorbaria, Dasiphora, Pinus mugo); **8 of 11 are proxies** | `site-parts.md` F1, F2 |
| Plants placed (run v006) / not placed (no object: pos. 2, 5, 8, 10, 13, 16 + Ива) | 3,170 / 1,745 | `site-parts.md` |
| Flora NPM triangles, current picks / with the 3 NPM-light variants (#362: 103→96, 105→225, 204→36) / budget [D097] | 118,774 / 64,454 / 70,000 | `site-parts.md`, `library/flora/npm-light.json` |
| NPM "star" billboard builder [D102] | none (only `build_flora_npm_light.py` = triangle subset of the old mesh) | `tools/flora/` |
| Flora atlas tool (one 2048 per site) | exists, tested on synthetic data only | `tools/library/flora_atlas_from_scene.py` (#217) |
| Accepted Flora model | **none** (placement v006 = technical QA only) | `docs/pipeline.md` |

## Route (A chosen [D232]; steps marked † are skipped or changed in B/C)

| # | Step | Input | Tool | Done when (measurable) | Max? | Artem |
|---|---|---|---|---|---|---|
| 1 | Species sheet: 17 positions + Ива → exact species, map status, proxy flag | `site-parts.md`, `maps.json`, schedule | table in `jobs/VATUTINO-SITE/flora-species.md` | 18 rows; each row: exact Latin name, map pair `approved`/`missing`, chosen source | offline | answers open F1–F3 |
| 2 | Map pairs for missing exact species (2K front view on white → cut-out → B/W opacity) | step 1 `missing` rows | image generation + `dt_ai.materials.flora` | every row has diffuse+opacity, opacity is binary (0/255 ≥ 99 %), plant fills 80–95 % of the frame | offline | **yes**: contact sheet, «approved» per pair |
| 3 | NPM star builder (new, `tools/flora/build_flora_star.py`, Blender headless [D110]) | map pair, height, crown | Blender bpy | unit tests on synthetic maps; readback: tree 4 planes = 8 tris, bush 3 planes = 6 tris; height and crown within ±20 % [D099]; UV = whole image, 0 faces outside 0–1 | offline | no |
| 4 | VPM = shell of the star [D102], UDIM after Ground [D210] | step 3 star | same tool | readback: closed shell per plane, UDIM tile = first free after Ground, texel 520–1706 px/m [D097] | offline | no |
| 5 | One Flora atlas 2048 for the site; UV transfer from the per-species maps to the atlas cells | stars of the 17+1 species | `flora_atlas_from_scene.py` (#217) | exactly 1 atlas; per object UV inside its cell (0 texels outside); species scale factor equal; rendered object = per-map render (pixel diff ≤ 2 %) | offline | no |
| 6 | Place v007 on Ground master | stars, SPOZU points | `place_site.py` → engine | 4,915 plants (3,170 + 1,745) or the list Artem keeps; 0 engine stops; sink 10 cm [D100]; NPM tris ≤ 70,000 (estimate ≈ 30,000: ~105 trees × 8 + ~4,810 bushes × 6) | offline | no |
| 7 | Read-back QA of the exported FBX (`validate-delivery`) | v007 FBX | `dt_ai` checks, Blender readback | topology, UV, material count, transforms, budget all pass; `passed=false` until step 9 | offline | no |
| 8 | Site package with Ground + MAF (#298) and SINTEZ check | v007 + Ground + MAF (#425) | 3ds Max batch, AGR Checker | package builds; SINTEZ report attached | **needs Max** | — |
| 9 | Visual acceptance | renders: 6 views of the site + 1 sheet per species NPM/VPM | Blender render | Artem's words recorded on the PR | offline renders | **yes** |
| 10† | Library v004: publish the stars; old v003 meshes stay as they are (#377 routes stay parked) | steps 3–5 | `flora_catalogue build` | `catalogue check` passes; v004 entries carry `source: star` | offline | no |

Steps 1–7, 9, 10 run without Max. Only step 8 waits for a free Max.
Step-2 map sources (A101 for pos 9 and 16, named stand-ins for the unmatched rows) are fixed [D237].

## Variants (A chosen [D232]; detail in the PR body)

- **A (chosen)** — the route above: new star objects for the Vatutino 17 + Ива; the broken v003 library is not repaired now.
- **B** — repair the v003 library first per #377 (99 objects, 38 VPM restore/bake in Max), then Vatutino: steps 2–3 become the #377 routes; needs Max for ~38 objects.
- **C** — the fastest slice: keep the 11 current picks with the 3 NPM-light variants (64,454 tris), leave 1,745 plants unplaced; only steps 5–9.
- **D** — like A, but the 6 missing positions + Ива get named stand-ins from the approved 54 maps instead of new maps (no step-2 review round).

Preferences found in this block go to `jobs/VATUTINO-SITE/LESSONS.md`, not D-rows.
