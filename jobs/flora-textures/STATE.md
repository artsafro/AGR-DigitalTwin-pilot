# Flora textures — issue #190

Status: three exact cut-out/opacity candidates APPROVED by Artem (2026-10-15);
external 2048 atlas packed and read back. Texture approval only, not full NPM delivery QA.
Native-size blocker resolved by the user's explicit 1254 -> 2048 LANCZOS exception.

## Final continuation (2026-10-15, explicit cut-out approval)

- Operator direct message: Artem «Одобряю», 2026-10-15 ~21:58, Telegram via
  orchestrator, all three pairs in `C:/x/flora-textures/review-sheet-v001.png`.
  Independently confirmed by owner comment on pilot #190. No repeat approval request.
- Recorded quote/date, exact unchanged candidate IDs/review hash in external
  `C:/x/flora-textures/approvals-v001.json`; read it back before packing.
- First real pack correctly stopped before output because diffuse exceeded 3 MiB.
  Lossless compression probe still gave 3,770,740 bytes. No retry of that layout.
  Added explicit `pack --max-tile-size` (1..2048, default 2048); no silent fallback,
  quantization, source/candidate changes or alpha. Manifest records the actual cap.
- Tests-first commit `dac8230`: `test_pack_explicit_tile_limit_via_cli` RED
  **1 failed, 56 deselected** (missing CLI option); same command after fix GREEN
  within affected suite **63 passed in 4.33s**, including six invalid cap values.
  Command: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q
  -p no:cacheprovider --basetemp=C:/x/t_4005c4b2 tests/test_flora_textures.py`.
- Actual pack: `uv run python -m dt_ai.materials.flora pack --review
  C:/x/flora-textures/review-v001 --approvals C:/x/flora-textures/approvals-v001.json
  --out C:/x/flora-textures/atlas-v001 --max-tile-size 768`.
- External atlas: **2/2** maps 2048 square, RGB/L, no alpha/transparency metadata;
  opacity strictly 0/255, diffuse 2,416,707 bytes, opacity 61,294 bytes (both <=3 MiB).
  **3/3** exact approved IDs and UV rectangles; **3/3** rectangle pairs separated;
  >=8px atlas-border margin. Viewed both maps: distinct complete silhouettes and
  foliage gaps, no obvious corruption. Full hashes: [review-pending.md](review-pending.md).
- `dt profiles check`: **3 profiles OK**; `dt schemas --check`: **11 schemas OK**.
- Final regression eval receipt: `tmp/evals/flora-regression-final/report.json`,
  **0 passed, 0 failed, 10 not measured**, exit 2 (no matching Claude transcript/PR
  capture on this Hermes branch; not a passing eval).
- Fetched main before packing: MAF #184/#196 is now merged, but its public planner
  enforces 512 and renderer is RGB material-only. No compatible shared 2048/binary
  opacity API; own Flora packer retained without modifying the GroundEl tool.
- Captured narrow user acceptance as a row in `docs/cases.md`. No modelling/DCC,
  FBX/geometry/Checker/package gates claimed. PROJECT_STATE stays main-only.
- The sections below are historical continuation evidence, not current blockers.

## Historical continuation (2026-10-15, after the 20:44 user decision)

> source 1254x1254 (codex image_generation, no size control) -> upscaled 2048x2048 LANCZOS, accepted by the user

- No new generation. The three originals remain unchanged outside git.
- Added explicit `flora upscale` CLI: only RGB 1254 square input, new output folder,
  Pillow LANCZOS, original/output hashes, authorization receipt. This conversion
  adds no native detail and grants no texture approval.
- `prepare` includes and validates the upscale receipt in each hashed candidate
  and displays it in the actual review HTML.
- Ran the pipeline through `prepare` for Betula pendula, Pinus sylvestris and
  Spiraea japonica (test list; no source pictures/URLs specified).
- Read back **6/6 actual maps**, all 2048 square, RGB diffuse / binary L opacity,
  no transparency metadata. Pillow 12.3.0. No claim of botanical correctness.
- External output root: `C:/x/flora-textures/`; see [review-pending.md](review-pending.md)
  for exact candidate IDs, hashes, paths and the question for Artem.
- Actual sheet: `C:/x/flora-textures/review-v001/review.html`.
  Companion: `C:/x/flora-textures/review-sheet-v001.png` (viewed by the worker).
- Real-batch gate probe: **1/1 passed**; empty approval records rejected before
  creating `atlas-v001`. No real atlas exists, no approval JSON was fabricated.
- New tests-first commit: `2447ea3`. Initial feature smoke RED: **1 failed,
  52 passed** (missing `upscale` on the inherited implementation); GREEN: **53 passed**.
- Replayable assertion regression at tests-first commit `57eda28`: **3 failed,
  53 passed** (`None`, `False`, `0` were stringified and accepted as authorization).
  Require nonempty text authorization instead; GREEN: **56 passed in 4.89s**.
  Command: `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q
  -p no:cacheprovider --basetemp=C:/x/t_4005c4b2 tests/test_flora_textures.py`.
  RED log: `tmp/flora-red-authorization.txt`. Earlier tRNS evidence below is inherited.
- `uv sync` completed. `dt profiles check`: **3 profiles OK**;
  `dt schemas --check`: **11 schemas OK**. Final full suite (same environment and
  basetemp, no file selector): **3251 passed, 9 skipped, 13 deselected, 48 warnings
  in 382.46s (0:06:22)**; log `tmp/flora-final-tests.txt`. Warnings: ezdxf/pyparsing
  deprecations and intentional duplicate-ZIP fixture. CI: not run (billing lock).
- Current invariant probes (all pass): 256 PNG transparency keys; 255 thresholds x
  256 gray levels; 24 approval faults across three positions; five changed review
  artifacts; 40 packing batch sizes; three repository-output paths; three invalid
  source dimensions; repeat plan/prepare/pack/upscale refuses overwrites; three
  non-text authorization inputs; actual real-batch missing approvals rejected.
- Regression eval receipt: `uv run dt evals --suite regression --output
  tmp/evals/flora-regression-v001`: **0 passed, 0 failed, 10 not measured**, exit 2.
  Hermes branch has no matching Claude transcript/PR evidence; not a passing eval.
- Next: Artem reviews the exact sheet, records approval/rejection per candidate;
  only then transcribe approval attestations and run `pack`, reopen both atlas
  maps and verify limits, commit final evidence, push, open the one PR and send to
  dt-reviewer. Source-quality acceptance alone does not authorize cut-out insertion.
- No changes to PROJECT_STATE (main-only). No images in git. No DCC calls.

## Historical prior continuation (superseded where noted)

### Codex continuation (2026-10-15, before the 20:44 decision)

Read AGENTS.md, PROJECT_STATE, uv-textures.md, conflicts.md, WORKFLOW,
implement skill, external COORDINATION_RULES and Flora grilling notes.
The orchestrator explicitly authorized Codex built-in generation and external
outputs under `C:/x/flora-textures/`; this supersedes the earlier access notes below.

Executed from this worktree:

```bash
codex exec --sandbox workspace-write --add-dir C:/x/flora-textures --enable image_generation '<three-species generation request>'
```

Request: Betula pendula, Pinus sylvestris, Spiraea japonica; each a complete plant,
front view, 2048x2048, pure white background, no shadows/ground/pot/text/cropping.
Codex session `01a140c4-9c1c-71e2-b91a-02affb5e81b5` generated three real RGB PNGs.
Independent Pillow readback confirmed **1254x1254 for all three**, not native 2K.
No upscaling, padding or acceptance was performed. Preserved outside the repo:

- `C:/x/flora-textures/betula-pendula/rejected-non2k-v001.png`
- `C:/x/flora-textures/pinus-sylvestris/rejected-non2k-v001.png`
- `C:/x/flora-textures/spiraea-japonica/rejected-non2k-v001.png`

SELF-FIX: the Codex sandbox could not create the absent external root
(`CreateDirectoryUnauthorizedAccessError`); the worker created the authorized root
and copied the outputs, then reopened each with Pillow. This path problem is resolved.

Targeted second invocation used the same command flags with this request:
"Inspect actual built-in schema for explicit native resolution control; generate
one native 2048 Betula only if supported; otherwise stop without more generations."
It reported `image_gen.imagegen` / `tools.image_gen__imagegen` supports only
`prompt`, `num_last_images_to_include`, `referenced_image_paths`,
`transparent_background`; no size/resolution/width/height parameter. No additional
generation was attempted. Model and generation IDs are not returned; filename UUIDs
must not be invented as generation IDs.

Remaining acceptance: genuine native 2048 inputs, actual three-species cut-out and
review sheet. No atlas may be packed before Artem approves the exact candidates.
Decision requested: authorize a resolution-controlled image API/CLI route, or supply
three native 2048 generated source images. No fallback API usage is authorized yet.
No new code/test changes, commits, pushes or PRs in this continuation. Earlier test
counts below are inherited evidence, not rerun claims.
Context: issue #190 / spec #149; docs/domain/uv-textures.md;
docs/agents/WORKFLOW.md; jobs/GROUND-PROJECTION/STATE.md.
External grilling notes and COORDINATION_RULES 27 were not available inside the
worktree; no outside-worktree files were opened. No git/gh or tracker mutation.

## Requirement

> the user makes plant textures by giving a browser screenshot to an image model ('2K, front view, no shadows, white background'), cutting it out, making a black-and-white opacity and placing it on the atlas; agents may do the same with the image-generation tool, with the user's review of every new texture (first 10-20 species).

Artem, 2026-10-15, Flora grilling rounds 1–2, as supplied in issue #190.

- Profile: NPM Flora texture pipeline; no modelling or VPM shells.
- Acceptance:
  - [x] Documented scripted plan -> real generator handoff -> cut-out/opacity ->
    candidate review sheet -> explicit Artem approval gate -> 2048 atlas.
  - [ ] Actual generation and review sheet with results for three species.
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
- Later decisions: none. No approvals supplied or invented.

## Route and verification

See ../../docs/pipeline-flora-textures.md for commands and the approval schema.
The own grid packer is used because no MAF packer is present in this tree.
The plan was run for Betula pendula, Pinus sylvestris and Spiraea japonica;
`generation-plan.json` records requests only, not generated images.
`review-pending.md` deliberately shows three blocked rows, not fabricated results.

### Verified continuation evidence

The inherited files were all untracked; `git diff` had no tracked changes.
Unchanged affected tests: **50 passed in 5.33s**. Earlier implementation RED
numbers were inherited notes, not independently reproduced in this session.

New regression on unchanged implementation: **2 failed, 50 passed in 4.20s**.
Both assertions detected RGB PNG `tRNS` metadata surviving cut-out and serialization,
including prepared review diffuse images. Fix: remove the transparency metadata
from the diffuse copy without altering RGB pixels or the source image.
Affected GREEN: **52 passed in 3.84s**.

Commands (same harness environment for baseline, RED, GREEN and full run):

```bash
# Affected runs: append tests/test_flora_textures.py to this command.
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_4005c4b2
```

Full suite run exactly once, final line:
`3247 passed, 9 skipped, 13 deselected, 48 warnings in 351.67s (0:05:51)`.
Warnings are ezdxf/pyparsing deprecations and the intentional duplicate ZIP fixture.

| Invariant | Generated / brute-force probe | Result |
|---|---|---|
| Separate opacity; no hidden diffuse transparency | All grayscale PNG color keys, serialize/read back both maps | 256/256 |
| Strictly binary cut-out | 255 thresholds x 256 gray levels | 65,280/65,280 |
| No atlas without individual user OK | 8 approval faults x 3 candidate positions; output absent | 24/24 |
| Changed review invalidates approval | Mutate diffuse, opacity, reference, HTML, manifest | 5/5 |
| No overlap; >=8px margins/gaps | All rectangle pairs for batch sizes 1..40 | 40/40 batches |
| No repository binary destination | outputs/, data/, src/ paths rejected before writes | 3/3 |
| No silent 2K upscaling | Three invalid dimensions; no output | 3/3 |
| No overwrite | Repeat prepare, pack, plan into existing destinations | 3/3 |
| <=3 MiB per atlas map | Two packed-map size checks plus generated noisy oversized map rejection | 3/3 |

All binary evidence is synthetic and remains in pytest's mandated temporary
location, not in tracked files. The synthetic three-entry HTML review is test
coverage only, not the required botanical review evidence.

## Exact blocker / next step

The session exposes only file/shell tools, no image-generation tool. Current
worktree-only permissions also prohibit creating external production PNG outputs.
A properly authorized operator with the dt-* image tool must execute the three
recorded prompts, provide actual generated RGB 2048 images/model/result IDs and
reference pictures where specified, run `prepare` outside the repo, and present
its real `review.html` to Artem. Only his explicit approval of each exact candidate
permits `pack`. No actual botanical texture or atlas has been created here.
