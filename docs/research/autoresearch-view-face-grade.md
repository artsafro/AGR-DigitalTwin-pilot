# Autoresearch #160 — above-datum elevation extents (OBSERVE)

## Кратко для Артёма

Заливки PDF и надземная ортопроекция дали совпадение габаритов на **6 из 11** реальных фасадных видов против **1 из 11** прежним способом. Все шесть совпадений — на ЭЛВ; на «Олимпийском» — **0 из 4**. Во всех шести случаях противоположная сторона проходила тот же допуск. Поэтому метод не назначил ни одной стороны: **14 из 14 отказов**, включая три реальных фрагмента. Точность среди ответов не определена, а не 100%.

Для таблицы «вид ↔ грань» габариты стоит показывать как дополнительную проверку полноразмерного вида, но не как основание для переноса отделки. При двух подходящих сторонах нужно независимое подтверждение по осям, плану или геометрическому рисунку. Для фрагмента нужен интервал на конкретной стене; без такого подтверждения — вопрос, а не догадка. Сокольники не открывались: #2001 ещё открыт.

## Frozen contract

H160: on the exact #159 labelled cohort, measured finish-fill extents against occupied above-datum orthographic ray pixels recover at least 6/11 known full-view directions **as size-compatible** at the unchanged ±1.2 m width / ±1.0 m height tolerances, with zero confident wrong directions. This is a corroboration experiment, not a production step. A size-compatible direction is not an assignment. Compare A = #159 ground-wall rule and side envelope on fresh #145 line extraction; B = #149 painted fill union, extent of positive labels, versus occupied native ray centres at or above the fixed cutoff. Unique at 1× and no other candidate at 2× permits a proposed direction. Require abstention on the known oblique/sub-span p19 6-1 and all three real partials: B does not search intervals. Report separately both assignment accuracy (correct/answered; undefined if none) and abstention, plus compatibility on 11 full views. Wrong or fewer than 6 compatible refutes. Native wrong-side candidates are negatives; expected ambiguity includes opposing orientations with equal size. ELV p18 I-A is an active known-direction size recovery witness; if it does not recover, record that separately without tuning. Full and partial GT/boxes/scales remain those committed in #145/#151. No title/axis identity enters the assignment; scale is allowed as before. Model direction is not physical wall/bay truth.

Input manifest: #145 and #159/151 fixture and code blobs at immutable commits; #149 fill reader and native format at immutable commit; sealed ELV and Olimpijsky PDFs/ray grids and #157 walls at the hashes in `autoresearch-view-face-grade/run.py`. 0 labels in #149/#151 type grids are **misses**, not occupied (the #159 post-hoc type-mask used `>=0` and measured the full frame). ELV cutoff z=-0.15 m (drawn grade proxy cited in #159); Olimpijsky cutoff z=0.00 m (model project datum proxy, not a certified uniform site grade). Measure signed errors per view, report datum/plot scope differences rather than tuning. Perturbation: fill all empty native cells strictly below the fixed cutoff. Expect positive changes counted by album/azimuth and zero changes to B extents in each exercised case. With the cutoff disabled this constructed control must change occupancy, even if the outer bounds already span that region. Not a rejected delivery; labels are accepted drawing identities plus wrong candidate directions. Missing real rejected package / fresh native or blind transfer are not measured.

Budget: one new candidate, one median-of-three paired confirmation series, no new tuning rounds. First pair sets the time estimate; stop inconclusive if the full series cannot fit the remaining card time (hard cap 6 min overall for the measured series); retain partial artifacts and exact command. Each pair independently reopens/parses PDFs and recomputes both variants; native grids are immutable reused readbacks, so no fresh-render stability claim. Require deterministic per-view rows including exact candidate sets, and all input hashes identical before and after. Report range and median paired wall times separately from verdict. No edits to deliveries/shared code/other cards, no dropped scored cases, no hidden held-out reads, no adjusted tolerances or scale after scoring. #2001 OPEN; exclude Sokolniki entirely. #2073/#2074 own finish-partition scoring, #2075 owns wall-exercise repair. Atlas/trainer/form targets were considered and not reopened.

Replay (limited to hosts with mounted evidence): fetch `research/autoresearch-standing-149`, `research/autoresearch-standing-151`, `research/autoresearch-standing-157`, `research/autoresearch-standing-159`, then run `uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-grade/run.py tmp/ar160-NEW`. `uv.lock` and environment versions recorded in receipt. The runner refuses existing outputs and verifies the full input manifest. This is an OBSERVE report, not a new OKS command.

## Round log

**H160 confirmed for compatibility only; no assignment gain.** Frozen contract `98276bad`; measured runner `682fef14`. One treatment and 3/3 byte-identical paired results (first-pair estimate 73.9 s for three; observed per pair 24.6425 / 21.7334 / 25.5469 s, median 24.6425 s, range 3.8135 s; finished). All external input hashes unchanged. The runner and per-view rows are bound in [`receipt.json`](autoresearch-view-face-grade/receipt.json).

| Clean cohort | Known side inside A | Known side inside B | B correct / wrong / abstain |
|---|---:|---:|---:|
| ELV full views (includes 6-1 oblique sub-span) | 1/7 | 6/7 | 0 / 0 / 7 |
| Olimpijsky full views | 0/4 | 0/4 | 0 / 0 / 4 |
| ELV real fragments | diagnostic only | diagnostic only | 0 / 0 / 3 |

A reproduced #159: 13 abstentions, one top-cut row not scored. B had 14 abstentions, zero answers; no denominator for answered accuracy. B accepted the exact opposite direction alongside the true one on 6/6 compatible views. The preregistered ELV p18 I-A witness changed incompatible → compatible (ΔW −0.8 m, ΔH +0.8 m), and its opposite remained eligible. All Olimpijsky rows failed at least one tolerance: p5/p7 height residuals −4.4/−7.0 m; p6/p8 width residuals +5.8/+4.2 m. The fixed project datum proxy and stage/plot scope differ from a verified per-wall grade; these results do not distinguish those causes. The fill union includes any painted vector fill allowed by #149; it is not a semantic finish mask.

**Injected:** below-datum miss → hit changed 8/8 azimuth grids (3,789–9,610 cells per grid), 0 pixels changed above datum on each; per-grid counts are in the receipt. Without the cutoff these cells change the occupancy mask. **Not measured:** local grade profiles, physical wall/bay truth, interval matcher, assignment under fresh native import, rejected package, finish transfer and STOP 04. No product changes.

## Next measured steps

1. On a second, independently labelled album with real inner-corner views, score wall and bay separately. Include the opposite-side candidate as a hard negative; width/height alone cannot reject it here.
2. Test candidate-local bands between independently registered drawing and model levels for partials and mixed-stage sheets. Require a live trigger, a retained correct control, and a count of wrong answers, not just compatible sizes.
3. Test blind transfer to Sokolniki only after #2001 closes.

Full suite: deferred to merge batch (rule 68).
