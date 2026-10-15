# Flora textures — issue #190

Status: three approved per-species library asset pairs published and read back;
independent code review pending. No atlas deliverable on this issue.

## Current scope and acceptance (Artem, 2026-10-15 via orchestrator)

1. «Одобряю» (~21:58, Telegram via orchestrator): all three exact cut-out/opacity
   pairs on `C:/x/flora-textures/review-sheet-v001.png`. Independently corroborated
   by owner's #190 comment. Quote/date and unchanged candidate IDs/review hash in
   [review-pending.md](review-pending.md) and external `approvals-v001.json`.
2. Later direct operator message: **NO atlas in #190**. Library first (#216),
   placement next, one atlas from placed scene later (#217). Any prior external
   atlas is scratch only. Removed packer/atlas CLI/tests from final branch content;
   historical commits are retained (no history rewrite).
3. Deliver per-species `diffuse-v001.png` + `opacity-v001.png`, both 2048 square,
   under `C:/x/flora-textures/{betula-pendula,pinus-sylvestris,spiraea-japonica}/`,
   the approved review sheet and documented pipeline. No generated binary in git.

## Actual command and readback

```bash
uv run python -m dt_ai.materials.flora library --review C:/x/flora-textures/review-v001 --approvals C:/x/flora-textures/approvals-v001.json --out C:/x/flora-textures
```

- **6/6** actual PNGs reopened: RGB diffuse, L binary opacity, 2048 square,
  no alpha or tRNS, opacity only 0/255. Every published byte equals the exact
  approved review map. **3/3** manifest candidate IDs/approval records match.
- `C:/x/flora-textures/library-v001.json`: per-species paths, hashes and approvals.
  `C:/x/flora-textures/library-evidence-v001.json`: complete numeric readback.
- Actual unchanged review: `C:/x/flora-textures/review-v001/review.html`;
  companion PNG `C:/x/flora-textures/review-sheet-v001.png` was viewed.
- Generation: Codex built-in `image_gen.imagegen`, trace session
  `01a140c4-9c1c-71e2-b91a-02affb5e81b5`. Model/result IDs not exposed.
  Original **1254x1254 -> 2048x2048 Pillow LANCZOS** explicitly accepted by Artem
  at 20:44 (COORDINATION_RULES 27); not native 2K detail. No new generation.
- This is a test list, not the actual GROUND-PROJECTION schedule. No botanical
  reference pictures/URLs supplied. No fabricated references or botanical claim.
- Source-quality acceptance did not approve cut-outs; publication waited for the
  separate exact-pair approval above. No future species inherit approval.

## Verification

- Tests-first library CLI commit `eb6c43e`: **1 failed, 53 deselected**, missing
  `library` command. GREEN: **54 passed in 3.22s** after implementation.
- Earlier retained regression `57eda28`: **3 failed, 53 passed** for None/False/0
  authorizations incorrectly accepted; `3a5e300` requires nonempty text consent.
- Final full-suite result recorded after completion below. Earlier pre-scope-change
  suite: 3258 passed, 9 skipped, 13 deselected, 48 warnings; not final-scope evidence.
- Command: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q
  -p no:cacheprovider --basetemp=C:/x/t_4005c4b2` (add tests/test_flora_textures.py
  for affected run). External test temp, no global machine changes.
- Profiles **3 OK**, schemas **11 OK**. Regression eval report
  `tmp/evals/flora-regression-final/report.json`: **0 passed, 0 failed,
  10 not measured**, exit 2: no matching Claude transcript/PR capture on Hermes.
- Synthetic invariants: 255 thresholds x256 gray levels; 256 PNG transparency keys;
  24 approval faults across three positions; five changed review artefacts;
  three repository destinations; three invalid source dimensions; no overwrite;
  byte-identical per-species publication. Atlas tests removed with user scope change,
  not to hide a failure. No DCC calls or full NPM delivery checks claimed.
- Narrow accepted case recorded in `docs/cases.md`. PROJECT_STATE remains main-only.
  CI: not run (billing lock).

## Original requirement (historical scope superseded above)

> the user makes plant textures by giving a browser screenshot to an image model ('2K, front view, no shadows, white background'), cutting it out, making a black-and-white opacity and placing it on the atlas; agents may do the same with the image-generation tool, with the user's review of every new texture (first 10-20 species).

Artem, 2026-10-15, Flora grilling rounds 1–2, as supplied in issue #190.

- Profile: NPM Flora texture pipeline; no modelling or VPM shells.
- Acceptance:
  - [x] Documented scripted plan -> real generator handoff -> cut-out/opacity ->
    candidate review sheet -> explicit Artem approval gate -> 2048 atlas.
  - [x] Actual generation and review sheet with results for three species.
  - [x] Synthetic white-background cut-out regression and invariant probes.
- Inputs: issue text; Pillow/numpy versions pinned in pyproject.toml; three-species
  **test list**, not a verified GROUND-PROJECTION planting schedule.
- Ownership: only this worktree; no DCC scene, MCP port or external production
  output is owned or mutated in this session.
- Outputs: text plan and pending review tracked here; candidate/atlas PNGs only
  through an authorized operator outside the repo. Synthetic test binaries only
  in the mandated pytest temporary directory.
- Stop conditions: no image tool, no genuine output IDs, missing/changed reference,
  non-2K generation, absent explicit Artem approval, changed reviewed artifacts.
- Later decisions: none. Artem approved the three exact pairs on 2026-10-15; atlas scope later removed.

## Handoff

Next: push the committed branch, open the single PR, request dt-reviewer.
#216 consumes the per-species maps and approved review evidence. #217 owns atlas
packing and MAF packer reuse; neither is implemented by this texture-only issue.
