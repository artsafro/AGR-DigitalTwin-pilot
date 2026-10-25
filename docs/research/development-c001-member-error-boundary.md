# Development C001 member error boundary

delivery_passed=false

## Summary

Synthetic one-member ZIPs only. Source commit `5c6098b8226cac3d04de39ce00f514914c7f118f` (worktree `ORIG_HEAD` and `logs/HEAD`; `git` was not run). `docs/research/zip-member-error-report-boundary.md` is not in this worktree, so the five archives were built here and checked with `zipfile` before any `dt_ai` call.

Through `dt_ai.publish.bundle.read_bundle` → `dt_ai.validate.bundle.validate(..., blender=None)` → a fresh-process `dt validate`, a no-password general-purpose flag bit 0 and compression method 1 both raise. `validate` does not record C001, and the fresh output directory is absent (`report.json` and `report.html` are absent). The CLI exits 1. Stderr is a single `ERROR:` line and stdout is empty. `NotImplementedError` is a `RuntimeError` subclass, so `main` catches both.

Stored and deflated `a.bin = b'hi'` are read back as those two bytes. C001 then fails because `bundle-manifest.json` is missing, and both report files are written. A bad CRC is a handled `BadZipFile`: C001 fail, both report files, CLI exit 1. That missing-manifest fail is a contract miss on a readable archive. The bad-CRC row is a handled control. Neither row is a successful development validation. `passed` on every written report is false.

CPython 3.14.7, zlib compile and runtime `1.3.1.zlib-ng`. No import failure. Pytest and the V001 matrix were not run.

## Findings

### Result table (verified by running)

| Row | Reader `read_bundle` | `validate(..., blender=None)` | CLI exit | Artifacts in a new output directory |
|---|---|---|---|---|
| `stored-a-bin` | returns `{"a.bin": b"hi"}` | C001 `fail`, observed `'bundle-manifest.json'`; `passed=false`; `development_checks_passed=false` | 1 | `report.json`, `report.html` |
| `deflated-a-bin` | returns `{"a.bin": b"hi"}` | same C001 `fail` and the same two booleans | 1 | `report.json`, `report.html` |
| `bad-crc` | `BadZipFile: Bad CRC-32 for file 'a.bin'` | C001 `fail`, observed `Bad CRC-32 for file 'a.bin'`; same two booleans | 1 | `report.json`, `report.html` |
| `flag-bit0-encrypted-no-password` | `RuntimeError: File 'a.bin' is encrypted, password required for extraction` | same `RuntimeError`; no report object | 1 | directory absent |
| `method-1-local-and-central` | `NotImplementedError: That compression method is not supported` | same `NotImplementedError`; no report object | 1 | directory absent |

CLI stdout for the three report rows is `Report: <output>\report.json; development_checks_passed=False; delivery_passed=False` and stderr is empty. CLI stdout for the flag-bit-0 row is empty; stderr is `ERROR: File 'a.bin' is encrypted, password required for extraction`. CLI stdout for method 1 is empty; stderr is `ERROR: That compression method is not supported`. No traceback is on either CLI stderr. Each exception's `__cause__` is none.

Each written report has 18 checks: C001 `fail`, plus 14 `not_run` and 3 `review`. The early C001 return means C002–C004 are not in that report. `ValidationReport.passed` is false on the three written JSON files.

Corpus SHA-256 was unchanged across the in-process probe and across the CLI probe (hashes taken before and after each script). `DT_BLENDER` was unset in the in-process probe and absent from the CLI child environment. No `--blender` argument was passed. `validate` was called with `blender=None`.

### Frozen corpus (synthetic)

Payload `b"hi"` (hex `6869`), CRC-32 `3633523372` (`0xD8932AAC`), SHA-256 `8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4`. One member name `a.bin`. Flag bit 0 means the encrypted bit (`zipfile._MASK_ENCRYPTED = 1 << 0`). Method 1 is the shrink method number; the payload bytes stay plaintext `6869`. These are not password-encrypted files.

