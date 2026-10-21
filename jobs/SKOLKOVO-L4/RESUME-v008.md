# Skolkovo L4 — resume v008c: Gate 1 design proposal

**Production incomplete; `passed=false`, `buildable=false`. No build/export/PR.**

## The prior question is answered

Artem's task comment2026-10-21 12:39 authorizes source-bound topology cleanup
of the five primary mast assemblies: duplicates, internal intersections,
weld/retessellation. Keep supplied FBX position, heights and exterior profile;
no PDF-rescale, no replacement mast, no BODY-J waiver. This supersedes only the
immutable-topology restriction, not the other source/model decisions.

Do not reopen interior/opaque glazing, PDF-vs-FBX authority, VPM appearance-only,
Drive storage, 108-KNS permission or the five-primary cleanup permission.

## Exact proposal requiring the user's Gate 1

Read [GATE1-PROPOSAL-v008.md](GATE1-PROPOSAL-v008.md): the operation/legend/budget
table, source-scope recipes, joint conditions and remaining execution risks.

Canonical PartsList:

```text
G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v008/parts-gate1-proposal-v008c.json
SHA256 f1867120b2c7072405d32440a27382a0be8bb2bf9edc56c9fbc2876eb3ff2302
```

49 parts; 32,961 unique source rows accounted for: 6,955 retained, 7,059
superseded exact-source counterparts, 18 superseded facade-package objects,
18,929 reasoned drops. Every retained source has an explicit appearance binding.
All 6,955 retained diagnostic buffers are available; no source geometry is
borrowed from the delivered VPM. Original source finish names remain recorded.

The proposed allocation is **147,000/150,000**, reserve3,000. This is a design
ceiling, NOT measured geometry. The target10,000 for108 KNS components is NOT
achieved: earlier constant-prism analytical preflights88,708/85,212 remain failed
feasibility evidence. A varying-source-section/profile route is proposed; no
permission to pass a failed count, silhouette or invariant is inferred.

There are291 **candidate-conditioned** joint recipes,240 weld/51 embed, from
17,355 source object bbox candidates at Euclidean0.003m. A bbox hit is not an
actual mating surface. Actual source-surface reconciliation after exterior
face selection rejects/reports false candidates; no artificial bridges. Welding
is joint-local; glass/frame groups stay separate with10mm insertion only where
source seating permits. Five primary mast positions are never moved.
`extra_edges` values are stated DESIGN allocations, not measurements or proved
bounds: refuse/replan if the real required segmentation exceeds them. All
added topology must fit the same per-part ceilings. These conditions are
explicit in the exact proposal and are part of the requested approval.

This is permission to **start that plan**, not approval of a completed model.
There is still no user Gate1 answer on its exact hash.

## Source/legend audit completed in this run

- F.9 lamellae were found by source shape/position against revision p1 / album
  p15/p16, not by a guessed material name.22 thin vertical source panels form
  four columns, outer pair to ground, inner pair fromZ5.7. All original grey
  names remain; proposed finish is the actual F.9/RAL6018 legend. Three
  horizontal top caps are F.10, not F.9. The source-only annotated sheet and
  exact census-row/hash witness are on Drive.
-20x20/25x25 cassette-perimeter profiles are separated from50x100 glazing
  frames and mapped to facade-metal F.10; revised profiles/plinth useRAL7015.
- The previous baseline native census had no geometry buffers for29 retained
  objects. Live Max2024 was reachable; it was **only pinged**. No user scene
  import/reset/mutation and no headless DCC process were started. Instead a
  job-only binary FBX supplement reads strict supported hierarchical XYZ
  transforms and declared UnitScaleFactor30.48 (0.3048m/unit), refuses unknown
  transform/graph cases, pins model/geometry IDs and writes new diagnostic
  buffers.29 objects plus20 independent native bbox/count controls pass49/49,
  max error0.000005308251m. This does not certify normals, UV, slots or topology.
- Source-supplement repair attempt1 failed during JSON serialization:
  `TypeError: Object of type bool is not JSON serializable` (numpy.bool).
  Explicit native `bool` conversion and a **new** output directory succeeded.
  Failed partial directory remains preserved; no original input was deleted.

## Tests and honest gate state

Data regressions, with old data as the failing witness before fixes:

- Primary-cleanup policy: oldv007 **9/11**, exit1 ->v008 **11/11**, exit0.
  Combined final source/legend table also passes11/11.
- Position-specific F.9/F.10 bindings: oldv008 **4/9**, exit1 ->v008b
  **9/9**, exit0. No other arbitrary first-slot bindings were introduced.
- Exact proposal consistency: oldv007 **13/18**, exit1 ->canonicalv008c
  **18/18**, exit0; **12/12** negative witnesses rejected (empty/partial,
  duplicate input, unsupported operation, NaN/inf, no-reserve threshold,
  missing legend/joints, unmapped/wrong-source material and invented approval).

Focused command:

