# Дорожная карта AGR-DigitalTwin

> Страница создаётся автоматически: `uv run python tools/roadmap_ru.py`. Не править вручную —
> правки пропадут при следующем запуске. Источники: оценка готовности, задачи и PR на GitHub, `docs/plans/`.

Обновлено: 2026-11-28; оценка готовности от 2026-11-28T08:36+01:00.

Общая готовность: **91.3 из 100** (+0.0 к прошлой оценке).

| Направление | Балл (0-100) | Готово, когда |
|---|---|---|
| Вход и правила | 95 | новый агент за 10 тысяч токенов находит нужные решения и правила |
| Порядок «задача → модель» | 97 | один порядок работы от исходников до отчёта, проверенный на новом агенте |
| Операции ядра | 97 | операции над геометрией работают на новом здании с проверками до и после |
| Самопроверки | 98 | автоматические проверки модели ловят ошибки и не пропускают брак |
| Ground | 88 | рельеф участка собран из исходников, текстуры привязаны и проверены после экспорта |
| UCX | 81 | коллизии односторонние, в бюджете и проверены на выгруженной сцене |
| МАФ | 83 | МАФ выбраны из принятой библиотеки и расставлены по точкам |
| Флора | 78 | растения из библиотеки расставлены, прозрачность и бюджет NPM проверены |
| Доступ к файлам | 98 | внешний агент скачивает всё нужное по манифестам без нас |
| Визуальная проверка | 90 | каждый результат приходит Артёму на просмотр, решение записывается |
| Здание целиком | 93 | реальное здание прошло весь путь до пакета сдачи |

## Сделано за 7 дней

Принято изменений (PR): 205.

### Вход и правила — 10
- #2091 fix(merge-policy): exclude card-unknown rows from backtest agreement
- #2041 feat(#2038): merge policy file + read-only observe classifier
- #2028 Close decision-link gaps and slim AGENTS.md (#2018)
- #2021 Restore live paths to agent search (#2016)
- #1977 search_noise: refuse archive rows a live non-entry doc or code links (#1891)
- #1975 docs: one owner for plans, AGR Tools plans, MCP plans (#1868, #1869, #1870)
- и ещё 4

### Порядок «задача → модель» — 12
- #2072 Trainer: User Proxy role + short stage tasks dev/holdout + run metrics (#2066)
- #2022 Normalize agent skill triggers and Blender routes (#2017)
- #2010 fix(trainer): isolate practice Codex user skills
- #1940 docs: document the executable Site trail (#1937)
- #1939 Measure cold entry after hygiene batches (#1938)
- #1880 Bound trainer Core Console stalls before DXF intake (#1874)
- и ещё 6

### Самопроверки — 12
- #2078 fix(merge-policy): require a checked card for small PRs (#2043)
- #1965 Reject truncated DXF readbacks (#1866)
- #1964 test: align TEC26 density check with KPP reference diagnostic (#1952)
- #1832 Form check: use 63B source geometry and observe envelope corners
- #1798 Refuse unsupported 3ds Max versions before xView staging (#1790)
- #1797 Skip image search in xView FBX imports (#1789)
- и ещё 6

### Ground — 23
- #2059 Improve: Reconcile the Ground/Site gap table with merged evidence
- #2048 Improve: Record source intent before building flat Ground
- #2030 Call graph: recognize repo-root Path joins in live Ground research callers (#2024)
- #2009 Ground context map: verify real handoffs and warn on disconnected nodes (#1930)
- #1967 Publish Ground UDIM tables beside VPM ZIPs (#1908)
- #1915 Ground context map: distinguish real tool handoffs from historical and manual paths (#191…
- и ещё 17

### UCX — 4
- #2061 feat(ucx-methods): section-boxes (OKS) and ground-coarse-faces (Ground) variants, measure…
- #2056 feat(ucx): observe passage blockage and disconnected bodies
- #2003 Fix UCX variant builder loading in Blender (#1991)
- #1995 Bind Methods UCX fit triangles to their FBX import (#1957)

