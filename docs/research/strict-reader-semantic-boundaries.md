# Strict reader semantic boundaries

## Summary

- Report-only research; `delivery_passed=false`; no implementation or policy decision.
- Repository baseline: `6e9f3faa22d0e05889c01e46ce15805ed9168a99`; CPython 3.14.7 / PyYAML 6.0.3.
- Frozen synthetic corpus: six families, 21 inputs, 42 parser/input observations; 7 inputs differ.
- AGR JSON autodetects UTF-16/32 and consumes a UTF-8 byte BOM; QA's explicit UTF-8 decode does not.
- Both JSON readers reject explicit nonfinite tokens but return positive infinity for `1e400`.
- AGR YAML accepts nonfinite floats; QA YAML rejects them, including float-notation overflow.
- Both reject nested duplicates and merge-key overrides after flattening; non-overlapping merges work.
- Current standards loading already uses QA in both packages; no real nonfinite caller exposure was established.
- Neither reader can replace the other unchanged; preserve independent checker verdicts and diagnostics.

## Findings (with sources)

### Evidence and source pins

**Observed** below means a standalone parser invocation, not a pytest result or delivery verdict.
**Static** means source inspection only. All repository `path:Lx-Ly` references in this report
are pinned to commit **6e9f3faa22d0e05889c01e46ce15805ed9168a99** in
[artsafro/AGR-DigitalTwin-pilot](https://github.com/artsafro/AGR-DigitalTwin-pilot/tree/6e9f3faa22d0e05889c01e46ce15805ed9168a99),
not the upstream repository. Main implementation/test anchors:

- [AGR reader, L21-L48](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/core/io.py#L21-L48).
- [QA reader, L25-L66](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/twinqa/io.py#L25-L66).
- [Contract tests, L13-L84](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/tests/contracts/test_contracts.py#L13-L84).
- [Standards tests, L30-L79](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/tests/qa/test_standards.py#L30-L79).

Primary external sources (fetched with curl / urllib in this session):

- **P1:** [Python 3.14 json documentation](https://docs.python.org/3.14/library/json.html#json.loads),
  including [`JSONDecoder`](https://docs.python.org/3.14/library/json.html#json.JSONDecoder),
  [infinite/NaN values](https://docs.python.org/3.14/library/json.html#infinite-and-nan-number-values)
  and [repeated names](https://docs.python.org/3.14/library/json.html#repeated-names-within-an-object).
  `loads` supports UTF-8/16/32 bytes; `parse_float` defaults to `float`; `parse_constant`
  handles only the named tokens. Default last-key-wins is overridden by these helpers.
- **P2:** CPython **823f0323ee6ec1402088b73bce1a38473cac36dc** (dereferenced v3.14.7 tag):
  [`Lib/json/__init__.py`, L248-L275, L339-L365](https://github.com/python/cpython/blob/823f0323ee6ec1402088b73bce1a38473cac36dc/Lib/json/__init__.py#L248-L365),
  [`decoder.py`, L327-L337](https://github.com/python/cpython/blob/823f0323ee6ec1402088b73bce1a38473cac36dc/Lib/json/decoder.py#L327-L337),
  [`scanner.py`, L48-L61](https://github.com/python/cpython/blob/823f0323ee6ec1402088b73bce1a38473cac36dc/Lib/json/scanner.py#L48-L61),
  and [`Modules/_json.c`, L884-L1015](https://github.com/python/cpython/blob/823f0323ee6ec1402088b73bce1a38473cac36dc/Modules/_json.c#L884-L1015).
- **P3:** [PyYAML documentation](https://pyyaml.org/wiki/PyYAMLDocumentation), sections
  **Aliases**, **YAML tags and Python types**, **Constructors, representers, resolvers**, and
  **Reference / Loading YAML**. Safe loading restricts object construction to standard tags;
  that is not a promise of duplicate rejection or finite floats.
- **P4:** PyYAML **49790e73684bebad1df05ef8d828fa12f685bffb** (6.0.3):
  [`constructor.py`, L180-L218](https://github.com/yaml/pyyaml/blob/49790e73684bebad1df05ef8d828fa12f685bffb/lib/yaml/constructor.py#L180-L218),
  [L270-L292](https://github.com/yaml/pyyaml/blob/49790e73684bebad1df05ef8d828fa12f685bffb/lib/yaml/constructor.py#L270-L292),
  [`resolver.py`, L177-L184](https://github.com/yaml/pyyaml/blob/49790e73684bebad1df05ef8d828fa12f685bffb/lib/yaml/resolver.py#L177-L184).
- **P5:** [YAML merge-key working draft](https://yaml.org/type/merge.html), definition and override example:
  insert inherited pairs unless the key already exists; explicit overrides are intentional syntax
  in that draft. This is not a decision that this repository must accept merges, or a claim that
  merge is part of every YAML version/schema.

### Observed parser results

Six families: valid UTF-8 JSON (J01-J02); nested duplicates (J03/Y01); named nonfinite
values (J04-J06/Y02-Y04); exponent notation/overflow (J07/Y05-Y06); encoding/BOM/error
contrasts (J08-J12); ordinary YAML/anchor/merge controls (Y07-Y09).

`AGR` = `dt_ai.core.io`; `QA` = `twinqa.io`. Inputs are the exact escaped literals in the
frozen script below (YAML file bytes are exactly `text.encode('utf-8')`, with LF).
Results below are Python representations, **not JSON**. Float classification uses
`math.isfinite`/`math.isnan` recursively, including mapping keys. `none` means no float
objects, not "a finite float"; all numbers in those successful rows are integers.

Exception abbreviations expand to these **actual types and complete messages**:

| Code | Type | Message |
|---|---|---|
| D | `ValueError` | `Duplicate key: a` |
| N | `ValueError` | `Nonfinite value: NaN` |
| I | `ValueError` | `Nonfinite value: Infinity` |
| MI | `ValueError` | `Nonfinite value: -Infinity` |
| U0 | `UnicodeDecodeError` | `'utf-8' codec can't decode byte 0xff in position 0: invalid start byte` |
| U6 | `UnicodeDecodeError` | `'utf-8' codec can't decode byte 0xff in position 6: invalid start byte` |
| B | `JSONDecodeError` | `Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)` |
| YN | `ValueError` | `Nonfinite value in YAML: .nan` |
| YI | `ValueError` | `Nonfinite value in YAML: .inf` |
| YMI | `ValueError` | `Nonfinite value in YAML: -.inf` |
| YO | `ValueError` | `Nonfinite value in YAML: 1.0e+400` |

| Input | AGR result / float status | QA result / float status |
|---|---|---|
| J01 UTF-8 bytes | `{'s': '\xe9', 'n': 1.25}` / n finite | same / n finite |
| J02 Unicode string | `{'s': '\xe9', 'n': 1.25}` / n finite | same / n finite |
| J03 nested duplicate | D | D |
| J04 NaN token | N | N |
| J05 Infinity token | I | I |
| J06 -Infinity token | MI | MI |
| J07 exponent overflow | `{'n': inf}` / n **+Infinity** | same / n **+Infinity** |
| J08 UTF-16LE BOM bytes | `{'n': 1}` / none | U0 |
| J09 UTF-32LE BOM bytes | `{'n': 1}` / none | U0 |
| J10 malformed UTF-8 | U6 | U6 |
| J11 UTF-8 BOM bytes | `{'n': 1}` / none | B |
| J12 BOM in string | B | B |
| Y01 nested duplicate | D | D |
| Y02 .nan | `{'n': nan}` / n **NaN** | YN |
| Y03 .inf | `{'n': inf}` / n **+Infinity** | YI |
| Y04 -.inf | `{'n': -inf}` / n **-Infinity** | YMI |
| Y05 1e400 | `{'n': '1e400'}` / none, **string** | same / none, **string** |
| Y06 1.0e+400 | `{'n': inf}` / n **+Infinity** | YO |
| Y07 ordinary mapping | `{'outer': {'s': 'ok', 'n': 1.25}}` / outer.n finite | same / outer.n finite |
| Y08 merge override | D | D |
| Y09 merge without overlap | `{'base': {'a': 1}, 'obj': {'a': 1, 'c': 2}}` / none | same / none |

Totals: **42/42 observations recorded**, 19 successful returns and 23 exceptions.
AGR: 13 returns / 8 exceptions; QA: 6 returns / 15 exceptions. Six successful returns
contain nonfinite floats (AGR 5, QA 1). Agreement on 14/21 inputs; differences on
7/21 (J08, J09, J11, Y02, Y03, Y04, Y06). Agreement is not validation success.
Corpus identity: `sha256(ascii(CORPUS).encode('ascii'))` =
`f93270a26f83c2c26db4574e4db5de273dfcacdc4361f102b26472847874630e`.

### Why these boundaries exist

1. **JSON bytes versus text (P1/P2; AGR L30-L32, QA L38-L42).** AGR passes bytes
   directly to `json.loads`: `detect_encoding` checks UTF-32 BOM before UTF-16,
   then UTF-8 BOM, then NUL patterns; decoding uses `surrogatepass`. QA decodes
   `bytes` with strict `utf-8` first. Consequently J08/J09 fail before JSON parsing
   in QA; J11 becomes a leading U+FEFF string, which `loads` rejects. A leading
   U+FEFF already in a string fails in both. J10 is malformed in both. The broader
   stdlib byte contract is allowed legacy behavior, not proof of an AGR encoding bug.
   Only LE BOMs and the particular malformed byte are empirically covered here;
   BE, BOM-less autodetection, surrogate edge cases and bytearray are source-only
   or untested (annotations advertise bytes/string; QA explicitly decodes only bytes).
2. **Constants are not all nonfinite results (P1/P2; both JSON functions).** Both
   set `object_pairs_hook` and `parse_constant`, but neither sets `parse_float` or
   recursively checks parsed values. Named NaN/Infinity tokens call the rejecting
   callback; `1e400` matches ordinary number syntax, then default float conversion
   overflows to infinity. Python scanner L48-L61 separates those paths; the C
   scanner calls `parse_constant` at L897 and `PyFloat_FromString` at L1009.
   JSONDecoder's `strict` flag concerns string control characters, not finite
   numeric bounds. Thus explicit `Infinity` and finite-notation overflow are
   observably different, even though their potential float result is the same.
   QA's module-level "non-finite numbers are errors" description is too broad for
   JSON (a proven reader/documentation mismatch, not a demonstrated delivery defect).
3. **YAML resolution precedes construction (P3/P4; AGR L35-L48, QA L45-L66).**
   Both subclass `SafeLoader`, but only QA registers `_float` for the YAML float tag.
   SafeConstructor normalizes signs/case, returns its NaN/infinity constants, or
   invokes `float(value)`. QA checks the resulting float, catching overflow as well
   as explicit tokens. The implicit float resolver requires a decimal point for the
   tested exponent form and a signed exponent: `1e400` is a string here, while
   `1.0e+400` is a float that overflows. A numeric-looking string is not evidence of
   a finite numeric value or schema acceptance. Neither parser enforces a schema.
4. **Duplicate keys after flattening (P4/P5; both `_mapping` functions).**
   `flatten_mapping` removes `<<`, obtains inherited node pairs and prepends them
   (`node.value = merge + node.value`). `unique_pairs` then sees inherited `a` and
   explicit `a`, raising D in Y08. A standard SafeLoader ordinarily constructs a
   dict in insertion order, allowing the explicit value to replace the inherited
   value; these two helpers intentionally impose a stricter effective-map uniqueness
   contract. Y09 proves merges/anchors are not categorically forbidden. Nested
   duplicates fail because the registered mapping constructor runs recursively;
   JSON's pairs hook similarly applies to nested objects. No key path or YAML
   line/column is added to their ValueError diagnostics. No new merge policy follows.

### Frozen corpus v1 and self-contained reproduction

Run from the repository root with Python and the pinned PyYAML 6.0.3 available:
`python -B -` with the following script as stdin. No pytest, uv sync or DCC is needed.
The script imports each source module by file path (no package initialization), writes YAML
only to a unique temporary directory under this worktree's `tmp/`, then removes that directory.
It does not write JSON fixtures, standards, data, source, or bytecode. Every exact input is
printed with `ascii()` (escaped Python literal); BOM payloads are fixed little-endian bytes.
The corpus tuple and its SHA-256 are printed before the first parse. Results use Python
representations plus a recursive float classification, not bare JSON nonfinite literals.

```python
import hashlib
import importlib.util
import math
import pathlib
import platform
import sys
import tempfile
try:
    import yaml
except ModuleNotFoundError:
    # Optional read-only bootstrap: pinned source, verified in memory, no install.
    import importlib.abc
    import io
    import tarfile
    import urllib.request
    url = ("https://files.pythonhosted.org/packages/05/8e/"
           "961c0007c59b8dd7729d542c61a4d537767a59645b82a0b521206e1e25c2/"
           "pyyaml-6.0.3.tar.gz")
    blob = urllib.request.urlopen(url, timeout=30).read()
    assert hashlib.sha256(blob).hexdigest() == (
        "d76623373421df22fb4cf8817020cbb7ef15c725b9d5e45f17e189bfc384190f")
    with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
        sources = {m.name.split("/lib/", 1)[1]: archive.extractfile(m).read()
                   for m in archive.getmembers() if "/lib/yaml/" in m.name
                   and m.name.endswith(".py")}
    class MemoryYaml(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, fullname, path=None, target=None):
            key = fullname.replace(".", "/")
            key += "/__init__.py" if fullname == "yaml" else ".py"
            if key in sources:
                return importlib.util.spec_from_loader(
                    fullname, self, is_package=fullname == "yaml")
        def create_module(self, spec):
            return None
        def exec_module(self, module):
            key = module.__name__.replace(".", "/")
            key += "/__init__.py" if module.__name__ == "yaml" else ".py"
            module.__file__ = "<pinned-pyyaml>/" + key
            exec(compile(sources[key], module.__file__, "exec"), module.__dict__)
    sys.meta_path.insert(0, MemoryYaml())
    import yaml

# Frozen corpus v1: six families, expanded to 21 exact inputs.
CORPUS = (
    ("J01", "json", b'{"s":"\xc3\xa9","n":1.25}'),
    ("J02", "json", '{"s":"\u00e9","n":1.25}'),
    ("J03", "json", '{"outer":{"a":1,"a":2}}'),
    ("J04", "json", '{"n":NaN}'),
    ("J05", "json", '{"n":Infinity}'),
    ("J06", "json", '{"n":-Infinity}'),
    ("J07", "json", '{"n":1e400}'),
    ("J08", "json", b'\xff\xfe{\x00"\x00n\x00"\x00:\x001\x00}\x00'),
    ("J09", "json", b'\xff\xfe\x00\x00{\x00\x00\x00"\x00\x00\x00n\x00\x00\x00"\x00\x00\x00:\x00\x00\x001\x00\x00\x00}\x00\x00\x00'),
    ("J10", "json", b'{"s":"\xff"}'),
    ("J11", "json", b'\xef\xbb\xbf{"n":1}'),
    ("J12", "json", '\ufeff{"n":1}'),
    ("Y01", "yaml", 'outer:\n  a: 1\n  a: 2\n'),
    ("Y02", "yaml", 'n: .nan\n'),
    ("Y03", "yaml", 'n: .inf\n'),
    ("Y04", "yaml", 'n: -.inf\n'),
    ("Y05", "yaml", 'n: 1e400\n'),
    ("Y06", "yaml", 'n: 1.0e+400\n'),
    ("Y07", "yaml", 'outer:\n  s: ok\n  n: 1.25\n'),
    ("Y08", "yaml", 'base: &b {a: 1}\nobj:\n  <<: *b\n  a: 2\n'),
    ("Y09", "yaml", 'base: &b {a: 1}\nobj:\n  <<: *b\n  c: 2\n'),
)
print("runtime", platform.python_version(), "PyYAML", yaml.__version__)
print("corpus-sha256", hashlib.sha256(ascii(CORPUS).encode("ascii")).hexdigest())
for row in CORPUS:
    print("input", row[0], row[1], ascii(row[2]))

modules = {}
for name, file in (("AGR", "src/dt_ai/core/io.py"), ("QA", "src/twinqa/io.py")):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    modules[name] = module

def floats(value, path="$"):
    if isinstance(value, float):
        state = "finite" if math.isfinite(value) else (
            "NaN" if math.isnan(value) else ("+Infinity" if value > 0 else "-Infinity"))
        return [(path, state)]
    if isinstance(value, dict):
        return [item for k, v in value.items() for item in
                floats(k, path + ".<key>") + floats(v, path + "[" + repr(k) + "]")]
    if isinstance(value, (list, tuple)):
        return [item for i, v in enumerate(value) for item in floats(v, path + f"[{i}]")]
    return []

scratch = pathlib.Path("tmp")
scratch.mkdir(exist_ok=True)
count = 0
with tempfile.TemporaryDirectory(prefix="strict-readers-", dir=scratch) as tmp:
    for id_, kind, raw in CORPUS:
        path = pathlib.Path(tmp) / (id_ + ".yaml")
        if kind == "yaml":
            path.write_bytes(raw.encode("utf-8"))  # exactly LF, independent of OS
        for name, module in modules.items():
            try:
                result = module.read_json(raw) if kind == "json" else module.read_yaml(path)
                print(id_, name, "OK", ascii(result), "floats=", ascii(floats(result)))
            except Exception as exc:
                print(id_, name, type(exc).__name__, ascii(str(exc)))
            count += 1
print("observations", count)
```

## How it applies to this repository (file paths)

### Static caller inventory

Inventory method (read-only, tracked Python files at the pinned baseline):
`git grep -n -E '(from (dt_ai\\.core|twinqa)\\.io import|import (dt_ai\\.core|twinqa)\\.io|from \\.io import)' -- '*.py'`,
plus `rg -n 'read_json|read_yaml|UniqueLoader|unique_pairs' src tests tools --glob '*.py'`
and inspection of bindings/call sites. No dynamic import/plugin reachability claim.
All discovered direct calls use bytes read from paths or archive members, except AGR's
contract test string inputs. AGR `read_yaml` has only the contract duplicate test as a
current direct caller; the standards test uses QA's reader.

| Reader | Current direct consumers and input role (pinned line numbers) |
|---|---|
| AGR JSON | `src/dt_ai/cli/main.py:L120,L132-L137,L183-L184,L199-L201,L217-L222,L239-L240`: job manifests, source objects/dumps/modules, spec/report pairs, tolerances, material registries. Some use Pydantic; others pass ordinary dicts onward. |
| AGR JSON | `src/dt_ai/core/build.py:L79,L110`: BuildJob validation and previous build manifest. |
| AGR JSON | `src/dt_ai/validate/bundle.py:L38-L48`: development ZIP manifest, BuildJob, layout; hashes/contracts checked, decode failures become C001 fail at L52-L56. |
| AGR JSON | `src/dt_ai/core/run_record.py:L65,L118`: writer readback and existing run ledger; generated writes use `allow_nan=False`. |
| AGR JSON | `src/dt_ai/core/run_inspection.py:L53-L54,L147`: ledger/manifest dicts and AdapterReport validation. |
| AGR JSON | `src/dt_ai/parts/readers/fbx.py:L370`: structure facts; decode errors wrapped as StructureError at L371-L372; conversion/model/schema checks follow. |
| AGR JSON | `tools/adapter_report.py:L18`; `tools/check_body_shell_readback.py:L15-L16,L29`: adapter/report validation and before/readback geometry. |
| AGR JSON | `tools/run_body_shell.py:L18,L26,L58`; `tools/run_exterior.py:L17,L23`: configs, profiles JSON/source JSON and saved model readback. |
| QA JSON + YAML | `src/twinqa/profiles.py:L68,L75,L89`: source lock JSON, three YAML profiles, traceability JSON; source/hash/conflict/traceability checks at L70-L107. |
| QA JSON | `src/twinqa/geojson.py:L89`: delivery GeoJSON bytes. UnicodeDecodeError -> UTF-8 fail (L90-L91); ValueError -> JSON fail (L92-L93). |
| QA JSON | `tools/qa/check_geometry.py:L37-L41`: Spec, tolerances, optional frame, model/etalon dumps. |
| QA JSON | `tools/qa/run_benchmark.py:L65,L74,L76,L96`: object/tolerance/material definitions and etalon/model dumps. |
| QA JSON | `tools/qa/run_from_source.py:L55-L56,L79`: dump/modules/object/tolerances and model readback. |
| Tests, AGR JSON | `tests/conftest.py:L16`; `tests/contracts/test_contracts.py:L15,L67,L80`; `tests/integration/test_pipeline.py:L71,L103,L157,L164`: fixture/contract/traceability and generated artifact checks. |
| Tests, AGR YAML | `tests/contracts/test_contracts.py:L61`: duplicate fixture only. |
| Tests, QA JSON/YAML | `tests/qa/test_standards.py:L64-L71`: duplicates and NaN/.nan. |

This is **15 non-test consumer files** with direct reader calls and **4 test/fixture
consumer files**, not 19 runtime entry points. Imports of other IO utilities only:
`src/dt_ai/drawing/index.py:L5`, `src/dt_ai/spec/mesh.py:L181`,
`tools/harness_status.py:L8`, `tools/qa/validate_package.py:L22`,
`tests/integration/test_pdf_index.py:L3`, `tests/test_run_inspection.py:L8`.
No outside calls of these modules' `unique_pairs`/`UniqueLoader` were found.
Same-named helpers in `src/dt_ai/procedure.py:L100-L118`, materials/flora,
flora_catalogue, library/maf tools, herdr, and `read_jsonl` in evals are separate
implementations, not callers of the two readers; they are not consolidation scope.

### Tested contracts versus untested assumptions

The two requested files were **read, not executed**: 8 test functions in
`tests/contracts/test_contracts.py` (14 cases by static expansion of its seven-way
mutation parametrization), 6 functions/cases in `tests/qa/test_standards.py`.
These are static counts, **not pytest collected/passed counts**.

- AGR's parser-specific assertions cover a top-level YAML duplicate, a top-level JSON
  duplicate, and the JSON NaN token. Its model `nonfinite` mutation inserts Python
  `float('nan')` directly into BuildJob validation, bypassing JSON entirely; it does
  not test `1e400` or YAML nonfinite handling.
- QA's combined parser test covers JSON bytes duplicate/NaN and YAML duplicate/.nan.
  It does not cover UTF-16/32, BOMs, JSON overflow, YAML infinity/overflow or merges.
- Both files also cover surrounding contracts: fixture/model validation and material
  proposals, profile locks/source evidence/traceability, optional PDF verification,
  conflict-field annotation checks and size limits. Those are not reader equivalence
  assertions, and their threshold guarantees are not re-tested in this research.
- The standalone corpus extends observation to nested duplicates, all three named JSON
  constants, encoding contrasts, YAML float resolution and merges. It does not establish
  a universal "finite-only" guarantee. No assertions were weakened and no regression
  test was added.

### Where consolidation would change behavior

| Replacement | Behavior change established by this corpus |
|---|---|
| Use AGR reader everywhere | QA callers would accept UTF-16/32 BOM bytes and UTF-8 byte BOMs; QA YAML would cease rejecting .nan/.inf/-.inf and 1.0e+400. GeoJSON's explicit UTF-8 failure path would be bypassed for J08/J09 (source trace, not a full valid GeoJSON run). |
| Use QA reader everywhere | AGR byte callers would reject previously accepted encodings/BOMs; AGR YAML's library API would reject four previously accepted float values, though current repository standards already use QA. |
| Extract duplicate-pair logic only | Current duplicate text and merge flattening order must remain explicit contracts; ordinary SafeLoader last-key-wins would change Y01/Y08. This isolated similarity is not evidence that entire readers are interchangeable. |
| Add finite checking during consolidation | Changes both JSON readers on J07; that is a semantic change beyond deduplication, requiring its own scope/decision. |

There are also non-reader boundaries: `json_bytes` in both modules uses
`allow_nan=False` (`src/dt_ai/core/io.py:L12-L13`, `src/twinqa/io.py:L21-L22`);
QA adds line-ending-normalized `digest_text`, while AGR owns path/root/write utilities.
Equal serializer options do not imply equal reader acceptance or safe package coupling.

### Exposure, legacy syntax, and checker independence

[Profile bridge, L3-L16](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/6e9f3faa22d0e05889c01e46ce15805ed9168a99/src/dt_ai/core/profiles.py#L3-L16)
already delegates to QA's locked loader; therefore it is incorrect to claim the
AGR YAML constructor currently admits infinity into production standards. QA parses
YAML before verifying its digest, but no modified standards files were made or loaded
here. Source hashes, traceability and caller/model validation are distinct layers.

The corpus proves a reader-level finite-description mismatch for QA JSON, **not** an
observed nonfinite real file, accepted production model or passed delivery. Current
bytes-based call paths make J07 a possible parser input, but that is only a syntactic
route, not proof that downstream contracts accept it. For example BuildJob has
finite-constrained fields (`src/dt_ai/core/models.py:L8,L94`, with `Finite` defined in
`src/dt_ai/core/provenance.py:L6`), and the contract tests exercise
model rejection. Other raw-dict routes need field-specific investigation.

A concrete static investigation candidate is GeoJSON: `_number` only checks Real/not-bool
(`src/twinqa/geojson.py:L28-L29`), `_decimals` reports zero for an infinity repr (L32-L34),
and the coordinate checks use those functions (L107-L114). Thus a hypothetical parsed
`[1e400, 0]` is not rejected by those *local* numeric/precision predicates. No complete
valid GeoJSON containing it was submitted, no output finding list was observed, and no
existing caller data was demonstrated to contain it. This is a source-supported risk,
not a proven caller-reachable delivery defect or evidence of actual exposure. It does
not authorize a new numeric bound or gate.

Keep generator-side contracts, checker-side acceptance and delivery/user acceptance
separate. In particular, moving QA imports into the generator's IO module would couple
the checker to the implementation it checks. Existing sharing of locked profiles is
already explicit; it does not justify sharing all parsers or validation predicates.
Any later helper discussion must retain independently asserted checker diagnostics and
counterexamples, rather than using generator output or a shared helper as its own oracle.
This report chooses neither shared-helper adoption nor new gates.

## Proposed next tasks

### S — Document and characterize the reader compatibility matrix

Scope: after approval, add narrowly scoped independent characterization assertions for
both public readers using the frozen contrasts; clarify the QA JSON description without
changing acceptance. Concrete input -> expected current diagnostic pairs:
`b'\xff\xfe{\x00"\x00n\x00"\x00:\x001\x00}\x00'` -> QA
`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`
(AGR returns `{'n': 1}`); YAML `n: .inf\n` -> QA
`ValueError: Nonfinite value in YAML: .inf` (AGR returns +Infinity). Keep these checker
assertions separate from generator assertions; do not decide an encoding or helper policy.
Value **M** / effort **S**: prevents an apparently mechanical deduplication from silently
changing accepted inputs. Proposal only; no tests or issues created.

### M — Establish field-specific numeric exposure before proposing a fix

Scope: construct one complete synthetic GeoJSON and a chosen raw-dict caller fixture,
trace exact fields through parsing and validation, and report acceptance/diagnostics
independently of producer serialization. First characterize `'{"n":Infinity}'` ->
`ValueError: Nonfinite value: Infinity`, versus `'{"n":1e400}'` ->
`reader observation: $['n'] = +Infinity`; then, if the user commissions finite-coordinate
rejection, the proposed acceptance pair is a complete GeoJSON with
`geometry.coordinates[0] = 1e400` -> `fail: coordinates[0] must be finite` rather than
pass/review or an unrelated failure. That last diagnostic is a **proposed contract**, not
an observed message or a numeric-policy decision. Include finite ordinary controls and
separate model rejection from reader rejection. Value **M** / effort **M**: converts a
hypothetical risk into a reproducible caller-level finding before any bounds, shared
helper, or new gate is considered. Proposal only; no issues created.

## Open questions for user

- If follow-up work is commissioned, should the current readers' distinct encoding/BOM
  contracts be retained as compatibility behavior, or should an explicit per-consumer
  policy be specified? GeoJSON's existing UTF-8 requirement is not a universal IO policy.
- Which fields require finite values, and are any finite numeric magnitude bounds needed?
  Rejecting special tokens, conversion overflow, and out-of-range finite values are different contracts.
- Should YAML effective-map duplicates from merge overrides remain errors, or should an
  explicitly selected merge/schema policy distinguish them from repeated literal keys?
- Is only characterization desired next, or should caller-level numeric exposure be
  established before considering any shared helper? Checker independence remains a constraint.

No UTF-8-only policy, numeric bounds, YAML merge policy, shared helper adoption or new gates
are selected. No issue/PR was created; any eventual PR is for
`artsafro/AGR-DigitalTwin-pilot` only.

Verification receipt: the initial standalone attempt stopped at `ModuleNotFoundError: No
module named 'yaml'`, before any parse. The optional in-memory, SHA-256-verified PyYAML
bootstrap was then added without altering corpus v1; the reproduction ran successfully
with **42/42 observations** on unchanged source. No dependency environment was installed
or repository dependency files changed. Temporary YAML files were cleaned automatically;
only this report is delivered. The source snapshot is read-only throughout.

RED / GREEN / affected pytest / full suite: **not run; 0 tests executed**, as required by
the report-only card's explicit exception to the generic implementation instructions.
No regression eval, CI, hooks, DCC, production validation or publication was run.
Invariant -> probe -> N/N: observation coverage -> frozen six-family corpus -> **42/42**
parser/input outcomes recorded; semantic agreement -> same corpus -> **14/21**, not a
pass criterion. Universal fail-closed/path/threshold invariants are **n/a**: no such
production behavior was changed or certified. Remaining work: user choices and any
separately commissioned caller-level probes; `delivery_passed=false`.
