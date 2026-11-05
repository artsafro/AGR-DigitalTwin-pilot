"""Extract embedded images and readable strings from a PureRef .pur board (read-only input).

Usage: py -3 -I pur_extract_v001.py <input.pur> <out_dir>
Carves PNG (chunk walk to IEND) and JPEG (marker walk to EOI after SOS) blobs by signature,
dumps UTF-16BE (Qt QString), UTF-16LE and UTF-8 strings (>= 4 chars) into strings.txt.
"""
import hashlib
import json
import re
import struct
import sys
from pathlib import Path


def carve_png(b, i):
    j = i + 8
    while j + 8 <= len(b):
        ln = struct.unpack(">I", b[j:j + 4])[0]
        typ = b[j + 4:j + 8]
        j += 12 + ln
        if typ == b"IEND":
            return j
        if ln > len(b):
            return None
    return None


def carve_jpeg(b, i):
    j = i + 2
    n = len(b)
    while j + 4 <= n:
        if b[j] != 0xFF:
            return None
        m = b[j + 1]
        if m == 0xFF:
            j += 1
            continue
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            j += 2
            continue
        if m == 0xD9:
            return j + 2
        ln = struct.unpack(">H", b[j + 2:j + 4])[0]
        j += 2 + ln
        if m == 0xDA:  # entropy-coded data: scan to next non-RST marker
            while j + 1 < n:
                if b[j] == 0xFF and b[j + 1] != 0x00 and not (0xD0 <= b[j + 1] <= 0xD7):
                    break
                j += 1
    return None


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=False)
    b = src.read_bytes()
    found = []
    for m in re.finditer(rb"\x89PNG\r\n\x1a\n", b):
        e = carve_png(b, m.start())
        if e:
            found.append((m.start(), e, "png"))
    for m in re.finditer(rb"\xff\xd8\xff", b):
        if any(s <= m.start() < e for s, e, _ in found):
            continue  # nested thumbnail inside another blob
        e = carve_jpeg(b, m.start())
        if e:
            found.append((m.start(), e, "jpg"))
    found.sort()
    # drop blobs nested inside an earlier blob (EXIF thumbnails)
    kept, last_end = [], -1
    for s, e, t in found:
        if s < last_end:
            continue
        kept.append((s, e, t))
        last_end = e
    manifest = []
    for k, (s, e, t) in enumerate(kept, 1):
        data = b[s:e]
        name = f"img_{k:03d}.{t}"
        (out / name).write_bytes(data)
        manifest.append({"file": name, "offset": s, "size": e - s,
                         "sha256": hashlib.sha256(data).hexdigest()})
    # strings outside image blobs
    mask = bytearray(len(b))
    for s, e, _ in kept:
        mask[s:e] = b"\x01" * (e - s)
    lines = []
    seen = set()
    pats = [
        ("utf16be", rb"(?:\x00[\x20-\x7e]|[\x04][\x00-\xff]){4,}", "utf-16-be"),
        ("utf16le", rb"(?:[\x20-\x7e]\x00|[\x00-\xff][\x04]){4,}", "utf-16-le"),
        ("utf8", rb"(?:[\x20-\x7e]|[\xd0\xd1][\x80-\xbf]|\xe2\x80[\x90-\xbf]){4,}", "utf-8"),
    ]
    for tag, pat, enc in pats:
        for m in re.finditer(pat, b):
            if mask[m.start()]:
                continue
            raw = m.group()
            if enc.startswith("utf-16") and len(raw) % 2:
                raw = raw[:-1]
            try:
                txt = raw.decode(enc)
            except UnicodeDecodeError:
                continue
            if sum(c.isalpha() for c in txt) < 3:
                continue
            if enc != "utf-8" and not re.search(r"[A-Za-zЀ-ӿ]{3}", txt):
                continue
            key = (tag, txt)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"{m.start():10d}\t{tag}\t{txt}")
    (out / "strings.txt").write_text("\n".join(lines), encoding="utf-8")
    meta = {"source": str(src), "size": len(b), "sha256": hashlib.sha256(b).hexdigest(),
            "images": manifest, "strings": len(lines)}
    (out / "extract_manifest.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"images": len(manifest), "strings": len(lines), "sha256": meta["sha256"]}))


if __name__ == "__main__":
    main()
