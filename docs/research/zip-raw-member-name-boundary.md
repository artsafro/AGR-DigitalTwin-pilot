# ZIP raw member-name boundary — t_797b79e9

## Summary

Research only. Every archive below is synthetic. No production code, tests, standards, or delivery was changed. `docs/research/zip-member-error-report-boundary.md` is not in this worktree; this note follows the requested sections and the measurement style of the other `docs/research` boundary notes.

Verified by running on the project venv, CPython 3.14.7, win32: when the local header and the central directory carry the same raw name `a.bin` + NUL + `../escape`, `zipfile` keeps that full string on `ZipInfo.orig_filename` and stores only `a.bin` on `ZipInfo.filename`. It does not reject the member. `ZipFile.read("a.bin")` returns the payload bytes. `ZipFile.read` of the raw string raises `KeyError`, because the lookup map is keyed by the truncated name. Neither call extracts to disk.

The official V001 path uses `ZipInfo.filename` (`src/twinqa/bundle.py`). It accepts that member as `a.bin`. The development reader uses `ZipInfo.orig_filename` (`src/dt_ai/publish/bundle.py`) and raises `ValueError: Unsafe ZIP path` before any read. The CLI report for that archive then fails on NPM content (`foreign files: a.bin`, FBX count), with `passed` false and no `../escape` or NUL in the JSON. The unsafe suffix is discarded from the identity V001 checks. It is checked by the development reader. It is not rejected by `zipfile` when both headers match.

A suffix that exists in only one of the two headers is a different fact: `zipfile` raises `BadZipFile` on read because the decoded local name must equal `orig_filename`. V001 wraps that as `BundleError` / finding `ZIP`. The development reader raises `ValueError` when the central name contains NUL, and lets `BadZipFile` escape when only the local name contains the suffix.

Sixteen synthetic archives, all input SHA-256 unchanged after the probes. None is a passing delivery: every CLI JSON has `passed: false`, `exit_code: 1`, process exit 1, empty stderr. Full rows: `C:/x/t_797b79e9/results.json` (SHA-256 `b3113ac08fc24589519b338e2b3d9b3e00859de16333b0443f742de1fa7a4be4`).

## Findings

### What each reader validates

Official read, used by V001, keeps non-directories and checks `filename` only. There is no NUL test and no case-fold. The return is inside the CRC `try` at line 33:

```21:28:src/twinqa/bundle.py
        infos = [x for x in archive.infolist() if not x.is_dir()]
        names = [x.filename for x in infos]
        if len(names) != len(set(names)):
            raise BundleError("Duplicate ZIP members")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise BundleError(f"Unsafe ZIP path: {name}")
```

```33:33:src/twinqa/bundle.py
            return {name: archive.read(name) for name in names}
```

`tools/qa/validate_package.py` calls that function with a 4 GB uncompressed cap. `BundleError` becomes one V001 finding `ZIP` and returns before size and content checks. A successful read continues into archive size and NPM/VPM composition:

```198:205:tools/qa/validate_package.py
        try:
            files = read_bundle(target, max_uncompressed=4 * 10**9)
        except BundleError as exc:
            kind = kind or "vpm"
            st = build_stages(profiles, kind)
            st["V001"].findings.append(finding("fail", "ZIP", str(exc), "readable ZIP, safe paths", st["V001"].source_pdf_pages))
            return report(target, data, kind, profiles, st, notes)
```

A successful read continues at lines 216–218 into archive size and then NPM or VPM composition. Those later findings are not the path gate.

The development reader validates `orig_filename`, including NUL and `casefold` duplicates, and does not skip directories. It does not catch `BadZipFile`. The NUL clause and the raw-name comment are:

```6:13:src/dt_ai/publish/bundle.py
    seen = set()
    for name in names:
        p = PurePosixPath(name)
        if not name or "\x00" in name or p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
            raise ValueError("Unsafe ZIP path")
        key = name.casefold()
        if key in seen:
            raise ValueError("Duplicate ZIP members")
```

```31:36:src/dt_ai/publish/bundle.py
        # ZipInfo.filename normalizes backslashes on Windows; validate raw names.
        names = [x.orig_filename for x in infos]
        _validate_member_names(names)
        if sum(x.file_size for x in infos) > 256_000_000:
            raise ValueError("Development bundle exceeds 256 MB uncompressed safety limit")
        return {name: archive.read(name) for name in names}
```

The existing safety test assigns `ZipInfo.filename` after construction so raw NUL and backslash bytes survive, and it asserts `ValueError` from the development reader only (`tests/test_bundle_package_safety.py` lines 70–94, import on lines 5–7). It does not call `twinqa.bundle.read_bundle` or the V001 CLI.

