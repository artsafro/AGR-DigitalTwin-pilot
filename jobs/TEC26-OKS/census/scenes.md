# Scene census

Read-only native Max 2026.3 / Python 3.11.12 on staged copies. No scene was saved.
All scenes: system metres, scale 1.0, Z up. Live Max 2024 was pinged but untouched.
Native process returned 4294967166 from polyunwrapper startup; wrapper tolerated it. All three scene markers and final completion marker exist; JSON content independently checked.
Source layers are **004–009**, not the proposed 0.0.* spelling. No remapping or rename performed.
Colizii_* / Col_* are **collision candidates**, not certified UCX. None were silently counted into surface budgets.
Areas are snapshot triangle cross-product sums in m². Poly face counts come from an evaluated transient Editable Poly copy. No source node was collapsed/saved.
Surface snapshot/native bbox parity <= 0.01 mm is checked; no second objectTransform is applied. Truba collision candidate Col_002 differs in Z by 0.101089 mm; it is retained as an unresolved diagnostic, not rendered or certified.
UV presence/bounds do not certify valid unwrap/density. Topology health, normals, overlap and export QA are not performed by intake.

| Scene | File version data (raw Max tokens) | Surface nodes / tris | Collision candidates / tris | Other nodes |
|---|---|---:|---:|---:|
| oks | `#(26000, 26000)` | 9 / 18550 | 63 / 1284 | 0 |
| truba | `#(26000, 27000)` | 1 / 50256 | 60 / 1168 | 0 |
| kpp | `#(28000, 28000)` | 4 / 49940 | 33 / 396 | 0 |

## oks

