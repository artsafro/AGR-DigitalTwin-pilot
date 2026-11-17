# General window seating — #1449

Authority: Artem's general-standard update [D322], not a per-site alternative to `win.generate`.
The window-agent brief is [library/windows/README.md](../../library/windows/README.md#window-agent-brief-new-builds-only-d322).

## Real 4bk-k3 comparison

Evidence root: `G:/Мой диск/AGR-evidence/1449-window-seating/t_98eaf13e-v001/`.
`comparison.png` shows measured Artem B v007 geometry on the left of each pair and
new general-builder output on the right. `comparison.blend` is a **diagnostic** scene,
not a delivery: flat diagnostic colours, labels, cameras and edge overlays are intentional.
No source, handed-over file, library binary or external release catalogue was edited.

Native source dumps under
`C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/build/gf_parts/_review/max/artem_v007_analysis/`:

| Source | SHA-256 |
|---|---|
| `STY_RoofB_RailGlass_dump.txt` | `9b992cc44cf0fbe3f0cfc7eba24b8c92c602b063ea272a6cc8c63377dd6d640e` |
| `STY_BodyL1_Shell_dump.txt` | `b842750dfefcf85cf6e2cec4fed40cc07e09e05c4355bdebb953c44397fdcc9c` |

`tests/fixtures/window_seating_1449.json` stores the measured vertices, zero-based native
face IDs, explicit material-role selection, local axes/translation and source hashes.
It is real source-derived text, not a synthetic object. Dimensions are measured from the
etalon; no Revit type observation is invented. The glass witness is bay face 148,
clipped at its transom top (1020 x 2335 mm); the grille witness is body face 1320
(1520 x 2870 mm opening). Both use measured 60 mm side/bottom frame faces, 20 mm depth;
the glass bay's top transom is 50 mm. Fallback family dimensions are tested separately.

| Comparison, millimetres | Glass bay | Grille opening | Limit |
|---|---:|---:|---:|
| Panel local bbox maximum coordinate residual | 0.0161 | 0.0644 | 2 |
| Shared frame vertex-to-rectangle, two directions, after native readback | 0.0446 | 0.0684 | 2 |
| Effective panel overlap under light edge | 17 | 17 | 15-20 |
| Panel depth behind frame face | 10 | 10 | real frame mid-depth |

The +20 mm enlargement in `ANALYSIS.md:15-16` is relative to the previous panel, which
had a 3 mm gap: effective cover in the native dump is 17 mm, not 20 mm. The general
builder defaults to 20 mm cover; the source comparison explicitly requests 17 mm.

Comparison covers glass/grille bounds and shared front/inner frame surfaces, **not**
whole-scene topology equivalence. Source frames were open shells; the new reusable frame
has additional outer/back closure. The grille source's frame-ID interior extension
(faces 826/828/830/832/834) is excluded from frame comparison and is not generated behind
our new grille. It remains untouched in the original. No claim of deleting an existing
capsule or fixing other source defects is made.

## Capsule and regression evidence

A separately requested visible interior is a five-quad inward-facing open-front box;
source seat and room depth must be explicit. Opening-relative margins are +44 mm per
side and +130 mm head/sill, from A's `artem_final_analysis/ANALYSIS.md:40,70`.
It is not compared to B's unchanged interiors. Pytest verifies its bounds, independent
part/material, no new frame faces at all, and minimum capsule edge >=20 mm.
Grille/interior requests (including mixed glass/grille openings) fail rather than
silently building or deleting a capsule. Main glass is a separate part/object.

Tests-first commit `2139ff5f` failed on the original builder: every overlap was 0 mm.
The one-opening negative reproduces the earlier no-cover construction; the fixed
builder passes. Generated probes cover 81 dimension/profile combinations, plus
empty/duplicate/degenerate fields, unknown roles/keys, partial profiles, NaN/inf,
rejected capsule seat/depth boundaries and overlap-range boundaries.

Native Blender **5.1.2**, metres, fresh factory document, no live user scene:
- `measurement.json`: panel dimensions/residuals;
- `readback-final.json`: reopens the saved scene against the final generator hash, checks 66 rebuilt quads, 0 nonquads,
  material separation, diagnostic UVs, identity rotation/scale and expected display translations;
- preserved scripts/logs and `SHA256SUMS.txt`: reproduce extraction, rebuild/capture and readback.
- First readback failed its boundary-selection predicate after float32 storage; the second
  uses a 0.001 mm coordinate-selection budget, keeping the 2 mm comparison limit unchanged.

Visual capture was inspected for readable labels, complete objects and source/rebuild parity.
Artem's visual approval remains pending; no delivery certificate or production export is claimed.

## Frozen library release provenance

The offered v003 library stays historical. Its repository catalogue's input pointer now
names `library/windows/sources/standard-d204-v003.json`, an exact byte snapshot of the
old standard (SHA-256 `36b8825c902d37a9214d3d4e660ca54743abdf9572febe6ade62cf57e0ee3427`).
No asset/hash/status row is changed or promoted. Active `standard.json` describes new
builds; publishing their binaries requires a new external version and readback, never
relabeling the old release with a new input hash.
The catalogue's old generator input is likewise pinned to exact non-executable text
`sources/windowgen-core-d204-v003.txt` (SHA-256
`0cfa7fb9ec6c2349eef0a85cf3723ce75f38f83544d5bc0bfc46130557fc8bf0`), not the changed active code.
The pre-existing ELV-21 family normalization collapses one opaque field; this geometry
is not repaired here, but `dropped_fields` now names its index/rectangle/reason instead
of silently skipping it. New degenerate glass/grille fields are errors.

Affected tests: 585 passed, 39 skipped (not counted as passes), 0 failed; exact selection
and output are retained in `affected-final2.txt` in the evidence root and in the PR.

Full suite: deferred to merge batch (rule 68).