CPython 3.14.7 `zipfile` (file SHA-256 `adb6f48ee990b42cabfc665d910992c5a30cee31d5d50d846e18e0e45c6a3f31`) truncates `filename` at the first NUL and rewrites `os.sep` / `os.altsep` to `/` (`_sanitize_filename`, lines 404–420). `ZipInfo.__init__` stores the constructor string on `orig_filename` before that sanitize (lines 450–457). The central-directory parser builds `ZipInfo` from the decoded central name and indexes `NameToInfo[x.filename]` (lines 1573–1601). On read, the decoded local name must equal `orig_filename` (lines 1762–1771). `_encodeFilenameFlags` encodes `self.filename`, not `orig_filename` (lines 568–576), so assigning `.filename` after `ZipInfo("placeholder")` is what writes the raw bytes. `is_dir` is true when `filename` ends with `/` or, on Windows, with `\` (lines 687–697). It does not consult the DOS directory attribute.

`PurePosixPath("..\\escape").parts` is a single part, so `".." in parts` is false. The development reader's backslash clause is what rejects that raw string. After Windows sanitize, the same bytes become `../escape`, and the official reader rejects that normalized string because `..` is a part. Verified by running both, not only by reading `PurePosixPath`.

### Corpus and runtime

Authoritative interpreter: `C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.venv\Scripts\python.exe`, CPython 3.14.7, shapely 2.1.2 present because `validate_package.py` imports `twinqa.scene` at import time. An earlier attempt on CPython 3.13.3 stopped at `ModuleNotFoundError: shapely` before any ZIP check. That attempt is not evidence about V001. The CLI was `py` via the venv executable: `tools/qa/validate_package.py <zip> --profile npm --json`, no `--scene`. Notes in every JSON were `[]`. Profile `vpm` was not executed. The accept/reject of the member name happens in `read_bundle` before `validate_npm_zip` / `validate_vpm_zip`, so the reader rows below are the V001 path gate. NPM findings after a successful read are composition, recorded separately.

Source SHA-256 at probe time:

| File | SHA-256 |
|---|---|
| `src/twinqa/bundle.py` | `679590acd8aab710ac15c02852cd314cbf0f8c62d7f67f01d75bd072a283d60a` |
| `src/dt_ai/publish/bundle.py` | `446f4b665772ebaf5ad31300512f3a4f544a8d66ef6ed4449cb4ad1a800ba024` |
| `tools/qa/validate_package.py` | `c751fc797222a15030907c3e3ca98029eb92d56f563ae78a274d72327b7de944` |
| `tests/test_bundle_package_safety.py` | `dbc5aea58d2455a42dea26bfd8308e0a98cdcc30702264cbcd40a174b327ce33` |

Fourteen archives were built by `ZipInfo("placeholder")` then `info.filename = name` then `writestr`, ZIP stored. An independent parser of the local header and the central directory found those raw name bytes equal to `name.encode("ascii")` in both headers (`raw_equals_assigned` true, flag bits 0). Two further archives were built with `struct` so the local name and the central name differ on purpose. General-purpose flag bit 11 (UTF-8) was 0. No data descriptors. No `extract` or `extractall`.

Payload SHA-256 (empty directory payload is the empty-string hash):

| Payload bytes | SHA-256 |
|---|---|
| `payload-safe` | `a9792369b5d2caa60674a82d1a694e50eab72e8cb94e1a065a0ab8161f892b22` |
| `payload-dup-1` | `e4d9d4ce83897004618e5b2f46b7638bdaee04f708dfa4d850bee93681c82c20` |
| `payload-dup-2` | `907836609b5429c0ab1c4a0bfaccce2a2fe63a8387e9516038842f609eed2c3f` |
| `payload-lower` | `28f03c2cbac882c5ba2065ee8453effbbce2faa5a75dc328995db02d07b5443c` |
| `payload-upper` | `e5ca7be0e1c3061fa548bdd9e237c04c2f180300645de12d6e6e9216071b5eee` |
| `payload-lead` | `2d23b5fb8ba8a2705dc54c27d3fb18028b2d819f3795d5a663aa579422dee086` |
| `payload-mid` | `8b825c8325298c1336dc4e1a67ddc27ee9db63ac08d05f907f72a041e613776c` |
| `payload-trail` | `138b5dce354ef078c12341b41ffe6bde79c1ce481ea1720185936339475d0862` |
| `payload-suffix` | `2c4a464e116cb01659fd8bbbe81ad042963c78b4428fafcb6d7426c986a412df` |
| `payload-bs` | `5001595da002dc6b345ffda65cd0decedbb6cfe4f336408652cfda60de2af137` |
| `payload-bs-dot` | `60d6f441d6089bf8bba23a5b7e6a2d8e6890d28fd6932d4219e9c10f05ff3b76` |
| `payload-dot` | `5a048b7ad11f62a0863ae9f4c00fab5cdc0203e261895e7fc6654176b7b95461` |
| empty | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `payload-mismatch` | `d641ea6b3d8d71883a5d9d4f89e99ccb1263ba1e453c45793b0021b2803ac971` |

Raw name `a.bin` SHA-256 `4fef9cffec13baaa0b8bab5ae61005c5ee8bdb7880b255d60c27e8b7b45202ba`. Raw name `a.bin` + NUL + `../escape` (hex `612e62696e002e2e2f657363617065`) SHA-256 `1960b2a5d32c32b6724575ea60fcd61b8597fe759b2e1c74266e8f23bdab9fb2`.

### Per-case results

`ZipFile` column is `archive.read`, in memory. `twinqa` is `twinqa.bundle.read_bundle`. `dev` is `dt_ai.publish.bundle.read_bundle`. V001 "path" means a finding named `ZIP`. "content" means `read_bundle` returned and V001 then failed NPM composition. Every row: stderr empty, `passed` false, process exit 1, JSON `exit_code` 1, input hash unchanged. `../escape` appears in the CLI stdout only for `backslash_dotdot`, `explicit_dotdot`, and the two header-mismatch cases.

| Case | Raw local = central | `filename` / `orig_filename` / `is_dir` | `ZipFile.read(filename)` | twinqa | dev | V001 |
|---|---|---|---|---|---|---|
| `safe_a_bin` | yes, `a.bin` | `a.bin` / `a.bin` / no | payload-safe | returns `a.bin` | returns `a.bin` | content: foreign `a.bin`, FBX count 0; size pass |
| `exact_duplicate` | yes, `a.bin` twice | both `a.bin`; write `UserWarning: Duplicate name: 'a.bin'` | second payload only (`payload-dup-2`) | `BundleError` Duplicate ZIP members | `ValueError` Duplicate ZIP members | path: `Duplicate ZIP members` |
| `case_pair` | yes, `a.bin` and `A.bin` | same strings, not dirs | both payloads | returns both keys | `ValueError` Duplicate ZIP members | content: foreign `A.bin, a.bin` |
| `leading_nul` | yes, `\x00../escape` | `""` / `\x00../escape` / no | payload-lead; `read(orig)` `KeyError` | returns `""` | `ValueError` Unsafe ZIP path | content: foreign observed empty; no suffix text |
| `middle_nul` | yes, `a\x00../escape` | `a` / full / no | payload-mid; `read(orig)` `KeyError` | returns `a` | `ValueError` Unsafe ZIP path | content: foreign `a` |
| `trailing_nul` | yes, `a.bin\x00` | `a.bin` / `a.bin\x00` / no | payload-trail; `read(orig)` `KeyError` | returns `a.bin` | `ValueError` Unsafe ZIP path | content: foreign `a.bin` |
| `nul_unsafe_suffix` | yes, `a.bin\x00../escape` | `a.bin` / full / no | payload-suffix; `read(orig)` `KeyError` | returns `a.bin` | `ValueError` Unsafe ZIP path | content: foreign `a.bin`; suffix absent from JSON |
| `backslash` | yes, `sub\a.bin` | `sub/a.bin` / `sub\a.bin` / no | payload-bs; `read(orig)` `KeyError` | returns `sub/a.bin` | `ValueError` Unsafe ZIP path | content: foreign `sub/a.bin` |
| `backslash_dotdot` | yes, `..\escape` | `../escape` / `..\escape` / no | payload-bs-dot would be readable by filename; readers do not return it | `BundleError` `Unsafe ZIP path: ../escape` | `ValueError` Unsafe ZIP path | path: `Unsafe ZIP path: ../escape` |
| `explicit_dotdot` | yes, `../escape` | same / same / no | bytes available to `ZipFile.read` | `BundleError` `Unsafe ZIP path: ../escape` | `ValueError` Unsafe ZIP path | path: `Unsafe ZIP path: ../escape` |
| `dir_safe` | yes, `nested/` | `nested/` / same / yes | empty payload | returns `{}` | returns `nested/` | content: FBX count 0; directory key omitted |
| `dir_unsafe` | yes, `../escape/` | same / same / yes | empty payload from `ZipFile.read` | returns `{}` | `ValueError` Unsafe ZIP path | content: FBX count 0; name absent from JSON |
| `dir_nul_suffix` | yes, `nested/\x00../escape` | `nested/` / full / yes | empty via `nested/`; `read(orig)` `KeyError` | returns `{}` | `ValueError` Unsafe ZIP path | content: FBX count 0; suffix absent |
| `dir_unsafe_plus_file` | yes, `a.bin` and `../escape/` | file not dir; directory is dir | both byte strings readable | returns only `a.bin` | `ValueError` Unsafe ZIP path | content: foreign `a.bin`; directory name absent |
| `mismatch_central_has_suffix` | local `a.bin`, central `a.bin\x00../escape` | `a.bin` / full / no | `BadZipFile` names differ; `read(orig)` `KeyError` | `BundleError` Broken ZIP member | `ValueError` Unsafe ZIP path | path: Broken ZIP member, message quotes both names |
| `mismatch_local_has_suffix` | local `a.bin\x00../escape`, central `a.bin` | `a.bin` / `a.bin` / no | `BadZipFile` names differ | `BundleError` Broken ZIP member | `BadZipFile` (not wrapped) | path: Broken ZIP member, message quotes the local suffix |

Archive SHA-256 (length in parentheses), unchanged after every reader and CLI call:

| Case | SHA-256 | Bytes |
|---|---|---|
| `safe_a_bin` | `a3b0cc4bce0529167d103821cb906dec781b078a7cf4b41a79796ce88e88d960` | 120 |
| `exact_duplicate` | `9e90a8f807138b61b773710ee7490f46a7872d4d0254b8bcb87013072bfebf8f` | 220 |
| `case_pair` | `f4e3e93c43a732549a95ec00c4a42740893a192192c2dc355a1941a3712e9720` | 220 |
| `leading_nul` | `c18a0d1aea3b016e242f73fc543cd174b64e6f8b7699263082f0495f8e86ac58` | 130 |
| `middle_nul` | `ef0cd7c1b02729991725eae635436b0e3eae87f1b8e30a337be209da31d6b17d` | 131 |
| `trailing_nul` | `0de13a877551a4b833db336044ccf636bdc8456db3f4a113ae8f2d0cec028874` | 123 |
| `nul_unsafe_suffix` | `ffada3fa8692fbe54bf83512c3e75cdcbdd8dc12c422fe14ff2dad33ce5dd077` | 142 |
| `backslash` | `64cb93d8f1891584bedf4006a3775f3abeaedc4f0dd552cc1fd68cc869dbb8d3` | 126 |
| `backslash_dotdot` | `56aab3bda46ce0313a8cd156f7688651500aa72cd3e9176776c0a3e544fbbe88` | 130 |
| `explicit_dotdot` | `c216d437e3b982726483536445f99972655ad12f515fb569335cb6460b0e2beb` | 127 |
| `dir_safe` | `457e6b662ae9fe3760f20a9e4b8fdf34a5c39caedcbc05e371afa74cebb8dbb4` | 112 |
| `dir_unsafe` | `4cfb7c375d8261e4ab1dfd9cbb1bdf7d3fda445df0d8ac22cad86c5c5003eb55` | 118 |
| `dir_nul_suffix` | `3d3af019e10c25d52393f3dbd94c5297679730ec652575cd093e43a8feb2873f` | 132 |
| `dir_unsafe_plus_file` | `ec3dc60878ca25a1f2cd8522878a9300bd505b1112ebe0cae3dd09fb5e57bf5e` | 216 |
| `mismatch_central_has_suffix` | `d6ad6b2d974fa96b29260afef7a23ca80069df22bf9f2d600203bb975720b202` | 134 |
| `mismatch_local_has_suffix` | `415f5a440dc02a5825c39d3e268747fc0f6f7cb14452e530e10030c6e5cf6310` | 134 |

`nul_unsafe_suffix` JSON `target_sha256` equals that archive hash. `code_commit` in that JSON begins `6d0dffcb9522`. The CLI itself records the commit; this research did not run git.

### Answer on the unsafe suffix

For a raw name that is identical in the local header and the central directory:

- `zipfile` discards the bytes after the first NUL from `filename` and from `NameToInfo`. It keeps them on `orig_filename`. Open succeeds. `read(filename)` returns the member payload. `read(orig_filename)` raises `KeyError`. The suffix is not a lookup key. The payload of that member is reachable under the truncated name. Nothing is extracted.
- The development reader checks `orig_filename` and rejects on NUL (`ValueError: Unsafe ZIP path`) before `archive.read`. The suffix is inside the string that check sees.
- V001 checks `filename` after the directory filter. For `a.bin\x00../escape` the checked identity is `a.bin`. The suffix is not in the check and not in the report. The later NPM fail is composition (a `.bin` is a foreign file), which is a separate failure from path acceptance.
- The same discard happens for a leading NUL (identity becomes `""`, and the official reader has no empty-name check), a middle NUL (identity `a`), and a trailing NUL (identity `a.bin` with the NUL only on `orig_filename`).
- A directory whose sanitized `filename` ends in `/` is removed before the official path loop. `../escape/` and `nested/\x00../escape` therefore never reach the `..` or NUL tests in V001. The development reader still sees `orig_filename` and rejects. `zipfile` itself returns the empty payload for those directory names.

For `../escape` with no NUL, both readers reject. `zipfile` still opens the archive and can `read` the bytes. The path is checked by both readers. For `..\escape`, both readers reject, V001 after sanitize (message shows `../escape`), the development reader on the raw backslash.

A backslash that does not become `..` after sanitize (`sub\a.bin` -> `sub/a.bin`) is accepted by V001 under the forward-slash name and rejected by the development reader. That is another identity split, measured here and left as a user question.

Header mismatch is the case `zipfile` rejects: `BadZipFile: File name in directory ... and header ... differ.` V001 reports that as a broken member, so the suffix text is visible in the finding only when the headers disagree. When they agree, the suffix is invisible to V001.

## How it applies to this repository

- `src/twinqa/bundle.py` is the official ZIP read. V001 in `tools/qa/validate_package.py` sees only `ZipInfo.filename` of non-directory members. A NUL suffix, a trailing NUL, a Windows backslash that sanitize turns into `/`, and a directory entry are outside that check.
- `src/dt_ai/publish/bundle.py` is the development reader. It validates `orig_filename`, so the same bytes fail there. `package()` in that module refuses NUL names before writing; it is not on the V001 read path.
- `tests/test_bundle_package_safety.py` locks the development reader and the writer. It does not lock `twinqa.bundle.read_bundle` or the CLI, so the measured V001 acceptance is currently untested.
- No scene, FBX readback, or extraction path was used. A returned key is not a delivery pass: these archives fail V001 for content or for an explicit ZIP finding, and `passed` stays false because other stages do not all pass.

## Proposed next tasks

1. **Pin the measured reader split as a current-behavior fixture.** Scope: one test module that builds the frozen `nul_unsafe_suffix`, `leading_nul`, `backslash`, `dir_unsafe_plus_file`, `explicit_dotdot`, and `mismatch_local_has_suffix` bytes (or calls the same builders) and asserts today's public outcomes: `twinqa.bundle.read_bundle` keys or `BundleError` message, `dt_ai.publish.bundle.read_bundle` exception family, and the V001 finding name (`ZIP` versus `foreign files`) with `passed` false. No change to which names are accepted. Value: a later edit cannot make V001 and the development reader agree, or disagree, without the fixture moving. Effort **S**. `Advances #149`.

