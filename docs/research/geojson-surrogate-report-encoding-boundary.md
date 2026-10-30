# GeoJSON lone surrogates and the UTF-8 CLI report

Report-only research, pilot repository. Synthetic corpus. No production code, test, standard, hook, CI or data change. No pytest and no DCC. `passed=false` on every report object this probe constructed. A V011 pass in a single-file run is a helper result, not delivery acceptance.

## Summary

ASCII GeoJSON that contains an escaped lone UTF-16 surrogate can parse and still lose the UTF-8 CLI report, when that surrogate is copied into a V011 diagnostic string. Frozen SHA `4c863c1a4616f1812595536d0507f53034e9acfe`. CPython 3.14.7, Pillow 12.3.0.

`read_json` accepted all six fixtures. For a non-dict Glasses entry whose material key is `\uD800` or `\uDC00`, `geojson_findings` returns `Glasses entry` / `fail` and the observed string contains that code point. `json.dumps(..., ensure_ascii=False)` returns a Python `str` that still contains the surrogate and does not contain the six characters `\uD800` / `\uDC00`. Encoding that string as strict UTF-8 raises `UnicodeEncodeError`. `json_bytes` raises the same class. The real CLI `--profile vpm --json` returns 1, writes 0 stdout bytes, and writes an ASCII traceback on stderr. The in-process report object exists before that encode; the process never reaches `return result.exit_code`.

The same Glasses-entry path with an ASCII key, the Cyrillic key `Стекло`, or the valid pair `\uD800\uDC00` (parsed as one scalar U+10000) emits a complete UTF-8 JSON report. Return code 1 matches the report's own `exit_code`, stderr is empty, and the parsed `observed` code points match the finding. A lone `\uD800` in `developer`, with a valid glasses object, stays out of every finding. That CLI emits JSON, V011 is `pass`, return code 2, and `passed` is false (14 other stages `not_run`).

On this host both the `PYTHONIOENCODING=utf-8:strict` child and the inherited child had stdout `utf-8` / `strict` and stderr `utf-8` / `backslashreplace`. Raw stdout and stderr matched across those policies. Two full runs matched. Successful stdout on this Windows host is UTF-8 with CRLF; after CRLF to LF it equals the in-process dumps text plus a final newline.

## Findings (with sources)

**Verified-by-me** means a measurement in this session. **Static** means a source line read in this session and not executed for that claim. **Claimed** means a fetched document. Repository lines are pinned to `4c863c1a4616f1812595536d0507f53034e9acfe`. The SHA was read from `.git/refs/heads/docs/research-geojson-surrogate-report-encoding-boundary`. This session did not run git or gh. Every constructed report's `code_commit`, and every CLI JSON that parsed, carried the same SHA. `code_commit()` (`src/twinqa/report.py:283-290`) is what invokes `git rev-parse HEAD`.

### Where the surrogate enters the diagnostic

**Static.** `read_json` (`src/twinqa/io.py:38-42`) decodes bytes with strict UTF-8, then `json.loads`. These fixtures are ASCII, so the UTF-8 decode succeeds. The surrogate is the JSON `\u` escape, not a non-UTF-8 byte. `geojson_findings` (`src/twinqa/geojson.py:86-93`) maps `UnicodeDecodeError` and `ValueError` to findings. Neither fired.

**Static.** A one-element list of a non-empty object whose value is not an object hits `Glasses entry` and interpolates the material key into `observed` (`src/twinqa/geojson.py:59-60`): `f"{material}: {props!r}"[:80]`. Single-file validation calls `geojson_findings` without `glass_names` (`tools/qa/validate_package.py:228-230`), so the FBX name cross-check (`src/twinqa/geojson.py:47-58`) is not this path.

**Static.** The CLI reconfigures stdout to UTF-8 and prints `json.dumps(result.to_dict(), ensure_ascii=False, indent=2)` (`tools/qa/validate_package.py:330-331`). `to_dict` copies `observed` (`src/twinqa/report.py:238-253`). `json_bytes` (`src/twinqa/io.py:21-22`) is a different call: `ensure_ascii=False`, `sort_keys=True`, `allow_nan=False`, then `.encode("utf-8")`. The `--json` CLI does not call `json_bytes`.

