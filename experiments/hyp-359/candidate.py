"""Experiment-only projection selector; unchanged production edge tests compiled below."""
import inspect
from technical_library.mesh_audit import core

BASELINE = core._has_proper_crossing
START = '    best_cross = None\n'
END = '    if best_cross is None or best_mag2 <= 0.0:\n'
SELECTION = '''    best_cross = None
    best_mag2 = 0.0
    p0 = poly[0]
    p1 = p0
    farthest = 0.0
    for p in poly:
        dx, dy, dz = p[0]-p0[0], p[1]-p0[1], p[2]-p0[2]
        distance = dx*dx + dy*dy + dz*dz
        if distance > farthest:
            farthest = distance
            p1 = p
    v1 = (p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2])
    for p2 in poly:
        v2 = (p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2])
        cx = v1[1]*v2[2] - v1[2]*v2[1]
        cy = v1[2]*v2[0] - v1[0]*v2[2]
        cz = v1[0]*v2[1] - v1[1]*v2[0]
        mag2 = cx*cx + cy*cy + cz*cz
        if mag2 > best_mag2:
            best_mag2 = mag2
            best_cross = (cx, cy, cz)
'''
source = inspect.getsource(BASELINE)
assert source.count(START) == source.count(END) == 1
prefix, tail = source.split(START)
_, suffix = tail.split(END)
namespace = dict(BASELINE.__globals__)
exec(compile(prefix + SELECTION + END + suffix, '<hyp-359-projection-only>', 'exec'), namespace)
CANDIDATE = namespace['_has_proper_crossing']
# Byte-for-byte equality outside normal selection, including all edge thresholds.
assert inspect.getsource(BASELINE) == source
assert '1e-10' in suffix and 'return True' in suffix


def install(mode):
    if mode not in ('A', 'B'):
        raise ValueError(f'Unknown implementation: {mode}')
    core._has_proper_crossing = {'A': BASELINE, 'B': CANDIDATE}[mode]
    return core.inspect_mesh
