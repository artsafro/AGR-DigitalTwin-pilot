"""new-case: #1729 3ds Max side of fbxmaps_core (thin pymxs glue): the maps connected in the scene after an FBX
import, the scene materials with their slots, and applying a fbxmaps_core.reconnect_plan.

A reconnect never overwrites a held slot (the plan refuses it) and never invents a file: a planned map whose file is
not in `folder` (the `<fbx>.fbm` folder Max extracts embedded media to) is a failure. The low-level helpers
also serve the repo batch probe; the installed panel checks the selected import and owns the undo scope.
"""
import os
from collections import Counter


def _walk_tex(rt, tm, top, slot, rows, depth=0):
    if tm is None or depth > 16:
        return
    if rt.classOf(tm) == rt.Bitmaptexture:
        rows.append({'material': top, 'slot': slot, 'file': str(tm.fileName or '')})
    for i in range(1, int(rt.getNumSubTexmaps(tm)) + 1):
        _walk_tex(rt, rt.getSubTexmap(tm, i), top, slot + '/' + str(rt.getSubTexmapSlotName(tm, i)), rows, depth + 1)


def _materials(rt, roots=None):
    seen, out = set(), []

    def add(m):
        if m is None or int(rt.getHandleByAnim(m)) in seen:
            return
        seen.add(int(rt.getHandleByAnim(m)))
        out.append(m)
        for i in range(1, int(rt.getNumSubMtls(m)) + 1):
            add(rt.getSubMtl(m, i))
    for m in rt.sceneMaterials if roots is None else roots:
        add(m)
    return out


def connected_maps(rt, materials=None):
    """[{'material', 'material_class', 'slot', 'file'}] of every Bitmaptexture under every scene material."""
    rows = []
    for m in _materials(rt) if materials is None else materials:
        for i in range(1, int(rt.getNumSubTexmaps(m)) + 1):
            part = []
            _walk_tex(rt, rt.getSubTexmap(m, i), str(m.name), str(rt.getSubTexmapSlotName(m, i)), part)
            for r in part:
                r['material_class'] = str(rt.classOf(m))
            rows.extend(part)
    return rows


def scene_materials(rt, slots_of, materials=None):
    """{name: {'class', 'slots': {slot: file|None}}}; slots_of: {class name: [slot property]} (RECONNECT_SLOT)."""
    out = {}
    for m in _materials(rt) if materials is None else materials:
        cls = str(rt.classOf(m))
        slots = {}
        props = slots_of.get(cls, ())
        for prop in props.values() if isinstance(props, dict) else props:
            tm = getattr(m, prop, None)
            slots[prop] = str(tm.fileName) if tm is not None and rt.classOf(tm) == rt.Bitmaptexture else (
                None if tm is None else '<{}>'.format(rt.classOf(tm)))
        out.setdefault(str(m.name), {'class': cls, 'slots': slots})
    return out


def apply_reconnect(rt, plan, folder, materials=None):
    """Connect plan['connect'] rows; -> {'connected': [...], 'failures': [...]} (plan failures carried over)."""
    by_name = {}
    for m in _materials(rt) if materials is None else materials:
        by_name.setdefault(str(m.name), m)
    done, failures = [], list(plan['failures'])
    for row in plan['connect']:
        path = os.path.join(folder, row['file'])
        mat = by_name.get(row['material'])
        if not os.path.isfile(path):
            failures.append({'file': row['file'], 'reason': 'not extracted to ' + folder})
            continue
        if mat is None or not rt.isProperty(mat, rt.Name(row['slot'])):
            failures.append({'file': row['file'], 'reason': '{}.{} not found'.format(row['material'], row['slot'])})
            continue
        setattr(mat, row['slot'], rt.Bitmaptexture(fileName=path))
        done.append(dict(row, path=path))
    return {'connected': done, 'failures': failures}


def check_selection(rt, core, path, confirm, undo):
    """Read selected import, offer a plan, then recheck before and after applying it."""
    def snapshot():
        nodes = list(rt.selection)
        if not nodes:
            raise ValueError('Select the objects from the FBX import first')
        materials = _materials(rt, (n.material for n in nodes))
        duplicates = sorted(name for name, count in Counter(str(m.name) for m in materials).items() if count > 1)
        if duplicates:
            raise ValueError('Duplicate material names: ' + ', '.join(duplicates))
        doc = core.read_fbx(path)
        connected = connected_maps(rt, materials)
        slots = scene_materials(rt, core.RECONNECT_SLOT, materials)
        identity = (sorted(int(rt.getHandleByAnim(n)) for n in nodes),
                    sorted(int(rt.getHandleByAnim(m)) for m in materials))
        return materials, (doc, connected, slots, identity)

    _, state = snapshot()
    doc, connected, slots, _ = state
    before = core.import_readback(doc, connected)
    result = {'before': before, 'after': None, 'failures': []}
    if before['status'] != 'fail' or before['conflicts']:
        return result

    plan = core.reconnect_plan(before['unconnected'], slots)
    result['failures'] = plan['failures']
    targets = Counter((r['material'], r['slot']) for r in plan['connect'])
    if any(count > 1 for count in targets.values()):
        for r in plan['connect']:
            if targets[r['material'], r['slot']] > 1:
                plan['failures'].append({'file': r['file'], 'reason': 'multiple maps target {material}.{slot}'.format(**r)})
        return result
    if not plan['connect'] or not confirm(before, plan):
        return result

    materials, current = snapshot()
    if current != state:
        raise ValueError('FBX or selection/materials changed; run the check again')
    folder = os.path.splitext(path)[0] + '.fbm'
    applied = None
    with undo(True, 'AGR Tools: reconnect FBX maps'):
        applied = apply_reconnect(rt, plan, folder, materials)
    if applied is None:
        raise RuntimeError('FBX reconnect did not complete')
    result['failures'] = applied['failures']
    result['after'] = core.import_readback(doc, connected_maps(rt, materials))
    return result
