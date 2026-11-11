# Vatutino showcase MAF colour zones (#889)

Geometry is the accepted v005-set mesh. `before` is the pre-apply readback
(site-maf-set.md / site-maf-zone-counts.json). `after` is the apply readback.
Vertex and face counts are equal before and after.
A schedule RAL is stated as that paint. A named finish with no number keeps the atlas-slot
hex and is marked colour assumed (the vendor candidate sheet is a library viewport, not a measurement).
Single-material meshes are split into face groups at a dihedral of 40 degrees; the kind of each
group (slab, tube, shell, fastener) is mapped by POSITION_POLICY.

QA: `maf_surface` readback from tools/blender/fbx_readback.py.

Photo status: not_required. Accepted: False.

APPLIED C:\x\889-maf-colour-zones\applied-v003.json max_exit_code=4294967166 (known polyunwrapper_autoload.mse startup error)

| position | zone | ID | key | colour | npm faces before | npm faces after | npm verts before | npm verts after | vpm faces before | vpm faces after | vpm verts before | vpm verts after | zone faces npm | zone faces vpm | colour source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VAT_MAF_T3510_01 | boards | 14 | wood_light | #C49A6C | 240 | 240 | 140 | 140 | 240 | 240 | 140 | 140 | 60 | 60 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_01 | frame | 4 | paint_ral7047 | #D0D0D0 | 240 | 240 | 140 | 140 | 240 | 240 | 140 | 140 | 180 | 180 | schedule RAL 7047 |
| VAT_MAF_T3510_02 | frame | 4 | paint_ral7047 | #D0D0D0 | 146 | 146 | 96 | 96 | 146 | 146 | 96 | 96 | 146 | 146 | schedule RAL 7047 |
| VAT_MAF_T3510_02 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | schedule names one finish; face groups keep that material id |
| VAT_MAF_T3510_07 | boards | 14 | wood_light | #C49A6C | 364 | 364 | 240 | 240 | 364 | 364 | 240 | 240 | 262 | 262 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_07 | frame | 4 | paint_ral7047 | #D0D0D0 | 364 | 364 | 240 | 240 | 364 | 364 | 240 | 240 | 102 | 102 | schedule RAL 7047 |
| VAT_MAF_T3510_09 | boards | 14 | wood_light | #C49A6C | 730 | 730 | 421 | 421 | 1460 | 1460 | 786 | 786 | 300 | 300 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_09 | frame | 4 | paint_ral7047 | #D0D0D0 | 730 | 730 | 421 | 421 | 1460 | 1460 | 786 | 786 | 430 | 1160 | schedule RAL 7047 |
| VAT_MAF_T3510_11 | boards | 14 | wood_light | #C49A6C | 434 | 434 | 236 | 236 | 724 | 724 | 388 | 388 | 70 | 104 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_11 | frame | 4 | paint_ral7047 | #D0D0D0 | 434 | 434 | 236 | 236 | 724 | 724 | 388 | 388 | 364 | 620 | schedule RAL 7047 |
| VAT_MAF_T3510_12 | boards | 14 | wood_light | #C49A6C | 678 | 678 | 416 | 416 | 678 | 678 | 416 | 416 | 452 | 452 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_12 | fasteners | 22 | cap_black | #303030 | 678 | 678 | 416 | 416 | 678 | 678 | 416 | 416 | 36 | 36 | schedule polyamide caps; no RAL; colour assumed; v005 cap_black #303030 |
| VAT_MAF_T3510_12 | frame | 4 | paint_ral7047 | #D0D0D0 | 678 | 678 | 416 | 416 | 678 | 678 | 416 | 416 | 190 | 190 | schedule RAL 7047 |
| VAT_MAF_T3510_16 | boards | 14 | wood_light | #C49A6C | 2281 | 2281 | 1356 | 1356 | 4562 | 4562 | 2580 | 2580 | 200 | 112 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_16 | frame | 4 | paint_ral7047 | #D0D0D0 | 2281 | 2281 | 1356 | 1356 | 4562 | 4562 | 2580 | 2580 | 2081 | 4450 | schedule RAL 7047 |
| VAT_MAF_T3510_26 | hpl | 32 | wood_hpl_satin | #B4825A | 3043 | 3043 | 1300 | 1300 | 8696 | 8696 | 4184 | 4184 | 12 | 35 | schedule HPL satin wood; no RAL; vendor images are library viewport colours, not a finish measurement; colour assumed; atlas slot hpl_satin_wood #B4825A |
| VAT_MAF_T3510_26 | frame | 4 | paint_ral7047 | #D0D0D0 | 3043 | 3043 | 1300 | 1300 | 8696 | 8696 | 4184 | 4184 | 3031 | 8661 | schedule RAL 7047 |
| VAT_MAF_T3510_27 | boards | 14 | wood_light | #C49A6C | 540 | 540 | 292 | 292 | 540 | 540 | 292 | 292 | 364 | 364 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_27 | frame | 4 | paint_ral7047 | #D0D0D0 | 540 | 540 | 292 | 292 | 540 | 540 | 292 | 292 | 176 | 176 | schedule RAL 7047 |
| VAT_MAF_T3510_28 | rope | 29 | rope_pp | #7A7A7A | 2030 | 2030 | 1027 | 1027 | 2030 | 2030 | 1027 | 1027 | 564 | 564 | schedule polypropylene rope; no RAL; colour assumed; atlas slot rope_pp #7A7A7A |
| VAT_MAF_T3510_28 | frame | 4 | paint_ral7047 | #D0D0D0 | 2030 | 2030 | 1027 | 1027 | 2030 | 2030 | 1027 | 1027 | 1466 | 1466 | schedule RAL 7047 |
| VAT_MAF_T3510_29 | boards | 14 | wood_light | #C49A6C | 320 | 320 | 156 | 156 | 320 | 320 | 156 | 156 | 292 | 292 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_29 | fasteners | 22 | cap_black | #303030 | 320 | 320 | 156 | 156 | 320 | 320 | 156 | 156 | 4 | 4 | schedule polyamide caps; no RAL; colour assumed; v005 cap_black #303030 |
| VAT_MAF_T3510_29 | frame | 4 | paint_ral7047 | #D0D0D0 | 320 | 320 | 156 | 156 | 320 | 320 | 156 | 156 | 24 | 24 | schedule RAL 7047 |
| VAT_MAF_T3510_31 | boards | 14 | wood_light | #C49A6C | 212 | 212 | 136 | 136 | 212 | 212 | 136 | 136 | 96 | 96 | schedule finish light oak; no RAL; vendor candidates_part*.jpg and candidates_sheet.jpg are library viewport colours, not a finish measurement; colour assumed; atlas slot larch_light_oak #C49A6C |
| VAT_MAF_T3510_31 | frame | 4 | paint_ral7047 | #D0D0D0 | 212 | 212 | 136 | 136 | 212 | 212 | 136 | 136 | 116 | 116 | schedule RAL 7047 |
| VAT_MAF_T3510_32 | frame | 4 | paint_ral7047 | #D0D0D0 | 3726 | 3726 | 1953 | 1953 | 3726 | 3726 | 1953 | 1953 | 3726 | 3726 | schedule RAL 7047 |
| VAT_MAF_T3510_32 | — | — | — | — | — | — | — | — | — | — | — | — | — | — | schedule names one finish; face groups keep that material id |

