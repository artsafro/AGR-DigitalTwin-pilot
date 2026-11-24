"""Runtime-only UV registration probe for the pinned AC08 export."""
import json
import math
from pathlib import Path
from struct import pack, unpack


def panel_cell(points, cells):
    owner = None
    for name, (u, v, side) in cells.items():
        hits = [u <= x <= u + side and v <= y <= v + side for x, y in points]
        if any(hits):
            if not all(hits) or owner is not None:
                raise ValueError(f'partial or ambiguous panel assignment: {name} {points}')
            owner = name
    return owner


def scene_state(obj):
    mesh = obj.data
    return (tuple(tuple(row) for row in obj.matrix_world), tuple(tuple(v.co) for v in mesh.vertices),
            tuple((tuple(p.vertices), p.material_index) for p in mesh.polygons),
            tuple(m.name for m in mesh.materials),
            tuple((l.name, tuple(tuple(e.vector) for e in l.uv)) for l in mesh.uv_layers if l != mesh.uv_layers.active))


def mutate(meshes, layout_path, shift_px, receipt_path):
    layout = json.loads(Path(layout_path).read_bytes())
    size, pad = layout['atlas'], layout['pad']
    if size != 2048 or pad != 6 or shift_px not in (0.5, 5.0):
        raise ValueError('unfrozen variant or atlas dimensions')
    cells = {n: tuple(r[k] for k in ('u0', 'v0', 'size')) for n, r in layout['finishes'].items()
             if n.startswith('PanelVJ')}
    counts = {n: 0 for n in cells}
    outside = {n: 0 for n in cells}
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
                if not math.isfinite(u + v):
                    raise ValueError('nonfinite UV')
                expected = unpack('f', pack('f', u + shift_px / size))[0]
                if not u < expected <= u0 + side + pad / size:
                    raise ValueError('shift leaves the padded atlas cell')
                outside[cell] += expected > u0 + side
                target[i] = (expected, v)
                counts[cell] += 1
        for i, target_uv in target.items():
            uv[i].vector = target_uv
        if stable != scene_state(obj) or any(tuple(e.vector) != target.get(i, original[i]) for i, e in enumerate(uv)):
            raise ValueError('runtime readback mismatch')
    if not counts or not all(counts.values()):
        raise ValueError(f'not_exercised: {counts}')
    Path(receipt_path).write_text(json.dumps(dict(shift_px=shift_px, changed_loops=counts,
                                                loops_in_extrusion=outside)), encoding='utf-8')