**Claimed, then verified as behavior.** [Python 3.14 json docs](https://docs.python.org/3.14/library/json.html), Character Encodings, fetched this session: with `ensure_ascii` false, characters are output as-is except quotation mark, reverse solidus, and U+0000 through U+001F; the module accepts and outputs unpaired surrogates present in the original `str`. Measured on 3.14.7: dumps returned a `str` whose lone surrogate was still a surrogate code point.

### Corpus

Synthetic. Not a real object. One generated 256×256 JPEG, solid RGB `(200, 200, 200)`, Pillow 12.3.0, sha256 `9d6bbbb4db21bf6468f917e65f23e3d7a69145340dfb0f6fb643918be5b6cf99`, base64 length 2204. Each GeoJSON is one LF-terminated ASCII line: FeatureCollection, one ObjectFeature, Point `[12345.678, 6789.012]`, the 20 App.3 property keys, `FNO_code` `123456`, `other` empty, `imageBase64` of that JPEG. Filenames are ASCII. Hashes were taken before the parser, `validate()`, and CLI calls and again after. Unchanged in 6/6 files, and the same on run 2.

| File | Bytes | SHA-256 | What varies |
|---|---:|---|---|
| `01-key-ascii.geojson` | 2732 | `a0600130330539e94012124055b8c9f68542cfe037ba002359bccb3bd419d4c1` | Glasses `[{"M_Address_MainGlass_1":1}]` |
| `02-key-cyrillic.geojson` | 2747 | `577fec05414c5002460b7aef18075710da2bea81f0be9ac9406a24e8037fcd76` | key `\u0421\u0442\u0435\u043a\u043b\u043e` (`Стекло`) |
| `03-key-pair.geojson` | 2723 | `004e1ddf39567b353598c1e6e40745fa0ad87a26a7d77b0e3cd07527177226b5` | key `\uD800\uDC00` |
| `04-key-high.geojson` | 2717 | `d6dc09fb65e7bf32f0799f677d84a38cee0f5b549b52413982c480bc050bcda9` | key `\uD800` |
| `05-key-low.geojson` | 2717 | `5ad10f59f7d352e035cd22e3b7da6b966fd69e7f62f586c2399f119084c777b7` | key `\uDC00` |
| `06-prop-high.geojson` | 2836 | `79ac103bf8ba2c5ceef9d5c00d85d3ac6eb3e48149915a3e166082746e98eafe` | `developer` is `\uD800`; Glasses value is a valid optics object |

Fixtures and raw stdout/stderr: `C:/x/t_6d2fae89/`. Full probe: `C:/x/t_6d2fae89/probe.py`. Position and CRLF checks: `C:/x/t_6d2fae89/explain_position.py`, `C:/x/t_6d2fae89/crlf_check.py`, `C:/x/t_6d2fae89/check_bytes.py`.

### Measured matrix

`read_json`, `geojson_findings`, and `validate()` raised nothing on these six files. V011 findings below are the whole list. Code points are decimal ordinals.

| Case | Parsed key / developer | V011 findings | dumps `str` | strict UTF-8 / `json_bytes` | CLI rc, stdout, stderr |
|---|---|---|---|---|---|
| 01 ASCII | key `M_Address_MainGlass_1`; developer `value` | `imageBase64` pass; `Glasses entry` fail, observed cps `77,95,65,100,100,114,101,115,115,95,77,97,105,110,71,108,97,115,115,95,49,58,32,49` | `str` len 5775, 0 surrogates | both succeed | rc 1; 6926 bytes; stderr empty; JSON `passed=false`, `exit_code=1` |
| 02 Cyrillic | key cps `1057,1090,1077,1082,1083,1086` (U+0421…U+043E) | `imageBase64` pass; `Glasses entry` fail, observed those six cps plus `58,32,49` | `str` len 5763, 0 surrogates | both succeed | rc 1; 6920 bytes; stderr empty; JSON `exit_code=1` |
| 03 valid pair | key cps `65536` (U+10000), one scalar | `imageBase64` pass; `Glasses entry` fail, observed `65536,58,32,49` | `str` len 5754, 0 surrogates | both succeed | rc 1; 6908 bytes; stderr empty; JSON `exit_code=1` |
| 04 lone high | key cps `55296` (U+D800) | `imageBase64` pass; `Glasses entry` fail, observed `55296,58,32,49` (1 surrogate) | `str` len 5754, 1 surrogate, no `\uD800` text | `UnicodeEncodeError` at dumps index 3724; `json_bytes` at 3667 | rc 1; **0 stdout bytes**; stderr 651 ASCII bytes |
| 05 lone low | key cps `56320` (U+DC00) | same shape, observed `56320,58,32,49` | `str` len 5753, 1 surrogate, no `\uDC00` text | `UnicodeEncodeError` at dumps index 3723; `json_bytes` at 3667 | rc 1; **0 stdout bytes**; stderr 651 ASCII bytes |
| 06 property contrast | key `M_Address_MainGlass_1`; developer cps `55296` | `imageBase64` pass; `Glasses` pass (`1 glass material(s)`); `schema` pass. 0 surrogates in findings | `str` len 6276, 0 surrogates | both succeed | rc 2; 7447 bytes; stderr empty; JSON `passed=false`, `exit_code=2`, V011 `pass` |

In-process `validate()` for rows 01–05 built a report with `passed=false` and `exit_code=1`. Row 06 built `passed=false` and `exit_code=2`. `code_commit` was the frozen SHA on all six objects.

CLI stderr for row 04, both policies, both runs (row 05 is the same traceback with `\udc00` and position 3875):

```text
UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' in position 3876: surrogates not allowed
```

The traceback names `tools/qa/validate_package.py:331`, the `print(json.dumps(...))` line. Position 3876 is the dumps index 3724 plus the 152 LF characters before the surrogate. Position 3875 is 3723 plus 152 LF. **Verified-by-me** in `explain_position.py`: Windows `TextIOWrapper`, after `reconfigure(encoding="utf-8")`, translates each `\n` to `\r\n` before the UTF-8 encoder. The pipe still received 0 bytes. The character index in the exception is not a prefix that was written.

For every successful CLI stdout (01, 02, 03, 06; both policies; both runs), decoding UTF-8, replacing CRLF with LF, and comparing to `json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"` matched. Parsed `observed` code points matched the in-process findings. Row 03's stdout contains the UTF-8 bytes of U+10000 (`F0 90 80 80`) and does not contain the ASCII escape `\uD800`. Row 02's stdout contains the UTF-8 bytes of `Стекло`. That is the scalar character in the report, not a `\u` escape.

Row 01 and row 06 stage lists, from the parsed CLI JSON: V001–V005, V007–V013, V015–V017 are `not_run` (14), and V011 is `fail` (row 01) or `pass` (row 06). `passed` is false in both. V006 and V014 are absent from this single-file VPM report.

### Encoding policy that was actually frozen

Parent of the probe: `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`, `PYTHONLEGACYWINDOWSSTDIO` unset. **Verified-by-me** child startup, before the CLI's `reconfigure`:

| Policy | `PYTHONIOENCODING` seen by the child | stdout | stderr | `utf8_mode` |
|---|---|---|---|---|
| controlled | `utf-8:strict` | `utf-8` / `strict` | `utf-8` / `backslashreplace` | 1 |
| inherited | `utf-8` | `utf-8` / `strict` | `utf-8` / `backslashreplace` | 1 |

The env var differed. The effective stdout error handler did not. Stderr stayed `backslashreplace` under `utf-8:strict` as well. The traceback bytes are ASCII, so that stderr handler did not have to rewrite a raw surrogate; the exception text already spells `\ud800`. Raw stdout and stderr sha256 were identical across the two policies. A stdout handler of `replace`, `backslashreplace`, or `surrogatepass` was not observed. Those outputs are not called lossless here.

### Repeatability

`uv run python C:/x/t_6d2fae89/probe.py run1` and `run2`. For all six cases and both policies: return code, stdout sha256, and stderr sha256 matched. Fixture sha256 matched before and after, and matched across runs.

### What was not measured

`summary()` text mode (the other branch of line 331). `glass_names` set to a real FBX set. A child whose stdout error handler is not `strict`. Raw UTF-16 surrogate bytes in the file (these files are ASCII escapes). The AGR reader in `dt_ai.core.io`. Pytest.

`tests/qa/test_validator.py:95-103` asserts V011 `fail` for `Glasses` 42 and for a bare glasses object. A search of `tests/` found no `Glasses entry` string and no `surrogate`. Those tests were read, not run.

## How it applies to this repository

PKG-19 (`docs/domain/areas/package.md`) says V011 decodes UTF-8 and parses JSON. These files are valid UTF-8; the loss happens after a successful parse, when a diagnostic `str` is encoded for the CLI. PKG-25 names the Glasses structure check. The measured loss uses the existing `Glasses entry` finding, which the single-file CLI does build.

The property-value row shows a parsed lone surrogate that never becomes a finding. V011 then passes. The package report still has `passed=false` and exit 2 because fourteen stages are `not_run`. That helper pass is not delivery acceptance (`docs/domain/areas/package.md` readiness note; `AGENTS.md` on `passed=true`).

`docs/research/strict-reader-semantic-boundaries.md` left surrogate edges untested for the QA byte decoder. This corpus does not exercise a bad UTF-8 byte. It exercises JSON escapes that `json.loads` turns into surrogate code points, then the report encoder.

## Proposed next tasks

1. **Emit the V011 JSON report when `Glasses entry` contains a lone surrogate.** Keep today's fail finding and the `exit_code` 1 verdict. Change only serialization so `tools/qa/validate_package.py --profile vpm --json` writes a complete strict UTF-8 JSON document for the frozen `04-key-high` and `05-key-low` fixtures: non-empty stdout, empty stderr, `json.loads` succeeds, and the parsed `observed` code points are still `55296,58,32,49` and `56320,58,32,49`. Cover `json_bytes` on the same dict if that helper remains the other UTF-8 encoder. Add RED tests for those two fixtures plus the ASCII control. A single-file V011 result stays short of delivery acceptance. Value: the diagnostic exists in memory and is dropped on the way to stdout. Effort: S. Advances #149.

2. **Pin the property-value contrast as current behavior.** One RED test for `06-prop-high`: `developer` ordinal 55296, V011 findings contain no surrogate, CLI stdout is strict UTF-8 JSON, V011 status is `pass`, report `passed` is false. Do not add a new acceptance rule in that test. Value: keeps the measured split visible so a later encoder change cannot be read as a decision about property values. Effort: S. Advances #149.

Open roadmap issues fetched this session from `https://api.github.com/repos/artsafro/AGR-DigitalTwin-pilot/issues?state=open&labels=roadmap&per_page=100` (8 issues): #426, #425, #371, #352, #349, #337, #298, #149. #149 is open, roadmap-labelled, title "Spec: capability roadmap NPM/VPM - L1 sheets, L2 self-checks, L3 verify". No issue was created.

## Open questions for the user

1. Should a lone surrogate in a property value that never reaches a finding stay a V011 pass, as measured for `developer`, or become its own finding?
2. Should diagnostic JSON keep the code point by escaping it (`\uD800` in the UTF-8 bytes), or should the parser reject an unpaired escape before findings are built?
3. Successful reports here were UTF-8 with Windows CRLF, and `json.loads` accepted them. Is LF-only part of the report contract?
4. Stdout was `strict` for both policies on this host. Is a `replace` or `backslashreplace` stdout in scope, or is strict UTF-8 the only output that counts?

## Probe excerpt

Effective corpus rows in `C:/x/t_6d2fae89/probe.py`. A draft sixth tuple is replaced before any fixture is written; the hashes above are from the replacement:

```python
CASES[5] = (
    "06-prop-high",
    '[{"M_Address_MainGlass_1":' + GLASS_OK + "}]",
    '"\\uD800"',
    "lone high surrogate in developer, valid glasses object",
)
```

`GLASS_OK` is the ASCII object `color_RGB` plus `transparency`, `refraction`, `roughness`, and `metallicity`. Rows 01–05 use a non-dict entry `1` under the material key.

CLI, one fresh process per fixture per policy:

```python
subprocess.run(
    ["uv", "run", "python", str(CLI), str(path), "--profile", "vpm", "--json"],
    cwd=REPO, env=env, capture_output=True, timeout=180,
)
```
