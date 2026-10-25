# Attached-decor fixture provenance

`contacts.json` contains **27 real polygon pairs**, extracted without rounding or simplification
from the retained parent #525 evidence. Coordinates are local metres, not synthetic geometry.
`source_root` is a read-only evidence location; normal pytest needs only this committed JSON.
Every case records the source NPZ, zero-based source polygon index and exact vertex cycle;
`sources` records SHA-256 of all four input archives. No NPZ/binary or Git LFS is added.

Selection comes from `rootcause/railings/a2.py`, `RAILINGS.md` A/B and
`rootcause/louvre_top/pairs_ours.json`: four AC units (2/3/5/6), railing face 28 / coping 102
in v013/v027/v028, two AC stubs in v027/v028, all 16 louvre/soffit contact pairs.
FBX source indices follow the parent's scripts (zero-based), not Max's one-based selection.
Original `source_part` is empty for the combined FBX arrays; case labels retain the pair roles.

Reproduce each polygon from an archive `d = numpy.load(path, allow_pickle=False)`:

```python
prefix = source_part + '__' if source_part else ''
s, n = int(d[prefix + 'ls'][source_face]), int(d[prefix + 'lt'][source_face])
vertices = d[prefix + 'co'][d[prefix + 'lv'][s:s+n]].astype(float)
```

Assert exact array equality and archive hashes before using these as real evidence.
These are deliberately defective originals, not approved replacement model parts.
The 0.7300-vs-0.73 and 130 mm controls and generated probes are explicitly synthetic.
The five synthetic louvre thresholds copy `rootcause/louvre_top/unit_cases.py::rail_soffit`
(SHA-256 `4b25621a5d0d97296d1bf8cfef32bd5549d633e671eb2d21ca786ae892d58808`).
6 mm clears the 5 mm xView diagnostic, not the conservative 10 mm construction check.
No fresh native DCC measurements, production rebuild or human acceptance are claimed.
