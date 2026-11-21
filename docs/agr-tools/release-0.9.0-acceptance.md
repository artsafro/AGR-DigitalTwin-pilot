# AGR Tools 0.9.0 — historical acceptance disposition

Scope: #1506, split from #1018. This is an archival receipts audit, not a rebuild,
re-release, reinstall or new native verification. The historical checks were **not rerun**.

Artem's dated answer, 2026-11-16 «принимаю»: [owner disposition](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1506#issuecomment-6915458337) [D331].
The [initial evidence audit](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1506#issuecomment-6911505408)
records the bounded path search and the original unanswered gates. This disposition supersedes
its pending-owner states only; it does not supply missing historical measurements.

## User acceptance

| Gate | Evidence and owner disposition |
|---|---|
| Max 2026 panel/button smoke | **DEFERRED / NOT MEASURED**. No separate historical receipt was located. Artem schedules a later isolated run in the **night slot**, only when Max is free; this is **not a blocker for closing the receipts audit** [D331]. The future run is not performed or dated by this audit and cannot retroactively prove the old smoke. |
| Installed-bundle backup/restore | **WAIVED / EVIDENCE MISSING**: **waived by Artem 2026-11-16, not available for a past release** [D331]. Before/after installed-bundle SHA256: unavailable. No evidence that install tests never installed the bundle was found either; neither byte-identical restore nor damage is asserted. |
| Russian release notes | **ACCEPTED EXISTING RUSSIAN NOTES** [D331]: [CHANGELOG 0.9.0 (#979)](../../adapters/max/agr_tools/CHANGELOG.md#090-979) and [GUIDE](GUIDE.md) satisfy #1018. GitHub release body remains English; no text-only addendum is requested or published. |

Owner acceptance closes the **receipts audit** with these explicit dispositions, not every
technical/manual gate. The later UI run remains open for the owner to arrange in an isolated
night slot when sessions are free. No Max launch or attach is authorized by this audit;
there is no automatic dispatch, downgrade or permission to interrupt an active session.

## Technical QA

- [Merged release PR #1042](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1042),
  merge `8364b7ca5886fa2364c29016ab5d9b025d7245e3`: Max **2024** panel/macro smoke,
  job `20261106-014746-1119fd30`, 19 macros + 2 panel presses each.
  That is not a separate Max 2026 panel/button smoke receipt.
- [Final polygon receipt](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1042#issuecomment-6672773049):
  Max 2024.2.5 and Max 2026.3 each **780/780**, zero mismatches, known_bug 0,
  commit `3ba9a3fff0d8f2f5af9fca3d5dfe417bbe15aad0`. Max 2026 exit **-130**
  remains recorded (polyunwrapper_autoload); batch comparison is not UI/manual acceptance.
- [Earlier profile receipt](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1042#issuecomment-6672179641):
  58 runner-profile files, initially four polygon mismatches. The final receipt resolves
  those mismatches; it reports 74 profile files restored for Max 2024 and Max 2026 restore
  deferred to the last slot. Neither receipt supplies installed-bundle before/after hashes.
- Missing install manifest pointer: `C:/x/release-agr-tools/user-install`, originally for
  `%APPDATA%/Autodesk/ApplicationPlugins`. The initial audit found neither that directory nor
  `C:/x/team-audit/polygon2026/20261106-005546/` or
  `C:/x/team-audit/polygon2024/20261106-005547/`. These are historical pointers, not verified
  current artifacts. No original installed-bundle SHA256 values are available to cite.
- Interactive Undo and light-theme checks remain separate unmeasured known limits.
  Current-main follow-up #1504 is not historical 0.9.0 acceptance.

## Publication

[agr-tools-v0.9.0](https://github.com/artsafro/AGR-DigitalTwin-pilot/releases/tag/agr-tools-v0.9.0)
was published `2026-11-06T00:19:53Z`. GitHub release-asset API digests rechecked in this audit:

| Asset | Published SHA256 |
|---|---|
| `AGR-Tools-0.9.0.bundle.zip` | `7cdf77f09695916ed92d098c6ee458664d61ccdc0b58cb3825b0ae5f79dbbf3e` |
| `AGR-Tools-0.9.0.mzp` | `33c67eb8ffe7102a9746c5dc355166cbad154a0aabd0351e7937b030385eeb4f` |

These are API-provided published digests, not fresh downloaded-archive byte verification
and not installed-bundle restore hashes. Both assets, release body and known-limits section
are unchanged by this audit. Delivered archives, customer scenes, installed bundles and user
profiles are outside the write scope. Publication is not proof of technical QA or user acceptance.

## Audit verification

`tests/test_agr_tools_090_acceptance_1506.py` checks this documentation contract and rejects
missing receipt tokens and promotion of the two unmeasured historical gates to a pass.
It does not execute Max, verify plugin functionality or establish install/restore integrity.
