# ZIP member error boundary — which unreadable members skip the V001 report

## Summary

Research only. All nine archives are synthetic, a few hundred bytes, built before any `read_bundle` / `validate()` / CLI call. `delivery_passed=false`. No production code, tests, standards, or real assets were changed. Pytest was not run.

Yes. Two exception families leave the delivery validator without a V001 report. `RuntimeError` (`File 'a.bin' is encrypted, password required for extraction`) and `NotImplementedError` (`That compression method is not supported`) propagate out of `twinqa.bundle.read_bundle`, out of `validate()`, and out of `tools/qa/validate_package.py` `main()`. The CLI then exits 1 with a traceback on stderr and no JSON. That exit is a crash. It is not a V001 fail finding.

`zipfile.BadZipFile` does reach the documented report. Bad CRC and the frozen central-directory size mutation become `BundleError`, one V001 `fail` finding named `ZIP`, JSON, and exit 1, with empty stderr. Unsafe `../x` is rejected in `read_bundle` before `ZipFile.read` and takes the same V001 path.

The frozen deflate XOR (first compressed byte `0xcb` → `0xca`) still inflates to `hi`. It is a reader-success row, then the usual VPM composition failures. `zlib.error` was not raised. Missing-codec `RuntimeError`, flag bits 5 and 6, and the source string `Truncated central directory` were not produced by this corpus.

Pinned source SHA from the task: `5c6098b8226cac3d04de39ce00f514914c7f118f`. Every returned report's `code_commit` field was that SHA. This session did not run git; `report()` calls `git rev-parse HEAD` inside `code_commit()`.

## Findings

### Handlers actually around the delivery reader

`docs/domain/validation.md` ("Implementation status inventory (static audit)") is the in-repo V001 inventory the package sheet points at. No file under `docs/` cites issue #71; `gh` was not used. The inventory attributes safe ZIP reading, CRC, unsafe paths, duplicates, and the uncompressed limit to `src/twinqa/bundle.py:read_bundle`, and archive size to `size_status`. PKG-01 and PKG-02 in `docs/domain/areas/package.md` name that same pair for "no broken or unreadable files". `docs/PROJECT_STATE.md` does not record a passed delivery.

`read_bundle` (`src/twinqa/bundle.py`) has two handlers:

- `ZipFile(path)` catches `zipfile.BadZipFile` and `OSError`, re-raises `BundleError` with `Not a readable ZIP: …`.
- `archive.read(name)` catches `zipfile.BadZipFile`, `OSError`, and `EOFError`, re-raises `BundleError` with `Broken ZIP member: …`.

`BundleError` subclasses `ValueError`. `validate()` (`tools/qa/validate_package.py`) catches only `BundleError` on the ZIP branch, appends one V001 finding (`fail`, name `ZIP`, expected `readable ZIP, safe paths`), and returns `report()` immediately. `main()` does not catch exceptions from `validate()`. `--scene` was not passed.

`src/dt_ai/publish/bundle.py:read_bundle` is a different reader: no `BundleError`, no CRC wrapper, 256 MB limit, names taken from `orig_filename`. Writer checks live in `tests/test_bundle_package_safety.py` (unsafe, NUL, casefold, duplicates, empty round-trip) and `tests/integration/test_pipeline.py` (`ValueError` on `../escape` and a duplicate; `b"not a zip"` / `b""` fail the synthetic validator). Those tests were read, not run. `src/dt_ai/validate/bundle.py` catches `ValueError`, `KeyError`, `OSError`, `TypeError`, and `BadZipFile` around its `read_bundle` and records C001. `RuntimeError` and `NotImplementedError` are outside that tuple. That path was not probed.

`tests/qa/test_validator.py::test_unsafe_zip_path_fails` expects V001 fail for `../evil.txt` inside an otherwise filled VPM zip. Nothing in `tests/` imports `twinqa.bundle.read_bundle` except `size_status` in `tests/qa/test_standards.py`. Encryption, method 1, CRC, and a damaged central directory have no twinqa test in the files searched.

### Corpus, runtime, hashes

Corpus directory `C:/x/t_eddff5d7/corpus/` (not in the repo). Payload `hi` (`6869`), SHA-256 `8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4`. Deflate body built with `zlib.compressobj(6, DEFLATED, -15)` on CPython 3.13.3, zlib 1.3.1, before probes. Probes ran on CPython 3.14.7 (`MSC v.1944 64 bit (AMD64)`), `.venv` interpreter, zlib compile/runtime `1.3.1.zlib-ng`. `zlib`, `bz2`, and `lzma` import. `compression.zstd` was not checked. `zipfile` is `...\cpython-3.14-windows-x86_64-none\Lib\zipfile\__init__.py`.

