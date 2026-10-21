# Sliver rule: read-only etalon check (#480)

## Verdict

**Advisory only.** The strict smallest-triangle-altitude rule `< 0.0002 m` rejects already delivered geometry in Vatutino and Skolkovo. B01 has no slivers. The all-three-zero prerequisite is not met; do not promote this rule to a blocking failure. No checker, threshold, decision, mutation fixture or source model was changed. This report implements only the orchestrator's etalon-measurement subtask, not Pi's autoresearch loop.

Authority: Artem's 2026-10-21 approval recorded in the orchestrator note on card `t_0eabd870` / pilot #480. This is a proposed checker calibration rule, not a newly inferred regulatory limit. Delivered/etalon status identifies the comparison input; it does not assert that these files pass all present validators.

## Inputs and census

All five FBX files were found. Both delivered profiles are measured to remove profile ambiguity. The Vatutino VPM input is the **final UCX-integrated** v014, not its intermediate VPM export. B01 is the user's Max etalon, not the engine-generated output or Blender reconstruction. Its hash matches `benchmark/bench-b01-box/etalon.json`. Vatutino hashes match `jobs/VATUTINO-SITE/ground-build-v014.md`. Skolkovo delivery paths come from pilot #353.

| Model | Surface triangles | Surface slivers | UCX triangles | UCX slivers |
|---|---:|---:|---:|---:|
| Vatutino v014 NPM | 46343 | 1 | 0 | 0 |
| Vatutino v014 VPM final | 46343 | 1 | 8788 | 14 |
| Skolkovo delivered NPM | 49657 | 2 | 0 | 0 |
| Skolkovo delivered VPM | 56440 | 3 | 2676 | 0 |
| B01 Max etalon | 150 | 0 | 0 | 0 |

There are **no zero-altitude (degenerate) triangles** in these imports. Surface includes every non-UCX mesh (including VPM MainGlass); UCX is reported separately, never silently discarded. Non-mesh level helpers are not triangles. The separate Skolkovo Light FBX and Ground FBX are not the primary building delivery and are not included. Counts are per file; the identical Vatutino surface sliver is not two independent defects.

| Model | Read-only input path | SHA256 before = after |
|---|---|---|
| Vatutino v014 NPM | `C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx` | `94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef` |
| Vatutino v014 VPM final | `C:/x/t_d94665f2/ground_v014/vpm_ucx/SM_Vatutino_Ground.fbx` | `a5f7d3963ffbe3003f4dd7d706395a84f30a3548c5281f3402b1c1694cfa3b6c` |
| Skolkovo delivered NPM | `C:/x/l4-skolkovo/03_LP/0809_BolshoyBulvar_64_01.fbx` | `1493b06f1bce777c85f36dbed904c16b1fe4d9346ba0532dc92fa0d0649e6d65` |
| Skolkovo delivered VPM | `C:/x/l4-skolkovo/04_HP/okc/SM_BolshoyBulvar_64.fbx` | `fc52d0e231846b5fdce07cba30464da08fe5c3993f60a64df7dd16053ed8f455` |
| B01 Max etalon | `C:/Users/artsafro/AGR-DigitalTwin/data/benchmark/bench-b01-box/etalon.fbx` | `a109aa9a9f25c72e8d4869ee43b0b33aee009f5c248caf62388c4dcb0c7816d9` |

Discovery also checked `jobs/SKOLKOVO-L4` (absent in this checkout), `G:/Мой диск/AGR-evidence/353-skolkovo-l4/` (diagnostic archives found; no substitution for the delivered FBX was needed), and the pilot checkout's `data/benchmark/bench-b01-box/` (absent); the B01 original was found in the source checkout at the exact path above.

## Method and limitations

