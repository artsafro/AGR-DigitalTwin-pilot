# GeoJSON Glasses: does `color_RGB` member order change the duplicate finding?

Report-only research. No production code, test, standard, hook, CI, data or dependency change. No pytest and no ZIP corpus. Synthetic documents only.

Pinned source: `4c863c1a4616f1812595536d0507f53034e9acfe` on `docs/research-geojson-glass-signature-key-order`. Confirmed by reading the worktree ref file (this task forbids invoking git) and by every CLI report's `code_commit`, which is `code_commit()` in `src/twinqa/report.py:283-290`.

## Summary

- Yes. Changing only the JSON member order inside `color_RGB` changes `Glasses duplicates`, even when the channel-to-value mappings are equal.
- The signature is `repr(sorted(props.items()))` (`src/twinqa/geojson.py:50-55`). `sorted` orders top-level optical keys only. The nested dict is copied into `repr` in insertion order.
- `read_json` keeps that order: `json.loads(..., object_pairs_hook=unique_pairs)` (`src/twinqa/io.py:25-42`). On this corpus, `dict` equality of the two glass objects was True for all six RGB permutations, and the duplicate fail appeared only for the permutation that repeated `Red, Green, Blue`.
- Reordering only the five outer optical keys does not change the finding: both materials stay in one group and `Glasses duplicates` fails. A real Blue change (140 to 141) and a real refraction change (1.5 to 1.6) stay ungrouped. Channel types stayed `int`; optical types stayed `float`.
- `glass_names=None` and the exact name census produced the same finding list on every row. The duplicate check is not behind the census.
- The single-file CLI does not pass `glass_names` (`tools/qa/validate_package.py:229`). It still exposes the order effect: identical order and outer reorder are V011 `fail`, exit 1; a Blue-Green-Red reorder is V011 `pass`, exit 2. `passed` was false on all six CLI runs. A V011 pass is not delivery acceptance.
- This report does not choose a duplicate-equivalence rule and does not canonicalize anything. [D016] says identical glasses are one material and does not say whether member order is part of identity.

## Findings

