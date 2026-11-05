"""For PNG chunks at given offsets, test CRC at the declared length and search other lengths (incremental CRC).
Usage: py -3 -I pur_crc_v001.py <file> <off1> [off2 ...]   (offset = start of the 4-byte length field)"""
import struct
import sys
import zlib
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
for a in sys.argv[2:]:
    o = int(a)
    ln = struct.unpack(">I", b[o:o + 4])[0]
    ok = zlib.crc32(b[o + 4:o + 8 + ln]) == struct.unpack(">I", b[o + 8 + ln:o + 12 + ln])[0]
    hit = None
    if not ok:
        c = zlib.crc32(b[o + 4:o + 8])
        p = o + 8
        for k in range(0, ln + 40000):
            if c == struct.unpack(">I", b[p:p + 4])[0]:
                hit = k
                break
            c = zlib.crc32(b[p:p + 1], c)
            p += 1
    print(o, b[o + 4:o + 8], ln, "crc_ok" if ok else f"crc_bad, crc_matches_at_len={hit}")