- Blender **5.1.2**, build `ec6e62d40fa9`, background / factory-startup / disable-autoexec / one thread; no live scene opened, saved, modified or closed. Private card-local temporary directory.
- Each source was copied into its own new `tmp/sliver-inputs-v001/<index>/` directory before FBX import; source, staged and post-run SHA256 agree. The staged directories still contain only their FBX files after both runs. No texture extraction was written beside an original.
- Import `global_scale=1.0`, metric scene, `scale_length=1.0`; the FBX importer applies declared units and object transforms. Coordinates below are **Blender-imported FBX world coordinates in metres**, not geodetic coordinates. B01 measures approximately 10 x 10 x 7.2 m; Vatutino local delivery spans approximately 213.483 x 198.756 m.
- `mesh.calc_loop_triangles()` defines the tessellation. Already triangular delivery polygons are unchanged; B01 quads are tessellated by Blender. Object names are imported labels; ordinal + triangle index identify an occurrence in the deterministic import. Triangle/polygon/vertex indices are zero-based.
- For edges AB, AC, BC, `h_min = ||AB × AC|| / max(||AB||, ||AC||, ||BC||)`. Zero longest edge gives zero altitude. Strict comparison, with **no epsilon or weld**. Computation uses float64 edge-relative coordinates transformed by the world linear matrix, avoiding float32 world-translation cancellation.
- This measures imported geometry, subject to FBX/Blender floating-point quantization; it does not prove topology, UVs, materials or delivery acceptance. Textures are irrelevant to this diagnostic. No geometry healing, modifier application or mesh export.
- Initial and fresh-process confirming runs produced **byte-identical full diagnostic JSON**. All input hashes were checked in each run.

## Ten smallest altitudes per imported model

These tables include ten triangles even when fewer than ten are slivers. The strict threshold is 0.0002 m. Full-precision coordinates, source hashes and the **complete sliver lists**, including all 14 Vatutino UCX occurrences, are in [the machine-readable evidence](sliver-rule-etalon-check.json).

### Vatutino v014 NPM — surface

| Altitude (m) | Object [ordinal] | Triangle / polygon | A; B; C coordinates (m) |
|---:|---|---|---|
| 0.000153281685868 | `SM_Vatutino_Ground` [0] | 13238 / 13238 | (-10.6485004425, -31.3560009003, 150.076309204); (-11.092499733, -30.8159999847, 150.085739136); (-10.7744998932, -31.202999115, 150.078979492) |
| 0.000359599525681 | `SM_Vatutino_Ground` [0] | 13454 / 13454 | (0.259499996901, -16.013999939, 150.449569702); (0.388500005007, -16.1669998169, 150.446670532); (0.262499988079, -16.0170001984, 150.449508667) |
| 0.000359599857021 | `SM_Vatutino_Ground` [0] | 13453 / 13453 | (0.259499996901, -16.013999939, 150.443572998); (0.388500005007, -16.1669998169, 150.440658569); (0.262499988079, -16.0170001984, 150.443511963) |
| 0.00035993188794 | `SM_Vatutino_Ground` [0] | 13452 / 13452 | (0.259499996901, -16.013999939, 150.437561035); (0.388500005007, -16.1669998169, 150.434661865); (0.262499988079, -16.0170001984, 150.437515259) |
| 0.000382756774287 | `SM_Vatutino_Ground` [0] | 17690 / 17690 | (-5.179500103, -38.0880012512, 149.953414917); (-5.19150018692, -38.0730018616, 149.953491211); (-5.19449996948, -38.0699996948, 149.95350647) |
| 0.000383002045418 | `SM_Vatutino_Ground` [0] | 17689 / 17689 | (-5.179500103, -38.0880012512, 149.947418213); (-5.19150018692, -38.0730018616, 149.947494507); (-5.19449996948, -38.0699996948, 149.947494507) |
| 0.000383908888504 | `SM_Vatutino_Ground` [0] | 17478 / 17478 | (-3.28949999809, -40.3860015869, 149.948562622); (-3.27749991417, -40.4010009766, 149.948501587); (-3.2595000267, -40.422000885, 149.948394775) |
| 0.00039893576019 | `SM_Vatutino_Ground` [0] | 32806 / 32806 | (-2.0055000782, -13.4265003204, 150.486328125); (-1.96650004387, -13.4729995728, 150.485443115); (-2.03850007057, -13.3859996796, 150.487091064) |
| 0.000399032242357 | `SM_Vatutino_Ground` [0] | 32807 / 32807 | (-2.0055000782, -13.4265003204, 150.492324829); (-1.96650004387, -13.4729995728, 150.491439819); (-2.03850007057, -13.3859996796, 150.493103027) |
| 0.000399032242357 | `SM_Vatutino_Ground` [0] | 32808 / 32808 | (-2.0055000782, -13.4265003204, 150.498321533); (-1.96650004387, -13.4729995728, 150.497436523); (-2.03850007057, -13.3859996796, 150.499099731) |

### Vatutino v014 VPM final — surface

