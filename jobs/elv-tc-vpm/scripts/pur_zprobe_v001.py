"""Tolerant PNG walk: collect IDAT data, report gaps between chunks, test zlib decode progress.
Usage: py -3 -I pur_zprobe_v001.py <file> <png_sig_offset>"""
import struct
import sys
import zlib
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
s = int(sys.argv[2])
w, h, bd, ct = struct.unpack(">IIBB", b[s + 16:s + 26])
print("IHDR", w, h, bd, ct)
j = s + 33
d = zlib.decompressobj()
out = 0
gaps = []
n = 0
while True:
    ln = struct.unpack(">I", b[j:j + 4])[0]
    t = b[j + 4:j + 8]
    if t == b"IEND":
        print("IEND at", j)
        break
    if t != b"IDAT":
        k = b.find(b"IDAT", j)
        k2 = b.find(b"IEND", j)
        nxt = min(x for x in (k, k2) if x >= 0) - 4
        gaps.append((j, nxt - j))
        j = nxt
        continue
    data = b[j + 8:j + 8 + ln]
    n += 1
    try:
        out += len(d.decompress(data))
    except zlib.error as e:
        print("zlib error in IDAT", n, "at", j, e, "decoded", out)
        break
    j += 12 + ln
print("idat", n, "decoded bytes", out, "expected", h * (w * (4 if ct == 6 else 3) + 1))
print("gaps (first 20):", gaps[:20], "count", len(gaps))
