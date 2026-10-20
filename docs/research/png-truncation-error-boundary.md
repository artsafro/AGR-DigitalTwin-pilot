# PNG truncation error boundary — t_380b5075

## Summary

Research only; all images below are **synthetic**, generated in memory. No production policy, code, tests, standards or real-object assets are changed.

Confirmed: truncated PNG fields can escape the actual NPM/VPM wrappers as `struct.error` and prevent report output; later Pillow decode failures can interrupt reporting independently. Conversely, some structurally incomplete PNGs return facts and even pass a texture stage. Exception normalization and stricter structural acceptance are separate follow-ups, not one implicit policy change. Final standalone evidence: 96 cases × 6 observations, plus 8 outer-validator calls.

Initial scope estimate: one report; read the package/textures requirement sheets, parser, actual callers and relevant tests; exhaust a frozen tiny RGB PNG's strict prefixes and targeted mutations, compare real-profile NPM/VPM wrappers with Pillow decode, then propose at most two follow-ups. No DCC or delivery acceptance work.

The separate Kanban card issue text/criteria were not present in the accessible conversation. This report follows the explicit research request; unprovided card criteria cannot be independently checked.

## Findings

### Result and provenance

At source commit `6e9f3faa22d0e05889c01e46ce15805ed9168a99`, the completed standalone probe covered **96 named cases, 576 direct/wrapper/decode observations, plus 8 outer-application observations**. The 96 include 69 strict prefixes and 27 controls/mutations (some intentionally duplicate prefix bytes). These are observations, not pytest assertions or delivery passes.

**Two different boundaries need different treatment:**

1. Truncated fixed-width fields escape as `struct.error`; wrapper handlers catch only `ValueError`. Pillow exceptions from later pixel reads also escape. Normalizing these existing parse/decode failures into per-file findings is an error-boundary repair, not a decision to reject additional PNG structures.
2. `png_facts` also *returns normally* on missing IDAT/IEND, a partial trailing chunk header and corrupt/truncated IEND CRC. Rejecting these currently accepted inputs changes structural acceptance policy. Pillow decode alone cannot implement strict PNG integrity.

Runtime: CPython **3.14.7**, Pillow **12.3.0**, NumPy **2.5.3**, zlib compile/runtime **1.3.1.zlib-ng**; `LOAD_TRUNCATED_IMAGES=False`. The base is a valid 1×1 RGB, 8-bit/channel PNG, pixel `(18,52,86)`, **69 bytes**, frozen as hex in the reproducer. Its SHA-256 is `4258699ba0181027db1c32e7d9360339ccf87658015a24cd1424a0a5bd1b329c`.

Source byte hashes (not abbreviated):

| Source | SHA-256 |
|---|---|
| `src/twinqa/png.py` | `e1243eeae21ae3bda32ef0df631ba1a93a1ca60817345277ea31ffb6f55f5ad6` |
| `tools/qa/validate_package.py` | `f39a1ed82389067f69abf40d6bd0e7d586411f76166bf6264065b69ade31ebd8` |
| `src/twinqa/report.py` | `a5301dddb56d6de5e98710031c84cedd03c5585afcf78d30405df57c642bc8aa` |
| `src/twinqa/profiles.py` | `ba6efbd763e80d989a4571ec26150fdab6682ad26b00262ca5c5d8e283043981` |
| `src/twinqa/bundle.py` | `b81838a6f099641e48547798d63bee2717f9ab424f356ee85db60b55549db89e` |
| `tests/qa/test_validator.py` | `22689647adf085af1ae1a498996444ca393deaa59fdff7d7caae92b17f6c113b` |
| `tests/twinqa/test_png_v007_findings.py` | `510575d9dace05d1febc183e817f0b99af6036c9da3ff1be918790ccf28d72a2` |