| File | Length | SHA-256 | Local flag / method | Central flag / method | Payload hex |
|---|---:|---|---|---|---|
| `stored-a-bin.zip` | 110 | `02fc9aed515b0c187fd6c267773e14725f47eb1fc86572c71233058f31c857af` | 0 / 0 | 0 / 0 | `6869` |
| `deflated-a-bin.zip` | 112 | `ab9860e6d351c30c06214c44cfdc2136de0d31373ade8145ae0aabd82a654056` | 0 / 8 | 0 / 8 | `cbc80400` |
| `bad-crc.zip` | 110 | `025ae2b05ddeba0e5196a973a8c3b51ca9646e9757db92ba09bdcdbe9db9ae2f` | 0 / 0 | 0 / 0 | `6869` |
| `flag-bit0-encrypted-no-password.zip` | 110 | `39ca305de460274e79ecc75915625a4d6f067037e02fb9a89fb0b12d4682b50d` | 1 / 0 | 1 / 0 | `6869` |
| `method-1-local-and-central.zip` | 110 | `a78539b40a95921e9705856920d2ad721cbabc1d1f5cfc95811b10727fe49a57` | 0 / 1 | 0 / 1 | `6869` |

`bad-crc` stores CRC `661443923` (`0x276CD553`, the bitwise complement of the payload CRC) in both the local and central headers. `zipfile.ZipFile.read` on that file raises `BadZipFile`. On the flag-bit-0 file it raises `RuntimeError`. On the method-1 file it raises `NotImplementedError`. `infolist()` opens all five. Manifest SHA-256 `7b2de8c11e1432f4379aaf959a891fa7750ad2c51ef3d74dd1bf2c6c40f954bc` (6968 bytes, the freeze script's JSON).

### Where the exception leaves the development path

Verified by reading these lines and by the runs above.

`src/dt_ai/publish/bundle.py:27-36` `read_bundle` checks member names and the 256 MB uncompressed sum, then calls `ZipFile.read`. It has no handler of its own. The runs raise at line 36.

`src/dt_ai/validate/bundle.py:36-55` calls that reader inside C001. The handler at line 52 is `(ValueError, KeyError, OSError, TypeError, BadZipFile)`. `RuntimeError` and `NotImplementedError` are outside that tuple, so they leave `validate` before `finish`. `finish` (`src/dt_ai/validate/bundle.py:179-200`) is what creates the output directory and writes `report.json` and `report.html` (`src/dt_ai/core/io.py:16-18` creates the parent). A missing `bundle-manifest.json` is the `KeyError` at line 38; `str` of that `KeyError` is the C001 observed text `'bundle-manifest.json'`.

`src/dt_ai/cli/main.py:88-92` registers `dt validate` with required `--archive`, optional `--output`, and `--blender` defaulting to `os.environ.get("DT_BLENDER")`. Lines 289-296 resolve the output directory, call `validate`, print `delivery_passed=False`, and return 1 when any check status is `fail`. Lines 298-300 catch `(ValueError, OSError, RuntimeError)`, print `ERROR: {exc}` to stderr, and return 1. The running interpreter's MRO is `NotImplementedError` → `RuntimeError` → `Exception`, so method 1 is caught there too. That is why the CLI exit code is 1 with an `ERROR` line and with no report files.

Stdlib, this interpreter, read-only: encrypted flag with no password raises at `zipfile/__init__.py:1794` before a decompressor is built. Method 1 reaches `_check_compression` and raises at `zipfile/__init__.py:851`. A member that set both flag bit 0 and method 1 was not built. The source order checks the flag first.

`src/dt_ai/core/models.py:144-150` fixes `ValidationReport.passed` to `False`. The CLI string `delivery_passed=False` is printed at `src/dt_ai/cli/main.py:292`. It is not a separate JSON field.

Source SHA-256 at this commit: `publish/bundle.py` `446f4b665772ebaf5ad31300512f3a4f544a8d66ef6ed4449cb4ad1a800ba024`; `validate/bundle.py` `f02a83cd99bbca43b1680d30d84b81ae65e6bf3caec2389cb9080d67fc42d484`; `cli/main.py` `c4bbe3ad4496936934b01ca2d39cd8778ac741a3568c03e541e300cc00fb4303`; `models.py` `e6012dc2c169b9fd3de97d4e3a9b899789cde14ebf6ae6f612f0f836c3085f70`; `io.py` `5b0014c84518291fee3646fde983b7f4d91513561779512cc2354fb695bc92c0`.

The task text for #675 says the V001 `read_bundle` path emits a traceback and exit 1 with no report. That V001 path was not executed here. On this development CLI path the same two exception classes produce exit 1 and no report files, and stderr is the `ERROR` line above.

### Commands

In-process, from the worktree, after the corpus existed:

```text
uv run python C:\x\t_a94a3bee\probe_api.py
```

Each `validate` output was `C:\x\t_a94a3bee\probe-api\validate-out\<row>` and did not exist beforehand.

CLI, one fresh process per row, child environment without `DT_BLENDER`, cwd the worktree:

```text
uv run dt validate --archive C:\x\t_a94a3bee\corpus\<row>.zip --output C:\x\t_a94a3bee\probe-cli\validate-out\<row>
```

### Bounded reproduction

```python
import hashlib, json, os, subprocess, sys
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO

REPO = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_a94a3bee")
HEX = {
    "stored-a-bin": "504b03041400000000000000215cac2a93d8020000000200000005000000612e62696e6869504b010214001400000000000000215cac2a93d80200000002000000050000000000000000000000800100000000612e62696e504b0506000000000100010033000000250000000000",
    "deflated-a-bin": "504b03041400000008000000215cac2a93d8040000000200000005000000612e62696ecbc80400504b010214001400000008000000215cac2a93d80400000002000000050000000000000000000000800100000000612e62696e504b0506000000000100010033000000270000000000",
    "bad-crc": "504b03041400000000000000215c53d56c27020000000200000005000000612e62696e6869504b010214001400000000000000215c53d56c270200000002000000050000000000000000000000800100000000612e62696e504b0506000000000100010033000000250000000000",
    "flag-bit0-encrypted-no-password": "504b03041400010000000000215cac2a93d8020000000200000005000000612e62696e6869504b010214001400010000000000215cac2a93d80200000002000000050000000000000000000000800100000000612e62696e504b0506000000000100010033000000250000000000",
    "method-1-local-and-central": "504b03041400000001000000215cac2a93d8020000000200000005000000612e62696e6869504b010214001400000001000000215cac2a93d80200000002000000050000000000000000000000800100000000612e62696e504b0506000000000100010033000000250000000000",
}
EXPECT = {
    "stored-a-bin": "02fc9aed515b0c187fd6c267773e14725f47eb1fc86572c71233058f31c857af",
    "deflated-a-bin": "ab9860e6d351c30c06214c44cfdc2136de0d31373ade8145ae0aabd82a654056",
    "bad-crc": "025ae2b05ddeba0e5196a973a8c3b51ca9646e9757db92ba09bdcdbe9db9ae2f",
    "flag-bit0-encrypted-no-password": "39ca305de460274e79ecc75915625a4d6f067037e02fb9a89fb0b12d4682b50d",
    "method-1-local-and-central": "a78539b40a95921e9705856920d2ad721cbabc1d1f5cfc95811b10727fe49a57",
}

def main():
    os.environ.pop("DT_BLENDER", None)
    sys.path.insert(0, str(REPO))
    from dt_ai.publish.bundle import read_bundle
    from dt_ai.validate.bundle import validate
    scratch = Path(r"C:/x/t_a94a3bee/repro")
    for name, hex_text in HEX.items():
        blob = bytes.fromhex(hex_text)
        assert hashlib.sha256(blob).hexdigest() == EXPECT[name]
        with ZipFile(BytesIO(blob)) as z:
            info = z.infolist()[0]
            print("fields", name, info.flag_bits, info.compress_type, info.CRC, info.file_size)
        archive = scratch / "in" / f"{name}.zip"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(blob)
        try:
            print("reader", name, {k: v.hex() for k, v in read_bundle(archive).items()})
        except Exception as exc:
            print("reader", name, type(exc).__name__, exc)
        out = scratch / "out" / name
        assert not out.exists()
        try:
            report = validate(REPO, archive, out, blender=None)
            c001 = next(c for c in report.checks if c.id == "C001")
            print("validate", name, c001.status, c001.observed, report.passed, out.is_dir())
        except Exception as exc:
            print("validate", name, type(exc).__name__, exc, out.exists())
        env = os.environ.copy()
        env.pop("DT_BLENDER", None)
        cli_out = scratch / "cli" / name
        assert not cli_out.exists()
        proc = subprocess.run(
            ["uv", "run", "dt", "validate", "--archive", str(archive), "--output", str(cli_out)],
            cwd=REPO, env=env, capture_output=True, text=True)
        print("cli", name, proc.returncode, proc.stdout, proc.stderr, cli_out.exists())

if __name__ == "__main__":
    main()
```

## How it applies to this repository

Development bundles use `src/dt_ai/publish/bundle.py` and C001 in `src/dt_ai/validate/bundle.py`. The CLI entry is `dt validate` in `src/dt_ai/cli/main.py`. Customer package V001 is a different reader, `src/twinqa/bundle.py`, described in `docs/domain/validation.md`. This note does not measure that reader.

`docs/domain/validation.md` states that C001–C004 are synthetic development checks and that a synthetic report leaves official delivery stages `not_run` or `review`. The three written reports match that: `passed` is false, and the extra findings are `not_run` or `review`.

`tests/test_development_bundle_integrity.py` is not in this worktree. This note adds no test and does not change that queued file.

Whether `RuntimeError` and `NotImplementedError` should be wrapped into a C001 finding is left to the user. This note adopts no encryption policy and no compression-method policy.

## Proposed next tasks

1. **Pin the measured boundary in a new test file.** Value: a later edit can see that these two inputs still produce no report. Effort **S**. Do not edit `tests/test_development_bundle_integrity.py`. Input `flag-bit0-encrypted-no-password` hex above → `read_bundle` and `validate(..., blender=None)` raise `RuntimeError` with message `File 'a.bin' is encrypted, password required for extraction`, and the fresh output directory does not exist. Input `method-1-local-and-central` hex → `NotImplementedError` with message `That compression method is not supported`, directory absent. Input `bad-crc` hex → a report object, C001 `fail`, observed `Bad CRC-32 for file 'a.bin'`, `passed` false, both `report.json` and `report.html` present. CLI on the flag-bit-0 file, `DT_BLENDER` unset, no `--blender` → exit 1, stdout empty, stderr `ERROR: File 'a.bin' is encrypted, password required for extraction\n`, output directory absent. `Archive: no roadmap link`

2. **Record the user's choice as a contract, and implement only that choice.** Value: exit code 1 alone does not show whether a report was written. Effort **S**. Leave the choice open until the user makes it. If the choice is to wrap both exceptions into the existing C001 handler, the flag-bit-0 input must return C001 `fail` with observed `File 'a.bin' is encrypted, password required for extraction`, and the method-1 input must return C001 `fail` with observed `That compression method is not supported`. Both write `report.json` and `report.html`, `passed` false, `development_checks_passed` false. The CLI then prints the `Report:` line, leaves stderr empty, and exits 1. If the choice is to keep today's behavior, the outputs stay those in the table. Supporting decryption, or rejecting every method other than store and deflate, is a separate decision and is not part of this proposal. `Archive: no roadmap link`

`gh` was not run. Docs in this worktree contain no open roadmap issue whose subject is this C001 member boundary. #675 is the question id from the task card and was not found as text in `docs/`.

## Open questions for the user

- Should `RuntimeError` (encrypted flag, no password) and `NotImplementedError` (method 1) become a failed C001 report, or stay process errors with no output files?
- Should development bundles reject an encrypted flag and compression methods other than store (0) and deflate (8) as a stated policy? This note does not adopt that policy.
- Should a follow-up be linked to #675, or to another roadmap issue? The issue list was not queried.