`read_bundle(path, max_uncompressed=4 * 10**9)` matches `validate()`. CLI: `python tools/qa/validate_package.py <file> --profile vpm --json`, no `--scene`. `load_profiles()` reported `pdf_verified=true`. Standards digest `533991c8de3a319f46f7da08d1d23ccf79dd9e910fa4a376513d46a474d44058`. SHA-256 of each zip was identical before and after the nine reads, nine `validate()` calls, and nine CLI processes.

| File | Bytes | SHA-256 | Mutation |
|---|---:|---|---|
| `stored.zip` | 110 | `d043f43957d7144d0f9486eda1daf1105a5da1c198c3053e5f4e3a20bb6393b4` | method 0, member `a.bin`, payload `hi` |
| `deflated.zip` | 112 | `6ee8de1fec3e03ac32c425e837fac906299fcfe2cefac87007c031c4f56950de` | method 8, compressed `cbc80400` at offset 35 |
| `empty.zip` | 22 | `8739c76e681f900923b900c9df0ef75cf421d39cabb54650c4b9ad19b6a76d85` | EOCD only |
| `unsafe.zip` | 108 | `934d1f82b33b0aebd965fc918cf84730507defd534265c6b0c9ca4f0cb50a898` | member name `../x` |
| `bad-crc.zip` | 110 | `7fad2b91f17192132b46e79751ca88c96b3636ae56932772b1f04be175fe486c` | payload offset 35 XOR `0x01`; CRC fields unchanged |
| `truncated-cd.zip` | 110 | `c2d87a6f53dbb9ee32c1ed806bbdb2b39bc558d69c6bb700d86df436a1787e0b` | EOCD size field at offset 100 set to 52 (actual central directory is 51) |
| `encrypted-flag.zip` | 110 | `92e24ded66dba40d2196f3b815ee0e84f97c52adbc9aceffad1a5562c3a7b94f` | flag bit 0 at local offset 6 and central offset 45; payload still plaintext `hi`; no password |
| `method-shrink.zip` | 110 | `6ae11817e94cd68b8cc00280aa68738ad51f78d3c4b6a2713fdd6274cec7699d` | method 1 at local offset 8 and central offset 47 |
| `corrupt-deflate.zip` | 112 | `79eecc981ec5e0de4fec420c080b1f94d4457e56a4cb3c65eb040ec38e0904af` | compressed byte at offset 35 XOR `0x01` (`cac80400`) |

Source file SHA-256 at probe time: `src/twinqa/bundle.py` `679590acd8aab710ac15c02852cd314cbf0f8c62d7f67f01d75bd072a283d60a`; `tools/qa/validate_package.py` `c751fc797222a15030907c3e3ca98029eb92d56f563ae78a274d72327b7de944`; `src/dt_ai/publish/bundle.py` `446f4b665772ebaf5ad31300512f3a4f544a8d66ef6ed4449cb4ad1a800ba024`; `src/dt_ai/validate/bundle.py` `f02a83cd99bbca43b1680d30d84b81ae65e6bf3caec2389cb9080d67fc42d484`.

### Per-case results

Profile `vpm`, stem from the file name, so a readable archive is checked as an OKS zip (limit 500 MiB). Reader-success rows fail V001 on composition (foreign `a.bin`, missing main FBX / GeoJSON, PNG count 0). `passed` is false. Those composition fails are separate from reader failures. Empty has no foreign-file finding. BundleError rows return before `size_status`, so their only V001 finding is `ZIP`.

