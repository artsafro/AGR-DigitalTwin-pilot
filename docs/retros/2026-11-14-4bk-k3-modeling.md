# Retro 2026-11-14: job 4bk-k3 — VPM corpus K3 + small stylobate (intake, modelling, UV)

Session `d1636320-…` (Claude Code, branch `job/4bk-k3-vpm`), 2026-11-12 12:39 → 17:18 local (UTC+1); the
2026-11-14 part is only the decisions commit `fd538338` and this retro. Condensed log:
`tools/retro/condense_transcript.py` output (one transcript, 133 lines; one 194 kB line was an inline image whose
text part was read separately). Job files: `jobs/4bk-k3/TASK.md`, `SOURCE_ANALYSIS.md`, `parts/k3_parts_v001.json`.

## Outcome

| Stage | Result |
|---|---|
| Intake 12:39–13:08 | passport + sources (14 files, hashes), SOURCE_ANALYSIS, parts v001; Gate 1 accepted 13:07 («Почти все принимаю») |
| Typical module 13:11–14:07 | v001 geometry (floor joins fixed), UV v002 (37 courses) → v003 (38) → v004 (bands ID2, niche sides brick); brick accepted 14:01 («кирпич увидел, разложил хорошо, красиво») |
| Parallel parts 13:32–14:14 | slats, band 8/13, superstructure 17–18, roof v002 (accepted 14:11 «По кровле я принимаю»), stylobate |
| UV + joints 14:13–15:02 | АКП joints 10 mm by the architect's red lines; assemblies `K3_assembly_v001…v004.blend` |
| Max 15:04–17:18 | `build/3k_v002…v004.max` (61 objects, quads), 33 AC units, 24 stylobate openings; tower АКП 3 tiles at 512 px/m (ID2/11/12) |

No delivery yet; nothing shown was declared final. Follow-ups already in the tracker: research #1314 (closed,
`docs/research/vpm-course-grid-1314.md`), pilot #1326 (open).

## Incidents by cause

### wrong-assumption-not-checked (4)

1. **Niche side walls read as window reveals** (14:01–14:04). The agent mapped «в нишах боковушки темные» to the
   reveals (ID3) and sent the v004 brief to repaint them. User: «Не-не-не, ты неправильно понял. Откосы у нас правильно
   выполнены сейчас». Brief re-sent in 3 min. Rule: none for confirming the target faces; #1326 now requires a per-face
   finish manifest first. Same class as item 5 of `2026-11-05-sessions-retro-04-05.md` (misread short replies).
2. **Wrong building block taken from «1 эт_2.jpg»** (14:39–14:54). The stylobate UV agent used the dark АКП block on
   the left of the sheet (another building) instead of the brick block right of the tower. User 14:42: «почему мы
   сделали его черно-белым. Он должен быть весь в кирпиче». Four more user turns (14:47–14:54) to settle plinth and
   joints. Rule: `docs/domain/materials.md:28` (decisions trace to the source sheet) covers the sheet, not the region
   on a multi-building sheet; SOURCE_ANALYSIS named sheets, not crops. → issue.
3. **37 courses per floor without the half-bond parity check** (13:31 → 13:54). One ~23-min UV run produced a bond
   break at every floor seam (odd count, bond repeats every 2 courses); the user chose 38 at 13:55. Rule:
   `docs/domain/uv-textures.md:57` (keep joint phase); the parity condition is now explicit in
   `docs/research/vpm-course-grid-1314.md` §metrics. Covered by #1326 (course/bond residual metric).
4. **34 windows on band floors, types sum to 31** (13:01 → corrected by the agent 14:08). One-off arithmetic slip, but
   `jobs/4bk-k3/SOURCE_ANALYSIS.md:33` still says «windows (34: …)» — fix in this branch, no issue.

### verification-gap (2)

5. **Saved review `.blend` had no textures** (13:57–13:59). Bricks1 was wired only in the agent's render script;
   `typ_module_v003.blend` had empty materials. User: «Что-то у меня в блендере не видно кирпича». Rule: none — no
   check that a file handed to the user shows its textures. → issue.
6. **Joints invisible in the Max viewport** (15:39). ID2 used MultiTile UDIM, which the Max viewport does not draw;
   brick joints were lost to Nitrous texture downscaling. User: «отображение металлического ID2 нету во Viewport из-за
   того, что мультитайл». The agent then raised `NitrousGraphicsManager.SetTextureSizeLimit 4096` — a global Max
   setting — without asking (permission matrix, `docs/agents/WORKFLOW.md:446`, «change machine settings: ask»).
   Rework 15:40–17:17 (2 tile rounds: 2 tiles at 420 px/m < 512 [D160], then 3 tiles). → issue (with item 5).

