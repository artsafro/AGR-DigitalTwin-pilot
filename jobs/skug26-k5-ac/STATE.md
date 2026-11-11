Current run: K5_VPM_textured_UV_v003.max viewport texture/hole layout accepted on 2026-11-05; not a delivery.
Source: K5_VPM_textured_UV_v002.max, hidden-layer SKUG-26_PP_AR_K5_fsd FBX hole geometry, konderi.psd (Inputs below).
Next gate: unknown — no next gate selected; FBX export, validate-delivery and cutout render remain undone.

# SKUG-26 K5 — conditioner screens, VPM texture 4K with alpha (UDIM 1004)

Status: **accepted by the user** (Artem, 2026-11-05: «Видны, принято») — the texture and the hole layout
seen in the 3ds Max viewport of v003. Not a delivery: no FBX export, no validate-delivery, no render.

## Requirement (Artem, 2026-11-05)

> «Object 004 и Object 005. Это двое кондиционер. Мне нужно сделать для них VPM текстуру 4К с альфа-каналом.
> И разложить полигоны кондиционеров на эту текстуру в UDIM таким образом, чтобы количество кружочков
> перфорации было как на скриншоте. То есть, чтобы попасть и по текселю, и по количеству кружочков. Также есть
> второй слой, там лежит FBX с которого, собственно, и надо брать кружочки у кондиционеров.»

Intake answers: texel 1300 px/m (as in the user's draft `konderi.psd`); holes alpha 0 on RAL1015; flat ERM + Normal
4K; save as v003 + PNG next to it, v002 untouched. After review: holes also dark in RGB (60,60,60), otherwise the
holes are invisible against the beige wall behind them.

## Inputs (`C:/Users/artsafro/Desktop/!3D viz/!А101/62_26sk_pravki/Pravki_november/`, SHA256 prefix)

- `K5_VPM_textured_UV_v002.max` `DE274321433D0B10` — 3ds Max 2024, metres. Conditioners inside Object002, mat ID 4
  (378 faces); the user's Object004/005 were never saved and were re-detached here.
- Hidden layer `SKUG-26_PP_AR_K5_fsd` (4.3 M faces) = `fbx/SKUG-26_PP_AR_K5_fsd_объединенный.fbx` `A7A8635F46657621`:
  perforated plates as geometry — hole source of truth.
- `konderi.psd` `F56AC75637BDB748` — the user's earlier 4K draft (RGB, 4 islands); same counts as the FBX.

## Measured on the FBX (holes.py, phase.py; D 50 mm, all elements)

| Screen | Object | Elements | Face (m) | Front holes | Side holes |
|---|---|---|---|---|---|
| horizontal | Object004 | 16 | 1.903 × 0.58, side 0.685 | 18 × 5 = 90, centred | 5 × 5 = 25, centred |
| vertical | Object005 | 110 | 1.20 × 1.944, side 0.685 | 10 × 18 = 180, margins 0.125 / 0.22 (66 left, 44 mirrored) | 4 × 18 = 72, nearer the wall |

FBX plates are 0.595 deep (model 0.685) and 0.60 / 1.95 high (model 0.58 / 1.944): pitch kept from the FBX, the
extra depth split between margins in the FBX proportion.

## Outputs

- `K5_VPM_textured_UV_v003.max` `FC54F439957392B9`: Object004 (48 faces) and Object005 (330) detached from
  Object002; UV ch1 only, tile 1004, 4 stacked islands; M_K5_AC_RAL1015 got new bitmaps + cutout from the diffuse
  alpha (other sub-materials untouched).
- `konder_tex/textures/T_K5_Diffuse_AC.1004.png` `739381B74AFE5248` (RGBA), `T_K5_ERM_AC.1004.png`
  `A8FC6E0E8C2D6F2C` (0,128,0 as the old AC ERM), `T_K5_Normal_AC.1004.png` `9CD7C44E0E9538F3` (flat); 4096².
- `konder_tex/layout_AC_1004.json`, `preview_AC_1004.png`, `uv_overlay_AC_1004.png`.

## Checks run

- Texel 1300.0 px/m on every edge > 5 cm of both objects (uvcheck in Max); island bounds as designed.
- uvverify.py: 367 holes in the texture; every face holds exactly its count — 16 × 90, 32 × 25, 110 × 180, 220 × 72;
  all faces in UDIM 1004. PNG headers: 4096², Diffuse RGBA, ERM/Normal RGB.
- Viewport capture of v003: holes visible (user confirmed). Cutout see-through not shown in Default Shading.

## Not done / open

- FBX export, validate-delivery, render with the cutout; naming against the regulation (`T_{Address}_...`) follows
  the scene's existing `T_K5_*` scheme, not checked.
- ERM non-metallic (kept from the scene); thin-walled / double-sided not set.

## Scripts (`scripts/`)

`holes.py` (hole grid of one exported plate), `phase.py` (margins per element), `make_ac_tex.py` (maps + layout),
`uv_ac.ms` (UV), `uvdump.ms` + `uvverify.py` (UV readback, holes per face). Paths inside are this session's.