| Handle | Node | Layer | Classification | Tris | Quads / other polygon degrees | Pivot (m) | UV channels |
|---|---|---|---|---:|---|---|---|
| 161 | АС.05 | 005 | surface | 1290 | {'4': 554, '8': 7, '3': 46, '12': 2, '6': 8, '5': 8, '20': 1} | [-6.070732593536377, 4.76837158203125e-07, 0.4465463161468506] | 1:1077 verts |
| 170 | АС.06 | 006 | surface | 5596 | {'4': 2566, '9': 4, '7': 4, '3': 376, '12': 4} | [5.285154819488525, 0.0749286413192749, 0.9664895534515381] | 1:3876 verts |
| 172 | АС.08 | 008 | surface | 348 | {'4': 168, '3': 12} | [33.953392028808594, 0.1133868619799614, 0.25183141231536865] | 1:275 verts |
| 173 | АС.09 | 009 | surface | 682 | {'4': 335, '3': 12} | [40.55158996582031, 0.11338730901479721, 0.2646005153656006] | 1:473 verts |
| 174 | АС.04 | 004 | surface | 5006 | {'4': 2454, '3': 98} | [-10.3193998336792, -2.384185791015625e-07, 1.2390339374542236] | 1:4087 verts |
| 219 | Colizii_001 | 006 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:24 verts |
| 220 | Colizii_002 | 006 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:24 verts |
| 221 | Colizii_003 | 006 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:24 verts |
| 222 | Colizii_004 | 006 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:24 verts |
| 223 | Colizii_005 | 006 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:24 verts |
| 224 | Colizii_006 | 006 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:24 verts |
| 225 | Colizii_007 | 006 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:24 verts |
| 226 | Colizii_008 | 006 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:24 verts |
| 241 | Colizii_009 | 007 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:24 verts |
| 242 | Colizii_010 | 007 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:24 verts |
| 243 | Colizii_011 | 007 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [21.855358123779297, 0.1133875846862793, 0.9664888381958008] | 1:24 verts |
| 244 | Colizii_012 | 007 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:24 verts |
| 245 | Colizii_013 | 007 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:24 verts |
| 246 | Colizii_014 | 007 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [21.855358123779297, 0.1133875846862793, 0.9664888381958008] | 1:24 verts |
| 247 | Colizii_015 | 007 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:24 verts |
| 248 | Colizii_016 | 007 | collision_candidate_noncompliant_name | 44 | {'4': 12, '12': 2} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:24 verts |
| 316 | Colizii_017 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664888381958008] | 1:20 verts |
| 317 | Colizii_018 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664885997772217] | 1:20 verts |
| 318 | Colizii_019 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664888381958008] | 1:20 verts |
| 319 | Colizii_020 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664888381958008] | 1:20 verts |
| 320 | Colizii_021 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664885997772217] | 1:20 verts |
| 321 | Colizii_022 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.11338749527931213, 0.9664885997772217] | 1:20 verts |
| 322 | Colizii_023 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.11338749527931213, 0.9664888381958008] | 1:20 verts |
| 323 | Colizii_024 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664888381958008] | 1:20 verts |
| 324 | Colizii_025 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:20 verts |
| 325 | Colizii_026 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:20 verts |
| 326 | Colizii_027 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.1133875846862793, 0.9664887189865112] | 1:20 verts |
| 327 | Colizii_028 | 007 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [21.855358123779297, 0.11338749527931213, 0.9664887189865112] | 1:20 verts |
| 328 | Colizii_029 | 007 | collision_candidate_noncompliant_name | 20 | {'4': 10} | [21.855358123779297, 0.11338749527931213, 0.9664887189865112] | 1:28 verts |
| 329 | Colizii_030 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 330 | Colizii_031 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 331 | Colizii_032 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 332 | Colizii_033 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 333 | Colizii_034 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 334 | Colizii_035 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.0749286413192749, 0.9664895534515381] | 1:20 verts |
| 335 | Colizii_036 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.0749286413192749, 0.9664895534515381] | 1:20 verts |
| 336 | Colizii_037 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 337 | Colizii_038 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 338 | Colizii_039 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 339 | Colizii_040 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.07492876052856445, 0.9664895534515381] | 1:20 verts |
| 340 | Colizii_041 | 006 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [5.285154819488525, 0.0749286413192749, 0.9664895534515381] | 1:20 verts |
| 341 | Colizii_042 | 006 | collision_candidate_noncompliant_name | 20 | {'4': 10} | [5.285154819488525, 0.0749286413192749, 0.9664895534515381] | 1:28 verts |
| 342 | Colizii_043 | 009 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [40.55158996582031, 0.11338730901479721, 0.2646005153656006] | 1:24 verts |
| 343 | Colizii_044 | 008 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [33.953392028808594, 0.1133868619799614, 0.25183141231536865] | 1:24 verts |
| 344 | Colizii_045 | 005 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-6.070732593536377, 4.76837158203125e-07, 0.4465463161468506] | 1:24 verts |
| 345 | Colizii_046 | 005 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-6.070732593536377, 4.76837158203125e-07, 0.4465463161468506] | 1:24 verts |
| 346 | Colizii_047 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 347 | Colizii_048 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 348 | Colizii_049 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, -4.76837158203125e-07, 1.2390339374542236] | 1:24 verts |
| 349 | Colizii_050 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 350 | Colizii_051 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 351 | Colizii_052 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 352 | Colizii_053 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 353 | Colizii_054 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 354 | Colizii_055 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 355 | Colizii_056 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, 0.0, 1.2390339374542236] | 1:24 verts |
| 356 | Colizii_057 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, -4.76837158203125e-07, 1.2390339374542236] | 1:24 verts |
| 357 | Colizii_058 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, -4.76837158203125e-07, 1.2390339374542236] | 1:24 verts |
| 358 | Colizii_059 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, -2.384185791015625e-07, 1.2390339374542236] | 1:24 verts |
| 359 | Colizii_060 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, -2.384185791015625e-07, 1.2390339374542236] | 1:24 verts |
| 360 | Colizii_061 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, -2.384185791015625e-07, 1.2390339374542236] | 1:24 verts |
| 361 | Colizii_062 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, -2.384185791015625e-07, 1.2390339374542236] | 1:24 verts |
| 362 | Colizii_063 | 004 | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-10.3193998336792, -2.384185791015625e-07, 1.2390339374542236] | 1:24 verts |
| 369 | АС.09_Glass | 009 | surface | 8 | {'4': 4} | [40.55158996582031, 0.11338730901479721, 0.2646005153656006] | 1:16 verts |
| 378 | АС.06_Glass | 006 | surface | 12 | {'4': 6} | [5.285154819488525, 0.0749286413192749, 0.9664895534515381] | 1:24 verts |
| 385 | АС.07 | 007 | surface | 5596 | {'4': 2566, '9': 4, '7': 4, '3': 376, '12': 4} | [21.855358123779297, 0.11338749527931213, 0.9664887189865112] | 1:3876 verts |
| 388 | АС.07_Glass | 007 | surface | 12 | {'4': 6} | [21.855358123779297, 0.11338749527931213, 0.9664887189865112] | 1:24 verts |

