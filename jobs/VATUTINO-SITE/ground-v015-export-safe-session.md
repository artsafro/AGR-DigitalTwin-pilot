# Ground v015 — export-safe producer checkpoint

Historical snapshot. Current construction, binding repair, strict `texel_ready` blocker and final test receipts: [texel contract checkpoint](ground-v015-texel-contract-checkpoint.md). The v005 assets below are diagnostic, not delivery evidence for v009.

Snapshot: 2026-10-21. Code: `da412dc5e673f8db9fcea6b28b0571895e30a792`.
**Not delivery acceptance.** Final texture binding, native final-file receipts and review publication remain open.

## Decisions and preserved contracts

- D157 was extended to Ground v015 **NPM and VPM**, quoting Artem's 2026-10-21 “принимаю рекомендации”: residual triangles <=35% of whole-Ground polygons, with per-slot reasons. Raw D129 classifications remain visible; the waiver is not a claim that every residual triangle is intrinsically needed.
- D169 approves only the recorded A–B–C notch. The additional contour remainder was technically removed with the source-bound void in `ground-source-void-v015.json`, not added to the exception.
- xView remains 0.002 m / 0.005 m; relief remains 10 mm; contour remains 2.2 mm. No source assets or exception maxima were overwritten.
- 59 shared-fan risks were not separated or displaced into duplicate vertices.

## Real producer replay

```text
uv run python jobs/VATUTINO-SITE/build_ground_v015.py \
  --adapter-json C:/x/t_d94665f2/paving_ground_inputs_v4.json \
  --source-master C:/x/t_d94665f2/ground_v014/ground_master_vpm.json \
  --d150-reference tmp/d150-original-surface-v001.npz \
  --pair-hints tmp/v015-pair-hints-v004.json \
  --out C:/x/t_eb1c51ca/ground-v015-build-v005
```

| Profile | Quads | Triangles | Whole-Ground triangle share |
|---|---:|---:|---:|
| NPM | 18,976 | 8,512 | 30.9662398137% |
| VPM | 18,305 | 9,854 | 34.9941404169% |

Both final virtual/mixed-diagonal proofs report zero xView combinations, zero under-band samples, zero unaccepted over-band samples, all 24 original D150 sample identities below their frozen maxima, and zero mirrored surface UV variants. Worst relief is **9.9666681276 mm**. Texel ranges: NPM 11.444772–30.175540 px/m; VPM 589.626403–1442.109135 px/m. The complete histories and raw per-slot D129 results are in `report.json`; these are not native-file receipts.

The reference corner 17852 (current vertex 17912) has a bounded float32 construction pin: Y -15379.661353 -> -15379.661358947753 m, delta -5.94775338 micrometres. The pre-existing 12 upper vertices also receive -20 micrometres Z. This repairs a measured ray-boundary instability without adding accepted samples or increasing frozen maxima. The producer rechecks the original sample table after the correction and all virtual fan combinations after pairing.

Pair hints contain only geometry-bound exclusions, not cached acceptance. The producer always repeats all safety checks and rejects changed inputs/code/HEAD before publication, existing outputs, input aliases/hardlinks and unmapped materials. Optional seven-edge matching augmentation makes no maximum-cardinality claim; exhaustive four-node graph controls cover its cardinality and source-pair exclusions.

## DCC staging and current obstruction

`C:/x/t_eb1c51ca/ground-v015-dcc-v002/` contains fresh NPM/VPM FBX, VPM with 725 UCX objects, independent Blender readbacks and a 100,000-sample UCX audit. Build/readback/audit commands exited 0; `commands.json` records each exact command.

Shared texture binding is **not complete**:
1. The #340 CLI's output is pinned to its immutable v014 `v001` directory. A task-local module configuration selected this card's isolated `textured` directory without changing any alias, snapshot, density or readback guard; the prior delivery was not touched.
2. The configured attempt correctly refused the new quad mesh: `non-triangle face`, `tools/materials/bind_ground_textures_blender.py:103`. The next in-scope repair is a TDD quad-aware fingerprint/area implementation; do not triangulate the delivered mesh to work around the check.
3. A validated binding **plan**, not a bound model, is available as `tmp/v015-texture-plan-v001.json`.

Max PID 145840 was read-only rechecked: Max 2024, metres, untitled, 40 objects, dirty=true. This session has not modified that scene. Earlier six native diagnostic 0/0 receipts belong to earlier geometry and are **not final v005 acceptance**. Prepared `tmp/make-native-v015-final-v001.py` has not been executed and needs completed texture binding first.

## Tests and continuation

Tests-first receipts: under-band identity tests RED 6 -> combined GREEN 52; bounded matching RED 3 -> combined GREEN 83; producer spacing/pin RED 2 -> GREEN 21; mirrored-UV regression RED 1 -> combined GREEN 22. Earlier focused whole-Ground run: 449 passed before the additional spacing/matching/UV regressions.

Full non-DCC suite is in progress on the frozen code head through `suite_slot.py`, log `tmp/full-suite-v015-v001.log`, exit receipt `tmp/full-suite-v015-v001.exit`. Its basetemp is the isolated `C:/x/t_eb1c51ca/pytest-full-v001` child: using the card's occupied parent would delete real inputs/evidence. Process-local TMP/TEMP use another isolated child. **Do not alter source/tests or start another suite until the existing run has finished and its task-owned children have been checked.** Do not treat the archived partial suite log as a green result.

Regression evals genuinely returned 0 passed / 0 failed / 10 not measured, exit 2: no Claude transcript/PR evidence. The eventual PR receipt must be checked with `dt evals --check-receipt`; it is not yet a review-ready receipt.

Remaining acceptance: quad-aware map binding; final native saved-Max and FBX readbacks including fixed IDs/maps; final geometry/placement/package checks; review scene plus pending.json; complete full-suite receipt; hostile self-review, author receipts and one PR. PR has not been opened.

## Durable evidence

- Archive: `G:/Мой диск/AGR-evidence/371-ground-v015-producer-20261021/checkpoint-v001.zip`
- SHA256: `0fa391cc4d184840e27cc0ba3bc2c04d312e1a9e05c1778f88460723fcd0d4b4`
- 11,343,482 bytes; CRC plus every one of 70 member hashes read back and verified.
- Contains v005 masters/report, raw DCC staging/readbacks/audit, source-bound reference NPZ, pair hints and reproduction scripts/logs. The suite log inside it is an interim snapshot, not completion evidence.
- Adjacent `SHA256SUMS.txt` preserves the archive hash. No binary was added to Git.