| Altitude (m) | Object [ordinal] | Triangle / polygon | A; B; C coordinates (m) |
|---:|---|---|---|
| 0.000153281685868 | `SM_Vatutino_Ground` [0] | 13238 / 13238 | (-10.6485004425, -31.3560009003, 150.076309204); (-11.092499733, -30.8159999847, 150.085739136); (-10.7744998932, -31.202999115, 150.078979492) |
| 0.000359599525681 | `SM_Vatutino_Ground` [0] | 13454 / 13454 | (0.259499996901, -16.013999939, 150.449569702); (0.388500005007, -16.1669998169, 150.446670532); (0.262499988079, -16.0170001984, 150.449508667) |
| 0.000359599857021 | `SM_Vatutino_Ground` [0] | 13453 / 13453 | (0.259499996901, -16.013999939, 150.443572998); (0.388500005007, -16.1669998169, 150.440658569); (0.262499988079, -16.0170001984, 150.443511963) |
| 0.00035993188794 | `SM_Vatutino_Ground` [0] | 13452 / 13452 | (0.259499996901, -16.013999939, 150.437561035); (0.388500005007, -16.1669998169, 150.434661865); (0.262499988079, -16.0170001984, 150.437515259) |
| 0.000382756774287 | `SM_Vatutino_Ground` [0] | 17690 / 17690 | (-5.179500103, -38.0880012512, 149.953414917); (-5.19150018692, -38.0730018616, 149.953491211); (-5.19449996948, -38.0699996948, 149.95350647) |
| 0.000383002045418 | `SM_Vatutino_Ground` [0] | 17689 / 17689 | (-5.179500103, -38.0880012512, 149.947418213); (-5.19150018692, -38.0730018616, 149.947494507); (-5.19449996948, -38.0699996948, 149.947494507) |
| 0.000383908888504 | `SM_Vatutino_Ground` [0] | 17478 / 17478 | (-3.28949999809, -40.3860015869, 149.948562622); (-3.27749991417, -40.4010009766, 149.948501587); (-3.2595000267, -40.422000885, 149.948394775) |
| 0.00039893576019 | `SM_Vatutino_Ground` [0] | 32806 / 32806 | (-2.0055000782, -13.4265003204, 150.486328125); (-1.96650004387, -13.4729995728, 150.485443115); (-2.03850007057, -13.3859996796, 150.487091064) |
| 0.000399032242357 | `SM_Vatutino_Ground` [0] | 32807 / 32807 | (-2.0055000782, -13.4265003204, 150.492324829); (-1.96650004387, -13.4729995728, 150.491439819); (-2.03850007057, -13.3859996796, 150.493103027) |
| 0.000399032242357 | `SM_Vatutino_Ground` [0] | 32808 / 32808 | (-2.0055000782, -13.4265003204, 150.498321533); (-1.96650004387, -13.4729995728, 150.497436523); (-2.03850007057, -13.3859996796, 150.499099731) |

### Vatutino v014 VPM final — ucx

| Altitude (m) | Object [ordinal] | Triangle / polygon | A; B; C coordinates (m) |
|---:|---|---|---|
| 0.000114876413013 | `UCX_SM_Vatutino_Ground_535` [535] | 1 / 1 | (-89.997795105, -15.5307769775, 148.309921265); (-89.9867935181, -15.5764780045, 148.309921265); (-89.9866256714, -15.5776786804, 148.309921265) |
| 0.000115207025015 | `UCX_SM_Vatutino_Ground_535` [535] | 0 / 0 | (-89.9866256714, -15.5776786804, 149.328033447); (-89.9867935181, -15.5764780045, 149.328079224); (-89.997795105, -15.5307769775, 149.32951355) |
| 0.000138438090844 | `UCX_SM_Vatutino_Ground_599` [599] | 1 / 1 | (39.8575744629, 23.2296237946, 150.097335815); (40.0997238159, 22.9353847504, 150.097335815); (40.0995445251, 22.9353847504, 150.097335815) |
| 0.000138850425936 | `UCX_SM_Vatutino_Ground_599` [599] | 0 / 0 | (40.0995445251, 22.9353847504, 151.099761963); (40.0997238159, 22.9353847504, 151.099746704); (39.8575744629, 23.2296237946, 151.114990234) |
| 0.000145348889521 | `UCX_SM_Vatutino_Ground_604` [604] | 1 / 1 | (-69.9664230347, 29.2123165131, 149.636856079); (-69.7326431274, 29.3615665436, 149.636856079); (-70.036277771, 29.1674957275, 149.636856079) |
| 0.000145624031148 | `UCX_SM_Vatutino_Ground_604` [604] | 0 / 0 | (-70.036277771, 29.1674957275, 150.648132324); (-69.7326431274, 29.3615665436, 150.654983521); (-69.9664230347, 29.2123165131, 150.649719238) |
| 0.000159984810299 | `UCX_SM_Vatutino_Ground_622` [622] | 1 / 1 | (-96.4033737183, 37.2230453491, 150.806518555); (-96.719833374, 38.2203063965, 150.806518555); (-96.7196655273, 38.2203063965, 150.806518555) |
| 0.000162233234888 | `UCX_SM_Vatutino_Ground_622` [622] | 0 / 0 | (-96.7196655273, 38.2203063965, 152.009963989); (-96.719833374, 38.2203063965, 152.009994507); (-96.4033737183, 37.2230453491, 151.93711853) |
| 0.000165555504293 | `UCX_SM_Vatutino_Ground_643` [643] | 1 / 1 | (-103.205749512, 43.7744369507, 150.783828735); (-103.197402954, 43.7803268433, 150.783828735); (-103.194641113, 43.7820091248, 150.783828735) |
| 0.000165608044729 | `UCX_SM_Vatutino_Ground_643` [643] | 0 / 0 | (-103.194641113, 43.7820091248, 151.804122925); (-103.197402954, 43.7803268433, 151.804016113); (-103.205749512, 43.7744369507, 151.803695679) |

