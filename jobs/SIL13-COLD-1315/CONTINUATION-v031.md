# #1315 — one bounded VPM Bench corner pilot, v031

**NOT ADOPTED / NOT DELIVERED.** This is a continuation of the Silikatny run, not a second cold run. [Artem’s answer 6971046788](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6971046788) closes v030’s permission question. D345 records that only original corners in the 2–5 mm band may move, vertically down by at most 2 mm. The hidden-only cut from D342 follows the move. No replication or QA waiver was authorized.

## Every moved vertex

One isolated VPM Bench013 / 33FB3BD (placement row 15). The two listed vertices were the only original vertices in the band. Reference: upper envelope of 57,226 upward Ground triangles from the retained raw VPM v029 export. Indices are zero-based; site indices refer to the source scene. Heights are above actual Ground; dimensions below in mm.

| Object | Local / site vertex | Before | After (precursor) | Downshift (precursor) |
|---|---:|---:|---:|---:|
| Bench013 / 33FB3BD | 677 / 124998 | 3.194513 | 1.204513 | 1.990 |
| Bench013 / 33FB3BD | 678 / 124999 | 3.236745 | 1.246745 | 1.990 |

`source-wide-summary-v031.json` records XY, absolute Z, and exported measurements with the same Ground reference. XY and all other original vertices are unchanged before FBX quantization. Incident triangle interiors interpolate the moved corners; there is no assertion that the whole piecewise-linear displacement field vanishes at the 5 mm isocontour. All other scene objects, placements, profile master, census and libraries are untouched. Cut-generated vertices are separately accounted for by source face and barycentric coordinates; they are not original vertices deliberately moved by D345.

## QA and decision boundary

- Blender 5.1.2, standalone diagnostic FBX, raw decoder and independent fresh native import: **2,200 vertices / 4,373 triangles** in both. Identical face indices; raw/native coordinates differ by up to 1.003 µm. Source-face inventory: 4,225 retained, 95 cut, 744 fully hidden; precursor UVs interpolated from their source face, material and smoothing assignments retained. Visual/material approval is not claimed.
- Same regulatory BVH route with actual Ground: original **183 Ground–MAF crossings → 0** in precursor, raw and native. Public xView **FAIL**: 0 face overlaps, **67 near vertices / 52 pairs**, 0 bow-ties in precursor, both readbacks and direct FBX CLI (exit 1). The earlier hidden-only pilot had 65 / 49; this is not an improvement. No site adoption.
- Source corners **124982 / 125000 / 126240** sit **0.502 / 1.885 / 1.844 mm** above Ground, outside the authorized original-height band. Actual native nearest witness distances: **0.522 / 1.885 / 1.844 mm**. In particular, neither 124982 nor 126240 shares an incident source face with any eligible moved vertex. No choice of lowering only the two authorized corners can change the local faces generating those witnesses. The two moved vertices and all failure identities are retained, not relabelled as passing.
- Current site still **NPM v026/site-flora-r3 (176,094) + VPM v029/site-maples-r3 (298,218)**; 37 physical MAF / 38 census; 4,582 plants; 545 VPM-only UCX. All previous whole-site QA, skirt, UV/maps, archive, visual and SINTEZ findings remain open. See [per-area report](REPORT.md) and the v030 handoff. The main branch’s isolated #1406/#1535/#1410 work does not establish full #1315 acceptance.

The permitted pilot is exhausted. [Question 6971407657](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6971407657) asks about a separate pilot on the three actual sub-2 mm witnesses, not a change to the public 2 mm QA threshold. No expanded pilot was built. Reproduction evidence is sealed under `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v031/`. Full suite: deferred to merge batch (rule 68).
