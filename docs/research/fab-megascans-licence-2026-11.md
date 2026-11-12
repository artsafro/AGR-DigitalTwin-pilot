# Fab / Quixel Megascans licence for client delivery (2026-11)

Question (plan `docs/plans/telegram-findings-rollout.md`, step 2.5): may Quixel Megascans assets obtained
through Fab fill the missing material sets for Moscow NPM/VPM deliveries (FBX + PNG maps handed to the client)
and for Unreal experiences? Which CC0 assets cover the same sets?

Method: primary pages only, read 2026-11-10 without sign-in, downloads or accounts. Fab EULA full text was read
from the rendered page (the static HTML carries only the summary). This is a reading of the licence text by an
agent, not legal advice; the user decides, and a lawyer or Epic (fab support / `legal@epicgames.com`) can confirm.

## Short answer

- Megascans on Fab are now free and listed under the **Fab Standard License** (listing "Gravel": `License terms:
  Standard License`, `Allows usage with AI: Yes`, last update 2026-11-06).
- The Standard License allows commercial use in any tool (3ds Max included), renders, and Unreal builds that ship
  the content **in object code with extraction restricted**.
- It does **not** allow handing the content to a client as editable files (FBX + PNG maps, baked atlas or not):
  that is either standalone distribution (§5a, §6a.ii) or a Project whose end users can extract the content and
  incorporate it into their own platform (§4c, §6a.iii). NPM/VPM packages are exactly such files.
- Verdict for step 2.5: **do not use Megascans for maps that end up in NPM/VPM FBX packages.** Use CC0 sources
  (ambientCG, Poly Haven). Megascans stay allowed for renders and for content that lives only inside a cooked
  Unreal build.

## Verdict table

Sources (all read 2026-11-10):
[EULA] https://www.fab.com/eula (full Fab EULA, "Last updated: October 1st, 2024", plus a non-binding summary);
[LIST] https://www.fab.com/listings/2e847f8a-5acd-4abe-af90-fb58e8145e76 (Megascans "Gravel");
[QX] https://quixel.com/news/update-megascans-are-going-free-again (2026-11-05);
[UE] https://www.unrealengine.com/eula/unreal; [ECL] https://www.unrealengine.com/eula/content (Epic Content
License, Megascans Content Addendum); [DOC] https://dev.epicgames.com/documentation/fab/licenses-and-pricing-in-fab;
[ACG] https://docs.ambientcg.com/license/; [PH] https://polyhaven.com/license.

| Use case | Allowed? | Quote (≤ 15 words) | Source |
|---|---|---|---|
| Which licence covers Megascans on Fab now | Fab Standard License | "License terms: Standard License" / "Allows usage with AI: Yes" | [LIST] |
| Megascans price after the migration | free (all listings free by 2026-11-12; buyers since 2025-01-01 refunded to Epic balance) | listing price "Free"; refunds to the Epic account balance (paraphrase) | [LIST], [QX] |
| Commercial use | yes | "Use the assets commercially or privately" (summary, not binding) | [EULA] summary |
| Use outside Unreal (3ds Max, Blender, baking) | yes | "Use the assets with any compatible tools (usage is not limited to Unreal Engine)" | [EULA] summary; binding §3a grant has no engine limit |
| UE EULA governs Fab content | no, Fab EULA does | Fab assets "are not Licensed Technology and are not licensed to you" under it | [UE] §1 |
| Renders, images, video for the client | yes | "you may freely Distribute a Project that is a rendered linear media product" | [EULA] §4b |
| Unreal experience delivered as a packaged (cooked) build | yes, with extraction restricted | "solely as incorporated in the Project in object code" | [EULA] §4c |
| Unreal **project** (editable uasset/source) to the client | no | "must restrict end users from extracting or otherwise using Content outside" | [EULA] §4c, §6a.iii |
| Raw texture files (PNG/EXR maps) to the client | no | "may not Distribute Content on a standalone basis to third parties" | [EULA] §5a |
| Maps baked into our atlas, delivered in an FBX + PNG package | no (high risk): the atlas is modified Content, the PNG is extractable, and the client loads it into its own platform | "allow any third party to incorporate Content into their own products" (prohibited) | [EULA] §4a, §4c, §6a.iii |
| Sharing source files with collaborators (subcontractors, AGR reviewers working on our project) | yes, privately; they may not redistribute and must delete after | "share Content with your employees, affiliates, and contractors" | [EULA] §5a |
| Attribution | not required | "You are not required to give credit to the publisher" | [EULA] summary |
| AI training on Megascans | yes since 2026-11-05 (EULA §16l bars only `NoAI`-tagged content) | "you can now train AI models on Megascans and Megaplants" | [QX], [LIST], [EULA] §16l |
| Personal vs Professional tier | same rights; Professional above USD 100k revenue (free listings make this moot) | "Both pricing tiers (Personal and Professional) grant you the same scope" | [EULA] summary, [DOC] |
| Legacy Megascans (Bridge / quixel.com, pre-Fab) | depends on the plan at acquisition: UE plan = Unreal only; no plan = evaluation only | "may only be used for your internal evaluation purposes" (free, no plan) | [ECL] Megascans Content Addendum §1c, §1e |
| Licence of content acquired earlier | the terms in force at acquisition stay | "will remain governed by the license terms applicable at the time" | [EULA] §7a |
| ambientCG: commercial use, raw files to the client, no credit | yes (CC0 1.0) | "All ambientCG assets are provided under the Creative Commons CC0 1.0" | [ACG] |
| Poly Haven: commercial use, raw files to the client, no credit | yes (CC0) | "You can use our assets for any purpose" | [PH] |
| Poly Haven bulk download by script | ask first / use their public API per ToS | ToS bars "Web scraping or data mining without express permission" | [PH] (ToS link) |

