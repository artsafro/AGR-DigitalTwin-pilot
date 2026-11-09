# GeoJSON: does exponent overflow reach a schema-pass finding or a parser failure?

Pinned source revision: `8d5c8987dbd46343176ca5af9d1791c864a86217` (merge of PR #395).
Origin of the question: `strict-reader-semantic-boundaries` (PR #406) observed that JSON `read_json` rejects the
literal `Infinity` yet silently accepts `1e400` as `inf`. This card implements only the **field-specific exposure**
part of that report's Proposal M; it does not choose a finite-value policy.

## Summary

- CPython `json` parses the numeric literal `1e400` to `float('inf')` (and `-1e400` to `-inf`) **without** calling
  `parse_constant`; only the literals `Infinity` / `-Infinity` / `NaN` reach `parse_constant`. Verified locally.
- `read_json` (both `src/twinqa/io.py` and `src/dt_ai/core/io.py`) rejects `Infinity`/`NaN` via `parse_constant` but
  therefore does **not** reject `1e400`: the parsed document carries a non-finite `float('inf')` coordinate.
- In `src/twinqa/geojson.py`, a coordinate `1e400` passes the number check (`numbers.Real`, not `bool`) and the
  decimal-places check (`_decimals(inf)` returns 0), so a complete synthetic OKS GeoJSON with a `1e400` coordinate
  emits **no fail/review finding** and ends with an explicit `schema: pass` finding → V011 stage `pass`.
- The same overflow in a Glasses optical field (`transparency`/`refraction`) is **caught as a `fail`**, but only
  because its bounded range (`0..1`, `1..3`) rejects `inf`; coordinates have no upper bound, only a 3-decimal rule.
- The delivery report's JSON stays strict-serializable: findings store `observed` as text, so `inf` never leaks into
  the `--json` payload (`json.dumps(..., allow_nan=False)` succeeds).
- In the AGR raw-dict path (`src/dt_ai/validate/bundle.py`), `read_json` accepts `1e400` → `inf`, but the pydantic
  contract (`Finite`/`Positive`, `allow_inf_nan=False`) rejects it as a `ValidationError`, which `bundle.validate`
  catches (`ValidationError` is a `ValueError` subclass) and records as a `fail`. So no false pass there.

## Findings

Evidence labels: **Verified** = ran a bounded probe against the pinned tree and read the code; **Source says** = the
raising PR's claim, not independently rerun here.

### 1. Primary Python json behavior (Verified)

`json.loads` decodes number literals with the default `parse_float=float`; overflow yields `inf`/`-inf` and
`parse_constant` is invoked **only** for the three JSON constants. Probe result (CPython, project interpreter via `uv run`):

| Input bytes | `json.loads` result | isfinite | note |
|---|---|---|---|
| `1e400` | `inf` | False | accepted silently |
| `-1e400` | `-inf` | False | accepted silently |
| `1e309` | `inf` | False | accepted silently |
| `1e308` | `1e+308` | True | largest finite |
| `Infinity` | `ValueError(const:Infinity)` | — | reaches `parse_constant` |
| `-Infinity` | `ValueError(const:-Infinity)` | — | reaches `parse_constant` |
| `NaN` | `ValueError(const:NaN)` | — | reaches `parse_constant` |

This is the CPython stdlib contract (`json.decoder`/`json.scanner`; `parse_float` default `float`). The project's
`read_json` replaces only `parse_constant` (`src/twinqa/io.py:34-42`, `src/dt_ai/core/io.py:30-32`), so the numeric
overflow path is untouched.

### 2. Coordinate overflow reaches a `schema: pass` (Verified)

`src/twinqa/geojson.py:28-29` accepts any `numbers.Real` that is not `bool`; `float('inf')` is a `numbers.Real`.
`_decimals` (`:32-34`) computes `repr(float(value))`; `repr(inf) == 'inf'` has no `.`, so it returns 0 decimals and the
3-decimal review (`:111-114`) never fires. Result on a complete synthetic OKS document with coordinate `1e400`:

- `read_json` returns a dict; `coordinates == [inf, 6789.012]`, `math.isfinite(inf) == False`.
- `geojson_findings` returns exactly `[imageBase64 pass, Glasses pass, schema pass]` — **no finding names the
  coordinate**, and the final `schema: pass` (`:142-143`) is emitted.
- The `-1e400` derivative on the y-axis behaves identically (`-inf`, same three pass findings).

Explicit `Infinity` (raw literal) is the contrast case: `read_json` raises `ValueError("Nonfinite value: Infinity")`
and `geojson_findings` returns one `JSON: fail` (`:92-93`). So the guard exists for the *constant spelling* but not for
the *numeric spelling* that overflows to the same `inf`.

### 3. Glasses optical overflow is caught, but as a range fail (Verified)

`_glasses` (`src/twinqa/geojson.py:66-69`) checks `_number(v) and lo <= v <= hi`. With `transparency = 1e400` →
`inf`, `0 <= inf <= 1` is False, so it emits `Glasses transparency: fail` with observed text `M_Test_MainGlass_1: inf`.
`refraction = -1e400` → `-inf` emits `Glasses refraction: fail` with observed `...: -inf`. These are correct rejections,
but they are classified as *range* failures, not as *non-finite*; the observed text still contains `inf`/`-inf`. There
is no false pass on the optical path.

### 4. Clean finite controls and the bool control behave as designed (Verified)

- Complete synthetic OKS (SHA `de902175cc85…`) and Ground (SHA `78c61611146a`) documents both return **no** non-pass
  finding (Ground needs `act_AGR` non-empty; the OKS/Ground nullable sets differ, `standards/VPM_STANDARD.yaml:139-140`).
- A finite 4-decimal coordinate (`12345.6789`) returns `coordinates precision: review` (`[12345.6789, 6789.012]`).
- A boolean coordinate `true` returns `coordinates: fail` (`[True, 6789.012]`) — `bool` is excluded by `_number`.

### 5. Local schema pass ≠ whole-package pass ≠ user acceptance (Verified)

`tools/qa/validate_package.py` on the suspect document:

- **Single `.geojson` target** (`:207-209`): V011 status `pass`, but `report.passed == False` and `exit_code == 2`,
  because every other blocking stage (V001-V013 except V011) has no findings and is `not_run`. Single-file scope covers
  only V011.
- **ZIP with the suspect GeoJSON + invalid FBX + 3 valid PNGs** (`validate_vpm_zip`, `:59-111`): V011 status `pass`,
  V001 `pass`, V002 `fail` (bad FBX header), V007 `fail` (texture names) → `report.passed == False`, `exit_code == 1`.
  The GeoJSON stage passes locally while the package fails on other components.
- **Strict-JSON serializability**: `json.dumps(report.to_dict(), allow_nan=False)` round-trips without error; the
  diagnostic payload contains no raw `inf`/`NaN` because `Finding.observed` is always `str` (`src/twinqa/report.py:12-24`).
- **User acceptance** is a separate manual gate (V015-V017, `docs/domain/areas/package.md:12`: no delivery has ever
  `passed`; `passed=false` everywhere). A local V011 `pass` is therefore never delivery acceptance.

### 6. AGR raw-dict path: parser accepts, contract rejects (Verified)

`src/dt_ai/validate/bundle.py:44` calls `BuildJob.model_validate(read_json(...))`. `read_json`
(`src/dt_ai/core/io.py:30-32`) accepts `1e400` → `inf`. The pydantic model's float fields
(`Finite` = `Annotated[float, Field(allow_inf_nan=False)]`, `src/dt_ai/core/provenance.py:6`; `Positive`,
`src/dt_ai/core/models.py:8`) then reject `inf`. Probe: `read_json` of
`{"project_zero_m": 1e400, ...}` returns `project_zero_m = inf`; `Placement.model_validate` raises
`ValidationError` (2 errors). `ValidationError` is a `ValueError` subclass (verified: `issubclass(..., ValueError) is
True`), so the `except (ValueError, KeyError, OSError, TypeError, BadZipFile)` boundary at
`src/dt_ai/validate/bundle.py:36-55` catches it and records a `C001` fail. No false pass; the distinction is **parser
acceptance** (returns `inf`) vs **later contract rejection** (pydantic `Finite`).

## Compact reproducer

Run from the repo root with `uv run python` (needs `Pillow`, `PyYAML`, `pydantic`; no pytest, no DCC):

```python
import base64, hashlib, json, math
from io import BytesIO
import sys; sys.path.insert(0, "src")
from PIL import Image
from twinqa.profiles import load_profiles
from twinqa.geojson import geojson_findings
from twinqa.io import read_json

PROFILE = load_profiles().vpm
KEYS = PROFILE["geojson"]["properties_keys"]
buf = BytesIO(); Image.new("RGB", (256, 256), (120, 130, 140)).save(buf, "JPEG")
img = base64.b64encode(buf.getvalue()).decode()
props = {k: "synthetic" for k in KEYS}
props.update(FNO_code="123 456", other="", act_AGR="synthetic", imageBase64=img)

def render(repl):
    doc = {"type": "FeatureCollection", "features": [{
        "type": "ObjectFeature",
        "geometry": {"type": "Point", "coordinates": ["<X>", "<Y>"]},
        "properties": props, "Glasses": []}]}
    s = json.dumps(doc, ensure_ascii=False, indent=2)
    for m, r in repl.items(): s = s.replace('"' + m + '"', r)
    return s.encode()

def run(repl):
    data = render(repl)
    try:
        doc = read_json(data)
        x, y = doc["features"][0]["geometry"]["coordinates"]
        parsed = (x, y, math.isfinite(x))
    except ValueError as e:
        parsed = ("ValueError", str(e)[:60])
    f = [(f.name, f.status) for f in geojson_findings(data, PROFILE, ground=False, glass_names=set())]
    return hashlib.sha256(data).hexdigest(), parsed, f

print("clean      ", run({"<X>": "12345.678", "<Y>": "6789.012"}))
print("x=1e400    ", run({"<X>": "1e400",      "<Y>": "6789.012"}))
print("x=Infinity ", run({"<X>": "Infinity",   "<Y>": "6789.012"}))
```

Observed output (pinned tree): `clean` → finite coordinate, findings `[imageBase64 pass, Glasses pass, schema pass]`;
`x=1e400` → `(inf, 6789.012, False)`, the **same** `[imageBase64 pass, Glasses pass, schema pass]` (no coordinate
finding); `x=Infinity` → `ValueError("Nonfinite value: Infinity")` and `[JSON fail]`.

## How it applies to this repository

- `src/twinqa/io.py:34-42` — `read_json` guards only the JSON constants, not numeric overflow.
- `src/twinqa/geojson.py:28-29` (`_number`), `:32-34` (`_decimals`), `:111-114` (coordinates), `:142-143` (`schema`
  pass) — the coordinate overflow escape path.
- `src/twinqa/geojson.py:66-69` — Glasses optical range check that happens to catch `inf`.
- `tools/qa/validate_package.py:110-111` (ZIP wiring), `:207-209` (single `.geojson`) — where the local V011 pass is
  produced and where the whole-report `passed` is computed.
- `standards/VPM_STANDARD.yaml:135` — the existing coordinate requirement is `coordinates.decimal_places: 3`
  (MSK-77); it is a precision rule, not a finiteness/bounds rule, and `_decimals` scores `inf` as 0 decimals.
- `standards/DELIVERY_VALIDATOR.yaml:85-90` — V011 is a `blocking` stage, so a V011 `pass` contributes to any
  whole-package `passed` calculation.
- `src/dt_ai/core/io.py:30-32`, `src/dt_ai/core/provenance.py:6`, `src/dt_ai/core/models.py:8`,
  `src/dt_ai/validate/bundle.py:36-55` — the separate AGR raw-dict path and its catch boundary.
- `docs/domain/areas/package.md:46-47` — PKG-24 (coordinate, 3 decimals, ≤50 cm offset) and PKG-25 (Glasses ranges).

## Proposed next tasks

1. **Finite-number guard for GeoJSON `coordinates` (and align Glasses optics)** — Add an explicit non-finite check so
   a coordinate that parsed to `inf`/`-inf`/`nan` yields a dedicated `fail` (or `review`) instead of silently reaching
   `schema: pass`. Scope: `src/twinqa/geojson.py` `coordinates` branch (and, for symmetry, the Glasses `_number` check
   so the finding is "non-finite" rather than "out of range"). Input → expected outcome:
   `coordinates: [1e400, 6789.012]` → `coordinates: fail` ("non-finite coordinate"); `[12345.678, 6789.012]` → unchanged
   (pass, no finding). Value **medium**, effort **S**. This adds a new finite-value/bounds rule and therefore
   **requires the user's decision** on which status (fail vs review) and on whether to also bound large-but-finite
   scientific-notation values (`_decimals` currently scores `1e20` as 0 decimals too).
2. **Parser-boundary rejection of numeric overflow in `read_json` (both `twinqa` and `dt_ai`)** — Wrap the default
   `parse_float` so that a decoded non-finite float raises `ValueError` exactly like `Infinity`/`NaN` do today, making
   the two paths consistent at the boundary. Input → expected outcome: `{"x": 1e400}` → `read_json` raises
   `ValueError("Nonfinite value ...")` → `JSON: fail`; `{"x": 1e308}` → accepted finite. Value **medium** (closes the
   delivery-path gap and removes the parser/contract asymmetry), effort **M**. This changes parser semantics for any
   caller and **requires the user's decision** (a finite-value policy at the JSON boundary).

## Open questions for the user

- Should the finite-value policy reject every non-finite float at the JSON parse boundary (making `1e400` behave exactly
  like the literal `Infinity`), or accept it at parse time and reject only where a field schema requires finiteness?
- For coordinates specifically, should a non-finite value be a hard `fail` or a `review`, given PKG-24's plan-position
  check (≤ 50 cm) is already a manual stage (V017)?
- Is a large-but-finite scientific-notation coordinate (e.g. `1e20`, which `_decimals` also scores as 0 decimals) in
  scope for the same guard, or is this card's exposure limited to non-finite values?

## Sources

- **Verified directly** (pinned tree `8d5c8987dbd46343176ca5af9d1791c864a86217`; `uv run python` probes; no pytest, no
  DCC): CPython `json` overflow behavior; `geojson_findings` on the clean OKS/Ground controls and every derivative; the
  single-`.geojson` and ZIP outer-validator calls; strict-JSON round-trip of the report; `dt_ai` parser vs pydantic
  contract probe. Input byte SHA-256: clean OKS `de902175cc8558ac140193707611253e716845ff41abf29be3627cb8b461b28f`,
  x=1e400 `f224918110e206c21c3294c71b2b236a6f24bed0540ecc3b47945d552cf15fa5`, y=-1e400
  `4b414be16dea8a02d400b5b21e3ba7e7f5d518fd77102147af07a5726344425b`, x=Infinity
  `de597da2fee6d40f059e01b8b412f07f88bd07057e897898db61fcaf7eab89ca`, x=4-dec
  `73d42aca6cdefb9a7ff911cd1dc44e7628967c3f86e792125975496460b14061`.
- **Source says, not rerun here:** the `1e400`-vs-`Infinity` observation originates in PR
  [#406](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/406) (`strict-reader-semantic-boundaries`).
