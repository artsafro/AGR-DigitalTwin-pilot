# Research: GeoJSON imageBase64 — does JPEG header acceptance imply pixel decodability?

**Card:** t_e4adae5c · **Status:** report only, `delivery_passed=false` · **Repo SHA:** `fc0a1fea4589ca48a59db6534a100f2fad87f517`

## Summary

`_image` (src/twinqa/geojson.py:73) checks an `imageBase64` value with `Image.open` plus
`.size`/`.format` and never calls `load()`. `Image.open` is **lazy**: it parses only the JPEG
header markers and returns an image object whose pixel data is decoded on first `load()`. Two
consequences follow, both confirmed empirically on Pillow 12.3.0:

1. **Header acceptance does not imply pixel decodability (false pass).** A JPEG with a complete,
   valid header but truncated/corrupted entropy data passes `_image` as `pass` ("JPG 256x256")
   while `img.load()` raises `OSError: image file is truncated`. For the frozen corpus, *every*
   strict prefix of a valid 256×256 JPEG in the range `[623, 29000]` bytes (28 378 prefixes) opens
   successfully and passes `_image`, yet none of them fully decodes; only the complete 29 001-byte
   file decodes. Format-metadata acceptance is therefore **not** a delivery verdict.
2. **Exception escape through V011.** A JPEG truncated mid-header (585 strict prefixes in
   `[6, 622]`) makes `Image.open` raise `OSError("Truncated File Read")` from
   `ImageFile._safe_read`. `_image` catches only `(binascii.Error, UnidentifiedImageError, ValueError)`,
   and `Image.open`'s `_open_core` re-raises `OSError` (`except BaseException: raise`), so the
   exception escapes `_image` → `geojson_findings` → the whole validator as an unhandled traceback
   (exit 1, **no JSON report**).

Malformed base64, valid-base64-of-non-image bytes, wrong-size JPEG and PNG all correctly return a
`fail` finding (no escape). A single flipped entropy byte decodes without exception (silent pixel
corruption, not conformance proof). Two isolated fix proposals (S / M) are given at the end; both
require a separate authorized decision, per card policy.

## Findings

### F1 — `_image` is lazy: `Image.open` reads the header, not pixels

`src/twinqa/geojson.py:73-83` does `img = Image.open(BytesIO(base64.b64decode(value, validate=True)))`
then reads `img.size` and `img.format`. No `load()` / `getdata()` / `verify()`.

Pillow primary source (installed venv `.venv/Lib/site-packages/PIL/`):

- `Image.open` → `_open_core` (Image.py:3660-3687) calls `factory(fp, filename)` — for JPEG this is
  `JpegImagePlugin.JpegImageFile._open` (JpegImagePlugin.py:347-402), which only walks the SOI/SOF/DHT/SOS
  marker headers to derive `self.size` and `self.format`, then `_decompression_bomb_check(im.size)`. Pixel
  data is not decoded here.
- `Image.load` (Image.py:968-972): "Allocates storage for the image and loads the pixel data. In normal
  cases, you don't need to call this method, since the Image class automatically loads an opened image
  when it is [accessed]." — the decode is deferred until `load()`/first pixel access.
- `JpegImagePlugin.load_read` (JpegImagePlugin.py:411-426) is only exercised during `load()`, and
  `ImageFile.load` (ImageFile.py:395-409) raises `OSError("image file is truncated (N bytes not processed)")`
  when `LOAD_TRUNCATED_IMAGES` is False (the default; never changed in this probe).

Conclusion: `_image`'s `pass` verdict rests on **header metadata**, never on a pixel-decode observation.

### F2 — False pass: header-valid JPEG, undecodable pixels, still `pass`

Frozen corpus witness "EOI removed" (valid 256×256 JPEG minus its trailing `FF D9`):

| Observation | Result |
|---|---|
| `_image(value)` | `pass` — observed `"JPG 256x256"` |
| `Image.open` | ok, format `JPEG`, size `(256, 256)` |
| `img.load()` | **`raise OSError: image file is truncated (8 bytes not processed)`** |

Aggregated strict-prefix sweep of the valid JPEG (`valid[:k]`, k = 1 … 29 000):

