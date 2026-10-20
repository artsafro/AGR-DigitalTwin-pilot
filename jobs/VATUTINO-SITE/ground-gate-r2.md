# Vatutino Ground — review round 2 gate (PR #308, #295)

Review round 2 (head `912c6d4`, P1): the user's band for locally raised layers is 5–20 mm along the base normal
(Artem, 2026-10-19); `build_ground.py` gated only the lower bound and wrote both masters with exit 0.

## Change

`acceptance_gates` has a new mandatory gate `normal_gap_max_20mm`: it fails when any upper-face centroid
(`normal_gap_centroids_above`) or corner sample (`normal_gap_vertices_above`) is over 20 mm, and lists
`normal_gap_faces_above` and `steep_raise.over_gap_max_vertices`. A failed gate means exit 1 and only
`ground_report.json` is written (no `ground_master_*.json`, so no FBX can be derived).

## Regression table (`tests/test_ground_review_r2.py`)

| # | failing input | expected output |
|---|---------------|-----------------|
| 1 | real `paving_ground_inputs_v4.json --snap 0.003` (sha256 `3b6b433d718c0292…`): 18 corners up to 36.924 mm, 6 centroids up to 26.623 mm; at `912c6d4` exit 0, both masters, 11/11 gates true | exit 1, only `ground_report.json`, failed gates = `[normal_gap_max_20mm]` (measured) |
| 1s | synthetic: lawn plate across a 0.5 m 6:1 bank (\|n_z\| 0.164) between flat terraces | exit 1, no masters, `normal_gap_min_5mm` true, `normal_gap_max_20mm` false with vertices listed |
| c | in-band control: flat 8 x 8 m site; gate fed an in-band report | exit 0, all gates true, both masters written |

At `912c6d4`: 3 failed (test 1s: `assert 0 == 1`, exit 0). Now: 3 passed; with `test_ground_review_r1.py`,
`test_ground_cake.py` and the reviewer probe `review-r2-ground/test_review_band.py`: 49 passed.
Full non-DCC suite via `suite_slot.py`: 6048 passed, 14 skipped.

## Real build after the gate

`uv run python jobs/VATUTINO-SITE/build_ground.py C:/x/t_d94665f2/paving_ground_inputs_v4.json --snap 0.003 --out C:/x/t_d94665f2/ground_v013_gate`
-> exit 1, `ground_report.json` only. Every other gate passes. Over band: faces 22992, 25840, 25852, 26265, 26280,
32790 (centroid max 26.62 mm), 12 vertices (corner max 36.92 mm) where an ~81 deg face (|n_z| 0.149) meets a
flatter face.

## Open: needs a user decision

No continuous Z-only plate gives >= 5 mm on the steep face and <= 20 mm on the flatter face at the same vertex
(gap = offset x n_z of the face). There is no Ground deliverable until the user picks one:
(a) accept these 12 local points as an exception (then the gate reads that exception explicitly);
(b) slit the upper plate at those vertices (new open border, a crack gate exception);
(c) move those vertices in XY (breaks "XY unchanged against the flat Ground").
