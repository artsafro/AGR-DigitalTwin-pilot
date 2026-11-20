# PDF binding: bubble orientation scan (standing #6)

## Кратко для Артёма

Проверяем, ускорится ли привязка трёх листов, если не проверять заведомо неподходящие отрезки для каждой осевой метки. Режим OBSERVE: только временная подмена в стенде, без записи в рабочий код и пакеты.

## Frozen contract

Use the existing three-sheet #1321 evaluator and timing driver from #1705 at `eccaf6c174a0f1bb0d1ec69679e1a1f4fe133f17` (extract its archived driver and candidate into ignored `tmp/`; no edits to that PR). Base is standing #5's R3 (R1+R2); candidate adds only an orientation prefilter in `_bubbles`. Run `uv run --extra pdf-review python -m tmp.ar_bubbles --out C:/x/ar_t_5ba9d505/r4.json`. The wrapper must use the driver's `replay` and existing input/score guards; one unmeasured R3 warmup then BC/CB/BC, one scalar metric: median of three sums of public `bind_album` elapsed seconds, lower is better. Keep only if candidate/base ≤ 0.80, all three pairs faster, all six full canonical binding documents (three sheets per replay) and oracle verdicts match the warmup, and the complete affected tests pass. Also compare synthetic orientations including inclusive near-axis boundaries, preserved segment order, and competing orientations. Timing is not a quality score. Stop after one candidate, after a reproducible guard failure, or after 480 s of measurement, whichever comes first. No test deselection, relaxed thresholds/checks, cached binding output, altered corpus, delivered package edits or edits to other cards' files. No suite or DCC run. A keep is a proposal for normal PR review, not an automatic production change.
