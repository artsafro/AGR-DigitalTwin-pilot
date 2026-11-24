# DCC review opener — native receipt (#1297)

Scope: synthetic scenes only; launcher verification, not model/user acceptance.
Policy: [D270], `docs/agents/CAPABILITIES.md#dcc-acceptance-defaults`.

## Commands executed (2026-11-13)

From the card worktree:

```bash
uv run python tools/open_review_scene.py --app blender --source tmp/native/synthetic_v001.blend --output tmp/native/synthetic_review_v002.blend --open-approved
uv run python tools/open_review_scene.py --app max --source C:/Users/artsafro/.codex/worktrees/ece9/.AGR_Project/tmp/mcp-research-20261103/mcp_cycle_2026_v001.max --output tmp/native/synthetic_review_v002.max --open-approved
uv run python tmp/native/observe.py
```

The Blender source was created in a separate factory-startup Blender 5.1.2 process
with metric units / scale 1.0. The Max source is the two-object synthetic MCP
fixture already recorded in `docs/agents/CAPABILITIES.md`; no production file used.
`observe.py` enumerated visible windows by the **returned PIDs**, queried executable
version metadata, and compared saved-copy SHA-256 to the launch receipt. No bridge
commands or scene mutations were used for observation.

## Observed log

- Blender PID **670424**: `synthetic_review_v002 [C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_2b388368\tmp\native\synthetic_review_v002.blend] - Blender 5.1.2`.
- Max PID **666564**: `synthetic_review_v002.max - Autodesk 3ds Max 2026`.
- Observer output: `{"loaded_apps": ["blender", "max"]}` (receipt also includes its absolute path).
- Both native review copies matched their source hashes. Original Max fixture
  re-hashed unchanged: `91f10f5a22a63a507e7821cb52a67b37d2c2ea9dd6a1d9312c4734276544bab5`.
- Max's live lock was held by the daytime reservation (holder PID 652416);
  it was not deleted, reaped or acquired. No existing Max/Blender process was
  present in the OS preflight. The opener started independent processes and
  never targeted a user's busy document.
- First Blender invocation returned nonzero and exposed an overly
  narrow header check: Blender 5.1 saves Zstandard containers by default.
  Preserved that error log; added two failing compressed-container regressions,
  then supported Zstandard/gzip signatures and repeated the actual native launch.

## Durable evidence (no binaries in git)

`G:/Мой диск/AGR-evidence/1297-dcc-review-open/`:

| File | SHA-256 |
|---|---|
| native-receipt.json | 414c5ca5a169fbea169550a1a7b815e7a8914ac86fb4c1ee629cf53ee1cc6110 |
| blender-launch.json (initial refusal) | bb2f0964df6a747874a8df755ee1f8554bae309fbb948421a7359920d9b853da |
| blender-launch-v002.json | 9965fc55864faa58310bddc79cec76474fdbbbb2c3e3bda229460cac8d2eef3c |
| max-launch.json | ac08ec6108b38dd638679378420d589d4e7993362cb64604229d70af3fa547e4 |
| synthetic_review_v002.blend | e34eaf4a96709d591302d5f008d2bb48a867fa285844baee5dab6f7d0adc908e |
| synthetic_review_v002.max | 91f10f5a22a63a507e7821cb52a67b37d2c2ea9dd6a1d9312c4734276544bab5 |

`SHA256SUMS.txt` is beside these files. The launch paths above name the originals
opened during the test; the Drive files are byte-identical evidence copies.

Boundary: OS document-title readback and executable metadata prove both apps
opened the requested copies; they do **not** certify topology, Max units, materials,
rendering or Artem's acceptance. The helper reports `launched`, not a fabricated
`loaded`/`passed` result. Native container sniffing is not full file validation.
Task consent remains an agent-procedure instruction: tests check all entry points
and the explicit launch flag, not an implemented conversation state machine.

## Focused verification and self-review

- Docs contract before fix: 6 failed; helper before implementation: 15 failed.
- Compressed Blender regression before repair: 2 failed.
- Final affected selection: 224 passed, 0 failed (includes decisions, context-diet,
  entry budget, Blender command and Max-marker contracts).
- Empty/partial/wrong-format/missing-consent: reject before copy/launch.
- Generated consent set (false/null/numeric/string/NaN/inf): 9/9 refused.
- Same/relative/hardlink/occupied/repeated output: 5/5 preserve all bytes.
- Source rewritten during copy: reject; racing output hardlink: atomic no-replace
  rejects without changing the source or leaving a predictable partial file.
- Fresh-process CLI help and unknown-app rejection exercised.
- Failed launch raises, leaves the saved new copy, and produces no success receipt.
- Version token boundaries v000/v001/v999/v1000: 4/4; unversioned/short-version/
  partial/NaN/inf output names: 5/5 rejected. No numerical threshold API exists.

Context-diet repair: retained every baseline rule (verbatim preservation test),
moved the rule-lookup paragraph into the already-linked on-demand agent reference,
and compacted pointer prose rather than raising the entry budget.

## `agr open-review` live test (#1740, 2026-11-21)

Sample: copy of the accepted 63A stage-2 FBX (`C:/x/review-63A/63A_Stage2_v001.fbx`, sha256 `3f9d89f3…ce774c`,
equal to that folder's `SHA256SUMS.txt`) at `C:/x/ev_t_964ab17e/src/`. Review folder `C:/x/review-1740-63A/`.

- Headless check of the copy: `blender -b --factory-startup --python tools/blender/fbx_readback.py -- <copy> <json>`:
  `readback_ok=true`, 1297 meshes, 41 424 polygons, 82 848 triangles (2.00 per polygon: all quads).
- Max 2026: `agr open-review <sample> --job 1740-63A --open-approved` -> `app=max`, new PID; Max imported the copy
  (1297 objects selected, screenshot `max_open_copy.png`). Artem's two open Max sessions (PIDs 26480, 63700) were
  running before and after, untouched.
- Attempt 1 used `3dsmax.exe -mxs "importFile ..."`: Max imported, then quit cleanly ~2 min later (twice, PIDs 161260
  and 59224, `Max.log` "Stop network" right after the script). Fixed: a startup script `<copy>.open.ms` run with
  `-U MAXScript` keeps the session open (PID 164388 alive after 270 s).
- Blender fallback: a simulated held `max-live` lock (`AGR_MCP_LOCK_DIR`, live pid, until +900 s) -> `app=blender`,
  `app_reason=max-live lock held (...)`, lock bytes unchanged; Blender 5.1.2 imported and framed the copy
  (`blender_open_copy.png`; the splash stays, one click closes it).
- Every copy has the source sha256; the source is unchanged. Agent-launched Max/Blender were closed by their own PIDs.

Evidence: `G:/Мой диск/AGR-evidence/1740-open-review/` + `SHA256SUMS.txt`
(`max_open_copy.png` `a03b48a1…`, `blender_open_copy.png` `de1ba999…`).
