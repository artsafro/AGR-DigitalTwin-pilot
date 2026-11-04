# GeoJSON: do small finite exponents and underflow bypass the three-decimal review?

Pinned source revision: `4c863c1a4616f1812595536d0507f53034e9acfe` (driver pin). The same value is the `code_commit` field of every CLI report below. This session did not run git; `ValidationReport` stamps that field itself (`src/twinqa/report.py:283-290`).
Interpreter, `uv run python -VV`: `Python 3.14.7 (main, Aug  7 2026, 02:26:22) [MSC v.1944 64 bit (AMD64)]`.
`sys.float_info.min` on that interpreter: `2.2250738585072014e-308`.
Synthetic data only. Corpus frozen before any probe and not extended afterwards.

Evidence labels: **Verified** = ran on this tree. **Source** = read from the file, not a separate run.

## Summary

A coordinate whose exact decimal scale is greater than 3 still reaches V011 `pass` and an explicit `schema: pass` when `repr(float(...))` contains `e`. `_decimals` (`src/twinqa/geojson.py:32-34`) then returns 0, and the review at `:113-114` does not fire. In this corpus that is the finite tokens of scale 6, 7 and 308, fixed-point and scientific spellings alike, including the y-axis `1e-7` and the negative `-1e-7`.
`1e-4` and `0.0001` (exact scale 4) do not take that path. `repr` rewrites them as `0.0001`, `_decimals` returns 4, and V011 is `review`. A small exponent is not by itself a bypass.
`1e-324`, `1e-400` and `-1e-400` also reach `schema: pass`, by a different change that happens earlier: `read_json` / `json.loads` underflows them to `0.0` or `-0.0` before `_decimals`. The function then takes its fixed-point branch on that zero and returns 0. The sign of `-1e-400` survives as `-0.0`.
Every nonzero finite token here, including the controls `12345.678` and `12345.6789`, differs from its exact decimal (binary64 quantization). That inequality did not remove the scale-4 review. `_decimals` counts digits of `repr`, which is a third spelling, after the lexical token and after the binary64 value.
On a single `.geojson`, V011 `pass` still leaves `passed: false` and process exit 2: eleven other blocking stages are `not_run`. No token raised. A schema pass is not delivery acceptance.

## Frozen corpus

Raw tokens are substituted into JSON bytes. The other axis is the raw token `6789.012`, except `t-y-1e-7`, whose x token is `12345.678`. The same JSON bytes are written as `synthetic_oks.geojson` (`ground=False`) and `synthetic_Ground.geojson` (`ground=True` only because the stem ends in `_Ground`). Properties are nonempty, `act_AGR` is `synthetic-act`, `name` is `synthetic`, `FNO_code` is `123 456`, `Glasses` is `[]`. The image is one generated 256×256 JPEG (RGB 120,130,140), 1650 bytes, SHA-256 `2116f6e3c323954039d16f9ee4f542fdfec43e5881fde35c0759cd1090b938c9`. Python floats are not serialized into the coordinate tokens.

| id | axis | raw token | other-axis raw token |
|---|---|---|---|
| t-0 | x | `0` | `6789.012` |
| t-neg0 | x | `-0.0` | `6789.012` |
| t-0.001 | x | `0.001` | `6789.012` |
| t-0.0001 | x | `0.0001` | `6789.012` |
| t-0.000001 | x | `0.000001` | `6789.012` |
| t-0.0000001 | x | `0.0000001` | `6789.012` |
| t-1e-3 | x | `1e-3` | `6789.012` |
| t-1e-4 | x | `1e-4` | `6789.012` |
| t-1e-6 | x | `1e-6` | `6789.012` |
| t-1e-7 | x | `1e-7` | `6789.012` |
| t-1e-308 | x | `1e-308` | `6789.012` |
| t-1e-324 | x | `1e-324` | `6789.012` |
| t-1e-400 | x | `1e-400` | `6789.012` |
| t-neg-1e-7 | x | `-1e-7` | `6789.012` |
| t-neg-1e-400 | x | `-1e-400` | `6789.012` |
| t-y-1e-7 | y | `1e-7` | `12345.678` |
| t-ctrl-3 | x | `12345.678` | `6789.012` |
| t-ctrl-4 | x | `12345.6789` | `6789.012` |