### МАФ — 10
- #1993 library: backfill other sessions' NPM/VPM MAF sets as 93 drafts (#1983, refs #1743) [D421]
- #1985 library: publish Moskovsky school 1200 MAFs as 28 drafts (#1981, refs #1743) [D421]
- #1956 Ground methods benchmark: do not mix vertices and triangle indices from separate imports…
- #1949 Library: MAF batch 3 drafts + drafts visible to agents, auto index, close-out guard (#174…
- #1834 Remove false NPM regulatory references from place.maf_checks (#1781)
- #1829 Fix MAF clearance diagnostic metadata (#1781)
- и ещё 4

### Флора — 6
- #2044 docs(#2039): decision trees per scenario skeleton + check
- #1979 job(moskovsky-sosh1200): site NPM Ground v003 + MAF v002 + Flora v002
- #1803 docs: restore Flora, OKS VPM and Obr22 owner pointers
- #1800 fix: sync the generated Flora skill after #1796
- #1778 Document UV-based shrub planting in NPM MAF planters (#1733)
- #1747 Report uncovered Flora dimensions in V015 (#1702)

### Доступ к файлам — 11
- #2082 fix(trainer): audit device and UNC drive aliases (#2034)
- #2070 Decision D432: eval-driven development principle (#2064)
- #2032 fix(trainer): audit drive-root aliases in holdout transcripts
- #2004 fix(trainer): catch holdout reads above the evidence root
- #1971 Move verified scratch inputs to Drive and guard new references (#1958)
- #1927 Trainer A/B probe of harness edits + LESSONS evidence form [D414] (#1924)
- и ещё 5

### Визуальная проверка — 4
- #1890 Hide reviewed B1 history from agent search (#1885)
- #1883 Prompt: require live-consumer evidence in audits and route reviews
- #1851 Promote the stage-2 review sheet to one owner tools/blender/stage2_review.py (#1804 harve…
- #1774 Skeletons review-scene: agr open-review opens a stage copy in new Max 2026, Blender when…

### Здание целиком — 31
- #2079 Restore AC09 D171 facade field checks (#2037)
- #2040 fix(trainer): preserve Windows timeout receipts during Codex cleanup
- #2036 Verify the drawn D171 panel field before counting facade joints (#2014)
- #2033 fix(#2008): match cold OKS STOP filenames to protocol IDs
- #2029 KPP1: retire build_kpp1.py stage builder, lattice-1609 is the route [D426] (#2020)
- #1972 Sokolniki: NPM delivery package v001 - inset offset, work FBX, checks (#1966) [D419]
- и ещё 25

### Исследования — 22
- #2073 research(#149): view->face by finish partition (PDF fills vs Revit types) - H149 confirme…
- #2069 Research #2068: agent-first audit (12 principles + OpenAI agentic-legibility 11/21)
- #2055 research(#145): view->face transfer test on ELV TC Sreda - H145 refuted (OBSERVE)
- #2047 research: Codex UCX cases (22) vs our UCX pipeline (#2042)
- #2045 Research: Job retro: moskovsky-sosh1200 (PR #1979)
- #2007 research(#2001): cold OKS run Sokolniki - evaluator (key, protocol, controls, builder pro…
- и ещё 16

### Служебное — 59
- порядок в репозитории и исправления упавших проверок, по одному не перечисляем

### Прочее — 1
- #1779 Native handoff harness bundle 001: split 8-gon caps for the work-FBX degree gate (#1761)

## Идёт сейчас

Ждут проверки или слияния: 10 PR. Открытых задач: 37, из них готовы для агента: 13.

### Ground — 4
- #2087 Ground event map: distinguish general rules from Vatutino exceptions (#1946)
- #2086 Preserve verified Ground FBX placement through UCX and binding (#1922)
- #2085 Package validator: check named Ground work FBX and align archive address parsing (#1919)
- #2084 Ground FBX readback: select the surface independently of UCX and expose strict UDIM statu…

### UCX — 2
- #2092 UCX: cut and validate a local passage in frozen collision (#2051)
- #2058 UCX decisions 2026-11-27: D427 budget vs form, D428-D431, Codex etalons (#2050)