| k range | `_image` outcome | `load()` outcome | category |
|---|---|---|---|
| 1 … 5 | `fail` (UnidentifiedImageError → "not a decodable image") | n/a | returns finding |
| 6 … 622 | **`RAISE OSError("Truncated File Read")`** (585 prefixes, non-contiguous) | n/a | **exception escape** |
| 623 … 29 000 | `pass` "JPG 256x256" (28 378 prefixes) | **`raise OSError` (truncated) for every one** | **false pass** |
| 29 001 (full) | `pass` | `decoded` | clean |

First `pass` occurs at k=623; at that point `load()` already raises ("0 bytes not processed"). No strict
prefix fully decodes. The boundary between "returns a fail finding" and "false pass" is the moment the
header is complete enough for `Image.open` to report `format="JPEG", size=(256,256)` — which is *before*
any scan data is validated.

### F3 — Exception escape through V011: `OSError("Truncated File Read")`

A JPEG truncated mid-header (e.g. the first 6…622 bytes of the valid file) makes `Image.open` raise
`OSError("Truncated File Read")`. Primary source: `ImageFile._safe_read`
(`.venv/Lib/site-packages/PIL/ImageFile.py:717-739`, raise at lines 725 and 737).

Why it escapes:

1. `Image.open`'s `_open_core` swallows only `(SyntaxError, IndexError, TypeError, struct.error)`
   (Image.py:3680) and re-raises everything else via `except BaseException: raise` (Image.py:3683-3686).
   `OSError` is a `BaseException` subclass but not in the swallow tuple, so it propagates unchanged.
2. `_image` catches only `(binascii.Error, UnidentifiedImageError, ValueError)`
   (src/twinqa/geojson.py:79). `OSError` is not caught → propagates.
3. The `_image` call site in `geojson_findings` (src/twinqa/geojson.py:136) is **not** wrapped, so
   `geojson_findings` raises, `validate_vpm_zip` (tools/qa/validate_package.py:111) raises, and the
   single-GeoJSON path (tools/qa/validate_package.py:208) raises → `main()` traceback, exit code 1,
   **no report is printed** (not even a JSON error object).

`OSError("Truncated File Read")` is the only escape observed in the whole corpus. `DecompressionBombError`
(Image.py:79, raised by `_decompression_bomb_check` at open time) would be a second, different escape path,
but it is excluded from this corpus by card policy (no decompression-bomb/resource-exhaustion inputs) and
cannot be triggered by a 256×256 image anyway (far below `MAX_IMAGE_PIXELS`).

### F4 — Inputs that correctly return findings (no escape)

| Input | `_image` verdict | mechanism |
|---|---|---|
| malformed base64: `"not base64!!!"` | `fail` "not a decodable image (Error)" | `b64decode(validate=True)` → `binascii.Error` (caught) |
| wrong padding/length: `"A==="`, `"A"` | `fail` (Error) | `binascii.Error` (caught) |
| valid b64 + embedded newline | `fail` (Error) | `validate=True` rejects non-alphabet chars |
| valid b64 of non-image bytes (`b"hello world…"`) | `fail` "…(UnidentifiedImageError)" | `Image.open` → `UnidentifiedImageError` (caught) |
| wrong-size JPEG (128×128) | `fail` "JPEG 128x128" | format/size gate |
| PNG control (256×256) | `fail` "PNG 256x256" | format gate |

Note: header-truncated prefixes k=1…5 also return `fail` via `UnidentifiedImageError` (the underlying
`SyntaxError("not a JPEG file")` is converted to `UnidentifiedImageError` by `_open_core`). The escape
begins only at k=6, where `_safe_read`'s `OSError` path replaces the `SyntaxError` path.

### F5 — Single entropy-byte corruption decodes (no exception), proving "decode ≠ conformance"

Predeclared, never tuned: flip one byte (XOR 0xFF) at absolute offset `len(JPEG)//2 = 14500` and at
`len(JPEG)-10 = 28991` of the valid 29 001-byte JPEG. Both are inside the scan/entropy region (SOS marker
at offset 609). Both pass `_image` and **`load()` decodes without exception** — libjpeg recovers from a
single corrupted entropy byte. This is the card's own caveat made concrete: a successful load is a
pixel-decode observation, not proof of complete JPEG conformance (the corrupted bytes very likely yield
wrong pixels, silently).

## Corpus and methodology