### АС.05 (handle 161)
Material: `Material #27`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 127 | 254 | 82.981130 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 2 | 22 | 44 | 56.484399 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 3 | 476 | 990 | 6.699798 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 4 | 1 | 2 | 4.313755 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### АС.06 (handle 170)
Material: `Material #6`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 181 | 362 | 177.127566 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 2 | 671 | 1290 | 83.268399 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 3 | 300 | 444 | 94.417866 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 4 | 772 | 1576 | 4.984936 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 5 | 24 | 48 | 0.697030 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 6 | 200 | 300 | 3.303690 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 7 | 120 | 204 | 5.655707 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 8 | 504 | 1008 | 21.514535 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 9 | 30 | 60 | 7.950371 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 10 | 88 | 176 | 105.289011 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 11 | 64 | 128 | 116.797765 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### АС.08 (handle 172)
Material: `Material #3`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 127 | 254 | 60.509525 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 2 | 15 | 30 | 35.328056 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 3 | 38 | 64 | 1.697453 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### АС.09 (handle 173)
Material: `Material #7`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 188 | 376 | 38.713608 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 2 | 50 | 100 | 18.757031 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 3 | 40 | 80 | 1.901034 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 4 | 39 | 66 | 1.771651 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 5 | 12 | 24 | 0.940521 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 7 | 18 | 36 | 27.345944 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### АС.04 (handle 174)
Material: `Material #35`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 439 | 780 | 179.668028 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 2 | 19 | 38 | 82.702408 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 3 | 2 | 4 | 0.238398 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 4 | 166 | 332 | 2.934883 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 5 | 1926 | 3852 | 24.248557 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### АС.09_Glass (handle 369)
Material: `Material #7`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 6 | 4 | 8 | 3.216858 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### АС.06_Glass (handle 378)
Material: `Material #6`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 12 | 6 | 12 | 32.651300 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### АС.07 (handle 385)
Material: `Material #59`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 181 | 362 | 177.127565 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 2 | 671 | 1290 | 83.268385 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 3 | 300 | 444 | 94.417860 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 4 | 772 | 1576 | 4.984936 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 5 | 24 | 48 | 0.697030 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 6 | 200 | 300 | 3.303691 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 7 | 120 | 204 | 5.655707 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 8 | 504 | 1008 | 21.514531 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 9 | 30 | 60 | 7.950371 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 10 | 88 | 176 | 105.289044 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 11 | 64 | 128 | 116.797767 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### АС.07_Glass (handle 388)
Material: `Material #59`. Full submaterial/map tree and transforms: `oks.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 12 | 6 | 12 | 32.651295 | ? | Material evidence delegated; no RAL inferred from viewport colour |

## truba

| Handle | Node | Layer | Classification | Tris | Quads / other polygon degrees | Pivot (m) | UV channels |
|---|---|---|---|---:|---|---|---|
| 395 | Tuba | 0 | surface | 50256 | {'4': 25128} | [-22.864810943603516, 5.076221866082923e-15, 33.96940994262695] | 1:100152 verts |
| 482 | Col_001 | Colizii | collision_candidate_noncompliant_name | 104 | {'4': 36, '18': 2} | [-22.864810943603516, 5.076221866082923e-15, 33.96940994262695] | 1:144 verts |
| 483 | Col_002 | Colizii | collision_candidate_noncompliant_name | 16 | {'18': 1} | [-22.864810943603516, 5.076221866082923e-15, 33.96940994262695] | 1:18 verts |
| 484 | Col_003 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 485 | Col_004 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 486 | Col_005 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 487 | Col_006 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 488 | Col_007 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 489 | Col_008 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 490 | Col_009 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 491 | Col_010 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 492 | Col_011 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 493 | Col_012 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 494 | Col_013 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 495 | Col_014 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 496 | Col_015 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 497 | Col_016 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 498 | Col_017 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 499 | Col_018 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 500 | Col_019 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 501 | Col_020 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 502 | Col_021 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 503 | Col_022 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 504 | Col_023 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 505 | Col_024 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 506 | Col_025 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 507 | Col_026 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 508 | Col_027 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 509 | Col_028 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 510 | Col_029 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 511 | Col_030 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 512 | Col_031 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 513 | Col_032 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 514 | Col_033 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 515 | Col_034 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 516 | Col_035 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 517 | Col_036 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 518 | Col_037 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 519 | Col_038 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:12 verts |
| 520 | Col_039 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 521 | Col_040 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 522 | Col_041 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 523 | Col_042 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 524 | Col_043 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 525 | Col_044 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 526 | Col_045 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 527 | Col_046 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 528 | Col_047 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 529 | Col_048 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 530 | Col_049 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 531 | Col_050 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 532 | Col_051 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 533 | Col_052 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 534 | Col_053 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 535 | Col_054 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 536 | Col_055 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 537 | Col_056 | Colizii | collision_candidate_noncompliant_name | 12 | {'4': 6} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:16 verts |
| 538 | Col_057 | Colizii | collision_candidate_noncompliant_name | 88 | {'4': 36, '18': 1} | [-22.864810943603516, 5.076221866082923e-15, 33.96940994262695] | 1:144 verts |
| 539 | Col_058 | Colizii | collision_candidate_noncompliant_name | 140 | {'4': 54, '18': 2} | [-22.864810943603516, 5.076221866082923e-15, 33.96940994262695] | 1:216 verts |
| 540 | Col_059 | Colizii | collision_candidate_noncompliant_name | 68 | {'4': 18, '18': 2} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:72 verts |
| 541 | Col_060 | Colizii | collision_candidate_noncompliant_name | 104 | {'4': 36, '18': 2} | [-22.864810943603516, 0.0, 33.96940994262695] | 1:144 verts |

### Tuba (handle 395)
Material: `Material #75`. Full submaterial/map tree and transforms: `truba.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 180 | 360 | 8725.373299 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 2 | 36 | 72 | 1504.130777 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 3 | 36 | 72 | 1099.967879 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 5 | 126 | 252 | 5758.079293 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 6 | 24462 | 48924 | 6957.647758 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 7 | 288 | 576 | 940.248613 | ? | Material evidence delegated; no RAL inferred from viewport colour |