### Skolkovo delivered NPM — surface

| Altitude (m) | Object [ordinal] | Triangle / polygon | A; B; C coordinates (m) |
|---:|---|---|---|
| 7.53353374666e-06 | `SM_BolshoyBulvar_64_001_Main` [0] | 47613 / 47613 | (-10140.2624416, 2463.62274885, 200.198280334); (-10140.8140564, 2462.61044502, 200.197841644); (-10140.8236942, 2462.59275818, 200.197841644) |
| 0.000159798885246 | `SM_BolshoyBulvar_64_001_Main` [0] | 19310 / 19310 | (-10140.2624416, 2463.62274885, 200.198280334); (-10140.1902981, 2463.75514364, 200.197841644); (-10140.2528038, 2463.64043283, 200.198061943) |
| 0.000229017697625 | `SM_BolshoyBulvar_64_001_Main` [0] | 10465 / 10465 | (-10103.728508, 2460.95249939, 200.190031052); (-10103.7811413, 2460.98117828, 200.180366516); (-10103.7399101, 2460.95871067, 200.188169479) |
| 0.000229017697625 | `SM_BolshoyBulvar_64_001_Main` [0] | 10471 / 10471 | (-10103.728508, 2460.95249939, 200.38706398); (-10103.7399101, 2460.95871067, 200.388925552); (-10103.7811413, 2460.98117828, 200.396728516) |
| 0.000229127662222 | `SM_BolshoyBulvar_64_001_Main` [0] | 10598 / 10598 | (-10103.6345177, 2461.1521244, 200.188169479); (-10103.6757488, 2461.17459202, 200.180366516); (-10103.6231155, 2461.14591122, 200.190031052) |
| 0.000229127662222 | `SM_BolshoyBulvar_64_001_Main` [0] | 10603 / 10603 | (-10103.6757488, 2461.17459202, 200.396728516); (-10103.6345177, 2461.1521244, 200.388925552); (-10103.6231155, 2461.14591122, 200.38706398) |
| 0.000229659576994 | `SM_BolshoyBulvar_64_001_Main` [0] | 10609 / 10609 | (-10102.288763, 2463.59464741, 200.190031052); (-10102.3414001, 2463.62333012, 200.180366516); (-10102.300169, 2463.6008625, 200.188169479) |
| 0.000229659576994 | `SM_BolshoyBulvar_64_001_Main` [0] | 10615 / 10615 | (-10102.288763, 2463.59464741, 200.38706398); (-10102.300169, 2463.6008625, 200.388925552); (-10102.3414001, 2463.62333012, 200.396728516) |
| 0.000229667384221 | `SM_BolshoyBulvar_64_001_Main` [0] | 10965 / 10965 | (-10101.795969, 2466.33427978, 200.190031052); (-10101.8486061, 2466.36296201, 200.180366516); (-10101.807375, 2466.34049487, 200.188169479) |
| 0.000229667384221 | `SM_BolshoyBulvar_64_001_Main` [0] | 10971 / 10971 | (-10101.795969, 2466.33427978, 200.38706398); (-10101.807375, 2466.34049487, 200.388925552); (-10101.8486061, 2466.36296201, 200.396728516) |

### Skolkovo delivered VPM — surface

