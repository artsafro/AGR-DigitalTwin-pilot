# Object registry

Object ids follow `docs/agents/NAMING.md`. Legacy job folders keep their names until the
code migration renames them.

Archived (removed from the tree, readable in tag `archive/2026-11`; index and status: `docs/ARCHIVE.md`):
`A-MAIN-ATLAS`, `B-MAIN-ATLAS`, `FACADE-SIGNS`, `FACADES-ATLAS`, `GLB-NPM`, `GROUND-PROJECTION`, `MASHI-LP`,
`MESH-OPT-AUDIT`, `REVIT-OPENINGS`, `UV-CONTINUOUS`, `WINDOW-ATLAS`, `WINDOW-FRAMES`, `flora-textures`
(each as `archive/2026-11:jobs/<folder>/`).

Harness and synthetic job folders (no real object, not deliveries): `ORCH-OBR22-NPM` (orchestration pilot on Obr22,
`STATE.md`: DELIVERY_NOT_PASSED), `SYNTH-001` (synthetic slice for the `dt` CLI, `passed=false`),
`KERNEL-SYNTHETIC` (synthetic kernel capability walk #351, `evidence.md`).

| Object id | Name (RU) | Site | Job folder | Sources | Notes |
|---|---|---|---|---|---|
| `tec26-oks` | ОКС АС.04–09 и дымовая труба — intake | ТЭЦ-26 | `jobs/TEC26-OKS/` | `jobs/TEC26-OKS/census/sources.json` (hash-pinned copies) | `jobs/TEC26-OKS/STATE.md`, #558; drawing analysis #561–566, truba #560 |
| `tec26-kpp1` | КПП1 — Центральная проходная | ТЭЦ-26 | `jobs/KPP1/` | `data/sources/revit/26_КПП1_АР_МЭП_RVT22.rvt`, `ТЭЦ26 на РР.pptx` (slides 25–30) | `jobs/KPP1/STATE.md` |
| `tec26-psu275` | ПСУ275 — главный корпус № 1 и отдельные ОКС | ТЭЦ-26 | `jobs/PSU275/` | `docs/sources/psu275.md` (PDF, Revit, FBX, PPTX with hashes) | `jobs/PSU275/STATE.md` |
| `vyatskaya-tow02` | Башня TOW02, ул. Вятская вл. 47–49 | 26_Vyatskoe | `jobs/vyatskaya-tow02/` | user Blender scene `…/26_Vyatskoe/001 - Моделирование НПМ с нуля/…/Untitled.blend` (read only) | `jobs/vyatskaya-tow02/STATE.md` |
| `skug26-k5-ac` | Корпус К5 — экраны кондиционеров (ВПМ текстура) | SKUG-26 (А101) | `jobs/skug26-k5-ac/` | user scene `…/62_26sk_pravki/Pravki_november/K5_VPM_textured_UV_v002.max` + `fbx/SKUG-26_PP_AR_K5_fsd_объединенный.fbx` (read only) | `jobs/skug26-k5-ac/STATE.md` |
| `4bk-k3` | 4БК, корпус К3 (STLB-04) — ВПМ, затем НПМ ОКС | А101 (Astro1) | `jobs/4bk-k3/` | `jobs/4bk-k3/sources.json` (inbox `…/!А101/63_4BK_vlad/inbox/`, hashed) | `jobs/4bk-k3/TASK.md`, `passport.json`; intake 2026-11-12 |
| `elv-tc-vpm` | ТЦ «СРЕDА», ул. Элеваторная вл. 1А (VPM-OKS only, stem `SM_Elevatornaya_Vl_1_A_001`) | Москва | `jobs/elv-tc-vpm/` | Revit FBX + AGR booklet (`jobs/elv-tc-vpm/TASK.md`) | `jobs/elv-tc-vpm/TASK.md`; deliveries v002–v005 accepted 2026-11-05, PR #969; V011 (MSK-77, FNO), УКЭП, SINTEZ open |
| `vatutino-site` | Ватутино — благоустройство: Ground, МАФ, Флора, расстановка | Ватутино | `jobs/VATUTINO-SITE/` | SPOZU DWG, MAF/planting schedules (`job.yaml`, `maf/site-maf-set.md`) | no STATE.md: `job.yaml` (stale, pins v014), `ground-v015-route-a-session-20261104.md`, `placement-report.md`; Ground v015 accepted 2026-11-04 (#906, [D193]); MAF geometry accepted, colour zones open (#889, PR #991); Flora/placement technical QA only |
| `cod-20207` | COD 20207 — Ground второй площадки | COD-22 | `jobs/COD-20207/` | `C:/x/ground-cod-22/spozu.dwg`, `gp.dwg` (local) | `ground-build-v016.md`; second-site Ground trial (#420), not passed |
| `obr22-k02` | Обр22 корпус 2, секции 7–9 — типовой этаж | Обр22 | `jobs/OBR22-K02/` | Revit typical floor via Blender | `jobs/OBR22-K02/STATE.md`, `APPROVED_VERSIONS.json`; NPM v012 / VPM v011 accepted |
| `obj03-decor` | OBJ03 — панельная башня, фасадный декор (harness run) | — | `jobs/OBJ03/` | `data/sources/OBJ03/source-geometry-v001.fbx` | `jobs/OBJ03/STATE.md`; pipeline status draft; unsuccessful [D079] |
| `butovskaya-sosh1000` | Общеобразовательная школа на 1000 мест, ул. Большая Бутовская вл. 9 (СОШ1000) | Южное Бутово | `jobs/butovskaya-sosh1000/` | live Revit 2025 `БУТОВСКАЯ_СОШ1000_АР_В3_ВИЗАМ_2025.rvt` (user's, read only), TwinPack mesh snapshot `C:/x/butovskaya-snapshot-twin/` (local; the box snapshot `C:/x/butovskaya-snapshot/` is exploration only) | `jobs/butovskaya-sosh1000/STATE.md`, #118 |
| `silikatny-maf-viz` | МАФ для визуализации, ЖК «Силикатный» (СИЛ13-УВК) | Силикатный | `jobs/silikatny-maf-viz/` | `СИЛ13-УВК-ПД-ПЗУ_.dwg` (pravki), `Силикатный маф.zip`, docx «МАФ_и_свет_модели_фото (4)» | `jobs/silikatny-maf-viz/README.md` [D189] |
