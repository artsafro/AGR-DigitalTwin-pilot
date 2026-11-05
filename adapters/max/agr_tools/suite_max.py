"""new-case: read-only pymxs glue for the AGR Tools 0.7.0 checks (suite_core.py holds the logic, #860).

Builds the plain row dicts of suite_core's contract. Geometry comes from snapshotAsMesh copies in memory
(deleted after reading); maps from usedMaps; nothing is converted, reset, collapsed or saved (GeoAGR D6).
"""
import os


def _rt():
    from pymxs import runtime
    return runtime


def _superclass(n):
    rt = _rt()
    sc = rt.superClassOf(n)
    for name, cls in (('geometry', rt.GeometryClass), ('shape', rt.shape), ('light', rt.light),
                      ('camera', rt.camera), ('helper', rt.helper)):
        if sc == cls:
            if name == 'geometry' and rt.classOf(n) in (rt.Biped_Object, rt.BoneGeometry):
                return 'bone'
            if name == 'geometry' and rt.classOf(n) == rt.Targetobject:
                return 'helper'
            return name
    return str(sc).lower()


def _materials(n, glue):
    """Every material of the node (Multi/Sub and its subs), each with class, maps, missing maps, opacity."""
    rt = _rt()
    out = []
    for m in glue._materials(n.material):
        maps = rt.usedMaps(m)
        paths = [str(maps[i]) for i in range(int(maps.count))] if maps is not None else []
        if rt.classOf(m) == rt.Multimaterial:
            paths = []  # the subs carry their own maps
        missing = [p for p in paths if not os.path.isfile(glue._resolve(p))]
        opacity = None
        try:
            if rt.classOf(m) == rt.Standardmaterial:
                opacity = float(m.opacity) / 100.0
            elif rt.classOf(m) == rt.PhysicalMaterial:
                opacity = 1.0 - float(m.transparency)
        except Exception:  # noqa: BLE001 - unreadable opacity stays None (judged fail-closed by the core)
            opacity = None
        out.append({'name': str(m.name), 'cls': str(rt.classOf(m)), 'maps': paths, 'missing': missing,
                    'opacity': opacity})
    return out


def _mesh_reader(n, scale):
    def read():
        rt = _rt()
        m = rt.snapshotAsMesh(n)
        try:
            verts = []
            for i in range(int(m.numverts)):
                p = rt.getVert(m, i + 1)
                verts.append((float(p.x) * scale, float(p.y) * scale, float(p.z) * scale))
            tris = []
            for i in range(int(m.numfaces)):
                f = rt.getFace(m, i + 1)
                tris.append((int(f.x) - 1, int(f.y) - 1, int(f.z) - 1))
            return {'verts': verts, 'tris': tris}
        finally:
            try:
                rt.delete(m)
            except Exception:  # noqa: BLE001
                pass
    return read


def _row(agr, glue, n, scale):
    rt = _rt()
    sc = _superclass(n)
    geo = sc == 'geometry' and bool(rt.canConvertTo(n, rt.TriMeshGeometry))
    faces = verts = 0
    if geo:
        m = rt.snapshotAsMesh(n)
        try:
            faces, verts = int(m.numfaces), int(m.numverts)
        finally:
            try:
                rt.delete(m)
            except Exception:  # noqa: BLE001
                pass
    tm = n.transform
    s = tm.scalepart
    q = tm.rotationpart
    det = float(rt.dot(rt.cross(tm.row1, tm.row2), tm.row3))
    bb = rt.nodeGetBoundingBox(n, rt.matrix3(1))
    zero = agr._prop(n, 'AGR_ZERO_M')
    try:
        zero = float(zero) if zero is not None else None
    except ValueError:
        zero = None
    count = int(rt.execute('fn agrToolsInstances n = (local a = #(); InstanceMgr.GetInstances n &a)')(n))
    group = bool(rt.isGroupHead(n) or rt.isGroupMember(n))
    animated = bool(n.isAnimated)
    return {
        'key': int(rt.getHandleByAnim(n)), 'name': str(n.name), 'fbx': agr._prop(n, 'AGR_EXPORT_PATH'),
        'superclass': sc, 'cls': str(rt.classOf(n)), 'faces': faces, 'verts': verts,
        'materials': _materials(n, glue) if sc == 'geometry' else [],
        'parent': str(n.parent.name) if n.parent is not None and n.parent != rt.undefined else None,
        'children': int(n.children.count), 'group': group, 'animated': animated,
        'modifiers': [str(md.name) for md in n.modifiers], 'layer': str(n.layer.name),
        'scale': (float(s.x), float(s.y), float(s.z)), 'rotation': (float(q.x), float(q.y), float(q.z), float(q.w)),
        'mirror': det < 0,
        'bbox': ((float(bb[0].x) * scale, float(bb[0].y) * scale, float(bb[0].z) * scale),
                 (float(bb[1].x) * scale, float(bb[1].y) * scale, float(bb[1].z) * scale)),
        'instances': count, 'zero_m': zero, 'roof_set': agr._prop(n, 'AGR_ROOF_SET') in ('1', 1, True),
        'mesh': _mesh_reader(n, scale) if geo else {'verts': [], 'tris': []},
    }


def targets(agr, nodes=None):
    """Selection, else every scene object (not only geometry: hygiene must see cameras and helpers)."""
    rt = _rt()
    if nodes is None:
        nodes = list(rt.selection) or list(rt.objects)
    nodes = list(nodes)
    if not nodes:
        raise ValueError('empty target set')
    handles = [int(rt.getHandleByAnim(n)) for n in nodes]
    if len(set(handles)) != len(handles):
        raise ValueError('duplicate target handle')
    return nodes


def scene_units():
    rt = _rt()
    path = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if str(rt.maxFileName) else '<untitled>'
    return {'unit_type': str(rt.units.SystemType), 'unit_scale': float(rt.units.SystemScale),
            'file_in_gamma': float(rt.fileInGamma), 'file_out_gamma': float(rt.fileOutGamma), 'path': path}


def run(agr, glue, core, tool, nodes=None, select=True):
    rt = _rt()
    if tool == 'units':
        scene = scene_units()
        return core.scene_report('units', scene['path'], core.units(scene))
    nodes = targets(agr, nodes)
    scale = agr._unit_m()
    rows = [_row(agr, glue, n, scale) for n in nodes]
    audit = None
    scene = scene_units() if tool == 'preflight' else None  # qa.preflight includes scene.units (#882)
    if tool in ('ucx_audit', 'preflight'):
        try:
            audit = agr._load_core('ucx_audit_core.py', 'agr_ucx_audit_core')  # shipped slice (MZP)
        except ValueError:  # source checkout: the slice is generated at build time
            from twinqa.geometry import ucx_audit as audit
    found, dropped, summary = core.run(tool, rows, audit, scene=scene)
    report = core.report(tool, rows, found, dropped, summary)
    if select:
        rt.select([n for n, o in zip(nodes, report['objects']) if o['findings']])
    return report