```text
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --extra pdf-review pytest -q -p no:cacheprovider tests/qa/test_topology.py tests/test_album_pdf_reader.py tests/test_album_below_line.py tests/parts/test_fbx_reader.py tests/contracts/test_parts_list.py tests/contracts/test_parts_import_order.py --basetemp=C:/x/t_b205c8e1-resume-v008
```

**338 passed in19.97s.** No production module or new library added.

`jobs/SKOLKOVO-L4/job.yaml` records all eight procedure gates and the intake
path deviation. Actual machine walk:

```text
uv run python -m dt_ai.procedure jobs/SKOLKOVO-L4/job.yaml --root . --output tmp/skolkovo-l4-v008/procedure-walk-v008.json
```

Expected exit1: **passed=false, zero validation errors**, parts/report review;
operations, measured budgets, export/readback, visual and checker missing.
Inputs is the pinned full inventory snapshot, not a claim of source-mesh QA.

No full suite before the first complete review head (rule49); later run through
`suite_slot.py`. CI: not run (billing lock). No kernel invariant, output budget,
clean export readback, board/user visual or final SINTEZ pass is claimed.

## Durable evidence / restore

Directory: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v008/`.
Small committed index: [evidence-v008/index.json](evidence-v008/index.json).

- `gate1-source-plan-v008c.zip`:18,840,411 bytes;
  SHA256`8ea9677d788bdb8b7b8badc98e9fcd0513aaecc527fd4ced7e09543c946872dc`.
- Local CRC + **7,043/7,043 member hashes**, then independent Drive CRC + all
  member hashes. **9/9** published Drive artifacts rehashed.
- `SHA256SUMS.txt` SHA256:
  `045f7a1c0a1dcf4b8e2acd22099f9841172a1b7e8ef78c043a786a548377c231`.
- Original **104/104** input hashes unchanged before/after publication;
  original mast buffers **113/113** rehashed. No new binary/LFS object in git.

The ZIP preserves original worktree-relative paths: all6,955 selected source
buffers, supplements, full source census/facts,30 C5 JSON readings, canonical
PartsList and full source/appearance/contact tables, job-only drivers, probes
and focused-test log. Full raw source FBX/texture inputs stay at their existing
hash-pinned external paths. To resume on another checkout, verify ZIP and its
internal manifest before restoring the versioned `tmp/` diagnostics. Do not
use the stale experimentalv008/v008b PartsLists instead of canonicalv008c.

## Checkout-byte portability self-repair

The first commit93bb452 exposed a real portability failure: a fresh CLI walk
using exact Git blobs rejected three references to two CRLF text files after
Git LF normalization (`GATE1-PROPOSAL-v008.md` and input-integrity JSON).
The working-tree walk alone had missed it. Preserve the RED witness.

Two exact job-local `.gitattributes` entries now use `-text` (as the existing
v004 evidence already does), preserving the hashed bytes across checkouts.
This is **not LFS**, not a global policy change and not a history rewrite.
Fresh immutable-Git-tree CLI witness: three hash errors ->zero, **5/5 evidence
entries verified**; `passed=false` and exit1 remain correct until user Gate1.
Canonical PartsList SHA and the nine-artifact source archive are unchanged.
Existing procedure tests additionally passed **136/136 in72.74s**
(`tests/test_task_to_model.py`, separate focused run; raw stdout/hash in
`evidence-v008/procedure-tests-v008.json`).
Witnesses pin the actual tested source bytes in
`evidence-v008/checkout-portability-{red,green}-v008.json`; the driver and both
records are independently rehashed on Drive in `evidence-v008-portability/`
(**3/3**, index `evidence-v008/portability-index.json`).

## Partial L5 timings (not completed production throughput)

| Measured pre-Gate1 stage | Seconds | Hours |
|---|---:|---:|
| Raw source supplement | 2.4097440 | 0.0006693733 |
| Source scope/contact census | 2.1468063 | 0.0005963351 |
| Canonical proposal generation | 0.3955876 | 0.0001098854 |
| Focused tests | 19.9700000 | 0.0055472222 |
| Packaging/integrity, nested total | 8.0777597 | 0.0022438221 |

Earlier source/album timings remain in v001-v007. Manual interpretation time and
kernel/build/export/visual/final SINTEZ remain **not measured**, not zero. Do not
sum nested or diagnostic timings into a fabricated whole-building L5 baseline.

## Resume after Gate 1

1. Read the actual user answer bound to the exact canonical SHA above; prior
   cleanup/material permissions are not that answer. Changed proposal -> new
   hash and new approval, never silently rewrite the approved plan.
2. Run the proposed source-bound operations with actual before/after invariants,
   real joints and measured per-part budgets. Preserve failed attempts and
   rollback; do not turn a design target or bbox candidate into a certificate.
3. Derive both profiles from one measured master; versioned export, clean
   readback, comparison with delivered model/album/source, board-tool/user
   visual decision on exact hashes, then complete final SINTEZ.
4. One full suite via suite_slot on first complete review head, receipts,
   committed/pushed branch, one PR, dt-reviewer. Acceptance is not complete now.
