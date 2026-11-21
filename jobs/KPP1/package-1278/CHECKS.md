# KPP1 #1278 — complete finding table

Fresh ZIP readback via `validate_package --scene`; before = package-v001, after = package-v003.
Raw JSON receipts are adjacent. Stage passes certify implemented subsets only.

| Profile / stage | Before -> after | Check | Observed after | Expected / limit | Finding status |
|---|---|---|---|---|---|
| npm / V001 | fail -> fail | archive size | 619212 B <= 1024 MiB | <= 1073741824 B | pass |
| npm / V001 | fail -> fail | FBX count | 1 | 2..21 (1 Ground + 1..20 OKS) | fail |
| npm / V001 | fail -> fail | Ground FBX | ['0000_Kpp_1_01.fbx'] | 0000_Kpp_1_Ground.fbx | fail |
| npm / V002 | pass -> pass | FBX header | 0000_Kpp_1_01.fbx: binary FBX version 7400 | binary FBX 7400 (7.4/2014) | pass |
| npm / V002 | pass -> pass | system units | 0000_Kpp_1_01.fbx: 1 unit = 100 cm (UnitScaleFactor 100, OriginalUnitScaleFactor 100.0) | 1 unit = 1 m (UnitScaleFactor 100) | pass |
| npm / V002 | pass -> pass | scale 1:1 | 0000_Kpp_1_01.fbx: scale 1 on every mesh | local and effective (inherited) scale 1 on every mesh (1:1) | pass |
| npm / V003 | not_run -> not_run | triangulated | 0000_Kpp_1_01.fbx: all triangles | triangulated on export | pass |
| npm / V003 | not_run -> not_run | triangle count | 0000_Kpp_1_01.fbx: 18836 | <= 150000 | pass |
| npm / V003 | not_run -> not_run | master quads | quad work FBX not given (--master) | quad master; VPM faces <= 4 m [D021] | not_run |
| npm / V004 | review -> review | applied transforms | 0000_Kpp_1_01.fbx: rotation 0, scale 1 | rotation 0, scale 1 after reset | pass |
| npm / V004 | review -> review | topology defects | 0000_Kpp_1_01.fbx: max 0 duplicates/self-intersections, no isolated or zero-length elements | <= 100 duplicates/self-intersections at 0.002 m per mesh; 0 isolated vertices/edges/polygons; 0 zero-length edges | pass |
| npm / V004 | review -> review | co-directional clearance | 0000_Kpp_1_01.fbx: 20374 co-directional overlapping pairs: 0 < 5 mm, 108 in band, 20266 > 20 mm; distance mm min/median/max 13.695/6870.2359/31170.3557; histogram {'0-1': 0, '1-5': 0, '5-10': 0, '10-20': 108, '20-50': 14, '50-100': 972, '100-1000': 987, '1000+': 18293}; worst: ['SM_Kpp_1_001_Main#7465/SM_Kpp_1_001_Main#16670 d=31170.4 mm', 'SM_Kpp_1_001_Main#7465/SM_Kpp_1_001_Main#16669 d=31170.3 mm', 'SM_Kpp_1_001_Main#7462/SM_Kpp_1_001_Main#10604 d=30670.4 mm', 'SM_Kpp_1_001_Main#7447/SM_Kpp_1_001_Main#10604 d=30420.5 mm', 'SM_Kpp_1_001_Main#7482/SM_Kpp_1_001_Main#11826 d=29670.2 mm'] | co-directional overlapping faces 5-20 mm apart (pairs beyond 20 mm: review) | review |
| npm / V005 | pass -> pass | color attributes | 0000_Kpp_1_01.fbx: 0 color attributes on 2 mesh(es) | no color attributes (reg 4.1.1: recommended to remove) | pass |
| npm / V006 | pass -> pass | embedded textures | 0000_Kpp_1_01.fbx: all embedded | PNG embedded in FBX | pass |
| npm / V012 | pass -> pass | FBX names | all match | 0000_Kpp_1_01..20.fbx and 0000_Kpp_1_Ground.fbx | pass |
| npm / V012 | pass -> pass | mesh names | 0000_Kpp_1_01.fbx: 2 name(s) follow the grammar | SM_{Address}_{001..020}_Main\|MainGlass; <= 254 characters, A-Z a-z 0-9 _ | pass |
| npm / V014 | not_run -> not_run | геометрия в московских проектных координатах и высотах; углы соответствуют плану | not measured | геометрия в московских проектных координатах и высотах; углы соответствуют плану | not_run |
| npm / V015 | not_run -> not_run | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | not measured | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | not_run |
| npm / V017 | not_run -> not_run | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | not measured | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | not_run |
| vpm / V001 | pass -> pass | archive size | 995768 B <= 500 MiB | <= 524288000 B | pass |
| vpm / V002 | pass -> pass | FBX header | SM_Kpp_1.fbx: binary FBX version 7400 | binary FBX 7400 (7.4/2014) | pass |
| vpm / V002 | pass -> pass | system units | SM_Kpp_1.fbx: 1 unit = 100 cm (UnitScaleFactor 100, OriginalUnitScaleFactor 100.0) | 1 unit = 1 m (UnitScaleFactor 100) | pass |
| vpm / V002 | pass -> pass | scale 1:1 | SM_Kpp_1.fbx: scale 1 on every mesh | local and effective (inherited) scale 1 on every mesh (1:1) | pass |
| vpm / V003 | not_run -> not_run | triangulated | SM_Kpp_1.fbx: all triangles | triangulated on export | pass |
| vpm / V003 | not_run -> not_run | triangle count | SM_Kpp_1.fbx: 30666 | <= 150000 project target (reuse as NPM; else windows as atlas planes), 1000000 regulation limit | pass |
| vpm / V003 | not_run -> not_run | master quads | quad work FBX not given (--master) | quad master; VPM faces <= 4 m [D021] | not_run |
| vpm / V004 | review -> review | applied transforms | SM_Kpp_1.fbx: rotation 0, scale 1 | rotation 0, scale 1 after reset | pass |
| vpm / V004 | review -> review | topology defects | SM_Kpp_1.fbx: max 0 duplicates/self-intersections, no isolated or zero-length elements | <= 100 duplicates/self-intersections at 0.002 m per mesh; 0 isolated vertices/edges/polygons; 0 zero-length edges | pass |
| vpm / V004 | review -> review | co-directional clearance | SM_Kpp_1.fbx: 108100 co-directional overlapping pairs: 0 < 5 mm, 166 in band, 107934 > 20 mm; distance mm min/median/max 9.6005/7450/31170.3993; histogram {'0-1': 0, '1-5': 0, '5-10': 3, '10-20': 163, '20-50': 229, '50-100': 2741, '100-1000': 7687, '1000+': 97277}; worst: ['SM_Kpp_1_Main#12134/SM_Kpp_1_Main#28204 d=31170.4 mm', 'SM_Kpp_1_Main#4162/SM_Kpp_1_Main#12134 d=31170.4 mm', 'SM_Kpp_1_Main#12134/SM_Kpp_1_Main#28205 d=31170.4 mm', 'SM_Kpp_1_Main#4162/SM_Kpp_1_Main#28077 d=31170.4 mm', 'SM_Kpp_1_Main#4162/SM_Kpp_1_Main#12103 d=30920.4 mm'] | co-directional overlapping faces 5-20 mm apart (pairs beyond 20 mm: review) | review |
| vpm / V005 | pass -> pass | color attributes | SM_Kpp_1.fbx: 0 color attributes on 6 mesh(es) | no color attributes (reg 4.1.1: recommended to remove) | pass |
| vpm / V007 | pass -> pass | VPM maps | 21 PNG: names, 8-bit, sizes, alpha rules, sets, ERM order, DirectX green | reg p.30-31 | pass |
| vpm / V008 | pass -> pass | UDIM sequence | slot 1: [1001, 1002, 1003, 1004, 1005, 1006, 1007] | 1001..1100 sequential without gaps | pass |
| vpm / V008 | pass -> pass | one UV channel | SM_Kpp_1.fbx: all meshes | 1 UV channel | pass |
| vpm / V008 | pass -> pass | mirrored islands | SM_Kpp_1.fbx: none | no mirrored UV | pass |
| vpm / V009 | pass -> pass | texel density | SM_Kpp_1.fbx: min 706.865 px/m at SM_Kpp_1_Main polygon 4738, tile 1003; 12231 placeholder polygon(s) exempt | >= 512 px/m | pass |
| vpm / V009 | pass -> pass | texel density upper | SM_Kpp_1.fbx: max 1000.51 px/m at SM_Kpp_1_Main polygon 30114, tile 1003 | <= 1706 px/m | pass |
| vpm / V010 | not_run -> not_run | UCX present | SM_Kpp_1.fbx: 4 UCX mesh(es) | own UCX_ collision in each non-lighting geometry FBX | pass |
| vpm / V010 | not_run -> not_run | UCX material slots | SM_Kpp_1.fbx: no slots | no material slots on UCX meshes | pass |
| vpm / V010 | not_run -> not_run | UCX triangle budget | SM_Kpp_1.fbx: 48 UCX for 30666 model triangles | <= 15000 | pass |
| vpm / V010 | not_run -> not_run | UCX intersections | SM_Kpp_1.fbx: no overlapping pairs among 4 pieces | no two UCX pieces intersect (reg p.36 §13.4) | pass |
| vpm / V010 | not_run -> not_run | UCX intersections coverage | SM_Kpp_1.fbx: every neighbour pair evaluated | every neighbour pair evaluated: closed convex non-degenerate hulls (SAT) or bounding boxes apart | pass |
| vpm / V010 | not_run -> not_run | UCX piece gap (advisory) | SM_Kpp_1.fbx: touch=0 below_band=0 in_band=5 wide=0 unmeasured=0; [] | neighbour gap 2 mm - 1 cm inclusive [D098] (advisory, never a failure) | pass |
| vpm / V010 | not_run -> not_run | UCX shape | SM_Kpp_1.fbx: 4 closed convex piece(s) | closed, convex, non-degenerate UCX pieces | pass |
| vpm / V010 | not_run -> not_run | UCX coverage and offsets | coverage of the model, offsets | reg p.34-37 | not_run |
| vpm / V011 | fail -> fail | FNO_code empty | empty | mandatory value (never invent it; ask the customer) | fail |
| vpm / V011 | fail -> fail | FNO_name empty | empty | mandatory value (never invent it; ask the customer) | fail |
| vpm / V011 | fail -> fail | s_obsh empty | empty | mandatory value (never invent it; ask the customer) | fail |
| vpm / V011 | fail -> fail | s_naz empty | empty | mandatory value (never invent it; ask the customer) | fail |
| vpm / V011 | fail -> fail | s_podz empty | empty | mandatory value (never invent it; ask the customer) | fail |
| vpm / V011 | fail -> fail | spp_gns empty | empty | mandatory value (never invent it; ask the customer) | fail |
| vpm / V011 | fail -> fail | imageBase64 | JPG 256x256 | JPG 256x256 | pass |
| vpm / V011 | fail -> fail | Glasses | 1 glass material(s) | colour, transparency, refraction, roughness, metallicity | pass |
| vpm / V012 | review -> review | archive name | SM_Kpp_1 | SM_{Address}; _001.. index for free-standing buildings | review |
| vpm / V012 | review -> review | MainGlass object | SM_Kpp_1.fbx: SM_Kpp_1_MainGlass | SM_Kpp_1_MainGlass | pass |
| vpm / V012 | review -> review | MainGlass materials | SM_Kpp_1.fbx: ['M_Kpp_1_MainGlass_1'] | M_Kpp_1_MainGlass_1..7 | pass |
| vpm / V012 | review -> review | mesh names | SM_Kpp_1.fbx: 2 name(s) follow the grammar | SM_{Address}_Main\|MainGlass; <= 254 characters, A-Z a-z 0-9 _ | pass |
| vpm / V012 | review -> review | UCX names | SM_Kpp_1.fbx: 4 name(s) follow the grammar | UCX_SM_{Address}_Main_001..999; <= 254 characters, A-Z a-z 0-9 _ | pass |
| vpm / V013 | not_run -> not_run | origin at FBX zero | SM_Kpp_1.fbx: SM_Kpp_1_Main at [0.0, 0.0, 0.0] | local origin (0, 0, 0) | pass |
| vpm / V013 | not_run -> not_run | pivot at geometric centre | SM_Kpp_1.fbx: X/Y offset [1.07, 1.99] % | <= 10 % of the size | pass |
| vpm / V013 | not_run -> not_run | shared pivot | SM_Kpp_1.fbx: all meshes | every mesh shares the Main origin within 1 mm (UCX exempt) | pass |
| vpm / V013 | not_run -> not_run | MSK-77 point | GeoJSON point vs survey coordinates and project zero | reg p.32-33, p.55 | not_run |
| vpm / V015 | not_run -> not_run | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | not measured | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | not_run |
| vpm / V016 | not_run -> not_run | проходы/арки/дворы свободны, расстояние коллизий до поверхностей соответствует высотной зоне | not measured | проходы/арки/дворы свободны, расстояние коллизий до поверхностей соответствует высотной зоне | not_run |
| vpm / V017 | not_run -> not_run | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | not measured | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | not_run |