| Altitude (m) | Object [ordinal] | Triangle / polygon | A; B; C coordinates (m) |
|---:|---|---|---|
| 1.29424870415e-06 | `SM_BolshoyBulvar_64_Main` [0] | 39962 / 39962 | (-23.4968166351, -4.30619382858, 13.3981246948); (-25.1457481384, -7.33228969574, 13.3983440399); (-25.1361103058, -7.31460285187, 13.3983440399) |
| 7.53353374666e-06 | `SM_BolshoyBulvar_64_Main` [0] | 39959 / 39959 | (-23.4968166351, -4.30619382858, 13.3981246948); (-24.0484313965, -5.31849765778, 13.3976860046); (-24.0580692291, -5.33618450165, 13.3976860046) |
| 0.000159923197347 | `SM_BolshoyBulvar_64_Main` [0] | 15886 / 15886 | (-23.4246730804, -4.17379903793, 13.3976869583); (-23.4871788025, -4.2885093689, 13.3979063034); (-23.4968166351, -4.30619382858, 13.3981246948) |
| 0.000228940166839 | `SM_BolshoyBulvar_64_Main` [0] | 9961 / 9961 | (13.0371141434, -6.97646331787, 13.389875412); (12.9844808578, -6.94778585434, 13.3802108765); (13.0257120132, -6.97025346756, 13.3880138397) |
| 0.000228940166839 | `SM_BolshoyBulvar_64_Main` [0] | 9967 / 9967 | (13.0371141434, -6.97646331787, 13.5869083405); (13.0257120132, -6.97025346756, 13.5887699127); (12.9844808578, -6.94778585434, 13.596572876) |
| 0.000229127662222 | `SM_BolshoyBulvar_64_Main` [0] | 10094 / 10094 | (13.1311044693, -6.77683830261, 13.3880138397); (13.0898733139, -6.75437068939, 13.3802108765); (13.1425065994, -6.78305149078, 13.389875412) |
| 0.000229127662222 | `SM_BolshoyBulvar_64_Main` [0] | 10099 / 10099 | (13.0898733139, -6.75437068939, 13.596572876); (13.1311044693, -6.77683830261, 13.5887699127); (13.1425065994, -6.78305149078, 13.5869083405) |
| 0.000229631552154 | `SM_BolshoyBulvar_64_Main` [0] | 10105 / 10105 | (14.4768590927, -4.33431529999, 13.389875412); (14.4242219925, -4.30563306808, 13.3802108765); (14.4654531479, -4.3281006813, 13.3880138397) |
| 0.000229631552154 | `SM_BolshoyBulvar_64_Main` [0] | 10111 / 10111 | (14.4768590927, -4.33431529999, 13.5869083405); (14.4654531479, -4.3281006813, 13.5887699127); (14.4242219925, -4.30563306808, 13.596572876) |
| 0.000229667384221 | `SM_BolshoyBulvar_64_Main` [0] | 10461 / 10461 | (14.9696559906, -1.59468412399, 13.389875412); (14.9170188904, -1.56600189209, 13.3802108765); (14.9582500458, -1.58846902847, 13.3880138397) |

### Skolkovo delivered VPM — ucx