## kpp

| Handle | Node | Layer | Classification | Tris | Quads / other polygon degrees | Pivot (m) | UV channels |
|---|---|---|---|---:|---|---|---|
| 1 | SM_Kpp_1_Main | VPM | surface | 24912 | {'4': 12456} | [0.0, 0.0, 0.0] | 1:39069 verts |
| 2 | SM_Kpp_1_MainGlass | VPM | surface | 76 | {'4': 38} | [0.0, 0.0, 0.0] | 1:152 verts |
| 3 | UCX_SM_Kpp_1_Main_001 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 4 | UCX_SM_Kpp_1_Main_002 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 5 | UCX_SM_Kpp_1_Main_003 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 6 | UCX_SM_Kpp_1_Main_004 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 7 | UCX_SM_Kpp_1_Main_005 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 8 | UCX_SM_Kpp_1_Main_006 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 9 | UCX_SM_Kpp_1_Main_007 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 10 | UCX_SM_Kpp_1_Main_008 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 11 | UCX_SM_Kpp_1_Main_009 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 12 | UCX_SM_Kpp_1_Main_010 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 13 | UCX_SM_Kpp_1_Main_011 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 14 | UCX_SM_Kpp_1_Main_012 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 15 | UCX_SM_Kpp_1_Main_013 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 16 | UCX_SM_Kpp_1_Main_014 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 17 | UCX_SM_Kpp_1_Main_015 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 18 | UCX_SM_Kpp_1_Main_016 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 19 | UCX_SM_Kpp_1_Main_017 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 20 | UCX_SM_Kpp_1_Main_018 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 21 | UCX_SM_Kpp_1_Main_019 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 22 | UCX_SM_Kpp_1_Main_020 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 23 | UCX_SM_Kpp_1_Main_021 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 24 | UCX_SM_Kpp_1_Main_022 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 25 | UCX_SM_Kpp_1_Main_023 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 26 | UCX_SM_Kpp_1_Main_024 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 27 | UCX_SM_Kpp_1_Main_025 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 28 | UCX_SM_Kpp_1_Main_026 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 29 | UCX_SM_Kpp_1_Main_027 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 30 | UCX_SM_Kpp_1_Main_028 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 31 | UCX_SM_Kpp_1_Main_029 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 32 | UCX_SM_Kpp_1_Main_030 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 33 | UCX_SM_Kpp_1_Main_031 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 34 | UCX_SM_Kpp_1_Main_032 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 35 | UCX_SM_Kpp_1_Main_033 | VPM_UCX | UCX_named_not_validated | 12 | {'3': 12} | [0.0, 0.0, 0.0] |  |
| 36 | SM_Kpp_1_001_Main | NPM | surface | 24876 | {'4': 12438} | [40.0, 0.0, 0.0] | 1:38994 verts |
| 37 | SM_Kpp_1_001_MainGlass | NPM | surface | 76 | {'4': 38} | [40.0, 0.0, 0.0] | 1:152 verts |