Method: shared-edge components with dihedral <= 40 deg; slab / tube / shell / fastener extents as in the module docstring.

maf_surface (tools/blender/fbx_readback.py):

| position | profile | vertices | faces | flipped_faces | inconsistent_edges | soft_over_40 |
|---|---|---|---|---|---|---|
| VAT_MAF_T3510_01 | npm | 140 | 240 | 0 | 0 | 0 |
| VAT_MAF_T3510_01 | vpm | 140 | 240 | 0 | 0 | 0 |
| VAT_MAF_T3510_02 | npm | 96 | 146 | 0 | 0 | 0 |
| VAT_MAF_T3510_02 | vpm | 96 | 146 | 0 | 0 | 0 |
| VAT_MAF_T3510_07 | npm | 240 | 364 | 0 | 0 | 0 |
| VAT_MAF_T3510_07 | vpm | 240 | 364 | 0 | 0 | 0 |
| VAT_MAF_T3510_09 | npm | 421 | 730 | 0 | 0 | 0 |
| VAT_MAF_T3510_09 | vpm | 786 | 1460 | 0 | 0 | 0 |
| VAT_MAF_T3510_11 | npm | 236 | 434 | 0 | 0 | 0 |
| VAT_MAF_T3510_11 | vpm | 388 | 724 | 0 | 0 | 0 |
| VAT_MAF_T3510_12 | npm | 416 | 678 | 0 | 0 | 0 |
| VAT_MAF_T3510_12 | vpm | 416 | 678 | 0 | 0 | 0 |
| VAT_MAF_T3510_16 | npm | 1356 | 2281 | 0 | 0 | 0 |
| VAT_MAF_T3510_16 | vpm | 2580 | 4562 | 0 | 0 | 0 |
| VAT_MAF_T3510_26 | npm | 1300 | 3043 | 0 | 0 | 0 |
| VAT_MAF_T3510_26 | vpm | 4184 | 8696 | 0 | 0 | 0 |
| VAT_MAF_T3510_27 | npm | 292 | 540 | 0 | 0 | 0 |
| VAT_MAF_T3510_27 | vpm | 292 | 540 | 0 | 0 | 0 |
| VAT_MAF_T3510_28 | npm | 1027 | 2030 | 0 | 0 | 0 |
| VAT_MAF_T3510_28 | vpm | 1027 | 2030 | 0 | 0 | 0 |
| VAT_MAF_T3510_29 | npm | 156 | 320 | 0 | 0 | 0 |
| VAT_MAF_T3510_29 | vpm | 156 | 320 | 0 | 0 | 0 |
| VAT_MAF_T3510_31 | npm | 136 | 212 | 0 | 0 | 0 |
| VAT_MAF_T3510_31 | vpm | 136 | 212 | 0 | 0 | 0 |
| VAT_MAF_T3510_32 | npm | 1953 | 3726 | 0 | 0 | 0 |
| VAT_MAF_T3510_32 | vpm | 1953 | 3726 | 0 | 0 | 0 |
