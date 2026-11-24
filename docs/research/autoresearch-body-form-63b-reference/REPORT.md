# Standing #52 — Round log (OBSERVE)

**Гипотеза H52 подтверждена для одной ниши на восточном фасаде 63B.** Сравнение с линиями исходных стен вместо кольца сборщика восстановило порядок: принятый v007 ближе к эталону, чем каждый из v002–v006. Минимальный отрыв сменился с **−1,270 на +1,270 м** во всех трёх повторах. Это ретроспективная проверка известного дефекта, не независимая калибровка всего фасада. Код производства, модели и поставки не менялись; PR нет. Отчёт готов к ревью, метрика не готова к внедрению.

## Measured run

[Contract](../autoresearch-body-form-63b-reference.md) frozen at `2fa22206c2386b1ee51a3803fc55271156724201`. Final probe: `9f3f3089`. Run03 `complete`, 23.62 s, timing pair 2.21 s, no budget stop. Blender 5.1: 21 fresh imports, A/B operands shared each readback. Full input preflight and postflight (35 files), staged FBXs verified unchanged. Raw files and failed attempts under `C:/x/t_c75552ae-r52/`; [receipt](receipt.json) pins the exact dependencies. Replay on this PC: `python docs/research/autoresearch-body-form-63b-reference/run52.py C:/x/t_c75552ae-r52/replay01` (new path; conditional on timing as frozen).

| Exact #51 variant | E against builder ring, m | E against source walls, m | Changed section scores per repeat |
|---|---:|---:|---:|
| v007 `53189b83…` accepted | 1.270453 | 0.032808 | 2/2/2 |
| v002 `a57cb3fb…` rejected | 0 | 1.303262 | 2/2/2 |
| v003 `83f3289c…` rejected | 0 | 1.303262 | 2/2/2 |
| v004 `6d22c572…` rejected | 0 | 1.303262 | 2/2/2 |
| v005 `a387a459…` rejected | 0 | 1.303262 | 2/2/2 |
| v006 `b2b26d44…` rejected | 0 | 1.303262 | 2/2/2 |
| W_shift_opening `489d1c0e…` native control | 1.270453 | 0.032808 | 2/2/2 |

Identical scores at both sampled sections and in all repetitions; paired spread 0 m for each reference. Source wall IDs `fd517ed` / `185b002` bracket [3.414374, 4.717635] m; v007 has [3.444100, 4.714553] m, the rejected variants bridge it. The source is a typical-floor plan projection; +10.98 m is 0.03 m above the nominal +10.95 m floor top, inherited from #51, not a second independent height-specific source. The local measure is disagreement length on the outer wall line, not reveal depth or two-sided contour deviation.

- **Clean:** legacy report parity 21/21, full decoded payload minus candidate FBX path only. The old key still reports 0.768 m contour deviation at both levels on A; openings TP/FP/FN = 5/2/0 on A and 5/0/0 on R; legacy F unmeasured 3/18 and 5/18 respectively. Legacy depths 0.500 m / 0.000 m are the old scorer readings against an unresolved source 0.710–0.713 m, not new corroboration. No legacy verdict was overwritten.
- **Injected:** filling the source gap in a copy of accepted section data adds one chord per section (2/2/2 changed segments, no other section edits): local C rises from 0.032808 to 1.303262 m at both levels. The historical native opening shift still fails its 100 mm edge check (clean passes), but the local C delta is 0 across both levels and all three fresh imports. This tests locality for that witness, not invariance to all out-of-scope edits.
- **Not measured:** local effects outside the crop or between levels, source-derived reveal depth, new aperture counting, full-facade transfer, KPP1 NW / Sokolniki body pairs and render judges. The six exact labelled variants are from one lineage, not six independent buildings; no new geometry proxy was computed.

## Retained attempts and verification

- Run01 (0.25 s, no import): a full-precision key coordinate was compared to the frozen millimetre-rounded frame. Fixed the driver to use the latter, as specified; receipt SHA-256 `aca85f472fa47f67ce86112fffabe9bc43ee0d6ef2c68b89568d40c99cf259e7`.
- Run02 (28.84 s, complete/inconclusive): the control lookup assumed a short opening ID and missed the actual prefixed item. The complete receipt demonstrates parity and the intended fail only on the witness. The driver now resolves the unique full ID in the frozen key and checks both clean and injected status, without changing the threshold, reference or control. Receipt SHA-256 `e112f876f13fb994be877fe490d8c48094653849aa0e4e16958317bdc2037f7c`.
- Run03 repeated the full series; SHA-256 `6b8cc3625c1ee3b5e72d142d6f8ffd21f20243c923ccef89b0cf0d180fb1e1ca`.
- Affected tests: `uv run --offline pytest -q tests/test_body_contours.py tests/test_blender_exit_code_guard.py --basetemp C:/x/t_c75552ae-r52-pytest` → 41 passed. `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh` → 542 passed, 1 warning; `repo_guards: GREEN`. Full suite not run (rule 68).

Next targets: freeze a height-specific source wall mask on a different accepted/rejected pair; separately establish 63B reveal-depth reference from traceable source faces before changing the held-out depth checker.