| Case | Class | `read_bundle` | `validate()` V001 | CLI JSON | CLI V001 | CLI exit | stderr |
|---|---|---|---|---|---|---|---|
| `stored.zip` | reader-success control | `{a.bin: hi}` | `fail` (size pass; foreign, main FBX, GeoJSON, PNG count) | valid | `fail` | 1 | empty |
| `deflated.zip` | reader-success control | `{a.bin: hi}` | `fail` (same shape, 112 B) | valid | `fail` | 1 | empty |
| `empty.zip` | reader-success control | `{}` | `fail` (size pass; main FBX, GeoJSON, PNG count) | valid | `fail` | 1 | empty |
| `unsafe.zip` | handled failure | `BundleError: Unsafe ZIP path: ../x` | `fail`, finding `ZIP` | valid | `fail` | 1 | empty |
| `bad-crc.zip` | handled failure | `BundleError: Broken ZIP member: Bad CRC-32 for file 'a.bin'` (`cause` `zipfile.BadZipFile`) | `fail`, finding `ZIP` | valid | `fail` | 1 | empty |
| `truncated-cd.zip` | handled failure | `BundleError: Not a readable ZIP: Bad magic number for central directory` | `fail`, finding `ZIP` | valid | `fail` | 1 | empty |
| `encrypted-flag.zip` | observed crash | `RuntimeError: File 'a.bin' is encrypted, password required for extraction` | V001 `unexecuted` | invalid (empty stdout) | `unexecuted` | 1 | traceback, 1407 chars |
| `method-shrink.zip` | observed crash | `NotImplementedError: That compression method is not supported` | V001 `unexecuted` | invalid | `unexecuted` | 1 | traceback, 2046 chars |
| `corrupt-deflate.zip` | reader-success (bit flip still inflated) | `{a.bin: hi}` | `fail` composition, same shape as deflated | valid | `fail` | 1 | empty |

Member bytes on the four return rows match the payload SHA-256 above. No password was supplied or searched. Nothing was extracted to disk.

`truncated-cd.zip` does not raise the source string `Truncated central directory`. CPython 3.14 `_handle_prepended_data` sets `concat = eocd_offset - cd_size - cd_offset` = `88 - 52 - 37` = `-1`, so the central directory is read at offset 36. Those four bytes are `69504b01`, and the parser raises `Bad magic number for central directory` (`zipfile/__init__.py` around the central-directory loop). The short-header branch that says `Truncated central directory` stays an untested hypothesis.

`corrupt-deflate.zip`: `zlib.decompressobj(-15)` on `cac80400` returns `b'hi'` and `eof` is false; `flush()` does not raise. `ZipExtFile` still accepts the member and the stored CRC matches, so the row never enters the member `except`.

### Docs versus this run

