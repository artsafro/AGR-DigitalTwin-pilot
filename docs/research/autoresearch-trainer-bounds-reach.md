# Autoresearch #103 — can any source-only envelope pass KPP1 `bounds`? (per-face reachability)

**Кратко.** #102 оставил 110 мм на западной грани KPP1 (E1b). Следующая цель из backlog #102 — «вынос столбов с западного фасада из исходника». Вместо подбора ещё одного правила проверяем необходимое условие для ЛЮБОГО правила: есть ли в трёх листах DWG банка (план L03, фасады L01 и L02 с привязкой по осям) хоть одна физическая кромка в пределах 0,10 м от каждой грани ключа. Проверяется только замороженный набор слоёв P (см. ниже); вывод о всех возможных правилах выбора этим условием не доказывается (ревью, раунд 1). OBSERVE: без пересборки, без изменения допусков, без публикации пакетов.

## Frozen contract (committed before the replay script)

- Base `d9af400c08852308f5f618c9bfc0547e067d82ce` (origin/main at card start). Ledger: `artifact` 3/4 (cleared on stored outputs by #100), `sources-dwg` 1/4 (#1874 closed, #1866 owns DXF truncation). Fresh first stop after artifact: KPP1 `bounds` 6/6 (#99). #101/#102 own E1/E1b; this card reuses their frozen layer set and does not add a candidate rule. Not duplicated: #1917 prompts, #1924/#1927 A/B, #1928 adapter, #1866 conversion; form research closed; atlas fallback inactive.
- Pre-freeze exploration (disclosed): ad-hoc ezdxf census on L03/L01 and a fresh Core Console conversion of L02 showed the 200x75 curtain-wall mullion block (`A-GLAZ-CWMG-OTLN`) 420 mm west of axis 1 as the outermost physical west entity on all three sheets, and an open steel door leaf (`A-DOOR-____-OTLN` -> `A-DOOR-____-MCUT`) at 550 mm on L03. Key corner posts/frames (`SM_Kpp_1_Main_Post_*`, `Frame_W01`) reach 530 mm west of axis 1. The expected direction is therefore *west unreachable*; the replay below is the measurement, not the exploration.
- Scope of the claim: rules whose envelope faces are bbox edges of source entities (union or selection), in the r101 frame (`contours.json` origin + shift), facades registered to plan by grid axes 1/4 (X) and А/В (Y) read from `S-GRID-*` lines and their labels on each sheet. Rules that add a constant offset not present in any source are out of scope and named as such.
- Metric `M103(face)`: min over physical entities e of |edge_e(face) − key(face)| in metres, for all six faces, on three layer sets: **P** = frozen r101 `PHYS` (`A-WALL-`, `A-GLAZ-`, `S-STRS-`) after the frozen E1b suffix filter (`-IDEN`, `-TEXT`, `-NOTE`, `-DIMS`); **A** = every layer after the E1b filter, except `G-*` (general annotation) and `S-GRID-*`; **A−door** = A without `A-DOOR-*`. Facade horizontal edges map to X (views S/N) or Y (views W/E); facade vertical edges map to Z for all views. Reported per sheet and for the union of sheets, with the witnessing entity (sheet, view, layer, type, block name).
- H103: on the union of sheets with layer set P, every face has `M103 <= 0.10` m. Refuted if any face has `M103 > 0.10` in all three repeats with calibration and witnesses ok. Confirmed only means *reachable*; it is not a KEEP (no rule, no transfer).
- Calibration (fresh Blender readbacks per repeat, no cache): accepted key vs itself `bounds` pass 0.0 (identity only) and Artem-rejected D380 lattice vs key fails with a larger deviation (native `trainer.bounds_step`). Reachability of the rejected file is not a quality score and is not computed.
- Positive trigger witness (injected, synthetic, per repeat): copy one L03 `A-WALL-` LINE, translate it so its world x_min equals the key west face, keep the layer -> P-west `M103` must become 0.0000; same copy relabelled `A-WALL-TEST-IDEN` -> P-west unchanged (filter exercised). Facade witness: copy one L01 view-S `A-GLAZ-` entity so its registered west edge equals the key west face -> L01 P-west 0.0000. Clean control: P with the suffix filter applied twice gives identical M103 for all faces. Registration control: axis spans 1-4 = 27 000 mm and А-В = 11 000 mm on every view of every sheet, else `inconclusive`.
- Held-out: no eligible independent OKS AIA DWG + accepted FBX exists in the checked Drive sources (#101 AC08, #102 AC05 ruled out; census of `G:/Мой диск/AGR-assets` 2026-11-26: only KPP1, AC08 and site/MAF DWGs). Transfer: **not measured**.
- Budget: 3 repeats, 0 candidates, 300 s total including pre/post hashes; no new repeat when < 60 s remain; stop = `budget stop` -> inconclusive. Forbidden: editing delivered packages or key, tolerance changes, key coordinates in any source rule (key used only for the metric and the synthetic witness), deselecting tests, touching other cards' files.
- Pinned inputs (SHA-256 checked before and after): r101 manifest `l03_dxf`, `l01_dxf`, `frame`, `key`, `rejected`; new `G:/Мой диск/AGR-evidence/1855-r103-bounds-reach/l02.dxf` `c0176ba9faed16ea30af6f6c08cbd1db003db5a5545eb0913257938da1adbcd3` (from L02 DWG `428426002f2642d29e97a8db34053546dc1e427bdff8aeef9ad1c81005b73cb2`, `dwg_to_dxf.py` receipt `38e2d3b5…c309e`, terminal `ENDSEC`/`EOF` present); Blender exe as r102; code parity `tools/trainer/trainer.py`, `tools/blender/fbx_readback.py` at base.

## Replay

```bash
uv run --frozen python docs/research/trainer_bounds_r103/measure.py --out <new empty dir>
```

Needs the r101 commit `d51167a2` locally (`git fetch origin research/autoresearch-standing-101`), the pinned Drive inputs and Blender; replay is limited to hosts with them. The script checks every input SHA-256 before and after and refuses a code drift of `tools/trainer/trainer.py` / `tools/blender/fbx_readback.py` from base. Driver committed at `5381eb17` (SHA-256 `4106480f6a6d4191c9d037763cfcb402476933b677c132cba3d7073467781d98`) before the series; contract at `a97dfb24`.


## Result — OBSERVE, no KEEP (review round 1 rework, receipt schema `r103-receipt/2`)

**Итог.** Гипотеза H103 **опровергнута, но только для замороженного набора слоёв P** (`A-WALL-`, `A-GLAZ-`, `S-STRS-` после фильтра E1b), объединённого по трём листам DXF: ни одна читаемая кромка P не подходит к западной грани ключа (−15,185 м) ближе 0,11002 м при допуске 0,10 м. Ближайшая кромка — импост витража 200x75 (`A-GLAZ-CWMG-OTLN`, −15,0750 м), одинаковая на L03, L01 и L02. Остальные пять граней в пределах 0,02 м.

Чего этот результат **не** доказывает (исправление вывода раунда 1):
- Он не доказывает, что `bounds` нельзя пройти никаким выбором элементов. Выбор S из ревью (L03 `1195`, `1562`, `15E8`; L01 `ADC`, `1832`; L02 `13C2`) даёт в штатном `trainer.bounds_step` **pass**, `max_corner_dev_m = 0.02`, ×3. В S входит открытое дверное полотно `15E8` (`A-DOOR-____-OTLN`, −15,2050 м). Как замена стойкам это архитектурно недопустимо, но численно это контрпример к общему утверждению.
- Он не доказывает, что стоек нет во всех исходниках. Проверена только читаемая непустая геометрия DXF. На L01 и L02 по 245 INSERT слоёв P имеют пустые определения блоков (системные панели — 99 имён, `MEP_Окно_Витражное` — 21, решётки `MEP_Веза_Р50` — 11). Есть ли в них геометрия в самом DWG, **не измерено**.
- Отдельное наблюдение, без вердикта: в наборе A−door (все слои без аннотаций и без `A-DOOR-*`) западная грань тоже даёт 0,11002 м.

Вопрос владельцу банка остаётся тем же, но теперь это открытый вопрос, а не доказанный факт: стойки ключа (`SM_Kpp_1_Main_Post_NW/SW`, `Frame_W01`) взяты из квад-сетки v003 по R1 (`jobs/KPP1/lattice-1609/README.md`, шаг 3; [D376]).

Three complete repeats, wall 142.696 s (43.927 / 46.405 / 51.786 s), no budget stop, input parity before/after passed, `P_complete` true. Receipt [`receipt.json`](trainer_bounds_r103/receipt.json) SHA-256 `9afa26e3bda240a492b37736bb6bf923e0f401c2d191a2ab094a7265d8cf1e51`; Drive copy `r103-receipt-r2.json` + L02 DXF + round-0 receipt in `G:/Мой диск/AGR-evidence/1855-r103-bounds-reach/SHA256SUMS.txt` (SHA-256 `7983ecd73c897284cb5217dc8ef1ab80fdc82e631ad7133b5fd3907d22c513b0`). Driver `measure.py` SHA-256 `e13fdf71dcbebcd88da5a95728c6e358e1b930b859313cce3244881c6b96efa4`.

| Face (key, m) | P union, raw min abs distance, m | witness | A − door union |
| --- | ---: | --- | ---: |
| x_min (−15.185) | **0.11002** (×3, > 0.10) | L03 / L01 / L02: `A-GLAZ-CWMG-OTLN` mullion | 0.11002 |
| y_min (−6.385) | 0.00000 | L03 `A-WALL-____-MCUT` | 0.00000 |
| z_min (0.0) | 0.02000 | L01/L02 `A-WALL-____-PATT` | 0.00000 |
| x_max (16.6755) | 0.00048 | — | 0.00048 |
| y_max (6.6746) | 0.00037 | — | 0.00037 |
| z_max (8.65) | 0.00000 | facade top | 0.00000 |

Decisions use raw distances; the table and `abs_m` fields are rounded for display only. Paired spread 0 across repeats.

### Checks (clean, injected, review rows, not measured)

- Calibration (fresh Blender readbacks each repeat): key vs itself `pass` 0.0000, Artem-rejected D380 `fail` 3.8005 m — ok ×3.
- Registration: plan 1-4 = 27 000.0 mm, А-В = 11 000.0 mm; 4 elevations per facade sheet, spans within 5 mm — ok ×3.
- Injected witnesses (synthetic copies): plan `A-WALL-` LINE on the key face -> P x_min 0; relabelled `-IDEN` -> unchanged; L01 `A-GLAZ-` insert on the face -> L01 x_min 0; clean re-filter parity — ok ×3.
- Source inventory per sheet and set (`inventory` in the receipt): every entity on kept layers is `ok`, `empty_def` (definition exists, no entities; listed by block name) or unread (`missing_def`, `bbox_error`, `no_extent`). Any unread entity in P makes the verdict `inconclusive`. Measured: unread 0 on all sheets and sets; `empty_def` P: L03 0, L01 245, L02 245.
- Review row 1 (selection S, real sources): `trainer.bounds_step` pass 0.02 ×3; envelope x_min −15.2050 (door leaf).
- Review row 2 (synthetic, per repeat): `A-WALL-____-MCUT` INSERT with a deleted definition + an empty-definition INSERT + a valid wall -> counts `missing_def 1 / empty_def 1 / ok 1`, `complete false`, verdict `inconclusive` — ok ×3. (Round 0 silently dropped such an INSERT: ezdxf raises on the missing definition and the old `except: continue` hid it.)
- Review row 3 (synthetic, per repeat): raw distance 0.10004 -> oracle `refuted`, native `bounds` `fail`; 0.10000 -> oracle reachable, native `pass` — ok ×3.
- Regression tests: `tests/research/test_trainer_bounds_r103.py` (7 tests: missing definition, empty definition, bbox error, tolerance boundary ×2, selection envelope, in-run checks): 7 failed on the round-0 driver, 7 passed on this one.
- **Not measured:** transfer to an independent OKS etalon (none eligible: AC08 #101, AC05 #102, Drive census); geometry inside the empty-definition blocks in the DWG; rules with constant offsets; fresh-agent behaviour; packaging.
- Disclosed: round-0 series (`8a77ee8f`, receipt `0bc8d2e7…1245`, 121.9 s) gave the same P numbers; it is superseded, not reused as evidence. Pre-series `dry1`/`dry2` as disclosed in round 0.

Full suite: deferred to merge batch (rule 68). No product code changed.

Next: (1) bank owner decision for KPP1 (#1861/#1855): add the R1 source that carries the corner posts, or document that the bounds key includes inset posts not in the DWG sheets; (2) check whether the empty-definition curtain-wall blocks carry geometry in the DWG (a DWG-side read, e.g. Core Console `LIST`/`BCOUNT`, or the #1866 converter) before any "absent from sources" claim; (3) an independent AIA plan/facade + accepted FBX pair is still needed for any transfer claim.