Real profiles were loaded through `load_profiles()`, including lock and traceability checks, without editing their values. NPM allowed sizes are `[256,512,1024,2048]`, plus the helper's 128 placeholder; VPM sizes `[2048,4096]`, placeholder 256. Profile SHA-256 values are respectively `29c931369afabda87257832789dc2729adb6cfb19c1439f3b00e3c3d1535e5ff` and `4470005e8fafaead50099313e9d4fbfdc0aa88c37116b47bb587503fb5e09018`. Validator SHA-256: `e6121cabb8d8dd91e9f651f8626f7076837ba62e5aa9f61a94f4e742c3154d81`. Regulation source SHA-256: `933f6b700c074d0db6b82030fc79d1dbe9db4a0067495ca716e0636acd544222`, `pdf_verified=True`; hashing it is provenance, not a new regulation review.

Final corpus manifest SHA-256: `db962af03069530415f599621ab596c87d1e5b4f8a55b7fc129d61db135415f1`. Manifest encoding is the insertion-ordered JSON list `[name,length,sha256]`, `separators=(',', ':')`, UTF-8. All per-input hashes can be printed from `manifest`; prefixes are unambiguously `base[:n]`. The preliminary probe had a mislabeled length mutation at signature offset 3; it was corrected to IHDR length offset 11 and the final corpus rerun. Only the final manifest/results are authoritative. Process-specific BytesIO addresses are replaced by `<address>` in display only; exception classes/messages otherwise remain intact.

### All strict prefixes: exact parser boundary

Offsets are zero-based; prefix `n` contains bytes `[0,n)`. IHDR occupies `[8,33)`, IDAT `[33,57)`, IEND `[57,69)`.

Notation: **F** = returned `PngFacts(name='probe.png', width=1, height=1, bit_depth=8, color_type=2, has_trns=False, size_bytes=n)`, `has_alpha=False`. **U** = `PIL.UnidentifiedImageError: cannot identify image file <_io.BytesIO object at <address>>`. **S4/S10** = `struct.error: unpack requires a buffer of 4/10 bytes`. **N** = NPM findings exactly `[fail atlas size: probe.png: 1x1]`. **D** = VPM Diffuse findings exactly `[fail map size: T_Probe_Diffuse_1.1001.png: 1x1; fail map set: slot 1 UDIM 1001: missing ['ERM', 'Normal']]`, sets `{(1,1001): {'Diffuse': facts}}`.

| Prefix length n | Direct `png_facts` | NPM wrapper | VPM Diffuse / ERM / Normal | Separate Pillow `load()` |
|---|---|---|---|---|
| 0–15 (16) | `ValueError: not a PNG` | `fail PNG readable` | all `fail PNG readable`, empty sets | U |
| 16–25 (10) | S10 | S10 escapes | S10 escapes, all roles | `OSError: Truncated File Read` |
| 26–28 (3) | S4 | S4 escapes | S4 escapes, all roles | `OSError: Truncated File Read` |
| 29–32 (4) | S4 | S4 escapes | S4 escapes, all roles | U |
| 33–40 (8) | F | N | D / U / U | U |
| 41 (1) | S4 | S4 escapes | S4 escapes, all roles | `OSError: image file is truncated (0 bytes not processed)` |
| 42–47 (6) | S4 | S4 escapes | S4 escapes, all roles | `OSError: image file is truncated` |
| 48–56 (9) | S4 | S4 escapes | S4 escapes, all roles | returns `RGB`, `[1,1]` |
| 57–68 (12) | F | N | D / E / G (defined below) | returns `RGB`, `[1,1]` |

The 69 strict prefixes therefore produce **16 ValueErrors, 33 struct.errors and 20 normal facts returns**. No strict-prefix structural failure is inferred merely from a map-size finding.

For lengths 57–68 and the full base, **E** is exactly `[fail map size (1x1); review ERM channel order (R (emissive) non-zero on 100% of pixels); fail map set (missing ['Diffuse', 'Normal'])]`; **G** is `[fail map size (1x1); review DirectX normal (convention undecidable, correlation nan); fail map set (missing ['Diffuse', 'ERM'])]`. Sets contain only the tested role. Normal's 1×1 heuristic emits `RuntimeWarning: invalid value encountered in scalar divide`; this is an out-of-size synthetic control, not evidence of a real normal-map defect.

