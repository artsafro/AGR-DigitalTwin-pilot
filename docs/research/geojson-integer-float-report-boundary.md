# GeoJSON: integer coordinates that pass `read_json` and raise in `_decimals`

Pinned source revision: `4c863c1a4616f1812595536d0507f53034e9acfe` (card SHA; every created report's `code_commit` field was this value).
Interpreter: CPython 3.14.7 (`main, Aug 7 2026, 02:26:22) [MSC v.1944 64 bit (AMD64)]`, `uv run python`.
`sys.get_int_max_str_digits()` was 4300 before and after. `sys.getrecursionlimit()` was 1000 before and after. Neither limit was changed.
Fixtures are synthetic. Probe: `C:/x/t_96e75870/probe.py`. Raw rows: `C:/x/t_96e75870/results.json`. ZIP follow-up: `C:/x/t_96e75870/followup_zip.py`, `C:/x/t_96e75870/followup_zip.json`. CLI stdout/stderr: `C:/x/t_96e75870/cli/`.

## Summary

A JSON integer coordinate of 310 digits (`1` and 309 zeros) or 401 digits (`1` and 400 zeros), positive or negative, passes `read_json` as `int` and `_number` as `True`, then raises `OverflowError: int too large to convert to float` at `src/twinqa/geojson.py:33` inside `_decimals`. `geojson_findings`, `validate()`, and the real CLI create no report. CLI stdout is empty, stderr is that traceback, and the process return code is 1. The same 310-digit member in a VPM ZIP raises at `tools/qa/validate_package.py:122` with no report.

The ordinary integer `12345`, the integers `1` followed by 307 zeros (308 digits) and by 308 zeros (309 digits), and the exponent token `1e400` do not raise. On a single `.geojson` each of those returns a report with V011 `pass`, `passed` false, and `exit_code` 2.

The same 401-digit integer placed only in `developer`, with three-decimal coordinates, parses as a 401-digit `int` and the coordinate check returns `3, 3`. The report is created with V011 `pass`.

Literal `Infinity` raises `ValueError: Nonfinite value: Infinity` at `src/twinqa/io.py:35`, and the report contains one `JSON` fail. Boolean `true` produces a `coordinates` fail and a report. Twelve Ground files with the same bytes as the matching OKS row matched those outcomes. All 27 rows were run twice and matched; fixture sha256 was unchanged after every CLI call. Largest fixture was 1857 bytes.

## Findings

Evidence: **Verified-by-run** = this probe on the pinned tree. **Source** = the file as read, not a second execution. The earlier `1e400` schema-pass measurement is in `docs/research/geojson-overflow-caller-exposure.md` (SHA `8d5c8987`); this run measured `1e400` again on `4c863c1a`.

### 1. Parser integer path and the 4300-digit limit (Verified-by-run; scanner source)

`read_json` (`src/twinqa/io.py:38-42`) calls `json.loads` with `object_pairs_hook` and `parse_constant` only. CPython 3.14 `json/scanner.py:48-54` sends a number token with a fraction or an exponent to `parse_float`, and an integer-only token to `parse_int` (default `int`). `scanner.py:56-61` sends the literals `NaN`, `Infinity`, and `-Infinity` to `parse_constant`.

Measured types on the coordinate that carried the injected token:

| token | `read_json` type | decimal digits |
|---|---|---|
| `12345` | `int` | 5 |
| `12345.678` and `6789.012` | `float` | — |
| `true` | `bool` | — |
| `Infinity` | `ValueError` | — |
| `1e400` | `float` | — |
| `1` + 307 zeros | `int` | 308 |
| `1` + 308 zeros | `int` | 309 |
| `1` + 309 zeros | `int` | 310 |
| `1` + 400 zeros | `int` | 401 |

Digit counts are `len(str(abs(parsed)))` for `type(value) is int`. The harness did not call `float` or `math.isfinite` on a parsed int before `_decimals`. 401 is below the active 4300-digit limit, and `read_json` returned the int. The limit was not what raised.

### 2. Where `_decimals` raises (Verified-by-run; source)

`_number` (`src/twinqa/geojson.py:28-29`) is `isinstance(value, numbers.Real) and not isinstance(value, bool)`. It returned `True` for every parsed int and for the `1e400` float, and `False` for `true`. It raised on no row.

`_decimals` (`src/twinqa/geojson.py:32-34`) is `repr(float(value))`, then a decimal-length count that returns 0 when the repr has no `.` or contains `e`. `geojson_findings` calls it only after both coordinates pass `_number` (`src/twinqa/geojson.py:111-114`).

| token on a coordinate | `_decimals` on that coordinate | `geojson_findings` |
|---|---|---|
| `12345` | `0` | `imageBase64` pass, `Glasses` pass, `schema` pass |
| `12345.678` / `6789.012` | `3` / `3` | same three pass findings |
| `1e400` | `0` | same three pass findings |
| `1` + 307 zeros, either sign | `0` | same three pass findings |
| `1` + 308 zeros, either sign | `0` | same three pass findings |
| `1` + 309 zeros, either sign | `OverflowError` | exception, no finding list |
| `1` + 400 zeros, either sign, on x or on y | `OverflowError` | exception, no finding list |
| `true` | harness call returned `0`; production did not call `_decimals` because `_number` was `False` | `coordinates` fail, `imageBase64` pass, `Glasses` pass |
| `Infinity` | not called | `JSON` fail |

Exception class and message, same on x, on y, and for both signs: `OverflowError: int too large to convert to float`.

Frames, single-file CLI (`C:/x/t_96e75870/cli/x_pos_z309_r1.stderr`, 1486 bytes, stdout 0 bytes):

- `tools/qa/validate_package.py:336`
- `tools/qa/validate_package.py:328` (`main` calls `validate`)
- `tools/qa/validate_package.py:229` (`geojson_findings` for a `.geojson` file)
- `src/twinqa/geojson.py:113` (`any(_decimals(c) ...)` and the generator expression)
- `src/twinqa/geojson.py:33` (`text = repr(float(value))`)

`validate()` does not catch that exception (`tools/qa/validate_package.py:228-242` reaches `report()` only after the branch returns). `main` (`tools/qa/validate_package.py:301-332`) does not catch it either. Process return code 1 here is the uncaught exception. There is no report, so there is no V011 status, no `passed`, and no report `exit_code` on these rows.

`Infinity` frames end at `json/decoder.py:345`, `json/decoder.py:361`, `src/twinqa/io.py:35` (`raise ValueError` in `_reject_constant`). `geojson_findings` catches `ValueError` (`src/twinqa/geojson.py:92-93`) and returns the `JSON` fail. A report is created.

Integers between `1`+308 zeros and `1`+309 zeros were not in the frozen corpus and were not measured.

### 3. Report fields on rows that returned a report (Verified-by-run)

Single `.geojson`, `--profile vpm --json`. V011 status, `passed`, and `exit_code` are the fields in the JSON report. stderr was empty on every row that printed JSON. Two runs matched. sha256 before and after the CLI matched.

| case | bytes | sha256 | V011 | `passed` | report `exit_code` | CLI rc | stdout bytes |
|---|---:|---|---|---|---:|---:|---:|
| `ctrl_12345` | 1460 | `8c5a20e10658d8294f252d72380cd889f7678fba5ca79164e0d41db883af2d6e` | pass | false | 2 | 2 | 7473 |
| `ctrl_3dec` | 1464 | `1f90d1e28dda9bf6f79abb83b55dc70a27ac10c132f5480a556f6a03a407f7bf` | pass | false | 2 | 2 | 7472 |
| `ctrl_1e400` | 1460 | `332511e1db9ed51e7c31037ae30259768282c1351b34e73104c4935f3da81f5f` | pass | false | 2 | 2 | 7473 |
| `x_pos_z307` | 1763 | `bb98b7384746bf24f4587717909a7fcc158ede3b5ce342da8c632a652a1dc6c6` | pass | false | 2 | 2 | 7473 |
| `x_neg_z307` | 1764 | `fc3c3a650547e22834cc39a000129b38d728de93d101f9ba78df539c4508e685` | pass | false | 2 | 2 | 7473 |
| `x_pos_z308` | 1764 | `fabb85b9f76504f8e73787b9f19d5ab6e49b9c27dc5d7bb2c3664592ad7c1057` | pass | false | 2 | 2 | 7473 |
| `x_neg_z308` | 1765 | `4aaff9081ee6de17e66e3543b7bd37a56664c263bc88498d05f119048fb99872` | pass | false | 2 | 2 | 7473 |
| `developer_z400` | 1854 | `8e500b96f543c44a81b92185e0d3b3392046201f2cbec1715ed2cb8a310e1d43` | pass | false | 2 | 2 | 7477 |
| `ctrl_true` | 1459 | `5574f888c31a280c0c1ef4c28dbb9198b7bdb2dba184c0ec5ac572ab05a4804d` | fail | false | 1 | 1 | 7374 |
| `ctrl_infinity` | 1463 | `3d156c3b34140aa8a379d572c034efe2cb310d4c0ec209d367aef87f02dd702d` | fail | false | 1 | 1 | 6577 |

Rows with no report (stdout 0, stderr 1486, CLI rc 1, two runs equal, hash unchanged):

| case | bytes | sha256 |
|---|---:|---|
| `x_pos_z309` | 1765 | `f779325f435fd2bd7f5944b32a607eb5a66b7dcacc05e7d99254155ea434dfc9` |
| `x_neg_z309` | 1766 | `c78a708db696e31c4e1f8dd9961d960ebad4153c9a898ac0869074a4bb5b48cc` |
| `x_pos_z400` | 1856 | `a7b2923a37650200a3d73716b934030bbbf6fa6634d185c0d2cbbb886d098104` |
| `x_neg_z400` | 1857 | `29dd9c27ce1b41ec51b06a6ba80d7f3f23b8202b5ac87c8979330f80ec2e5285` |
| `y_pos_z400` | 1857 | `b4c71597415fec7505612fad8c2dfed1f0d0cd82b560a659a126b6cc181f0243` |

`y_pos_z400` keeps x at `12345.678`. The harness `_decimals` pair was `3` then `OverflowError`. The production `any()` raises on y.

`report.passed` (`src/twinqa/report.py:226-228`) is true only when every blocking stage status is `pass`. `exit_code` (`src/twinqa/report.py:231-236`) is 0 when `passed` is true, 1 when any finding is `fail`, and 2 otherwise. On a single GeoJSON the other blocking stages have no findings and stay `not_run` (`tools/qa/validate_package.py:228-230` adds only V011, note "single GeoJSON: only V011 applies"). A V011 `pass` with report `exit_code` 2 is the single-file report shape. `docs/domain/areas/package.md:11` records that no delivery package has ever been passed.

`developer_z400` puts the 401-digit integer only in `developer` (App.3 property, no coordinate check). `read_json` type of `developer` was `int`, 401 digits. `_decimals` on the coordinates returned `3, 3`. V011 `pass`. The float conversion ran on the coordinates, which are the three-decimal baseline.

The JPEG was a generated 256×256 RGB JPEG, quality 30, 667 bytes, base64 length 892. Rows that reached `_image` recorded `imageBase64` pass. `act_AGR` was the nonempty string `synthetic-act` on OKS and Ground. `FNO_code` was `123456`.

### 4. Ground files (Verified-by-run)

Each Ground file is the OKS bytes under a stem ending in `_Ground`, so `validate()` passes `ground=True` (`tools/qa/validate_package.py:229`). sha256 matched the OKS row of the same token, including `gnd_x_neg_z400` = `x_neg_z400` and `gnd_y_pos_z400` = `y_pos_z400`. In-process results and report fields matched. CLI stdout was 11 bytes longer (path text). Two runs equal. Names: `gnd_ctrl_3dec`, `gnd_ctrl_12345`, `gnd_ctrl_true`, `gnd_ctrl_infinity`, `gnd_ctrl_1e400`, `gnd_x_pos_z307`, `gnd_x_pos_z308`, `gnd_x_pos_z309`, `gnd_x_pos_z400`, `gnd_x_neg_z400`, `gnd_y_pos_z400`, `gnd_developer_z400`.

The coordinate branch (`src/twinqa/geojson.py:107-114`) does not read the `ground` flag. The `ground` flag selects the nullable property set at line 124. These documents have nonempty `act_AGR`, so that branch did not add a finding on the rows that returned findings.

### 5. ZIP caller follow-up (Verified-by-run)

One follow-up. Stored ZIP, one member, two runs, hash unchanged. The 3-decimal control member is the `ctrl_3dec` bytes. The witness member is the `x_pos_z309` bytes.

| ZIP | member sha256 | zip bytes | CLI rc | stdout | stderr | report |
|---|---|---:|---:|---:|---:|---|
| `SM_SynthCtrl.zip` | `1f90d1e28dda9bf6f79abb83b55dc70a27ac10c132f5480a556f6a03a407f7bf` | 1602 | 1 | 9993 | 0 | created |
| `SM_SynthZ309.zip` | `f779325f435fd2bd7f5944b32a607eb5a66b7dcacc05e7d99254155ea434dfc9` | 1903 | 1 | 0 | 1800 | none |

Control report fields: V011 `pass` with `imageBase64` pass, `Glasses` pass, `schema` pass; `passed` false; `exit_code` 1. Other stage statuses in that report: V001 `fail` (`main FBX`, `PNG count`), V012 `review` (`archive name`), V008 `not_run`. The ZIP is an incomplete synthetic archive used to reach the GeoJSON call.

Witness frames (`C:/x/t_96e75870/cli/zip_x_pos_z309_r1.stderr`): `validate_package.py:336`, `:328`, `:218`, `:122`, `geojson.py:113`, `geojson.py:33`. Same `OverflowError` message. `validate_vpm_zip` (`tools/qa/validate_package.py:121-122`) does not catch it, so `report()` at line 242 is not called. Both process return codes are 1. The control has a report `exit_code` of 1. The witness has no report.

No second follow-up. No test in `tests/` calls `_decimals` or asserts `int too large to convert to float` (search of `tests/**/*.py`).

## How it applies to this repository

- `src/twinqa/io.py:34-42` — `read_json` rejects the `Infinity` spelling and leaves integer tokens on `parse_int`.
- `src/twinqa/geojson.py:28-29` — `_number` accepts an `int`.
- `src/twinqa/geojson.py:32-34` — `_decimals` converts with `float`.
- `src/twinqa/geojson.py:111-114` — the 3-decimal review runs only when `_decimals` returns.
- `src/twinqa/geojson.py:142-143` — `schema` pass when every finding so far is `pass`.
- `tools/qa/validate_package.py:122` — VPM ZIP V011 call, uncaught.
- `tools/qa/validate_package.py:229` — single-file V011 call, uncaught.
- `tools/qa/validate_package.py:301-332` — CLI has no handler around `validate`.
- `src/twinqa/report.py:226-236` — `passed` and `exit_code` exist only on a constructed report.
- `standards/VPM_STANDARD.yaml:135` — `coordinates.decimal_places: 3`.
- `standards/DELIVERY_VALIDATOR.yaml:85-90` — V011 is `blocking`.
- `docs/domain/areas/package.md:41` — PKG-19, syntax and keys, V011.
- `docs/domain/areas/package.md:46` — PKG-24, 3 decimals in the file; plan position is V013 `not_run` and V017 manual. The sheet states no magnitude limit.
- `docs/domain/areas/package.md:66` and `:11` — V011 covers PKG-19 through PKG-25; no delivery package has been passed.
- `docs/research/capability-roadmap.md` §7.8 — export, package, and validation are L2-partial.
- `docs/research/geojson-overflow-caller-exposure.md` — prior measurement that exponent `1e400` reaches V011 `pass`. Re-measured here on this SHA with the same V011 `pass` and a report.

## Proposed next tasks

1. **Pin the measured integer rows as current-behavior checks.** One test module, synthetic bytes only, the tokens already measured: `12345`, `1`+307 zeros, `1`+308 zeros, and `1e400` return a single-file report with V011 `pass`, `passed` false, and `exit_code` 2; `1`+309 zeros and `1`+400 zeros on x, and `1`+400 zeros on y, raise `OverflowError` at `geojson.py:33` and the CLI writes no JSON; `developer` holding `1`+400 zeros returns V011 `pass`; `Infinity` returns a `JSON` fail report; `true` returns a `coordinates` fail report; a ZIP whose only member is the 310-digit coordinate raises at `validate_package.py:122` and writes no JSON; a ZIP of the three-decimal control returns a report with V011 `pass`. No change to limits, status rules, or conversion. Value: a later edit cannot turn the missing report into a silent pass, or a pass into a finding, without the fixture moving. Effort **S**. `Advances #149`.

2. **Decision sheet for the coordinate integer, with no code change.** One page that places the measured rows next to PKG-24's 3-decimal rule and the uncaught `float` call, and asks which status, if any, a future check should record. The page does not choose a magnitude bound, a coercion, a parser rejection, or fail versus review. Value: the report-loss rows and the V011-pass rows are ready for a decision. Effort **S**. `Advances #149`.

## Open questions for the user

- When a coordinate is a JSON integer and `float` in `_decimals` raises `OverflowError`, should V011 record a finding, and should that finding be `fail` or `review`?
- The measured 308-digit and 309-digit integers, and `12345`, make `_decimals` return `0` and reach `schema` pass. Should that return stay the precision result?
- Should a magnitude bound, a coercion to decimal text, or a parser rejection of large integers be added at `read_json`, or only at the coordinate check? This note does not adopt one.
- Integers strictly between `1` followed by 308 zeros and `1` followed by 309 zeros were not measured. Is that gap worth a separate bounded probe?

## Sources

- **Verified-by-run:** `uv run python C:/x/t_96e75870/probe.py` and `followup_zip.py` on this tree. Interpreter 3.14.7. Limits 4300 and 1000, unchanged. 27 GeoJSON rows × 2, plus 2 ZIP rows × 2. No pytest, no limit change, no production edit.
- **Source, this tree:** `src/twinqa/geojson.py`, `src/twinqa/io.py`, `src/twinqa/report.py`, `tools/qa/validate_package.py`, `standards/VPM_STANDARD.yaml`, `standards/DELIVERY_VALIDATOR.yaml`, `docs/domain/areas/package.md`, `docs/research/capability-roadmap.md` §7.8, `docs/PROJECT_STATE.md`.
- **CPython 3.14.7 on this machine:** `json/scanner.py:48-61`, `json/decoder.py:329-330` and `:345`/`:361` (traceback frames).
- **Prior report, not the measurement above:** `docs/research/geojson-overflow-caller-exposure.md`, `docs/research/geojson-fno-code-type-boundary.md`.
