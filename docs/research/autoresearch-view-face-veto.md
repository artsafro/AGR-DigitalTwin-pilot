# #147 — Raw-vs-chance disagreement veto for elevation-to-face matching (OBSERVE)

**Кратко (RU):** раунд #147 проверяет «вето несогласия», предложенное в #146: ответ «вид → фасад» выдаётся только если
сырой оценщик #140 (A) и оценщик с поправкой на случайность #146 (B) независимо выбрали один и тот же фасад; иначе — отказ
(вопрос Артёму). Метрика: верно / неверно / отказ по когортам; граница — ноль уверенных ошибок при сохранении покрытия.
Соколники (#2001 OPEN) не открываются. Результат — в `autoresearch-view-face-veto/result.md`.

## Frozen contract (written before any measurement)

Target: view -> face assignment accuracy (correct / answered) and abstain rate on views with a known answer, under a rule
that must abstain rather than guess. Previous rounds: #139-#146 (backlog). This round continues the #146 harness; no new
scorer, no threshold search.

- **A** = pinned #140 2D edge scorer (0.30 floor, 0.10 cross-face margin) as exercised by #145 ELV, #140 KPP1/AC08,
  #142 OBR22. **B** = #146 chance-corrected F1 with the same floor/margin. Both are produced by the unchanged #146 runner
  `e839c2ee177c8ea5a766988019f2db6e55b1e61a:docs/research/autoresearch-view-face-density/run.py`, which itself enforces
  full historical A-row parity (212 rows) and input/staging manifest pins (ELV fixture SHA-256, KPP1/AC08 manifest,
  OBR22 hashes, Blender SHA-256).
- **C (candidate)** = `A.answer if A.answer is not None and A.answer == B.answer else abstain`. Exactly this variant;
  no other candidate. No labels, other views or historical scores inform C.
- **Parity proof:** per pair, A and B rows (picks, scores, verdicts, groups) must equal the published #146 receipt rows
  (`e839c2ee:docs/research/autoresearch-view-face-density/receipt.json`, 212 rows) byte-for-value; else status
  `b_parity_failed` and no verdict.
- **Gate (H147 confirmed iff all hold on the final pair, all three pairs identical):**
  zero C wrong on every row (clean full/fragments/top-cut, injected synthetic crops, exercised mirrors, AC08, OBR22);
  ELV full C correct >= 5 of 7; ELV synthetic crops C correct >= 15 of 63 (A level); ELV real fragment `p23 frag D-G`
  correct; KPP1 full C correct >= 3 of 4; KPP1 synthetic crops C correct >= 20 of 36 (A = 22, at most 2 lost);
  AC08 abstains on all 40 clean rows. OBR22 and AC08 give no positive-retention evidence (A has 0 correct there) —
  reported as **not measured** for retention.
- **Positive trigger witness:** the 13 #145 ELV crops where A wrongly picks the dense east face (az 0) — C must abstain
  or answer correctly on each. **Accepted control where the rule fires:** every accepted-project row where exactly one of A/B
  is correct (C abstains there; counted as lost coverage per group). Trigger on a B-only wrong: KPP1 full `В-А`
  (#146: A abstain, B wrong) — C must abstain. Expected direction: wrong(C) <= min(wrong A, wrong B); correct(C) <=
  min(correct A, correct B) per group. Mirrors are injected negatives; unchanged-pixel mirrors are `not_exercised`.
- **Budget:** one series = 3 fresh paired native runs, fresh output dir per run, ceiling 1500 s (one #146 pair = 299 s);
  stop `budget_stop` (inconclusive) if `elapsed + 1.15 x first pair x remaining pairs > 1500`. No confirm-vs-new
  candidate split: 100% confirmation of C, zero new candidates. Report median/min/max pair wall time.
- **Forbidden:** threshold/floor/margin changes, editing #139-#146 objects, labels, delivery packages or guards,
  deselecting rows, opening Sokolniki outputs (#2001 OPEN), auto-applying anything.
- **Not measured:** real unlabeled inner-corner transfer, within-face (bay) position, G22, Vatutino, Sokolniki,
  perturbations other than synthetic crops and mirrors.

Replay (pilot host, repository root; historical refs #139/#140/#141/#142/#145/#146 fetched):
`uv run --offline --locked --extra cad --extra pdf-review python docs/research/autoresearch-view-face-veto/run.py C:/x/ar147/<fresh>`.
Inputs live on the pilot host (workspace paths and mounted sources); off-host replay is limited.
