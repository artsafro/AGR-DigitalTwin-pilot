# GeoJSON nesting — where a small deep document meets the V011 report

## Summary

Research only. Nineteen synthetic UTF-8 fixtures, each under 64 KiB, were written to disk and hashed before any `read_json`, `geojson_findings`, `validate()`, or CLI call. No production code, tests, standards, or real assets were changed. Pytest was not run. `delivery_passed=false` on every report.

On CPython 3.14.7 with `sys.getrecursionlimit() == 1000` and `sys.get_int_max_str_digits() == 4300` (both left unchanged), no frozen depth escapes V011. Depths 32, 128, 512, and 2048 all parse. The CLI writes a strict JSON report and an empty stderr. There was no escaping witness to repeat. The three shallow controls were run twice and matched.

A complete document whose `developer` value is a nested array or object receives V011 `schema: pass`, exit 2, `passed` false. A top-level array or object parses, then becomes one V011 `type` fail. `{` and a duplicated `designer` key become the existing V011 `JSON` fail. The parser-error handler catches `UnicodeDecodeError` and `ValueError`. `RecursionError` is a `RuntimeError`. CPython 3.14.7 calls `_Py_EnterRecursiveCall` from the scanner and the encoder; that check uses the C stack soft limit, and depth 2048 does not reach it on this interpreter. That later depth was not measured. A V011 pass is not delivery acceptance.

Pinned source SHA: `4c863c1a4616f1812595536d0507f53034e9acfe`. Every returned report's `code_commit` was that SHA. This session did not run git; `report()` calls `git rev-parse HEAD` inside `code_commit()`.

## Findings

Evidence labels: **Verified** = this run, this interpreter, these frozen bytes. **Source** = a file read for this note, not a crash produced here.

### Handler and the three later sites

`geojson_findings` wraps only `read_json` (`src/twinqa/geojson.py:88-93`). `UnicodeDecodeError` becomes a `UTF-8` fail. `ValueError` becomes a `JSON` fail whose `observed` is `str(exc)[:120]`. The `try` ends before the schema checks.

`read_json` (`src/twinqa/io.py:38-42`) decodes bytes as UTF-8 and calls `json.loads` with `object_pairs_hook=unique_pairs` and `parse_constant=_reject_constant`. `unique_pairs` (`src/twinqa/io.py:25-31`) raises `ValueError` on a repeated key. `JSONDecodeError` subclasses `ValueError` (Verified MRO). `RecursionError` subclasses `RuntimeError`, and `issubclass(RecursionError, ValueError)` is false (Verified).

`validate()` (`tools/qa/validate_package.py:228-230`) appends the findings for a `.geojson` file and does not catch. `main()` (`tools/qa/validate_package.py:328-332`) prints `json.dumps(result.to_dict(), ...)` only after `validate()` returns. `to_dict` (`src/twinqa/report.py:238-253`) serializes findings, stages, and digests. It does not carry the parsed document.

Three source sites can still recurse after that design:

- Parse: CPython 3.14.7 `Modules/_json.c` `scan_once_unicode`, lines 1052-1056 for `{` and 1060-1064 for `[`, each calling `_Py_EnterRecursiveCall` before `_parse_object_unicode` / `_parse_array_unicode`. **Source**, tag `v3.14.7`.
- Diagnostic repr: `src/twinqa/geojson.py:97` evaluates `repr(...)` and then slices `[:60]`. For a non-dict the argument is the whole document. For a dict it is `doc.get("type")` only. **Source**, and the slice does not stop the `repr` call.
- Serialization of a nested container: `encoder_listencode_obj` in the same `_json.c`, lines 1518-1529, calls `_Py_EnterRecursiveCall` for a list and for a dict. The delivery report uses `json.dumps` on the finding dict (`tools/qa/validate_package.py:331`), whose strings are already short.

CPython 3.14 `InternalDocs/stack_protection.md` (tag `v3.14.7`) says `_Py_EnterRecursiveCall` compares the C stack pointer with a soft limit and raises `RecursionError` (`Stack overflow (used N kB)`) at that limit. The Python counter from `sys.getrecursionlimit()` is a different mechanism. **Source.** This run did not raise that `RecursionError`, so the kilobyte figure is not a measured threshold.

The pure-Python scanner (`json/decoder.py` `JSONArray` at line 221, called from `json/scanner.py` `py_make_scanner`) is the fallback when `_json.make_scanner` is absent. This interpreter loaded `c_scanstring` from builtin `_json`, and `json/scanner.py:73` selects `c_make_scanner` in that case. The pure-Python fallback was not executed.