| Altitude (m) | Object [ordinal] | Triangle / polygon | A; B; C coordinates (m) |
|---:|---|---|---|
| 0.0161380062503 | `UCX_SM_BolshoyBulvar_64_Main_018` [19] | 0 / 0 | (-22.7385997772, -3.08447194099, 12.3387374878); (-22.7308826447, -3.07029867172, 12.3387374878); (-22.7308826447, -3.07030439377, 0.0817715078592) |
| 0.0161380062503 | `UCX_SM_BolshoyBulvar_64_Main_018` [19] | 6 / 6 | (-22.7308826447, -3.07030439377, 0.0817715078592); (-22.7385997772, -3.08447766304, 0.0817715078592); (-22.7385997772, -3.08447194099, 12.3387374878) |
| 0.0161380155604 | `UCX_SM_BolshoyBulvar_64_Main_018` [19] | 9 / 9 | (-22.7308826447, -3.07029867172, 12.3387374878); (-22.7385997772, -3.08447194099, 12.3387374878); (10.1750202179, -21.0195350647, 12.3387460709) |
| 0.0161380196125 | `UCX_SM_BolshoyBulvar_64_Main_018` [19] | 10 / 10 | (-22.7385997772, -3.08447766304, 0.0817715078592); (-22.7308826447, -3.07030439377, 0.0817715078592); (10.1837100983, -21.0036087036, 0.0817808136344) |
| 0.0181443521789 | `UCX_SM_BolshoyBulvar_64_Main_018` [19] | 2 / 2 | (10.1837062836, -21.0036048889, 12.3387460709); (10.1750202179, -21.0195350647, 12.3387460709); (10.1837100983, -21.0036087036, 0.0817808136344) |
| 0.0181443711278 | `UCX_SM_BolshoyBulvar_64_Main_018` [19] | 4 / 4 | (10.1750202179, -21.0195350647, 12.3387460709); (10.1837062836, -21.0036048889, 12.3387460709); (-22.7308826447, -3.07029867172, 12.3387374878) |
| 0.0181452653402 | `UCX_SM_BolshoyBulvar_64_Main_018` [19] | 11 / 11 | (10.1750202179, -21.0195350647, 12.3387460709); (10.1750221252, -21.0195388794, 0.0817808136344); (10.1837100983, -21.0036087036, 0.0817808136344) |
| 0.0181452787738 | `UCX_SM_BolshoyBulvar_64_Main_018` [19] | 5 / 5 | (10.1837100983, -21.0036087036, 0.0817808136344); (10.1750221252, -21.0195388794, 0.0817808136344); (-22.7385997772, -3.08447766304, 0.0817715078592) |
| 0.038029537015 | `UCX_SM_BolshoyBulvar_64_Main_030` [31] | 2 / 2 | (10.8616132736, -19.7595405579, 12.3387460709); (10.843413353, -19.7929325104, 12.3387460709); (10.8616132736, -19.7595462799, 0.0817802846432) |
| 0.038029537015 | `UCX_SM_BolshoyBulvar_64_Main_030` [31] | 10 / 10 | (10.843413353, -19.7929325104, 12.3387460709); (10.843413353, -19.7929382324, 0.0817802846432); (10.8616132736, -19.7595462799, 0.0817802846432) |

### B01 Max etalon — surface

| Altitude (m) | Object [ordinal] | Triangle / polygon | A; B; C coordinates (m) |
|---:|---|---|---|
| 0.198245583039 | `B01_ETALON` [0] | 137 / 68 | (3.5, 2.49154904897e-07, 5.69999980927); (3.5, 0.200000186568, 4.19999980052); (3.5, 1.83587822467e-07, 4.19999980927) |
| 0.198245583039 | `B01_ETALON` [0] | 140 / 70 | (2, 1.83587822467e-07, 4.19999980927); (2, 0.200000186568, 4.19999980052); (2, 0.200000252135, 5.69999980052) |
| 0.198245583039 | `B01_ETALON` [0] | 141 / 70 | (2, 1.83587822467e-07, 4.19999980927); (2, 0.200000252135, 5.69999980052); (2, 2.49154904897e-07, 5.69999980927) |
| 0.198245583039 | `B01_ETALON` [0] | 124 / 62 | (3.5, 3.93402484159e-08, 0.899999976158); (3.5, 0.20000004232, 0.899999967416); (2, 0.20000004232, 0.899999967416) |
| 0.198245583039 | `B01_ETALON` [0] | 125 / 62 | (3.5, 3.93402484159e-08, 0.899999976158); (2, 0.20000004232, 0.899999967416); (2, 3.93402484159e-08, 0.899999976158) |
| 0.198245583039 | `B01_ETALON` [0] | 128 / 64 | (2, 1.04907336057e-07, 2.40000009537); (2, 0.200000107888, 2.40000008663); (3.5, 0.200000107888, 2.40000008663) |
| 0.198245583039 | `B01_ETALON` [0] | 129 / 64 | (2, 1.04907336057e-07, 2.40000009537); (3.5, 0.200000107888, 2.40000008663); (3.5, 1.04907336057e-07, 2.40000009537) |
| 0.198245583039 | `B01_ETALON` [0] | 134 / 67 | (3.5, 1.83587822467e-07, 4.19999980927); (3.5, 0.200000186568, 4.19999980052); (2, 0.200000186568, 4.19999980052) |
| 0.198245583039 | `B01_ETALON` [0] | 135 / 67 | (3.5, 1.83587822467e-07, 4.19999980927); (2, 0.200000186568, 4.19999980052); (2, 1.83587822467e-07, 4.19999980927) |
| 0.198245583039 | `B01_ETALON` [0] | 136 / 68 | (3.5, 2.49154904897e-07, 5.69999980927); (3.5, 0.200000252135, 5.69999980052); (3.5, 0.200000186568, 4.19999980052) |

## Reproduction and independent controls