Exact value and scale below use `decimal.Decimal` on the raw token. Scale is the number of fractional digits in `format(abs(Decimal), 'f')` after stripping trailing zeros. `_decimals` is recorded as a measured return, not as the definition of scale.

## Findings

### 1. Two representation changes happen before the V011 precision finding (Verified + Source)

Call chain for a single file: `validate` reads the bytes (`tools/qa/validate_package.py:191`) and, for `.geojson`, extends V011 with `geojson_findings` (`:228-230`). Inside that function, `read_json` (`src/twinqa/io.py:38-42`) decodes UTF-8 and calls `json.loads` with `parse_constant` set and `parse_float` left as `float`. The coordinate check then runs (`src/twinqa/geojson.py:111-114`).

Measured order on every frozen token:

1. Lexical token → Python value. `0` stays `int`. Every other token becomes `float`. `1e-324`, `1e-400` and `-1e-400` become `0.0` or `-0.0` (hex `0x0.0p+0` / `-0x0.0p+0`). `1e-308` stays a nonzero subnormal (hex `0x0.730d67819e8d2p-1022`). `parse_constant` is not involved: these tokens are numeric literals, and `read_json` returned a document for all 18.
2. That Python value → `repr(float(value))` inside `_decimals` (`src/twinqa/geojson.py:32-34`). The source returns 0 when the text has no `.` or when it contains `e`. Otherwise it counts the fractional digits of that repr after `rstrip("0")`.
3. The comparison `_decimals(c) > decimal_places` uses `standards/VPM_STANDARD.yaml:135` (`decimal_places: 3`). The finding text is the literal `3 decimal places` (`src/twinqa/geojson.py:114`).

The file bytes are unchanged by `validate` and by the CLI (SHA-256 before and after matched on every row).

### 2. The exponent branch drops a finite scale greater than 3 (Verified)

`_decimals` returned 0 with branch `exponent` for `0.000001`, `1e-6` (both repr `1e-06`, hex `0x1.0c6f7a0b5ed8dp-20`), `0.0000001`, `1e-7`, y-axis `1e-7` (repr `1e-07`, hex `0x1.ad7f29abcaf48p-24`), `-1e-7` (repr `-1e-07`, hex `-0x1.ad7f29abcaf48p-24`), and `1e-308` (repr `1e-308`). Exact scales are 6, 7 and 308. Each document’s findings are exactly `imageBase64: pass`, `Glasses: pass`, `schema: pass`. V011 is `pass`. There is no `coordinates precision` finding. The other axis scored 3 (`6789.012` or `12345.678`), so the probed axis alone decided the comparison.

`schema: pass` is appended only when every finding so far is `pass` (`src/twinqa/geojson.py:142-143`). These rows reached that statement.

### 3. Scale 4 still reviews, including the scientific spelling `1e-4` (Verified)

`0.0001` and `1e-4` share exact value `0.0001`, scale 4, and hex `0x1.a36e2eb1c432dp-14`. Both repr as `0.0001`. `_decimals` returns 4 on the fixed-point branch. Findings: `coordinates precision: review` with observed `[0.0001, 6789.012]`, then `imageBase64: pass`, `Glasses: pass`. No `schema` finding. V011 is `review`.
`12345.6789` (scale 4, repr `12345.6789`, hex `0x1.81cd6e631f8a1p+13`) reviews with observed `[12345.6789, 6789.012]`.
`0.001` and `1e-3` share exact `0.001`, scale 3, hex `0x1.0624dd2f1a9fcp-10`, repr `0.001`, `_decimals` 3, and the three pass findings. `12345.678` (scale 3, repr `12345.678`) does the same.
So `repr` rewrites a lexical exponent into fixed-point form when the shortest spelling has no `e`, and the review follows that spelling. The frozen corpus has no `1e-5` or `0.00001`, so the switch between the scale-4 review and the scale-6 exponent return is not located more tightly than those two points.