`developer` is not formatted into a finding. The property loop (`src/twinqa/geojson.py:125-134`) interpolates a value only for an empty string/`None`, and for `FNO_code` when that value is a `str`. A list or dict fails neither test. `schema: pass` is appended at lines 142-143 when every earlier finding passed.

### Runtime

Probe: `uv run python C:\x\t_0d81e812\run_probe.py` from the worktree. Interpreter `3.14.7 (main, Aug 7 2026, 02:26:22) [MSC v.1944 64 bit (AMD64)]`, `.venv` `Scripts\python.exe`. `json` is `...\cpython-3.14-windows-x86_64-none\Lib\json\__init__.py`. `_json` is builtin. Each function call and each CLI call was a fresh process with a 45-second timeout. `--scene` was not passed. CLI: `python tools/qa/validate_package.py <file> --profile vpm --json`.

Source SHA-256 at probe time: `src/twinqa/io.py` `50ba4590710973f096b4b44ff2f7875901295e79d2e4949828fbda2b128765d8`; `src/twinqa/geojson.py` `2418b273ec3314e5f215cbed52924b256d03f90274b315aa698e3018a9d83c67`; `src/twinqa/report.py` `324d1ab3499b7ed09fad50fe03d10c90db52e8391083eadbdc667ff4e905165e`; `tools/qa/validate_package.py` `c751fc797222a15030907c3e3ca98029eb92d56f563ae78a274d72327b7de944`.

Every worker started and ended at recursion limit 1000 and integer-string limit 4300. File SHA-256 was unchanged across each read. Largest fixture: 14983 bytes.

The complete documents share one synthetic flat JPEG: RGB `(200, 200, 200)`, 256×256, quality 20, base64 length 2200. That image is only there so the control document is complete. It is not a JPEG-boundary corpus. `FNO_code` is the checker-shaped `123 456`. Depth is the count of single-child containers around the leaf `0`, built by byte repetition (`b"[" * depth`, `b'{"k":' * depth`). The manifest at `C:/x/t_0d81e812/manifest.json` was sealed, and each file was re-hashed from disk, before the first parser call. Results: `C:/x/t_0d81e812/results.json`.

Parsed values were summarized by an iterative walk (type, depth, leaf). The probe did not `repr` or `json.dumps` a parsed document. A separate process built the same shapes by a Python loop and recorded only the length of `repr` and `json.dumps`, or the exception class.

### Frozen rows

`[run` is the longest run of `[` in CLI stdout. Controls were executed twice; run 2 matched run 1 on reader, findings, V011, exit, CLI code, stdout length, and stderr. Nest rows were executed once: none met the escape rule (findings list, `validate()` report, and strict CLI JSON).

| File | Shape | Depth | Where | Bytes | SHA-256 |
|---|---|---:|---|---:|---|
| `control-valid.geojson` | document | 0 | `developer` string | 2701 | `8cfbb443ae2d91395012b8df4eace001a77cec0c0eb927df2bb7bcc70bf328ad` |
| `control-malformed.geojson` | `{` | 0 | top | 1 | `021fb596db81e6d02bf3d2586ee3981fe519f275c0ac9ca76bbcf2ebb4097d96` |
| `control-duplicate.geojson` | duplicate `designer` | 0 | properties | 2720 | `b31db5d8307cf9128706c496186034a6af040ed52fbd77fc65510add7242719d` |
| `array-d0032.geojson` | array | 32 | top | 65 | `4e04cac422d9ecd4a5f6221653eeb4eaf29077cf3f588cd36bf6dc8ead76971f` |
| `object-d0032.geojson` | object | 32 | top | 193 | `54f9943141e7283ca5fc31fd79dd9603049f052cfa718143b6ec1a21cc4eb204` |
| `doc-array-d0032.geojson` | document | 32 | `developer` | 2759 | `28b1e4b40a1533cefbda2271b287efb9b8126c9efd8222e72991be11115d191d` |
| `doc-object-d0032.geojson` | document | 32 | `developer` | 2887 | `a0743fe52fabe21345aee3ac6877456ad8cd018c02d0a9351d65ff6c28f4392c` |
| `array-d0128.geojson` | array | 128 | top | 257 | `a87f12d34d179c4dd058f06d205b96585bd84797eab5360fe32bc414d56028ba` |
| `object-d0128.geojson` | object | 128 | top | 769 | `6e5ab688de8d2f71d23fb95a6e0df107339efd64ed8a1000da862e839aacb527` |
| `doc-array-d0128.geojson` | document | 128 | `developer` | 2951 | `bc008bc5dc6427e687a91ccefe40d07a87685c6c302a086b815d7e5304b26025` |
| `doc-object-d0128.geojson` | document | 128 | `developer` | 3463 | `5f9fc54e0c456e6e5172848b761f137f029cde27d281faa5bee8876b2283390a` |
| `array-d0512.geojson` | array | 512 | top | 1025 | `8ffc0a1c6c684d5a33431fd2d1cd8295423335157134c42b1ee0be9ab57b36eb` |
| `object-d0512.geojson` | object | 512 | top | 3073 | `ba166cb5bcb8b7677c049edefa286bdee29d534f6ec320e4cb4a92dcdb097ded` |
| `doc-array-d0512.geojson` | document | 512 | `developer` | 3719 | `b2effc3d6c68469c5eb8fc980eaa31d7601c96df20cd2155fe6be3d6c3cbad5c` |
| `doc-object-d0512.geojson` | document | 512 | `developer` | 5767 | `d1ecb09d96c460b4157d2a49a0864ec2c32952b08b67c167b118bcea5f7dd407` |
| `array-d2048.geojson` | array | 2048 | top | 4097 | `41c232a67abacbd9e4ffa57f1775077ec16a9e8185c9a33573bb9ca82bd6172a` |
| `object-d2048.geojson` | object | 2048 | top | 12289 | `08e990132a3711ab36aa18eca1594dc128d187c8253582ebfc7197a7113cca23` |
| `doc-array-d2048.geojson` | document | 2048 | `developer` | 6791 | `a7e57f1f2ec14d3ce8102d0c4bd0d6a13ded70f8d20af27f1f4165d5aab8423d` |
| `doc-object-d2048.geojson` | document | 2048 | `developer` | 14983 | `e64c627551fe753f1310594b906cbb4d064d95030d5b7edc8b80dbfdb7f7dfd6` |

