# Силикатный, PZU DWG visualisation prep — lessons (job-local)

User preferences from the 2026-11-04/05 session «DWG подготовка к визуализации», recorded per Artem's
triage of #1038 (2026-11-09: «такие решения не хочется принимать, они индивидуальны, скорее лучше у каждого
джоба складывать, а потом уже искать связи»). Scope of every line: **this job only**. These are not `D<n>`
decisions and not domain rules; cross-job patterns are searched later in a separate research card.
Source: `docs/retros/2026-11-05-sessions-retro-04-05.md`, "User preferences not yet captured in the repo".
The job's other files live on branch `job/silikatniy-uvk-pzu-viz` (not on `main`).

| # | Rule | Source (session, date UTC, quote) | Scope |
|---|---|---|---|
| 1 | The agent opens the scene itself and gives the full absolute path, never a repo-relative `for_ai/...` link. | «DWG подготовка», 2026-11-04 14:17 and 2026-11-05 15:29: «открой сцену в 26 максе посмотрб», «еще раз открой, вылетела сцена» | this job |
| 4 | Viz ground from DWG: a smooth white paint line on every joint between different rubber colours. | «DWG подготовка», 2026-11-04 14:05: «на месте стыки тоже должна идти плавная дуга белой разметки» | this job |
| 5 | Material ID colour = the hatch background fill (`bgcolor`) seen in AutoCAD, not the hatch pattern line colour. | «DWG подготовка», 2026-11-04 14:19–14:30: «теперь надо разбить на id и мультисаб сделать для визуализации» (v001 took the pattern colour) | this job |
