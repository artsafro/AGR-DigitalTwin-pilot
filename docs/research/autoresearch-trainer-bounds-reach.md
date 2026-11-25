# Autoresearch #103 — can any source-only envelope pass KPP1 `bounds`? (per-face reachability)

**Кратко.** #102 оставил 110 мм на западной грани KPP1 (E1b). Следующая цель из backlog #102 — «вынос столбов с западного фасада из исходника». Вместо подбора ещё одного правила проверяем необходимое условие для ЛЮБОГО правила: есть ли в трёх листах DWG банка (план L03, фасады L01 и L02 с привязкой по осям) хоть одна физическая кромка в пределах 0,10 м от каждой грани ключа. Если на грани такой кромки нет, ни одно правило «объединение габаритов исходных элементов» не пройдёт `bounds`, и вопрос уходит владельцу банка, а не в следующий раунд подбора. OBSERVE: без пересборки, без изменения допусков, без публикации пакетов.

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

## Result — OBSERVE, no KEEP

**Гипотеза H103 опровергнута.** Ни одно правило «габарит = объединение/выбор исходных элементов» не может пройти `bounds` KPP1 по трём листам DWG банка: западная грань ключа (угловые стойки `SM_Kpp_1_Main_Post_NW/SW` и рама `Frame_W01`, −15,185 м) на 110 мм западнее самой западной физической кромки в любом листе — импоста витража 200x75 (`A-GLAZ-CWMG-OTLN`, −15,0745 м) на плане L03 и на фасадах L01 и L02. Допуск 100 мм. Остальные пять граней достижимы (≤ 20 мм). Единственный элемент, который «достаёт» до плоскости стоек, — открытое полотно наружной двери на плане (`A-DOOR-____-OTLN`, −15,205 м, 20 мм): это не граница здания, совпадение, а не правило. Значит, 110 мм остатка #102 — не дефект фильтра, а данные, которых нет в исходниках задачи: стойки ключа взяты из квад-сетки v003 по R1 (`jobs/KPP1/lattice-1609/README.md`, шаг 3; [D376]). Вопрос владельцу банка (#1861 / #1855), не новый раунд подбора.

Three complete repeats, wall 121.934 s (40.124 / 40.919 / 40.209 s per repeat), no budget stop, input parity before/after passed. Receipt [`receipt.json`](trainer_bounds_r103/receipt.json) SHA-256 `0bc8d2e79c091793d180804ea45bb7585050dba5b7e610077a6e193ecce01245`; Drive copy + L02 DXF in `G:/Мой диск/AGR-evidence/1855-r103-bounds-reach/SHA256SUMS.txt` (SHA-256 `9a97e52af6621bffb5dbcef31ee827cfd21a2c034acf4e79eb7f719c3a7a7db6`).

| Face (key, m) | P union: min abs edge distance, m | witness | A union | A − door |
| --- | ---: | --- | ---: | ---: |
| x_min (−15.185) | **0.1100** (×3) | L03 plan / L01, L02 view S: `A-GLAZ-CWMG-OTLN` mullion | 0.0200 (door leaf, spurious) | **0.1100** |
| y_min (−6.385) | 0.0000 | L03 `A-WALL-____-MCUT` | 0.0000 | 0.0000 |
| z_min (0.0) | 0.0200 | L01/L02 `A-WALL-____-PATT` | 0.0000 | 0.0000 |
| x_max (16.6755) | 0.0005 | — | — | — |
| y_max (6.6746) | 0.0004 | — | — | — |
| z_max (8.65) | 0.0000 | facade top | — | — |

Identical in all three repeats (paired spread 0). Per sheet, P x_min is 0.1100 on L03, L01 and L02 separately — three independent drawings agree.

- Calibration (fresh Blender readbacks each repeat): accepted key vs itself `pass` 0.0000 (identity only), Artem-rejected D380 lattice `fail` 3.8005 m — ok ×3.
- Registration: plan axes 1-4 = 27 000.0 mm, А-В = 11 000.0 mm; four elevations per facade sheet found by axis pairs, all spans within 5 mm on L01 and L02 — ok ×3.
- Injected witnesses (synthetic copies, sources untouched): plan `A-WALL-` LINE moved to the key west face -> P x_min 0.0000; same copy relabelled `A-WALL-TEST-IDEN` -> 0.1100 unchanged (filter exercised); L01 view-S `A-GLAZ-____-OTLN` insert moved so its registered west edge hits the face -> L01 x_min 0.0000 (facade registration exercised). Clean re-filter parity true. All ok ×3.
- **Not measured:** transfer to an independent OKS etalon (none eligible: AC08 #101, AC05 #102, Drive census here); rules with constant offsets (e.g. «posts 200 mm proud»), which are outside the claim; fresh-agent behaviour; packaging.
- Disclosed pre-series runs: `dry1` crashed (facade views rebuilt from a pre-filtered stream), `dry2` used a wall hatch instead of the frozen A-GLAZ entity for the facade witness; both fixed before the commit `5381eb17`. Same numbers as the series; not used as evidence.

Full suite: deferred to merge batch (rule 68). No product code changed.

Next: (1) bank owner decision for KPP1: add the R1 source that carries the corner posts to the task, or document that the bounds key includes inset posts not in the DWG sheets (then a 0.11 m west miss is expected); (2) only after that, re-run the r102 E1b envelope; (3) an independent AIA plan/facade + accepted FBX pair is still needed for any transfer claim.
