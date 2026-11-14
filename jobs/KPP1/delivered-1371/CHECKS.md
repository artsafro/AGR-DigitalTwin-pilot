# Fresh validator before / after — NOT PASSED

Validator code: origin/main bd842f97; no code changes in this task.
All `--scene` runs used background Blender 5.1.2. Raw complete JSON is in the sealed evidence root.

| Stage | NPM v006 before | NPM v007 diagnostic after | VPM byte-unchanged v007 |
|---|---|---|---|
| V001 | fail | pass | pass |
| V002 | pass | pass | pass |
| V003 | not_run | fail | not_run |
| V004 | review | fail | review |
| V005 | pass | pass | pass |
| V006 | pass | pass | n/a (profile) |
| V007 | n/a (profile) | n/a (profile) | pass |
| V008 | n/a (profile) | n/a (profile) | pass |
| V009 | n/a (profile) | n/a (profile) | pass |
| V010 | n/a (profile) | n/a (profile) | not_run |
| V011 | n/a (profile) | n/a (profile) | fail |
| V012 | pass | fail | review |
| V013 | n/a (profile) | n/a (profile) | not_run |
| V014 | not_run | not_run | n/a (profile) |
| V015 | not_run | not_run | not_run |
| V016 | n/a (profile) | n/a (profile) | not_run |
| V017 | not_run | not_run | not_run |

All three exits: **1**. All `passed=false`. Before Ground missing; after V001 composition passes only.
Static-only after exits 2 and must not be substituted for scene-based validation.

## Key observations / owners

| Check | Before | After | Meaning / owner |
|---|---|---|---|
| NPM V001 count / Ground member | 1 FBX, Ground missing (fail) | 2 FBX incl. renamed unchanged Ground (pass) | Package composition only; worker |
| NPM V003 Ground budget | No Ground | 180934 > 180000 (fail) | Whole-site customer Ground, not KPP crop; Ground author |
| NPM V003 Flora share | No Ground | 110362 > indicative share 70000 (review), total also over | No flora removed; Ground author / Artem |
| NPM V003 skirt | No Ground | Broken face geometry (fail) | Source finding, not repaired; Ground author |
| NPM V004 topology | R1 checks, clearance review | Ground duplicate/intersection counts: Flora 152427, Ground 16745, GroundEl 64561 (fail) | Checker counts, not independently certified defect classes; Ground author |
| NPM V004 MAF normals | No Ground | Flipped 606, inconsistent 8, undetermined 567 (fail) | No source repair; Ground author |
| NPM V004 clearance | R1 review: 20374 pairs, 0 <5mm | R1 unchanged; Ground 557463 pairs, 1498 <5mm, 14947 in band, 541018 >20mm (fail) | Not an accepted D256 exception; Ground author / Artem |
| NPM V012 mesh names | pass | Three project Ground mesh names fail package stem masks | ZIP member rename does not rename objects; worker, pending copy-edit authority |
| V003 master | not_run, missing --master | Still not_run | Delivered triangle exports are not quad masters; model author / Artem |
| VPM V011 FNO / areas | Missing in v006 | Unchanged empty; fail | Proposed values held for user decision; s_podz still unknown |
| Ground / NPM frame | Ground absent | Local Ground vs absolute R1, incompatible | Independently measured census; V001 cannot detect/certify placement; Artem |

## Exact commands

```bash
uv run python tools/qa/validate_package.py "G:/Мой диск/AGR-evidence/1278-kpp1-package/package-v006/0000_Kpp_1.zip" --profile npm --scene --json
uv run python tools/qa/validate_package.py "G:/Мой диск/AGR-evidence/1371-kpp1-delivered/v001/package-v007-diagnostic/0000_Kpp_1.zip" --profile npm --scene --json
uv run python tools/qa/validate_package.py "G:/Мой диск/AGR-evidence/1371-kpp1-delivered/v001/package-v007-diagnostic/SM_Kpp_1.zip" --profile vpm --scene --json
```

No VPM before scene run duplicated: output ZIP is byte-identical to v006, so the one fresh scene run measures both byte-identical inputs. The static VPM report is separate.
Source `assembly.json` pins before/after ZIP hashes. Full observations/thresholds/evidence are retained in raw JSON, not inferred from stage summaries.
