# #1315 — isolated VPM Bench013 contact snap, v032

**NOT ADOPTED / NOT DELIVERED.** [Issue #1315 comment 6973526978](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6973526978) closes the sub-2 mm question. D346 permits vertical snapping onto actual Ground for this copy; replication requires a passing pilot. This started from the original Bench, not from the rejected v031 geometry. Ground was the upper envelope of 57,226 actual raw VPM v029 triangles. XY was unchanged before FBX serialization.

| Object | Source local / site vertex (0-based) | Before above Ground (mm) | After snap (mm) | Down (mm) |
|---|---:|---:|---:|---:|
| Bench013 / 33FB3BD | 661 / 124982 | 0.501764 | 0 | 0.501764 |
| Bench013 / 33FB3BD | 679 / 125000 | 1.884831 | 0 | 1.884831 |
| Bench013 / 33FB3BD | 1919 / 126240 | 1.843767 | 0 | 1.843767 |

These are all referenced original corners in the open band. The exact-cut ledger accounts for all 5,064 source faces: 4,225 kept, 92 cut, 747 hidden; UV interpolation, material and smoothing lineage verified in the precursor. Blender 5.1.2 standalone FBX, raw decoder and fresh native import agree on 2,194 vertices / 4,364 triangles and face indices; raw/native coordinate difference ≤1.003 µm. Native Z at original snapped XY differs from target by at most 0.002 µm; XY serialization drift is reported separately. The same regulatory BVH route reports **183 → 0 Ground–MAF crossings**.

**Public xView still fails** in precursor, raw, native and direct FBX CLI (exit 1): 0 face overlaps, 59 close vertices / 42 pairs, 0 bow-ties. Of the 42 pairs, 40 are cut-generated at both endpoints, and two involve snapped source corner 125000 (1.585 / 1.592 mm). The shortest pair is 0.114447 mm; its incident source faces 2723/2771/2764 have noncoplanar normals (29.03–43.62°). A blanket planar dissolve or index weld would not preserve these source surfaces. v030's exact cut without a snap was 65/49, v031 was 67/52; none passed. No threshold changed or finding waived. See `audit.json` on Drive for every actual-native witness and source-face identity.

No MAF replication. Current pair remains NPM v026/site-flora-r3 (176,094 render triangles) and VPM v029/site-maples-r3 (298,218), with 37 physical MAF / 38 census, 4,582 plants and 545 VPM UCX. Ground, buried master, census, libraries and all previous full-site QA/skirts/UV/maps/archive/visual/SINTEZ findings are unchanged. See [per-area report](REPORT.md).

[New question 6974008831](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6974008831) asks Artem to choose whether to permit one bounded contact-line reconstruction (including XY, max 2 mm 3D shift inside the 5 mm surface band; no bench relocation or gap), or retain exact shape and the open technical failure. No reconstruction was built. Evidence: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v032/` (`SHA256SUMS.txt`).

New regression matrix: 21 RED on missing hook; 61 focused GREEN including prior D342/D345 cases. 490 affected tests passed. Full suite: deferred to merge batch (rule 68).
