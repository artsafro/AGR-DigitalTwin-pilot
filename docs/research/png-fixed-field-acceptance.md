# PNG fixed-field errors — post-review Acceptance table

PR: [#402](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/402).

**This table was added after implementation, in response to changes_requested.**
It is a retrospective mapping of the card to existing tests, not evidence that an
Acceptance table existed before code. No uncovered row was found; no parser or test
changes are needed for this review request.

All fixtures are synthetic and generated in memory. `test_frozen_synthetic_rgb`
pins the original 69-byte RGB PNG, including its SHA-256. Profiles are loaded by
`load_profiles()`; parser verdicts are not mocked. Test links below target
[tests/qa/test_png_fixed_field_errors.py](../../tests/qa/test_png_fixed_field_errors.py).

## Acceptance

| Card input | Expected verdict / unchanged behavior | Existing test (parameter coverage) |
|---|---|---|
| Frozen RGB prefixes 16..32 inclusive | Direct parser raises diagnostic `ValueError` identifying truncation; real-profile NPM and each VPM role (Diffuse, ERM, Normal) return one per-file `fail`, `PNG readable`, naming the input, instead of raising; no VPM facts retained | [`test_truncated_fixed_fields`](../../tests/qa/test_png_fixed_field_errors.py) (`n=16..32`, all five routes): 85/85 |
| Frozen RGB prefixes 41..56 inclusive | Same diagnostic `ValueError` and per-file NPM / all VPM-role failures as above | [`test_truncated_fixed_fields`](../../tests/qa/test_png_fixed_field_errors.py) (`n=41..56`, all five routes): 80/80 |
| Existing IDAT CRC corrupted by one bit | Direct parser retains `CRC error in IDAT chunk` `ValueError`; NPM and all VPM roles retain the corresponding `PNG readable` failure | [`test_existing_idat_crc_failure`](../../tests/qa/test_png_fixed_field_errors.py): 5/5 |
| Original valid RGB, RGBA and palette+tRNS controls | Identical complete `PngFacts` and alpha facts; exact existing NPM and Diffuse/ERM/Normal finding sequences and VPM sets. The 1x1 Normal heuristic remains review, not pass | [`test_valid_facts_and_wrapper_policy_unchanged`](../../tests/qa/test_png_fixed_field_errors.py): 3/3 controls, each checks all wrappers |
| Prefix 57: RGB with no IEND | Unchanged `PngFacts(1,1,8,2,False,57)` (with input name); existing NPM atlas-size and VPM Diffuse map-size/map-set failures. Facts are explicitly **not integrity approval** | [`test_existing_structural_acceptance_is_not_integrity_approval`](../../tests/qa/test_png_fixed_field_errors.py) (`n=57`): 1/1 |
| Empty and short prefixes 0..15 | Direct `ValueError("not a PNG")`; NPM and all VPM roles return per-file `PNG readable` failure | [`test_empty_and_short_signature_remain_rejected`](../../tests/qa/test_png_fixed_field_errors.py): 80/80 |
| Retained structural controls: prefixes 33..40 and 58..69 | Facts and existing NPM/VPM Diffuse outcomes remain unchanged, including missing IDAT/IEND, short trailing headers and incomplete IEND/CRC. No new structural-integrity requirement | [`test_existing_structural_acceptance_is_not_integrity_approval`](../../tests/qa/test_png_fixed_field_errors.py): 20/20 additional cases (21/21 including prefix 57) |
| Outer NPM validation of one prefix-25 PNG in `tmp_path` | Report returned; V006 has one input-naming `fail`, `PNG readable`, with truncation diagnostic; `passed=False`; `json.dumps(..., allow_nan=False)` succeeds; original file bytes preserved | [`test_outer_validate_returns_strict_json_and_preserves_input`](../../tests/qa/test_png_fixed_field_errors.py) (`npm-V006`): 1/1 |
| Outer VPM validation of `SM_Probe.zip`: validly named prefix-25 Diffuse plus clean generated 256px ERM/Normal | Report returned; V007 has one input-naming `fail`, `PNG readable`, with truncation diagnostic; `passed=False`; strict JSON serialization succeeds; ZIP bytes and every member preserved. Missing package components may fail normally | [`test_outer_validate_returns_strict_json_and_preserves_input`](../../tests/qa/test_png_fixed_field_errors.py) (`vpm-V007`): 1/1 |
| Original input bytes across error and control routes | No input mutation: rejection helper compares bytes; valid and structural controls compare original bytes; outer tests compare file bytes and ZIP members | Same tests above: 276/276 parameterized cases assert preservation; frozen fixture identity: [`test_frozen_synthetic_rgb`](../../tests/qa/test_png_fixed_field_errors.py), 1/1 |

## Evidence and limits

- Historical RED supplied with this continuation: **167 failed, 159 passed** on
  unchanged pre-fix code. This review pass did not recreate or rerun historical RED.
- Historical GREEN: **326 passed**. Post-review focused rerun: **326 passed in 0.64s**.
- Focused command (only the three requested files):

  ```bash
  env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_a04e5734 tests/qa/test_png_fixed_field_errors.py tests/qa/test_validator.py tests/twinqa/test_png_v007_findings.py
  ```

- Full suite was not rerun after review. Its earlier run timed out at approximately
  47%; no final count is available.
- Existing receipt check: exit 0; 10 evals not measured (no Claude transcript).
  No new receipt measurement is claimed here.
- Original report `docs/research/png-truncation-error-boundary.md` was referenced by
  the implementation PR body as living on the origin research branch; it is absent
  from this worktree. This table uses the card's verbatim inputs and existing tests,
  not a newly inspected copy of that report.
- Missing IDAT/IEND requirements, short trailing-header rejection, IEND CRC checks,
  modes and universal decoding remain separate decisions. Pillow exception handling
  is unchanged. No blanket catch or resource-error swallowing was added.
- No standards, profiles, gates, procedures, dependencies, CI, data or DCC changes.
  No output/report/temp path API was introduced. Technical failure reporting is
  **not delivery certification**.
- The PR body update is staged as text in ignored `tmp/pr-body.md` for the driver;
  remote publication was not performed because this run forbids `gh` and owns no
  commit/push operation.
