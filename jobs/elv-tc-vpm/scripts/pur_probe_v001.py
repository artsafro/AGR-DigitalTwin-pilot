"""Probe a .pur file: header hex, signature counts and offsets. Usage: py -3 -I pur_probe_v001.py <file> [offset] [len]"""
import re
import sys
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
off = int(sys.argv[2]) if len(sys.argv) > 2 else 0
ln = int(sys.argv[3]) if len(sys.argv) > 3 else 512
for i in range(off, min(off + ln, len(b)), 32):
    chunk = b[i:i + 32]
    print(f"{i:10d} {chunk.hex(' ')}  {''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)}")
if len(sys.argv) <= 2:
    for name, sig in [("png", rb"\x89PNG"), ("jpg", rb"\xff\xd8\xff"), ("IEND", rb"IEND"), ("zlib", rb"\x78[\x01\x5e\x9c\xda]"),
                      ("webp", rb"RIFF....WEBP"), ("bmp", rb"BM....\x00\x00\x00\x00"), ("QImg", rb"Q\x00I\x00m")]:
        offs = [m.start() for m in re.finditer(sig, b, re.S)]
        print(name, len(offs), offs[:20])
