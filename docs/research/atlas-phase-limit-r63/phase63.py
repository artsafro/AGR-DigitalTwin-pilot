"""#63: signed runtime UV shift of PanelVJ cells and the frozen detection-limit verdict."""
import json
import math
from pathlib import Path
from struct import pack, unpack

from phase import panel_cell, scene_state  # #62 phase.py staged unchanged from 75257229

GRID = (-5.0, -2.0, -1.0, -0.5, 0.5, 1.0, 2.0, 5.0)
MAGNITUDES = (0.5, 1.0, 2.0, 5.0)


def shifted(u, u0, side, pad, size, shift_px):
    """float32 U after a signed shift; refuse leaving the padded cell [u0-pad, u0+side+pad]."""
    if not math.isfinite(u):
        raise ValueError('nonfinite UV')
    new = unpack('f', pack('f', u + shift_px / size))[0]
    if not (new > u if shift_px > 0 else new < u):
        raise ValueError('shift lost to float precision')
    if not u0 - pad / size <= new <= u0 + side + pad / size:
        raise ValueError('shift leaves the padded atlas cell')
    return new


def mutate(meshes, layout_path, shift_px, receipt_path):
    layout = json.loads(Path(layout_path).read_bytes())
    size, pad = layout['atlas'], layout['pad']
    if size != 2048 or pad != 6 or shift_px not in GRID:
        raise ValueError('unfrozen variant or atlas dimensions')
    cells = {n: tuple(r[k] for k in ('u0', 'v0', 'size')) for n, r in layout['finishes'].items()
             if n.startswith('PanelVJ')}
    counts = {n: 0 for n in cells}
    in_pad = {n: 0 for n in cells}
    for obj in meshes:
        if obj.name.startswith('UCX_'):
            continue
        mesh = obj.data
        stable = scene_state(obj)
        uv = mesh.uv_layers.active.uv
        original = [tuple(e.vector) for e in uv]
        target = {}
        for face in mesh.polygons:
            ids = list(face.loop_indices)
            cell = panel_cell([original[i] for i in ids], cells)
            if cell is None:
                continue
            u0, _, side = cells[cell]
            for i in ids:
                u, v = original[i]
                if not math.isfinite(v):
                    raise ValueError('nonfinite UV')
                new = shifted(u, u0, side, pad, size, shift_px)
                in_pad[cell] += not u0 <= new <= u0 + side
                target[i] = (new, v)
                counts[cell] += 1
        for i, target_uv in target.items():
            uv[i].vector = target_uv
        if stable != scene_state(obj) or any(tuple(e.vector) != target.get(i, original[i]) for i, e in enumerate(uv)):
            raise ValueError('runtime readback mismatch')
    if not counts or not all(counts.values()):
        raise ValueError(f'not_exercised: {counts}')
    Path(receipt_path).write_text(json.dumps(dict(shift_px=shift_px, changed_loops=counts,
                                                loops_in_pad=in_pad)), encoding='utf-8')


def limit(je):
    """L63 from {shift_px: JE on v010}: smallest m with both signs detected at m and every larger magnitude."""
    best = math.inf
    for m in reversed(MAGNITUDES):
        if je[m] > 0 and je[-m] > 0:
            best = m
        else:
            break
    return best


def verdict(je, clean_v007, clean_v010):
    """Frozen H63 verdict for one valid round; label order failure is inconclusive."""
    if not clean_v007 > clean_v010 == 0:
        return 'inconclusive'
    symmetric = all((je[m] > 0) == (je[-m] > 0) for m in MAGNITUDES)
    quiet = je[0.5] == 0 and je[-0.5] == 0
    return 'confirmed' if limit(je) <= 2 and symmetric and quiet else 'refuted'
