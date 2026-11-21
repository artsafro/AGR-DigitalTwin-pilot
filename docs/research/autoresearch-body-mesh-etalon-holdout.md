# Body mesh quality — standing #25, R3 on Artem's own G22 etalon (OBSERVE)

## Frozen contract (before measurement)

Continue the #18 held-out harness (`origin/research/autoresearch-standing-18` commit
`789b2c895ae181ad098dbbd912c183a4393d6990`, `holdout.py` SHA-256
`bec61ed41989d5b7b6a6513266c65caa4f692e18a023f9d00c98a4f9d58a0075`) with the unchanged #17 R3 candidate
(local irregular-face neighbours, R3 core SHA-256 `ec35063d3617c9cd000079ce184e75bc799645daf1040bcb13b84561aaa557df`)
on base core `tools/qa/mesh_quality_core.py` SHA-256 `6458a5a1282d31d9212ef195ffcd0f21f27165984b54677c93e1f0b1df7333dd`
(unchanged on `origin/main` `346b9b12`). #18/#24 asked for an accepted control that is independent of every prior
calibration/holdout; the most authoritative accepted geometry is Artem's own G22 NPM etalon. Not duplicated: builder/failure
census (#1736/#1742), skeleton QA (#1739/#1751), stage 2 (#1722), atlas (#1649), KPP1 corners (#1609/#1627), cold runs
(#1315/#1622/#1738/#1748), suite timing (#1615).

**One number:** `max_median_drop` = max over the frozen fixture of median-of-3 (R0 score − R3 score), points.
Threshold **≤ 0.500** (same as #18). Pass = R3 does not falsely penalise the etalon; it is not a keep of code.
**Activation gate (diagnostic, reported per input):** stock `totals.irregular_faces` and R3 `local_irregular_area_share`.
An input with 0 irregular faces is a *non-activating* control: it can show no false penalty but cannot clear the #24 open item
("accepted control that genuinely activates the detector"); the verdict says so explicitly.

**Frozen fixture** (typical bands from #1619, `C:/x/ev_1619`, not full buildings; accepted by definition = Artem's etalon, plus one accepted agent body never used in R0–R6 calibration or holdout):

| key | path | SHA-256 |
|---|---|---|
| G22-etalon-k1 | `r2/etalon_k1.mq.json` | `413515339be03d1aa8eb88d23c487ce81f1605eced51d3b822d2919141acefb1` |
| G22-etalon-k2 | `r4/etalon_k2.mq.json` | `50df5fb7252078a3fc1edc9076b9e0043051f897bb3aa363b2014b404e6f8d0d` |
| G22-etalon-k3 | `r1/etalon_k3.mq.json` | `dc389b008673016871591e1cb42f151379b63aa2ffe271590c52b3009a7d4a13` |
| G22-k3-v006 | `r1/k3_v006.mq.json` | `39d22ea93efd8ff93c9c8542a314b8b2533fc8f5784d2807a7d5d1581a30dab0` |

**Parity proof:** the same run re-scores #18's `G22-k2-v002r1` (`r7/k2_v002r1.mq.json`) and must reproduce its #18 row
(R0 = R3 = 83.693 ×3, local 0.0) exactly; any mismatch = no verdict.

**Replay:** `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-etalon-holdout-harness/replay.py NEW_DIR`
(fetch `origin/research/autoresearch-standing-17` and `-18` first). The script execs the pinned #18 `holdout.py` from git
(hash-checked), swaps only its `INPUTS`, and writes `NEW_DIR/holdout.json` exclusively. Clean checks: input hashes before/after,
pinned-source hashes, #18 witness, repeat identity, parity row. Injected check: a wrong pinned hash must refuse before scoring.
Not measured: native readback/new DCC build, full buildings, rejected held-out pair, KPP1, package parity, any body-core change.

**Budget / stop:** one confirmation run (3 repeats in-process, ≤ 5 min), **zero** new candidates (R3 is already a failed
candidate on 63B v007; this only answers whether the etalon activates the detector and how R3 treats it). Stop at the first
complete receipt or any hash/parity failure. Forbidden: editing inputs/packages/cores/scorers, tolerance changes, deselecting
tests, cropping or re-banding after seeing results, touching other cards' files.

## Round log
