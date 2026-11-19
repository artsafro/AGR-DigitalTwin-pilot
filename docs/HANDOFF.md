# Handoff — 2026-11-19 09:30

Branch: `job/colleague-maf-models` · Commit: `e39e0d30` · Worktree: `C:/Users/artsafro/.AGR-DigitalTwin_pilot/.claude/worktrees/model-two-mafs-7892db` · Job: `-`
Transcript: `C:\Users\artsafro\.AGR-DigitalTwin_pilot\logs\transcripts\job-colleague-maf-models-prnone-b5c2da4d-df90-403b-b1e7-e82fbd5ef2cf.jsonl`

<!-- Written by /handover (.claude/commands/handover.md), read by tools/hooks/session_context.py and /takeover.
Keep the `Branch:` line as is (the hook parses it). Facts only, no history: git log and the pull requests hold
that. The whole file stays under 7000 characters so the SessionStart hook passes it in full. Empty section: "-". -->

## Where we are

Goal: model playground/park MAFs for Artem's colleague (Vlad) — clean mid-poly QUAD geometry, loops/rings,
sunk "lego" joints, split by material ID per manufacturer spec; NO textures/UV.
Batch 1 done and accepted by Artem 2026-11-15: Leber MG4013 (5769 quads) and Mestooo 171620 (1989 quads).
All work is outside git (no repo code changed): `C:\x\two-mafs\` (source/, work/scripts/, outputs/, BREAKDOWN.md).
Library candidates (unfinished: no UV/textures/xView/NPM light) copied with README + SHA256SUMS to
`G:\Мой диск\AGR-assets\_inbox\two-mafs-2026-11-15\`. Max readback: `outputs/*-max-v001/readback_v001.txt`.

Working route (reuse it):
1. Manufacturer page -> renders + DWG (`curl` into `C:\x\<job>\source\`, sha256); DWG -> DXF via
   `dcc_batch.py acad` + ezdxf (subagent) for dims, post schedule, heights.
2. Part breakdown + quad rules + ID table first (`C:\x\two-mafs\BREAKDOWN.md` is the template).
3. Build headless in Blender 5.1 with `C:\x\two-mafs\work\scripts\maf_parts.py` (log/sleeve/slab/board/sweep,
   quad caps, sharp 45°); `preview.py` workbench renders; open each stage as a NEW versioned .blend in a new
   Blender window for Artem (`Start-Process blender.exe <file>`).
4. After "принято": `export_maf_fbx.py` (join, pivot D095 to origin, quad FBX) -> `3dsmaxbatch fbx_to_max.ms`
   (Editable Poly, Multi/Sub with library IDs from `<id>_<name>` material prefix, readback log) -> open in a new Max.
   Colour review scene: `review_colors.ms`.

## In progress

Batch 2 (not started), links from Vlad (Telegram 2026-11-19):
1. Leber swing «Контур радиусные, подвес диван» — https://leber.ru/ru/catalog/ulica-i-park/kaceli-parkovye/kaceli-kontur-radiusnye-podves-divan-pm
2. Aira parklet PR-014 — https://aira.ru/produktsiya/malye-arkhitekturnye-formy/parkleti/parklet-pr-014/
3. Adanat parklet type 6.2 with lighting — https://adanatgroup.ru/katalog/ulichnaya-mebel/parklety/parklet-tip-6-2-s-podsvetkoy/
4. Leber carousel «Гнездо 2» — https://leber.ru/ru/catalog/igrovoe-oborudovanie/karuseli/karusel-gnezdo-2
5. Adanat spring rocker «Божья коровка» — https://adanatgroup.ru/katalog/detskoe-igrovoe-oborudovanie/eko-stil/pruzhinnye-kachalki/kachalka-na-pruzhine-bozhya-korovka/

Open DCC windows left by this session: Blender (mg4013/m171620 review .blend), Max `two_mafs_review_v001.max`
(PID 950992). Artem's own Max (4BK scenes, PIDs 316280/772888) and Blender `gf_body_A_v008e` — never touch.

## User decisions not in the code

- (Artem 2026-11-19) Before modelling each new MAF, check the digital-twin MAF library: if it exists there, do
  NOT model it; otherwise model by the same logic as batch 1. Library lookup: `library/assets/maf_unified.json`
  (A101 archive, articles/makers), `library/maf/catalogue.json` (+ previews, Union scene audit),
  `G:\Мой диск\AGR-assets\maf\` and `_inbox\` (incl. two-mafs-2026-11-15). Match by article/maker/name, then
  dims ±10 cm and picture — a dimension-only candidate is not a match.
- (2026-11-15) Model in any DCC; review copies open in Blender; final assembly/acceptance in 3ds Max (memory
  `review-in-blender-final-in-max`). Acceptance-scene answer = yes: open each stage automatically + path.
- (2026-11-15) Accepted recommendations: HPL panels -> ID 5 paint_ral9003; decks = one slab, visible-silhouette
  boards (pickets, lap roof boards) separate; logs 33 wood_pine, boards 14 wood_light, log ends 18; one mesh per
  MAF, FBX + quad .max, pivot D095; light NPM version only on request; pilot piece first, then the rest.
- (2026-11-15) Artem's corrections to design in from the start: slide side guard boards, entries (rope net,
  ladder), grab handles at entries, openings in pickets for every entry, rails/handrails end in posts.
- (2026-11-15) Finished MAFs go to the library as unfinished candidates in `_inbox\<job>\` with README.

## Waiting for the user

-

## Next step

Fresh session: library check of the 5 batch-2 MAFs (table: exists / model), then pilot of the first one to model.

## Rules broken

- Retro step skipped: corrections were normal review feedback (captured in memory `two-mafs-leber-mestooo-job`), no retro file.
- No job folder/README in `jobs/` and no `jobs/REGISTRY.md` entry for this work (outputs outside git only).

## Open PRs and issues for this task

-

## Agent trace

- Sessions: `b5c2da4d-df90-403b-b1e7-e82fbd5ef2cf`
- Written by: -
- Subagents: general-purpose 3, web-fetch 2, Explore 1
- Skills: 3dsmax-mcp-dev 1, blender-mcp 1
- Commands: none
- Hook denials: 1: mcp__blender__execute_blender_code - Load the `blender-mcp` skill first (Skill tool), follow it, then repeat this cal
- Retries: none
- Context at handover: 36 % (361k of 1000k tokens)
- Duration: 90 h 32 min (2026-11-15T14:08:33Z - 2026-11-19T08:41:29Z, UTC)
- Commits: `e39e0d30..e39e0d30` (0 commits)
