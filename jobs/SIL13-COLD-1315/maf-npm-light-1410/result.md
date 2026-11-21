# #1410 proof: MAF NPM-light + atlas UV on Silikatny (#1315) MAF copies

Technical proof of the one command, NOT a delivery: the four #1315 v018 isolated MAF copies are geometry-only (one
material each), so the atlas slot of each row is a proof choice (`material-list.json`), not a decided finish.
Sources were read only; their SHA-256 is checked after the run (`sources_unchanged: true`).

Command (Blender 5.1 headless via `TWINQA_BLENDER`):

    uv run dt derive maf-npm-light jobs/SIL13-COLD-1315/maf-npm-light-1410/spec.json --out C:/x/ev_1410/run-v002
    (alias: uv run agr npm-light <spec> --out <new dir>)

Atlas: `uv run python tools/materials/atlas_maf.py jobs/SIL13-COLD-1315/maf-npm-light-1410/material-list.json
--out-png .../sil_maf_atlas_512.png --out-json .../sil_maf_atlas_512.json` (512 x 512, 3 materials).

| Row | Source tris | Ratio | Light | NPM tris | Max dim dev, m | Silhouette IoU (min of 3 views) | UV faces outside slot | Gate |
|---|---|---|---|---|---|---|---|---|
| SIL_MAF_0466 bicycle rack | 900 | 0.8 | decimated | 720 | 0.0004 | 0.972 | 0 | pass |
| SIL_MAF_0625 sand pit | 5 332 | 0.35 | decimated | 1 866 | 0.0024 | 0.991 | 0 | pass |
| SIL_MAF_0698 urn | 158 | 0.5 | refused_floor (≤ 400) | 158 | 0 | 1.000 | 0 | pass |
| SIL_MAF_0423 bench | 3 600 | 0.5 | decimated | 1 800 | 0.0003 | 0.993 | 0 | pass |
| Total | 9 990 | | | 4 544 | | | | exit 0, pass |

First run (`spec-v001.json`, bicycle rack at ratio 0.5): 900 -> 450 tris, silhouette IoU 0.696 < 0.95, exit 3,
status `fail` - the gate refuses a light version that loses the thin tubes; ratio 0.8 passes.

Evidence (outside git): `G:/Мой диск/AGR-evidence/1410-maf-npm-light/` + `SHA256SUMS.txt` (52 files): atlas,
`run-v001/` (gate fail), `run-v002/` (pass: `npm/*.fbx`, `full/*.fbx`, `readback/`, `build-report.json`,
`npm-light-report.json` sha256 `189396875b127bce2e360fc36a5bbe4d28252fcb60b1a437f3af3b112e1b89ed`).
