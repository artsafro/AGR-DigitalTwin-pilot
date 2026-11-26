# Autoresearch #121: SKELETONS-first sentence on held-out 63B (one OBSERVE A/B)

Card t_cc06dd03 (standing #121). Decision: Artem 2026-11-26 ~22:00, «Да» to the question of #122 (t_ee783d8d).
He allowed ONE bounded OBSERVE A/B on 63B outside the regular schedule, with the current Drive manifest, after
checking that the builder cannot see the accepted versions. The isolation rule is the one used for the G22 key: the
path never appears in the builder context, and a post-run audit of reads fails the run if the builder read it.
OBSERVE only: no product code, no bank change on `main`, no merge.

## Contract (frozen before the run)

- **Hypothesis H121.** On held-out `63b-stage1` the #1924 phrase "read `docs/agents/SKELETONS.md` FIRST (it lists
  every stage command)" moves the first failing step later than the baseline. On G22 (tuning) it moved from
  `artifact` to `form_v2`, one pair only.
- **Command.** `uv run -q agr trainer --bank <BANK> ab 63b-stage1 --ab <OLD> <NEW> --scope INVARIANT --lane codex
  --out <OUT>`. The A/B mechanism, its scoring and its verdicts come from [D415] and `docs/trainer/ETALONS.md`.
  Nothing is reimplemented.
- **Metric.** The `ab.json` verdict (`fixed` / `unchanged` / `regressed` / `inconclusive`) and `first_failing_step`
  for old and new. Secondary, report only: commands, wrong-turns, input tokens, stages used.
- **Series.** Exactly one pair, because the user authorised ONE. The median-of-3 rule does not apply. No rerun after
  a bad arm, and no second candidate.
- **Outcome rule.** Isolation audit `pass` on both arms and verdict `fixed` gives **confirmed (n=1)**. Verdict
  `unchanged` or `regressed` gives **refuted (n=1)**. Verdict `inconclusive`, a preflight fail or an audit
  `fail`/`error` on either arm gives **inconclusive**. With n=1, LLM run-to-run variance is not controlled. No KEEP
  is possible: a KEEP needs 3 fresh pairs per etalon (#122 next 1).
- **Variants.** OLD = an empty folder (the `origin/main` baseline). NEW = `AGENTS.md` of the head with one change
  on line 7. `One door [D324-D327]: \`docs/agents/SKELETONS.md\` -> ...` becomes
  `One door [D324-D327]: read \`docs/agents/SKELETONS.md\` FIRST (it lists every stage command) -> ...`.
  This carries the #1924 wording over to the current entry line. The #1924 variant file itself (54b63bab
  AGENTS.md) would revert later AGENTS.md changes.
- **Bank.** A copy of `docs/trainer/etalons.json` at the head (sha256 `016aab0c…`). In that copy, 63B has
  `practice_ready=true` and no `missing`; every other field is the current Drive manifest. Admission is
  `trainer.load_bank` (`bank_problems`: Drive paths and sha256).
- **Isolation preflight** (`trainer_63b_ab_r121/isolation.py preflight`). It builds a real scrubbed practice tree
  of the head and scans it for these FAIL patterns: the key and rejected tokens (`scan_tokens`), the Drive stores
  of accepted 63B versions (`1619-body-training`, `1855-trainer-v0`, `stage2-63b`), the hidden job `POLY63-B`, the
  path of the unscrubbed main checkout (`agr-pilot/AGR-DigitalTwin`, `AGR-DigitalTwin/jobs`) and the stored run
  dumps `C:/x/trainer/runs`. Pass = 0 files left and a prompt with no hits.
- **Post-run audit** (`isolation.py audit`). It scans each arm's `events.jsonl` commands, agent messages and every
  file the agent wrote (practice tree changes and `built/`) for the same FAIL patterns. Any hit = `fail`, and the
  arm counts as not passed. A missing transcript = `error` (fail closed). Mentions of `AGR-evidence`, `AGR-assets`
  and `G:/` are recorded as WARN.
- **Forbidden.** Editing `docs/trainer/etalons.json` or the trainer on this branch; touching #1917/#1928/#1970
  files; rescoring old dumps as evidence; a second pair; Max.
- **Positive trigger witness.** The preflight on the unmodified bank must fail, so that the scan is shown to fire
  (see round 0). Accepted control: 63A/G22 are not rerun (cost; authorised scope is 63B only), so collateral
  impact is **not measured**.

## Round log

See `trainer_63b_ab_r121/ROUNDS.md`.
