# Current-main validator readback on package-v006

Main 9d7753e1; both validators exit 1 / passed=false. Historical before/after remains in ../latest/CHECKS.md.
Package payloads: 3/3 identical to measured v004; reproduction: 5/5 files identical.

| Profile / stage | Status | Check | Value | Limit | Owner / missing input |
|---|---|---|---|---|---|
| npm/V001 | pass | archive size | 619204 B <= 1024 MiB | <= 1073741824 B | n/a |
| npm/V001 | fail | FBX count | 1 | 2..21 (1 Ground + 1..20 OKS) | Ground author / Artem: approved Ground missing |
| npm/V001 | fail | Ground FBX | ['0000_Kpp_1_01.fbx'] | 0000_Kpp_1_Ground.fbx | Ground author / Artem: approved Ground missing |
| npm/V002 | pass | FBX header | 0000_Kpp_1_01.fbx: binary FBX version 7400 | binary FBX 7400 (7.4/2014) | n/a |
| npm/V002 | pass | system units | 0000_Kpp_1_01.fbx: 1 unit = 100 cm (UnitScaleFactor 100, OriginalUnitScaleFactor 100.0) | 1 unit = 1 m (UnitScaleFactor 100) | n/a |
| npm/V002 | pass | scale 1:1 | 0000_Kpp_1_01.fbx: scale 1 on every mesh | local and effective (inherited) scale 1 on every mesh (1:1) | n/a |
| npm/V003 | pass | triangulated | 0000_Kpp_1_01.fbx: all triangles | triangulated on export | n/a |
| npm/V003 | pass | triangle count | 0000_Kpp_1_01.fbx: 18836 | <= 150000 | n/a |
| npm/V003 | not_run | master quads | quad work FBX not given (--master) | quad master; VPM faces <= 4 m [D021] | KPP1 master author / Artem: quad work FBX absent |
| npm/V004 | pass | applied transforms | 0000_Kpp_1_01.fbx: rotation 0, scale 1 | rotation 0, scale 1 after reset | n/a |
| npm/V004 | pass | topology defects | 0000_Kpp_1_01.fbx: max 0 duplicates/self-intersections, no isolated or zero-length elements | <= 100 duplicates/self-intersections at 0.002 m per mesh; 0 isolated vertices/edges/polygons; 0 zero-length edges | n/a |
| npm/V004 | review | co-directional clearance | 0000_Kpp_1_01.fbx: 20374 co-directional overlapping pairs: 0 < 5 mm, 108 in band, 20266 > 20 mm; distance mm min/median/max 13.695/6870.2359/31170.3557; histogram {'0-1': 0, '1-5': 0, '5-10': 0, '10-20': 108, '20-50': 14, '50-100': 972, '100-1000': 987, '1000+': 18293}; worst: ['SM_Kpp_1_001_Main#7465/SM_Kpp_1_001_Main#16670 d=31170.4 mm', 'SM_Kpp_1_001_Main#7465/SM_Kpp_1_001_Main#16669 d=31170.3 mm', 'SM_Kpp_1_001_Main#7462/SM_Kpp_1_001_Main#10604 d=30670.4 mm', 'SM_Kpp_1_001_Main#7447/SM_Kpp_1_001_Main#10604 d=30420.5 mm', 'SM_Kpp_1_001_Main#7482/SM_Kpp_1_001_Main#11826 d=29670.2 mm'] | co-directional overlapping faces 5-20 mm apart (pairs beyond 20 mm: review) | KPP1 geometry author / Artem: rotated-pair classification missing |
| npm/V005 | pass | color attributes | 0000_Kpp_1_01.fbx: 0 color attributes on 2 mesh(es) | no color attributes (reg 4.1.1: recommended to remove) | n/a |
| npm/V005 | pass | material assignments | 0000_Kpp_1_01.fbx: every opaque material has a bound diffuse image | each NPM opaque material resolves to its diffuse texture; glass excluded | n/a |
| npm/V006 | pass | embedded textures | 0000_Kpp_1_01.fbx: all embedded | PNG embedded in FBX | n/a |
| npm/V006 | pass | texture dimensions | 0000_Kpp_1_01.fbx: all measured sides <= 2048 px | positive measured NPM image dimensions, each side <= 2048 px; PNG-byte checks separate | n/a |
| npm/V012 | pass | FBX names | all match | 0000_Kpp_1_01..20.fbx and 0000_Kpp_1_Ground.fbx | n/a |
| npm/V012 | pass | mesh names | 0000_Kpp_1_01.fbx: 2 name(s) follow the grammar | SM_{Address}_{001..020}_Main\|MainGlass; <= 254 characters, A-Z a-z 0-9 _ | n/a |
| npm/V014 | not_run | геометрия в московских проектных координатах и высотах; углы соответствуют плану | not measured | геометрия в московских проектных координатах и высотах; углы соответствуют плану | Validator maintainer / Artem: coordinate-stage implementation absent |
| npm/V015 | not_run | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | not measured | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | Artem: architectural acceptance absent |
| npm/V017 | not_run | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | not measured | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | Artem / survey author: point/zero/orientation acceptance absent |
| vpm/V001 | pass | archive size | 990039 B <= 500 MiB | <= 524288000 B | n/a |
| vpm/V002 | pass | FBX header | SM_Kpp_1.fbx: binary FBX version 7400 | binary FBX 7400 (7.4/2014) | n/a |
| vpm/V002 | pass | system units | SM_Kpp_1.fbx: 1 unit = 100 cm (UnitScaleFactor 100, OriginalUnitScaleFactor 100.0) | 1 unit = 1 m (UnitScaleFactor 100) | n/a |
| vpm/V002 | pass | scale 1:1 | SM_Kpp_1.fbx: scale 1 on every mesh | local and effective (inherited) scale 1 on every mesh (1:1) | n/a |
| vpm/V003 | pass | triangulated | SM_Kpp_1.fbx: all triangles | triangulated on export | n/a |
| vpm/V003 | pass | triangle count | SM_Kpp_1.fbx: 30484 | <= 150000 project target (reuse as NPM; else windows as atlas planes), 1000000 regulation limit | n/a |
| vpm/V003 | not_run | master quads | quad work FBX not given (--master) | quad master; VPM faces <= 4 m [D021] | KPP1 master author / Artem: quad work FBX absent |
| vpm/V004 | pass | applied transforms | SM_Kpp_1.fbx: rotation 0, scale 1 | rotation 0, scale 1 after reset | n/a |
| vpm/V004 | pass | topology defects | SM_Kpp_1.fbx: max 0 duplicates/self-intersections, no isolated or zero-length elements | <= 100 duplicates/self-intersections at 0.002 m per mesh; 0 isolated vertices/edges/polygons; 0 zero-length edges | n/a |
| vpm/V004 | review | co-directional clearance | SM_Kpp_1.fbx: 105773 co-directional overlapping pairs: 0 < 5 mm, 159 in band, 105614 > 20 mm; distance mm min/median/max 14.7994/7345.9993/31170.3993; histogram {'0-1': 0, '1-5': 0, '5-10': 0, '10-20': 159, '20-50': 230, '50-100': 2722, '100-1000': 7626, '1000+': 95036}; worst: ['SM_Kpp_1_Main#12042/SM_Kpp_1_Main#28032 d=31170.4 mm', 'SM_Kpp_1_Main#4091/SM_Kpp_1_Main#12042 d=31170.4 mm', 'SM_Kpp_1_Main#12042/SM_Kpp_1_Main#28033 d=31170.4 mm', 'SM_Kpp_1_Main#4091/SM_Kpp_1_Main#27904 d=31170.4 mm', 'SM_Kpp_1_Main#4091/SM_Kpp_1_Main#12001 d=30920.4 mm'] | co-directional overlapping faces 5-20 mm apart (pairs beyond 20 mm: review) | KPP1 geometry author / Artem: rotated-pair classification missing |
| vpm/V005 | pass | color attributes | SM_Kpp_1.fbx: 0 color attributes on 6 mesh(es) | no color attributes (reg 4.1.1: recommended to remove) | n/a |
| vpm/V007 | pass | VPM maps | 21 PNG: names, 8-bit, sizes, alpha rules, sets, ERM order, DirectX green | reg p.30-31 | n/a |
| vpm/V008 | pass | UDIM sequence | slot 1: [1001, 1002, 1003, 1004, 1005, 1006, 1007] | 1001..1100 sequential without gaps | n/a |
| vpm/V008 | pass | one UV channel | SM_Kpp_1.fbx: all meshes | 1 UV channel | n/a |
| vpm/V008 | pass | mirrored islands | SM_Kpp_1.fbx: none | no mirrored UV | n/a |
| vpm/V009 | pass | texel density | SM_Kpp_1.fbx: min 706.865 px/m at SM_Kpp_1_Main polygon 5133, tile 1003; 12064 placeholder polygon(s) exempt | >= 512 px/m | n/a |
| vpm/V009 | pass | texel density upper | SM_Kpp_1.fbx: max 1000.51 px/m at SM_Kpp_1_Main polygon 29930, tile 1003 | <= 1706 px/m | n/a |
| vpm/V010 | pass | UCX present | SM_Kpp_1.fbx: 4 UCX mesh(es) | own UCX_ collision in each non-lighting geometry FBX | n/a |
| vpm/V010 | pass | UCX material slots | SM_Kpp_1.fbx: no slots | no material slots on UCX meshes | n/a |
| vpm/V010 | pass | UCX triangle budget | SM_Kpp_1.fbx: 48 UCX for 30484 model triangles | <= 15000 | n/a |
| vpm/V010 | pass | UCX intersections | SM_Kpp_1.fbx: no overlapping pairs among 4 pieces | no two UCX pieces intersect (reg p.36 §13.4) | n/a |
| vpm/V010 | pass | UCX intersections coverage | SM_Kpp_1.fbx: every neighbour pair evaluated | every neighbour pair evaluated: closed convex non-degenerate hulls (SAT) or bounding boxes apart | n/a |
| vpm/V010 | pass | UCX piece gap (advisory) | SM_Kpp_1.fbx: touch=0 below_band=0 in_band=5 wide=0 unmeasured=0; [] | neighbour gap 2 mm - 1 cm inclusive [D098] (advisory, never a failure) | n/a |
| vpm/V010 | pass | UCX shape | SM_Kpp_1.fbx: 4 closed convex piece(s) | closed, convex, non-degenerate UCX pieces | n/a |
| vpm/V010 | not_run | UCX coverage and offsets | coverage of the model, offsets | reg p.34-37 | Artem / collision reviewer: independent coverage and offset evidence absent |
| vpm/V011 | fail | FNO_code empty | empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1-specific area schedule absent |
| vpm/V011 | fail | FNO_name empty | empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1-specific area schedule absent |
| vpm/V011 | fail | s_obsh empty | empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1-specific area schedule absent |
| vpm/V011 | fail | s_naz empty | empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1-specific area schedule absent |
| vpm/V011 | fail | s_podz empty | empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1-specific area schedule absent |
| vpm/V011 | fail | spp_gns empty | empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1-specific area schedule absent |
| vpm/V011 | pass | imageBase64 | JPG 256x256 | JPG 256x256 | n/a |
| vpm/V011 | pass | Glasses | 1 glass material(s) | colour, transparency, refraction, roughness, metallicity | n/a |
| vpm/V012 | review | archive name | SM_Kpp_1 | SM_{Address}; _001.. index for free-standing buildings | Validator maintainer / Artem: single-OKS index review [D019] |
| vpm/V012 | pass | MainGlass object | SM_Kpp_1.fbx: SM_Kpp_1_MainGlass | SM_Kpp_1_MainGlass | n/a |
| vpm/V012 | pass | MainGlass materials | SM_Kpp_1.fbx: ['M_Kpp_1_MainGlass_1'] | M_Kpp_1_MainGlass_1..7 | n/a |
| vpm/V012 | pass | mesh names | SM_Kpp_1.fbx: 2 name(s) follow the grammar | SM_{Address}_Main\|MainGlass; <= 254 characters, A-Z a-z 0-9 _ | n/a |
| vpm/V012 | pass | UCX names | SM_Kpp_1.fbx: 4 name(s) follow the grammar | UCX_SM_{Address}_Main_001..999; <= 254 characters, A-Z a-z 0-9 _ | n/a |
| vpm/V013 | not_run | Z bounds vs export_meta | export_meta not supplied; height unverified | render Z min/max differ from export_meta by < 0.001 m | Survey author / Artem: authoritative plan tie; validator subset absent |
| vpm/V013 | pass | origin at FBX zero | SM_Kpp_1.fbx: SM_Kpp_1_Main at [0.0, 0.0, 0.0] | local origin (0, 0, 0) | n/a |
| vpm/V013 | pass | pivot at geometric centre | SM_Kpp_1.fbx: X/Y offset [1.07, 1.99] % | <= 10 % of the size | n/a |
| vpm/V013 | pass | shared pivot | SM_Kpp_1.fbx: all meshes | every mesh shares the Main origin within 1 mm (UCX exempt) | n/a |
| vpm/V013 | not_run | MSK-77 point | GeoJSON point vs survey coordinates and project zero | reg p.32-33, p.55 | Survey author / Artem: authoritative plan tie; validator subset absent |
| vpm/V015 | not_run | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | not measured | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | Artem: architectural acceptance absent |
| vpm/V016 | not_run | проходы/арки/дворы свободны, расстояние коллизий до поверхностей соответствует высотной зоне | not measured | проходы/арки/дворы свободны, расстояние коллизий до поверхностей соответствует высотной зоне | Artem: collision acceptance absent |
| vpm/V017 | not_run | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | not measured | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | Artem / survey author: point/zero/orientation acceptance absent |
