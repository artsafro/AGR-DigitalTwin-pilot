# agent-sim-k4 — сценарный eval «имитация агента» (приёмка К4, #1024, ветка U)

Проверяет не то, что MCP «работает», а то, что агент через MCP **решает задачу по контракту К4** и не может выйти
за его границы. Агент — скрипт (`run.py`), говорит с демоном agr-mcp по настоящему MCP (Streamable HTTP, токен),
как CLI в доке. Человек — тоже скрипт: «Применить» = `agr_gate.confirm(preview_id)` внутри Max.

## Строки (каждая pass/fail в `report.json`)

| Проверка | Что должно быть |
|---|---|
| `profile_no_exec` | в `tools/list` моста есть `agr_agent_*` и **нет** `agr_exec_unsafe` (даже при `AGR_MCP_UNSAFE=1` у демона); вызов — `unknown_tool` |
| `context` | `agr_agent_context(request)` отдаёт запрос и объекты сцены как ObjRef |
| `needs_human` | apply до кнопки — `needs_human`, сцена не меняется |
| `mark_opening` | preview → кнопка → applied: `OPEN_<nnn>` в `AGENT_<req>`, роль `opening`, одна запись Undo |
| `keep_copy` | `keep` тела → копия в `AGENT_<req>`; инварианты D115 посчитаны на сервере (`dt_ai.ops.run_operation`) |
| `set_role_in_layer` | `set_role` на своей копии → applied |
| `outside_rollback` | `set_role` на объекте **вне** слоя: preview предупреждает, кнопка → `rolled_back`, откат доказан хешами, вопрос в `questions.md` |
| `invariant_refusal` | `primitive_box` на Г-образной детали → `rolled_back` уже на preview (силуэт), `preview_id` нет |
| `stale_after_change` | preview, сделанный до другого apply, устарел (`state_hash`) → `stale_preview` |

## Где запускается

- pytest: `tests/max_tools/test_agr_tools_agent_bridge.py::test_eval_agent_simulation_k4` — фейковая сцена
  (`fake_max.py`), настоящий демон (uvicorn) и listener в процессе.
- Нативно: `tests/max_tools/run_agr_tools_agent_bridge_native.py` — 3ds Max 2024 в слоте agr-lab, демон и этот
  скрипт — отдельные процессы; кнопку нажимает харнесс Max через файлы `--press-dir`.

`task.json` нет намеренно: раннер `dt evals` оценивает транскрипты и требует грейдер из
`twinqa.evals.graders.GRADERS` (модуль без владельца — только маленьким PR). Папка без `task.json` раннером
пропускается. Регистрация грейдера `agent_sim_k4` (читает `report.json`) и ночной прогон в Lab CI — задача R 1.0
(`BRANCH0-U-L12-ADDENDUM.md`, «К R 1.0»).

Данные синтетические.
