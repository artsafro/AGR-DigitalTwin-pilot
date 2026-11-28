# #155 — View -> face by the keyplan arrow on untitled sheets (Sokolniki template), OBSERVE

## Кратко для Артёма

Проверял самый дешёвый признак листа «как у Сокольников» (растровые фасады без подписей): красную
стрелку на миниатюре плана рядом с каждым видом. Чтец находит стрелку и серый план, совмещает план с
отпечатком 3D-модели (8 поворотов/зеркал) и говорит, какую грань показывает вид, или молчит, если
совмещение неоднозначно. Набор — Савёловская УВК1000 (тот же шаблон Weltbau, 4 альбома, 16 видов),
ответы сверены глазами по ортографическим рендерам моделей. Сокольники не открывал (#2001 открыт).

- **Направление (какая грань): 16/16 верно, 0 ошибок**, и так же 16/16 при повороте и зеркале миниатюры.
  Когда план подменён прямоугольником (симметрия) или стёрт — молчит 16/16 + 16/16, на чужом шаблоне
  (Олимпийский, без стрелок) молчит 4/4. Три прогона байт-в-байт одинаковые, ~106 с.
- **Какая стена (внешняя / внутренний угол): не работает.** 4 главных фасада со ступенчатым отступом
  3.5-3.75 м названы «внутренними» (порог 2.0 м); проверка с искусственно сдвинутой стрелкой на выемку
  не дала эффекта (12/12 прочитано как без сдвига) — это дефект подстановки, а не результат.
- Итог гипотезы H155 по замороженным критериям: **опровергнута** (из-за стены), часть «направление» —
  подтверждена. Реальных частичных видов без подписи в наборе нет — их это не проверяет.
- **Рекомендация для шага «карта вид↔грань»:** взять стрелку миниатюры как первый, дешёвый и
  безопасный признак направления (с отказом при неоднозначном совмещении); стену внутреннего угла
  этим признаком не определять — нужен второй признак (содержимое вида против рендера модели).

## Frozen contract (committed before any reader score was computed)

Card t_436d52d6 (standing #155), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki is held out and was not
opened. Rounds #139-#154 measured content cues (edges, raster, finish partition D, keyplan red lines on a
registered vector situation plan); none was measured on the **untitled raster sheet template** that the
Sokolniki cold run (#2001 STOP 04) has to read. This round measures the cheapest cue that template carries.

**Fixture (never used by #139-#154).** Savelovskaya UVK1000 (Weltbau, same template as Sokolniki): 4 issued
albums (В3 «Береста», В4-1 «Цветные арки», В4-2 «Белые арки», «вариант 3»), each a 2-3 page raster-printed
Revit PDF with 4 untitled elevations and per view a keyplan icon (grey plan with a courtyard notch, a red
triangle arrow and a thin red line), plus each album's own Revit FBX (1.0-2.0 M tris). Paths and SHA-256 in
[`fixture.json`](autoresearch-view-face-arrow/fixture.json) (owner's PC, `!Weltbau/8_Савеловская/`). 16 arrows =
16 views; the 4 albums repeat one building, so the rows are 4 re-issues of 4 faces, not 16 independent faces.

- **GT** (independent of the keyplan): each view was matched by eye to Workbench orthographic renders of its
  own album FBX (az 0/90/180/270) by geometry and finish features only (curved corner elements, ornament /
  arch positions, low framed block, the big-window short face). All 16 agree with layout; az = outward normal,
  0 = +X, 90 = +Y.
- **Reader R (the candidate; frozen params in the fixture).** Page raster at zoom 3. Red triangle = pure-red
  component with area/fill/aspect bounds; arrow direction = base -> apex (the narrower end). Keyplan icon = the
  nearest uniform-grey component (R 190-225, chroma <= 6, >= 3000 px) whose centre lies ahead of the arrow.
  Red line = thin red component between arrow and icon, perpendicular to the arrow (optional; its midpoint is
  the ray origin, else the arrow apex). Model footprint = heightmap of the FBX triangles at 0.25 m, cells
  >= 3.0 m above the ground level (median height of the 2 m border ring). Registration = 8 dihedral transforms
  of the icon mask, aspect within x1.2 of the footprint, resized to the footprint grid, IoU. Each transform
  yields an az (arrow direction mapped through it; outward normal = minus viewing direction). Answer = az of
  the best transform if IoU >= 0.75 and IoU margin to the best transform with a **different az** >= 0.05,
  else abstain. Wall = march from the ray origin along the viewing direction to the first footprint cell;
  depth below the footprint bbox side; `outer` if depth <= 2.0 m.
- **States (per arrow, all from the same page raster).** `clean`; `rotated` (keyplan patch = icon + arrow +
  line rotated 90 deg onto a blank canvas — expected: same GT az, registration must recover the rotation);
  `mirrored` (patch flipped left-right — expected: same GT az through a reflection); `symmetric` (icon
  replaced by its filled bbox rectangle — expected: **abstain**, positive abstention witness);
  `no_icon` (icon erased — expected abstain); `inner` (only arrows on the notch side: arrow + line moved over the
  notch columns of the icon — expected: same az, wall inner at the notch depth measured on the footprint,
  +-2.0 m). Changed-pixel counts per state are recorded; a state with 0 changed pixels is `not_exercised`.
- **Control (other template).** Olimpijsky AR.2 p5-p8 (vector, situation plan with red line, no triangle
  arrows): R must answer nothing (abstain 4/4); this is a no-trigger control, not an accuracy result.
- **Primary metric.** correct / wrong / abstain of az on the 16 real views (`clean`). Secondary: wall outer /
  inner identity; per-state tallies.
- **Acceptance H155 (frozen).** clean wrong 0 and correct >= 14/16; rotated wrong 0, correct >= 14; mirrored
  wrong 0, correct >= 14; symmetric wrong 0 (abstain on every exercised row); no_icon abstain 16/16; inner: wrong
  az 0, wall-correct >= 75 % of exercised rows; clean wall `outer` on >= 14/16; control abstain 4/4.
  Witnesses: positive trigger = `B3 p1 upper long` clean must answer 270; abstention = every `symmetric` row.
- **Stability / replay.** `uv run --offline --locked --extra pdf-review python
  docs/research/autoresearch-view-face-arrow/run.py C:/x/ar155/<fresh>` (pilot host; Blender 4.4 for the FBX
  triangle dump). Three fresh runs, each re-exports the FBX triangles and re-reads every PDF; row JSON must be
  byte-identical; median / spread wall time reported. Invariance: reversed component order must change 0 rows.
- **Budget / stop.** One candidate (R), no retuning after the first score; a failed row is reported, not
  fixed. Stop `inconclusive` if elapsed + 1.15 x first-run s x remaining runs > 3600 s or on parity failure;
  timing stop and hypothesis verdict are reported separately.
- **Forbidden.** Changing params, GT, arrow keys or states after a score; opening Sokolniki outputs; editing
  source drawings, models, deliveries, production `src/` or other cards' files; weakening guards.
- **Pre-score amendment A1** (code review of the runner, before any real run): the ground level is the 5th
  percentile of occupied heightmap cells (`fp_ground_pct` 5), not the median of the 2 m border ring — on an FBX
  without a site slab the building itself touches the bbox ring, so the ring median would be the roof level.
- **Not measured (declared up front).** Real untitled **partial** views (Savelovskaya has none; `inner` is
  injected), arrow -> view association (GT per arrow, by layout), notch side walls (az 0/180 inner), rotated
  keyplans on a real sheet, other templates with arrows, Sokolniki transfer (held out).

## Result (frozen series, head 6a44665b, runner unchanged)

Receipt: [`receipt.json`](autoresearch-view-face-arrow/receipt.json) (SHA-256
`61355e34f8af56cf859abe15f768e0ae3b201a49eac54c1b697fb3a321f1ccdb` as written, Git LF `06cbb9b68bca8f2a59b683f390779f810520309a2587874d0513e79cc43e5b05`), `status: finished`. Runner SHA-256
`e0462948…a9fb`, fixture `81df3a65…c697`, all 8 PDF/FBX inputs and Blender pinned in `receipt.pins`.
Evidence (GT orthographic renders az 0/90/180/270 per album, keyplan crop, receipt):
`G:/Мой диск/AGR-evidence/155-view-face-arrow/` + `SHA256SUMS.txt` (18 files).

| Check | Result | Frozen bound | Pass |
|---|---|---|---|
| clean az (16 real views) | correct 16 / wrong 0 / abstain 0 | wrong 0, correct >= 14 | yes |
| rotated az | 16 / 0 / 0 | wrong 0, >= 14 | yes |
| mirrored az | 16 / 0 / 0 | wrong 0, >= 14 | yes |
| symmetric (abstention witness) | abstain 16/16 (margin 0.000-0.0025) | wrong 0 | yes |
| no_icon | abstain 16/16 | 16/16 | yes |
| control Olimpijsky p5-p8 | abstain 4/4 (0 triangles) | 4/4 | yes (no-trigger) |
| witness B3 p1 upper long = 270 | 270 | 270 | yes |
| clean wall `outer` | 12/16 (4 az-90 views: depth 3.5-3.75 m -> `inner`) | >= 14 | **no** |
| inner (injected) | wrong az 0; wall correct 0/12; 4 `not_exercised` | >= 75 % | **no** |
| stability | 3 runs byte-identical rows (`d7938519…e307`), median 105.708 s, spread 0.229 s | identical | yes |
| invariance (reversed component order) | 16/16 clean rows `reversal_parity: true`, 0 changed | 0 changed | yes |

Clean registration: best IoU 0.931-0.961, margin to a different az 0.174-0.210 (threshold 0.75 / 0.05).

**H155: refuted** (two frozen clauses fail, both on the wall part). Sub-result az (which face direction):
confirmed on this fixture. Review readiness is separate (below).

Failure analysis (reported, not fixed — no retuning after the score):
- Clean wall: the az-90 facade of this building is stepped; the first footprint cell is 3.5-3.75 m below the
  bbox side, so the 2.0 m `outer` threshold calls a main elevation `inner`. A bbox-depth threshold cannot tell
  a setback from an inner corner.
- Injected inner: 12/12 rows read the same az, wall and depth as `clean` although 1.7-2.5 k pixels changed —
  the shift did not move the ray origin onto the notch (harness defect in the injection, likely the icon-vs-
  footprint notch mapping). Counted as failed by the frozen rule; as evidence it is **not measured**. The 4
  az-270 rows have no concavity on the arrow side -> `not_exercised`.

Not measured (unchanged from the contract): real untitled partial views, arrow->view association, rotated
keyplans on a real sheet, other arrow templates, Sokolniki transfer.

**Recommendation for the shared OKS step 'view<->face map sheet' (OBSERVE, not built here):** (1) when the
sheet carries a keyplan arrow, use the arrow + dihedral footprint registration as the first, cheap az cue with
the frozen abstain rule (IoU >= 0.75, margin >= 0.05) — 0 wrong / 48 answered rows, 48/48 abstentions where
expected; (2) do not decide outer vs inner-corner wall from the arrow ray depth; the wall needs a content cue
(view silhouette vs per-wall model render, #157/#159 line) and must abstain until that is measured on real
partial views; (3) Sokolniki STOP 04 transfer test after #2001 closes.