2. **Decision sheet for which string V001 treats as the member identity.** Scope: one page that places the measured rows next to the two existing checks (`filename` after `is_dir`, versus `orig_filename` with the NUL and case-fold clauses) and asks the user which identity the official gate should see. The sheet records consequences already measured (truncated `a.bin` accepted by V001, directory `../escape/` omitted, `sub\a.bin` accepted as `sub/a.bin`, case pair accepted by V001). It does not pick a NUL, case, directory, or slash rule. Value: the identity question is ready for a decision without an implementation guess. Effort **S**. `Advances #149`.

`#149` is the open roadmap item this repo's research notes already use for the NPM/VPM delivery-check seam. `gh` was not run in this session. `#298`, `#352`, `#371`, `#425`, and `#426` are other seams in those notes (SINTEZ verify, library/acceptance, Ground/xView, UV numeric). They do not name this ZIP identity split.

## Open questions for the user

- Should official V001 validate `ZipInfo.orig_filename`, `ZipInfo.filename`, or both?
- Case folding, directory entries, and backslash-to-slash normalization are separate choices. This probe only measured the current split.
- When the central name is safe and the local name carries a NUL suffix, the development reader lets `BadZipFile` propagate, while V001 records `Broken ZIP member`. Should that exception stay uncaught on the development reader?

