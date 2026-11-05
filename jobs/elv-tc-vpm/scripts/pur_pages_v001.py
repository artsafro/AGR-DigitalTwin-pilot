"""Print 4-byte page headers (every 4096 bytes). Usage: py -3 -I pur_pages_v001.py <file> <first_page> <count>"""
import sys
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
f, n = int(sys.argv[2]), int(sys.argv[3])
print("pages", len(b) / 4096)
for k in range(f, min(f + n, (len(b) + 4095) // 4096)):
    o = k * 4096
    h = b[o:o + 4]
    print(k, o, h.hex(" "), int.from_bytes(h, "big"), int.from_bytes(h, "little"), b[o + 4:o + 20].hex(" "))
