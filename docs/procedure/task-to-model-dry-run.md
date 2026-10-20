# Task-to-model dry-run gate report (#351)

Read-only inventories: no DCC, model export, human approval or SINTEZ run is performed.
Both CLI walks returned **exit 1**, `passed=false`, intentionally. Existing file evidence
is not equivalent to a completed gate. The checker is final per D104.

Implementation base: `a3e091b` (origin/main merged without rebase).

## Reproduce

```bash
uv run python -m dt_ai.procedure jobs/KERNEL-SYNTHETIC/job.yaml --root . --output tmp/kernel-walk-v002.json
uv run python -m dt_ai.procedure jobs/VATUTINO-SITE/job.yaml --root . --output tmp/vatutino-walk-v002.json
```

Use new output paths on repeats; the validator refuses overwrites.

## Observed inventories

### Synthetic kernel tests

| Gate | Status | Verified evidence files | Ready | Gap / interpretation |
|---|---|---|---|---|
| inputs | pass | `tests/ops/test_invariants.py`<br>`tests/ops/test_operations.py`<br>`tests/contracts/test_parts_list.py` | true | Synthetic test source inventory |
| parts | review | `tests/contracts/test_parts_list.py` | false | PartsList contract tests exist; no confirmed job-specific parts.json |
| operations | review | `src/dt_ai/ops/invariants.py`<br>`src/dt_ai/ops/operations.py`<br>`jobs/KERNEL-SYNTHETIC/evidence.md` | false | 220 kernel/parts tests passed; not a per-export before/after receipt |
| budgets | missing | none | false | No job-specific execution evidence available |
| export_readback | missing | none | false | No job-specific execution evidence available |
| report | pass | `jobs/KERNEL-SYNTHETIC/evidence.md` | false | Synthetic capability evidence and unmeasured delivery gates recorded |
| visual | missing | none | false | No job-specific execution evidence available |
| checker | missing | none | false | No job-specific execution evidence available |

### Vatutino site repository artifacts

| Gate | Status | Verified evidence files | Ready | Gap / interpretation |
|---|---|---|---|---|
| inputs | review | `jobs/VATUTINO-SITE/ground-parts.json`<br>`jobs/VATUTINO-SITE/ground-build-v014.md`<br>`jobs/VATUTINO-SITE/maf/site-maf-set.json` | false | Repository artifacts recorded; original DWG/album and external exports are not in this checkout |
| parts | review | `jobs/VATUTINO-SITE/ground-parts.json`<br>`jobs/VATUTINO-SITE/maf/source-dimension-gate.md` | false | Ground decomposition and MAF mapping exist; ground-parts.json is not PartsList.schema.json |
| operations | review | `jobs/VATUTINO-SITE/build_ground.py`<br>`jobs/VATUTINO-SITE/ground-build-v014.md` | false | Builder and geometry evidence exist; no kernel before/after receipt for full site |
| budgets | review | `jobs/VATUTINO-SITE/ground-build-v014.md` | false | Ground counts/density documented; no measured full-site budget receipt |
| export_readback | review | `jobs/VATUTINO-SITE/ground-build-v014.md` | false | v014 report names FBX hashes/readback on C:/x; external exports and raw receipts not committed |
| report | pass | `docs/deliveries/vatutino-ground-2026-10-20.md` | false | Delivery report explicitly not passed |
| visual | missing | none | false | No user approval through review tool for these exact final site exports |
| checker | missing | `jobs/VATUTINO-SITE/ground-build-v014.md` | false | General validator has review/not_run; no complete SINTEZ acceptance |

## Executed tests and budget

- `tests/ops` + `tests/contracts/test_parts_list.py`: **220 passed**, 165.61 s; synthetic capability evidence only.
- Procedure plus C7 tests: **79 passed**, 27.20 s.
- Final procedure probes including D129 completeness: **59 passed**, 1.76 s. Both quad_dominance and texel_ready are mandatory; unavailable producers leave the gate incomplete.
- C7 `--budget-files AGENTS.md CLAUDE.md docs/domain/areas/groundel-maf.md`: **31284 characters < 40000**, exit 0.
- Actual card context `--budget-files AGENTS.md docs/domain/areas/groundel-maf.md tmp/card.txt`: **37075 characters < 40000**, exit 0. Card text is copied read-only from the board.
- Initial regression at tests-first commit `3d17dc4`: **1 failed** (`Missing task-to-model validator`) before implementation.
- Empty/partial/unsupported, nonfinite and boundary, gate-subset, required-check and alias probes are automated in `tests/test_task_to_model.py`.

## Interpretation and limits

The synthetic walk has test sources and a capability report, but no job-specific Gate 1
approval, operations receipt tied to an export, measured delivery budgets, export readback,
user visual verdict or checker receipt. The positive complete-bundle unit test is explicitly
SYNTHETIC contract data; it is not evidence of real user acceptance or checker execution.

Vatutino has genuine committed decomposition/build/delivery reports. Its source DWG/album,
external FBX files and raw readback reports are not in this reproducible repository inventory.
`ground-parts.json` has another format, not `PartsList.schema.json`. The v014 report already
says not passed: general validator stages include review/not_run, and final site visual
acceptance and complete SINTEZ evidence are absent. This walk preserves those limits.

Visual publication tooling is independently tracked by #348; no unmerged code from that
card is used here. The checklist consumes normalized, hashed review-tool user receipts;
absent publication/verdict evidence leaves the gate missing.
