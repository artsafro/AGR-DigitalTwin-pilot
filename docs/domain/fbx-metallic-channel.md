# FBX metallic channel (SINTEZ 2.5.6) and Max FBX import of customer maps — #1729

Measured 2026-11-21 on this PC: 3ds Max 2026.3 batch (28.3.0.30732), Blender 5.1.2 + SINTEZ AGR Checker 1.6.1
(`tools/qa/sintez_checker.py`). Probe: `tools/max/metallic_channel_probe_max.py`; readback:
`tools/qa/fbx_maps_readback.py` over `adapters/max/agr_tools/fbxmaps_core.py`. SINTEZ is evidence, not the norm
(validation.md); the norm is reg 2.5.6 (requirements-2026.md: metallic and roughness only as a pair).

## Which channel SINTEZ reads as Metallic

Minimal FBX: one plane, one material, diffuse + roughness (`_r`) + metallic (`_m`) on one candidate slot, binary FBX
2014 with embedded media, zipped as `0001_Probe1729<case>.zip`.

| Max slot | FBX channel written by Max 2026 export | SINTEZ 1.6.1 2.5.6 |
|---|---|---|
| Standard `specularLevelMap` (SLOT_TABLE before #1729) | `SpecularFactor` | **fail**: «карты metallic и roughness должны использоваться в паре» + «недопустимая карта 'Specular IOR Level'» |
| Standard `reflectionMap` (SLOT_TABLE after #1729) | `ReflectionColor` | pass |
| Physical `metalness_map` | `3dsMax|Parameters|metalness_map` (+ legacy `DiffuseColor`/`ShininessExponent`) | pass |
| customer Ground FBX (Blender-written) | `ReflectionFactor` | pass |

The only difference between the specularLevel and reflection runs is 2.5.6 (the other fails of the minimal package are
the same in all three). SINTEZ source (`scripts/fbx_material_sync.py`, read, not copied) takes Metallic from
`ReflectionFactor`, `ReflectionColor`, `3dsMax|maps|texmap_reflection`, `3dsMax|Parameters|metalness_map`
(`fbxmaps_core.METALLIC_CHANNELS`). Rule: the NPM/VPM `_m` map of a Standard material sits on `reflectionMap`; a map on
`specularLevelMap` is reported by `qa.names_fix`, never renamed `_m` (names_core V2, one slot per role, kept).

## Max FBX import drops customer maps

Customer `0205_ProezdStaropetrovskyi_ZU_7_A_Ground.fbx` (sha256 8cac7c81…, outside git): 8 materials, 23 embedded
maps. Max 2026.3 import (Mode create) connects 15: it drops the 7 `T_ProezdStaropetrovskyi_ZU_7_A_Ground_m_1…7` maps
(`ReflectionFactor`) and the Flora `_o_1` map (`TransparencyFactor`), though it extracts all 23 to `<fbx>.fbm`.
Readback after import (`fbx_maps_readback.py import`): `status=fail embedded=23 connected=15 unconnected=8`, every
unconnected map listed with material, channel and role. `fbxmaps_core.reconnect_plan` + `fbxmaps_max.apply_reconnect`
connect them (`_m` -> Standard `reflectionMap`, `_o` -> `opacityMap`; an occupied slot, unknown channel or missing
material is a named failure): readback after = pass, re-export carries `_m` on `ReflectionColor`, SINTEZ 2.5.6 pass.

Rule: after any customer FBX import in Max run the readback; `passed` only when every embedded map is connected (an FBX
without embedded maps is `no_embedded_maps`, not a pass).

Evidence: `G:/Мой диск/AGR-evidence/1729-metallic-channel/` + `SHA256SUMS.txt` (sha256 64504206558a8d36…; fallback
`C:/x/ev_t_505f2a0e/`). Fixtures (synthetic Max exports, gzip+base64 text, no LFS): `tests/fixtures/fbx_metallic_1729/*.fbx.gz.b64`.