### 4. Underflow removes the token before `_decimals` (Verified)

| token | exact scale | parsed repr | hex | sign | `_decimals` branch | return |
|---|---|---|---|---|---|---|
| `1e-324` | 324 | `0.0` | `0x0.0p+0` | + | fixed-rstrip | 0 |
| `1e-400` | 400 | `0.0` | `0x0.0p+0` | + | fixed-rstrip | 0 |
| `-1e-400` | 400 | `-0.0` | `-0x0.0p+0` | − | fixed-rstrip | 0 |

`Decimal(token) != 0` and the parsed float compares equal to zero, so this is underflow, not an exact zero. Findings are the same three passes as a clean three-decimal file. V011 is `pass`. The exponent branch does not run: the text `_decimals` sees is `0.0` or `-0.0`.
`0` is a real integer zero (`type int`, repr of the float `0.0`, hex `0x0.0p+0`, scale 0). `-0.0` is a float signed zero (hex `-0x0.0p+0`, scale 0 after the trailing zero is ignored). Both also return 0 and pass V011. Their exact values are zero, so they are not underflow.

### 5. Binary64 quantization is present on the controls and does not choose the review (Verified)

`Decimal.from_float(parsed) == Decimal(token)` only for `0` and `-0.0`. Every other finite nonzero token is `quantized`, including `12345.678`, `0.001` and `0.0001`. The scale-4 rows still review. The check never sees the exact decimal expansion of the binary64 value; it sees `repr`.

Pairs with the same exact decimal share a hex and a verdict, and differ in file bytes: `0.0000001` SHA-256 `d594d50c150bb117618f583b5fd6e133d659656a3b642d0bf53e907cb2ad554d` versus `1e-7` SHA-256 `d650c079b82db58de486d79c9db0d9199d85e540763c2682e4377e607b528803`.

### 6. In-process report and real CLI agree; a V011 pass is not `passed` (Verified)

`validate(..., "vpm")` returned a report for all 18 OKS files and all 18 Ground files. Ground findings, V011, `passed` and `exit_code` matched the OKS file of the same bytes on every token. `_decimals` raised on none.

CLI: `uv run python tools/qa/validate_package.py <file> --profile vpm --json`, timeout 120 s, two runs each. Stderr was empty (0 bytes) on every run. Stdout was strict UTF-8 and one JSON object. Process `rc` was 2, equal to the report `exit_code`. Input SHA-256 was unchanged. Run 2 repeated run 1’s stdout SHA-256. `code_commit` was the pinned SHA. Notes: `single GeoJSON: only V011 applies`.

