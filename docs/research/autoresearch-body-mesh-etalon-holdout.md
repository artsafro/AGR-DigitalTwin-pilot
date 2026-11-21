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

**Итог (OBSERVE, ничего не внедрено).** Неизменённый R3 (#17) штрафует собственный эталон Артёма G22: падение балла
к.1 **6,946**, к.2 1,891, к.3 2,010 при пороге 0,500 → `max_median_drop = 6.946`, **R3 окончательно не годится**.
Эталон — первый принятый контроль, на котором детектор реально срабатывает (#24 просил именно такой): косых граней
к.1 7 733 (670,8 м², 2,7 % площади), к.2 1 589, к.3 1 873. **Все** косые грани эталона — треугольники
(`irregular_faces == tris` на всех трёх полосах), все четырёхугольники эталона прямоугольны. Принятый агентский
k3_v006 (вне всех прежних калибровок) — 0 косых граней, падение 0,000. Значит, признак «треугольник / косой угол»
сам по себе не отделяет брак от принятого: у эталона треугольников 9–15 % граней. Любое правило-штраф за треугольники
(R3/R4/R5/R6-подобное) должно сначала пройти этот эталонный контроль.

| input | stock irregular faces (= tris) | R0 | R3 | median drop | spread |
|---|---:|---:|---:|---:|---:|
| G22-etalon-k1 | 7733 | 89.244 | 82.298 | 6.946 | 0 |
| G22-etalon-k2 | 1589 | 86.883 | 84.992 | 1.891 | 0 |
| G22-etalon-k3 | 1873 | 92.182 | 90.172 | 2.010 | 0 |
| G22-k3-v006 (accepted agent) | 0 | 90.275 | 90.275 | 0.000 | 0 |

- **Clean:** pinned #18 `holdout.py`/receipt hashes, #17 R3/R0 core hashes, #18 synthetic witness, input hashes before/after,
  3 identical repeats per input (spread 0), parity row `G22-k2-v002r1` identical to #18 (R0 = R3 = 83.693, local 0.0).
  A second full replay after a typing-only edit of `replay.py` was byte-identical (`r25.json`, `holdout.json`).
- **Injected:** wrong pinned `holdout.py` hash → `ValueError` before any scoring, no output directory created.
- **Not measured:** whether the etalon triangles are native modelling or residue of the `--rejoin-rectangles` diagnostic
  copy (#1634) of the triangulated NPM delivery; native readback, full buildings, KPP1, a rejected held-out pair, any
  body-core change. `holdout.json` keeps #18's inherited `clean_checks`/`not_measured` text verbatim (it is #18's code).
- **Receipt:** `autoresearch-body-mesh-etalon-holdout-harness/r25.json` SHA-256
  `606423c349a9b3a232016654f6df7177fd8ddb6b6b2084f11ca1529b40e4ca18`; `holdout.json`
  `fef11a46545232498446617136e897b8f7d08a4d0c72b07d9271f7afed6cd700`; `replay.py`
  `0920059fa1bc6a6bef92dfc7deb42a58e878d4d51997bb58cc3bbcdcee746963`.
- **Would change:** nothing in code. Add the three etalon bands as a mandatory accepted control (drop ≤ 0.5) to every future
  local-irregular rule; stop the triangle/oblique-face line of R3–R6 unless a rule separates the etalon's triangles from the
  rejected bodies' (e.g. by triangle placement/role, measured first on this fixture).
