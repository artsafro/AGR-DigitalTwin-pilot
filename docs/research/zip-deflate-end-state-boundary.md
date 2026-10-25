# ZIP DEFLATE end state — unfinished streams, CRC, and V001

## Summary

Research only. Eight synthetic ZIPs, each a few hundred bytes with member `a.bin` and intended payload `b"hi"`, were written and hashed under `C:/x/t_e0e95577/` before any `read_bundle`, `validate()`, or CLI call. `delivery_passed=false` on every row that produced a report. No production code, tests, standards, or real assets were changed. Pytest was not run.

An unfinished raw DEFLATE stream can return the CRC-correct bytes `b"hi"`. The PR #675 payload `cac80400` does that: `decompressobj(-15)` yields `6869`, `eof` is false, `flush()` returns empty and does not raise, and `ZipFile.open` / `ZipFile.read` / `read_bundle` all return `b"hi"`. V001 then has no finding named `ZIP`. The three-byte prefix `cbc804` does the same. A finished `cbc80400` plus a trailing `00` also returns `b"hi"`; there `eof` is true and `unused_data` is `00`.

A reserved block is a different event. First byte `07` (BFINAL=1, BTYPE=3) raises `zlib.error: Error -3 while decompressing data: invalid block type` from `decompress()`. That class subclasses `Exception`, not `OSError`, so `read_bundle` does not catch it. `validate()` and `python tools/qa/validate_package.py --profile npm --json` produce no JSON. Stderr is a traceback (1504 bytes) ending in that message; the process exit is 1.

The one-byte and two-byte prefixes do not raise `zlib.error`. Raw inflate returns `b""` and `b"h"` with `eof` false. `ZipExtFile` still marks its own EOF because the compressed size is exhausted, then `BadZipFile: Bad CRC-32 for file 'a.bin'` becomes a V001 `ZIP` fail, JSON, exit 1, empty stderr. Recovered bytes, a finished stream, and a delivery verdict are three separate outcomes.

## Findings

### What #675 claimed, and what this run did with it

