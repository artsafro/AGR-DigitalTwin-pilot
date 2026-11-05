# Vatutino showcase MAF colour zones (#889)

Geometry is the accepted v005-set mesh. Vertex and face counts below are one read of that mesh;
before and after are equal because no mesh was written. Colours are the v005 target of the atlas
slot the position already uses. Passport photos for these 13 positions were not on disk, so no
colour was measured from a photo and no extra zone was added to a single-material mesh.

Photo status: missing. Accepted: False.

| position | zone | ID | key | colour | faces npm | faces vpm | vertices npm | vertices vpm | colour source |
|---|---|---|---|---|---|---|---|---|---|
| VAT_MAF_T3510_01 | larch_light_oak | 14 | wood_light | #BEA581 | 60 | 60 | 140 | 140 | schedule finish light oak; v005 target, photo not measured |
| VAT_MAF_T3510_01 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 180 | 180 | 140 | 140 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_02 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 146 | 146 | 96 | 96 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_02 | — | — | — | — | — | — | — | — | source mesh has one atlas material; passport photo not on disk; no further colour zone invented |
| VAT_MAF_T3510_07 | larch_light_oak | 14 | wood_light | #BEA581 | 364 | 364 | 240 | 240 | schedule finish light oak; v005 target, photo not measured |
| VAT_MAF_T3510_07 | — | — | — | — | — | — | — | — | source mesh has one atlas material; passport photo not on disk; no further colour zone invented |
| VAT_MAF_T3510_09 | larch_light_oak | 14 | wood_light | #BEA581 | 300 | 300 | 421 | 786 | schedule finish light oak; v005 target, photo not measured |
| VAT_MAF_T3510_09 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 430 | 1160 | 421 | 786 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_11 | larch_light_oak | 14 | wood_light | #BEA581 | 70 | 104 | 236 | 388 | schedule finish light oak; v005 target, photo not measured |
| VAT_MAF_T3510_11 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 364 | 620 | 236 | 388 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_12 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 678 | 678 | 416 | 416 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_12 | — | — | — | — | — | — | — | — | source mesh has one atlas material; passport photo not on disk; no further colour zone invented |
| VAT_MAF_T3510_16 | larch_light_oak | 14 | wood_light | #BEA581 | 2281 | 4562 | 1356 | 2580 | schedule finish light oak; v005 target, photo not measured |
| VAT_MAF_T3510_16 | — | — | — | — | — | — | — | — | source mesh has one atlas material; passport photo not on disk; no further colour zone invented |
| VAT_MAF_T3510_26 | hpl_satin_wood | 14 | wood_light | #BEA581 | 12 | 35 | 1300 | 4184 | schedule HPL satin wood merged to wood_light; v005 target, photo not measured |
| VAT_MAF_T3510_26 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 3031 | 8661 | 1300 | 4184 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_27 | larch_light_oak | 14 | wood_light | #BEA581 | 364 | 364 | 292 | 292 | schedule finish light oak; v005 target, photo not measured |
| VAT_MAF_T3510_27 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 176 | 176 | 292 | 292 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_28 | rope_pp | 29 | rope_pp | #5A5A5A | 564 | 564 | 1027 | 1027 | schedule polypropylene rope, no RAL; v005 target, photo not measured |
| VAT_MAF_T3510_28 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 1466 | 1466 | 1027 | 1027 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_29 | larch_light_oak | 14 | wood_light | #BEA581 | 320 | 320 | 156 | 156 | schedule finish light oak; v005 target, photo not measured |
| VAT_MAF_T3510_29 | — | — | — | — | — | — | — | — | source mesh has one atlas material; passport photo not on disk; no further colour zone invented |
| VAT_MAF_T3510_31 | larch_light_oak | 14 | wood_light | #BEA581 | 212 | 212 | 136 | 136 | schedule finish light oak; v005 target, photo not measured |
| VAT_MAF_T3510_31 | — | — | — | — | — | — | — | — | source mesh has one atlas material; passport photo not on disk; no further colour zone invented |
| VAT_MAF_T3510_32 | steel_ral7047 | 4 | paint_ral7047 | #D0D0D0 | 3726 | 3726 | 1953 | 1953 | schedule RAL 7047; v005 target, photo not measured |
| VAT_MAF_T3510_32 | — | — | — | — | — | — | — | — | source mesh has one atlas material; passport photo not on disk; no further colour zone invented |

Positions with one zone were left as the recorded atlas slot. A passport photo is required before splitting them.
