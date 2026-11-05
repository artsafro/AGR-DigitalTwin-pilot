"""Extract images and text from a PureRef 2.x .pur board (read-only input).

Finding (2026-11-05, PureRef 2.0.3 file "2.1"/"2.3"): after a custom first page (version QStrings + 256 px JPEG
thumbnail) the file is an SQLite-style b-tree with 4096-byte pages: table leaf pages start with 0x0d, overflow pages
start with a 4-byte big-endian next-page number (1-based), payload 4092 bytes. This script walks every table leaf
page, decodes each cell record (SQLite record format) and follows overflow chains. It does not need the SQLite header.

Usage: py -3 -I pur_extract_v002.py <input.pur> <out_dir>
Writes: img_NNN.<ext> (blobs with an image signature), strings.txt (all text values), records.json (record summary).
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

PAGE = 4096
U = PAGE  # usable size (reserved bytes assumed 0)


def varint(b, i):
    v = 0
    for k in range(9):
        c = b[i + k]
        if k == 8:
            return (v << 8) | c, i + 9
        v = (v << 7) | (c & 0x7F)
        if c < 0x80:
            return v, i + k + 1
    return v, i + 9


def page(b, n):
    return b[(n - 1) * PAGE:n * PAGE]


def read_payload(b, pg, off):
    P, i = varint(pg, off)
    rowid, i = varint(pg, i)
    X = U - 35
    if P <= X:
        return rowid, P, bytes(pg[i:i + P]), True
    M = ((U - 12) * 32 // 255) - 23
    K = M + ((P - M) % (U - 4))
    local = K if K <= X else M
    data = bytearray(pg[i:i + local])
    nxt = struct.unpack(">I", pg[i + local:i + local + 4])[0]
    seen = set()
    while nxt and len(data) < P:
        if nxt in seen or (nxt - 1) * PAGE >= len(b):
            return rowid, P, bytes(data), False
        seen.add(nxt)
        op = page(b, nxt)
        data += op[4:4 + min(U - 4, P - len(data))]
        nxt = struct.unpack(">I", op[:4])[0]
    return rowid, P, bytes(data), len(data) == P


def decode_record(data, raw_text=False):
    hlen, i = varint(data, 0)
    types = []
    while i < hlen:
        t, i = varint(data, i)
        types.append(t)
    vals = []
    p = hlen
    sizes = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 6, 6: 8, 7: 8, 8: 0, 9: 0}
    for t in types:
        if t in sizes:
            n = sizes[t]
            raw = data[p:p + n]
            if t == 0:
                v = None
            elif t == 7:
                v = struct.unpack(">d", raw)[0] if len(raw) == 8 else None
            elif t in (8, 9):
                v = t - 8
            else:
                v = int.from_bytes(raw, "big", signed=True)
        elif t >= 12 and t % 2 == 0:
            n = (t - 12) // 2
            v = bytes(data[p:p + n])
        else:
            n = (t - 13) // 2
            v = bytes(data[p:p + n]) if raw_text else data[p:p + n].decode("utf-8", "replace")
        vals.append(v)
        p += n
    return vals


def img_ext(v):
    if v[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if v[:3] == b"\xff\xd8\xff":
        return "jpg"
    if v[:4] == b"RIFF" and v[8:12] == b"WEBP":
        return "webp"
    if v[:2] == b"BM":
        return "bmp"
    if v[4:12] in (b"ftypheic", b"ftypmif1", b"ftypheix", b"ftypavif"):
        return "heic"
    if v[:4] in (b"II*\x00", b"MM\x00*"):
        return "tif"
    if v[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    b = Path(src).read_bytes()
    npages = len(b) // PAGE + (1 if len(b) % PAGE else 0)
    records, texts, images = [], [], []
    for n in range(2, npages + 1):
        pg = page(b, n)
        if len(pg) < 8 or pg[0] != 0x0D:
            continue
        ncell = struct.unpack(">H", pg[3:5])[0]
        if ncell == 0 or 8 + 2 * ncell > PAGE:
            continue
        for c in range(ncell):
            off = struct.unpack(">H", pg[8 + 2 * c:10 + 2 * c])[0]
            if off < 8 or off >= PAGE:
                continue
            try:
                rowid, P, data, complete = read_payload(b, pg, off)
                vals = decode_record(data)
            except Exception as e:  # noqa: BLE001 - tolerant scan, report and continue
                records.append({"page": n, "cell": c, "error": str(e)})
                continue
            summ = []
            for k, v in enumerate(vals):
                if isinstance(v, bytes):
                    ext = img_ext(v)
                    if ext and len(v) > 1000:
                        h = hashlib.sha256(v).hexdigest()
                        if h not in {im["sha256"] for im in images}:
                            name = f"img_{len(images) + 1:03d}.{ext}"
                            (out / name).write_bytes(v)
                            images.append({"file": name, "page": n, "rowid": rowid, "col": k, "size": len(v),
                                           "sha256": h, "complete": complete})
                        summ.append(f"<{ext} {len(v)}B>")
                    else:
                        summ.append(f"<blob {len(v)}B {v[:24].hex()}>")
                        # blobs may hold UTF-16 text (Qt serialisation)
                        for enc in ("utf-16-be", "utf-16-le"):
                            try:
                                s = v.decode(enc)
                            except UnicodeDecodeError:
                                continue
                            if sum(ch.isalpha() for ch in s) > 0.5 * max(1, len(s)):
                                texts.append(f"page {n} row {rowid} col {k} blob-{enc}: {s}")
                elif isinstance(v, str):
                    summ.append(v if len(v) < 300 else v[:300] + "...")
                    if any(ch.isalpha() for ch in v):
                        texts.append(f"page {n} row {rowid} col {k}: {v}")
                else:
                    summ.append(v)
            records.append({"page": n, "cell": c, "rowid": rowid, "payload": P, "complete": complete,
                            "values": summ})
    (out / "records.json").write_text(json.dumps(records, ensure_ascii=False, indent=1, default=str),
                                      encoding="utf-8")
    (out / "strings.txt").write_text("\n".join(texts), encoding="utf-8")
    meta = {"source": str(src), "size": len(b), "sha256": hashlib.sha256(b).hexdigest(), "images": images,
            "records": len(records), "text_values": len(texts)}
    (out / "extract_manifest.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"images": len(images), "records": len(records), "texts": len(texts),
                      "incomplete": sum(1 for im in images if not im["complete"])}))


if __name__ == "__main__":
    main()