Run from this worktree after `uv sync`. Diagnostic scripts are included verbatim below rather than installed as shared tools. Save the first block as `tmp/sliver_etalon_measure.py` and the second as `tmp/probe-sliver.py`. Create `tmp/sliver-manifest.json` as a list of `{name, source, staged, sha256}` records from the input table, after copying each source into a distinct new card-local directory. The diagnostic refuses an existing output file and verifies all manifest hashes.

```bash
TEMP="$PWD/tmp/blender-temp" TMP="$PWD/tmp/blender-temp" TMPDIR="$PWD/tmp/blender-temp" \
  "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" \
  --background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1 \
  --python tmp/sliver_etalon_measure.py -- tmp/sliver-manifest.json tmp/sliver-results-v001.json
uv run python tmp/probe-sliver.py
```

Both Blender runs exited 0 and printed `SLIVER_MEASUREMENT_COMPLETE`. Independent controls: **1124 passed / 0 failed** (seed 480): 30 altitude/boundary/permutation cases, 1000 seeded random triangles versus the independent point-to-line projection formula, 3 malformed/nonfinite cases, and 91 Decimal recomputations of worst/sliver records. Maximum Decimal difference from the reported altitude: **5.551115123125783e-17 m**. Exactly 0.0002 m is not a sliver; adjacent `nextafter` controls classify on the appropriate side. The Decimal recomputation uses the reported world coordinates, independently checking the relative-coordinate transform path. Duplicated records in worst + all_slivers are intentionally checked again, not counted as distinct source defects.

No production code is changed, so a before-fix failing checker regression is not applicable: this is an empirical measurement, not a checker fix. The negative finding is retained, not repaired or tuned away. The four embedded analytic controls also run before each FBX import batch.

### Measurement script

```python
"""Read-only, card-local etalon diagnostic; not a delivery validator."""
import bpy
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def altitudes(points):
    if points.shape[1:] != (3, 3) or not np.isfinite(points).all():
        raise ValueError('invalid triangle coordinates')
    ab = points[:, 1] - points[:, 0]
    ac = points[:, 2] - points[:, 0]
    bc = points[:, 2] - points[:, 1]
    longest = np.maximum.reduce([np.linalg.norm(ab, axis=1), np.linalg.norm(ac, axis=1), np.linalg.norm(bc, axis=1)])
    cross = np.linalg.norm(np.cross(ab, ac), axis=1)
    return np.divide(cross, longest, out=np.zeros_like(cross), where=longest > 0)


manifest_path, out_path = map(Path, sys.argv[sys.argv.index('--') + 1:])
if out_path.exists():
    raise ValueError('refusing existing output')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
threshold = 0.0002
# Synthetic analytic controls, independent of any checker.
for height in [0.0, threshold / 2, threshold, threshold * 2]:
    points = np.array([[[0., 0., 0.], [1., 0., 0.], [0.5, height, 0.]]])
    measured = altitudes(points)[0]
    assert measured == height
    assert bool(measured < threshold) == (height < threshold)
results = []
for item in manifest:
    source, staged = Path(item['source']), Path(item['staged'])
    before = digest(source)
    assert before == digest(staged) == item['sha256']
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.import_scene.fbx(filepath=str(staged.resolve()), global_scale=1.0, use_anim=False)
    stats = {kind: {'triangles': 0, 'slivers': 0, 'degenerate': 0, 'objects': 0, 'worst': [], 'all_slivers': []} for kind in ['surface', 'ucx']}
    inventory = []
    for ordinal, obj in enumerate(sorted(bpy.context.scene.objects, key=lambda x: x.name)):
        if obj.type != 'MESH':
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()
        if not mesh.loop_triangles:
            raise ValueError('empty mesh: ' + obj.name)
        vertices = np.array([list(v.co) for v in mesh.vertices], dtype=np.float64)
        indices = np.array([list(t.vertices) for t in mesh.loop_triangles], dtype=np.int64)
        matrix = np.array([list(row) for row in obj.matrix_world], dtype=np.float64)
        if not np.isfinite(matrix).all():
            raise ValueError('nonfinite transform')
        # Transform edge-relative coordinates first: do not round translated world vertices to float32.
        local = vertices[indices]
        relative = (local - local[:, :1, :]) @ matrix[:3, :3].T
        heights = altitudes(relative)
        world = vertices @ matrix[:3, :3].T + matrix[:3, 3]
        kind = 'ucx' if obj.name.upper().startswith('UCX_') else 'surface'
        stat = stats[kind]
        stat['triangles'] += len(indices)
        stat['objects'] += 1
        stat['slivers'] += int(np.count_nonzero(heights < threshold))
        stat['degenerate'] += int(np.count_nonzero(heights == 0))
        inventory.append({'ordinal': ordinal, 'object': obj.name, 'kind': kind, 'triangles': len(indices), 'bbox_m': [world.min(axis=0).tolist(), world.max(axis=0).tolist()], 'matrix_world': matrix.tolist()})
        selected = sorted(set(np.argsort(heights, kind='stable')[:10].tolist() + np.flatnonzero(heights < threshold).tolist()))
        records = [{'altitude_m': float(heights[i]), 'object': obj.name, 'ordinal': ordinal, 'triangle_index': i, 'polygon_index': mesh.loop_triangles[i].polygon_index, 'vertex_indices': indices[i].tolist(), 'coordinates_m': world[indices[i]].tolist()} for i in selected]
        stat['worst'] = sorted(stat['worst'] + records, key=lambda r: (r['altitude_m'], r['ordinal'], r['triangle_index']))[:10]
        stat['all_slivers'].extend(r for r in records if r['altitude_m'] < threshold)
    assert stats['surface']['triangles'] > 0
    assert digest(source) == digest(staged) == before
    result = {**item, 'sha256_after': before, 'stats': stats, 'inventory': inventory}
    results.append(result)
    print('ETALON', item['name'], {k: {q: v[q] for q in ['objects', 'triangles', 'slivers', 'degenerate']} for k, v in stats.items()}, flush=True)
with out_path.open('x', encoding='utf-8') as f:
    json.dump({'blender': bpy.app.version_string, 'threshold_m': threshold, 'analytic_controls': 4, 'results': results}, f, indent=2, allow_nan=False)
print('SLIVER_MEASUREMENT_COMPLETE', flush=True)
```