| CLI case | file | input SHA-256 | rc | stdout SHA-256 | stdout bytes | V011 | passed | exit | machine counts |
|---|---|---|---|---|---|---|---|---|---|
| clean three-decimal `12345.678` | OKS | `7678090524596a196ded606133a4f73d2dafb7abf2e979c2f96fac3b264a4548` | 2 | `6cdca13d0653f0e18a7710ff9d6ebefa6fb78930f069c889a1c2bd32cdd960fe` | 7459 | pass | false | 2 | pass 1, review 0, not_run 11 |
| four-decimal `12345.6789` | OKS | `0c9448aa1a81aa257fe7fbd9844d7b1e6ded63407b85fbfffcc386e5d8eec9ac` | 2 | `3d3bb02f4383fb1150373365d52ad84724cde3a158b02b127323cfbe4840ab18` | 7356 | review | false | 2 | review 1, not_run 11 |
| `0.0000001` | OKS | `d594d50c150bb117618f583b5fd6e133d659656a3b642d0bf53e907cb2ad554d` | 2 | `c9780b0dd1b0ccbe6aa21cc9ef677fb71ddfaf25bf433ed7a987aff7fbbc254f` | 7462 | pass | false | 2 | pass 1, not_run 11 |
| `1e-7` | OKS | `d650c079b82db58de486d79c9db0d9199d85e540763c2682e4377e607b528803` | 2 | `5c3302338ce97d00e187d30a94fe9f4cf34413fb053c267f0b8de0a8e04bae48` | 7457 | pass | false | 2 | pass 1, not_run 11 |
| `-1e-400` | OKS | `b85dd3430b8f2599bf11908b17f582a9a75637a60f4452ae6578263945c5f907` | 2 | `72c595019a0389fcf340f85d7398d47e120698c19b1694dbfe7cca8cafb8f984` | 7463 | pass | false | 2 | pass 1, not_run 11 |
| `1e-400` | OKS | `e26c3d8f40ec55af303d41dda5f835725de07fd8d63ad880d683324154ede6ad` | 2 | `6a82734457809649fd6c0d74b293be4583940356cd8c45c5652826438d6a9cf5` | 7459 | pass | false | 2 | pass 1, not_run 11 |
| Ground counterpart of `1e-7` | Ground stem | `d650c079b82db58de486d79c9db0d9199d85e540763c2682e4377e607b528803` | 2 | `0b2088cde7a8733621a417f9f907370971de4b681d584e2c1534262b4d8b89c7` | 7464 | pass | false | 2 | pass 1, not_run 11 |

The pass rows’ V011 findings are `imageBase64` / `Glasses` / `schema`, all `pass`. The four-decimal row’s V011 findings are `coordinates precision: review` (observed `[12345.6789, 6789.012]`), `imageBase64: pass`, `Glasses: pass`. `passed` is false because `ValidationReport.passed` requires every blocking stage to be `pass` (`src/twinqa/report.py:226-228`); a stage with no findings is `not_run` (`:171-173`). Exit 2 is the “no fail, but not passed” code (`:231-236`). Manual stages V015–V017 are pending. V013 (MSK-77 position) is `not_run` on a single GeoJSON. PKG-24’s plan-position check stays manual (V017; `docs/domain/areas/package.md:46`, `:72`).

ZIP wiring (`tools/qa/validate_package.py:121-122`) and `tools/sintez_parity.py:206` also call `geojson_findings`. This session did not run them.

## Compact reproducer

From the repo root, `uv run python`. Synthetic JPEG and synthetic properties. The placeholders are raw-token substitutions.

```python
import base64, json
from io import BytesIO
import sys; sys.path.insert(0, "src")
from PIL import Image
from twinqa.profiles import load_profiles
from twinqa.geojson import geojson_findings
from twinqa.io import read_json

profile = load_profiles().vpm
keys = profile["geojson"]["properties_keys"]
buf = BytesIO(); Image.new("RGB", (256, 256), (120, 130, 140)).save(buf, "JPEG")
props = {k: "synthetic" for k in keys}
props.update(FNO_code="123 456", other="", act_AGR="synthetic-act",
             imageBase64=base64.b64encode(buf.getvalue()).decode())

def render(x, y="6789.012"):
    doc = {"type": "FeatureCollection", "features": [{
        "type": "ObjectFeature",
        "geometry": {"type": "Point", "coordinates": ["<X>", "<Y>"]},
        "properties": props, "Glasses": []}]}
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    return text.replace('"<X>"', x, 1).replace('"<Y>"', y, 1).encode()

def show(label, data):
    coords = read_json(data)["features"][0]["geometry"]["coordinates"]
    names = [(f.name, f.status) for f in geojson_findings(data, profile, ground=False)]
    print(label, coords, names)

show("1e-4", render("1e-4"))
show("1e-7", render("1e-7"))
show("1e-400", render("1e-400"))
show("clean", render("12345.678"))
```