PR [#675](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/675) (`docs/research-zip-member-error-report-boundary`, head `f05cf43647ee1485a1a9a878fee8aa788c0b8ccc`) records that method-8 payload `cac80400` inflates to `hi` while `decompressobj.eof` is false, and that the ZIP reader then succeeds. This run did not use `git fetch` or `git show`. The report text was read with `gh api` raw contents for that ref. The claim matches this run. It is not a mismatch.

Three archives built here are byte-identical to that report's frozen hex, SHA-256 included:

| This file | SHA-256 | #675 name |
|---|---|---|
| `stored.zip` | `d043f43957d7144d0f9486eda1daf1105a5da1c198c3053e5f4e3a20bb6393b4` | `stored.zip` |
| `deflate-valid.zip` | `6ee8de1fec3e03ac32c425e837fac906299fcfe2cefac87007c031c4f56950de` | `deflated.zip` |
| `deflate-unfinished.zip` | `79eecc981ec5e0de4fec420c080b1f94d4457e56a4cb3c65eb040ec38e0904af` | `corrupt-deflate.zip` |

`zlib.compressobj(6, DEFLATED, -15)` on this interpreter emits `cbc80400` for `b"hi"`. That is the valid control, not an assumption carried over from #675.

### Corpus and runtime

Pinned checkout `6d0dffcb95221492e039f14187fe40a7e7a1caf3`. `ValidationReport.code_commit` returned that SHA (its implementation calls `git rev-parse HEAD`). The worktree HEAD ref file contains the same SHA. This session did not run git.

CPython 3.14.7 (`MSC v.1944 64 bit (AMD64)`), zlib compile and runtime `1.3.1.zlib-ng`, zlib-ng `2.2.4`. `zipfile` is `cpython-3.14-windows-x86_64-none\Lib\zipfile\__init__.py`. `load_profiles()` reported `pdf_verified=true`. Standards SHA-256 `533991c8de3a319f46f7da08d1d23ccf79dd9e910fa4a376513d46a474d44058`.

`b"hi"` SHA-256 `8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4`. CRC-32 `0xd8932aac`. In the ZIP headers that integer is stored little-endian as `ac2a93d8`, the same field #675 used. Every local header, central header, and EOCD was parsed before probes: method, CRC, sizes, name `a.bin`, and offsets agree; payload starts at offset 35. SHA-256 of each zip was unchanged after the raw inflate, both zipfile reads, `read_bundle`, `validate()`, and the CLI process.

Source SHA-256 at freeze time: `src/twinqa/bundle.py` `679590acd8aab710ac15c02852cd314cbf0f8c62d7f67f01d75bd072a283d60a`; `tools/qa/validate_package.py` `c751fc797222a15030907c3e3ca98029eb92d56f563ae78a274d72327b7de944`; `src/twinqa/report.py` `324d1ab3499b7ed09fad50fe03d10c90db52e8391083eadbdc667ff4e905165e`.

CLI for every row: `python tools/qa/validate_package.py <file> --profile npm --json`, no `--scene`, fresh process, cwd the worktree. `read_bundle` limit `4 * 10**9`, the same value `validate()` passes.

Bit fields below are this run's read of the first payload byte, LSB first, using the RFC 1951 block header (BFINAL, then BTYPE). They are a structural description. They are not a decoder result.

| Case | Bytes | Payload | First-byte bits | Intended structural note |
|---|---:|---|---|---|
| `stored` | 110 | `6869` | method 0, no deflate header | stored `hi` |
| `deflate-valid` | 112 | `cbc80400` | BFINAL=1, BTYPE=1 | method 8, the four-byte compressor output |
| `deflate-unfinished` | 112 | `cac80400` | BFINAL=0, BTYPE=1 | method 8, exact #675 payload |
| `deflate-reserved` | 109 | `07` | BFINAL=1, BTYPE=3 | method 8, one byte |
| `deflate-prefix-1` | 109 | `cb` | BFINAL=1, BTYPE=1 | first byte of `cbc80400` |
| `deflate-prefix-2` | 110 | `cbc8` | BFINAL=1, BTYPE=1 | first two bytes |
| `deflate-prefix-3` | 111 | `cbc804` | BFINAL=1, BTYPE=1 | first three bytes |
| `deflate-suffix` | 113 | `cbc8040000` | BFINAL=1, BTYPE=1 | `cbc80400` plus `00` inside the compressed field |

Compressed size is the payload length. Uncompressed size is 2. CRC in both headers is the CRC of `b"hi"` on every row, including the short payloads.

### Per-case measurements

Raw columns are one `zlib.decompressobj(-15)`: `decompress(payload)` then `flush()`. `unused_data` and `unconsumed_tail` were empty except the suffix. `ZipFile.open().read()` and `ZipFile.read()` returned the same bytes or the same exception on every row. `passed` is the report field. Reader-success rows also fail V012 `archive name` (the file stem) and leave V002 `units and scale` and V006 `embedded atlases` as `not_run`.

| Case | Raw output | eof | flush | Raw exception | zipfile open / read | `read_bundle` | V001 | CLI |
|---|---|---|---|---|---|---|---|---|
| `stored` | `b""` (deflate applied to stored bytes) | false | `b""` | none | `b"hi"` | `{a.bin: hi}` | fail: size pass, foreign `a.bin`, FBX count `0`; no `ZIP` | JSON, `passed` false, exit 1, stderr empty |
| `deflate-valid` | `b"hi"` | true | `b""` | none | `b"hi"` | `{a.bin: hi}` | same composition shape, 112 B | JSON, exit 1, stderr empty |
| `deflate-unfinished` | `b"hi"` | false | `b""` | none | `b"hi"` | `{a.bin: hi}` | same shape, 112 B; no `ZIP` | JSON, exit 1, stderr empty |
| `deflate-reserved` | none | false | `b""` | `zlib.error` invalid block type | same `zlib.error` | same `zlib.error` escapes | unexecuted | stdout 0 bytes, stderr 1504, exit 1 |
| `deflate-prefix-1` | `b""` | false | `b""` | none | `BadZipFile` Bad CRC-32 | `BundleError` Broken ZIP member: Bad CRC-32 | fail, only finding `ZIP` | JSON, exit 1, stderr empty |
| `deflate-prefix-2` | `b"h"` | false | `b""` | none | `BadZipFile` Bad CRC-32 | same `BundleError` | fail, only finding `ZIP` | JSON, exit 1, stderr empty |
| `deflate-prefix-3` | `b"hi"` | false | `b""` | none | `b"hi"` | `{a.bin: hi}` | composition fail, 111 B; no `ZIP` | JSON, exit 1, stderr empty |
| `deflate-suffix` | `b"hi"`, `unused_data=00` | true | `b""` | none | `b"hi"` | `{a.bin: hi}` | composition fail, 113 B; no `ZIP` | JSON, exit 1, stderr empty |

A second open of the same frozen files read `ZipExtFile` after `read()`:

| Case | decompressor.eof | unused_data | `_eof` | `_left` | `_compress_left` |
|---|---|---|---|---:|---:|
| `deflate-valid` | true | empty | true | 0 | 0 |
| `deflate-unfinished` | false | empty | true | 0 | 0 |
| `deflate-prefix-1` | false | empty | true | 2 | 0 |
| `deflate-prefix-2` | false | empty | true | 1 | 0 |
| `deflate-prefix-3` | false | empty | true | 0 | 0 |
| `deflate-suffix` | true | `00` | true | 0 | 0 |
| `deflate-reserved` | false | empty | false | 2 | 0 |

`_left` is the uncompressed count still owed. Prefix-1 counted zero uncompressed bytes before the CRC failure. Prefix-2 counted one. The reserved row raised inside `decompress` with `_eof` still false. The stored member was not put through this second table; its zipfile result is the method-0 read of `b"hi"`.

### Why the reader accepts an unfinished stream

`ZipExtFile._read1` in this CPython 3.14.7 file (lines 1179–1195, read here) sets its EOF when `decompressor.eof` is true, or when `_compress_left <= 0` and `unconsumed_tail` is empty. It then calls `flush()` and later CRC-checks only if that EOF flag is set (lines 1122–1123 and 1195). The function does not read `unused_data`. `ZipFile.read` is `open().read()` (lines 1687–1691).

On `cac80400` and on `cbc804`, inflate has already produced `b"hi"` when the compressed bytes run out, so `_left` reaches 0 and the stored CRC matches. `decompressor.eof` stays false. The member is still returned. On the suffix, inflate sets `eof` and parks `00` in `unused_data`; the CRC of `b"hi"` matches, and the extra byte does not become a finding.

`read_bundle` (`src/twinqa/bundle.py`) catches `BadZipFile`, `OSError`, and `EOFError` around `archive.read`, and re-raises `BundleError`. `validate()` catches only `BundleError` and appends one V001 finding `ZIP` (`tools/qa/validate_package.py` lines 199–205). `zlib.error.__mro__` is `zlib.error`, `Exception`, `BaseException`, `object`. The reserved-block traceback from the CLI names `validate` line 200, `read_bundle` line 33, and `_read1` line 1181. That exit 1 is an uncaught exception. It is not `ValidationReport.exit_code`.

Prefix-1 and prefix-2 do reach that handler, because the failure class is `BadZipFile`, not `zlib.error`. Their V001 list is only the `ZIP` finding. `size_status` and `validate_npm_zip` do not run. `passed` is still false: a stage with no findings is `not_run` (`src/twinqa/report.py` `Stage.status`), and `passed` requires every blocking stage to be `pass`.

The raw deflate call on the stored payload `6869` returned empty bytes and `eof` false with no exception. That call is not the ZIP reader. Method 0 returned `b"hi"`.

### What the specifications say, and what was executed

Verified by running, on these eight files: the outputs, `eof`, `unused_data`, `flush`, exception classes, zipfile reads, `read_bundle`, in-process `validate()`, and the npm CLI.

Read in the installed library, not executed as a separate test: `ZipExtFile._read1` EOF and CRC conditions cited above.

Primary text, fetched for this note:

- [RFC 1951 §3.2.3](https://www.rfc-editor.org/rfc/rfc1951): BFINAL is set if and only if this is the last block; BTYPE `11` is reserved (error). The first-byte table above is this run's parse of that layout.
- [Python zlib](https://docs.python.org/3/library/zlib.html): `eof` is a boolean indicating whether the end of the compressed data stream has been reached, and "makes it possible to distinguish between a properly formed compressed stream, and an incomplete or truncated one." `unused_data` holds bytes past the end of the compressed data. `unconsumed_tail` holds data not consumed because it exceeded the uncompressed buffer limit. `zlib.error` is the exception raised on compression and decompression errors. `wbits` from −8 to −15 means a raw stream with no header or trailer.
- [zlib manual](https://www.zlib.net/manual.html): `Z_DATA_ERROR` is defined as −3. `inflate()` returns `Z_STREAM_END` if the end of the compressed data has been reached and all uncompressed output has been produced, and `Z_DATA_ERROR` if the input data was corrupted. The reserved row's message says `Error -3`. The C mapping from `Z_STREAM_END` onto `decompressobj.eof` is not in this Windows install; the `eof` values in the table are observed, and the manual sentence is the library's description of stream end. The Adler-32 trailer check in that `inflate()` paragraph applies to zlib-wrapped data. These rows are raw DEFLATE (`wbits=-15`), so the ZIP CRC is a separate field.
- [zipfile, Python 3.14](https://docs.python.org/3.14/library/zipfile.html): `ZipInfo.CRC` is the CRC-32 of the uncompressed file. `ZipFile.testzip` reads the members and checks their CRCs and headers. The pitfalls section says decompression may fail due to an incorrect CRC checksum, the ZIP format, or an unsupported method. The per-read CRC compare that fired on prefix-1 and prefix-2 is the source read above, not a sentence in that `read()` paragraph.

PKG-01 and PKG-02 (`docs/domain/areas/package.md`) send "no broken or unreadable files" through V001 `read_bundle`. The V001 inventory in `docs/domain/validation.md` attributes CRC handling to that function. `docs/PROJECT_STATE.md` does not record a passed delivery. Those rows match the Bad CRC path. They do not describe the `zlib.error` path, which never builds the report.

## How it applies to this repository

`src/twinqa/bundle.py` `read_bundle` is the V001 reader. A CRC failure inside `ZipFile.read` becomes `BundleError` and one finding named `ZIP`. A `zlib.error` from the same `archive.read` does not. `tools/qa/validate_package.py` `main` does not catch it, so `--json` prints nothing.

`ZipExtFile._read1` treats "compressed bytes exhausted and no `unconsumed_tail`" as EOF even when `decompressor.eof` is false, then accepts the member when the uncompressed CRC matches. That is why `cac80400` and `cbc804` are reader-success rows. Composition checks then fail the synthetic archive in the ordinary way (`foreign files`, `FBX count`), and `passed` stays false. `src/twinqa/report.py` `exit_code` is 1 when any finding is `fail`. The reserved row never gets that far.

`docs/research/capability-roadmap.md` §7.8 is still L2-partial for export, package, and validation. Issue #149 is open and labeled `roadmap`. This note does not add a check and does not change PKG-01 or PKG-02.

## Proposed next tasks

1. **Pin the rows that already return a report, including unfinished and trailing payloads.** Size S. Test-only, against `twinqa.bundle.read_bundle` and `validate()` with `--profile npm` and no `--scene`. Value: a later edit can see CRC-matching unfinished bytes as a successful read, and can see the short prefixes as the existing V001 `ZIP` finding. Effort is one test module and the frozen hex. Advances #149. Input `deflate-valid.zip` → member `a.bin` is `b"hi"` and raw `eof` is true → V001 has `foreign files` and `FBX count`, no finding named `ZIP`, `passed` false, exit 1. Input `deflate-unfinished.zip` (`cac80400`) and `deflate-prefix-3.zip` (`cbc804`) → the same member bytes, raw `eof` false, and the same V001 shape. Input `deflate-suffix.zip` → member `b"hi"`, raw `eof` true, `unused_data` `00`, no `ZIP` finding. Input `deflate-prefix-1.zip` and `deflate-prefix-2.zip` → `BundleError` whose message contains `Bad CRC-32 for file 'a.bin'` → V001 finding `ZIP` only, JSON, exit 1, empty stderr.

2. **Route `zlib.error` from `archive.read` into the existing V001 `ZIP` finding.** Size S. In `src/twinqa/bundle.py` only, catch `zlib.error` beside the current `BadZipFile` / `OSError` / `EOFError` tuple and re-raise `BundleError` with the current `Broken ZIP member:` prefix. Leave CRC, method, and encryption policy as they are. Value: a reserved block shows up as a report instead of a traceback. Effort is one handler plus the input below. This note does not adopt that handler. Advances #149. Input `deflate-reserved.zip` (payload `07`) → `BundleError` containing `invalid block type` → V001 `ZIP` fail, JSON object, exit 1, empty stderr. Input `deflate-valid.zip` → `a.bin` still `b"hi"`, and the composition findings stay.

## Open questions

- Should a raw stream with `eof` false and CRC-matching output (`cac80400`, and the prefix `cbc804`) count as unreadable? This note does not choose.
- Should bytes left in `unused_data` after a finished stream (`cbc80400` plus `00`) count as unreadable? This note does not choose.
- Should `zlib.error` use the same V001 `ZIP` finding as a bad CRC? Normalizing that exception is a user decision. This note does not adopt it.
- Prefix-1 and prefix-2 already become a CRC finding without a `zlib.error`. A completeness rule and the existing CRC rule are not the same lever.
- `zlib.decompress()` (the one-shot function) was not called. The C file that sets `decompressobj.eof` from `Z_STREAM_END` was not in the install. Development C001, encryption, and method policy were out of scope.

## Reproduction

Synthetic bytes only. Writes `C:/x/t_e0e95577/*.zip` and prints one JSON object per case. Run from the worktree with `uv run python`. The script freezes the files and the manifest first, checks the hashes, then probes.

```python
import hashlib, json, struct, subprocess, sys, zipfile, zlib
from pathlib import Path
REPO = Path(r"C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_e0e95577")
OUT = Path(r"C:/x/t_e0e95577")
NAME, CRC = b"a.bin", zlib.crc32(b"hi") & 0xFFFFFFFF
VALID = bytes.fromhex("cbc80400")
CASES = [
    ("stored", 0, b"hi"),
    ("deflate-valid", 8, VALID),
    ("deflate-unfinished", 8, bytes.fromhex("cac80400")),
    ("deflate-reserved", 8, bytes.fromhex("07")),
    ("deflate-prefix-1", 8, VALID[:1]),
    ("deflate-prefix-2", 8, VALID[:2]),
    ("deflate-prefix-3", 8, VALID[:3]),
    ("deflate-suffix", 8, VALID + b"\x00"),
]
def build(method, payload):
    local = struct.pack("<4sHHHHHIIIHH", b"PK\x03\x04", 20, 0, method, 0, 0x0021,
                        CRC, len(payload), 2, len(NAME), 0) + NAME + payload
    central = struct.pack("<4sHHHHHHIIIHHHHHII", b"PK\x01\x02", 20, 20, 0, method, 0, 0x0021,
                          CRC, len(payload), 2, len(NAME), 0, 0, 0, 0, 0, 0) + NAME
    eocd = struct.pack("<4sHHHHIIH", b"PK\x05\x06", 0, 0, 1, 1, len(central), len(local), 0)
    return local + central + eocd
OUT.mkdir(parents=True, exist_ok=True)
frozen = {}
for name, method, payload in CASES:
    blob = build(method, payload)
    (OUT / f"{name}.zip").write_bytes(blob)
    frozen[name] = hashlib.sha256(blob).hexdigest()
(OUT / "manifest.json").write_text(json.dumps(frozen), encoding="utf-8")
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools" / "qa")]
from twinqa.bundle import read_bundle
from twinqa.profiles import load_profiles
import validate_package as vp
profiles = load_profiles()
for name, method, payload in CASES:
    path = OUT / f"{name}.zip"
    if hashlib.sha256(path.read_bytes()).hexdigest() != frozen[name]:
        raise SystemExit(name)
    dec = zlib.decompressobj(-15)
    try:
        out, err = dec.decompress(payload), None
    except Exception as exc:
        out, err = None, f"{type(exc).__qualname__}: {exc}"
    try:
        dec.flush()
    except Exception as exc:
        err = f"{err}; flush {type(exc).__qualname__}: {exc}"
    try:
        got = {k: v.hex() for k, v in read_bundle(path, 4 * 10**9).items()}
    except Exception as exc:
        got = f"{type(exc).__qualname__}: {exc}"
    proc = subprocess.run([sys.executable, str(REPO / "tools/qa/validate_package.py"),
                           str(path), "--profile", "npm", "--json"], cwd=REPO, capture_output=True)
    print(json.dumps({"name": name, "raw": None if out is None else out.hex(), "eof": dec.eof,
                      "unused": dec.unused_data.hex(), "err": err, "bundle": got,
                      "cli_exit": proc.returncode, "cli_json": proc.stdout[:1] == b"{",
                      "stderr_empty": proc.stderr == b""}))
```

## Sources

15 sources: `docs/domain/areas/package.md` (PKG-01/02); `docs/domain/validation.md` (V001 inventory); `docs/PROJECT_STATE.md`; `docs/research/capability-roadmap.md` §7.8; PR [#675](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/675) report at `f05cf43647ee1485a1a9a878fee8aa788c0b8ccc`; `src/twinqa/bundle.py`; `tools/qa/validate_package.py`; `src/twinqa/report.py`; CPython 3.14.7 `Lib/zipfile/__init__.py`; [zipfile 3.14](https://docs.python.org/3.14/library/zipfile.html); [zlib](https://docs.python.org/3/library/zlib.html); [zlib manual](https://www.zlib.net/manual.html); [RFC 1951](https://www.rfc-editor.org/rfc/rfc1951); open issue [#149](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/149) (`gh issue list --label roadmap`); the frozen corpus under `C:/x/t_e0e95577/` (`manifest.json`, `probe_results.json`, `stderr-deflate-reserved.txt`).
