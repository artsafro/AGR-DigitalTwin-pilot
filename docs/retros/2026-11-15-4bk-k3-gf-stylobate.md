# Retro 2026-11-15: job 4bk-k3 — VPM tower floor 1 (A) + small stylobate (B) from Revit

Session `0a3a9c47-…` (Claude Code, branch `job/4bk-k3-vpm`, PR #1443), 2026-11-14 13:00 → 2026-11-15 15:44 local,
three context compactions. Condensed log: `tools/retro/condense_transcript.py` (one transcript, 203 lines).
Job record: `jobs/4bk-k3/TASK.md` (commit `6aa786d9`). Build root (outside git):
`Desktop/!3D viz/!А101/63_4BK_vlad/build/gf_parts/`. Artem's hand-finish analyses:
`gf_parts/_review/max/artem_v007_analysis/ANALYSIS.md` (B) and `artem_final_analysis/ANALYSIS.md` (A and B).

## Outcome

| Stage | Result |
|---|---|
| Intake + Revit read 13:00–13:21 | read-only Revit analysis; FBX exported through RevitBridge (`export_fbx`, doc not saved) |
| Swarm v001 13:21–14:17 | 7 parts, ~15.7k tris; the independent check failed; Artem: B «на четыре с минусом», A «на троечку» |
| v003 / v004 14:34–17:31 | B v003 accepted 17:02 («стилобат принимаю, почти идиальный»); A v004 accepted 17:31 («принимаю первый этаж, все норм по геометрии») |
| UV B 17:03–22:36 | 530 px/m, long walls cut by panels; accepted in Max |
| QA rounds on A after acceptance, 17:53 → 00:48 | checks v004–v009, body A v005–v008e; most findings came from the checker's own method |
| Textures 11:41–14:00 | A textured on v008e, rejected 12:54; redone on the accepted v004 set (`K3_A_tex_review_v002/v003.max`) |
| UCX 12:15–15:10 | plan accepted 12:15; UCX B accepted 13:03, UCX A accepted 15:10 |
| Hand finish | Artem finished A and B himself (`bldA.max`, `bldB.max`); merged into `scene_build_A_build_B_v002.max`; both at ~80 % |

No delivery package. Open (Artem): naming/address, full texture set, GeoJSON, pivot and rotation, canopies.

## Incidents by cause

### missing-rule (2)

1. **Five technical QA rounds on geometry the user had accepted** (A accepted 17:31 on 11-14; rounds v005–v009 until
   00:48; anger 11:55). Each round's findings came mostly from the checker's method (incident 9). The fixes added
   thin strips and diagonals, and no textured A existed for half a day. Artem: «надо было мне отдельно указать … хелперы
   поставить мне». Rule: AGENTS.md says technical QA and user acceptance are separate statuses; nothing says accepted
   geometry is frozen and later findings go to the user as a list. D201 freezes accepted geometry only for the AC08
   kernel. Memory `accepted-geometry-freeze` (written in this session) is the only record. → issue.
2. **Artem had to finish both bodies by hand** (12:57, 15:10: «у тебя было много упущений, мне пришлось перемоделивать
   за тебя»). B: glass and grilles 20 mm larger and moved to the frame's mid-depth, rings on lamellae and fins at transom
   heights, the cornice and band as closed boxes. A: brick and АКП re-unwrapped as segment × band islands with the left
   edge on the painted joint, reveals as closed U-profiles, capsules enlarged, joint maps edited. Evidence: both
   `ANALYSIS.md`. Rule: none in `docs/domain/` for infill overlap under the frame, vertical-member rings, cornice
   boxes, or segment × band UV islands. Memory `facade-uv-etalon-4bk` and `window-agent-defects` only. Artem asked for
   the window defects as a separate kanban card (12:10). → two issues (domain rules; window builder).

### ignored-existing-rule (2)

3. **Fans and diagonal edges in body A** (11:34 «почему так нельщя моделить?», 11:39, 11:48). Measured on the
   vertical walls (sliver = one side < 5 cm and another > 0.5 m): v001 15 slivers / 172 diagonals / 49 tris; v004
   (accepted) 4 / 124 / 80; v008e 23 / 125 / 30. A v008 centroid split gave 1898 tris and 61 slivers (rejected 22:36).
   Rules: [D200], [D129], `docs/domain/geometry.md:110` («BODY quad layout … no fans»). Enforcement gap:
   `src/twinqa/look.py` checks only T-junctions for D200, `src/dt_ai/ops/inv_quads.py` counts triangles but not
   diagonal edges or slivers in quads, neither ran on the swarm's parts, and `docs/scenarios/oks-vpm.md:76` lists loop
   continuity as not checked automatically. Artem: one diagonal between opening corners is better than dense cuts
   (11:48). → issue.
4. **Texture deliverable built on v008e, not the accepted v004 set** (12:12 shown; 12:54 «ни в какие ворота не
   годится … нужно использовать геометрию, которую я вчера утвердил»). TASK.md recorded the accepted set (body v004,
   windows v003, roof v003) at 17:31; the UV brief took the latest versions. Redone at 12:58. → same issue as 1.

### wrong-assumption-not-checked (3)

5. **Colonnade of A v001 built by a "sees the sky" face filter on the Revit FBX** — under the tower almost no face sees
   the sky, so back walls, half the windows and a door were deleted (14:31 review; 17:05–17:07 «почему нельзя снять
   сечение колонн и посторить по сечению квадратному?»). The agent admitted a briefing error; v004 rebuilt the columns
   as prisms from plan sections. Rule: memory `panelised-source-direct-build` (measure and build) only.
6. **E2 end post of roof A deleted on a simplified tower prism** (brief for v006; admitted 23:25). The prism sat
   0.26–0.36 m off the real pylon. Restored in v007/v008. Part of the checker-method family → issue (incident 9).
7. **Revit analysis agent reported base and survey points "unavailable"** (13:14; user asked twice 13:14/13:15). They
   are readable as `OST_ProjectBasePoint` / `OST_SharedBasePoint` via `revit_list_elements`. One-off; candidate line
   for `.agents/skills/revit-mcp/SKILL.md` (no issue).

### verification-gap (2)

8. **Body A v007 deleted visible reveals (A_OP12, A_OP01) as "hidden"** (22:11), and **L2 v004 deleted the grille back
   panels Artem had asked for** (18:00, rejected). Hidden-face cleanup without a visibility check from close eyes.
   → covered by the checker issue (incident 9).
9. **Checker method varied run to run** (checks v004–v009): eye-only jitter vs eye+target (334 vs 0 back faces), prism
   vs real tower, caps that leaked through the tower's openings, embeds by vertex vs by edge. Each part agent and each
   checker rebuilt the method from a brief. Recorded as `docs/backlog.md` Q10 (committed `6aa786d9`), no issue yet.
   → issue (tracks Q10).
10. **Max review opened grey** (17:46 «материалов не вижу в сцене текстур геометрия серая»): Cyrillic path in a `.ms`
    without BOM, MultiTile showing black tiles, no light. Covered by #1365 (open).

### harness/permission-friction (3)

11. **SendMessage into workflow agents spawned duplicate writers** (14:40): four parts had two writers; body A detected
    it and stopped. Memory `workflow-agent-sendmessage-duplicates`. → issue (swarm coordination).
12. **L2 v006 task sent to the windows B agent** (it refused: not its part); the coordinator found the L2 agent by
    grepping task outputs. → same issue.
13. **Stray agent output outside the build root that the guard would not let agents delete**: `C:\png_v003`,
    `C:\dbg\top_op11_15.png`, `C:\gf_parts`, `C:\x\chk-4bk-k3-v005`, plus `.blend1` and debug folders; Artem has to
    delete them by hand. → same issue.
- Minor, no issue: revit-mcp skill gate denied 4 calls before the skill loaded (by design); pyRevit bridge tab absent,
  used RevitBridge through a scratch stdio client `bridge_call.py` (route documented in `docs/agents/CAPABILITIES.md`
  :135); bare `python` exit 49 (#1034, warn-only); the independent checker cannot write its report (hook) — the
  coordinator wrote `check_v00N.md`.

### scope-creep (observation)

- UCX agents started 12:16 in parallel with texture acceptance, against the order Artem stated at 12:13; the agent
  said so and offered to rerun. No harm (UCX accepted).

## Acceptances and experience-transfer

| Time | Acceptance | experience-transfer |
|---|---|---|
| 11-14 17:02 | stylobate B v003 geometry | not run |
| 11-14 17:31 | floor 1 A v004 geometry | not run |
| 11-15 12:15 | UCX plan | not run |
| 11-15 13:03 | UCX B; B geometry + UV + UCX closed (~80 %) | not run |
| 11-15 15:10 | UCX A; A and B as near-etalon | not run (analysis + memory instead) |
| 11-15 15:32 | the etalon analysis confirmed | not run |

The skill never ran (skills used: revit-mcp, blender-mcp, workflow-authoring). The acceptance nudge does not fire on
Russian prompts: covered by #1363 (open, recurred again).

## Preferences and decisions not captured as D-lines

Recorded in `jobs/4bk-k3/TASK.md` and/or memory only:

| Preference / decision | Where |
|---|---|
| Texel ≥ 520 px/m («512 это слишком низкое значение, надо хотя бы 520») — conflicts with [D160] (512) | TASK.md |
| Main window glass is always a separate object at delivery | TASK.md, memory `delivery-glass-detached` |
| Long walls over a tile: vertical loops (Connect on horizontal edges), on joints or every ~4 m | TASK.md, memory `long-wall-udim-loop-cuts` |
| Accepted geometry is frozen; later findings go to Artem as a helper list | memory `accepted-geometry-freeze` |
| Ground drop 2 m (−2.305); a frame < 10 cm above the bottom goes down; a protruding open polygon is moved down, not capped | TASK.md |
| Railing glass one 20 mm slab, posts on its axis, top handrail; no top face, one continuous cap | TASK.md, etalon analysis |
| Roof exit boxes take the roof colour | TASK.md |
| Columns from plan sections as prisms | TASK.md |
| One diagonal between opening corners is acceptable instead of dense cuts | not recorded |
| No capsule behind a ventilation grille | etalon analysis |
| Box projection gives 441 vs 613 px/m on diagonal facades — open question | etalon analysis |

## Issues

Filed with `needs-triage` + `retro`; all pass `tools/check_ready_gate.py`:

| # | Item |
|---|---|
| #1445 | Freeze user-accepted geometry: accepted set with hashes, post-acceptance findings as a helper list (incidents 1, 4) |
| #1446 | BODY wall-layout check: diagonal edges, sliver strips, fans (incident 3) |
| #1447 | Shared VPM visibility checker `dt qa visibility`, tracks backlog Q10 (incidents 6, 8, 9) |
| #1448 | Promote the confirmed facade etalon rules into `docs/domain/` (incident 2) |
| #1449 | Window builder: glass/grille overlap, frame width, set-back capsule — Artem's kanban card (incident 2) |
| #1450 | Swarm coordination: part-writer registry, absolute output root (incidents 11–13) |
| #1451 | Triage: preferences to promote to D-lines, incl. texel 520 vs [D160] |

Covered by existing issues: incident 10 → #1365 (open); acceptances without `experience-transfer` → #1363 (open,
recurred again). One-off / no issue: incidents 5 and 7 (briefing and Revit base points), minor harness items
(#1034 warn-only).
