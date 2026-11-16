# Headless window generator — #1405

Program choice: CPython, because `windowgen_core` is stdlib-only and the Max button
already writes its OBJ without a scene mutation. No Max/Blender/Revit session was opened.
This is a generator/diagnostic command, **not building assembly or delivery acceptance**.
The CLI writes local type OBJ meshes and an opening-to-type plan carrying explicit inset
instructions; a DCC consumer still places those types in the building.

## Commands

```bash
uv run agr window-generate --ids KPP1-W01 KPP1-W02 KPP1-W03 --out NEW_DIRECTORY
uv run agr window-generate --request request.json --out NEW_DIRECTORY
uv run agr window-generate --kpp1-source SOURCE_DIRECTORY --kpp1-census CENSUS_DIRECTORY --inset-m 0.2 --out NEW_DIRECTORY
```

Synthetic request example (metres, not a KPP1 measurement):

```json
{"schema":"window-request/1","openings":[{"id":"example","w":1.18,"h":1.8,"inset_m":0.2}]}
```

Library-first size matching uses `winplace_core.match`. Equal best types require an
explicit `type`; unknown or quarantined IDs are errors. If no type fits, the opening
must supply `generator`: a complete source-derived window-types record with a new ID,
explicit pane rectangles and optional source `frame_profile_m`. No one-pane shape,
role, material or source profile is invented. Unknown generator keys fail by name.
Generator records are not added to the library and still need the D116 review gate.
D322 seating/cover comes from the same `build_type` as the Max button.

`inset_m` is required and positive for every opening; it is a placement instruction,
not inferred from a glass bounding box. KPP1's explicit 0.2 m invocation demonstrates
D037's half-default-depth plan only; it does not approve or change KPP1 seating.

Outputs: the Max-compatible `quality.json`, `sheet.png`, `<type>.obj`, `meshes.json`,
plus `run.json` (input SHA-256s, opening plans, ownership, per-reason drops and status).
Exit 0 means a complete diagnostic pass; 1 means a written failing diagnostic;
2 means refusal. An existing directory/receipt is never refreshed or reused as success.
Publication uses private staging and atomic no-replace **Windows** directory rename;
other OSes explicitly refuse publication. No fixed `.partial` name is used.
Input snapshots are rechecked before publication; this is not a filesystem lock or a
claim to detect a change restored between snapshots.

## Current retained KPP1 inputs, read-only

Root: `C:/Users/artsafro/AGR-DigitalTwin/.claude/worktrees/laughing-hawking-e62961/jobs/KPP1/outputs/`.
These are retained source dumps, not a fresh Revit export.

| Input | SHA-256 |
|---|---|
| `source-v001/curtain.export.json` | `65b1f5a17b646a1ea040219e085af3b475e062b8b340dd8dc24f2ade76400d41` |
| `census-v001/curtain.objects.json` | `c486ee9f10963a590409affe440a4ee9c8906cbcb708765a3ac005e12425d0e3` |
| `census-v001/openings.objects.json` | `5cdf48050ca844cff05c2af8ede7ad11c6b9107d912745f9fc4900b430293af8` |

Measured command outcome: **20 bays** -> 18 KPP1-W01, 1 KPP1-W02, 1 KPP1-W03.
All **24 exterior window/glass objects** have exactly one 3D bay owner, including
depth containment (the existing KPP1 12 mm allowance; equality is refused).
Zero/many matches are named failing drops, never first-match assignments.
All **406 raw objects** are accounted for: **162 represented + 244 dropped**.
Of the drops, 124 are explicitly outside the exterior-facade stage; **120 remain
unexplained** (unknown-family/in-surround/outside-bay records). Therefore **exit 1**
and `status: fail`, despite all three type meshes building successfully. This is
intentional fail-closed input reporting, not a generator failure and not a repair
of KPP1. Per-object identities and exact reason counts are in the sealed `run.json`.

## Historical opening mismatch, not today's whole-model verdict

`jobs/KPP1/spec-compare-v002.md` (SHA-256
`831181e3e55ba2cf62345cc9a7ca9c155c5c4685bc4e7f4e5a29ce2083ddc573`)
is embedded verbatim as `measured_input`, marked historical:
L0 Revit/mesh 21/21, L1 11/12, zero pairs at 0.05 m; at 0.30 m, 21 L0 and 10 L1
pairs. Revit used frame boxes (1.08 x 1.70 m), mesh glass (0.94 x 1.56 m),
70 mm per side; depth definitions differed by up to 0.27 m.
Later `spec-compare-v003.md` records a match after the definition change. The v002
measurement is not silently promoted to a current failure or repaired here.
No accepted KPP1 geometry, output package or published library asset is changed.

## Verification boundary

The test invokes `windowgen_max.win_generate` preview/apply with only its unused
selection runtime replaced, then compares every emitted Max-adapter file byte-for-byte
with the agent bundle: quality, PNG, three OBJ files and mesh inventory. This exercises
the actual button adapter's file path, **not a physical UI click or native DCC readback**.
A fresh-process `agr` probe independently checks all three OBJ files.
`duplicate_guard` now rejects new window builder/ownership implementations under
jobs/tools/src. There were no window-generator allowlist rows to remove; unrelated
historical job duties remain untouched.

Evidence: `G:/Мой диск/AGR-evidence/1405-window-command/t_fcec63fc-v001/` (first run)
and `t_fcec63fc-v002/` (code-provenance run), then `t_fcec63fc-v003/` (validated
fallback), and `t_fcec63fc-v004/` (final all-object finite-bound validation and
reader provenance), each with `SHA256SUMS.txt`.
Only small text receipts belong in git; generated PNG/OBJ/JSON bundles stay on Drive.