Primary pages: [zipfile, Python 3.14](https://docs.python.org/3.14/library/zipfile.html) and [zlib](https://docs.python.org/3/library/zlib.html).

Verified by running:

- `ZipFile.read` on method 1 raises `NotImplementedError`. The 3.14 `read()` paragraph says a method other than stored, deflate, bzip2, lzma, or zstd raises `NotImplementedError`. The observed message is `That compression method is not supported`, from `_check_compression` (the traceback reaches line 851, then `_get_decompressor`). The later source string `compression type 1 (shrink)` was not the exception raised.
- Bad CRC surfaces as `BadZipFile: Bad CRC-32 for file 'a.bin'`, which the delivery handler turns into `BundleError`. The doc calls `BadZipFile` "The error raised for bad ZIP files" and the pitfalls list names CRC among reasons decompression may fail. The doc does not quote the CRC message; the message is from `ZipExtFile._update_crc`.
- Flag bit 0 with no password raises `RuntimeError` inside `ZipFile.open` before a decrypter is built. The module intro says decryption is supported and that the library cannot create an encrypted file. `read()` documents `pwd` and does not name `RuntimeError` for a missing password. The pitfalls line says failure may be due to an incorrect password; this run used no password, so the "Bad password" `RuntimeError` was not observed.

Documented, not executed here:

- `read()`: "An error will also be raised if the corresponding compression module is not available." The constructor paragraph names `RuntimeError` for a missing module when writing. `_check_compression` raises `RuntimeError` for a missing zlib, bz2, lzma, or `compression.zstd` module. All three of zlib, bz2, and lzma imported, so this is an untested hypothesis, not a platform-limited result.
- `zlib.error` is what `decompress` raises on a bad stream ([zlib docs](https://docs.python.org/3/library/zlib.html)). `ZipExtFile._read1` does not catch it, and `read_bundle` does not list it. This corpus did not raise it.

Also untested, from the 3.14 `open()` source only: `NotImplementedError` for flag bit 5 (`compressed patched data`) and flag bit 6 (`strong encryption`). Both sit outside the `read_bundle` handler, same as method 1.

## How it applies to this repository

PKG-01 / PKG-02 say an unreadable member is a V001 integrity failure via `read_bundle`. That is true for `BadZipFile` / `OSError` / `EOFError` and for the path check. It is false for the two families that were observed to escape: the process ends in `main()` at `tools/qa/validate_package.py` line 328, and no stage JSON is written.

Call chain for those two rows: `main` → `validate` line 200 → `read_bundle` line 33 `archive.read` → `zipfile.ZipFile.read` / `open`. `validate` lines 201–205 catch `BundleError` only. Early return skips `size_status` and `validate_vpm_zip`.

`src/dt_ai/publish/bundle.py` is the development writer/reader. Its tests already reject unsafe and duplicate names. It is not the V001 implementation. A crash in `twinqa.bundle` does not say the writer checks failed.

`src/twinqa/report.py` `exit_code` is 1 when any finding is `fail`. The crashing CLI's exit 1 comes from an uncaught exception (`sys.exit` is not reached). Stdout is empty, so JSON validity fails and V001 is unexecuted.

## Reproduction

Synthetic bytes only. Writes under `C:/x/t_eddff5d7/corpus/` and prints one JSON object per file. Requires the repo on `sys.path` and the same dependencies `validate_package.py` imports (this run used the worktree `.venv`, CPython 3.14.7).

```python
import hashlib, json, subprocess, sys
from pathlib import Path

REPO = Path(r"C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_eddff5d7")
OUT = Path(r"C:/x/t_eddff5d7/corpus")
HEX = {
    "stored.zip": "504b030414000000000000002100ac2a93d8020000000200000005000000612e62696e6869504b0102140014000000000000002100ac2a93d80200000002000000050000000000000000000000000000000000612e62696e504b0506000000000100010033000000250000000000",
    "deflated.zip": "504b030414000000080000002100ac2a93d8040000000200000005000000612e62696ecbc80400504b0102140014000000080000002100ac2a93d80400000002000000050000000000000000000000000000000000612e62696e504b0506000000000100010033000000270000000000",
    "empty.zip": "504b0506000000000000000000000000000000000000",
    "unsafe.zip": "504b030414000000000000002100ac2a93d80200000002000000040000002e2e2f786869504b0102140014000000000000002100ac2a93d802000000020000000400000000000000000000000000000000002e2e2f78504b0506000000000100010032000000240000000000",
    "bad-crc.zip": "504b030414000000000000002100ac2a93d8020000000200000005000000612e62696e6969504b0102140014000000000000002100ac2a93d80200000002000000050000000000000000000000000000000000612e62696e504b0506000000000100010033000000250000000000",
    "truncated-cd.zip": "504b030414000000000000002100ac2a93d8020000000200000005000000612e62696e6869504b0102140014000000000000002100ac2a93d80200000002000000050000000000000000000000000000000000612e62696e504b0506000000000100010034000000250000000000",
    "encrypted-flag.zip": "504b030414000100000000002100ac2a93d8020000000200000005000000612e62696e6869504b0102140014000100000000002100ac2a93d80200000002000000050000000000000000000000000000000000612e62696e504b0506000000000100010033000000250000000000",
    "method-shrink.zip": "504b030414000000010000002100ac2a93d8020000000200000005000000612e62696e6869504b0102140014000000010000002100ac2a93d80200000002000000050000000000000000000000000000000000612e62696e504b0506000000000100010033000000250000000000",
    "corrupt-deflate.zip": "504b030414000000080000002100ac2a93d8040000000200000005000000612e62696ecac80400504b0102140014000000080000002100ac2a93d80400000002000000050000000000000000000000000000000000612e62696e504b0506000000000100010033000000270000000000",
}
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools" / "qa")]
from twinqa.bundle import read_bundle
from twinqa.profiles import load_profiles
import validate_package as vp
profiles = load_profiles()
for name, hex_text in HEX.items():
    path = OUT / name
    data = bytes.fromhex(hex_text)
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    try:
        got = read_bundle(path, max_uncompressed=4 * 10**9)
        read = {k: hashlib.sha256(v).hexdigest() for k, v in got.items()}
    except Exception as exc:
        read = f"{type(exc).__module__}.{type(exc).__qualname__}: {exc}"
    try:
        report = vp.validate(path, "vpm", profiles, scene=False)
        stage = next(s for s in report.stages if s.id == "V001")
        validated = {"v001": stage.status, "exit": report.exit_code,
                     "findings": [(f.status, f.name, f.observed) for f in stage.findings]}
    except Exception as exc:
        validated = {"v001": "unexecuted", "error": f"{type(exc).__qualname__}: {exc}"}
    proc = subprocess.run([sys.executable, str(REPO / "tools/qa/validate_package.py"),
                           str(path), "--profile", "vpm", "--json"],
                          cwd=REPO, capture_output=True)
    try:
        payload = json.loads(proc.stdout)
        cli_v001 = next(s["status"] for s in payload["stages"] if s["id"] == "V001")
    except (json.JSONDecodeError, KeyError, StopIteration):
        cli_v001 = "unexecuted"
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({"name": name, "sha256": digest, "unchanged": after == digest,
                      "read_bundle": read, "validate": validated,
                      "cli_exit": proc.returncode, "cli_v001": cli_v001,
                      "stderr_empty": proc.stderr == b""}, ensure_ascii=False))
```

## Proposed next tasks

1. **Route observed delivery-reader escapes into the existing V001 ZIP finding.** Size S. In `src/twinqa/bundle.py` only, catch `RuntimeError` and `NotImplementedError` from `archive.read` and re-raise `BundleError` with the current `Broken ZIP member:` prefix, so `validate()` and the CLI already produce the V001 fail JSON and exit 1. Leave encryption, allowed methods, and size limits as they are. Value: PKG-01/02 unreadable-member failures show up as a report instead of a traceback. Effort is one handler plus the two inputs below. Advances #149 (roadmap §7.8 package validation, L2 self-check). Input `encrypted-flag.zip` (flag bit 0, plaintext `hi`, no password) → `BundleError` whose message contains `password required for extraction` → V001 finding `ZIP` `fail`, JSON object, exit 1, empty stderr. Input `method-shrink.zip` (method 1 in both headers) → `BundleError` containing `That compression method is not supported` → the same V001 JSON shape and exit 1. Input `stored.zip` and `deflated.zip` → member `a.bin` still SHA-256 `8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4`, and the composition findings stay `foreign files` / `main FBX` / `GeoJSON` / `PNG count`.

2. **Pin the rows that already return a report, including the deflate XOR that stays readable.** Size S. Test-only, against `twinqa.bundle.read_bundle` and `validate()` with `--profile vpm` and no `--scene`. Value: a later handler edit can see bad CRC and the size-field mutation as V001, and can see the XOR as a successful read. Effort is one test module and the frozen hex above. Advances #149. Input `bad-crc.zip` → `BundleError` `Broken ZIP member: Bad CRC-32 for file 'a.bin'` → V001 `fail`, exit 1. Input `truncated-cd.zip` → `BundleError` `Not a readable ZIP: Bad magic number for central directory` → V001 `fail`, exit 1. Input `unsafe.zip` → `BundleError` `Unsafe ZIP path: ../x` → V001 `fail`. Input `corrupt-deflate.zip` → returned `a.bin` equals `hi` → V001 `fail` on composition, with no finding named `ZIP`. Input `empty.zip` → `{}` → V001 `fail` on main FBX, GeoJSON, and PNG count.

## Open questions

- Should flag bit 0 with no password, and compression methods outside the five `ZipFile.read` implements, stay process-killing, or use the same V001 `ZIP` finding as a bad CRC? This note does not choose.
- The XOR at offset 35 still yields `hi` with a matching CRC, while `decompressobj.eof` is false. Should a stream zlib has not marked finished count as unreadable? This note does not choose.
- Is a fixture wanted for the source branch `Truncated central directory` (short 46-byte central header with `concat >= 0`)? The frozen size-plus-one input takes the bad-magic branch instead.
- Should `src/dt_ai/validate/bundle.py`'s C001 handler grow the same two families? That reader was not probed.
- Flag bits 5 and 6, a wrong password (`Bad password for file …`), and a missing zlib/bz2/lzma/zstd module were not in the corpus.

## Sources

16 sources: `docs/domain/areas/package.md` (PKG-01/02); `docs/domain/validation.md` (implementation inventory); `docs/PROJECT_STATE.md`; `docs/research/capability-roadmap.md` §7.8; `src/twinqa/bundle.py`; `tools/qa/validate_package.py`; `src/twinqa/report.py`; `src/dt_ai/publish/bundle.py`; `src/dt_ai/validate/bundle.py`; `tests/qa/test_validator.py`; `tests/test_bundle_package_safety.py`; `tests/integration/test_pipeline.py`; CPython 3.14.7 `Lib/zipfile/__init__.py`; [zipfile 3.14 docs](https://docs.python.org/3.14/library/zipfile.html); [zlib docs](https://docs.python.org/3/library/zlib.html); the frozen corpus and probe record under `C:/x/t_eddff5d7/` (`manifest.json`, `probe_results.json`).