### SM_Kpp_1_Main (handle 1)
Material: `SM_Kpp_1_Main_UDIM_Blend`. Full submaterial/map tree and transforms: `kpp.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 514 | 1028 | 233.068965 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 2 | 100 | 200 | 103.034383 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 3 | 20 | 40 | 38.111999 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 4 | 6 | 12 | 9.464004 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 5 | 10 | 20 | 17.658995 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 6 | 1220 | 2440 | 165.323031 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 7 | 3430 | 6860 | 345.119181 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 8 | 636 | 1272 | 67.352616 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 9 | 3566 | 7132 | 101.216218 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 10 | 314 | 628 | 30.450008 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 11 | 540 | 1080 | 177.357211 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 12 | 376 | 752 | 333.886016 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 13 | 394 | 788 | 155.543032 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 14 | 298 | 596 | 4.164705 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 15 | 77 | 154 | 1.939600 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 16 | 114 | 228 | 31.832935 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 17 | 37 | 74 | 23.297903 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 18 | 376 | 752 | 40.001444 | ? | Material evidence delegated; no RAL inferred from viewport colour |
| 19 | 428 | 856 | 55.102404 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### SM_Kpp_1_MainGlass (handle 2)
Material: `M_Kpp_1_MainGlass_1`. Full submaterial/map tree and transforms: `kpp.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 38 | 76 | 33.488107 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### SM_Kpp_1_001_Main (handle 36)
Material: `M_Kpp_1_001_Main_1`. Full submaterial/map tree and transforms: `kpp.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 12438 | 24876 | 1901.337170 | ? | Material evidence delegated; no RAL inferred from viewport colour |

### SM_Kpp_1_001_MainGlass (handle 37)
Material: `M_Glass_01`. Full submaterial/map tree and transforms: `kpp.json`.

| Material ID | Poly faces | Triangles | Area m² | Candidate finish | Evidence |
|---:|---:|---:|---:|---|---|
| 1 | 38 | 76 | 33.488110 | ? | Material evidence delegated; no RAL inferred from viewport colour |