## Probe script

The script that produced the rows lives at `C:/x/t_797b79e9/probe_zip_raw_names.py`, SHA-256 `97f633c6e453bf2f4b31159b6328104e520cd505404491f33d58cb6835182c3f`. Corpus zips are under `C:/x/t_797b79e9/corpus/`. CLI JSON and stderr captures are under `C:/x/t_797b79e9/reports/`. The same source follows.

```python
"""Synthetic ZIP raw-name probe. Not a delivery check. Writes only under C:/x/t_797b79e9/."""
import hashlib
import json
import struct
import subprocess
import sys
import traceback
import warnings
import zipfile
import zlib
from pathlib import Path
from zipfile import ZipFile, ZipInfo

REPO = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_797b79e9")
OUT = Path(r"C:\x\t_797b79e9")
sys.path.insert(0, str(REPO / "src"))

from dt_ai.publish.bundle import read_bundle as dev_read  # noqa: E402
from twinqa.bundle import read_bundle as twin_read  # noqa: E402

SIG_LOCAL = b"PK\x03\x04"
SIG_CENTRAL = b"PK\x01\x02"
SIG_EOCD = b"PK\x05\x06"
LOCAL_FMT = "<4s2B4HL2L2H"
CENTRAL_FMT = "<4s4B4HL2L5H2L"
EOCD_FMT = "<4s4H2LH"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha256(path.read_bytes())


def exc_record(exc: BaseException) -> dict:
    return {
        "family": type(exc).__name__,
        "module": type(exc).__module__,
        "message": str(exc),
        "mro": [cls.__name__ for cls in type(exc).__mro__ if cls is not object],
    }


def parse_headers(data: bytes) -> dict:
    eocd_at = data.rfind(SIG_EOCD)
    if eocd_at < 0:
        raise ValueError("no EOCD")
    eocd = struct.unpack_from(EOCD_FMT, data, eocd_at)
    # "<4s4H2LH": sig, disk, cd_disk, disk_entries, total_entries, cd_size, cd_offset, comment_len
    cd_count = eocd[4]
    cd_size = eocd[5]
    cd_off = eocd[6]
    comment_len = eocd[7]
    centrals = []
    pos = cd_off
    for _ in range(cd_count):
        fixed = struct.unpack_from(CENTRAL_FMT, data, pos)
        if fixed[0] != SIG_CENTRAL:
            raise ValueError(f"bad central signature at {pos}")
        # "<4s4B4HL2L5H2L": name length is field 12, local header offset is field 18
        name_len = fixed[12]
        extra_len = fixed[13]
        comment_len_m = fixed[14]
        name = data[pos + 46:pos + 46 + name_len]
        centrals.append({
            "offset": pos,
            "name_hex": name.hex(),
            "name_sha256": sha256(name),
            "name_len": name_len,
            "flag_bits": fixed[5],
            "method": fixed[6],
            "local_offset": fixed[18],
        })
        pos += 46 + name_len + extra_len + comment_len_m
    locals_ = []
    pos = 0
    while pos + 4 <= len(data) and data[pos:pos + 4] == SIG_LOCAL:
        fixed = struct.unpack_from(LOCAL_FMT, data, pos)
        # "<4s2B4HL2L2H": flag is field 3, method field 4, sizes fields 8 and 9
        name_len = fixed[10]
        extra_len = fixed[11]
        comp_size = fixed[8]
        flag = fixed[3]
        name = data[pos + 30:pos + 30 + name_len]
        locals_.append({
            "offset": pos,
            "name_hex": name.hex(),
            "name_sha256": sha256(name),
            "name_len": name_len,
            "flag_bits": flag,
            "method": fixed[4],
            "comp_size": comp_size,
            "uncomp_size": fixed[9],
        })
        pos += 30 + name_len + extra_len + comp_size
        if flag & 0x8:
            raise ValueError("data descriptor not expected in this corpus")
    return {
        "eocd_offset": eocd_at,
        "cd_count": cd_count,
        "cd_size": cd_size,
        "cd_offset": cd_off,
        "comment_len": comment_len,
        "local": locals_,
        "central": centrals,
        "local_equals_central": [a["name_hex"] == b["name_hex"] for a, b in zip(locals_, centrals)],
    }


def build_via_zipinfo(path: Path, members: list[tuple[str, bytes]]) -> list[str]:
    warned = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with ZipFile(path, "w") as archive:
            for name, payload in members:
                info = ZipInfo("placeholder")
                info.filename = name
                info.compress_type = 0
                archive.writestr(info, payload)
        for item in caught:
            warned.append(f"{item.category.__name__}: {item.message}")
    return warned


def build_struct(path: Path, members: list[tuple[bytes, bytes, bytes]]) -> None:
    """members: (local_name, central_name, payload), ZIP_STORED, no extra/comment."""
    blobs = []
    central_parts = []
    offset = 0
    for local_name, central_name, payload in members:
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        local = struct.pack(
            LOCAL_FMT,
            SIG_LOCAL, 20, 0, 0, 0, 0, 0, crc, len(payload), len(payload),
            len(local_name), 0,
        ) + local_name + payload
        blobs.append(local)
        central_parts.append(struct.pack(
            CENTRAL_FMT,
            SIG_CENTRAL, 20, 0, 20, 0, 0, 0, 0, 0, crc, len(payload), len(payload),
            len(central_name), 0, 0, 0, 0, 0, offset,
        ) + central_name)
        offset += len(local)
    body = b"".join(blobs)
    central = b"".join(central_parts)
    eocd = struct.pack(
        EOCD_FMT, SIG_EOCD, 0, 0, len(members), len(members), len(central), len(body), 0,
    )
    path.write_bytes(body + central + eocd)


def zipfile_view(path: Path) -> dict:
    view = {"open": None, "members": [], "reads": []}
    try:
        archive = ZipFile(path)
    except Exception as exc:
        view["open"] = exc_record(exc)
        return view
    view["open"] = "ZipFile"
    with archive:
        view["namelist"] = [repr(n) for n in archive.namelist()]
        for info in archive.infolist():
            view["members"].append({
                "filename": repr(info.filename),
                "orig_filename": repr(info.orig_filename),
                "is_dir": bool(info.is_dir()),
                "file_size": info.file_size,
                "filename_eq_orig": info.filename == info.orig_filename,
            })
        seen = []
        for info in archive.infolist():
            for label, key in (("filename", info.filename), ("orig_filename", info.orig_filename)):
                token = (label, key)
                if token in seen:
                    continue
                seen.append(token)
                try:
                    payload = archive.read(key)
                except Exception as exc:
                    view["reads"].append({"by": label, "key": repr(key), "result": exc_record(exc)})
                else:
                    view["reads"].append({
                        "by": label,
                        "key": repr(key),
                        "result": "bytes",
                        "sha256": sha256(payload),
                        "length": len(payload),
                    })
    return view


def reader_call(kind: str, path: Path) -> dict:
    try:
        if kind == "twinqa":
            result = twin_read(path, max_uncompressed=4 * 10**9)
        else:
            result = dev_read(path)
    except Exception as exc:
        return {"outcome": "exception", **exc_record(exc)}
    return {
        "outcome": "returned",
        "keys": [repr(k) for k in result],
        "payload_sha256": {repr(k): sha256(v) for k, v in result.items()},
        "count": len(result),
    }


def cli_call(path: Path, json_out: Path, stderr_out: Path) -> dict:
    before = file_sha(path)
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "qa" / "validate_package.py"),
         str(path), "--profile", "npm", "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    after = file_sha(path)
    json_out.write_text(proc.stdout, encoding="utf-8")
    stderr_out.write_text(proc.stderr, encoding="utf-8")
    parsed = None
    v001 = None
    notes = None
    passed = None
    exit_field = None
    profile = None
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        parsed_error = exc_record(exc)
    else:
        parsed_error = None
        passed = parsed.get("passed")
        exit_field = parsed.get("exit_code")
        profile = parsed.get("profile")
        notes = parsed.get("notes")
        for stage in parsed.get("stages", []):
            if stage.get("id") == "V001":
                v001 = {
                    "status": stage.get("status"),
                    "findings": [
                        {
                            "name": f.get("name"),
                            "status": f.get("status"),
                            "observed": f.get("observed"),
                            "expected": f.get("expected"),
                        }
                        for f in stage.get("findings", [])
                    ],
                }
                break
    stdout_text = proc.stdout
    return {
        "process_exit": proc.returncode,
        "json_exit_code": exit_field,
        "json_passed": passed,
        "profile": profile,
        "notes": notes,
        "v001": v001,
        "json_parse_error": parsed_error,
        "stderr": proc.stderr,
        "stdout_sha256": sha256(stdout_text.encode("utf-8")),
        "stdout_mentions_dotdot_escape": "../escape" in stdout_text,
        "stdout_mentions_nul_escape": "\\x00" in stdout_text or "\x00" in stdout_text,
        "stderr_mentions_dotdot_escape": "../escape" in proc.stderr,
        "input_sha256_before": before,
        "input_sha256_after": after,
        "input_unchanged": before == after,
    }


CASES = [
    ("safe_a_bin", [("a.bin", b"payload-safe")]),
    ("exact_duplicate", [("a.bin", b"payload-dup-1"), ("a.bin", b"payload-dup-2")]),
    ("case_pair", [("a.bin", b"payload-lower"), ("A.bin", b"payload-upper")]),
    ("leading_nul", [("\x00../escape", b"payload-lead")]),
    ("middle_nul", [("a\x00../escape", b"payload-mid")]),
    ("trailing_nul", [("a.bin\x00", b"payload-trail")]),
    ("nul_unsafe_suffix", [("a.bin\x00../escape", b"payload-suffix")]),
    ("backslash", [("sub\\a.bin", b"payload-bs")]),
    ("backslash_dotdot", [("..\\escape", b"payload-bs-dot")]),
    ("explicit_dotdot", [("../escape", b"payload-dot")]),
    ("dir_safe", [("nested/", b"")]),
    ("dir_unsafe", [("../escape/", b"")]),
    ("dir_nul_suffix", [("nested/\x00../escape", b"")]),
    ("dir_unsafe_plus_file", [("a.bin", b"payload-safe"), ("../escape/", b"")]),
]


def main() -> None:
    corpus = OUT / "corpus"
    reports = OUT / "reports"
    corpus.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, members in CASES:
        path = corpus / f"{name}.zip"
        warned = build_via_zipinfo(path, members)
        data = path.read_bytes()
        assigned = [m.encode("ascii") for m, _ in members]
        parsed = parse_headers(data)
        rows.append({
            "case": name,
            "builder": "ZipInfo.filename assignment then writestr",
            "assigned_name_hex": [b.hex() for b in assigned],
            "assigned_name_sha256": [sha256(b) for b in assigned],
            "payload_sha256": [sha256(p) for _, p in members],
            "write_warnings": warned,
            "archive_sha256": sha256(data),
            "archive_length": len(data),
            "parsed": parsed,
            "raw_equals_assigned": (
                [x["name_hex"] for x in parsed["local"]] == [b.hex() for b in assigned]
                and [x["name_hex"] for x in parsed["central"]] == [b.hex() for b in assigned]
            ),
            "zipfile": zipfile_view(path),
            "twinqa": reader_call("twinqa", path),
            "development": reader_call("dev", path),
            "cli": cli_call(path, reports / f"{name}.json", reports / f"{name}.stderr.txt"),
        })
        rows[-1]["archive_sha256_after_probes"] = file_sha(path)
        rows[-1]["archive_unchanged"] = rows[-1]["archive_sha256_after_probes"] == rows[-1]["archive_sha256"]

    suffix = b"a.bin\x00../escape"
    short = b"a.bin"
    payload = b"payload-mismatch"
    for name, local_name, central_name in (
        ("mismatch_central_has_suffix", short, suffix),
        ("mismatch_local_has_suffix", suffix, short),
    ):
        path = corpus / f"{name}.zip"
        build_struct(path, [(local_name, central_name, payload)])
        data = path.read_bytes()
        parsed = parse_headers(data)
        rows.append({
            "case": name,
            "builder": "struct local+central independent names",
            "assigned_name_hex": [local_name.hex(), central_name.hex()],
            "assigned_name_sha256": [sha256(local_name), sha256(central_name)],
            "payload_sha256": [sha256(payload)],
            "write_warnings": [],
            "archive_sha256": sha256(data),
            "archive_length": len(data),
            "parsed": parsed,
            "raw_equals_assigned": (
                parsed["local"][0]["name_hex"] == local_name.hex()
                and parsed["central"][0]["name_hex"] == central_name.hex()
            ),
            "zipfile": zipfile_view(path),
            "twinqa": reader_call("twinqa", path),
            "development": reader_call("dev", path),
            "cli": cli_call(path, reports / f"{name}.json", reports / f"{name}.stderr.txt"),
        })
        rows[-1]["archive_sha256_after_probes"] = file_sha(path)
        rows[-1]["archive_unchanged"] = rows[-1]["archive_sha256_after_probes"] == rows[-1]["archive_sha256"]

    sources = [
        REPO / "src" / "twinqa" / "bundle.py",
        REPO / "src" / "dt_ai" / "publish" / "bundle.py",
        REPO / "tools" / "qa" / "validate_package.py",
        REPO / "tests" / "test_bundle_package_safety.py",
        Path(zipfile.__file__),
    ]
    meta = {
        "python": sys.version,
        "platform": sys.platform,
        "sources": {str(p): file_sha(p) for p in sources},
        "cases": rows,
    }
    (OUT / "results.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"cases {len(rows)}")
    for row in rows:
        print(
            row["case"],
            "raw_ok" if row["raw_equals_assigned"] else "RAW_MISMATCH",
            "local=central" if all(row["parsed"]["local_equals_central"]) else "local!=central",
            "twin", row["twinqa"]["outcome"], row["twinqa"].get("family") or row["twinqa"].get("keys"),
            "dev", row["development"]["outcome"], row["development"].get("family") or row["development"].get("keys"),
            "cli", row["cli"]["process_exit"],
            "v001", None if not row["cli"]["v001"] else row["cli"]["v001"]["status"],
            "unchanged", row["archive_unchanged"],
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
```

