# Object registry

Object ids follow `docs/agents/NAMING.md`. Legacy job folders keep their names until the
code migration renames them.

| Object id | Name (RU) | Site | Job folder | Sources | Notes |
|---|---|---|---|---|---|
| `tec26-kpp1` | КПП1 — Центральная проходная | ТЭЦ-26 | `jobs/KPP1/` | `data/sources/revit/26_КПП1_АР_МЭП_RVT22.rvt`, `ТЭЦ26 на РР.pptx` (slides 25–30) | `jobs/KPP1/STATE.md` |
| `tec26-psu275` | ПСУ275 — главный корпус № 1 и отдельные ОКС | ТЭЦ-26 | `jobs/PSU275/` | `docs/sources/psu275.md` (PDF, Revit, FBX, PPTX with hashes) | `jobs/PSU275/STATE.md` |
| `butovskaya-sosh1000` | Общеобразовательная школа на 1000 мест, ул. Большая Бутовская вл. 9 (СОШ1000) | Южное Бутово | `jobs/butovskaya-sosh1000/` | live Revit 2025 `БУТОВСКАЯ_СОШ1000_АР_В3_ВИЗАМ_2025.rvt` (user's, read only), snapshot `C:/x/butovskaya-snapshot/` (local) | `jobs/butovskaya-sosh1000/STATE.md`, #118 |