Evidence: **verified-by-run** means a bounded probe on this tree. **read-from-code** means the cited file, not a separate execution. Python dict insertion order and `json.loads` `object_pairs_hook` are the language contract (https://docs.python.org/3/library/stdtypes.html#mapping-types-dict and https://docs.python.org/3/library/json.html#json.loads); the probe measured both on CPython 3.14.7.

### 1. Signature uses nested `repr` order (read-from-code, verified-by-run)

`_glasses` groups materials by `repr(sorted(props.items()))`. The stored signature for the canonical glass is:

```text
[('color_RGB', {'Red': 120, 'Green': 130, 'Blue': 140}), ('metallicity', 0.84), ('refraction', 1.5), ('roughness', 0.1), ('transparency', 0.5)]
```

Outer keys are alphabetical. The `color_RGB` text follows JSON member order. A second material whose parsed key order was `Blue, Green, Red` produced a different signature string and its own group, while `props_a == props_b` and `color_RGB_a == color_RGB_b` were True. The oracle was dict equality, not string order.

The same function accepts any key order as a valid colour: `set(rgb) == {"Red", "Green", "Blue"}` (`src/twinqa/geojson.py:63-65`). None of the five reordered rows emitted `Glasses color_RGB`.

### 2. Measured grouping (verified-by-run)

First material is always `M_Test_K_1_MainGlass_1` with `color_RGB` order Red, Green, Blue and values 120 / 130 / 140. Second, when present, is `M_Test_K_1_MainGlass_2`. Optics unless noted: transparency 0.5, refraction 1.5, roughness 0.1, metallicity 0.84. Direct `_glasses` and public `geojson_findings` were run with `glass_names=None` and with the exact census (`{M1}` or `{M1, M2}`). Those two modes matched on every row. Public findings below are the `glass_names=None` list; the census list was identical.

| case | second `color_RGB` order | mapping `==` | groups | `_glasses` / public glasses finding | schema pass |
|---|---|---|---|---|---|
| one_glass | (none) | n/a | M1 alone | `Glasses` pass, `1 glass material(s)` | yes |
| rgb_Red_Green_Blue | Red, Green, Blue | True | M1+M2 | `Glasses duplicates` fail, `M1, M2` | no |
| rgb_Red_Blue_Green | Red, Blue, Green | True | two groups | `Glasses` pass, `2 glass material(s)` | yes |
| rgb_Green_Red_Blue | Green, Red, Blue | True | two groups | `Glasses` pass, `2 glass material(s)` | yes |
| rgb_Green_Blue_Red | Green, Blue, Red | True | two groups | `Glasses` pass, `2 glass material(s)` | yes |
| rgb_Blue_Red_Green | Blue, Red, Green | True | two groups | `Glasses` pass, `2 glass material(s)` | yes |
| rgb_Blue_Green_Red | Blue, Green, Red | True | two groups | `Glasses` pass, `2 glass material(s)` | yes |
| outer_reorder | Red, Green, Blue; outer keys reversed | True | M1+M2 | `Glasses duplicates` fail, `M1, M2` | no |
| blue_141 | Red, Green, Blue; Blue 141 | False | two groups | `Glasses` pass, `2 glass material(s)` | yes |
| refraction_1_6 | Red, Green, Blue; refraction 1.6 | False | two groups | `Glasses` pass, `2 glass material(s)` | yes |

`schema` pass is appended only when every earlier finding passed (`src/twinqa/geojson.py:142-143`). The duplicate rows also have `imageBase64` pass and no `schema` finding. The pass rows are `imageBase64` pass, `Glasses` pass, `schema` pass. No `Glasses material` finding occurred: both names were in the census, and `None` skips that check (`src/twinqa/geojson.py:47-48, 57-58`).

So: only the identical member order groups. The other five RGB permutations do not. Outer optical-key order does not split the group. A changed Blue channel or a changed refraction does not group.

### 3. Caller exposure is the CLI path, not only the helper (verified-by-run and read-from-code)

`geojson_findings(..., glass_names=None)` is the default (`src/twinqa/geojson.py:86`). Production callers that were read:

- `tools/qa/validate_package.py:229` — single `.geojson`. Measured below.
- `tools/qa/validate_package.py:122` — VPM ZIP. Same call, no `glass_names`. Not executed (no ZIP corpus).
- `tools/sintez_parity.py:206` — `geojson_findings(data["geojson"], profile, False)`. No `glass_names`. Not executed.

The census is therefore unwired on the package path (PKG-25 already says this). That does not hide the order effect. The signature runs for every glass object.

Command, timeout 120s, from the worktree: `uv run python tools/qa/validate_package.py <file> --profile vpm --json`. Stderr empty. Stdout parsed with `parse_constant` rejecting non-finite tokens and re-serialized with `allow_nan=False`. Input sha256 unchanged before/after on 6 of 6. `code_commit` was the pinned SHA on 6 of 6. `passed` false on 6 of 6.

| case | file sha256 | V011 | passed | report exit | process rc |
|---|---|---|---|---|---|
| one_glass | `13f63c69ae265196beda87d87b22d420ee243f27654413722d215bfde22f3257` | pass | false | 2 | 2 |
| rgb_Red_Green_Blue | `3c37d50ccb3433115cf9a3c9a7a896c970ff4d72d7a33de0da08c960d7645a71` | fail | false | 1 | 1 |
| rgb_Blue_Green_Red | `41bbfb2b2878782eb90185301ebaa4521ef4ce168d96faeae5592935b1e25e98` | pass | false | 2 | 2 |
| outer_reorder | `630de2ff28f5cf34066993dd250d86a182ce436a1cb9b554e7b7e396a0b18f9f` | fail | false | 1 | 1 |
| blue_141 | `3b5d15d866e8ba6facd4cd09ec121c6d6879e6483f042b494d9cf772195f90e2` | pass | false | 2 | 2 |
| refraction_1_6 | `52fc42aab6bb646925c08dfd0b0f52dcef2b5d339fecbad2c4412c0d4040fe15` | pass | false | 2 | 2 |

V011 findings on the CLI matched the public `geojson_findings` list. Exit 2 is the single-file shape: V011 can pass while other blocking stages have no findings and stay `not_run` (`src/twinqa/report.py:171-174, 226-236`; `tools/qa/validate_package.py:228-230`). Exit 1 is the duplicate fail. Neither exit is user acceptance (`docs/domain/areas/package.md` PKG-25; `passed=true` is a separate gate).

API-only file hashes (no CLI): `rgb_Red_Blue_Green` `86d8fb180f607bc96d7499e5ae51709cfbf7f250d174dafadf8efc6011176bf9`; `rgb_Green_Red_Blue` `9ed938e50c27aaa7e2dd14bce4fc44a029491fae7e42845259056afeb69b3e63`; `rgb_Green_Blue_Red` `de59d9f497166fa350151256db7e7e39dde2858144c9cf3a0147edcc0e749ae0`; `rgb_Blue_Red_Green` `690069dcc410ee0cf210997b79f9d70026d8bf207b27575acdf8dd83847c8003`. Each file is 3051 bytes except `one_glass` (2906).

### 4. What the existing tests pin (read-from-code)

`tests/qa/test_validator.py:166-175` treats two `dict(GLASS)` copies as a duplicate fail. `dict(GLASS)` keeps the original insertion order, so that row cannot see a member-order split. `tests/qa/test_geojson_glasses_contract.py:32-33` excludes "duplicate-glass equivalence policy" on purpose. Its distinct-refraction row (`refraction = 2.0`) only avoids a duplicate finding; it does not permute `color_RGB`.

[D016] / conflict C13 (`docs/decisions.md`, `docs/domain/conflicts.md` item 13): `"Glasses": []` or one object keyed by material name; identical glasses must be one material. No sentence defines identical under object-member order.

### 5. Provenance and corpus (verified-by-run)

- OS: Windows-11-10.0.26200-SP0. `uv` 0.8.3. CPython 3.14.7 (MSC v.1944 64-bit). Pillow 12.3.0.
- Probe and corpus: `C:/x/t_7be53ea9/probe_glass_order.py`, `C:/x/t_7be53ea9/corpus/*.geojson`, `C:/x/t_7be53ea9/results.json`. Not in the repo.
- JPEG: `Image.new("RGB", (256, 256), (120, 130, 140)).save(..., "JPEG")`. 1650 bytes. sha256 `2116f6e3c323954039d16f9ee4f542fdfec43e5881fde35c0759cd1090b938c9`. The same base64 is in every document. File `C:/x/t_7be53ea9/clean256.jpg`.
- Document shape: FeatureCollection / ObjectFeature / Point `[12345.678, 6789.012]`, property keys from `standards/VPM_STANDARD.yaml` `geojson.properties_keys` in that order, `FNO_code` `123 456`, `other` and `act_AGR` empty, other strings `synthetic`. Marked synthetic. Not a real object.
- Number spellings were fixed (`120`, `0.5`, `1.5`, `0.1`, `0.84`, and `141` / `1.6` only on the distinct rows). Parsed RGB values were `int`; parsed optics were `float` on both materials.

### Compact reproducer

Run from the worktree with `uv run python`. Needs Pillow. No pytest.

```python
import base64, json
from io import BytesIO
import sys
sys.path.insert(0, "src")
from PIL import Image
from twinqa.geojson import _glasses, geojson_findings
from twinqa.io import read_json
from twinqa.profiles import load_profiles

profile = load_profiles().vpm
buf = BytesIO()
Image.new("RGB", (256, 256), (120, 130, 140)).save(buf, "JPEG")
image = base64.b64encode(buf.getvalue()).decode("ascii")
M1, M2 = "M_Test_K_1_MainGlass_1", "M_Test_K_1_MainGlass_2"

def glass(rgb_order, outer=None, blue="140", refraction="1.5"):
    vals = {"Red": "120", "Green": "130", "Blue": blue}
    rgb = "{" + ",".join(f'"{k}":{vals[k]}' for k in rgb_order) + "}"
    fields = {"color_RGB": rgb, "transparency": "0.5", "refraction": refraction,
              "roughness": "0.1", "metallicity": "0.84"}
    outer = outer or ["color_RGB", "transparency", "refraction", "roughness", "metallicity"]
    return "{" + ",".join(f'"{k}":{fields[k]}' for k in outer) + "}"

def document(second_glass):
    keys = profile["geojson"]["properties_keys"]
    props = []
    for key in keys:
        if key == "imageBase64":
            val = json.dumps(image)
        elif key == "FNO_code":
            val = '"123 456"'
        elif key in ("other", "act_AGR"):
            val = '""'
        else:
            val = '"synthetic"'
        props.append(f'"{key}":{val}')
    glasses = '[{"' + M1 + '":' + glass(["Red", "Green", "Blue"])
    if second_glass is not None:
        glasses += ',"' + M2 + '":' + second_glass
    glasses += "}]"
    return (
        '{"type":"FeatureCollection","features":[{"type":"ObjectFeature",'
        '"geometry":{"type":"Point","coordinates":[12345.678,6789.012]},'
        '"properties":{' + ",".join(props) + '},"Glasses":' + glasses + "}]}"
    ).encode()

def show(label, raw):
    doc = read_json(raw)
    obj = doc["features"][0]["Glasses"][0]
    names = list(obj)
    equal = None if len(names) < 2 else obj[names[0]] == obj[names[1]]
    groups = {}
    for material, props in obj.items():
        groups.setdefault(repr(sorted(props.items())), []).append(material)
    findings = [(f.name, f.status, f.observed) for f in geojson_findings(raw, profile, False, None)]
    print(label, "equal", equal, "groups", list(groups.values()), findings)

show("identical", document(glass(["Red", "Green", "Blue"])))
show("bgr", document(glass(["Blue", "Green", "Red"])))
show("outer", document(glass(["Red", "Green", "Blue"],
    outer=["metallicity", "roughness", "refraction", "transparency", "color_RGB"])))
show("blue141", document(glass(["Red", "Green", "Blue"], blue="141")))
show("refr1.6", document(glass(["Red", "Green", "Blue"], refraction="1.6")))
direct = _glasses(read_json(document(glass(["Blue", "Green", "Red"])))["features"][0]["Glasses"], {M1, M2})
print("direct census", [(f.name, f.status) for f in direct])
```

Measured on this tree: `identical` and `outer` print one group and `Glasses duplicates` fail; `bgr`, `blue141` and `refr1.6` print two groups and `Glasses` pass plus `schema` pass. `direct census` for `bgr` is `Glasses` pass. `equal` is True for `identical`, `bgr` and `outer`, and False for `blue141` and `refr1.6`.

## How it applies to this repository

- `src/twinqa/geojson.py:50-55` is the whole duplicate rule. `:63-65` already treats `color_RGB` keys as an unordered set for the range check. `:142-143` withholds `schema` pass when the duplicate finding fires.
- `src/twinqa/io.py:25-42` is why JSON member order reaches that `repr`. A parser that sorted keys would hide this; this parser does not.
- `tools/qa/validate_package.py:122` and `:229` are the package callers. Both omit `glass_names`. The single-file path was measured; the ZIP path is the same call and was not run.
- PKG-25 (`docs/domain/areas/package.md`) records the census as unwired and points V011 at `_glasses`. It does not mention member order. The duplicate examples in `tests/qa/test_validator.py:170` and the exclusion in `tests/qa/test_geojson_glasses_contract.py:32-33` leave this gap untested.
- [D016] remains the rule that identical glasses are one material. Applying it to key order is a user choice, not a code default this report can pick.

## Proposed next tasks

### Record the duplicate-identity rule, then test that one rule

One paragraph: the user chooses whether two glasses are identical when their parsed mappings compare equal, or only when `color_RGB` member order also matches. Concrete pair, second material only: `color_RGB` members `Blue, Green, Red` with Red 120, Green 130, Blue 140, other optical keys and values unchanged. Mapping equality is True today. Current output: no `Glasses duplicates`; `Glasses` pass `2 glass material(s)`; `schema` pass; CLI V011 `pass`, `passed` false, exit 2. If the user chooses mapping equality, that same file must become `Glasses duplicates` fail with observed `M_Test_K_1_MainGlass_1, M_Test_K_1_MainGlass_2`, no `schema` pass, V011 `fail`, exit 1. The outer-key-reversed file must stay a duplicate fail under either choice. `Blue` 141 must stay two groups and V011 `pass` / exit 2 under either choice. Put the chosen triple in `tests/qa/test_geojson_glasses_contract.py`, which already names this exclusion and does not cover it. Value/effort: M value, S effort. Advances #149.

### If mapping equality is the rule, stop using nested `repr` as the signature

One paragraph: only after that choice, replace the signature so nested objects compare by key and value, not by `repr` order. Do not invent a wider policy for unknown properties, numeric coercion, or non-finite values; those stayed out of this corpus. Input to expected output: the Blue-Green-Red file above goes from today's V011 pass to `Glasses duplicates` fail; `outer_reorder` stays fail with the same observed pair; `blue_141` stays `Glasses` pass and V011 pass. Value/effort: M value, S effort. Advances #149.

## Open questions for the user

- Are two glasses identical when Red, Green and Blue hold the same integers, regardless of JSON member order?
- Should outer optical-key order stay insignificant (it already is, because of `sorted`) while `color_RGB` order stays significant (it is, because of `repr`)?
- Is a V011 pass on a reordered pair acceptable until that choice, given the package CLI already returns it?