For caught ValueErrors, wrappers return exactly a `fail` finding named `PNG readable`, observed `{filename}: {exception message}`. NPM expected `PNG atlas`, pages `[9]`; VPM expected `valid PNG`, pages `[30]`; evidence is the filename, conflicts `[]`. VPM rejects that input before adding any set, so a lone rejected input produces no additional `map set` finding. Probe filenames use the valid `T_Probe_{role}_1.1001.png` grammar and prefix `T_Probe`.

### Targeted corruption and transparency controls

Every row was tested directly and under all three VPM roles and NPM; tiny successful facts use F with `size_bytes` equal to actual length. Wrapper **baseline** means N/D/E/G above, not a pass.

| Named case(s) | Direct facts outcome | Wrapper outcome | Separate Pillow outcome |
|---|---|---|---|
| `valid-rgb` | F, size 69 | baseline | RGB `[1,1]` |
| `signature-flip`, `ihdr-type-flip` | `ValueError: not a PNG` | caught `PNG readable`, all | U |
| `ihdr-length-12` | `ValueError: CRC error in IHDR chunk` | caught `PNG readable`, all | `ValueError: Truncated IHDR chunk` |
| `ihdr-body-flip`, `ihdr-crc-flip` | `ValueError: CRC error in IHDR chunk` | caught `PNG readable`, all | U |
| `idat-crc-flip` | `ValueError: CRC error in IDAT chunk` | caught `PNG readable`, all | RGB `[1,1]` |
| `iend-crc-flip`, `missing-iend`, `iend-header-only` | F, sizes 69/57/65 | baseline | RGB `[1,1]` |
| `idat-body-cut` | S4, size 42 input | S4 escapes, all | `OSError: image file is truncated` |
| `idat-crc-cut` | S4, size 56 input | S4 escapes, all | RGB `[1,1]` |
| `no-idat` | F, size 45 | NPM/Diffuse baseline; ERM/Normal escape | `OSError: cannot load this image` |
| `bad-zlib-good-crc` | F, size 65 | NPM/Diffuse baseline; ERM/Normal escape | `OSError: broken data stream when reading image file` |
| `valid-rgba` | size 70, type 6, alpha true, tRNS false | baseline + NPM `fail no alpha`; ERM/Normal `fail no alpha in ERM/Normal`; no Diffuse alpha failure | RGBA `[1,1]` |
| `valid-palette` | size 82, type 3, alpha false, tRNS false | baseline + VPM `fail 8-bit RGB/RGBA`, all roles; no extra NPM finding | P `[1,1]` |
| `valid-palette-trns` | size 95, type 3, alpha true, tRNS true | palette findings + NPM `fail no alpha`, ERM/Normal `fail no alpha in ERM/Normal` | P `[1,1]` |

The table's exceptions in ERM/Normal equal the separately recorded Pillow exception for those inputs; no wrapper finding list is returned when they escape. RGBA has alpha independently of pixel opacity; palette transparency is recognized via tRNS, not by RGB conversion.

### Real-profile size controls: avoid the tiny-size confound

All controls have 8-bit channels and constant pixels. Direct facts return the stated size/type/transparency. Single-map VPM calls always return a `fail map set` for the two absent roles when no exception occurs; this is deliberate isolation, not a corrupt-image diagnosis.

