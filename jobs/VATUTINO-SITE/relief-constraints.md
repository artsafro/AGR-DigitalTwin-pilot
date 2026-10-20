# Relief cut-spacing decision — issue #295

2026-10-19, continuation of PR #308 at `e127106`.
Status: **resolved** — orchestrator 2026-10-19 14:57: TIN edges closer than 1 m are allowed inside cells that need
relief correction; implemented in v005, see `ground-build-v005.md`. The analysis below is kept as the record.

## Constraints being checked

User correction E: one 4 x 4 m master; no added lines closer than 1 m.
User follow-up: method C; add TIN-edge cuts only in cells whose relief deviation exceeds
10 mm; final relief deviation <= 10 mm ("разница в 1 см не страшна").

The distinction requiring a decision is whether the 1 m spacing applies to TIN slope-break
edges too, or only to added regular grid lines. No relaxation of either requirement is assumed.

## Measured existing result

Read-only probe against the adapter output and v002 mesh:

- 10,430 surface triangles; 822 face centres over 10 mm; 283 distinct XY grid cells affected
  (unlike the previous report's cell count, this count does not count layers separately).
- Maximum centre error: 790.4173749305414 mm.
- Adapter input: `C:/x/t_d94665f2/paving_ground_inputs_v2.json`.
  SHA-256: `231e4044774c520a4deb721a1c92f6f2db14eb15c431c5c20765200af34fba35`.
- Existing master: `C:/x/t_d94665f2/ground_v002/ground_master_vpm.json`.
  SHA-256: `47979bd4378a4008e77f15cb260b312050f374356abe39d273dc297f95b686ee`.

## Concrete spacing witness

Original face 1858 (zero-based), TileLight, level 0:

```text
x           y               z
-7604.0     -15377.261114    145.531697
-7608.0     -15380.0         145.514635
-7604.0     -15380.0         145.180522
```

A 0.99 m horizontal cross-section from
`(-7606.466664896665, -15379.087038)` to
`(-7605.476664896665, -15379.087038)` lies strictly inside this face;
**101/101** equally spaced samples are inside. There are no existing face/grid edges
inside this section.

If distinct new cut edges must stay at least 1 m apart, at most one can cross this
section. The resulting height field has at most two linear pieces along it. For every
possible partition of the 101 samples, fit two independent least-squares lines, even
allowing a discontinuity between them. This relaxation can only reduce the error.
The minimum RMS error over all 100 partitions is **28.941750940966013 mm**. Maximum
absolute error is at least RMS, so even this more permissive approximation cannot keep
all measured samples within 10 mm. Exact TIN slope-break cuts therefore cannot simply
be added here while asserting that all new edges stay 1 m apart.

This is an independent cross-section probe of relief fidelity, not a claim that final
face-centre tests or the requested mesh build were run. Moving test sample locations
to hide the unresolved relief between them is not a fix.

## Reproduce the witness (read-only)

Run from this worktree with `uv run python` and the following code. It uses the existing
typed adapter result, not another DXF parser. Output is `101 101` and the RMS above.

```python
import json
from pathlib import Path
import numpy as np
from shapely.geometry import Point, Polygon
from dt_ai.geometry import ground_cake as gc

root = Path('C:/x/t_d94665f2')
d = json.loads((root / 'paving_ground_inputs_v2.json').read_text(encoding='utf-8'))
m = json.loads((root / 'ground_v002/ground_master_vpm.json').read_text())
s = gc.ReliefSampler(gc.build_tin([(e['x'], e['y'], e['z']) for e in d['elevations']]))
x = np.linspace(-7606.466664896665, -7605.476664896665, 101)
xy = np.column_stack([x, np.full(101, -15379.087038)])
z, hit = s.sample(xy)
assert hit.all()
p = Polygon(np.array(m['verts'])[m['faces'][1858], :2])
print(sum(p.contains(Point(*q)) for q in xy), len(xy))
A = np.column_stack([np.linspace(0, .99, 101), np.ones(101)])
best = float('inf')
for split in range(1, 101):
    ss = 0.
    for part in (slice(None, split), slice(split, None)):
        aa, zz = A[part], z[part]
        residual = zz - aa @ np.linalg.lstsq(aa, zz, rcond=None)[0]
        ss += float(residual @ residual)
    best = min(best, (ss / 101) ** .5)
print(best * 1000)
```

## Decision requested

May TIN slope-break edges be closer than 1 m **only inside cells requiring relief
correction**, keeping the regular grid 4 x 4 m and the relief error <= 10 mm?
Or must the 1 m rule also apply to TIN edges, requiring a different approved relief
approximation/tolerance? No smoothing, elevation removal or method switch is assumed.

## Remaining implementation

Selective relief cuts; curb geometry (+150/+50 mm) and stairs from VP; fixed-camera
back-face renders outside git; exported density correction/readback. UCX remains
`not checked: #166 open`. Blender 5.1.2 is available (confirmed this run); previous
v002 evidence used Blender 4.4 and is not substituted for a 5.1.2 verification.
