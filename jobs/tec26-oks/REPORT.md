# TEC26 OKS 3 truba — VPM / NPM packages

Issue 560, acceptance items 3 and 4 for this object. The source `truba.max` and
the working copy were not modified (sha256 of both:
`4f2d97744853de1f50347d432da609e08ec7c846cd8ddb3bb62b452440b03556`).

This is not a passed delivery. SINTEZ, GeoJSON and the manual gates are open.

## Mesh

`Tuba` is an Editable Poly, 24 372 vertices, **25 128 quads** (0 other faces),
**50 256 triangles**. The brief's 50 256 faces are that triangle count.
World bbox min `[-51.174, -27.8791, -1.4456]`, max `[5.4444, 27.8791, 69.3844]`
metres. The base stays below ±0.000.

## Finish → material id

`Material #75` is a Multi/Sub with 10 slots. A used slot maps by the diffuse-map
filename (`dark_gray2`, `dark_gray`, `railing`, `gray`, `blu`, `red`). The swatch
is the PNG in `materials.json`. The Standard diffuse tint is recorded and is not
used when a bitmap is assigned. Empty slots with no faces are not given a finish.

| Source id | Faces | Map | Finish | UDIM | Export slot |
|---|---:|---|---|---:|---:|
| 1 | 180 | `gray.png` | Band_RAL7047 | 1003 | 3 |
| 2 | 36 | `blu.png` | Band_RAL5015 | 1002 | 2 |
| 3 | 36 | `red.png` | Paint_Red | 1001 | 1 |
| 5 | 126 | `dark_gray2.png` | Band_RAL7004_Dark | 1005 | 5 |
| 6 | 24462 | `dark_gray.png` | Band_RAL7004 | 1004 | 4 |
| 7 | 288 | `railing_…RGBA_2048.png` | Railing_Steel | 1006 | 6 |

Empty, 0 faces: source ids **4, 8, 9, 10**. Unmapped used slots: none.
Dropped finishes: none. Face ids on the export are the export slots above.
Slot 6's material tint `(205, 210, 215)` is nearer the gray swatch than the
`dark_gray.png` swatch `(173, 173, 173)`; the bitmap filename decides the finish.

## Names

| Role | Name |
|---|---|
| VPM mesh | `SM_Truba_1_Main` |
| NPM mesh | `SM_Truba_1_003_Main` |
| VPM material | `M_Truba_1_Main_1` (sub-materials `M_Truba_1_Main_1_<Finish>`) |
| NPM material | `M_Truba_1_003_Main_1` (sub-materials `M_Truba_1_003_Main_1_<Finish>`) |
| UCX | `UCX_SM_Truba_1_Main_001` … `_060` (renamed `Col_001` … `Col_060`, not rebuilt) |

UCX is inside the VPM FBX (`ucx.md` R05, same file as KPP1) and is also written
as its own FBX. The VPM zip does not contain that second FBX. NPM has no UCX.

## Packages

FBX 7.4 (version 7400), Z-up, quads kept, metres. Geometry was not moved.

| File | Bytes | SHA-256 |
|---|---:|---|
| `C:/x/tec26-oks/package-vpm/SM_Truba_1/SM_Truba_1.fbx` | 1 896 976 | `4d6be473c8746e49d256b3e26ea857e102ab6f6e8f00b696bf8181b122ae9487` |
| `C:/x/tec26-oks/package-vpm/SM_Truba_1.zip` | 1 559 043 | `2fe0dce55046baddce37fd64f9d11bc34a59d5a051ee4c7410266e84a358efa0` |
| `C:/x/tec26-oks/package-vpm/UCX_SM_Truba_1_Main.fbx` | 245 248 | `b3fd42bfc338a1b505bf4917513382e34f7c2e3735268c49cd3ca0e6c11be778` |
| `C:/x/tec26-oks/package-npm/SM_Truba_1_003_Main.fbx` | 1 771 168 | `df1d853978ab999185f64d70e2f4f029d24178347c61a9b19667857c47aa96a0` |
| `C:/x/tec26-oks/package-npm/SM_Truba_1_003_Main.zip` | 1 525 239 | `4a6e3a5db75b13486f1522b79ffeb32e695d1be5c3d46c1f3f3285544871749b` |

The VPM zip is the FBX, 18 PNGs (Diffuse/ERM/Normal × UDIM 1001–1006) and
`manifest.json`. The NPM zip is the FBX (textures embedded), the `_d_/_r_/_m_/_o_`
PNGs and `manifest.json`. No `_n_` map is in the zip. Max also wrote
`SM_Truba_1_003_Main.fbm/` beside the NPM FBX when it embedded the maps.

On re-import, Max names the Multi/Sub container `MultiMat_0`. The sub-material
names above are the strings stored in the FBX.

## Checks

Same numbers on the source mesh, the re-imported VPM mesh and the re-imported
NPM mesh. Receipt: `scripts/qa-receipt.json`.

| Check | Source | VPM | NPM |
|---|---:|---:|---:|
| Vertices | 24 372 | 24 372 | 24 372 |
| Quads / poly faces | 25 128 | 25 128 | 25 128 |
| Triangles | 50 256 | 50 256 | 50 256 |
| Material slots | 10 (4 empty) | 6 | 6 |
| xView overlapping vertices, 0.002 m | 0 | 0 | 0 |
| xView overlapping faces, 0.005 m | 0 | 0 | 0 |
| Edges with disagreeing winding | 0 | 0 | 0 |
| Open edges | 756 | 756 | 756 |
| Non-manifold edges | 0 | 0 | 0 |
| Outside rays, front / back / miss (96) | 90 / 0 / 6 | 90 / 0 / 6 | 90 / 0 / 6 |
| Min z, m | −1.4456 | −1.4456 | −1.4456 |

UCX readback: 60 hulls, names `_001`–`_060`, no material, lowest z **−1.466 m**
in both the VPM file and `UCX_SM_Truba_1_Main.fbx`. `Col_002` stays one polygon
(18 verts); it was renamed, not rebuilt. The 756 open edges are borders of the
lattice, not flipped faces.

## Renders

Scanline, UCX hidden, red bar centred on z = 0 (bbox z −0.04…+0.04). 1280×960.

| File | SHA-256 |
|---|---|
| `C:/x/tec26-oks/renders/truba_shaded.png` | `b367cedfab20eb9c0db2a7655800fc5731255831c8e92330c908584edb73c0c7` |
| `C:/x/tec26-oks/renders/truba_finishes.png` | `84f1539044b1b441298faa86b1a823e53086a127f700fa859d178f263237471d` |
| `C:/x/tec26-oks/renders/truba_finishes_base.png` | `b1877cacc945d4df1b7fa92229ed83613c3cf48b47c8c7968c42e57f5029e5e8` |

The side view shows the base below the zero bar.

## Drive

`G:/Мой диск/AGR-evidence/560-tec26-oks3-truba/` — `package-vpm/`, `package-npm/`,
`renders/`, `SHA256SUMS.txt`.

## Still open

SINTEZ, GeoJSON, district code, MSK-77, manual gates V015–V017.
The Multi/Sub container name does not survive the Max FBX importer.
