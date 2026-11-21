"""new-case: #1729 3ds Max side of fbxmaps_core (thin pymxs glue): the maps connected in the scene after an FBX
import, the scene materials with their slots, and applying a fbxmaps_core.reconnect_plan.

A reconnect never overwrites a held slot (the plan refuses it) and never invents a file: a planned map whose file is
not in `folder` (the `<fbx>.fbm` folder Max extracts embedded media to) is a failure. No undo / no save here: the
caller owns the scene (batch probe tools/max/metallic_channel_probe_max.py loads this file from the repo). Not in the
MZP file list yet (tools/max/build_agr_tools.py + install.ms count): the panel row and shipping are a follow-up.
"""
import os


def _walk_tex(rt, tm, top, slot, rows, depth=0):
    if tm is None or depth > 16:
        return
    if rt.classOf(tm) == rt.Bitmaptexture:
        rows.append({'material': top, 'slot': slot, 'file': str(tm.fileName or '')})
    for i in range(1, int(rt.getNumSubTexmaps(tm)) + 1):
        _walk_tex(rt, rt.getSubTexmap(tm, i), top, slot + '/' + str(rt.getSubTexmapSlotName(tm, i)), rows, depth + 1)


def _materials(rt):
    seen, out = set(), []

    def add(m):
        if m is None or int(rt.getHandleByAnim(m)) in seen:
            return
        seen.add(int(rt.getHandleByAnim(m)))
        out.append(m)
        for i in range(1, int(rt.getNumSubMtls(m)) + 1):
            add(rt.getSubMtl(m, i))
    for m in rt.sceneMaterials:
        add(m)
    return out


def connected_maps(rt):
    """[{'material', 'material_class', 'slot', 'file'}] of every Bitmaptexture under every scene material."""
    rows = []
    for m in _materials(rt):
        for i in range(1, int(rt.getNumSubTexmaps(m)) + 1):
            part = []
            _walk_tex(rt, rt.getSubTexmap(m, i), str(m.name), str(rt.getSubTexmapSlotName(m, i)), part)
            for r in part:
                r['material_class'] = str(rt.classOf(m))
            rows.extend(part)
    return rows


def scene_materials(rt, slots_of):
    """{name: {'class', 'slots': {slot: file|None}}}; slots_of: {class name: [slot property]} (RECONNECT_SLOT)."""
    out = {}
    for m in _materials(rt):
        cls = str(rt.classOf(m))
        slots = {}
        for prop in slots_of.get(cls, ()):
            tm = getattr(m, prop, None)
            slots[prop] = str(tm.fileName) if tm is not None and rt.classOf(tm) == rt.Bitmaptexture else (
                None if tm is None else '<{}>'.format(rt.classOf(tm)))
        out.setdefault(str(m.name), {'class': cls, 'slots': slots})
    return out


def apply_reconnect(rt, plan, folder):
    """Connect plan['connect'] rows; -> {'connected': [...], 'failures': [...]} (plan failures carried over)."""
    by_name = {}
    for m in _materials(rt):
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
