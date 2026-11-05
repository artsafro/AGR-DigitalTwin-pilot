"""Print board layout: for each cell holding a QTransform blob (len 0x50 + 9 doubles), print row values and dx, dy.
Usage: py -3 -I pur_layout_v001.py <input.pur> <page> [<page> ...]"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pur_extract_v002 import decode_record, read_payload, page  # noqa: E402

b = Path(sys.argv[1]).read_bytes()
for n in map(int, sys.argv[2:]):
    pg = page(b, n)
    ncell = struct.unpack(">H", pg[3:5])[0]
    for c in range(ncell):
        off = struct.unpack(">H", pg[8 + 2 * c:10 + 2 * c])[0]
        try:
            rowid, P, data, ok = read_payload(b, pg, off)
            vals = decode_record(data, raw_text=True)
        except Exception as e:  # noqa: BLE001
            print(n, c, "err", e, pg[off:off + 40].hex(" "))
            continue
        out = []
        for v in vals:
            raw = v
            if isinstance(raw, bytes) and raw[:4] == b"\x00\x00\x00\x50" and len(raw) >= 77:
                d = struct.unpack(">9d", raw[5:77])
                out.append(f"T(sx={d[0]:.3f} sy={d[4]:.3f} dx={d[6]:.1f} dy={d[7]:.1f})")
            elif isinstance(v, (bytes, str)) and len(v) > 40:
                out.append(f"<{len(v)}>")
            else:
                out.append(v)
        print(n, "row", rowid, out)
