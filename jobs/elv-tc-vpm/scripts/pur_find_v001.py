"""Find all offsets of a hex byte pattern in a file. Usage: py -3 -I pur_find_v001.py <file> <hex> [start] [end] [max]"""
import sys
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
pat = bytes.fromhex(sys.argv[2])
s = int(sys.argv[3]) if len(sys.argv) > 3 else 0
e = int(sys.argv[4]) if len(sys.argv) > 4 else len(b)
mx = int(sys.argv[5]) if len(sys.argv) > 5 else 60
offs = []
i = b.find(pat, s, e)
while i >= 0:
    offs.append(i)
    i = b.find(pat, i + 1, e)
print(len(offs))
for o in offs[:mx]:
    print(o, o % 4096, b[o - 8:o + 24].hex(" "))
