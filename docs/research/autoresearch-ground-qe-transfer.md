# Standing #36 — paired NPM/VPM transfer of Ground short-edge density (OBSERVE)

## Кратко

Проверяем, переносится ли уже измеренный в #35 показатель коротких рёбер на три сданные пары НПМ/ВПМ. Только наблюдение, не приёмка и не правка Ground.

**H36 подтверждена на этой выборке.** На всех трёх парах Qe = 0 в обоих профилях; у отклонённых SIL13 r1–r5 — 215,95–250,35. Первый OBJ ядра #1738 снова дал 69,84 (185 коротких рёбер на 26 491 треугольник). Сданного контроля с ненулевым Qe и независимо отклонённого ВПМ нет: порог приёмки не обоснован. Изменений рабочих проверок и моделей нет, PR не открывался.

## Frozen contract — before scores or new readbacks

Only target: Qe = 10,000 × E/T, lower is better, from the unchanged #35 implementation at `ec403b83113d89f6b8a98f648421a33a17819603`. E counts undirected polygon edges of length ≤2 mm including zero; T counts k−2 per polygon. Scope is the one non-UCX mesh ending `_Ground`, identical to #35. If ambiguous or absent, retain census and classify unavailable, not zero. VPM Ground can contain merged context; this measures the exported named node, not a recovered terrain-only part or native Max state. No per-component exclusion beyond #35. #1738/#1787 own construction, relief and skirt; #1315/#1622 own cold delivery; body is closed; #35 owns original NPM metric.

Fixed inputs: A1–A8 and SIL13 F1–F5 from #31 `dumps.sha256` on `C:/x/ev_t_193a0887/dumps-v002`; F3 and F5 share geometry. Fresh paired controls use latest available revision copies already staged with `C:/x/ground-etalons/standing-32/SHA256SUMS.txt` and `SOURCES.txt`, listed below (no edits to originals or copies):

| paired project | NPM SHA-256 | VPM SHA-256 |
|---|---|---|
| Skolkovo (A2) | 91910cb6f4741fc4f376f25f7a2e994e88c1a16c434f33f188b6e35666906d55 | d2dcb79efdc9772de2859b138fffc22e85b08bb91f560bd377c44b4f2bffa85b |
| COD (A3) | 01d5fb3b013eee95eae5f61ab73361fe1012a0a7348b2ca0738267ceac0412df | 8ed0e8b146d27ef5dc986cbeffec72e831fb3e4674435d4b843807acbd8b17d1 |
| Donskoy (A4) | 943bfb01e4f3cd949ac57227546842f0cf5ea238e6f6dd27d23476fa867c8306 | 9976c93708f17c5ce248b40c5db3ec2f73854db4d77c1f256235c1889fe816bd |

H36 is narrow: all available accepted controls including all three VPM must score below all SIL13 NPM r1–r5, with #35's frozen margin `min(F) >= 2 * max(1, max(A))`. Vatutino v015 NPM stays in A. No claim about rejected VPM or universal transfer. Confirm only on complete series and parity: all A/F exact E,T,V and median parity to #35; fresh NPM E,T,V parity to their frozen A2–A4 counters; same hash before/after readback. Refute on full series if separation or parity/stability bounds fail; inconclusive on unavailable/ambiguous scope, failed readback, capacity, or incomplete series. Collateral control fires iff a real accepted input has E>0; if none, not measured (no substitutions). No adoption/gating regardless of verdict.

Three scores for each input, median and spread; for each real input repeat #35 rigid perturbation (30° Z, shift +123.456/−78.9/+3.21 m): E,T exactly unchanged; publish paired VPM−NPM Qe differences and per-input spread. Positive witness: A1 Vatutino and each fresh accepted control, #35 injection up to 50 1 mm short edges, expected ΔE ≥25 with T unchanged. Synthetic injection in memory only, not accepted collateral evidence. Record any failed mutation as such. Fresh readback: same pinned Blender 5.1.2 and image search off as #31; raw dump via existing runner then scale to metres. Preserve manifest, input and dump hashes and census; no repair/fallback rewriting geometry.

One confirmation series, zero new candidates. First timed paired import+score Skolkovo NPM/VPM; cap 240 s for series from launch and ≤ available card time; if 4× first pair >240 s, stop inconclusive, no downsizing. Each DCC subprocess max 45 s or remaining budget, whichever smaller. If confirmed, replay the existing score on the first #1738 OBJ `C:/x/ev_t193/sil13_shared_v003/SM_SIL13_Ground.obj` pinned by #35, three evaluations with exact #35 E/T/V parity; not a new build. No newer OBJ is assumed. Ground packages, historical evidence, tolerances, validators, other cards and tests remain untouched; no test deselection. No KEEP based on private scratch.

Replay in this worktree: `../../.venv/Scripts/python.exe docs/research/autoresearch-ground-qe-transfer-r36.py NEW_WORKSPACE_DIR` (use a fresh output directory, versioned by caller). The wrapper reuses #35 scorer and #31 import and reads #35 and #31 receipts; no changes to those files. Inputs are private, replay limited to this PC. Skirt, actual delivery budget, source-visible deviation, native Max and independently rejected VPM are not measured.

## Round log

Contract `2b7adfdc`; one complete run, first pair 7.53 s, total 158.46 s, cap 240 s. The larger Donskoy VPM made the first pair a poor total-time predictor; the observed series still fit the cap. All six source hashes match the frozen contract. Raw receipt `C:/x/ev_t_cb0ffb18/r36-v001/receipt.json` and committed copy `autoresearch-ground-qe-transfer-r36.json`, SHA-256 `ce8b4ad488b43290c00f4ea43cd041f8ef18f48fa93c4507b25b2027135b6991`. Readbacks, logs and per-input manifests under that versioned directory. Measured wrapper SHA-256 `c49f0c3257c2f4b253023278b258727fbb8f5e2bfc11266ebd8df8540c35cd09` (worktree bytes).

| Paired site | NPM triangles | VPM triangles | median Qe NPM → VPM | within-input spread (NPM/VPM) | rigid E,T | injected ΔE (NPM/VPM) |
|---|---:|---:|---:|---:|---|---:|
| Skolkovo | 5,733 | 19,673 | 0 → 0 | 0 / 0 | identical | +50 / +50 |
| COD | 2,801 | 47,677 | 0 → 0 | 0 / 0 | identical | +50 / +50 |
| Donskoy | 11,528 | 989,408 | 0 → 0 | 0 / 0 | identical | +50 / +50 |

- **Clean:** 19 inputs, 3 calls each, zero spread and exact rigid E,T parity. All 13 frozen NPM dumps and three freshly read NPM nodes match #35 E,T,V. Vatutino v015 = 0, weakest separation is SIL13 r4 = 215.9486, greater than frozen floor 2; all five SIL13 variants worse than every accepted node. Qe = 0 does not imply xView = 0: Donskoy VPM had 6 near vertices (companion diagnostic), but no short polygon edges. The large VPM triangle counts are node counts, not terrain-only area or full-delivery budget evidence. Core v003 exact parity with #35, spread 0.
- **Injected:** +50 on A1 and all six fresh controls, unchanged T, above bound +25. No mutation of input files. Existing accepted exports with E>0: none, so real collateral impact not measured.
- **Not measured:** independent rejected VPM or second short-edge defect family, native Max, visible deviation, skirt and delivery budget. No inference about universal calibration or promotion to a gate.
- Affected tests: `../../.venv/Scripts/python.exe -m pytest -q tests/ops/test_xview_gate.py tests/qa/test_xview_dump_contract.py` — 179 passed. Full suite: deferred to merge batch (rule 68).
