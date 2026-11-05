"""Find where K extra bytes were inserted into a PNG chunk body, by CRC.
Usage: py -3 -I pur_insert_find_v001.py <file> <chunk_len_field_offset> <body_len_in_file> <declared_len>"""
import struct
import sys
import zlib
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
o, blen, dlen = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
k = blen - dlen
body = b[o + 8:o + 8 + blen]
target = struct.unpack(">I", b[o + 8 + blen:o + 12 + blen])[0]
typ = b[o + 4:o + 8]
# suffix CRCs need combine; instead use: crc(prefix + suffix) computed by continuing prefix crc over suffix.
# Try aligned candidates first (every file offset), with prefix crc cached in steps of 256.
pref = zlib.crc32(typ)
hits = []
c = pref
for p in range(0, dlen + 1):
    c_full = zlib.crc32(body[p + k:], c)
    if c_full == target:
        hits.append((p, o + 8 + p, (o + 8 + p) % 4096))
        break
    c = zlib.crc32(body[p:p + 1], c)
print("extra", k, "hits", hits)
if hits:
    p = hits[0][0]
    print("inserted bytes:", body[p:p + k].hex(" "))
