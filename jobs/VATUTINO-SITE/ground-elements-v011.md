# Vatutino Ground Step 8 — per-entity dispositions v011

Source: typed SPOZU adapter output `C:/x/t_d94665f2/paving_ground_inputs_v4.json` (paving DWG COPY, metres).
User approval: Artem, 2026-10-19, "Принимаю" (relayed on card): read curb/stair layers; drives 150 mm high × 150 mm wide; garden curbs 50 mm × 80 mm; stairs from VP; geometry not defined by the DWG is skipped and listed.

Garden curb paths are width centrelines (the source polyline width is also 80 mm). Solids use the common VP datum +18 mm as their bottom (method-C stack is at most +12 mm); height is 50 mm above that bottom. This 6 mm construction offset is explicit, not an inferred source height. No road-curb path occurs on the configured drive layer. Wood/buried/unclassified curbs have no approved visible section and stay skipped with reasons. Stair symbols' arbitrary source Z is never used as VP elevation. Outlines closing within 2 mm are closed explicitly; tread endpoints extend at most 20 mm to reach an outline. Modeled stairs replace 10.260678 m² of the Ground and of crossing curbs, rather than intersecting those surfaces. Missing or nonpartitioning tread geometry is not invented. Bench symbols are MAF, excluded here. No separately named ramp/retaining-wall layer was found in the source layer inventory; this is an inventory limitation, not inferred absence of such structures.

Every adapter record is listed, including parent INSERTs and nested path provenance. Repeated symbols are distinct instances. `modeled` on a path means its contribution belongs to the modeled parent solid; it is not an additional duplicate mesh.