Observed on this tree: `1e-4` → `[0.0001, 6789.012]` and a `coordinates precision` review; `1e-7` → `[1e-07, 6789.012]` and `schema: pass` with no coordinate finding; `1e-400` → `[0.0, 6789.012]` and the same three passes; `clean` → the same three passes.

## Frozen outcomes

`rel` is `Decimal(token)` against `Decimal(int)` or `Decimal.from_float`. `branch` is the arm of the `_decimals` condition on `repr(float(value))`. Findings are the whole V011 list. `passed` / `exit` are the in-process report. Ground matched every row. Report object existed for every row. No exceptions.

| id | token | exact | scale | type | repr | class | sign | zero | hex | rel | `_decimals` | branch | findings | V011 | passed | exit | SHA-256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t-0 | `0` | 0 | 0 | int | `0` | zero | + | yes | `0x0.0p+0` | equal | 0 | fixed-rstrip | 3 pass + schema | pass | false | 2 | `19eb30dc9489cf1518596529a6497ce13a4854fe0776cbbca9a045360a336235` |
| t-neg0 | `-0.0` | -0 | 0 | float | `-0.0` | zero | − | yes | `-0x0.0p+0` | equal | 0 | fixed-rstrip | 3 pass + schema | pass | false | 2 | `ffc97b0fbe982a0c7236bcc6d25013961fb8e36b92a49c223a6b3546337de237` |
| t-0.001 | `0.001` | 0.001 | 3 | float | `0.001` | normal | + | no | `0x1.0624dd2f1a9fcp-10` | quantized | 3 | fixed-rstrip | 3 pass + schema | pass | false | 2 | `dd195ece150e2ff9cbf5fe91dac1808459a587a8fa234a1162b1c638dbe38f75` |
| t-0.0001 | `0.0001` | 0.0001 | 4 | float | `0.0001` | normal | + | no | `0x1.a36e2eb1c432dp-14` | quantized | 4 | fixed-rstrip | precision review | review | false | 2 | `6a5c10ed0799d7117b49bc63f36c816a14aae6f7703fed4178d9c60461a46651` |
| t-0.000001 | `0.000001` | 0.000001 | 6 | float | `1e-06` | normal | + | no | `0x1.0c6f7a0b5ed8dp-20` | quantized | 0 | exponent | 3 pass + schema | pass | false | 2 | `be7b59c2a18257e78c23883c90dcfc82dfb7fc3fe37d34f54a2ff82aab89801a` |
| t-0.0000001 | `0.0000001` | 0.0000001 | 7 | float | `1e-07` | normal | + | no | `0x1.ad7f29abcaf48p-24` | quantized | 0 | exponent | 3 pass + schema | pass | false | 2 | `d594d50c150bb117618f583b5fd6e133d659656a3b642d0bf53e907cb2ad554d` |
| t-1e-3 | `1e-3` | 0.001 | 3 | float | `0.001` | normal | + | no | `0x1.0624dd2f1a9fcp-10` | quantized | 3 | fixed-rstrip | 3 pass + schema | pass | false | 2 | `112e4260e9d58596815789f7f19e7d3ad8e829bbe6443e117acd6b1778772110` |
| t-1e-4 | `1e-4` | 0.0001 | 4 | float | `0.0001` | normal | + | no | `0x1.a36e2eb1c432dp-14` | quantized | 4 | fixed-rstrip | precision review | review | false | 2 | `74145b7163de458406ad027eeba0748b02322c5ccd22db3ce70527a3592b93dd` |
| t-1e-6 | `1e-6` | 0.000001 | 6 | float | `1e-06` | normal | + | no | `0x1.0c6f7a0b5ed8dp-20` | quantized | 0 | exponent | 3 pass + schema | pass | false | 2 | `bed916e54914df2d79ceb98443c9cbf845d8192364288bc6b4b378c1e28c7eac` |
| t-1e-7 | `1e-7` | 0.0000001 | 7 | float | `1e-07` | normal | + | no | `0x1.ad7f29abcaf48p-24` | quantized | 0 | exponent | 3 pass + schema | pass | false | 2 | `d650c079b82db58de486d79c9db0d9199d85e540763c2682e4377e607b528803` |
| t-1e-308 | `1e-308` | 1E-308 | 308 | float | `1e-308` | subnormal | + | no | `0x0.730d67819e8d2p-1022` | quantized | 0 | exponent | 3 pass + schema | pass | false | 2 | `a24cffbdbff7f8072c348969378d8d5b4e7c42a2433af46c37cb086dbea10a74` |
| t-1e-324 | `1e-324` | 1E-324 | 324 | float | `0.0` | zero | + | yes | `0x0.0p+0` | underflow-to-zero | 0 | fixed-rstrip | 3 pass + schema | pass | false | 2 | `c4ba14e6eba4bbed8b51e1a5e31a064ebc5d6324ab5cc87ca4aa20f3c3e6f0e1` |
| t-1e-400 | `1e-400` | 1E-400 | 400 | float | `0.0` | zero | + | yes | `0x0.0p+0` | underflow-to-zero | 0 | fixed-rstrip | 3 pass + schema | pass | false | 2 | `e26c3d8f40ec55af303d41dda5f835725de07fd8d63ad880d683324154ede6ad` |
| t-neg-1e-7 | `-1e-7` | -0.0000001 | 7 | float | `-1e-07` | normal | − | no | `-0x1.ad7f29abcaf48p-24` | quantized | 0 | exponent | 3 pass + schema | pass | false | 2 | `8fb4acab4e8de1b197eb34f483ced4f3047ed9d9ca3b0b9069d69f4f930b9b5d` |
| t-neg-1e-400 | `-1e-400` | -1E-400 | 400 | float | `-0.0` | zero | − | yes | `-0x0.0p+0` | underflow-to-zero | 0 | fixed-rstrip | 3 pass + schema | pass | false | 2 | `b85dd3430b8f2599bf11908b17f582a9a75637a60f4452ae6578263945c5f907` |
| t-y-1e-7 | `1e-7` on y | 0.0000001 | 7 | float | `1e-07` | normal | + | no | `0x1.ad7f29abcaf48p-24` | quantized | 0 | exponent | 3 pass + schema | pass | false | 2 | `c7a31a604e50444c2dbeb83874cac730c2cc803562b3c798a7aab65ef3600270` |
| t-ctrl-3 | `12345.678` | 12345.678 | 3 | float | `12345.678` | normal | + | no | `0x1.81cd6c8b43958p+13` | quantized | 3 | fixed-rstrip | 3 pass + schema | pass | false | 2 | `7678090524596a196ded606133a4f73d2dafb7abf2e979c2f96fac3b264a4548` |
| t-ctrl-4 | `12345.6789` | 12345.6789 | 4 | float | `12345.6789` | normal | + | no | `0x1.81cd6e631f8a1p+13` | quantized | 4 | fixed-rstrip | precision review | review | false | 2 | `0c9448aa1a81aa257fe7fbd9844d7b1e6ded63407b85fbfffcc386e5d8eec9ac` |