| File | Runs | `read_json` | `geojson_findings` | V011 | `passed` | exit | CLI | stdout | JSON | stderr | `[` run |
|---|---:|---|---|---|---|---:|---:|---:|---|---|---:|
| `control-valid.geojson` | 2 | dict, `developer` str | `imageBase64` pass, `Glasses` pass, `schema` pass | pass | false | 2 | 2 | 7465 | yes | empty | 1 |
| `control-malformed.geojson` | 2 | `JSONDecodeError` | `JSON` fail, observed the decode message (75 chars) | fail | false | 1 | 1 | 6620 | yes | empty | 1 |
| `control-duplicate.geojson` | 2 | `ValueError: Duplicate key: designer` | `JSON` fail, observed `Duplicate key: designer` | fail | false | 1 | 1 | 6568 | yes | empty | 1 |
| `array-d0032.geojson` | 1 | list depth 32, leaf int | `type` fail, observed 60 chars ending in `0` and `]` | fail | false | 1 | 1 | 6566 | yes | empty | 32 |
| `object-d0032.geojson` | 1 | dict depth 32, leaf int | `type` fail, observed `None` | fail | false | 1 | 1 | 6511 | yes | empty | 1 |
| `doc-array-d0032.geojson` | 1 | dict, `developer` list depth 32 | same three passes as the valid control | pass | false | 2 | 2 | 7467 | yes | empty | 1 |
| `doc-object-d0032.geojson` | 1 | dict, `developer` dict depth 32 | same three passes | pass | false | 2 | 2 | 7468 | yes | empty | 1 |
| `array-d0128.geojson` | 1 | list depth 128, leaf int | `type` fail, observed 60 `[` | fail | false | 1 | 1 | 6566 | yes | empty | 60 |
| `object-d0128.geojson` | 1 | dict depth 128, leaf int | `type` fail, observed `None` | fail | false | 1 | 1 | 6511 | yes | empty | 1 |
| `doc-array-d0128.geojson` | 1 | `developer` list depth 128 | three passes | pass | false | 2 | 2 | 7467 | yes | empty | 1 |
| `doc-object-d0128.geojson` | 1 | `developer` dict depth 128 | three passes | pass | false | 2 | 2 | 7468 | yes | empty | 1 |
| `array-d0512.geojson` | 1 | list depth 512, leaf int | `type` fail, observed 60 `[` | fail | false | 1 | 1 | 6566 | yes | empty | 60 |
| `object-d0512.geojson` | 1 | dict depth 512, leaf int | `type` fail, observed `None` | fail | false | 1 | 1 | 6511 | yes | empty | 1 |
| `doc-array-d0512.geojson` | 1 | `developer` list depth 512 | three passes | pass | false | 2 | 2 | 7467 | yes | empty | 1 |
| `doc-object-d0512.geojson` | 1 | `developer` dict depth 512 | three passes | pass | false | 2 | 2 | 7468 | yes | empty | 1 |
| `array-d2048.geojson` | 1 | list depth 2048, leaf int | `type` fail, observed 60 `[` | fail | false | 1 | 1 | 6566 | yes | empty | 60 |
| `object-d2048.geojson` | 1 | dict depth 2048, leaf int | `type` fail, observed `None` | fail | false | 1 | 1 | 6511 | yes | empty | 1 |
| `doc-array-d2048.geojson` | 1 | `developer` list depth 2048 | three passes | pass | false | 2 | 2 | 7467 | yes | empty | 1 |
| `doc-object-d2048.geojson` | 1 | `developer` dict depth 2048 | three passes | pass | false | 2 | 2 | 7468 | yes | empty | 1 |