| Ref | Role | Layer | Label | Disposition | Dimensions / reason |
|---|---|---|---|---|---|
| F3FD3 | curb_unclassified | Борт |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| F3FD4 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FD5 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FD6 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FD7 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FD8 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FD9 | curb_unclassified | Борт |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| F3FDA | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FDB | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FDC | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FDD | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FDE | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE1 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE2 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE3 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE4 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE5 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE6 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE7 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE8 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FE9 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FEA | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FEB | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FEC | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FED | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FEE | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FEF | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FF0 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FF1 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FF2 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FF3 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FF4 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FF5 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FF6 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FF7 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FFB | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FFC | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FFD | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FFE | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F3FFF | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4000 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4001 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4002 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4003 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4004 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4005 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4006 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4007 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F400C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F400D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F400E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F400F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4010 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4013 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4014 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4015 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4016 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4017 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4018 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4019 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F401A | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F401B | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F401C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F401D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F401E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F401F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4020 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4021 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4022 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4023 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4024 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4025 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4026 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4027 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4028 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4029 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F402A | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F402B | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F402C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F402D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F402E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F402F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4030 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4031 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4032 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4033 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4034 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4035 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4036 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4037 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4038 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4039 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F403A | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F403B | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F403C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F403D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F403E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F403F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4040 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4041 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4042 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4043 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4044 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4045 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4046 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4047 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4048 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4049 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F404A | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F404B | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F404C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F404D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F404E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F404F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4050 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4051 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4052 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4054 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4055 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4056 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4057 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4058 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4059 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F405A | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F405B | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F405C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F405D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F405E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F405F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4060 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4061 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4062 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4063 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4064 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4065 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4066 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4067 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4068 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4069 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F406A | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F406E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F406F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4070 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4071 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4072 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4073 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4074 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4075 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4076 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4077 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4078 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4079 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F407A | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F407B | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F407C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F407D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F407E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F407F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4080 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4083 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4086 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4089 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F408B | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F408C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F408D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F408E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F408F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4090 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4091 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4092 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4093 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4094 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4095 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4096 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4097 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4098 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F409C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F409D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F409E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F409F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40A0 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40A1 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40A2 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40A6 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40A9 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40AA | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40AB | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40AC | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40AD | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40AE | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40AF | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B0 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B1 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B2 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B3 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B4 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B5 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B6 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B7 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B8 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40B9 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40BA | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40BB | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40BC | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40BD | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40BE | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40BF | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C0 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C1 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C2 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C3 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C5 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C6 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C7 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C8 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40C9 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40FE | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F40FF | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4100 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4102 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4103 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4104 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4105 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4106 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4107 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4108 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4109 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F410A | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F410B | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F410C | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F410D | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F410E | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F410F | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4110 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4111 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4112 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4113 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F4114 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F5DF8 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F5DF9 | curb_unclassified | Борт |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| F5DFA | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F5E27 | curb_unclassified | Борт |  | skipped | outside Ground boundary or collapsed at 2 mm |
| F5EB2 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 103948 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 12A3B9 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 12A3BE | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 12A6A9 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 13287B | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 14B3D1 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 14BB11 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 1500A2 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 15083B | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 188CA5 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18906A | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18A624 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A62B | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18A62F | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A630 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18A638 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A63B | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A63C | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A63D | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A641 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A642 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A643 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A644 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A645 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A646 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A647 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A648 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A64A | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A64B | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A64C | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A64D | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A64E | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A64F | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A650 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A651 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A652 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A653 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A654 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A655 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A656 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A664 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A665 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A666 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A667 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A668 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A669 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A66B | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A66C | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 18A66D | curb_garden | !_А101_борт_садовый_бетонный |  | skipped | outside Ground boundary or collapsed at 2 mm |
| 18A66E | curb_garden | !_А101_борт_садовый_бетонный |  | skipped | outside Ground boundary or collapsed at 2 mm |
| 18A66F | curb_garden | !_А101_борт_садовый_бетонный |  | skipped | outside Ground boundary or collapsed at 2 mm |
| 18A670 | curb_garden | !_А101_борт_садовый_бетонный |  | skipped | outside Ground boundary or collapsed at 2 mm |
| 18A674 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18A678 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18A679 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18A67A | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18A682 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18A7EC | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB40 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB41 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB4C | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB4D | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB4E | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB4F | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB50 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB52 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB53 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB54 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB5A | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB5C | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB5D | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB73 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB74 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB75 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AB80 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AD3C | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AE47 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AF0F | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AF11 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 18AF12 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 19077A | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 19077B | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 19077C | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 19077D | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 19078C | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 190911 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 190990 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | outside Ground boundary or collapsed at 2 mm |
| 190992 | curb_wood | !_А101_борт_деревянный |  | skipped | outside Ground boundary or collapsed at 2 mm |
| 190994 | curb_garden | !_А101_борт_садовый_бетонный |  | skipped | outside Ground boundary or collapsed at 2 mm |
| 195B45 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195B4C | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195C4D | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195CC3 | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D29 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D2A | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D33 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D34 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D3B | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D3C | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D3D | curb_wood | !_А101_борт_деревянный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D43 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D45 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D46 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D47 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D48 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 195D49 | curb_buried | !_А101_борт_металлический_заглубленный |  | skipped | DWG/user do not define visible height and cross-section for this curb class |
| 1987FF | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198835 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198836 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198837 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198839 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 19883A | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 19883B | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 19883C | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198842 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198843 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198844 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198845 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198846 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198847 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198848 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198863 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198864 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198865 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198866 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198867 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198869 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1988B0 | stairs | !_А101_лестница | лестница 1 | skipped | DWG tread lines do not partition the stair footprint |
| 1988B0>1988AD | stairs | Defpoints |  | skipped | DWG tread lines do not partition the stair footprint |
| 1988B0>1988AE | stairs | Defpoints |  | skipped | DWG tread lines do not partition the stair footprint |
| 1988B0>1988AF | stairs | Defpoints |  | skipped | DWG tread lines do not partition the stair footprint |
| 1988C0 | stairs | !_А101_лестница | лестница 2 | modeled | 3 treads; source footprint/tread cuts; heights from VP |
| 1988C0>1988BA | stairs | !_А101_лестница |  | modeled | 3 treads; source footprint/tread cuts; heights from VP |
| 1988C0>1988BB | stairs | !_А101_лестница |  | modeled | 3 treads; source footprint/tread cuts; heights from VP |
| 1988C0>1988BC | stairs | !_А101_лестница |  | modeled | 3 treads; source footprint/tread cuts; heights from VP |
| 1988C0>1988BD | stairs | !_А101_лестница |  | modeled | 3 treads; source footprint/tread cuts; heights from VP |
| 1988C0>1988BE | stairs | !_А101_лестница |  | modeled | 3 treads; source footprint/tread cuts; heights from VP |
| 1988C0>1988BF | stairs | !_А101_лестница |  | modeled | 3 treads; source footprint/tread cuts; heights from VP |
| 1988D2 | stairs | !_А101_лестница | лестница 3 | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 1988D2>1988CB | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 1988D2>1988CC | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 1988D2>1988CD | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 1988D2>1988CE | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 1988D2>1988CF | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 1988D2>1988D0 | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 1988D2>1988D1 | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 1988D3 | stairs | !_А101_лестница | лестница 3 | skipped | stair footprint outside Ground or unsupported holes/multiple parts |
| 1988D3>1988CB | stairs | !_А101_лестница |  | skipped | stair footprint outside Ground or unsupported holes/multiple parts |
| 1988D3>1988CC | stairs | !_А101_лестница |  | skipped | stair footprint outside Ground or unsupported holes/multiple parts |
| 1988D3>1988CD | stairs | !_А101_лестница |  | skipped | stair footprint outside Ground or unsupported holes/multiple parts |
| 1988D3>1988CE | stairs | !_А101_лестница |  | skipped | stair footprint outside Ground or unsupported holes/multiple parts |
| 1988D3>1988CF | stairs | !_А101_лестница |  | skipped | stair footprint outside Ground or unsupported holes/multiple parts |
| 1988D3>1988D0 | stairs | !_А101_лестница |  | skipped | stair footprint outside Ground or unsupported holes/multiple parts |
| 1988D3>1988D1 | stairs | !_А101_лестница |  | skipped | stair footprint outside Ground or unsupported holes/multiple parts |
| 1988F9 | stairs | !_А101_лестница | лестница 5 | skipped | DWG tread lines do not partition the stair footprint |
| 1988F9>1988F3 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 1988F9>1988F4 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 1988F9>1988F5 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 1988F9>1988F6 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 1988F9>1988F7 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 1988F9>1988F8 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198903 | stairs | !_А101_лестница | лестница 4 | skipped | DWG tread lines do not partition the stair footprint |
| 198903>198900 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198903>198901 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198903>198902 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198ADB | stairs | !_А101_лестница | Скамья Индивид лестн 2 | skipped | bench symbol, MAF excluded from Ground surface scope |
| 198ADB>198AD9 | stairs | !_А101_маф |  | skipped | unsupported element primitive HATCH |
| 198ADB>198ADA | stairs | !_А101_маф |  | skipped | bench symbol, MAF excluded from Ground surface scope |
| 198BAC | stairs | !_А101_лестница | Скамья Индивид лестн 2.1 | skipped | bench symbol, MAF excluded from Ground surface scope |
| 198BAC>198C87 | stairs | !_А101_маф |  | skipped | unsupported element primitive HATCH |
| 198BAC>198C88 | stairs | !_А101_маф |  | skipped | bench symbol, MAF excluded from Ground surface scope |
| 198C08 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C09 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C0A | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C0B | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C0C | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C0D | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C0E | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C0F | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C10 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C11 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C12 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C13 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C14 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C1D | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C1E | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C1F | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C45 | stairs | !_А101_лестница | лестница 6 | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 198C45>198C42 | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 198C45>198C43 | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 198C45>198C44 | stairs | !_А101_лестница |  | modeled | 2 treads; source footprint/tread cuts; heights from VP |
| 198C53 | stairs | !_А101_лестница | лестница 7 | skipped | DWG tread lines do not partition the stair footprint |
| 198C53>198C4E | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C53>198C4F | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C53>198C50 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C53>198C51 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C53>198C52 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C65 | stairs | !_А101_лестница | лестница 8 | skipped | DWG tread lines do not partition the stair footprint |
| 198C65>198C5E | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C65>198C5F | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C65>198C60 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C65>198C61 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C65>198C62 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C65>198C63 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C65>198C64 | stairs | !_А101_лестница |  | skipped | DWG tread lines do not partition the stair footprint |
| 198C66 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C67 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C68 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C8D | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C8E | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C8F | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C90 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C91 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C92 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C93 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C94 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C95 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C96 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C97 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 198C9A | stairs | !_А101_лестница | Скамья Индивид лестн 2 | skipped | bench symbol, MAF excluded from Ground surface scope |
| 198C9A>198AD9 | stairs | !_А101_маф |  | skipped | unsupported element primitive HATCH |
| 198C9A>198ADA | stairs | !_А101_маф |  | skipped | bench symbol, MAF excluded from Ground surface scope |
| 198C9B | stairs | !_А101_лестница | Скамья Индивид лестн 2.1 | skipped | bench symbol, MAF excluded from Ground surface scope |
| 198C9B>198C87 | stairs | !_А101_маф |  | skipped | unsupported element primitive HATCH |
| 198C9B>198C88 | stairs | !_А101_маф |  | skipped | bench symbol, MAF excluded from Ground surface scope |
| 1A5EAE | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1A66C4 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1A66C5 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1A6BB3 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1A6BB4 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1A7817 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1A7919 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1A791A | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1AAD88 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1AAF10 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1AB1F9 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1AB1FA | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
| 1ACB64 | curb_garden | !_А101_борт_садовый_бетонный |  | modeled | 0.05 m high × 0.08 m wide; approved section; polyline is the width centreline |