- **Pillow:** 12.3.0 (pinned by `pyproject.toml`; `.venv` reports 12.3.0, `_imaging.cp314-win_amd64.pyd`).
- **Repo source SHA:** `fc0a1fea4589ca48a59db6534a100f2fad87f517`.
- **Generation (deterministic, byte-reproducible):** `Image.fromarray(arr, "RGB").save(..., format="JPEG",
  quality=85, subsampling=0, optimize=False, progressive=False)` over a 256×256 numpy array
  `R=x%256, G=y%256, B=(x*7+y*13)%256`.
- **Canonical inputs (SHA-256):**
  - valid 256×256 JPEG — `bb65d62a2885595819da7bd884901a974503ce2eefd68cc1b499ad3177d38a7f` (29 001 B; SOS at 609; trailing `FF D9` present).
  - 256×256 PNG control — `9fcd41f59629f7090addeb2a84f7ebc717d590176b8f2ed078b423dcae97b145`.
- **Outer-validator routing** used a second deterministic baseline JPEG
  `11f14faad7c2152120afbdeb8a014f43d96de58f04d44578fe7ff348dcaa88a5` (gradient `(x*7+y*13+c*37)%256`);
  the qualitative outcomes (false pass, escape) are structural and baseline-independent.
- **Constraints honoured:** fresh context-managed `BytesIO`/`Image` per call; `LOAD_TRUNCATED_IMAGES` left
  at its default `False`; warnings recorded via `warnings.catch_warnings(record=True)` but never suppressed;
  no decompression-bomb / resource-exhaustion corpus; corruptions predeclared, never tuned after outcomes.

## How it applies to this repository

- `src/twinqa/geojson.py:73-83` — `_image`: the lazy `Image.open` + size/format gate; caught-tuple
  `(binascii.Error, UnidentifiedImageError, ValueError)` omits `OSError`.
- `src/twinqa/geojson.py:136` — `_image(props["imageBase64"])` call site, unwrapped.
- `tools/qa/validate_package.py:111` — ZIP V011 wiring (`validate_vpm_zip` → `geojson_findings`).
- `tools/qa/validate_package.py:208` — single-GeoJSON V011 wiring.
- `standards/VPM_STANDARD.yaml:136` — `imageBase64_input: {format: jpg, width_px: 256, height_px: 256}`;
  `docs/domain/areas/package.md:45` — PKG-23 "Decode base64 and read JPEG size".
- Pillow internals cited above are in the project venv
  `.venv/Lib/site-packages/PIL/{Image.py, ImageFile.py, JpegImagePlugin.py}` (version 12.3.0).

## Real outer-validator routing (single GeoJSON + tiny ZIP)

Synthetic document is otherwise valid (all 20 property keys present, `FNO_code="123"`, `Glasses: []` inside
the feature, `Point` geometry with 0-decimal coordinates), so only `imageBase64` varies.

**Single GeoJSON** (`validate_package.py <file>.geojson --profile vpm --json`):

| witness | V011 stage | exit | passed | JSON |
|---|---|---|---|---|
| clean (valid JPEG) | `pass` (imageBase64 + Glasses + schema) | 2 | false | yes |
| false pass (EOI removed) | **`pass`** (imageBase64 "JPG 256x256") | 2 | false | yes |
| escape (JPEG[:100]) | — | 1 | — | **no** (traceback `OSError: Truncated File Read`) |

`exit_code` semantics (src/twinqa/report.py:62-67): `passed` is false for a single GeoJSON because the other
`blocking` machine stages are `not_run` (never run without the FBX scene); exit 2 = "no fail, only
pass/not_run/review remain", exit 1 = "a fail". The false-pass witness therefore reports **V011 = pass** and
exit 2 — indistinguishable from a genuinely decodable image — while its pixels cannot actually be decoded.

**Tiny synthetic ZIP** (`SM_Test.zip` = 27-byte binary FBX 7.4 header + 3 PNGs + `SM_Test.geojson`):

| witness | V011 | unrelated non-pass stages | exit | JSON |
|---|---|---|---|---|
| clean | `pass` | V007 fail (texture set), V012 review (archive name), others not_run | 1 | yes |
| false pass | `pass` | same unrelated failures | 1 | yes |
| escape | — | — | 1 | **no** (whole report aborted) |

