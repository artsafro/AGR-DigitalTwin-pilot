# UV / atlas — requirement sheet

**Area and profiles:** UV / atlas, cross-cutting for NPM and VPM, with the Ground, GroundEl and Flora
target table (OKS Main texture-set targets sit in the same index). NPM delivers embedded PNG atlases;
VPM lays out UDIM on one channel. In scope: texture-set targets per object class, Ground relief
density, UV channel / UDIM / glass tile, and island padding and margins. Out of scope: map types,
suffixes, naming and PNG format details (future `areas/textures.md`, T-TEX-1), materials, Ground
geometry and UCX.

**Readiness:** [roadmap §7.4 and §7.10](../../research/capability-roadmap.md#74-uv--atlas--l2-partial-cross-cutting-rule-table)
records L2-partial for the cross-cutting UV rule table and L1-partial for Ground textures. This sheet
adds the L1 index only. It does not add a skill, a benchmark or V009, and it is not a delivery
acceptance.

**Reading:** the table is an index, not replacement rule text. `reg p.N` is the one-based PDF page
of [the supplied regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf).
`L2 coverage` names only implemented checks, with their limits; `none` includes manual-only checks.
Coverage was checked against [the implementation inventory](../validation.md#implementation-status-inventory-static-audit),
[`scene_findings`](../../../src/twinqa/scene.py) and [`uv.py`](../../../src/twinqa/uv.py). Scene
subsets need exported-FBX readback (`--scene`). This research ran no DCC or delivery validation.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| UV-01 — OKS Main texture-set target | reg p.9 §5.11; reg p.6 §1.4; reg p.30 §4.3–4.5 | 1 texture set per OKS; +1 extra set if the project has a usable roof (that set may also hold OKS facades): 2 sets per OKS model. OKS FBX: OKS geometry up to 20 objects, max 40 texture sets (consistent with 20 × 2) | UDIM sets, no fixed set count; more than 100 UDIM maps on Main -> additional material(s) up to seven, SlotNumber from 1 sequential; do not split Main by slots with fewer than 100 maps; max 7 materials per object | Manual count of materials/sets per OKS against usable-roof presence; `standards/NPM_STANDARD.yaml` `texture_sets_per_oks` is a machine-readable value, not an implemented check; exactly-100 boundary is C11 | none | [NPM structure](../npm-vpm.md#npm-appendix-1), [VPM textures](../uv-textures.md#vpm-textures-app2), [C11](../conflicts.md#a-inside-the-regulation) |
| UV-02 — NPM materials equal texture sets | reg p.9 §4.5–4.6 | Material count (except translucent-part materials) equals texture-set count; translucent-part materials <= 7 | see UV-01 (material/slot rules on p.30) | Manual material/set inventory on exported FBX | none | [Materials](../materials.md), [NPM textures](../uv-textures.md#npm-textures-app1) |
| UV-03 — Ground relief texture-set target | reg p.6–7 §1.5 | Ground FBX up to 22 texture sets: Ground geometry max 20 sets (count also governed by the density rule), GroundGlass and GroundElGlass without sets, GroundEl 1 set, Flora 1 set | Ground is UDIM on one channel (UV-09); no NPM set ceiling transferred | Manual set count per Ground object class | none | [NPM structure](../npm-vpm.md#npm-appendix-1) |
| UV-04 — GroundEl atlas target | reg p.10 §5.12; reg p.7 §1.5 | One texture set for all GroundEl (MAF, lighting masts etc.), <= 512×512 px | Not an NPM limit transferred to VPM; VPM Ground texture contract applies | Manual grouping of all GroundEl into one set and image-dimension readback; generic NPM size helper does not enforce 512 | none | [NPM textures](../uv-textures.md#npm-textures-app1), [GroundEl / MAF sheet](groundel-maf.md) |
| UV-05 — Flora atlas target | reg p.10 §5.13; reg p.7 §1.5 | One texture set for all vegetation, <= 2048×2048 px; only diffuse map and, if needed, opacity map | No separate Flora atlas limit on p.30–31; VPM Ground texture contract applies | Manual set count, map-type list and dimension readback | none | [NPM textures](../uv-textures.md#npm-textures-app1) |
| UV-06 — Ground relief density band | reg p.10 §6.1; reg p.32 §6.2; [D097]; [D021] | only the relief surface inside the site: >= 10 and <= 40 (page text says "pixels per sq. metre", example 2048×2048 <-> square 204 × 204 m); C4 decided by the user [D097]: pixels per LINEAR metre, 10–40 px/m with 2K textures. Baking vs slicing: see UV-08 | Diffuse 512–1706 px/m, formula ρ = L_t ÷ L_p (texture side px / polygon length m); [D097] quotes 520–1706 px/m at 4K — differs from the regulation's 512, recorded as C36 (open, no side chosen); [D021] cut target about 4 × 4 m (1024 px/m) | Manual metric UV inspection; NPM Ground density has no general check; V009 unimplemented; OCR "+" vs image "÷" is C10 | none | [C4 / D097](../conflicts.md#a-inside-the-regulation), [C36](../conflicts.md#c-between-local-sources-project-decisionslessons), [VPM UV](../uv-textures.md#vpm-uv--udim) |
| UV-07 — Density applicability and exemptions | reg p.10 §6.2; reg p.31–32 §6.1 | Density not applied to perimeter polygons extruded down (§3.4), Flora, OKS, GroundEl | Density applies only to Diffuse; ERM, Normal and placeholders exempt; for maps with alpha a higher density in the range is recommended (p.32 §6.2) | Manual target classification before grading | none | [NPM textures](../uv-textures.md#npm-textures-app1), [VPM UV](../uv-textures.md#vpm-uv--udim) |
| UV-08 — Ground baking vs slicing approaches | reg p.18 fig.7–8 | Two example approaches for site landscaping and its atlas: «Запекание» (baking) and «Нарезка» (slicing); illustrative figures, not a numeric rule | Not shown for VPM | Choose and record the approach per site; manual atlas review | none | [NPM textures](../uv-textures.md#npm-textures-app1) |
| UV-09 — VPM UDIM, single UV channel | reg p.31 §2.1.1; reg p.9 §5.1 | PNG atlases embedded in FBX (not UDIM) | `*_Main` and `*_Ground`: UV only by UDIM, one UV set on one channel | Exported-FBX readback of UV channel count | V008 — `scene_findings` `uv_channels != 1` (needs `--scene` readback) | [VPM UV](../uv-textures.md#vpm-uv--udim), [implementation](../../../src/twinqa/scene.py) |
| UV-10 — UDIM tile sequence | reg p.31 §2.1.3; reg p.39 | n/a (atlas) | Tiles filled from 1001 strictly sequentially, no gaps, 10 × 10 scheme (1001–1100, appendix 1 fig. 1.2) | Archive filename tile sequence; scene UV tile layout is not cross-checked against filenames | V008 — `uv.sequential_tiles` (archive filename sequence only) | [VPM UV](../uv-textures.md#vpm-uv--udim), [uv.py](../../../src/twinqa/uv.py) |
| UV-11 — No mirrored islands | reg p.31 §2.1.4 | Not stated for NPM on p.9–10 | Mirrored UDIM islands forbidden; rotating islands not recommended | Mirrored-triangle readback; rotation is advisory and unchecked | V008 — `scene_findings` mirrored UV triangles (needs `--scene`) | [VPM UV](../uv-textures.md#vpm-uv--udim), [implementation](../../../src/twinqa/scene.py) |
| UV-12 — Splitting, overlap, tile margins and seams | reg p.31 §2.1.2, §2.1.5–2.1.6 | NPM atlas rules (UV-13 padding) | Geometry larger than one UDIM tile at required density is split; repeating/similar islands placed by overlap; margin from UDIM tile borders; no visible seams, shifts or pattern mismatch between maps | Manual UV/render review; no island-overlap or margin metric implemented | none | [VPM UV](../uv-textures.md#vpm-uv--udim), [validation inventory](../validation.md#implementation-status-inventory-static-audit) |
| UV-13 — Island padding | reg p.9 §5.4; reg p.30 §5.1.5 | >= 8 px between neighbouring islands with unique images on one atlas | >= 16 px at 2048×2048, >= 32 px at 4096×4096 between unique-image islands on one UDIM tile | Manual island-edge/dilation review; V006/V007 do not measure padding; local padding variants are C29 | none | [NPM textures](../uv-textures.md#npm-textures-app1), [VPM textures](../uv-textures.md#vpm-textures-app2), [C29](../conflicts.md#c-between-local-sources-project-decisionslessons) |
| UV-14 — Glass UVs in tile 1001 | reg p.31 §2.2.1–2.2.2; reg p.9 §5.10 | Opaque glass in the atlas: white on diffuse and metallic, black on roughness; no opacity map or opacity UV region white | `*_MainGlass`, `*_GroundGlass`: all glass UVs inside UDIM tile 1001, maximum fill, margin from tile borders, island overlap allowed, single UDIM channel | Readback of glass mesh tiles; GroundGlass and glass faces in meshes not named `*MainGlass` are not checked | V008 — `scene_findings`, meshes named `*MainGlass` only (needs `--scene`) | [VPM UV](../uv-textures.md#vpm-uv--udim), [implementation](../../../src/twinqa/scene.py) |

## Source-image evidence

All numbers, units and limits stated in the table were visually checked on PyMuPDF-rendered PDF
pages, not accepted from OCR alone. Renders are local only at `C:/x/l1-evidence/uv-atlas/pNN.png`
(not committed; PNG is Git LFS). PyMuPDF 1.28.2; render matrix `(1.6, 1.6)`, no alpha.
The working command is `uv run --extra pdf-review python`, using `pymupdf.open(...)` and
`page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False).save(...)`.
Visually inspected pages: 6, 7, 8, 9, 10, 18, 30, 31, 32, 39. On p.39 fig. 1.2 the
row-8 cell after 1078 also reads 1078 (expected 1079 by the 1001 + U + 10 × V scheme); a figure
typo that does not change UV-10.

- **UV-01, reg p.9 §5.11** (`p09.png`, bottom): «На каждый ОКС в составе модели АГР допустимо использовать только 1 текстурный набор» … «(2 текстурных набора на модель ОКС)».
- **UV-04, reg p.10 §5.12** (`p10.png`, top): «один текстурный набор на все элементы, размером не более 512×512 пикселей».
- **UV-05, reg p.10 §5.13** (`p10.png`): «один текстурный набор на все элементы, размером не более 2048x2048 пикселей» … «исключительно карта диффузного цвета и, при необходимости, карта прозрачности».
- **UV-06, reg p.10 §6.1** (`p10.png`, middle): «не меньше 10 пикселей на кв.метр, что при текстуре 2048×2048 соответствует квадрату со сторонами 204 на 204 метров, но не более 40 пикселей на кв.метр». Unit decided by the user as px per linear metre [D097].
- **UV-09, reg p.31 §2.1.1** (`p31.png`, top): «UV-развертка выполняется исключительно по технологии UDIM в единственном экземпляре и только на один канал».
- **UV-14, reg p.31 §2.2.1** (`p31.png`, middle): «в пределах 1001 UDIM-плитки с максимальным заполнением и соблюдением отступа от границ UDIM-плитки. Допускается наложение UV-островов друг на друга».

The issue text (written before 2026-10-15) said the Ground density unit conflict stays open; C4 was since decided by the user [D097]; the sheet only points to it. p.6 §1.4 (max 40 sets per OKS FBX) and p.9 §5.11 (1+1 per OKS) are consistent (20 OKS objects × 2), no conflict recorded.

## L2 gaps

The table contains **14 requirement rows**: **10** with `none` and **4** with partial coverage (UV-09, UV-10, UV-11, UV-14).

- **UV-01:** automatic count of OKS materials and texture sets against usable-roof presence; `texture_sets_per_oks` is machine-readable only, and the exactly-100 slot boundary (C11) is not checked.
- **UV-02:** equality of material count and texture-set count, excluding translucent-part materials, with translucent-part materials <= 7.
- **UV-03:** Ground FBX set ceiling (22) split by class: Ground max 20, GroundEl 1, Flora 1, glass classes without sets.
- **UV-04:** one shared GroundEl texture set and the 512×512 px ceiling.
- **UV-05:** one Flora texture set, diffuse plus optional opacity only, and the 2048×2048 px ceiling.
- **UV-06:** NPM Ground relief density 10–40 px per linear metre [D097] and the VPM Diffuse band; V009 is unimplemented, and the 520 vs 512 lower bound stays open as C36.
- **UV-07:** exemption classification before grading (NPM perimeter extrusion, Flora, OKS, GroundEl; VPM non-Diffuse maps).
- **UV-08:** per-site record of baking versus slicing, and atlas review against the illustrative figures.
- **UV-12:** split-at-tile, island overlap, tile-border margin and seam/shift/pattern-mismatch checks.
- **UV-13:** island padding (NPM >= 8 px; VPM >= 16 px at 2048 and >= 32 px at 4096); local variants remain C29.

Remaining work on the partial rows: UV-10 checks archive filename sequence only and does not cross-check scene UV tile layout against filenames; UV-14 checks meshes named `*MainGlass` only and does not check GroundGlass. V009 density is roadmap T-UV-3. The UV benchmark is roadmap T-UV-2. No complete UV L2 is claimed.

## Notes

No tests were added. This sheet is an L1 index and is not delivery acceptance.
