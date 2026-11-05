# Object registry

Object ids follow `docs/agents/NAMING.md`. Legacy job folders keep their names until the
code migration renames them.

Archived (removed from the tree, readable in tag `archive/2026-11`; index and status: `docs/ARCHIVE.md`):
`A-MAIN-ATLAS`, `B-MAIN-ATLAS`, `FACADE-SIGNS`, `FACADES-ATLAS`, `GLB-NPM`, `GROUND-PROJECTION`, `MASHI-LP`,
`MESH-OPT-AUDIT`, `REVIT-OPENINGS`, `UV-CONTINUOUS`, `WINDOW-ATLAS`, `WINDOW-FRAMES`, `flora-textures`
(each as `archive/2026-11:jobs/<folder>/`).

| Object id | Name (RU) | Site | Job folder | Sources | Notes |
|---|---|---|---|---|---|
| `tec26-oks` | ОКС АС.04–09 и дымовая труба — intake | ТЭЦ-26 | `jobs/TEC26-OKS/` | `jobs/TEC26-OKS/census/sources.json` (hash-pinned copies) | `jobs/TEC26-OKS/STATE.md`, #558; drawing analysis #561–566, truba #560 |
| `tec26-kpp1` | КПП1 — Центральная проходная | ТЭЦ-26 | `jobs/KPP1/` | `data/sources/revit/26_КПП1_АР_МЭП_RVT22.rvt`, `ТЭЦ26 на РР.pptx` (slides 25–30) | `jobs/KPP1/STATE.md` |
| `tec26-psu275` | ПСУ275 — главный корпус № 1 и отдельные ОКС | ТЭЦ-26 | `jobs/PSU275/` | `docs/sources/psu275.md` (PDF, Revit, FBX, PPTX with hashes) | `jobs/PSU275/STATE.md` |
| `vyatskaya-tow02` | Башня TOW02, ул. Вятская вл. 47–49 | 26_Vyatskoe | `jobs/vyatskaya-tow02/` | user Blender scene `…/26_Vyatskoe/001 - Моделирование НПМ с нуля/…/Untitled.blend` (read only) | `jobs/vyatskaya-tow02/STATE.md` |
| `butovskaya-sosh1000` | Общеобразовательная школа на 1000 мест, ул. Большая Бутовская вл. 9 (СОШ1000) | Южное Бутово | `jobs/butovskaya-sosh1000/` | live Revit 2025 `БУТОВСКАЯ_СОШ1000_АР_В3_ВИЗАМ_2025.rvt` (user's, read only), TwinPack mesh snapshot `C:/x/butovskaya-snapshot-twin/` (local; the box snapshot `C:/x/butovskaya-snapshot/` is exploration only) | `jobs/butovskaya-sosh1000/STATE.md`, #118 |
| `silikatny-maf-viz` | МАФ для визуализации, ЖК «Силикатный» (СИЛ13-УВК) | Силикатный | `jobs/silikatny-maf-viz/` | `СИЛ13-УВК-ПД-ПЗУ_.dwg` (pravki), `Силикатный маф.zip`, docx «МАФ_и_свет_модели_фото (4)» | `jobs/silikatny-maf-viz/README.md` [D189] |
