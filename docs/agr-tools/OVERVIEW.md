# AGR Tools: входная страница для агента

Читайте это первым, если задача касается AGR Tools, панели 3ds Max, `agr-mcp`, окон, материалов или конвейера ОКС. Ссылки ведут только на файлы этого репозитория. Правила для всех агентов — `AGENTS.md`; здесь только карта AGR Tools.

## Что это

**AGR Tools** — собственная панель 3ds Max (2024 и 2026) для производства цифрового двойника ОКС вместо стороннего скрипта-комбайна. Версия **1.0.0** (тег `agr-tools-v1.0.0`) — конвейер из этапов 0–9 плюс этап «Агент»:

`0 Паспорт → 1 Бадик → 2 Окна → 3 Капсулы → 4 Крыша → 5 Материалы → 6 ВПМ → 7 НПМ → 8 НПМ↔ВПМ → 9 Сдача`, и сбоку агент (`agent.request` / `agent.accept`).

Каждая кнопка — функция одного ядра с двумя «мордами»: Qt-панель и MCP-сервер `agr-mcp`. Таблица кнопок, версий и режимов — `docs/plans/agr-tools-suite.json` (по ней собраны справка `docs/agr-tools/GUIDE.md` и вкладка «Путь» панели). Что сделано в 1.0 и что осталось — `docs/plans/agr-tools-1.x.md`. Предыдущий релиз — **0.9.0** (тег `agr-tools-v0.9.0`, проверки, правки на копиях, замены, МАФ, UDIM, атласы). Журнал версий — `adapters/max/agr_tools/CHANGELOG.md`.

## Где код

- `adapters/max/agr_tools/` — всё: `*_core.py` (stdlib, тестируются без Max), `*_max.py` (тонкий адаптер pymxs), `runtime.py` (диспетчер), `ui_*.py` (Qt-панель). Обзор, сборка и установка — `adapters/max/agr_tools/README.md`; сборка MZP — `tools/max/build_agr_tools.py`.
- `src/agr_mcp/` — MCP-сервер, `src/agr_mcp/max_side/` — свой listener, демон, профили, шлюз D108 внутри Max. Описание — `src/agr_mcp/README.md`.
- `library/` — таблицы и указатели библиотек (окна, материалы, МАФ, flora); `schemas/ProjectPassport.schema.json`, `schemas/AgentRequest.schema.json` — паспорт и запрос агента.
- `test-polygon/` — синтетический тестовый полигон; `tests/max_tools/`, `tests/agr_mcp/` — тесты и нативные прогоны.

## Как проверять

- **Юнит-тесты:** `uv sync`, затем `uv run python -m pytest tests/max_tools tests/agr_mcp tests/qa -q -n 4` (полный набор — `uv run pytest -q -n 4`, подробности в `docs/agents/agents-reference.md`). Только в `uv`-окружении своего worktree.
- **Полигон:** сцена с базами 0.1…1.0 и станциями PASS/FAIL, у каждой кнопки своя станция [D194]. Как играть и как прогнать все кнопки — `test-polygon/README.md`, `test-polygon/run_polygon.py`; результат сравнивается с `test-polygon/expected/`.
- **Нативные прогоны в Max и AGR Lab runner:** скрипты `tests/max_tools/run_agr_tools_*_native.py` ставятся раннером в batch Max 2024 на одноразовых синтетических сценах; правила работы с раннером и слотами — `docs/agents/agr-tools-impl-rules.md`, ночной Lab CI — `lab-ci.toml` и раздел «Lab CI» в `docs/agents/CAPABILITIES.md`. Запускать Max самому и трогать GUI Max владельца нельзя.

## MCP v2

Сервер `agr-mcp` (регистрация `.agents/mcp_config.json`, запись в `docs/agents/CAPABILITIES.md`):

