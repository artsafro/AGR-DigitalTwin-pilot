# Cross-session retro, 2026-11-04 … 2026-11-05

Scope: 12 Claude Code sessions of the pilot repo with activity on 04–05.11 (NTR presentation had none).
Method: transcripts condensed to user messages, assistant text and tool errors, then classified.
Full per-session reports (local, not in git): `%TEMP%\claude\retro\group{A..E}.md`.

## Sessions

| Session | Outcome | Experience capture |
|---|---|---|
| Опорные стенки (diffuse) | accepted; scene not saved | no |
| Полезные решения для пилота | PR #789, #793 merged; cards #790, #792 | n/a |
| Ворота Object001 | accepted (lp_006, hp_002) | no |
| Garibaldi NPM→VPM | OKS 2 accepted; delivery-v001 handed over without independent check; nothing committed | no |
| VPM кондиционеры K5 | accepted, PR #1008 | yes |
| DWG viz prep (Silikatny) | accepted; part B uncommitted | no |
| Kasatkino Ground | v007 accepted, v008 checked 8/8; uncommitted | yes (end only) |
| VPM ОКС «СРЕDА» | v002–v005 accepted, PR #969 merged; own retro written | no (cases.md has no entry) |
| МАФ Blender | upkeep only; PR #803 draft | n/a |
| Аудит и очистка / Repo hygiene 4 | PR #1009–#1014 merged | n/a |

## Recurring problems (by root cause)

1. **Verification gap: "done" before checking against source/viewport** (СРЕDА 7 defects after green checks;
   K5 alpha holes invisible; DWG/Kasatkino IDs, gaps, skipped face `face_create_fail: 1`; Garibaldi no
   independent check). Rules exist (`uv-textures.md:57,83`, `geometry.md:78`, independent-checker), checks
   do not enforce them. Agents also bent geometry to pass validators (6 mm stand-off vs 10 mm embed).
2. **Existing rules not applied; user had to remind** (Garibaldi: DER-14/18/19, D198 work FBX, xView,
   reveals ID; Gates: D165 lego joints). Validator does not detect a missing `MainGlass`.
3. **DCC instance handling breaks the user's environment**: heavy single calls hang Max/Blender main thread;
   `resetMaxFile` via MCP crashed Max; `freeSceneBitmaps()` blacked out the scene; edits into the user's
   live unsaved scene lost; `adapters/cad/dwg.py:54,113` sets `FILEDIA 0` and never restores it (on main).
   Blender MCP port 9876/9877 confusion cost ~30 min.
4. **Harness / permission friction**: `guard.py` false positives (`\brepo\b` matches `repo-hygiene-*` and
   `--repo`; `\s-D\b` matches `-d` under IGNORECASE), 25 prompts in one session; merge asked twice after
   «Мерджи» (2.5 h wait); 7 of 34 user messages in СРЕDА were permission prompts; bare `python` = Store
   stub (exit 49) although `CAPABILITIES.md` says `py -3`; pytest basetemp inside the repo.
5. **Misread short replies** («принимаю только d15», «хватит спрашивать подтверждения» written to memory
   as skipping Gate 1) and an unverified cause written to memory (`max-mesh-edit-pitfalls.md` line 14:
   the user closed Max himself).
6. **Process skips**: merge recommended before review/receipts (#793), PROJECT_STATE not regenerated,
   experience-transfer skipped after ~10 acceptances, jobs missing from `jobs/REGISTRY.md`.
7. **Decision-number collision**: Garibaldi branch defines a new D198 (290k budget); `main` D198 is the
   work FBX rule.

## Issues filed (labels `needs-triage`, `retro`)

| # | Item |
|---|---|
| #1026 | `dwg.py` FILEDIA not restored |
| #1027 | guard false positives (`--repo`, `repo-*`, `-d`) |
| #1028 | merge gate asked twice after an explicit command (needs the user's decision) |
| #1029 | validator: missing `MainGlass` passes |
| #1030 | texture-joint continuity and decor embed; never bend geometry for a validator |
| #1031 | build reports with skipped faces must fail |
| #1032 | live 3ds Max / Blender safety pitfalls into the DCC skills |
| #1033 | blender-mcp: port check, agent-owned Blender on a copy (needs the user's decision) |
| #1034 | warn on bare `python` |
| #1035 | pytest basetemp outside the repo |
| #1036 | acceptance-phrase reminder for experience-transfer |
| #1037 | D-number collisions across branches |
| #1038 | promote uncaptured preferences (needs the user's decision per item) |
| #1039 | session retro loop |
| #1040 | before/after metric for harness tasks |

## User preferences not yet captured in the repo

- Agent opens/owns its own DCC instance; otherwise always gives the full file path.
- Ground: user does Conform himself and accepts the flat base first; outer gaps close along a smooth
  contour as lawn; white paint on every rubber/rubber joint; IDs follow the hatch background colour.
- Garibaldi: ground-floor frames go into the ground; delivery folder structure.
- СРЕDА: interior capsules recessed to mid-frame, corner glass as 6 mm two-face shell, continuous strips
  (only in `jobs/elv-tc-vpm/TASK.md`, not in `docs/domain/`).
- Gates: simple tube joints with an insert; material IDs 17/21/36.
- Archive policy "tag + git rm" not recorded as a D-line.
- Harness tasks: define a before/after metric up front (user asked twice whether agents got easier).