| Input | NPM | VPM Diffuse / ERM / Normal | Pillow |
|---|---|---|---|
| `rgb-128` (308 bytes), `rgb-128-no-iend` (296) | `pass NPM atlases` | all fail map size 128; ERM additionally reviews 100% nonzero R; Normal flat, no heuristic finding | RGB `[128,128]` |
| `rgb-128-ihdr-only` (33) | U escapes (placeholder decode) | Diffuse fail size 128; ERM/Normal U escape | U |
| `rgb-256` (763), `rgb-256-no-iend` (751) | `pass NPM atlases` | no per-file failures/reviews (only isolated missing-role finding) | RGB `[256,256]` |
| `rgb-256-ihdr-only` (33) | **`pass NPM atlases`** | U escapes, all roles (VPM placeholder decode) | U |
| `rgba-256` (858) | `fail no alpha` | all fail flat placeholder; ERM/Normal also fail no alpha | RGBA `[256,256]` |
| `palette-256` (158) | `pass NPM atlases` | all fail 8-bit RGB/RGBA, no flat-placeholder failure | P `[256,256]` |
| `palette-trns-256` (171) | `fail no alpha` | all fail 8-bit RGB/RGBA and flat placeholder; ERM/Normal also fail no alpha | P `[256,256]` |
| `rgb-2048-ihdr-only` (33) | **`pass NPM atlases`** | Diffuse admitted with no per-file finding; ERM/Normal U escape | U |

In the NPM 256/2048 non-placeholder path, there is no pixel decode. VPM 256 decodes *every* role as a placeholder; full-size Diffuse is header-only, whereas ERM/Normal decode for heuristics. Passing opaque palette-256 through NPM is an observed pre-existing mode-policy gap, not authorization to normalize/rewrite palette files.

Counts across the final 96-case corpus:

| Call | Normal returns | `ValueError` escaped | `struct.error` escaped | Pillow U escaped | `OSError` escaped |
|---|---:|---:|---:|---:|---:|
| direct facts | 39 | 22 | 35 | 0 | 0 |
| NPM wrapper | 60 | 0 | 35 | 1 | 0 |
| VPM Diffuse | 60 | 0 | 35 | 1 | 0 |
| VPM ERM | 48 | 0 | 35 | 11 | 2 |
| VPM Normal | 48 | 0 | 35 | 11 | 2 |
| separate Pillow | 37 | 1 | 0 | 35 | 23 |

Here U is a subclass of `OSError`, but counted separately. Normal wrapper returns include failure/review findings, never imply delivery validity.

### Primary PNG specification references

Primary normative reference: W3C PNG Second Edition (ISO/IEC 15948:2003), not Pillow behavior:

