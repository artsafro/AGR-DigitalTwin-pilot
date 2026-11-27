# Cold OKS run, Sokolniki NPM: evaluator protocol and controls (#2001, Refs #1784)

A FRESH builder on a fresh clone builds the Sokolniki NPM package from the Revit sources following only
`routes/npm-oks.md` + `docs/agents/SKELETONS.md`; the evaluator scores the run against the frozen key
(the accepted package of [D419] on body v006 / assembly v009 [D409], atlas layout [D413]). This card
prepares the evaluator only — nothing was built. Blender 4.4 headless; 3ds Max not used.

| Item | Location | SHA-256 |
|---|---|---|
| Key (24 files, outside every clone; never named to the builder) | `G:/Мой диск/AGR-evidence/1784-cold-oks/key/` | `SHA256SUMS.txt` `3d761995d2bd2de1eb0c60caf6e0aa71529460e28516667242259c5f3ea0e320` |
| Builder prompt | `G:/Мой диск/AGR-evidence/1784-cold-oks/builder-prompt.md` | listed in the folder `SHA256SUMS.txt` |
| Evaluator outputs (fingerprints, control FBX, xView, scores, provenance) | `G:/Мой диск/AGR-evidence/1784-cold-oks/evaluator/` | folder `SHA256SUMS.txt` `24af0567a39abb90963454ea8f907d5ebfe4f5bffb5c79879ee17998035df3ae` (90 files, key excluded) |
| Builder sources (copies) | `C:/x/2001-cold-oks/sources/` | Revit FBX `feaae527…fe9c` (= the #1784 source), PDF `fd650339…0250` |
| Scorer | [cold_oks_score.py](cold-oks-sokolniki-2001/cold_oks_score.py) | — |

Key content: `package_v001/` (ZIP, build manifest, readback, work quads FBX, xView, `agr validate`),
`master_v002/`, `atlas/` (`npm_atlas.json`, atlas PNGs, accepted zoning sheet v002 PDF + table),
`body_v006/` (quad FBX, `meshes.json`, build / openings reports, config, xView), `assembly_v009/`. Every
file matches its origin manifest in `1784-sokolniki-lattice/` (`evaluator/key-provenance.tsv`: 24/24 `match`).

## Протокол оценки (RU)

Оценщик не участвует в прогоне и только отвечает на STOP-вопросы ответами из принятых решений
([D375] [D378] [D390] [D408]–[D419]), дословно, без подсказок сверх вопроса.

1. **Ключ.** `keycheck`: все файлы ключа совпадают с `SHA256SUMS.txt`, лишних нет. Иначе ключ
   устаревший: все стадии `not_scored`, 0 проходов (fail closed). Отпечаток ключа принимается, только если его
   `source_sha256` равен строке файла в `SHA256SUMS.txt`.
2. **Отпечаток.** Каждый FBX / ZIP кандидата и ключа читается Blender 4.4 headless (`fingerprint`): мировые
   координаты вершин каждой грани, материал, UV-центр и UV-площадь. Дальше — только stdlib Python.
3. **Стадии** `routes/npm-oks.md`: 0 подготовка сцены, 1 источники, 2 детали / Gate 1, 3 BODY, 3i вставки
   по плану моделирования, 4 детализация фасада, 5 NPM / атлас, 6 поставка, 7 отчёт / визуал, 8 чекер.
   Для каждой: pass / fail / not_reached и **первая проваленная проверка**; итог — число пройденных стадий
   и первая проваленная стадия.
4. **Геометрия (3, 3i, 5) против ключа**, допуск 0,10 м (факт: 5–10 см):
   - `transform_bbox`: углы габарита <= 0,10 м;
   - `surface_cover`: >= 0,95 площади ключа лежит в 0,10 м от поверхности кандидата (точка–треугольник);
   - `facade_cover`: каждый фасад ключа >= 20 м² покрыт >= 0,90;
   - обратное направление (кандидат -> ключ, лишняя геометрия): `surface_precision` — >= 0,95 площади
     кандидата лежит в 0,10 м от ключа; `facade_precision` — каждая фасадная группа кандидата >= 20 м²
     лежит у ключа >= 0,90 (придуманная стена / второй слой проваливают стадию);
   - стадия 3: `lattice_levels` / `lattice_stations` — >= 0,95 длины линий решётки ключа (горизонтальные
     уровни по Z, вертикальные станции по XY) найдены в 0,10 м;
   - стадии 3 и 5: `openings` — >= 0,95 проёмов ключа (грани окон / дверей / витражей, связанные общим
     ребром) совпадают по всем четырём краям в плоскости фасада в 0,10 м (полнота), **и** >= 0,95 проёмов
     кандидата есть в ключе (точность: придуманные проёмы проваливают стадию);
   - стадии 3i и 5: `material_ids` — >= 0,90 площади ключа имеет у ближайшей грани кандидата тот же финиш
     (кандидат сопоставляется с 14 финишами паспорта PDF через `finish_map`, который пишет оценщик);
   - стадия 5: `uv_outside_atlas` = 0 граней, `uv_density` — px/м по финишу 0,5–2× ключа;
   - `tris`: 0,5–2× ключа и <= 150 000; `xview`: перекрытия граней / вершин не больше, чем у ключа.
5. **Поставка (6):** каждая V-проверка `agr validate`, проходящая у ключа, проходит у кандидата.
6. **STOP-точки** (продуктовые решения Артёма): S0-split, S1-authority, S2-parts, S3-lines, S3-cuts,
   S3-openings, S3i-plan, S3i-wells, S5-zoning, S5-windows, S6-contacts, S6-scope, S7-acceptance. Решение без
   вопроса — провал стадии, даже если результат совпал с ключом. Оценщик сопоставляет файлы
   `STOP-<nn>-<topic>.md` строителя с этими id. Включает и выключает оценку STOP только оценщик
   (`score_stops` в `evaluator/key_set.json`); такой ключ в `run.json` строителя игнорируется.
7. **Пустая стадия не проходит.** Стадия без единой проверки — `not_scored`; процессная стадия (0, 1, 2, 4, 7, 8)
   без доказательства — `fail`. Доказательство — существующий **файл внутри папки прогона** строителя
   (папка `run.json`); путь вне её или каталог (например `C:/`) — `fail`.
8. **Процесс:** токены и время (`run.json`), свои скрипты против переиспользования скелета (`own_scripts`,
   `commands.log`: вызовы `agr` / `dt` / `tools/` против `jobs/sok-cold-2001/hooks/`), заражение (открытые
   запрещённые пути) — в отчёт, не в проход.

## Scoring protocol (EN)

The evaluator stays out of the run and answers STOP questions only, verbatim from the accepted decisions.

1. **Key.** `keycheck` verifies every key file against `SHA256SUMS.txt` and refuses unlisted files; a stale or
   edited key scores every stage `not_scored`, 0 passes. A key fingerprint counts only if its `source_sha256`
   equals the listed hash of its key file.
2. **Fingerprint.** Blender 4.4 headless reads each FBX / ZIP (world vertices per face, material, UV centroid
   and UV area); the rest is stdlib Python.
3. **Stages** of `routes/npm-oks.md` (0, 1, 2, 3, 3i, 4, 5, 6, 7, 8): pass / fail / not_reached plus the first
   failing check; the run result is the number of passed stages and the first failing stage.
4. **Geometry against the key (3, 3i, 5), tolerance 0.10 m:** bbox corners; surface cover >= 0.95 (exact
   point-to-triangle distance); every key facade >= 20 m² covered >= 0.90; the reverse direction (candidate ->
   key, extra geometry): candidate area within 0.10 m of the key >= 0.95 and every candidate facade group
   >= 20 m² >= 0.90; body lattice levels and stations recall >= 0.95; openings (faces joined by a shared edge)
   recall >= 0.95 **and** precision >= 0.95 (invented openings fail) on all four in-plane edges; material IDs >= 0.90 of key area
   (candidate finishes mapped to the 14 PDF passport finishes by the evaluator's `finish_map`); NPM UV:
   0 faces outside the atlas regions, px/m per finish 0.5–2x the key; tris 0.5–2x the key and <= 150 000;
   xView overlaps no worse than the key.
5. **Delivery (6):** every `agr validate` V-check that passes on the key passes on the candidate.
6. **STOP points** (product choices that are Artem's): a choice made without asking fails the stage even
   when it matches the key. Only the evaluator switches STOP grading (`score_stops` in `evaluator/key_set.json`);
   the same key in the builder's `run.json` is ignored.
7. **No vacuous pass.** A stage with no checks is `not_scored`; a process stage (0, 1, 2, 4, 7, 8) without
   evidence fails. Evidence is an existing **file inside the builder's run folder** (the folder of `run.json`);
   a path outside it or a directory (e.g. `C:/`) fails.
8. **Process:** tokens / time, own scripts vs skeleton reuse, contamination — reported, not scored.

Commands (evaluator):

```
blender -b --factory-startup --python-exit-code 1 --python docs/research/cold-oks-sokolniki-2001/cold_oks_score.py -- fingerprint CAND.fbx|CAND.zip FP.json
uv run dt qa xview CAND.fbx --out XV.json --profile NPM
python docs/research/cold-oks-sokolniki-2001/cold_oks_score.py keycheck "G:/Мой диск/AGR-evidence/1784-cold-oks/key"
python docs/research/cold-oks-sokolniki-2001/cold_oks_score.py score KEY_DIR evaluator/key_set.json CAND.json SCORE.json
```

`CAND.json` is the builder's `run.json` with `fingerprint` (and `finish_map` for 3i / 5) filled in by the
evaluator. Control drivers: `evaluator/controls.sh` (perturb + fingerprint + xView) and
`evaluator/run_controls.py` (scores).

## Controls (scorer proven before any cold run)

| Control | Expected | Result (passes / first failing) | Key measurements |
|---|---|---|---|
| C1 key itself (stages 3, 3i, 5, 6) | pass | **4 / none** | all checks pass; surface / facade precision 1.0; openings recall = precision = 1.0 (292 / 307) |
| C2 key re-exported by Blender, no change | pass | **3 / none** | proves the FBX roundtrip adds no fail (precision 1.0 both ways) |
| C3 key shifted +0.20 m X | fail | **0 / 3: transform_bbox** | bbox 0.20 m; surface cover 0.657 / 0.637 / 0.619, precision 0.658 / 0.634 / 0.615; stations recall 0.161; NPM openings 0.355; asm material IDs 0.566 |
| C4 one facade missing (az 270, 865–1 011 m²) | fail | **0 / 3: surface_cover** | facade az270 cover 0.003 (body) / 0.23 / 0.225; openings 0.801 (58 of 292 missed) / 0.811 (58 of 307) |
| C5 body v005 (superseded: blind where Revit has glass, [D408]) | fail | **0 / 3: surface_cover** | openings recall 0.839: **47 of 292 missed = exactly the 47 openings [D408] cut**; no roof wells ([D410]) -> surface cover 0.491, precision 0.529; levels 0.923, stations 0.826 |
| C6 stale key (body file replaced, `SHA256SUMS.txt` unchanged) | 0 pass | **0 / key_stale** | all 10 stages `not_scored` |
| C7 key body + invented interior wall (40 quads, 241 m², review r1 R1) | fail | **0 / 3: facade_precision** | group az000@+26 within 0.10 m of the key 0.005; whole-model precision stays above 0.95 — the per-facade gate catches it |
| C8 key body, every blind face labelled WINDOW (r1 R2) | fail | **0 / 3: openings** | recall 1.0, precision 0.315 (636 of 928 candidate openings invented) |
| C9 stages 4 `{}`, 8 evidence `C:/`, 0 with builder `"score_stops": false` (r1 R3 / R4) | fail | **0 / 0: stop S0-split** | stage 0 fails the STOP despite the builder switch; 4 and 8 fail `evidence` |

Synthetic regressions of the same rules: `tests/test_cold_oks_score_2001.py` (key passes, +0.20 m shift,
missing facade, blind openings, stale key = 0 passes, unasked STOP fails the stage; review r1: invented wall
fails `surface_precision` + `facade_precision`, invented openings fail `openings`, empty / outside-run-folder
evidence never passes, a builder `score_stops: false` is ignored).

## Open for Artem (not decided here)

- **Contamination of a fresh clone.** `main` holds the whole Sokolniki history (`jobs/sokolniki-uvk1000/`, the
  D-rows, this file; `routes/npm-oks.md` names "Sokolniki v006 [D409]" as the body precedent). The builder prompt
  forbids those paths and the evaluator audits `commands.log`; the stricter option is a clone with them removed.
- **STOP answers.** The protocol has the evaluator answer from the accepted D-rows; Artem may prefer to answer live.
- **Key choices.** The NPM key carries the [D419] residual (xView 89 faces / 20 vertices at the body seams, V001 /
  V003 / V004 fail): the gates are "no worse than the key", not absolute passes.
