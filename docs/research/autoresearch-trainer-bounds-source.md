# Autoresearch #101 — trainer: KPP1 `bounds` from the DWG sources only (OBSERVE)

**Кратко (RU).** После того как `artifact` закрыт (#95–#100), чаще всего прогон останавливается на `bounds`:
KPP1 — 6/6 прогонов #99 (4 из 6 с отклонением 4.0647 м), 63B (отложенный) — тоже `bounds`. Здесь мы проверяем,
можно ли получить габарит KPP1 **только из DWG** (без ключа) и какой член ошибки остаётся. Правило E1 (ниже)
берёт план L03 и фасады L01 по слоям стен/остекления/лестниц. Изменений продукта нет, это наблюдение.
Результат — в разделе «Result».

Status: **contract frozen before the r101 series** (commit of this file precedes `measure.py` results).

## Target and ownership

- Ledger `docs/trainer/ledger.json` @ `d9af400c`: `artifact` 3/4, `sources-dwg` 1/4. `artifact` is cleared on stored
  outputs (#100 receipt 0/3 → 3/3). Next stop on fresh runs: `bounds` (KPP1 6/6 in #99 receipt; 63B held-out in #100).
- Not owned elsewhere: #96 listed "KPP1 L01 levels + east extent" as its next target and did not run it; #1924/PR #1927
  (A/B harness), #1928 (G22 adapter), #1917 (FBX-first prompt) do not touch bounds. Form research is closed.
- Honesty note: the per-mesh key bounds of KPP1 were read **before** this freeze (exploration, this card). KPP1 is the
  `tuning` split; numbers on KPP1 are attribution, not evidence of transfer. Transfer evidence must come from the
  held-out fixture below.

## Rule E1 (frozen, source-only, no key input)

- Plan (L03 DXF, mm): plan box = union bbox of all `A-WALL-*` entities, dilated by 5000 mm. Footprint XY = union bbox of
  entities on `A-WALL-*`, `A-GLAZ-*`, `S-STRS-*` whose bbox lies fully inside the plan box. Plan → world = the agents'
  own frame from r99-C1 `contours.json` (`origin_mm`, `frame_shift_m`; produced by `plan_from_dxf.py`, no key).
- Facades (L01 DXF, mm): Z1 = max Y of entities on `A-WALL-*`, `A-GLAZ-*`, `S-STRS-*` / 1000 (facade datum DXF y = 0
  = ±0.000; checked by the level-mark text offset mode). Z0 = 0.000.
- Not used: level-mark texts as the top (agents' rule; recorded as perturbation P2), any key value.

## Metric

- **M101** = native `tools/trainer/trainer.py::bounds_step` `max_corner_dev_m` (tol 0.10 m, unchanged) of the E1
  envelope vs the native readback of the KPP1 key. Baseline B = the same step on each of the six #99 built FBXs
  (fresh native readback). Also reported: per-face deviations (6 values), and for each run the east term after the
  union of its built box with the E1 `S-STRS` box (what an annex would add).
- Positive trigger witness / perturbations (expected direction, bounds):
  P1 = E1 without `S-STRS` → east term ≥ 3.9 m (reproduces the 4.0 m agent miss);
  P2 = E1 with Z1 = max level-mark text value on L01 → top term ≥ 0.2 m;
  P3 = E1 with `A-GLAZ` dropped → recorded, no bound expected.
- Calibration (native step, unchanged): key vs key = 0.0 (accepted); Artem-rejected KPP1 step-3 lattice master
  (`1609-kpp1-lattice-posts/step3`, [D380]) vs key must be **> 0** (strictly worse) — if equal, bounds cannot rank
  this pair and that is reported as "bounds does not separate", not as a failed calibration of E1.
- Held-out (not used for tuning): TEC26 AC08 DWG (`22E56-AR2-1002-AC08.dwg`, same 22E56 АР2 project family) vs AC08
  v010 master `SM_Nku_1_quads_review.fbx`. Frame unknown → compare sizes (dx, dy, dz) only. If E1 finds no
  `A-WALL-*` entities the held-out is `not_exercised` → **not measured** (no transfer claim).

## Hypothesis H101 and verdict rules

H101: E1 reduces the KPP1 bounds max corner deviation from ≥ 4.0 m (all six #99 runs) to ≤ 0.25 m; it does **not**
pass 0.10 m (expected remaining west term ≈ 0.2 m from facade posts that are not on the plan physical layers).
Confirmed only if KPP1 numbers hold in 3/3 repeats **and** the held-out is exercised with size deviation ≤ 0.25 m;
refuted if the held-out is exercised and deviates more; inconclusive if the held-out is not measured or a native
tool fails.

## Budget, stop rule, forbidden shortcuts

- 3 repeats, fresh readback folder each (readbacks are not cached between repeats); budget 900 s wall for the series;
  no new score launch with < 60 s left; a budget stop = inconclusive for that run. One variant (E1) + P1–P3 only;
  no new candidate after the first repeat.
- Forbidden: changing tolerances or `trainer.py`, choosing layers per fixture after seeing the held-out, editing
  delivered packages or bank files, using key geometry inside E1, touching other cards' files.
- Parity: all inputs pinned by SHA-256 in `trainer_bounds_r101/manifest.json`; the script aborts on any mismatch and
  re-hashes after the series.

## Replay

`uv run --frozen python docs/research/trainer_bounds_r101/measure.py --out C:/x/<new-dir>` (new folder; needs the
Drive/local fixtures in the manifest; the KPP1 DXFs and frame are mirrored to
`G:/Мой диск/AGR-evidence/1855-r101-bounds-source/` with `SHA256SUMS.txt`). Replay limited to hosts with that Drive
and Blender 5.1.

## Result

**H101: опровергнута в замороженном виде (refuted), перенос не измерен.** Правило E1 как заморожено даёт на KPP1
0.5396 м (а не ≤ 0.25 м): префикс `A-WALL-*` захватил слой марок стен `A-WALL-____-IDEN` (аннотация, на 0.54 м
западнее стены). Отложенный AC08 — `not_exercised`: в его DWG нет слоёв `A-WALL-*` (слои СПДС / PDF-импорт), так
что о переносе правила ничего не сказано (**not measured**). Улучшения продукта нет, KEEP нет.

Что измерено (receipt `trainer_bounds_r101/receipt.json`, SHA-256
`d4b08afccb449223ba5e7fbab3708077e394dcc824247fb81f6061a70ff96654`; 3/3 repeats, all values identical, paired
spread 0; series wall 57.1 s, repeats 20.8 / 17.2 / 16.4 s; no budget stop; input parity before and after = true):

| Variant (KPP1, native `bounds_step`) | max dev, m | x_min | y_min | z_min | x_max | y_max | z_max |
|---|---|---|---|---|---|---|---|
| E1 (frozen) | 0.5396 | −0.5396 | −0.0311 | 0 | −0.0005 | 0.0004 | 0 |
| P1 no `S-STRS` (witness) | 4.0005 | −0.5396 | −0.0311 | 0 | **−4.0005** | 0.0004 | 0 |
| P2 top = max level mark (agents' rule) | 0.85 | −0.5396 | −0.0311 | 0 | −0.0005 | 0.0004 | **+0.85** |
| P3 no `A-GLAZ` | 0.5396 | −0.5396 | −0.0311 | 0 | −0.0005 | 0.0004 | 0 |

- Calibration (native, unchanged): accepted key vs key 0.0 pass; Artem-rejected step-3 lattice master 3.8005 fail →
  rejected scores worse. Positive witness P1 reproduces the agents' 4.0 m east miss (bound ≥ 3.9 m met); P2 the
  level-mark top (+0.85 m, bound ≥ 0.2 m met). P3 had no expected bound (no effect).
- Attribution of the six #99 runs (baseline native max dev 4.0647 ×4, 4.0005, 40.7395): the east term is the exterior
  stair/porch on L03 `S-STRS-____-OTLN` (source x_max = key x_max within 0.5 mm; key mesh `SM_Kpp_1_Main_Annex_E01`,
  Z 0–3.9 = L01 `S-STRS` top 3.9). The agents' wall-hatch contour drops it. After a union with the source `S-STRS` box,
  the next term per run: C1 0.25 (top +8.900 level mark vs physical 8.65), D2 0.741 (top 7.909 roof band), C3/D1/D3
  1.0–1.1 (z_min below ±0.000), C2 36.47 (placement), plus x_min +0.2 in five runs (west facade posts, not on plan
  physical layers).
- Top: max Y of `A-WALL`/`A-GLAZ`/`S-STRS` on the L01 facades = 8.650 m = key top; level marks reach 9.5 m (equipment,
  `M-EQPM`/`M-HVAC` up to 9.925 m). Facade datum check: mark text offset mode 830 mm (80 marks) → DXF y 0 = ±0.000.
- Post-hoc, **not a result** (variant chosen after seeing E1, KPP1 only): E1b = E1 without `*-IDEN/-TEXT/-NOTE/-DIMS`
  layers → 0.11 m (x_min +0.11: `A-GLAZ-CWMG` at −15.075 vs posts at −15.185). `trainer_bounds_r101/e1b_posthoc.json`.
- Side finding (sources-dwg, out of scope): `dwg_to_dxf.py` reports `pass` for AC08 although the DXF stops before the
  terminal ENDSEC/EOF (log: "Custom object(s) encountered", same 2 690 929 bytes on two runs); `dxf_intake.py` would
  reject it. Held-out read here with `ezdxf.recover` (2 fixes).

Evidence: `G:/Мой диск/AGR-evidence/1855-r101-bounds-source/` (`SHA256SUMS.txt` SHA-256
`371a2dfe5b1efc379914c016b65719b190a599e0d47b5d1b91b452e8870fe155`).

Next (not run): (1) E1b as a frozen candidate + a held-out OKS DWG with AIA (Revit-export) layers; (2) teach the
agent route to keep `S-STRS` exterior stairs as an annex volume and take the top from physical facade layers, then
fresh KPP1 runs; (3) make `dwg_to_dxf.py` fail on a DXF without terminal `0/EOF` (AC08 custom objects).
