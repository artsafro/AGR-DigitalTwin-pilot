# Trainer FBX-first transfer — round 112, OBSERVE

## Frozen contract

- Input revision: `7762dcfe2e78219155461bb633faaca2015e259b` (`origin/main` at intake). Trainer, bank, ledger, validator and route all come from that Git tree. Candidate text is `CANDIDATE` from `aee3296dcdf5daba3943a4bf9cbb0fd5dd485c20:docs/research/trainer-artifact-first-r95/make_bank.py` (#1917). Only its location differs: append it as a visible practice-only preface to `docs/agents/SKELETONS.md` in the disposable A/B overlay rather than modifying each etalon task. Baseline overlay is empty. One candidate, no retuning or new candidate after inspecting the holdout.
- First scored failure in the bank ledger is `artifact` (3/4; one `sources-dwg`). The sealed #111 follow-up is separate: 7/8 scored first fail at artifact and one additional attempt was unscored. No atlas or form work; no duplicate of the G22 adapter (#1928), A/B mechanism (#1924/#1927), DWG lane (#1866), bank responsibilities (#1861), or the KPP1/G22 comparison (#1917).
- Holdout: `63b-stage1`, not used to choose #95 wording (KPP1/G22). `63a-stage1` is a practice-ready admission control, not a substitute holdout; #111 showed accepted-lineage reads on 63A. Do not change task scope, bank, readiness, production rules, output tolerances, scoring, or artifacts. No Max, no access to accepted lineage by either agent; do not start agents if an explicitly isolated eligible holdout is unavailable. The selected fixture is never swapped after preflight.
- Metric M112: binary escape-free `artifact` pass per arm on 63B, using unmodified trainer scoring on fresh sources-only builds; compare median of 3 paired runs (range of paired deltas too). Confirm only if candidate passes in >=2/3, baseline <=1/3, and no measured scorer-pass stage regresses in a pair. Refute if all three pairs are admissible but the threshold is missed. Escape, unscored, missing provenance, fewer than three admissible pairs or preflight refusal => inconclusive, never a scored zero. Record elapsed time separately. Accepted/rejected key calibration is not passage and must be rerun blind to tuning before a claim of confirmation; historical 63B form is not usable as calibrated passage.
- Budget: 1 read-only admission series (63B clean, 63A clean, 63A identical-overlay and hidden-path perturbations). Then one fresh pair to estimate the remaining series; at most two further fresh pairs, no alternative candidate. Per-arm timeout 600 s. Stop at first failed admission, lack of isolation, or if the remaining pairs do not fit within card time; do not launch a shortened series and call it conclusive.
- Admission witness: candidate changes exactly `docs/agents/SKELETONS.md` and the ready control must admit it (`rc=0`, one edit); identical versus empty must refuse (`rc=2`); one extra file under `docs/trainer` must refuse (`rc=2`). None writes an A/B output dir. Control is exercised for overlay admission only; accepted/rejected FBX quality, agent adoption and isolation are **not measured** by these probes. If permission allows subsequent live runs, the native trigger is an explicit H95 instruction in the candidate tree and absent in baseline, with the baseline `artifact` failure expected on >=2/3. Audit exact input/overlay hashes, equal scorer/head/lane, run exits and command events before adopting any delta. Do not publish a passing grade for a build obtained from accepted evidence.

## Replay

From this worktree at the recorded executable revision, use the pinned existing A/B CLI. Build variants from Git blobs (not working-tree newline representations) with the command in the round log. Recompute and compare manifest SHA-256 before reuse. Then run `uv run --locked agr trainer ab 63b-stage1 --ab .r112/old .r112/new --scope INVARIANT --out .r112/pair-1 --lane codex --timeout-s 600 --dry-run`. If admission and source-only isolation are independently established by the bank/runtime owners, replay with the documented approved bank diff, preflight hashes for all source/key/calibration inputs, and drop `--dry-run` for each fresh `pair-1..3`. If executable `origin/main` has moved, do not silently run the comparison on it. A failed dry-run never exercises the metric.

## Round log

**Hypothesis: inconclusive.** No agent runs and no native scorer runs. The unchanged bank has `split: held_out`, `status: complete`, and `practice_ready: false` on 63B; `complete` does not permit practice on that row. The bank says practice was not scheduled in v0. The command refuses *before* it checks the overlay or mounts/reads source data. A rehearsal on 63A would not validate transfer to 63B; the ready control is only for the overlay. The trainer's dry-run no-write result is not a filesystem isolation test.

| Fixture and input | Observed | Change exercised | A/B output created |
| --- | --- | --- | --- |
| Held-out 63B, 0 vs 1 file | rc 2: `63b-stage1 is not practice_ready` | Overlay not exercised | No |
| Ready 63A, 0 vs 1 file | rc 0: exactly `docs/agents/SKELETONS.md`, no scope warnings | 1 candidate file seen | No |
| Ready 63A, empty vs same directory | rc 2: `--ab OLD and NEW are the same folder` | Alias check only; not the identical-content witness | No |
| Ready 63A, two distinct empty directories | rc 2: `variants are identical: nothing to probe` | 0 file differences, intentionally | No |
| Ready 63A, 0 vs 2 files | rc 2: `docs/trainer/r112-synthetic.txt` is under hidden `docs/trainer` | 1 injected file relative to the candidate | No |

Initial admission batch: 2.558 s wall. The same-directory command tested the wrong guard for the identical-content witness; the corrected, distinct-directory command took 0.536 s. Status: stopped at admission. **Not measured:** source/key byte readback, clean or rejected native fixtures, agent adoption, artifact pass, paired median/spread, geometry, and calibration. The production bank and trainer remain unchanged; no KEEP, no PR. Review readiness is for this receipt, not the candidate.

Input bindings (SHA-256 of Git-LF bytes or generated raw bytes):

| Input | SHA-256 |
| --- | --- |
| `7762dcfe:docs/trainer/ledger.json` | `230eace1a0a434cb25091f449760d3895d5b7d169086a2f2ba049db88a8496a7` |
| `7762dcfe:docs/trainer/etalons.json` | `016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635` |
| `7762dcfe:docs/agents/SKELETONS.md` | `eb7c3b486d0433c1f0df403068c97c9aa2de17677e557d1a7a45f2017b0d5692` |
| `aee3296d:docs/research/trainer-artifact-first-r95/make_bank.py` | `f1e39bc8e6d29f8625b18ff39e230bab9050a1155eba413747725db0deec1188` |
| `09bd5aeed0acd0188fe8e8291489e23776fc1308:docs/research/trainer_ledger_fresh_r111/receipt.json` | `0fd60f444de5b9b7b2527af11618e6b7626f9eb0732ea8e1207b895b7b2c7276` |
| `new` and `hidden` variant `docs/agents/SKELETONS.md` | `58f44bcfca191e317f2fe63fcc83b469bf90bce561fdffbd3184064babdeef52` |
| `hidden` variant `docs/trainer/r112-synthetic.txt` | `03bea87ebb0381533c2fdaa1fdd6d149e6b6149e732c8c032a377b078145e2f0` |

Replay commands for the admission series, in Bash from the receipt branch with the pinned trainer and bank. The fixture is Git-bound; no private scratch or Drive bytes are needed for these probes. Live replay is not eligible on this bank.

```bash
mkdir -p .r112/{old,empty,new/docs/agents,hidden/docs/agents,hidden/docs/trainer}
python -c 'import ast,pathlib,subprocess; get=lambda ref:subprocess.check_output(["git","show",ref]); base=get("7762dcfe2e78219155461bb633faaca2015e259b:docs/agents/SKELETONS.md"); r95=ast.parse(get("aee3296dcdf5daba3943a4bf9cbb0fd5dd485c20:docs/research/trainer-artifact-first-r95/make_bank.py")); text=next(ast.literal_eval(n.value) for n in r95.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="CANDIDATE" for t in n.targets)); title,tail=base.split(b"\n",1); overlay=title+b"\n\n"+text.encode("utf-8")+b"\n"+tail; [pathlib.Path(f".r112/{v}/docs/agents/SKELETONS.md").write_bytes(overlay) for v in ("new","hidden")]; pathlib.Path(".r112/hidden/docs/trainer/r112-synthetic.txt").write_bytes(b"synthetic forbidden overlay path\n")'
sha256sum .r112/{new,hidden}/docs/agents/SKELETONS.md .r112/hidden/docs/trainer/r112-synthetic.txt
ab() { uv run --locked agr trainer ab "$1" --ab .r112/old ".r112/$2" --scope INVARIANT --out ".r112/pair-$3" --lane codex --timeout-s 600 --dry-run; }
ab 63b-stage1 new holdout
ab 63a-stage1 new ready
ab 63a-stage1 old identical
ab 63a-stage1 hidden hidden
ab 63a-stage1 empty identical-distinct
```

Affected tests: `uv run --locked pytest -q tests/tools/test_trainer.py tests/tools/test_trainer_ab.py tests/test_trainer_inspect.py` — 134 passed, 1 basetemp warning.
Full suite: deferred to merge batch (rule 68).

Next: bank/runtime owners identify an untuned, source-only practice-ready fixture and demonstrate accepted-lineage isolation before the three fresh A/B pairs. Do not make 63B ready by overriding the flag in scratch. Keep the multi-FBX selection issue separate from fresh artifact passage (#98/#99).
