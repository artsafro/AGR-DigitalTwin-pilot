# TEC26-OKS — scene intake

Job: `tec26-oks`; source issue #558; branch `job/tec26-oks-intake`.
Base main at intake: `442f0b695a91f9abc180783c26978fbe85fefcf9`.
Profiles: both NPM and VPM; **intake only, no production outputs**.

Requirement: «Сначала одно здание целиком (mid-poly -> материалы -> VPM + NPM), после моей приёмки остальные параллельно» (Artem, 2026-10-22).
Scope update: operator/user moved per-building drawing/material analysis to #561–566 and truba follow-up to #560; this card publishes native scene census first, KPP recipe and provisional pilot pick, titles only from drawings.

## Completed

- 64 source copies, 144040284 bytes, source/copy SHA-256 checked; local staging `C:/x/tec26-oks/sources-v001/`, manifest `C:/x/tec26-oks/SHA256SUMS.txt`.
- One locked Max batch read three copied scenes with no saves. Native 2026.3 completion markers/JSON verified despite the known startup-script native exit; exact version tokens and warning retained.
- Census published to `C:/x/tec26-oks/census/` before downstream work; classified JSON/MD committed under `census/`. 9 OKS surfaces + 63 collision candidates; truba one surface + 60 candidates; KPP four surfaces + 33 UCX-named meshes.
- Seven two-view material-ID renders and raw buffers/logs stored outside git on Drive with checksums. No binary/LFS evidence committed.
- KPP actual map/header inventory, native preview ID→tile mapping and script recipe recorded. Actual supplied KPP folder has no ERM; truba railing is 4096², not 2048².
- Provisional pilot: AC.08, conditional on #565's evidence; fallback AC.05 if #562 is more complete. No finish assigned by viewport colour, no production authorization inferred.

## Later user decision and corrected visual evidence

Artem: «должна, это опуски геометрии по требованиям — полигоны по периметру должны быть утоплены минимум на метр вниз». Preserve the perimeter drop in NPM and VPM; inherit adjacent wall/plinth finish, no new ID unless source multisub already supplies it. Every perimeter wall must reach ≤ −1.0 m. Source geometry/IDs remain unchanged; node bbox minima are not a per-wall continuity certificate.

Painter diagnostic images are superseded, never Gate evidence. Blender 5.1.2 Workbench rendered 14 depth-correct images into seven paired ID/plain-shaded sheets with red ±0.000 outline and no UCX at `G:/Мой диск/AGR-evidence/tec26-oks/depth-census-v002/`. 23/23 evidence member hashes verified; receipts `census/depth-renders.json`. Native first render failed on factory-empty world None; RED regression captured in d6747fc, fixed by explicitly creating World; 18 focused tests pass. No scene save/export.

The whole-project suite before this visual-only follow-up: **13367 passed / 19 skipped / 179 deselected**, exit 0, via suite_slot (1808.36 s). Follow-up changes are job-only renderer/docs and affected tests, no shared files; affected tests rerun, no second full suite.

## Verification and open gates

Regression: native bitmap-as-Material error captured in RED commit `1b55514`, 1 failed; corrected traversal, 17 focused tests passed via suite_slot. Additional whole-project run and author receipts are recorded in PR/handoff (not delivery QA).
All delivery QA, coordinates/zero reference, topology/normals, UV density, hull validity, material evidence and human visual acceptance remain open. `passed=true` is not asserted. `Col_002` has explicit bbox parity false (0.101089 mm Z discrepancy); it is a collision diagnostic, not a certified hull.

Source geometry untouched. No VPM/NPM models, textures, packages or exports built. Next: collect #561–566/#560 receipts, finalize pilot, then request approval of the exact pilot proposal.

Transcript: Hermes session `local-e92d7962ac47bbe3a7753bf3acc0e564e892854103048b6af44b6213acb099a6` (profile dt-worker-codex; no Claude JSONL transcript).
Report: `census/README.md`; scene tables: `census/scenes.md`; KPP: `census/kpp-recipe.md`; evidence index: `census/evidence.json`.

## Pilot AC08 VPM + NPM (#559, branch `job/tec26-oks-pilot-ac08`)

Gate 1 approved (#565). Scope (Artem 2026-10-22): colour only - geometry, topology, UCX and IDs as in the source; the
one allowed edit is a clean edge-ring cut at a joint where a panel does not fit a tile. v007 (joints every 0.60 m) was
rejected; Artem accepted the v008 panels and asked for a blue wall edging, then made the presentation the authority and
the facade legend binding [D171]. Run `pilot-v010` [D169] [D170] [D171]: rib count per facade counted on presentation
slide 49 (29 / 11 joint lines = 30 / 12 ribs, equal to the DWG sheet `AC08/sheet-facades.json`), evenly and
symmetrically over the panel field (P = 0.19532 / 0.18628 m, tiles 1001 / 1002, Artem's texture = one joint's look,
KPP texel 1000 px/m); frame band (ID1 above ±0.000) blue RAL 5015 with a dark field outline; plinth and door RAL 7004;
legend table in `AC08/MATERIALS.md` checked by `finish_map.validate_legend`; one ring cut at joint 12 (X = 33.3673,
19 quads -> 38). Drive `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v010/` (34/34 hashes). `qa_packages.py`
40/40 (also from the Drive ZIPs and textures); acceptance picture slide | VPM | NPM at 200 px/m with the measured counts
(`compare_facades.py`), all 4 facades equal; SINTEZ as v007. Open for Artem (`AC08/PILOT_REPORT.md`): roof colour (now
blue), outer outline, UCX triangulation.
Scripts: `scripts/run_building.sh`, `render_facades.py`, `compare_facades.py`, `sheet_facades.py`.