### ignored-existing-rule (2)

7. **ID2 spread to ~25 MultiTile tiles** before the user's left-edge stacking method (15:59). Rule:
   `docs/domain/uv-textures.md:57-58` (stack identical islands; VPM one UDIM per texture ID, «not 19 from unique
   packing»). The user had accepted «ID 2 занимает 4 тайла» for the typical floor only (14:42). Covered by #1326 /
   #1314 (procedure, tile metrics).
8. **Acceptances without `experience-transfer`.** Four acceptances (12:52 partial, 13:07 Gate 1, 14:01 brick, 14:11
   roof); the skill never ran. Root cause found: the acceptance nudge (#1036, closed) never fired —
   `tools/hooks/prompt_hooks.py` reads stdin as cp1251 on this host (`sys.stdin.encoding` = cp1251, UTF-8 mode off),
   so Russian prompts arrive garbled and `condense_transcript.signal()` returns ' '. Reproduced: the same JSON piped
   with `PYTHONIOENCODING=utf-8` prints the nudge, without it prints nothing. Other hooks read stdin the same way
   (`guard.py:673`, `pretool.py:217`, `skill_gate.py:73`, `context_watch.py:117`). → issue (recurred #1036).

### tool/MCP-failure (1)

9. **3ds Max MCP retargeted to a second Max** (13:33). PID 563748 was pinned at 12:56 (`pinned: true`); at 13:33
   `list_max_instances` showed new PID 570920 as default + selected. One call timed out, one read-only call ran on the
   wrong Max (error, no damage); the agent re-pinned. Third occurrence (2026-11-06, 2026-11-07 in memory
   `max-mcp-instance-pinning`). The memory's PID guard was used in 0 of 41 `execute_maxscript` calls (maxFileName
   guard in 16). Rule: memory + `.agents/skills/3dsmax-mcp-dev/SKILL.md:16` (pin) — pinning alone does not hold, and
   the guard is not enforced. → issue.

### harness/permission-friction (minor, no issue)

- Bare `python` → exit 49 at 12:40 despite the pretool warning (covered by #1034, warn-only by design).
- Skill-gate denial before `list_max_instances` (12:56), heredoc backslash SyntaxError (15:04), FBX import dropped
  the stylobate walls (60 of 61 objects, re-imported in add mode, 15:05).

### slow/inefficient-path (observation)

- 13:45 user: «почему у агента 15 мину на разверкту тратится?» — the main session could not see inside the running
  agent; the run took 23 min (13:31–13:54) and included the 37-course mistake (item 3).

## User preferences stated, where recorded

| Preference | Recorded |
|---|---|
| Working DCC folder is `build/`, not `work/` | TASK.md only (job) |
| Lego joints: embed the smaller part into the larger, delete its buried faces | TASK.md «Part joints» (job); general? → triage |
| Joint UV method: one texel, straighten, stack panels by the left edge onto one painted joint | TASK.md (job); research #1314 |
| Review in the Max viewport: plain Bitmap per ID, joints visible | TASK.md (job); not a rule → triage |
| Two VPM deliveries for separate buildings; АКП 3 tiles at ≥ 512 px/m | TASK.md (job) |
| AC units one-sided box, facade faces embedded 10 mm | TASK.md (job) |
| Quads, loops and rings as in Vlad's model; Blender allowed, final Max scene | TASK.md; D200 |

## Issues

Filed with `needs-triage` + `retro` (all pass `tools/check_ready_gate.py`):

| # | Item |
|---|---|
| #1363 | Hooks read stdin as cp1251: acceptance nudge never fires (item 8; recurred #1036) |
| #1364 | 3dsmax-mcp pin lost on a new Max; enforce PID guard (item 9) |
| #1365 | Review handoff check: textures visible in the file opened for the user (items 5-6) |
| #1366 | Per-part crops on multi-building architect sheets (item 2) |
| #1367 | Triage: preferences to promote to D-lines |

Covered by existing issues: items 3 and 7 → #1326 (with #1314 research); item 1 partly → #1326 (finish manifest per
face). One-off: item 4 (fix `SOURCE_ANALYSIS.md:33` in this branch). Harness minor items → #1034 (closed, warn-only).
