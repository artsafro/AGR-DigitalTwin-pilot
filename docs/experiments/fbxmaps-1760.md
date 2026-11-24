# #1760: installed MZP FBX map readback in Max 2026.3

## Question and scope

Does PR #1792's installed panel detect a silently dropped embedded metallic map,
respect refusal, reconnect on approval and report a fresh native readback?
Card `t_75727fc0` explicitly authorizes **headless only**, synthetic inputs and a
copy of the bundle; it supersedes the previous live-GUI test setup for this run.
No GUI session was attached, no customer file was used, no production code changed.
This is native smoke evidence, not customer acceptance or a complete delivery certificate.

## Setup

- Tested production head: `91cabf2ba849b7f60e63a80fbc56e2f6ccf9afb0`.
- Max **2026.3 (28.3.0.30732)**, embedded Python 3.11.12; metres, system scale 1.
- `dcc_batch.py max --ping`: success, 44.9 s after shared-lock waiting.
- Build: `uv run python tools/max/build_agr_tools.py tmp/native-1760/AGR-Tools.mzp`.
- MZP SHA256: `1ae31f4706a93bf8444df76b5b74e57b581deb8ed6f0966b7bca3fe5bb3f9797`.
- Copied `%APPDATA%/Autodesk/ApplicationPlugins/AGR-Tools.bundle` into isolated
  scratch, removed only the copied `Contents/agr_tools`, extracted the built MZP,
  then executed its **real `install.ms`** with `AGRToolsInstallRoot` pointing to
  the copied bundle and `AGRToolsStartupRoot` pointing to scratch. Installer and
  startup executed successfully (2.185 s). All four changed runtime/panel sources
  match the shipped sources after newline normalization. Original bundle's full
  file/hash dictionary is unchanged after all trials.
- Native harness: `experiments/fbxmaps-1760/native_smoke.py`. Config at
  `tmp/native-1760/config.json` has absolute `output` (must not exist), `bundle`
  (read-only original bundle), and `mzp` paths. Example output root:
  `C:/Users/artsafro/.hermes/profiles/dt-experimenter-codex/cache/scratch/agr-3dsmax-t_75727fc0-v4`.

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max \
  --file experiments/fbxmaps-1760/native_smoke.py --card t_75727fc0 \
  --wait 300 --timeout 300 --out tmp/native-1760/batch-v4.json --max-chars 1000
```

Only one headless Max runs at a time. A busy lock was not bypassed.
Always inspect `result.json`: Max's exit 0 alone is not the smoke verdict.

## Inputs and method

Both inputs are **synthetic one-plane scenes**, derived from the project's actual
native-export FBX fixtures in `tests/fixtures/fbx_metallic_1729/` as copies:

1. Standard material diffuse/roughness/metallic. The original fixture uses
   `ReflectionColor`, which Max reconnects automatically (3/3). To reproduce the
   incident deterministically, the harness changes only the final OP connection
   `ReflectionColor` to `ReflectionFactor`, updating FBX 7400 node end offsets and
   property lengths. Geometry and embedded media remain in the native fixture.
   This variation imports with **2/3** maps, metallic absent.
2. Physical material diffuse/roughness/metallic, unmodified fixture. Already
   imports with **3/3** maps; negative/no-op control.

For each input, three independent output paths/imports in one session. Select
only the imported object. First invoke installed `MaxBackend.check_fbx_maps`
with decline, assert the native map inventory is unchanged. Then instantiate
installed `AgrPanel`, click its real map-check button, decline and inspect the
report; click again with approval, inspect the report and native readback.
Only file-picker/confirmation answers are automated; backend, scene, import,
installer, panel handler and report rendering are real. No native modal-dialog
interaction is claimed. Existing Qt tests cover default-No confirmation.

## Measurements

Times below are medians of **3** runs, in seconds, excluding startup. Approval
includes panel report rendering; decline is backend-only, so these are different
operations, not a speed comparison.

| Input | Native import baseline | Decline unchanged | Approved readback | Import s | Decline s | Panel approve s |
|---|---:|---:|---:|---:|---:|---:|
| Standard / ReflectionFactor | 2/3, fail | 2/3, fail (3/3 trials) | 3/3, pass (3/3 trials) | 0.163840 | 0.002808 | 0.010939 |
| Physical / native metalness | 3/3, pass | 3/3, pass (3/3 trials) | 3/3, pass (3/3 trials), no reconnect | 0.212869 | 0.003035 | 0.005863 |

- Final batch wall time: **66.3 s**, exit 0, no startup warnings; result: `pass`, 6 runs.
- Reconnect failures: **0**. Standard's exact missing map:
  `T_Probe1729_stdreflection_Ground_m_1.png`, target `reflectionMap`.
- Native pre/post vertices, triangle counts and node transforms: exact equality
  for **6/6** trials; maximum vertex deviation **0 mm**. No geometry repair.
- FBX input-copy hashes unchanged **6/6**; original installed bundle unchanged.
- Affected offline tests:
  `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider tests/max_tools/test_agr_tools_builder.py tests/max_tools/test_agr_tools_ui_qt.py tests/max_tools/test_fbx_metallic_1729.py`
  → **46 passed**, 0 skipped, 11.72 s; one basetemp fallback warning.
- No full suite (card policy). No remote CI checks reported for this branch.
- Production complexity unchanged. Added only a standalone native harness and this report.

## Evidence

External evidence (no binary committed):
`G:/Мой диск/AGR-evidence/1760-fbxmaps-native-max2026/`.
`SHA256SUMS.txt` accompanies `AGR-Tools.mzp`, `batch.json`, `result.json` and the
paired panel captures. The captures are rendered **inside headless Max**, not
screenshots from Artem's GUI. Visually inspected: before shows one red
`Не подключена: M_Probe1729_stdreflection_Ground_1 / ReflectionFactor`; after
shows `FBX: 3 / 3 карт`, `OK`, zero errors. Same panel size and synthetic input.

- `result.json`: `4a5ee3581e30094897914c655afc6222643f23b6081ae9d07afa1736565eda3f`
- `panel-before.png`: `75999f47df9026a023600d72b402044dc121d22a6b3cd740054baf6d62d2fd5f`
- `panel-after.png`: `070bde59c9e38abf6810723840d97d2dc331e0d78a01ecd3ac2dd44af430f790`

Three harness setup trials preceded the successful run: two exposed the wrong
assumption that the native ReflectionColor fixture would drop its map, and one
found both a property definition and OP occurrence when constructing the variant.
These were harness/input mistakes, not product regressions; no production fix was needed.

## Verdict and handoff

**ADOPT / native smoke PASS:** the installed optional readback/reconnect row works
on the synthetic dropped-channel case and remains a no-op on the intact control.
Mark PR #1792 ready **for independent review**, not merged. Proposed follow-up:
**Independent review #1792 native installed-MZP receipts** — verify this harness,
its FBX mutation, external hashes, production diff and acceptance scope; decide
whether the new authorized synthetic/headless evidence is sufficient to retire
previous customer/live-GUI acceptance items. Do not claim the earlier 23-map
customer example was rerun; it was not. Issue #1760 remains open pending review.
UV, material appearance, undo behavior and complete delivery QA are not certified
by this smoke; no customer acceptance is claimed.