“3 pass + schema” means `imageBase64: pass`, `Glasses: pass`, `schema: pass`. “precision review” means `coordinates precision: review` plus the image and Glasses passes, and no schema finding.

## How it applies to this repository

- `src/twinqa/io.py:38-42` — `read_json` turns the token into an int or a binary64 before any coordinate finding. Underflow to ±0 happens here. `parse_constant` (`:34-35`) handles the literals `Infinity` / `NaN`, which this corpus does not use.
- `src/twinqa/geojson.py:28-29` — `_number` accepts that int or float.
- `src/twinqa/geojson.py:32-34` — `_decimals` scores `repr`, and the `e` arm returns 0.
- `src/twinqa/geojson.py:111-114` — the only precision comparison. It emits `review`, and only when that return is greater than 3.
- `src/twinqa/geojson.py:142-143` — `schema: pass` when the precision review was not emitted and nothing else failed.
- `tools/qa/validate_package.py:228-230` — single-file V011. `:121-122` is the ZIP call, not run here.
- `src/twinqa/report.py:171-173`, `:226-236` — `not_run` stages keep `passed` false and the exit code at 2 when V011 itself passes.
- `standards/VPM_STANDARD.yaml:135` — `coordinates.decimal_places: 3`. The implementation applies that integer to `repr` digits.
- `standards/DELIVERY_VALIDATOR.yaml:85-90` — V011 is a blocking stage.
- `docs/domain/areas/package.md:41`, `:46` — PKG-19 is syntax and keys; PKG-24 is the 3-decimal insertion point. Position against the survey is V013 `not_run` plus V017 manual (`:68`, `:72`).

