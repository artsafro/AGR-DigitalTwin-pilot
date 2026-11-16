# ТЦ «СРЕDА», VPM-OKS — lessons (job-local)

User preferences from the 2026-11-05 session «VPM ОКС СРЕDА», recorded per Artem's triage of #1038
(2026-11-09: «такие решения не хочется принимать, они индивидуальны, скорее лучше у каждого джоба
складывать, а потом уже искать связи»). Scope of every line: **this job only**. These are not `D<n>`
decisions and not domain rules; cross-job patterns are searched later in a separate research card.
Source: `docs/retros/2026-11-05-sessions-retro-04-05.md`, "User preferences not yet captured in the repo".

| # | Rule | Source (session, date UTC, quote) | Scope |
|---|---|---|---|
| 10 | Interior capsules (false rooms) recessed to mid-frame/reveal; corner glass as a 6 mm two-face shell; continuous trims (P44) stay one mesh, and on a clash the minor element moves. Details: `TASK.md` lines 122 and 168–176. | «СРЕDА», 2026-11-05 ~10:10: «швы не сходятся на верхних полигонах… плашка… должна быть непрерывной… стекло… шесть миллиметров» | this job |
| 11 | Post-acceptance album review of v005 (Влад Жуков, 25 findings: 7 ours, 5 sources disagree, 5 simplifications, 3 not defects, 5 unclear). Our misses: faceted curves (no smoothing set), base flashing 5024 against TASK D13 / parts list, dock shelters 9005 with no source, dropped detail (TP door louvres, TP vent grilles, revolving-door frame, ladder guard). Before acceptance here: census every Revit family and booklet legend item into the parts list, cite a source per colour, and show source-vs-ours close-ups. Details: `REVIEW-album-2026-11-10.md`. | chat «3D_A&V», 2026-11-10 09:42–11:13, ids 1540–1612: «сглаживание не настроенно», «вент боксы отличаются … короче это по всюду» | this job |

## SINTEZ retro, 2026-11-15/16

Source: [issue #1542](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1542), quoting session `0a21d4de` (elv-tc-vpm SINTEZ).
Artem's scope approval, 2026-11-16: «принимаю рекомендации» — keep these individual preferences here only, not shared rules or D-rows.
The referenced `docs/retros/2026-11-16-elv-tc-vpm-sintez-claude.md` is not present on origin/main at recording time; the quotes below are preserved from the issue, not independently checked against the transcript.

| Topic | Job-local preference / context | Source (session, date, verbatim quote) | Scope |
|---|---|---|---|
| Trim UV | Box mapping when re-unwrapping trims. | `0a21d4de`, 2026-11-15/16: «Я обычно делаю UVW-map box 5-5-5 метров. Получаю нужный тексель» | this job |
| UCX budget | Preserve the model's polygon count; detach an element for subdivision. | `0a21d4de`, 2026-11-15/16: «Не увеличивай полигоны, чтобы там ничего не сбить» / «детачу какой-то элемент, делаю ему subdivide» | this job |
| Soffits | Low-texel soffits: 256 stub tile (issue context, not part of the quote). | `0a21d4de`, 2026-11-15/16: «Потолок можно просто в заглушку» | this job |
| Portals | Mid-face cut and connect. | `0a21d4de`, 2026-11-15/16: «посередине грани пилим, делаем connect» | this job |
| Collision gaps | A 2–10 mm band, not an exact 3 mm target. | `0a21d4de`, 2026-11-15/16: «зазор между коллизиями может быть от 2 мм до 10 мм. Ему не обязательно ровно 3 соблюдать» | this job |
