# Autoresearch #145 — view -> face transfer test on a fresh asymmetric pair (ELV TC Sreda, OBSERVE)

## Кратко для Артёма

Проверил лучший метод прошлых раундов (#140 B: линии чертежа против ортопроекции модели, порог отрыва 0,10)
на новом, никогда не использованном объекте — ТЦ «Среда» (ЭЛВ): векторный буклет АГР + Revit FBX. Здесь есть то,
чего не было на KPP1/AC08: косая стена (вид «6-1»), пристройка с внутренним углом и три НАСТОЯЩИХ фрагмента фасада
на других листах (без названий и осей для метода).
**Итог: гипотеза опровергнута.** На реальных видах метод безопасен: 7 полных фасадов — 5 верно, 0 ошибок,
2 отказа (косой «6-1» и западный «А-И»); 3 реальных фрагмента — 1 верно (вход Д-Г), 2 отказа, 0 ошибок. Но на
63 синтетических обрезках — 13 уверенных ошибок, и **все 13 указывают на один и тот же восточный фасад** (сплошной
витраж: в модели Revit там больше всего рёбер — он «притягивает» любой полосатый фрагмент). Это новая, ясная причина:
оценка не нормирована на «насыщенность» кандидата. Проверка после замера (не принимается как результат, только
подсказка следующему раунду): вычесть из оценки кандидата его медиану по остальным видам того же альбома —
ошибки на обрезках 13 → 2, верных 15 → 24, полные фасады 6/7 верно без ошибок. Три прогона — байт-в-байт одинаково.

Рекомендация для шага OKS-трассы «view<->face map sheet» (не реализован, OBSERVE): (1) сначала оси/ключевой
план/название вида; (2) для неподписанных — метод B только для ЦЕЛЫХ видов (0 ошибок на 7+4 реальных видах
двух объектов) и только с отказом при отрыве < 0,10; (3) фрагменты и частичные виды — пока всегда вопрос с двумя
лучшими кандидатами, пока нормировка «по альбому» не подтверждена на свежей паре; (4) фрагменты с обрезанным верхом
(как лист 20) метод B принципиально не видит — их привязывать только по осям/тексту. Сокольники не открывались.

**Hypothesis result:** H145 **REFUTED** (13 confident-wrong synthetic crops; full-view bound met 5/7 >= 4).
Run status: finished, 3/3 pairs byte-identical. Review readiness is separate (below).

Card t_6c816f20, branch `research/autoresearch-standing-145`. Focus 0 (Artem 2026-11-27 ~15:05): tie every elevation
view on a sheet, including untitled partial views, to the model face it shows; abstain (ask) below a threshold.
Sokolniki (#2001, OPEN) is HELD OUT and was not opened.

## Frozen contract (committed before any scoring)

**Why this target.** #139-#144 measured view->face only on KPP1/AC08 (boxes, synthetic crops) and OBR22 K02
(raster). #140 B (2D drawing lines vs orthographic mesh edges) was the only CONFIRMED method, on calibration only;
its own next step was "a second asymmetric, independently labelled PDF/model pair to test transfer before
implementing an OKS step". ELV TC Sreda (`jobs/elv-tc-vpm`, sources.json) is such a pair and was never used:
vector AGR booklet (42 sheets, SHA-256 `49c10527...`) + Revit 2023 FBX (SHA-256 `7ccf502d...`). It has what the
earlier cohort lacked: a slanted (non-axis) wall drawn true-length as its own view (`6-1`), a west annex with a
re-entrant corner, a recessed entrance, and three REAL partial views (fragments) on other sheets.

**H145:** #140 B, unchanged (pinned `score.py` @ `ab33b7e4`, thresholds score >= 0.30 and margin >= 0.10, 0.1 m/px,
width slack 0.6 m), transfers to ELV: zero confident-wrong answers on all clean cases AND at least 4 of 7 real full
views answered correctly. Refuted if any clean case is confidently wrong or fewer than 4/7 full views are correct.
Fragments are reported separately (n = 3 is too small for a rate) and must not be confidently wrong either.

- **Metric (one number + abstain):** correct / answered and abstain / total per group: real full views (7: p18 I-A,
  p18 1-10, p19 10-1, p19 A-I, p19 6-1, p21 I-A, p21 1-12), synthetic crops of those (63, #139 scheme 25/40/60 % x
  left/centre/right), real fragments (p23 D-G 1:100, p24 8-9 1:100), real top-cut fragment (p20 9-10, 1:20; B
  aligns tops, so its precondition is violated: expected abstain). Safety = confident-wrong count.
- **Candidates:** 4 sides, az 0/90/180/270 (as #139/#140). The slanted wall (about 5.9 deg off +Y) belongs to side
  az 90; its orthographic foreshortening is 0.5 % (0.25 m over 50 m, inside the 0.6 m slack). Face identity is
  side-level; within-face localisation is NOT scored (not measured).
- **GT (independent of the method):** title convention (left axis -> right axis seen from outside) mapped to the model
  frame via the ray-cast roof footprint: axes 1..12 west->east (12 = east wall with the rounded entrance recess, p23
  plan fragment), axes A..I north->south (I = south: p20 section B-B, p24 plan fragment). Visual cross-check before
  scoring (`preview` contact sheet: stepped wood volume and loading gates have the same handedness in drawing and
  render). Recorded in `autoresearch-view-face-elv/fixture.json`.
- **Front end (frozen before scoring):** PDF vector items fully inside a per-view box that excludes titles, axis
  bubbles, dimension chains and level marks; only segments within 2 deg of horizontal/vertical, longer than 0.05 m
  (drops glass hatch, rhomb callouts, letter curves); rasterised with #139 `raster_view` logic. Scale (pt per m) from
  the x-distance of the two end axis labels and the written dimension (labels used ONLY for scale; p20 from the
  +2.700/-0.100 level marks). Callout boxes and leader lines that overlap the facade (p21, p20) stay in: real noise.
  Model: pinned #139 `rays.py` @ `38f7d95e`, one change: skip mesh objects with world max z > 30 m (one stray
  Revit batten at z 166 m; building top 16.4 m).
- **Controls:** injected mirror of each full view (changed-pixel count, `not_exercised` if 0), not pooled with clean.
  Positive witness = the 4 axis-aligned full views (distinct silhouettes); hard case = 6-1 (slanted, sub-span of
  side 90) and the p21 sheets (callout boxes over the facade). Symmetric-negative control: p18/p21 I-A are nearly
  mirror-symmetric glazed entrance facades - a confident answer is allowed only on the correct side.
- **Repeatability / budget:** 3 fresh pairs (new Blender ray cast + new PDF read each, not rescoring a dump), outputs
  must be byte-identical; one pair measured at about 36 s in the preview, budget 15 min. ONE variant only (B as is);
  no threshold or box change after the first scoring. A failed bound is a result, not a reason to retune.
- **Forbidden:** editing sources/deliveries/other cards' files, tuning boxes/thresholds after scoring, opening
  Sokolniki outputs, presenting synthetic crops as real views, deselecting tests.
- **Replay:** `uv run --offline --extra pdf-review python docs/research/autoresearch-view-face-elv/run.py <new_dir>`
  (pilot host: inputs in the owner's named folder per `jobs/elv-tc-vpm/sources.json`; needs
  `git fetch origin research/autoresearch-standing-139 research/autoresearch-standing-140`). All inputs and upstream
  bytes are SHA-256 checked at stage time and the inputs again after the run. Replay is limited to hosts with that
  folder; hash-identical copies go to the evidence folder.

## Round log (one frozen variant, no change after scoring)

Contract commit `7f175843` (before any scoring). Run `C:/x/ev_t_6c816f20/run1`: 3 fresh pairs (new Blender ray cast
+ new PDF read each), pair wall 157.5 / 157.3 / 166.4 s (median 157.5 s, range 9.0 s; total 482.6 s incl. staging;
the 36 s preview estimate excluded the 80 PDF-scoring cases), all three pair outputs byte-identical (content
SHA-256 in the receipt). Inputs re-hashed after the run: unchanged.

| Group (clean unless noted) | correct / wrong / abstain | Bound | Outcome |
|---|---:|---|---|
| Real full views (7) | 5 / 0 / 2 | >= 4 correct, 0 wrong | met |
| Synthetic crops of those (63) | 15 / 13 / 35 | 0 wrong | **missed** -> H145 refuted |
| Real fragments 1:100 (p23 D-G, p24 8-9) | 1 / 0 / 1 | 0 wrong | met |
| Real top-cut fragment 1:20 (p20 9-10) | 0 / 0 / 1 | expected abstain | met (scores 0.985 vs 0.951: attractor, see below) |
| Injected mirror of full views (7 exercised) | 2 / 1 / 4 | reported only | 1 wrong: mirrored 10-1 -> 270 (handedness, as #139) |

Per-view facts (receipt rows):
- Full: I-A (p18, p21) -> 0 with margins 0.239 / 0.255; 1-10 / 1-12 -> 270 (0.280 / 0.294); 10-1 -> 90 (0.104).
  Abstain: A-I (180 best, margin 0.088), slanted 6-1 (best 0 at 0.563 over the true 90 at 0.527).
- **All 13 wrong crops pick az 0** (east glazed curtain-wall entrance; densest Revit edge field). The real
  fragment p24 8-9 (true 270) also ranked az 0 first (0.737 vs 180 at 0.637, true 270 third at 0.583; margin
  0.0998, abstained by 0.0002) and the
  top-cut p20 scored 0.985 on az 0. Diagnosis: the harmonic mean of hit fractions rewards a candidate with many
  edges; a dense candidate is a universal attractor for any striped drawing (cassette joints, panel lines).
- KPP1/AC08 (#140) had no such dense face, so the bias was invisible there.

**Post-hoc diagnostic (not a keep; rescoring the frozen receipt is not stability evidence):**
`posthoc.py` subtracts from each candidate score that candidate's median over the OTHER views of the same booklet
(sheet-level, no GT). Margin 0.10: full 6 / 0 / 1, crops 24 / 2 / 37, fragments 0 / 0 / 2. Margin 0.05: full 7/0/0,
crops 38 / 6 / 19. Still not safe on crops; it is the next hypothesis, to be frozen and measured on fresh pairs
(this booklet as regression + KPP1/AC08/OBR22 + Sokolniki after #2001).

Clean vs injected vs not measured:
- Measured clean: 7 real full views, 3 real fragments, 63 synthetic crops (labelled synthetic).
- Injected: 7 mirrors, all exercised (changed pixels 19 624 - 49 614).
- **Not measured:** within-face localisation (which bay a fragment shows), Revit view names / keyplans as
  algorithms, raster PDFs, the faces of the west annex / re-entrant corner as separate candidates (side-level only),
  finish-callout transfer and STOP 04, Sokolniki (held out).

## Recommendation (OBSERVE, not implemented)

Shared OKS-trail step "view<->face map sheet" (core + `agr` command): order = axes/keyplan/titles first; untitled
WHOLE views by #140 B with margin 0.10 (0 confident-wrong on 11 real full views over KPP1 + ELV); partial views and
fragments always a two-candidate question for now; the sheet must print, per view, the top-2 candidates, scores and the
reason for abstaining. Before any partial-view auto-answer: freeze the sheet-level candidate-prior normalisation and
measure it on fresh pairs with zero confident-wrong as the bound.

## Replay and evidence

```
git fetch origin research/autoresearch-standing-139 research/autoresearch-standing-140
uv run --offline --extra pdf-review python docs/research/autoresearch-view-face-elv/run.py <new_dir>
python docs/research/autoresearch-view-face-elv/posthoc.py <new_dir>/receipt.json
```

Receipt: `autoresearch-view-face-elv/receipt.json` (SHA-256 as committed, LF: `539e946200b711e69a8f9377d51159d6320ee540825cd1c4ef141c3b742482bc`;
evidence copy `run1/receipt.json`, CRLF as written on Windows: `372a8f672ffbb0e09ff1d36cb1c70813b79f7ec5148fd59a8b49573b778c547a`). Evidence (staged hash-identical PDF/FBX inputs, all pair JSONs,
ray npz, logs, view/model edge previews, GT contact sheet `sheet_main.png`):
`G:/Мой диск/AGR-evidence/145-view-face-elv/` + `SHA256SUMS.txt`. Replay is limited to the pilot host (owner's
named folder or the evidence copies; Blender 4.4 pinned by SHA-256).

## Checks

Affected tests: `env -u PYTEST_ADDOPTS uv run --offline --extra pdf-review pytest -q -p no:cacheprovider --basetemp C:/x/pt_t_6c816f20 docs/research/autoresearch-view-face-elv/test_run.py` — 4 passed.
`bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` — GREEN (568 passed).
Full suite: deferred to merge batch (rule 68). No product code changed.