The `imageBase64`/V011 verdict is independent of the unrelated package failures (V007/V012). The escape
witness aborts the **entire** report — the ZIP validator prints no JSON at all, so one truncated JPEG in one
GeoJSON kills every other stage's output.

## Self-contained reproducer

```python
# Requires: pip install pillow  (project venv: Pillow==12.3.0)
import base64
from io import BytesIO
import numpy as np
from PIL import Image

def jpeg():
    y, x = np.mgrid[0:256, 0:256]
    a = np.dstack([(x % 256), (y % 256), ((x * 7 + y * 13) % 256)]).astype("u1")
    b = BytesIO()
    Image.fromarray(a, "RGB").save(b, format="JPEG", quality=85, subsampling=0,
                                   optimize=False, progressive=False)
    return b.getvalue()

def image(value):                    # mirrors src/twinqa/geojson.py:_image
    from PIL import Image, UnidentifiedImageError
    import binascii
    if not isinstance(value, str) or not value:
        return "fail(empty)"
    try:
        im = Image.open(BytesIO(base64.b64decode(value, validate=True)))
        size, fmt = im.size, im.format
    except (binascii.Error, UnidentifiedImageError, ValueError) as e:
        return f"fail({type(e).__name__})"
    return "pass" if fmt == "JPEG" and size == (256, 256) else f"fail({fmt} {size})"

J = jpeg()

# 1) false pass: EOI removed -> header ok, pixels undecodable
eoi = base64.b64encode(J[:-2]).decode()
print("EOI-removed  _image:", image(eoi))            # -> pass
try:
    Image.open(BytesIO(J[:-2])).load()
except OSError as e:
    print("EOI-removed  load  : OSError:", e)        # -> image file is truncated (8 bytes not processed)

# 2) exception escape: mid-header truncation
trunc = base64.b64encode(J[:100]).decode()
try:
    image(trunc)
except OSError as e:
    print("truncated    _image: UNCAUGHT", e)        # -> OSError: Truncated File Read
```

## Proposed next tasks

Both change `_image`'s acceptance or normalize a new exception; **each requires a separate authorized task /
user decision and is not adopted here** (card policy).

### P1 (S) — Fail closed: add a pixel-decode check to `_image`
Scope: inside `_image`'s existing `try`, after the format/size gate, force one pixel-decode observation
(`img.load()` or `img.getdata()[0]`) and map any `OSError`/`SyntaxError`/decode failure to a `fail` finding
("imageBase64 not decodable …"). Concrete pairs: EOI-removed JPEG → `fail` instead of `pass`;
valid JPEG → `pass` unchanged; single flipped entropy byte → still `pass` (decode succeeds). Value: closes the
false-pass so an undecodable image can no longer earn V011 = pass / exit 2. Effort: S (≈30 lines + regression
tests). `Archive: no roadmap link` (no open roadmap issue covers validator robustness; thematic lineage is the
now-closed #415/#418 PNG decode isolation).

### P2 (M) — Normalize `OSError` into a finding at the V011 boundary
Scope: extend the caught tuple / wrap the `_image` call in `geojson_findings` so `OSError` (and other Pillow
IO errors) become a `fail` finding instead of aborting the whole report. Concrete pairs: JPEG[:100] → a clean
`fail` "not a decodable image (OSError)" + JSON report (exit 1), instead of an unhandled traceback with no
report; a valid image → unchanged. Value: a single truncated JPEG in one GeoJSON no longer suppresses every
other stage's report. Effort: M (touch `geojson_findings`, add tests, consider `DecompressionBombError` in the
same breath). `Archive: no roadmap link`.

## Open questions for the user

1. Should `imageBase64` be *delivery-blocking* on pixel decodability (P1), or is header-level acceptance
   (current behavior, matches the letter of PKG-23 "read JPEG size") the intended bar for V011?
2. Is the unhandled `OSError` escape (P2) in scope for the same change as #415/#418's PNG decode isolation,
   or tracked as its own bug?
3. The regulation (reg p.54 table 1 row 19) says "256×256 JPG"; nothing there requires the pixels to decode.
   Do you want the strict-JSON report to remain intact (never traceback) even when a customer uploads a
   corrupted image — i.e. is "always return a report" a hard guarantee we should encode?
