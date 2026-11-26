# Autoresearch #122 — first-module dependency triage (OBSERVE)

## Frozen contract

- **H122.** Explicitly separating first-module blockers from replication/package blockers after PartsList increases the number of cold runs that pass the unchanged trainer `artifact` step, without permitting a guessed module or scope reduction. This is not the FBX-first instruction from #1917, the missing G22 adapter from #1928, the occupied output slot from #120, or the SKELETONS-first sentence from #121. `artifact` is the first scored failure in 3/4 rows of `docs/trainer/ledger.json` (last ledger change `28430fbe`). It does not explain why execution stopped.
- **Exact variant.** OLD is an empty overlay. NEW differs only by this one appended AGENTS.md paragraph (practice only, not a policy edit):

  > In trainer practice only, after PartsList, separate questions that block the first BM-12 module from questions that only block replication or packaging; use the documented route to build and check the first module from verified source evidence before stopping for the latter questions, but stop if that module itself lacks evidence.

- **Fixture and direction.** Tune on KPP1 v004. Independent transfer on bank split `held_out`, `sokolniki-body-v005` only; do not tune on its key, rejected versions, or builder results. Positive opportunity witness: the retained KPP1 r111-1 final note mentions absent package GeoJSON while no first module was made (this does not establish that there was enough first-module evidence). Holdout accepted/rejected package/model quality must be calibrated with the unchanged applicable native steps before interpreting a quality result; no accepted control is asserted to trigger the wording yet. If a missing first-module dependency is documented, expected effect on artifact passes is zero, not a bypass. For an exercised packaging-only blocker the expected direction is positive. Missing geometry/units, a protected read, and an identical overlay have zero allowed false credit. No-op controls are `not_exercised`.
- **Metric / budget.** Score a valid arm as 1 for `steps.artifact.status=pass`, 0 for a measured fail; no read audit/invalid arm = not measured. Median of 3 paired `new - old` values per etalon, with all three deltas and min/max. Require +1 on both and no regression on the native accepted/rejected controls, holdout audit, declared whole deliverable and unchanged checks. One candidate, three pairs per etalon, no further candidate or confirmatory series in this card. Per arm maximum 1800 s. Start none until bank admits both and its owner confirms copied source hashes, the builder cannot access approved versions, and post-run read audit will fail closed. A missing prerequisite or incomplete series is `inconclusive`, not 0/3 or `refuted`. No fresh cold runs or DCC without that gate.
- **Parity.** Same pinned approved Git revision, provider/model, manifest and sources, task, order and limits; separate clean roots per arm. The only treatment is one paragraph. No loosened scoring, deselection, archive rescoring as stability evidence, bypass of D391 or other gates, edits to delivered packages or other cards' files, edits to trainer/bank, Max or auto-application. FBX header success is not native acceptance. An admitted control must have both accepted/rejected native quality checks exercised before claiming parity.

## Read-only admission round (frozen before execution)