Every row's note was `single GeoJSON: only V011 applies`. Every stage other than V011 was `not_run`. Exit 2 is `ValidationReport.exit_code` (`src/twinqa/report.py:231-236`) when the report is not `passed` and no finding is `fail`. `passed` (`src/twinqa/report.py:226-228`) requires every blocking stage to be `pass`.

Size check, Verified: `doc-object-d2048` is `2701 - len(b'"value"') + 12289 = 14983`. The nest was spliced into the shell. Stdout length is constant across depths of the same shape (7467 for every `doc-array-*`, 7468 for every `doc-object-*`, 6566 for every top-level array from depth 128 up, 6511 for every top-level object). The one-byte gap between `doc-array` and `doc-object` is the file-name character in `target`. The nest is absent from the report JSON.

### What each stage did inside the cap

**Parse (Verified).** `read_json` returned a value for every nested fixture, including both 2048-deep files and both 2048-deep `developer` values. The iterative walk measured the requested depth and leaf `int`. Malformed input raised `JSONDecodeError` with `Expecting property name enclosed in double quotes: line 1 column 2 (char 1)`, and `geojson_findings` caught it as `JSON` fail. The duplicate key raised `ValueError` from `unique_pairs` and was caught the same way. No `RecursionError` was raised, so the parse-stage stack check in `_json.c:1052` and `:1060` did not fire. **Source** says it would raise `RecursionError`, which `geojson.py:90-93` does not catch, so `validate()` and `main()` would then end with a traceback and no JSON. That path is unmeasured above this cap.

**Diagnostic repr (Verified for the calls that exist).** Top-level arrays hit `geojson.py:97` with the list itself. `repr` completed: depth 32 stores a 60-character prefix that still contains the leaf `0`; depths 128, 512, and 2048 store 60 `[` characters, and CLI stdout's longest `[` run is 60. The full `repr` ran before the slice. It did not raise. Top-level objects are dicts, so line 97 stores `repr(None)` (`None`). The nested body is not the `repr` argument. Documents never format `developer`. Their finding text matches the shallow valid control.

**Report serialization (Verified).** `json.dumps` of `to_dict()` succeeded for every row. Stdout parsed as a report object with `stages` and `exit_code`. Stderr length was 0. The separate, non-parsed containers also completed `repr` and `json.dumps` at every depth. Lengths equal `2*depth+1` for arrays (2048 → 4097) and `7*depth+1` for objects (2048 → 14337), which is the full string. Those calls are the encoder site at `_json.c:1518-1529` and Python `repr`. They did not raise. The delivery serializer never receives the parsed nest; the constant stdout lengths are that observation.

An observed exception did not occur on the nest rows. The `JSON` and `type` fails above are findings, with a report. The `schema: pass` rows are a V011 pass on a single file, with `passed` false.

## How it applies to this repository

PKG-19 (`docs/domain/areas/package.md`) says V011 decodes UTF-8, parses JSON, rejects duplicate keys, and compares the key set. That is the path these rows took. The duplicate control and the `{` control become the `JSON` finding. A nested value at these depths is a successful parse, so the parser-error finding is not the row that describes it.

A nested `developer` still has the App.3 key present, so the exact-key check passes, and the value is not type-checked. V011 then reports `schema: pass`. PKG-19 also says values follow App.3. The checker does not enforce a string type on `developer`. This run shows the consequence for a small deep value: a report exists, V011 passes, and the package is still `passed` false because a single GeoJSON leaves the other blocking stages `not_run`. `docs/domain/areas/package.md` records that no delivery package has `passed`.

The source gap that would skip the report is narrower than the cap: `RecursionError` from `_Py_EnterRecursiveCall` is outside the handler, and `main()` has no handler of its own. This corpus did not reach it. `sys.getrecursionlimit()` staying at 1000 does not, on 3.14, mean that 1000 JSON levels is the failure point.

## Reproduction

Synthetic bytes only. From the worktree: `uv run python C:\x\t_0d81e812\run_probe.py`. The process freezes `C:/x/t_0d81e812/corpus/`, writes `manifest.json`, then measures. Corpus builders:

```python
def nested_array(depth: int) -> bytes:
    return (b"[" * depth) + b"0" + (b"]" * depth)

def nested_object(depth: int) -> bytes:
    return (b'{"k":' * depth) + b"0" + (b"}" * depth)
```

The shell concatenates a complete FeatureCollection around those bytes in the `developer` position, with `Glasses` `[]`, coordinates `[12345.678, 6789.012]`, and the flat JPEG above. The duplicate control inserts a second `"designer":"value"`. The malformed control is the single byte `{`. The executed orchestrator is `C:/x/t_0d81e812/run_probe.py`. The quote below matches that file except that it drops the per-row rewrite of `results.json`:

```python
"""Frozen-corpus probe: deep but small UTF-8 JSON versus the V011 parser-error handler.

Phase order is fixed: write every fixture and manifest, then measure.
Fixture bytes are built by repetition, never by json.dumps of a nested value.
This process does not call sys.setrecursionlimit or change the integer-string limit.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_0d81e812")
OUT = Path(r"C:\x\t_0d81e812")
CORPUS = OUT / "corpus"
MANIFEST = OUT / "manifest.json"
RESULTS = OUT / "results.json"
PINNED_SHA = "4c863c1a4616f1812595536d0507f53034e9acfe"
DEPTHS = (32, 128, 512, 2048)
LIMIT = 64 * 1024
TIMEOUT_S = 45


def nested_array(depth: int) -> bytes:
    return (b"[" * depth) + b"0" + (b"]" * depth)


def nested_object(depth: int) -> bytes:
    return (b'{"k":' * depth) + b"0" + (b"}" * depth)


def jpeg_b64() -> str:
    from io import BytesIO
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (256, 256), (200, 200, 200)).save(buf, "JPEG", quality=20)
    import base64

    return base64.b64encode(buf.getvalue()).decode("ascii")


def shell(developer: bytes, duplicate_designer: bool = False) -> bytes:
    before = ("address", "okrug", "rajon", "name")
    after = (
        "designer", "cadNum", "FNO_code", "FNO_name", "ZU_area", "h_relief", "h_otn",
        "h_abs", "s_obsh", "s_naz", "s_podz", "spp_gns", "act_AGR", "imageBase64", "other",
    )
    image = jpeg_b64()
    values = {key: "value" for key in before + after}
    values["FNO_code"] = "123 456"
    values["other"] = ""
    values["imageBase64"] = image

    def field(key: str) -> bytes:
        return b'"' + key.encode("ascii") + b'":"' + values[key].encode("ascii") + b'"'

    props = b",".join(field(key) for key in before)
    props += b',"developer":' + developer
    tail = [field(key) for key in after]
    if duplicate_designer:
        tail.insert(1, field("designer"))
    props += b"," + b",".join(tail)
    return (
        b'{"type":"FeatureCollection","features":[{"type":"ObjectFeature","properties":{'
        + props
        + b'},"geometry":{"type":"Point","coordinates":[12345.678,6789.012]},"Glasses":[]}]}'
    )


def freeze() -> dict:
    CORPUS.mkdir(parents=True, exist_ok=True)
    image = jpeg_b64()
    rows = []

    def add(name: str, data: bytes, **meta) -> None:
        if len(data) >= LIMIT:
            raise SystemExit(f"fixture {name} is {len(data)} bytes")
        data.decode("utf-8").encode("utf-8")
        path = CORPUS / name
        path.write_bytes(data)
        rows.append({
            "id": name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "utf8": True,
            **meta,
        })

    add("control-valid.geojson", shell(b'"value"'), role="control", shape="document", depth=0, where="developer-string")
    add("control-malformed.geojson", b"{", role="control", shape="malformed", depth=0, where="top")
    add("control-duplicate.geojson", shell(b'"value"', duplicate_designer=True), role="control", shape="duplicate-key", depth=0, where="designer")
    for depth in DEPTHS:
        add(f"array-d{depth:04d}.geojson", nested_array(depth), role="nest", shape="array", depth=depth, where="top")
        add(f"object-d{depth:04d}.geojson", nested_object(depth), role="nest", shape="object", depth=depth, where="top")
        add(f"doc-array-d{depth:04d}.geojson", shell(nested_array(depth)), role="nest", shape="document-array", depth=depth, where="developer")
        add(f"doc-object-d{depth:04d}.geojson", shell(nested_object(depth)), role="nest", shape="document-object", depth=depth, where="developer")

    manifest = {
        "pinned_sha": PINNED_SHA,
        "image_b64_len": len(image),
        "recursion_limit_unchanged": True,
        "rows": rows,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        disk = (CORPUS / row["id"]).read_bytes()
        if hashlib.sha256(disk).hexdigest() != row["sha256"] or len(disk) != row["size"]:
            raise SystemExit(f"freeze mismatch {row['id']}")
    (OUT / "FREEZE_COMPLETE").write_text("ok\n", encoding="ascii")
    return manifest


def site_key(frame) -> list:
    path = Path(frame.f_code.co_filename)
    parts = path.parts[-2:]
    return ["/".join(parts), frame.f_lineno, frame.f_code.co_name]


def exc_info(exc: BaseException) -> dict:
    message = str(exc)
    if len(message) > 240:
        message = message[:240] + f"...<{len(str(exc))} chars>"
    tb = exc.__traceback__
    first = last = None
    count = 0
    seen: Counter = Counter()
    while tb is not None and count < 8000:
        key = tuple(site_key(tb.tb_frame))
        seen[key] += 1
        if first is None:
            first = list(key)
        last = list(key)
        tb = tb.tb_next
        count += 1
    top = [{"site": list(key), "n": n} for key, n in seen.most_common(6)]
    return {
        "outcome": "exception",
        "exc": type(exc).__qualname__,
        "module": type(exc).__module__,
        "mro": [cls.__qualname__ for cls in type(exc).__mro__ if cls is not object],
        "msg": message,
        "frames": count,
        "first": first,
        "last": last,
        "top_sites": top,
    }


def measure(obj) -> dict:
    depth = 0
    cur = obj
    top = type(obj).__name__
    while depth < 10000:
        if isinstance(cur, list) and len(cur) == 1:
            cur = cur[0]
            depth += 1
            continue
        if isinstance(cur, dict) and len(cur) == 1:
            cur = next(iter(cur.values()))
            depth += 1
            continue
        break
    return {"top_type": top, "depth": depth, "leaf": type(cur).__name__}


def summarize_doc(doc) -> dict:
    summary = measure(doc)
    if not isinstance(doc, dict):
        summary["container"] = "top"
        return summary
    summary["container"] = "document"
    features = doc.get("features")
    if not isinstance(features, list) or len(features) != 1 or not isinstance(features[0], dict):
        summary["developer"] = "not-navigable"
        return summary
    props = features[0].get("properties")
    if not isinstance(props, dict) or "developer" not in props:
        summary["developer"] = "absent"
        return summary
    dev = measure(props["developer"])
    summary["developer_type"] = dev["top_type"]
    summary["developer_depth"] = dev["depth"]
    summary["developer_leaf"] = dev["leaf"]
    return summary


def clip_text(text: str) -> dict:
    if len(text) > 160:
        return {"len": len(text), "prefix": text[:40]}
    return {"text": text, "len": len(text)}


def finding_row(finding) -> dict:
    return {
        "status": finding.status,
        "name": finding.name,
        "observed": clip_text(finding.observed),
        "expected": clip_text(finding.expected),
    }


def worker_env() -> None:
    import _json
    import json.decoder as decoder

    payload = {
        "python": sys.version,
        "executable": sys.executable,
        "recursion_limit": sys.getrecursionlimit(),
        "int_max_str_digits": sys.get_int_max_str_digits(),
        "json_file": json.__file__,
        "decoder_file": decoder.__file__,
        "c_scanstring": getattr(decoder, "c_scanstring", None) is not None,
        "json_module": getattr(_json, "__file__", "builtin"),
        "JSONDecodeError_mro": [c.__qualname__ for c in json.JSONDecodeError.__mro__],
        "RecursionError_mro": [c.__qualname__ for c in RecursionError.__mro__],
        "ValueError_in_RecursionError": issubclass(RecursionError, ValueError),
    }
    for rel in (
        "src/twinqa/io.py",
        "src/twinqa/geojson.py",
        "src/twinqa/report.py",
        "tools/qa/validate_package.py",
    ):
        data = (REPO / rel).read_bytes()
        payload[rel] = hashlib.sha256(data).hexdigest()
    print(json.dumps(payload))


def worker_repr(kind: str, depth: int) -> None:
    limit = sys.getrecursionlimit()
    obj = 0
    for _ in range(depth):
        obj = [obj] if kind == "array" else {"k": obj}
    out = {"kind": kind, "depth": depth, "built": "iterative", "recursion_limit": limit}

    def attempt(label, fn):
        try:
            value = fn()
            out[label] = {"outcome": "ok", "len": len(value)}
        except Exception as exc:
            info = exc_info(exc)
            info.pop("top_sites", None)
            out[label] = info

    attempt("repr", lambda: repr(obj))
    attempt("dumps", lambda: json.dumps(obj))
    out["recursion_limit_after"] = sys.getrecursionlimit()
    print(json.dumps(out))


def worker_functions(name: str) -> None:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools" / "qa"))
    from twinqa.geojson import geojson_findings
    from twinqa.io import read_json
    from twinqa.profiles import load_profiles
    import validate_package as vp

    path = CORPUS / name
    data = path.read_bytes()
    out = {
        "id": name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "recursion_limit": sys.getrecursionlimit(),
        "int_max_str_digits": sys.get_int_max_str_digits(),
    }
    profiles = load_profiles()
    try:
        doc = read_json(data)
        out["reader"] = {"outcome": "value", **summarize_doc(doc)}
        del doc
    except Exception as exc:
        out["reader"] = exc_info(exc)
    try:
        found = geojson_findings(data, profiles.vpm, path.stem.endswith("_Ground"))
        out["findings"] = {"outcome": "list", "n": len(found), "rows": [finding_row(f) for f in found]}
    except Exception as exc:
        out["findings"] = exc_info(exc)
    try:
        report = vp.validate(path, "vpm", profiles, scene=False)
        stage = next(s for s in report.stages if s.id == "V011")
        out["validate"] = {
            "outcome": "report",
            "v011": stage.status,
            "v011_rows": [finding_row(f) for f in stage.findings],
            "passed": report.passed,
            "exit": report.exit_code,
            "code_commit": report.code_commit,
            "notes": list(report.notes),
            "stage_status": {s.id: s.status for s in report.stages},
        }
    except Exception as exc:
        out["validate"] = exc_info(exc)
    out["recursion_limit_after"] = sys.getrecursionlimit()
    print(json.dumps(out))


def stderr_family(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    family = "empty"
    tail = lines[-1][:180] if lines else ""
    for line in reversed(lines):
        if line.startswith("Traceback"):
            continue
        head = line.split(":", 1)[0]
        if head.endswith("Error") or head.endswith("Exception") or head.endswith("Exit"):
            family = head.split()[-1]
            tail = line[:180]
            break
    return {"family": family, "tail": tail, "lines": len(lines)}


def max_run(text: str, char: str) -> int:
    best = cur = 0
    for item in text:
        if item == char:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def run_cmd(args: list[str]) -> dict:
    try:
        proc = subprocess.run(args, cwd=REPO, capture_output=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        err = exc.stderr or b""
        out = exc.stdout or b""
        return {"returncode": None, "timeout": True, "stdout_len": len(out),
                "stderr_len": len(err), "json_ok": False, "stderr_family": "TimeoutExpired"}
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    parsed = False
    keys = None
    try:
        payload = json.loads(stdout)
        parsed = isinstance(payload, dict) and "stages" in payload and "exit_code" in payload
        if parsed:
            v011 = next(s for s in payload["stages"] if s["id"] == "V011")
            keys = {"v011": v011["status"], "exit": payload["exit_code"], "passed": payload["passed"],
                    "code_commit": payload.get("code_commit"),
                    "finding_names": [f["name"] for f in v011["findings"]]}
    except (json.JSONDecodeError, UnicodeError, StopIteration, KeyError, TypeError):
        parsed = False
    family = stderr_family(stderr)
    return {"returncode": proc.returncode, "timeout": False, "stdout_len": len(proc.stdout),
            "stderr_len": len(proc.stderr), "json_ok": parsed, "cli_report": keys,
            "stderr_family": family["family"], "stderr_tail": family["tail"],
            "stderr_lines": family["lines"], "stdout_bracket_run": max_run(stdout, "["),
            "stdout_brace_run": max_run(stdout, "{")}


def call_worker(mode: str, *args: str) -> dict:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", mode, *args]
    try:
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"outcome": "timeout"}
    raw = proc.stdout.decode("utf-8", errors="replace").strip()
    line = raw.splitlines()[-1] if raw else ""
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        payload = {"outcome": "worker-crash", "returncode": proc.returncode,
                   "stdout_len": len(proc.stdout), "stderr_len": len(proc.stderr)}
        payload["stderr"] = stderr_family(proc.stderr.decode("utf-8", errors="replace"))
    payload["worker_returncode"] = proc.returncode
    return payload


def escapes(row: dict) -> bool:
    if (row.get("findings") or {}).get("outcome") != "list":
        return True
    if (row.get("validate") or {}).get("outcome") != "report":
        return True
    if not (row.get("cli") or {}).get("json_ok"):
        return True
    return False


def probe_file(row: dict, run: int) -> dict:
    before = hashlib.sha256((CORPUS / row["id"]).read_bytes()).hexdigest()
    functions = call_worker("functions", row["id"])
    cli = run_cmd([sys.executable, str(REPO / "tools" / "qa" / "validate_package.py"),
                   str(CORPUS / row["id"]), "--profile", "vpm", "--json"])
    after = hashlib.sha256((CORPUS / row["id"]).read_bytes()).hexdigest()
    measured = {"id": row["id"], "run": run, "sha256": row["sha256"], "size": row["size"],
                "shape": row["shape"], "depth": row["depth"], "where": row["where"],
                "role": row["role"], "hash_stable": before == after == row["sha256"],
                "functions": functions, "cli": cli, "reader": functions.get("reader"),
                "findings": functions.get("findings"), "validate": functions.get("validate")}
    measured["escapes"] = escapes(measured)
    return measured


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        mode = sys.argv[2]
        if mode == "env":
            worker_env()
        elif mode == "repr":
            worker_repr(sys.argv[3], int(sys.argv[4]))
        elif mode == "functions":
            worker_functions(sys.argv[3])
        else:
            raise SystemExit(f"unknown worker {mode}")
        return
    manifest = freeze()
    env = call_worker("env")
    repr_rows = [call_worker("repr", kind, str(depth)) for kind in ("array", "object") for depth in DEPTHS]
    measured = []
    for row in manifest["rows"]:
        runs = 2 if row["role"] == "control" else 1
        for run in range(1, runs + 1):
            measured.append(probe_file(row, run))
    seen = {item["id"] for item in measured if item["run"] == 2}
    for row in manifest["rows"]:
        first = next(item for item in measured if item["id"] == row["id"] and item["run"] == 1)
        if first["escapes"] and row["id"] not in seen:
            measured.append(probe_file(row, 2))
    print(json.dumps({"frozen": len(manifest["rows"]), "measured": len(measured),
                      "escapes": sorted({item["id"] for item in measured if item["escapes"]})}))


if __name__ == "__main__":
    main()
```