- каталог строится из `docs/plans/agr-tools-suite.json`: 15 инструментов больших кнопок этапов, `agr_check_run`, `agr_op_preview`, `agr_op_apply`;
- правки идут как **preview → apply**: сервер хранит preview, `preview_id` привязан к хосту, процессу Max, документу, версии ядра и хешу состояния сцены; apply кнопки 1.0 подтверждает человек в панели или доке [D212];
- ответ — конверт v2 (`summary`, `counts`, `findings_top`, `report_uri`, `next_actions`, машинные коды ошибок); один общий журнал для панели и MCP;
- профили `observer` / `operator` / `modeller` / `dev` (`agr_exec_unsafe` только в `dev`), один демон на хост и свой listener в Max [D210];
- агент пишет **только** в слой `AGENT_<req>`; результат принимает шлюз `agent.accept`; операции меню проходят шлюз D108 с инвариантами до и после и откатом [D108], [D212].

План и ревью MCP, в том числе Blender как второй хост: `docs/plans/agr-mcp-target.md`; исходный план фазы 0: `docs/plans/agr-mcp.md`.

## Паспорт проекта

Без паспорта этапы 1–9 не запускаются (К1). У проекта есть `jobs/<ID>/passport.json` и `PASSPORT.md`, схема `schemas/ProjectPassport.schema.json`; сцена хранит в file properties `agr_passport` путь и sha паспорта; «завести проект» — `tools/project/new_project.py` или кнопка `project.passport`. Роли объектов (`agr_role`), метки проёмов `OPEN_<nnn>`, хелперы высот `LEVEL_<name>` — `adapters/max/agr_tools/contract_core.py`. Правила — `docs/agents/agr-tools-1.0-rules.md`.

## Библиотеки

Тяжёлое лежит на Google Диске `G:\Мой диск\AGR-assets\<lib>\` (окна, материалы, МАФ, flora, корпус), в git — таблицы и указатели. Список, версии и связь с git — `library/README.md`. Читать только с копии в своей scratch-папке, оригинал на Диске не открывать и не менять. Окна: `library/windows/` (стандарт, карантин, лист превью). Материалы: `library/materials/` и аудит `library/materials/AUDIT-2026-11.md`.

## Решения владельца 06.11.2026

Полный текст — строки D202–D218 в `docs/decisions.md`; здесь указатель по теме.

| Тема | Что решено | Запись |
|---|---|---|
| `model.move_apart` | `To` — итоговый зазор | [D202] |
| Окна | стандарт по семействам F100 / F73 / F58, стекло на 80 мм от лица рамы | [D203] |
| Капсулы | открытый край на середине рамы, outline 100 мм наружу, глубина 1,0 м, угловой проём — одна Г-капсула | [D204] |
| Quick Attach | по умолчанию Keep split | [D205] |
| Сетка текстур | 3,6 м на UDIM, 1000 px/м | [D206] |
| Крыша | подъём плиты плоской крыши 5 мм | [D207] |
| UDIM | нумерация в каждом меше отдельно с 1001 | [D208] |
| Ассеты ВПМ | флора и МАФ — в UDIM после Ground | [D209] |
| MCP | один сервер на хост, свой listener вместо `3dsmax-mcp` | [D210] |
| Экспорт | из Max или Blender, предпочтительно Max | [D211] |
| Агент | пишет только в `AGENT_*`, apply — кнопкой | [D212] |
| Blender | материалы возвращаются по `materials.json` | [D213] |
| Материалы | аудит джобов, таблица и плитки, ответы Q1–Q12 | [D214], [D215], [D216], [D217] |
| Уровни | `LEVEL_L1` / `LEVEL_L2` / `LEVEL_roof`, `LEVEL_RULE`, `accept_precision_loss` | [D218] |

Часть кода ещё не приведена в соответствие с решениями: список расхождений — `docs/plans/agr-tools-1.x.md` §2.2.

## Что читать дальше

- Кнопки, режимы, требования: `docs/agr-tools/GUIDE.md`, `docs/plans/agr-tools-suite.md`.
- Лабораторные отчёты по кнопкам: `docs/experiments/<id>.md`.
- Пилотные ограничения и известные дефекты 1.0.0: `adapters/max/agr_tools/CHANGELOG.md`, «Известные ограничения».
- Хвост 1.x, хендофф Max↔Blender, паритет Blender: `docs/plans/agr-tools-1.x.md`.
- Правила для нового агента в ветке AGR Tools: `docs/agents/agr-tools-impl-rules.md`, `docs/agents/agr-tools-1.0-rules.md`.