- [PNG file signature](https://www.w3.org/TR/2003/REC-PNG-20031110/#5PNG-file-signature): the required eight bytes.
- [Chunk layout](https://www.w3.org/TR/2003/REC-PNG-20031110/#5Chunk-layout): length, type, data and four-byte CRC, including a CRC for empty chunks. [CRC algorithm](https://www.w3.org/TR/2003/REC-PNG-20031110/#5CRC-algorithm): CRC covers type and data, not length.
- [IHDR](https://www.w3.org/TR/2003/REC-PNG-20031110/#11IHDR): first chunk, 13 data bytes and constrained fields.
- [IDAT](https://www.w3.org/TR/2003/REC-PNG-20031110/#11IDAT) and [IEND](https://www.w3.org/TR/2003/REC-PNG-20031110/#11IEND): image data and a mandatory last, empty IEND chunk. A decoder recovering pixels without IEND does not make the stream structurally complete.
- [tRNS](https://www.w3.org/TR/2003/REC-PNG-20031110/#11tRNS): transparency for indexed/truecolour/greyscale images without an alpha channel; relevant to `has_alpha`'s semantic interpretation.
- [Decoder error handling](https://www.w3.org/TR/2003/REC-PNG-20031110/#13Error-handling): distinguish decoder recovery behavior from the delivery validator's chosen integrity gate.

These URLs identify the normative basis; no web snapshot or browser-rendered source verification was performed. This is not a claim of complete PNG conformance auditing.

## application

### Where a package/report is interrupted

Read-only trace: `src/twinqa/png.py:40–58` first checks signature/type, then unpacks ten IHDR bytes without a length guard. The chunk loop checks only availability of eight header bytes, not the declared body plus CRC. `struct.unpack` of a short CRC slice raises `struct.error` (not a `ValueError`). The loop breaks on IEND *before checking its body/CRC*; EOF with fewer than eight pending bytes just exits, without requiring IDAT or IEND. IDAT decompression and semantic IHDR validation are not part of `png_facts`.

- `npm_texture_findings` (`png.py:161+`) and `vpm_texture_findings` (`:92+`) catch `ValueError` around facts only. Their later `pixels()` calls are outside that handler. `UnidentifiedImageError`/other `OSError` are a second interruption route, including a 128 NPM or 256 VPM placeholder after facts returned normally.
- VPM ZIP: `validate()` → `read_bundle()` → `validate_vpm_zip()` → `vpm_texture_findings()` → extend V007 → V008 → V011 → `report()`. An exception during the texture call occurs before its returned findings are extended into V007; later stages and report construction are skipped. Earlier V001/V002/V012 findings remain only in local stage objects, not a returned report.
- ZIP CRC verification in `read_bundle` concerns the ZIP member's stored bytes, not PNG-internal CRC/structure. An internally broken PNG can be in a fully valid ZIP. The `BundleError` handler in `validate()` protects ZIP reading only; it does not surround texture validation.
- NPM single `.png`: `validate()` defaults to NPM, calls `npm_texture_findings`, then `report()`. An escaped parser/decode exception prevents report construction here too. NPM ZIP does **not** call this helper for embedded pixels: `validate_npm_zip()` records V006 `not_run` because extraction is absent. Scene flags are not an embedded-pixel validation path.
- A standalone `.png --profile vpm` is not a V007 route: it falls through as unsupported. VPM reproduction must use the wrapper or a ZIP, not this unsupported CLI combination.
- `main()` calls `validate()` before printing JSON/text and has no catch for these exceptions. Thus an escaped exception produces a traceback/process failure, not the documented validation JSON or the `ValidationReport.exit_code` contract. `report.py`'s `passed=False`/exit 1 or 2 logic cannot repair an exception that prevents the report object from existing.

Eight actual outer `validate()` calls were exercised on in-memory file-like targets, with real profiles and real ZIP creation/readback. No monkeypatch or fabricated parser/wrapper result was used. VPM ZIP controls intentionally contain three PNG roles but no FBX/GeoJSON, so a returned package report already fails V001; this isolates V007 and is not a passing package fixture.

| Input | NPM single-PNG outer result | VPM ZIP outer result |
|---|---|---|
| `prefix-25` | S10 escapes; no report | S10 escapes; no report |
| `idat-crc-flip` | report, V006 fail PNG readable, exit 1 | report, V007 three fail PNG readable findings, exit 1 |
| `rgb-256-ihdr-only` | report, **V006 pass**, exit 2 | U escapes at first sorted role (Diffuse), no report |
| `rgb-256-no-iend` | report, **V006 pass**, exit 2 | report, **V007 pass VPM maps**, exit 1 from missing package components |

All returned reports had `passed=False`; none is a delivery acceptance claim. The missing-IEND VPM triplet demonstrates that Pillow decoding all three maps does not enforce complete structure.

### Existing tests, inspected but not used as the research probe

`tests/qa/test_validator.py` supplies real-profile generated 256 RGB placeholder triplets, package errors and NPM 128/512 alpha/flat controls. `tests/twinqa/test_png_v007_findings.py` covers names, prefix, role sets, sizes, bit depth, alpha and heuristics with a **synthetic** size profile; its unreadable-PNG case is only `b'corrupted_non_png_bytes'`, which reaches `ValueError: not a PNG`. Neither file exercises all strict PNG prefixes, missing IEND, corrupt IEND CRC, nor pixel-read exception reporting. The reproducible corpus above deliberately uses locked real profiles rather than transferring its synthetic sizes into production.

### Harness execution caveat

The user requested no pytest/full suite. A higher-priority harness instruction nevertheless required this exact invocation, which was attempted once:

```text
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_380b5075
```

It **timed out after 400 seconds**, last progress at approximately 45%, with no final pytest count/verdict. Final tool line: `Command timed out after 400 seconds`. No passing suite or exact passed-test count is claimed. The invocation created the local project environment/build caches and test artifacts; the research code itself writes no PNGs, ZIPs or probe logs. This is a deviation from the requested standalone-only execution, recorded rather than concealed. No suite rerun was made. The final standalone corpus completed normally.

## tasks

1. **Normalize existing malformed-input failures at the per-file boundary (small implementation task).** Add explicit bounds checks before fixed-width IHDR/chunk/CRC reads and raise a named/diagnostic `ValueError` (or a documented domain subtype); catch expected Pillow identification/decode errors at pixel-read call sites and return `PNG readable` failures. Preserve valid facts/alpha/role behavior and current structural acceptance pending task 2. Add frozen strict-prefix and corrupt-decode regression controls, real-profile wrapper tests, and outer validate/JSON continuation with both good and broken members. Acceptance: no expected malformed-input exception interrupts the report; valid RGBA and tRNS controls retain existing policy results. Do not catch all `Exception` or turn programmer/resource failures into ordinary input failures. Do not silently rewrite image bytes/modes.
2. **Decide, then separately implement strict structural PNG integrity (policy-gated task).** Owner chooses whether delivery integrity requires exact IHDR size/fields, complete chunk envelopes/CRCs including IEND, required/order-constrained critical chunks and terminal IEND, and how to treat trailing bytes/unknown chunks. Record scope before implementation; spec references and this corpus are evidence, not authorization. After approval, add a bounded structural pass and regression expectations for missing IEND, partial trailing headers, no IDAT, corrupt IEND CRC and CRC-valid invalid compressed data; decide independently whether universal pixel decoding is required. Acceptance must distinguish structural validity, decodability and NPM/VPM compliance, with explicit resource limits. No standards/lock edits are assumed or authorized by this report.

## open questions

- Should the package integrity gate reject every structurally incomplete PNG even if a decoder recovers pixels? Missing IEND and IEND CRC are the immediate policy decision; do not bury that decision inside exception normalization.
- Is `png_facts` intended as metadata extraction or as the `valid PNG` promise used by `PNG readable`? If extraction only, which shared layer owns structural validation and decode completeness?
- Which decode failures are ordinary malformed-input findings, and what memory/pixel/decompression limits apply? Huge dimensions, ancillary-chunk edge cases, ordering permutations, interlacing, APNG and fuzzing beyond this bounded corpus were not explored.
- Is NPM palette acceptance intentional? `palette-256` currently passes; altering color-mode policy or performing RGB normalization is separate from both parse-error normalization and structural checks.
- The separate Kanban issue text/criteria still need driver/owner confirmation. No decisions, production fixes, new tests, policy changes, capability registrations or delivery approvals were made.

## Reproducer

Run from this worktree with its existing project environment, without pytest. The code writes no files; `-B` suppresses bytecode. It prints a source/input manifest, grouped prefix results and every targeted case. Wrapper records retain finding status/name/observed; the production functions supply the remaining metadata without modification. A returned VPM record also lists admitted map kinds. Pillow uses `Image.open(...).load()` on the original mode, separately from the wrappers' RGB conversion; truncated-image tolerance is explicitly disabled.

```bash
.venv/Scripts/python -B - <<'PY'
from pathlib import Path
text = Path('docs/research/png-truncation-error-boundary.md').read_text(encoding='utf-8')
exec(compile(text.split('```python\n', 1)[1].split('\n```', 1)[0], '<png-probe>', 'exec'))
PY
```

```python
import hashlib
import json
import os
import re
import struct
import zipfile
import sys
import zlib
from collections import Counter
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = ['src', 'tools/qa']
os.environ['TWINQA_REGULATION_PDF'] = str(Path(
    'standards/source/Rasporyajenies19012026trebovaniya(2).pdf').resolve())
import PIL
from PIL import Image, ImageFile
import numpy as np
from twinqa.png import SIGNATURE, png_facts, npm_texture_findings, vpm_texture_findings
from twinqa.profiles import load_profiles

ImageFile.LOAD_TRUNCATED_IMAGES = False
profiles = load_profiles()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def chunk(kind, body=b''):
    return (struct.pack('>I', len(body)) + kind + body
            + struct.pack('>I', zlib.crc32(kind + body)))

def image(side=1, ct=2, transparency=False):
    channels = {2: 3, 6: 4, 3: 1}[ct]
    pixel = {2: b'\x12\x34\x56', 6: b'\x12\x34\x56\x80', 3: b'\x00'}[ct]
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', side, side, 8, ct, 0, 0, 0))
    extra = chunk(b'PLTE', b'\x12\x34\x56') if ct == 3 else b''
    if transparency:
        extra += chunk(b'tRNS', b'\x00')
    raw = (b'\x00' + pixel * side) * side
    assert len(raw) == side * (1 + side * channels)
    return SIGNATURE + ihdr + extra + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND')

def flip(data, pos):
    return data[:pos] + bytes([data[pos] ^ 1]) + data[pos + 1:]

base = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63103209030000f8009dcc6a21780000000049454e44ae426082')
assert image() == base
assert sha(base) == '4258699ba0181027db1c32e7d9360339ccf87658015a24cd1424a0a5bd1b329c'
cases = {f'prefix-{n:02}': base[:n] for n in range(len(base))}
cases.update({
    'valid-rgb': base,
    'signature-flip': flip(base, 0),
    'ihdr-type-flip': flip(base, 12),
    'ihdr-length-12': base[:11] + b'\x0c' + base[12:],
    'ihdr-body-flip': flip(base, 16),
    'ihdr-crc-flip': flip(base, 29),
    'idat-crc-flip': flip(base, len(base) - 16),
    'iend-crc-flip': flip(base, len(base) - 1),
    'idat-body-cut': base[:42],
    'idat-crc-cut': base[:len(base) - 13],
    'missing-iend': base[:-12],
    'iend-header-only': base[:-4],
    'no-idat': base[:33] + chunk(b'IEND'),
    'bad-zlib-good-crc': base[:33] + chunk(b'IDAT', b'not-zlib') + chunk(b'IEND'),
    'valid-rgba': image(ct=6),
    'valid-palette': image(ct=3),
    'valid-palette-trns': image(ct=3, transparency=True),
})
for side in (128, 256):
    b = image(side)
    cases[f'rgb-{side}'] = b
    cases[f'rgb-{side}-ihdr-only'] = b[:33]
    cases[f'rgb-{side}-no-iend'] = b[:-12]
for ct, label in ((6, 'rgba'), (3, 'palette')):
    cases[f'{label}-256'] = image(256, ct)
cases['palette-trns-256'] = image(256, 3, True)
cases['rgb-2048-ihdr-only'] = image(2048)[:33]

# Names deliberately match actual VPM grammar and address; profiles are not edited.
def findings(fs):
    return [[f.status, f.name, f.observed] for f in fs]

def outcome(fn):
    try:
        return fn()
    except Exception as exc:
        return {'exception': type(exc).__module__ + '.' + type(exc).__name__, 'message': re.sub(r'0x[0-9A-Fa-f]+', '<address>', str(exc))}

def facts(b):
    f = asdict(png_facts('probe.png', b))
    f.pop('name')
    f.pop('size_bytes')  # exactly len(b), recorded in manifest
    f['has_alpha'] = png_facts('probe.png', b).has_alpha
    return f

def decode(b):
    with Image.open(BytesIO(b)) as im:
        im.load()
        return [im.mode, list(im.size)]

def npm(b):
    return findings(npm_texture_findings({'probe.png': b}, profiles.npm))

def vpm(b, kind):
    name = f'T_Probe_{kind}_1.1001.png'
    fs, sets = vpm_texture_findings({name: b}, profiles.vpm, 'T_Probe')
    return {'findings': findings(fs), 'sets': {f'{s}/{u}': sorted(m) for (s, u), m in sets.items()}}

def row(b):
    return {label: outcome(fn) for label, fn in (
        ('facts', lambda: facts(b)), ('Pillow', lambda: decode(b)),
        ('npm', lambda: npm(b)),
        *[(f'vpm-{kind}', lambda kind=kind: vpm(b, kind)) for kind in ('Diffuse', 'ERM', 'Normal')])}

paths = ['src/twinqa/png.py', 'tools/qa/validate_package.py', 'src/twinqa/report.py',
         'src/twinqa/profiles.py', 'src/twinqa/bundle.py', 'standards/NPM_STANDARD.yaml',
         'standards/VPM_STANDARD.yaml', 'standards/DELIVERY_VALIDATOR.yaml',
         'standards/source/source-lock.json', 'tests/qa/test_validator.py',
         'tests/twinqa/test_png_v007_findings.py']
print('ENV', sys.version, PIL.__version__, np.__version__, zlib.ZLIB_VERSION, zlib.ZLIB_RUNTIME_VERSION)
print('SOURCES', json.dumps({p: sha(Path(p).read_bytes()) for p in paths}, sort_keys=True))
print('PDF', profiles.pdf_sha256, profiles.pdf_verified)
print('BASE', len(base), base.hex(), sha(base))
manifest = [[name, len(b), sha(b)] for name, b in cases.items()]
print('MANIFEST', len(manifest), sha(json.dumps(manifest, separators=(',', ':')).encode()))
results = {name: row(b) for name, b in cases.items()}
groups = {}
for name, result in results.items():
    if name.startswith('prefix-'):
        groups.setdefault(json.dumps(result, sort_keys=True), []).append(name)
for result, names in groups.items():
    print('PREFIX', ','.join(names), result)
for name, result in results.items():
    if not name.startswith('prefix-'):
        print('CASE', name, len(cases[name]), sha(cases[name]), json.dumps(result, sort_keys=True))
print('COUNTS', json.dumps({key: dict(Counter(
    value[key].get('exception', 'returned') if isinstance(value[key], dict) else 'returned'
    for value in results.values())) for key in next(iter(results.values()))}, sort_keys=True))
print('DONE', len(results), 'cases;', len(results) * 6, 'observations')

# Exercise the actual outer validate()/report() path with file-like in-memory targets.
# ZIP CRCs are freshly generated and valid even when a PNG member is malformed.
import validate_package as vp
class MemoryTarget(BytesIO):
    def __init__(self, data, name):
        super().__init__(data)
        self.name = name
        self.stem = Path(name).stem
        self.suffix = Path(name).suffix
    def read_bytes(self):
        return self.getvalue()
    def __str__(self):
        return self.name

def application(b, kind):
    if kind == 'npm':
        target = MemoryTarget(b, 'probe.png')
    else:
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            for role in ('Diffuse', 'ERM', 'Normal'):
                archive.writestr(f'T_Probe_{role}_1.1001.png', b)
        target = MemoryTarget(buf.getvalue(), 'SM_Probe.zip')
    report = vp.validate(target, kind, profiles)
    d = report.to_dict()
    stage = next(s for s in report.stages if s.id == ('V006' if kind == 'npm' else 'V007'))
    return {'report_returned': True, 'passed': d['passed'], 'exit_code': d['exit_code'],
            'texture_stage': stage.status, 'findings': findings(stage.findings)}
for name in ('prefix-25', 'idat-crc-flip', 'rgb-256-ihdr-only', 'rgb-256-no-iend'):
    for kind in ('npm', 'vpm'):
        print('APPLICATION', name, kind, json.dumps(outcome(lambda: application(cases[name], kind)), sort_keys=True))
```