The listing above omits the per-row `results.json` rewrite that the executed file performs after each case. Outcomes were read from that results file. `import traceback` in the executed file is unused.

## Proposed next tasks

1. **Pin the capped rows as current behavior.** Size S. Test-only, against `read_json`, `geojson_findings`, and `validate_package.py --profile vpm --json` with no `--scene`. Value: a later edit can see that depth 2048 still produces a report, and that `{` and a duplicate key stay the `JSON` finding. Effort is one test module and the frozen bytes. This note does not add the test. Advances #149. Input `control-malformed.geojson` (`7b`) → `JSONDecodeError` → V011 `JSON` fail, exit 1, JSON stdout, empty stderr. Input `control-duplicate.geojson` → `ValueError: Duplicate key: designer` → the same `JSON` fail. Input `array-d2048.geojson` → list depth 2048 → V011 `type` fail, observed length 60, exit 1. Input `object-d2048.geojson` → V011 `type` fail, observed `None`, exit 1. Input `doc-array-d2048.geojson` and `doc-object-d2048.geojson` → V011 `schema` pass, `passed` false, exit 2, stdout length independent of the nest.

2. **Decision sheet for a stack-overflow exception and for a `developer` value that is not a string.** Size S. One page. It places the handler tuple at `src/twinqa/geojson.py:90-93` next to `RecursionError`'s MRO and the `_Py_EnterRecursiveCall` calls in CPython 3.14.7 `_json.c:1052`, `:1060`, and `:1519`, and it places the `developer` loop at `src/twinqa/geojson.py:125-134` next to the measured `schema: pass` at depth 2048. The page asks for a decision. It does not choose a depth, adopt a handler change, or type-check the field. Value: the unmeasured stack limit and the measured schema pass are separated before anyone edits V011. Effort is the page. Advances #149. Input: this note's depth-2048 rows → a sheet that records "report exists, stack check not reached" and leaves the threshold and the exception mapping blank. Input: `doc-object-d2048.geojson` → the sheet records V011 `schema` pass with `developer` as a dict, and leaves the value-type rule blank.

## Open questions for the user

- **Depth threshold.** These rows stop at 2048, where parse, diagnostic `repr`, and report `json.dumps` all return. Whether V011 should reject some smaller depth, or any depth, is undecided here.
- **Exception-normalization.** Whether a future `RecursionError` from `_Py_EnterRecursiveCall` should become the existing `JSON` fail, instead of a traceback with no report, is undecided here. This corpus did not raise it.
- **Parser consolidation.** V011 parses through `twinqa.io.read_json`. The CLI serializes the report with `json.dumps` on the finding dict. Other tools call `json.loads` directly. Whether those callers should share one parser is undecided here. These fixtures do not show those callers disagreeing.
- **Unicode policy.** Every frozen file is ASCII and decodes as UTF-8. The handler's separate `UnicodeDecodeError` branch was not exercised. A Unicode policy is undecided here.
