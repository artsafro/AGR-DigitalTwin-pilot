"""Test the page hypothesis: a PNG chunk body is interrupted every PAGE bytes of file by HDR foreign bytes.
For each phase c, drop HDR bytes at file offsets with (off % PAGE) == c inside the chunk, then check CRC.
Usage: py -3 -I pur_page_test_v001.py <file> <chunk_off> <page> <hdr>"""
import struct
import sys
import zlib
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
o, page, hdr = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
ln = struct.unpack(">I", b[o:o + 4])[0]
typ = b[o + 4:o + 8]
for c in range(page):
    # rebuild body skipping headers
    out = bytearray()
    p = o + 8
    while len(out) < ln:
        if p % page == c:
            p += hdr
            continue
        nxt = p + (c - p % page) % page
        if nxt == p:
            nxt = p + page
        take = min(nxt - p, ln - len(out))
        out += b[p:p + take]
        p += take
    if p % page == c:
        p += hdr
    crc = struct.unpack(">I", b[p:p + 4])[0]
    if zlib.crc32(bytes(out), zlib.crc32(typ)) == crc:
        print("MATCH phase", c, "crc at", p, "next chunk at", p + 4)
        break
else:
    print("no match")