## Unconfirmed

- Whether Epic published a revised full EULA text for the 2026-11 AI change: the page still says
  "Last updated: October 1st, 2024"; the AI right is stated in [QX] and on each listing, not in a new EULA version.
- Whether Epic would treat an NPM/VPM package as a permitted "Project" if the PNG maps were the only Megascans
  derivative. The text points to "no" (extractable, incorporated into the city platform); only Epic or a lawyer can
  say otherwise. Not asked.
- Quixel studio licences ("continue under the terms of your contract", [QX]): not applicable unless AGR has one.
- Module size, px/m and colour of the CC0 candidates below: not checked against [D207] and the regulation; that is
  step 2.2/2.5 work after the user picks.

## CC0 coverage of the missing sets

Missing sets come from `docs/research/telegram-3dsmax-chat-2026-11.md` (gravel, pebbles, mulch, rubber crumb, roll
lawn, roofs Logicroof / Solo / profiled sheet, facade masks cassette 600 / tile 600×1200 / panel V1200, pine) and the
SPOZU paving «Готика» 100×300 (`docs/research/spozu-vatutino-inventory.md`). Found through the ambientCG API v2 and
the Poly Haven API (names and tags only, nothing downloaded), 2026-11-10. Pages: `https://ambientcg.com/view?id=<Id>`,
`https://polyhaven.com/a/<slug>` (all listed URLs returned HTTP 200).

| Set | ambientCG (CC0) | Poly Haven (CC0) | Recommended |
|---|---|---|---|
| Gravel | Gravel020–043 (66 hits), e.g. https://ambientcg.com/view?id=Gravel022 | https://polyhaven.com/a/gravel, https://polyhaven.com/a/gravel_floor | Poly Haven `gravel_floor` (2.25 m scan) or ambientCG `Gravel022` |
| Pebbles | Gravel0xx / Rocks0xx tagged pebbles, e.g. https://ambientcg.com/view?id=Rocks022 | https://polyhaven.com/a/pebbles, https://polyhaven.com/a/clean_pebbles | Poly Haven `clean_pebbles` |
| Mulch | https://ambientcg.com/view?id=WoodChips001 (–003) | https://polyhaven.com/a/wood_chip_path (tagged mulch), https://polyhaven.com/a/wood_chips | Poly Haven `wood_chip_path` |
| Rubber crumb (EPDM) | Rubber001–004 are gym-floor rubber: https://ambientcg.com/view?id=Rubber001 | https://polyhaven.com/a/rubberized_track, https://polyhaven.com/a/running_track | Poly Haven `rubberized_track`, recolour per SPOZU; crumb look unconfirmed |
| Roll lawn | https://ambientcg.com/view?id=Grass005 (tags clean, lawn, short), Grass004/008 | only dry / sparse / leafy grass (`grass_ground`, `sparse_grass`) | ambientCG `Grass005` |
| Roof: profiled sheet | https://ambientcg.com/view?id=CorrugatedSteel005 (CorrugatedSteel002–009) | https://polyhaven.com/a/box_profile_metal_sheet, https://polyhaven.com/a/corrugated_iron_02 | Poly Haven `box_profile_metal_sheet` (trapezoid profile) |
| Roof: Logicroof (PVC membrane) | none found | https://polyhaven.com/a/bitumen (approximate, bitumen/tar) | none exact: flat colour + noise, synthetic |
| Roof: «Solo» | product type unconfirmed; RoofingTiles001–015 (clay), https://ambientcg.com/view?id=RoofingTiles006 | `roof_tiles`, `grey_roof_01`, `roof_slates_02` | decide after the user names the product |
| Facade masks (cassette 600, tile 600×1200, panel V1200) | Facade001–020 are whole-building photos, not layout masks | https://polyhaven.com/a/concrete_tile_facade (square tiles, module unconfirmed) | generate procedurally at exact module, mark synthetic |
| Paving 100×300 «Готика» | https://ambientcg.com/view?id=PavingStones144 (rectangular, modern, gray) | https://polyhaven.com/a/rectangular_paving, https://polyhaven.com/a/red_brick_pavers | module unconfirmed in both; procedural 100×300 layout + CC0 concrete surface |
| Pine (wood) | Bark001–016 (bark); https://ambientcg.com/view?id=Ground077 (pine forest floor) | https://polyhaven.com/a/stained_pine, https://polyhaven.com/a/coated_pine, https://polyhaven.com/a/pine_bark | Poly Haven `stained_pine` (MAF WOOD2), `pine_bark` (flora) |

Side finding: `SheetMetal001` (flagged "licence to check" in the Telegram research) is an ambientCG asset, so CC0:
https://ambientcg.com/view?id=SheetMetal001.