Use the preflight CLI from `8531433d1f1a1e4860ce156fd29d7e0b20bf5903`; latest main consulted for the unchanged bank and ledger: `83e44c0c863fdd70839b76a9cab384618ed8af84` (#1970). Live scoring, if eligible later, requires the audited trainer; this old CLI is only used for dry-run.

Generate the variant from `git show 83e44c0c863fdd70839b76a9cab384618ed8af84:AGENTS.md` plus a blank line and the exact paragraph above, UTF-8 LF with final LF. Use new directories `$root/old` (empty), `$root/new` (only AGENTS.md), `$root/same` (distinct empty), and fresh `--out` paths. Compare OLD vs NEW for KPP1 and Sokolniki three times with output directories absent. Also check the separate run admission and an identical-byte negative on the admitted control. Repeat runs are CLI admission replays, not independent cold trials.

```bash
uv run -q agr trainer ab "$etalon" --ab "$root/old" "$root/new" --scope INVARIANT --lane codex --out "$root/$etalon-ab-$i" --dry-run
uv run -q agr trainer run "$etalon" --lane codex --out "$root/$etalon-run" --dry-run
uv run -q agr trainer ab kpp1-v004 --ab "$root/old" "$root/same" --scope INVARIANT --lane codex --out "$root/same-refusal" --dry-run
```

Expected: KPP1 A/B reports one AGENTS.md edit, the identical variant is refused, and no output path is created. An admission refusal on Sokolniki stops before overlay/application or input hashing: report that treatment as not exercised. KPP1 `run --dry-run` checks source path existence but not content hashes. No builder, key open or native acceptance measurement in this round.

**Conditional next command (bank owner, only after admission/isolation):** verify the bank manifest + every source SHA-256, pin `origin/main` and overlay base/hash before each pair, then run `uv run -q agr trainer --bank "$bank" ab "$etalon" --ab "$root/old" "$root/new" --scope INVARIANT --lane codex --timeout-s 1800 --out "$root/$etalon-pair-$i"` for `i=1..3`. Check the pinned revision in each arm, record independent post-run read audits and native accepted/rejected controls. Do not use the one-off 63B approval for this series.

## Admission receipt — 2026-11-26

**Результат H122: inconclusive.** Проверка допуска повторилась трижды: KPP1 принял оверлей с одной правкой, Sokolniki отказал до чтения оверлея. Холодный эффект формулировки не измерен. Изменения в рабочие инструкции не внесены.

Contract committed before execution as `d840f942`. Raw SHA-256 of replay inputs:

| Input | SHA-256 / identity |
| --- | --- |
| Base `AGENTS.md` (Git bytes) | `0cc3820ad0ff4f946aaa04846e4873f9939187cf1b2fd7d49cc488c355d2d881` |
| NEW `AGENTS.md` (rebuild from frozen one-paragraph recipe above) | `144773457a1bc35514b22ec07186b706bc3f10224eb179d8c4b62d6091fda0ab` |
| Bank (same Git and local bytes) | `016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635` |
| Local ledger | `230eace1a0a434cb25091f449760d3895d5b7d169086a2f2ba049db88a8496a7` |

| Preflight check | Exit codes | Wall seconds | Effect |
| --- | --- | --- | --- |
| Clean, `kpp1-v004` A/B admission | 0, 0, 0 | 0.609, 0.550, 0.723 | One AGENTS.md edit, no scope warnings, all three. This is a bank/CLI control, not a native accepted model control. |
| Clean, `sokolniki-body-v005` A/B admission | 2, 2, 2 | 0.511, 0.539, 0.512 | `is not practice_ready`; zero overlay checks because admission stops first (`not_exercised`). |
| Clean, separate run admission, KPP1 / Sokolniki | 0 / 2 | 0.663 / 0.588 | KPP1 prompt printed; Sokolniki source set DWG/PDF not hash-bound in the bank. No builder or source hashing. |
| Injected, two distinct but byte-identical overlays (KPP1) | 2 | 0.557 | `variants are identical: nothing to probe`; zero changed files. |

No output path created in 9/9 probes. 5.252 s summed CLI wall time. A/B admission timing medians were 0.609 s / 0.512 s, paired KPP1 minus Sokolniki spread 0.011–0.211 s; these are timings of different admission paths, **not** an estimate of the candidate's effect. Initial setup attempt exited 1 (`WinError 3`, absent `tmp/` parent) before any probe; switched to creating parents in the owned worktree. The full preflight commands above can be replayed; the KPP1 run-admission control requires the bank's Drive source paths to resolve.

**Not measured:** fresh cold `artifact` passes and paired deltas (0 valid pairs), native accepted/rejected ranking, first-module feasibility, collateral geometry, isolation, copied source hashes and post-run reads. Not a rejection of H122 or proof that packaging questions were the sole blocker. No KEEP, no PR. Ready for independent review of this admission receipt only, not for adopting the paragraph. Reopening the experiment requires the bank owner to bind and admit the independent source set, and to verify builder isolation before the first pair.
