# Plan: rolling out the Telegram findings (2026-11-10)

Source: `docs/research/telegram-3dsmax-chat-2026-11.md` (items, message ids, links). This plan covers the
digital-twin repository only; archviz items go to the max-viz session (prompt kept with the user).
One step = one branch / PR unless marked "batch". Status: `done`, `next`, `later`, `blocked`.

## Phase 0 — done

| Step | Result |
|---|---|
| Research note + backlog items H14, P15–P17, IN9, Q9, Q10 | PR #1176 |
| «Материалы» originals in `G:\Мой диск\AGR-assets\_inbox\telegram-materials-2026-11\` + `manifest.json` | 42 files, sha256 |
| `revit-mcp` skill: session rules from the Revit «zero prompt» | PR #1176, `7ffa0880` |

## Phase 1 — agent hygiene (small, batch; owner Claude, review Codex)

| # | Step | Done when | Status |
|---|---|---|---|
| 1.1 | «Log papercuts» block in `AGENTS.md` → `docs/papercuts.md`, read by `/retro` | block ≤ 5 lines; `/retro` lists papercuts | PR #1179 |
| 1.2 | Compare `destructive_command_guard` with `.claude/hooks/guard.py`; port missing patterns only | diff table + tests for each new pattern | PR #1186 |
| 1.3 | Prompt-guide paragraphs (focus, parallel tool calls, no filler) into subagent prompt templates | one shared paragraph, no duplicates in CLAUDE.md | PR #1186 |
| 1.4 | Try `CLAUDE_CODE_RETRY_WATCHDOG=1` on one long overnight run | run resumes after a limit reset, noted in `CAPABILITIES.md` | later |
| 1.5 | Evaluate Rejudge (3 models + judge) on two closed PR diffs vs the Codex review | findings compared, keep / drop decision | later |

## Phase 2 — materials library (owner Claude; tool code to Codex)

| # | Step | Done when | Status |
|---|---|---|---|
| 2.1 | Approve the layout: `materials\v001\<library_id>\`, `materials\placeholders\v001\`, `flora\v003\maps\<slug>\`, manifest `library/materials/maps_v001.json` | user decision recorded `[D<n>]` | done: [D239] |
| 2.2 | Process the inbox: neutral names, NPM 128 + VPM 256 placeholders, flora split to diffuse RGB + `_o`, power-of-two resize, px/m check against [D207] | manifest rows with sha256, size, px/m, source msg id; validators pass | done: 98 maps in `library/materials/maps_v001.json` by `tools/materials/inbox_maps.py` (spec `maps_v001.spec.json`); new ids 43–52 proposed, not yet table rows |
| 2.3 | MAF atlas 512 bake from 53407 by `library/maf/material_ids_v005.json`; pine as its own WOOD2 slot if the user agrees | atlas passes the MAF atlas rules | review: pine = own id 33 [D240]; `material_ids_v007.json` (v006 + `wood_pine`), 512 atlas `library/maf/atlas_512_v007.json` (`jobs/maf-atlas-512/`, r2 log end); accepted visually 2026-11-10 [D240]; for new MAF only, library MAF keep their UV / atlas (no re-mapping) [D240] |
| 2.4 | New flora species (daisy white / yellow, lavender, wheat, loosestrife, yarrow) into `library/flora/catalogue.json` | rows + maps, `model-flora` tests pass | after 2.2 |
| 2.5 | Fill the missing sets (gravel, pebbles, mulch, rubber crumb, roll lawn, roofs, facade masks, pine) from our own textures (Telegram inbox, tiles of our delivered projects), then generate the rest (`synthetic: true`, 1000 px/m); external CC0 / Megascans not used [D243] (the Fab licence research stays background) | rows in `library/materials/maps_v002.json` | in review: 116 maps (own: gravel, mulch, rubber crumb, roll lawn, pine, rows marked `provenance`; generated: facade / paving masks, brick, pebbles, roofs with roll seams) by `inbox_maps.py` + `texture_surfaces.py`; pine id 53 proposed |

## Phase 3 — 3ds Max tooling

| # | Step | Backlog | Status |
|---|---|---|---|
| 3.1 | Update `3dsmax-mcp` v1.7.5 → v1.7.8 (close Max and all agent clients) | H14 | blocked: user window |
| 3.2 | Live smoke tests of AGR Tools / `agr-mcp` in a pinned Max | Q9 | after 3.1 |
| 3.3 | Link Info «Inherit» → FBX test scene; rule into `docs/domain/` if confirmed | Q10 | done: partly confirmed (rotate-off), rule in `export-import.md`, `docs/research/link-info-inherit-fbx-2026-11.md` |
| 3.4 | Scene analyser: near-identical meshes → instance proposals (report only) | P15 | later (Codex) |
| 3.5 | FenceFit03.dlm on a Ground fence: deterministic, collapse, FBX readback | P16 | later |
| 3.6 | Raster plan → walls with a scale anchor | IN9 | later |
| 3.7 | sand3d (parametric models as code) as a pattern for the MAF family registry | with P14 | later |

## Phase 4 — Unreal (sandbox only)

| # | Step | Done when | Status |
|---|---|---|---|
| 4.1 | UE 5.9 Preview: Unreal MCP on a test project — import one delivery FBX, read back transforms, materials, collisions | report: what the MCP can and cannot do; no production use | later |

## Not taken

Max Ultra MCP, opencode, rea, DragShift, allesimfluss, UV Unfoldr, new requirements PDF / IFC post / window atlas
rule / SintezAgrChecker / AlexYo_AssetImporter from «АГР - Holding» (user 2026-11-10 [D237]), the DLSS exe from
@neuroviza (untrusted binary), the inventory of the Yandex «ALL textures» folder (69813, former step 2.6; user 2026-11-10 [D241]).