### Исследования — 4
- #2080 research(#153, #2075): view-face-wall harness; nontrivial exercised counts only W1-answer…
- #2077 research(#155): keyplan-arrow view->face reader on the untitled raster template (OBSERVE)
- #2074 research(#151): view->face finish-partition D transfer to Olimpijsky FOK — refuted (OBSER…
- #2062 Research #147: view->face disagreement veto (H147 refuted, OBSERVE)

### Планы в работе
- Plan: rolling out the Telegram findings (2026-11-10) (`docs/plans/telegram-findings-rollout.md`)

## Осталось до сдачи без Артёма

Три главных препятствия до 100; каждое агенты закрывают сами.

1. **Ground, UCX, МАФ, Флора** (+5.9 к общему баллу).
   Что закроет: рельеф участка собран из исходников, текстуры привязаны и проверены после экспорта; коллизии односторонние, в бюджете и проверены на выгруженной сцене; МАФ выбраны из принятой библиотеки и расставлены по точкам; растения из библиотеки расставлены, прозрачность и бюджет NPM проверены.
   Подробно: One site Ground -> UCX -> MAF/Flora with export readback, budget and visual gates (Moskovsky closest); cold agent reproduces it.
   Задачи: #1315, jobs/moskovsky-sosh1200, #2058, #2061, #2084-#2087

2. **Вход и правила, Порядок «задача → модель»** (+0.8 к общему баллу).
   Что закроет: новый агент за 10 тысяч токенов находит нужные решения и правила; один порядок работы от исходников до отчёта, проверенный на новом агенте.
   Подробно: Make the out-of-repo coordination rules repo-visible, one check entry; run the #2001 cold OKS builder vs frozen key.
   Задачи: #2068 audit, #2072, #2001

3. **Здание целиком, сдача объекта** (+0.7 к общему баллу).
   Что закроет: реальное здание прошло весь путь до пакета сдачи.
   Подробно: Sokolniki package to passed=true: seams snap, V004, V003 n-gons, Ground/MSK placement, SINTEZ + xView in Max.
   Задачи: #1966 / #1972, #1784

Сдача: здание — не пройдена, участок — не пройдена.

## Ждёт Артёма

1. Sokolniki NPM: UCX/GeoJSON нужны без отдельного ТЗ заказчика? (рекомендация в #1972: нет)
   Рекомендация: нет
2. Швы тела Sokolniki (0.9 мм, 43 пары xView): snap в копии сдачи (рекомендовано) / пересобрать тело / оставить?
   Рекомендация: snap в копии сдачи
3. Moskovsky Ground v003: текстуры принять (визуальный гейт открыт в STATE.md)?
   Рекомендация: не записана, нужен ответ Артёма.
4. #1500 MAF from PDF + library NPM status after Artem's Staropetrovsky MAF session (#425 route st…
   Рекомендация: в задаче #1500.
5. #1507 Manual mode: AGR Tools stage for Ground / MAF / Flora on the compaction cores (#1374 chun…
   Рекомендация: в задаче #1507.
6. #1509 Manual mode: doors by opening sizes from a door library, placed like windows (#1374 chunk…
   Рекомендация: в задаче #1509.

## Отложено сознательно

- #1808 MAF context map: separate showcase, scene checks and archived handoffs (AI Council) — причина не записана в задаче
- #1809 MAF atlas: number material cells in new colour PNGs — причина не записана в задаче
- #1918 Placement: distinguish Ground footprint notches from enclosed holes — причина не записана в задаче
- #1920 Ground tools: reuse checked headless Blender execution — причина не записана в задаче
- #1923 Local CI receipt: retain pytest skip reasons in the optional evidence log — причина не записана в задаче
- #1944 Ground builder: apply D251 outer-ring skirt check to exported OBJ — причина не записана в задаче
- #1945 Ground VPM GeoJSON: carry the sourced parcel area into ZU_area — ждёт #1908
- #1947 NPM package validation: do not pass V006 against an atlas bound to a different master — ждёт #1919
- #1948 Ground: expose conflicting UDIM seam results in the OBJ build report — ждёт #1944
