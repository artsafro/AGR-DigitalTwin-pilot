"""List IDAT/IHDR/IEND tag offsets in a range. Usage: py -3 -I pur_idat_v001.py <file> <start> <end>"""
import re
import struct
import sys
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
s, e = int(sys.argv[2]), int(sys.argv[3])
for m in re.finditer(rb"IDAT|IHDR|IEND|PLTE|iCCP|pHYs|sRGB", b[s:e]):
    o = s + m.start()
    ln = struct.unpack(">I", b[o - 4:o])[0]
    print(o - 4, m.group(), ln, "next_chunk_at", o - 4 + 12 + ln)
