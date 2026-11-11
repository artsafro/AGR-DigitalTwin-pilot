# KPP1 R1 #1244 — V004 5-20 mm band pairs listed, xView rerun

Agent: dt-worker (Hermes Kanban card t_dd6f4bf9), 2026-11-11. Base: origin/main 42c3bdb9 (PR #1243 merged).
Inputs (read-only, no model rebuilt, no DCC scene touched; readback = the validator's own headless Blender dump):

- #1230 run `issue-1230-r1-v002`: `G:/Мой диск/AGR-evidence/1230-kpp1-r1/r1-v002/` (`sha256sum -c`: 12/12 OK),
  copied to `C:/x/ev_t_dd6f4bf9/`.
- #1209: `C:/x/kpp1/r1209/out-v003/` (SHA256 of both FBX = `../rerun-1209/evidence-SHA256SUMS.txt`).

## What the band pairs are

`list_band_pairs.py` runs the validator's readback and pair kernel (`twinqa.clearance.co_directional_pairs`,
band edges from the profile, `BAND_EDGE_TOL_M`) and refuses to write when its count differs from the
validator's `in_band`.

| FBX | pairs in 5-20 mm | distance | overlap area | faces | receipt |
|---|---|---|---|---|---|
| #1209 VPM | 14 | 15.0 mm | 5.510 m2 | parapet inner face vs С35 glass (4) + С35 frame vs parapet (10) | `band-pairs-vpm-1209.json` |
| #1209 NPM | 4 | 15.0 mm | 5.055 m2 | parapet inner face vs С35 glass | `band-pairs-npm-1209.json` |
| #1230 VPM | **98** | 15.0 mm | **3.608 m2** | parapet inner face (90 faces) vs С35 glass (2) | `band-pairs-vpm-r1-v002.json` |
| #1230 NPM | **52** | 15.0 mm | **3.868 m2** | parapet inner face (45 faces) vs С35 glass (2) | `band-pairs-npm-r1-v002.json` |

One physical overlap, the same in both builds: the North curtain-wall glass of opening С35 (5.68 x 5.23 m,
plane y = 5.640, z 3.36..8.59, normal -Y) runs up into the parapet (inner face y = 5.625, outer face 5.975,
top 8.65), so its top strip lies inside the parapet solid, 15 mm behind the parapet's inner face. In #1209
that inner face was two large polygons; in #1230 the union build splits it into 90 (VPM) / 45 (NPM) faces
between the roof top 7.909 and 8.59, and the validator counts one pair per face. The overlap area went
**down** (VPM 5.51 -> 3.61 m2, NPM 5.06 -> 3.87 m2) because the overlap now starts at the roof top 7.909
instead of 7.7; the #1209 VPM frame/parapet pairs are gone. The rise 14/4 -> 98/52 is face count, not a new
clash; the 4 mm weld and the 10 mm mullion embedding are not involved.

The 15 mm spacing is inside the regulation's band for co-directional overlapping polygons (5 mm..2 cm, reg
p.8 §3.9, p.29 §3.13; `docs/domain/geometry.md`). V004 clearance fails only below 5 mm (0 pairs in both FBX);
its `review` status comes from the 96,417 / 33,492 pairs above 20 mm (#1209: 48,618 / 17,866), not from the
band.

The hidden glass strip is a model question: the source opening С35 is 3.300..8.650 (to the parapet top),
the parapet (provisional, [D249]) is not cut, so the glazing above the roof is invisible from both sides.

## xView receipt (current FBX, explicit profile)

`dt qa xview` with `--profile VPM` / `--profile NPM` (the #1230 receipts were run without `--profile` and are
labelled NPM; thresholds are identical, 0.002 / 0.005 m):

| FBX | overlapping faces | overlapping vertices | pairs (contact / area / area+contact) | exit | #1209 |
|---|---|---|---|---|---|
| VPM | **112** (all `SM_Kpp_1_Main`) | 0 | 67 / 23 / 76 | 1 | 2853 |
| NPM | **12** (all `SM_Kpp_1_001_Main`) | 0 | 9 / 0 / 0 | 1 | 785 |

Totals equal the #1230 receipts. Not xView-clean ([D152] zero-count rule): `passed=false`, not a delivery pass.

## Commands

```bash
for k in vpm:SM_Kpp_1 npm:0000_Kpp_1_01; do p=${k%%:*}; f=${k#*:}
  uv run python jobs/KPP1/rerun-1244/list_band_pairs.py C:/x/ev_t_dd6f4bf9/$f.fbx $p jobs/KPP1/rerun-1244/band-pairs-$p-r1-v002.json
  uv run python jobs/KPP1/rerun-1244/list_band_pairs.py C:/x/kpp1/r1209/out-v003/$f.fbx $p jobs/KPP1/rerun-1244/band-pairs-$p-1209.json
done
uv run dt qa xview C:/x/ev_t_dd6f4bf9/SM_Kpp_1.fbx --profile VPM --out jobs/KPP1/rerun-1244/xview-vpm-r1-v002.json      # exit 1
uv run dt qa xview C:/x/ev_t_dd6f4bf9/0000_Kpp_1_01.fbx --profile NPM --out jobs/KPP1/rerun-1244/xview-npm-r1-v002.json  # exit 1
uv run pytest -q tests/test_kpp1_band_pairs_1244.py
```

## Open

- User decision (issue acceptance "or the user accepts the listed pairs"): accept the 98 / 52 pairs as listed,
  or change the model (clip the С35 glass at the roof top, or cut С35 through the parapet as drawn to 8.650).
- xView residuals 112 / 12 stay nonzero.