### Independent probe

```python
import ast
import decimal
import itertools
import json
import math
from pathlib import Path
import numpy as np

module = ast.parse(Path('tmp/sliver_etalon_measure.py').read_text())
fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'altitudes')
ns = {'np': np}
exec(compile(ast.Module(body=[fn], type_ignores=[]), '<measurement function>', 'exec'), ns)
altitudes = ns['altitudes']
count = 0
for h in [0., math.nextafter(.0002, 0.), .0002, math.nextafter(.0002, math.inf), .1]:
    for perm in itertools.permutations(range(3)):
        tri = np.array([[0., 0., 0.], [1., 0., 0.], [.5, h, 0.]])[list(perm)]
        value = altitudes(tri[None])[0]
        assert value == h
        assert (value < .0002) == (h < .0002)
        count += 1
rng = np.random.default_rng(480)
for _ in range(1000):
    tri = rng.uniform(-10, 10, (3, 3))
    heights = []
    for a, b, c in [(0,1,2),(1,2,0),(2,0,1)]:
        edge, offset = tri[b]-tri[a], tri[c]-tri[a]
        projection = offset - edge * np.dot(edge, offset) / np.dot(edge, edge)
        heights.append(float(np.linalg.norm(projection)))
    assert math.isclose(altitudes(tri[None])[0], min(heights), rel_tol=1e-12, abs_tol=1e-12)
    count += 1
for invalid in [np.array([[[0.,0.,0.],[1.,0.,0.],[0.,math.nan,0.]]]), np.full((1,3,3), math.inf), np.zeros((1,2,3))]:
    try:
        altitudes(invalid)
    except ValueError:
        count += 1
    else:
        raise AssertionError('invalid input accepted')
# Independent Decimal world-coordinate calculation on every listed worst/sliver triangle.
decimal.getcontext().prec = 60
D = decimal.Decimal
raw = json.loads(Path('tmp/sliver-results-v001.json').read_text())
records = []
for model in raw['results']:
    for stats in model['stats'].values():
        records.extend(stats['worst'] + stats['all_slivers'])
max_difference = 0.
for row in records:
    a,b,c = [[D.from_float(v) for v in p] for p in row['coordinates_m']]
    edges = [[q-p for p,q in zip(x,y)] for x,y in [(a,b),(a,c),(b,c)]]
    u,v,_ = edges
    cross = [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
    area2 = sum(x*x for x in cross).sqrt()
    longest = max(sum(x*x for x in e).sqrt() for e in edges)
    height = float(area2/longest) if longest else 0.
    difference = abs(height-row['altitude_m'])
    max_difference = max(max_difference, difference)
    assert difference < 1e-10
    assert (height < .0002) == (row['altitude_m'] < .0002)
    count += 1
print(json.dumps({'passed':count,'failed':0,'decimal_records':len(records),'max_decimal_difference_m':max_difference,'seed':480}))
```