## Proposed next tasks

No status and no threshold is chosen here.

1. **Exponent-form diagnostic for a finite coordinate (effort S).** Pin the already measured split between a scale-4 scientific token and a scale-7 scientific token. Input → diagnostic: `1e-7` → V011 `pass`, findings `imageBase64`/`Glasses`/`schema` all `pass`, parsed repr `1e-07`, `_decimals` 0. Paired input `0.0000001` → the same verdict and the same hex `0x1.ad7f29abcaf48p-24`, with a different file SHA-256. Control `1e-4` → `coordinates precision: review`, observed `[0.0001, 6789.012]`, no `schema` finding. Control `12345.678` → V011 `pass` with `schema: pass`. Advances #149.
2. **Underflow-versus-exponent diagnostic (effort M).** Separate a token that is already ±0 when `_decimals` runs from a token that is still a tiny finite float. Input → diagnostic: `1e-400` → parsed `0.0`, `_decimals` branch fixed-rstrip, return 0, V011 `schema: pass`. `-1e-400` → parsed `-0.0` (hex `-0x0.0p+0`), same verdict, sign still visible on the float. `1e-308` → nonzero subnormal, `_decimals` branch exponent, return 0, same V011 `schema: pass`. Control `1e-4` → `coordinates precision: review`. Advances #149.

## Open questions

These are user choices. This report does not pick one.

- Precision definition: lexical fractional digits of the source token, exact decimal scale of that token (trailing zeros ignored), or the fractional digits of the shortest binary64 `repr`.
- Threshold: whether `decimal_places: 3` applies to the chosen definition, and whether a value whose shortest `repr` uses an exponent counts as more than three decimal places.
- Finiteness and magnitude: whether a finite subnormal, or any absolute value below a bound the user sets, is in scope on its own, apart from the decimal count.
- Parser rejection: whether `read_json` should reject a numeric literal that underflows to ±0, or keep accepting it as zero the way it does today.
- Fail versus review: when the exact scale is greater than 3 and the current check emits no `coordinates precision` finding, what status a future check would use.

## Sources

- **Verified** on `4c863c1a4616f1812595536d0507f53034e9acfe`, CPython 3.14.7 via `uv run python`. In-process `geojson_findings` and `validate` for all 18 tokens, OKS and Ground. Two CLI runs each of the seven files in the CLI table. Scratch probe and raw stdout/stderr: `C:/x/t_02b51ff8/`. No pytest, no ZIP, no DCC.
- **Source**, read in this session: `src/twinqa/geojson.py`, `src/twinqa/io.py`, `src/twinqa/report.py`, `tools/qa/validate_package.py`, `tools/sintez_parity.py:206`, `standards/VPM_STANDARD.yaml:135`, `standards/DELIVERY_VALIDATOR.yaml:85-90`, `docs/domain/areas/package.md` PKG-19 and PKG-24.
