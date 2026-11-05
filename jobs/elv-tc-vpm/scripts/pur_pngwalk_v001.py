"""Walk PNG chunks from an offset and print them. Usage: py -3 -I pur_pngwalk_v001.py <file> <offset> [max]"""
import struct
import sys
from pathlib import Path

b = Path(sys.argv[1]).read_bytes()
j = int(sys.argv[2]) + 8
mx = int(sys.argv[3]) if len(sys.argv) > 3 else 40
for k in range(mx):
    ln = struct.unpack(">I", b[j:j + 4])[0]
    typ = b[j + 4:j + 8]
    print(j, ln, typ)
    if not typ.isalpha():
        print("bad chunk; next bytes:", b[j - 16:j + 32].hex(" "))
        break
    j += 12 + ln
    if typ == b"IEND":
        print("end", j)
        break
