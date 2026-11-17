"""new-case: read-only pymxs glue for the AGR Tools 0.7.0 checks (suite_core.py holds the logic, #860).

Builds the plain row dicts of suite_core's contract. Geometry comes from snapshotAsMesh copies in memory
(deleted after reading); maps from usedMaps plus Bitmaptexture file names (usedMaps drops a missing file);
nothing is converted, reset, collapsed or saved (GeoAGR D6).
0.9 (#979, E3): scene.census / qa.preflight also take missing maps from the shared bitmap enumerator of tex_max
(`_scene_maps`, owner E1, read only), map sizes from file headers (suite_core.image_size), the base object handle
(instance groups) and the renderer.
"""
import os

_FILE_PROPS = ('filename', 'fileName', 'HDRIMapName', 'bitmapFileName', 'Filename')


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


def _node_label(node):
    """(name, error). A blank or unreadable name is an error; the caller chooses the message."""
    try:
        text = str(node.name).strip()
    except Exception as exc:  # noqa: BLE001 - the caller fails closed with this cause
        return repr(node), exc
    if not text:
        return repr(node), ValueError('blank name')
    return text, None


def _map_fail(material_node, label, exc):
    if material_node:
        raise ValueError('unmapped material {}: {}'.format(label, exc)) from exc
    raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc


def _used_paths(rt, mat, label):
    """Filenames from usedMaps. undefined is no maps (D3); a broken entry is an error, never a pass."""
    try:
        maps = rt.usedMaps(mat)
    except Exception as exc:  # noqa: BLE001
        raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc
    if maps is None or maps == rt.undefined:
        return []
    try:
        count = int(maps.count)
    except Exception as exc:  # noqa: BLE001
        raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc
    out = []
    for i in range(count):
        try:
            item = maps[i]
        except Exception as exc:  # noqa: BLE001
            raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc
        if item is None or item == rt.undefined:
            raise ValueError('unreadable map entry on {}: {!r}'.format(label, item))
        try:
            text = str(item).strip()
        except Exception as exc:  # noqa: BLE001
            raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc
        if not text:
            raise ValueError('unreadable map entry on {}: {!r}'.format(label, item))
        if text not in out:
            out.append(text)
    return out


def _bitmap_file(rt, node, label):
    """Bitmaptexture file name, including a path whose file is not on disk."""
    for prop in _FILE_PROPS:
        try:
            if not rt.isProperty(node, prop):
                continue
            value = rt.getProperty(node, prop)
        except Exception as exc:  # noqa: BLE001
            raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc
        if value is None or value == rt.undefined:
            continue
        try:
            text = str(value).strip()
        except Exception as exc:  # noqa: BLE001
            raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc
        if text:
            return text
    raise ValueError('unreadable map entry on {}: Bitmaptexture has no file name'.format(label))


def _bitmap_paths(rt, mat):
    """File names of Bitmaptexture nodes in this material's texmap tree, each once.

    Sub-materials are not walked: glue._materials yields them on their own. usedMaps omits a
    Bitmaptexture whose file does not exist (#886); the file name is still returned.
    """
    out, seen = [], set()
    stack = [(mat, True)]
    while stack:
        node, material_node = stack.pop()
        if node is None or node == rt.undefined:
            continue
        label, name_exc = _node_label(node)
        if name_exc is not None:
            _map_fail(material_node, label, name_exc)
        try:
            key = int(rt.getHandleByAnim(node))
            cls = rt.classOf(node)
        except Exception as exc:  # noqa: BLE001
            _map_fail(material_node, label, exc)
        if key in seen:
            continue
        seen.add(key)
        if cls == rt.Bitmaptexture:
            path = _bitmap_file(rt, node, label)
            if path not in out:
                out.append(path)
        try:
            count = int(rt.getNumSubTexmaps(node))
        except Exception as exc:  # noqa: BLE001
            _map_fail(material_node, label, exc)
        children = []
        for i in range(count):
            try:
                children.append(rt.getSubTexmap(node, i + 1))
            except Exception as exc:  # noqa: BLE001
                raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc
        for child in reversed(children):  # first slot is read first
            stack.append((child, False))
    return out


def _file_missing(glue, path, label):
    try:
        resolved = glue._resolve(path)
    except Exception as exc:  # noqa: BLE001
        raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc
    try:
        return not (resolved and os.path.isfile(resolved))
    except Exception as exc:  # noqa: BLE001
        raise ValueError('unreadable map entry on {}: {}'.format(label, exc)) from exc


def _materials(n, glue, sizer=None):
    """Every material of the node (Multi/Sub and its subs), each with class, maps, missing maps, opacity.

    Map paths are usedMaps unioned with Bitmaptexture file names, so a file Max will not list is still
    `missing`. A material that cannot be read raises, naming it.
    """
    rt = _rt()
    mat = n.material
    if mat is None or mat == rt.undefined:
        return []
    found = list(glue._materials(mat))
    if not found:
        label, name_exc = _node_label(mat)
        if name_exc is not None:
            raise ValueError('unmapped material {}'.format(label)) from name_exc
        raise ValueError('unmapped material {}'.format(label))
    out = []
    for m in found:
        label, name_exc = _node_label(m)
        if name_exc is not None:
            raise ValueError('unmapped material {}'.format(label)) from name_exc
        paths = _used_paths(rt, m, label)
        if rt.classOf(m) == rt.Multimaterial:
            paths = []  # the subs carry their own maps; usedMaps on the multi repeats them
        for path in _bitmap_paths(rt, m):
            if path not in paths:
                paths.append(path)
        missing = [p for p in paths if _file_missing(glue, p, label)]
        sizes = {p: _map_size(glue, p, sizer) for p in paths if p not in missing} if sizer else {}
        opacity = None
        try:
            if rt.classOf(m) == rt.Standardmaterial:
                opacity = float(m.opacity) / 100.0
            elif rt.classOf(m) == rt.PhysicalMaterial:
                opacity = 1.0 - float(m.transparency)
        except Exception:  # noqa: BLE001 - unreadable opacity stays None (judged fail-closed by the core)
            opacity = None
        out.append({'name': label, 'cls': str(rt.classOf(m)), 'maps': paths, 'missing': missing,
                    'opacity': opacity, 'sizes': {p: s for p, s in sizes.items() if s is not None}})
    return out


def _map_size(glue, path, sizer):
    """[w, h] from the file header (scene.census large maps, suite_core.image_size); None when unreadable.
    Only the first 64 KiB are read: the bitmap is never loaded (Optimise_info loaded every 8K map, T04)."""
    try:
        with open(glue._resolve(path), 'rb') as fh:
            head = fh.read(65536)
    except (OSError, TypeError, ValueError):
        return None
    size = sizer(head)
    return list(size) if size else None


def _shared_maps(agr, nodes):
    """Missing map files from the shared bitmap enumerator of tex_max (`_scene_maps(core, nodes)`: materials of the
    nodes, scene materials, AssetManager; owner E1, read only here). Returns ({node handle: [paths]}, [paths with
    no owner node]). usedMaps drops a Bitmaptexture whose file is missing (#886, polygon known bug
    census-usedmaps-drops-missing-file); this reader does not."""
    tex = agr._load_core('tex_max.py', 'agr_tools_tex_max_census')
    core = agr._load_core('tex_core.py', 'agr_tools_tex_core_census')
    records, _notes = tex._scene_maps(core, nodes)
    by_node, scene = {}, []
    for rec in records:
        path = rec.get('path')
        if not path or tex._exists(path):
            continue
        owners = [o for o in rec.get('owners') or [] if o.get('handle') is not None]
        if not owners and path not in scene:
            scene.append(path)
        for o in owners:
            lst = by_node.setdefault(int(o['handle']), [])
            if path not in lst:
                lst.append(path)
    return by_node, sorted(scene)


def _renderer():
    rt = _rt()
    try:
        return str(rt.classOf(rt.renderers.current))
    except Exception:  # noqa: BLE001 - reported as unknown, the census is read-only
        return None


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


def _row(agr, glue, n, scale, sizer=None):
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
        'materials': _materials(n, glue, sizer) if sc == 'geometry' else [],
        'parent': str(n.parent.name) if n.parent is not None and n.parent != rt.undefined else None,
        'children': int(n.children.count), 'group': group, 'animated': animated,
        'modifiers': [str(md.name) for md in n.modifiers], 'layer': str(n.layer.name),
        'scale': (float(s.x), float(s.y), float(s.z)), 'rotation': (float(q.x), float(q.y), float(q.z), float(q.w)),
        'mirror': det < 0,
        'bbox': ((float(bb[0].x) * scale, float(bb[0].y) * scale, float(bb[0].z) * scale),
                 (float(bb[1].x) * scale, float(bb[1].y) * scale, float(bb[1].z) * scale)),
        'instances': count, 'base_key': int(rt.getHandleByAnim(n.baseObject)), 'zero_m': zero, 'roof_set': agr._prop(n, 'AGR_ROOF_SET') in ('1', 1, True),
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


def run(agr, glue, core, tool, nodes=None, select=True, ucx_export=None):
    if ucx_export is not None and select:
        raise ValueError('UCX export preview requires select=False')
    rt = _rt()
    if tool == 'units':
        scene = scene_units()
        return core.scene_report('units', scene['path'], core.units(scene))
    nodes = targets(agr, nodes)
    scale = agr._unit_m()
    sizer = core.image_size if tool in ('census', 'preflight') else None
    rows = [_row(agr, glue, n, scale, sizer) for n in nodes]
    audit = None
    scene = scene_units() if tool == 'preflight' else None  # qa.preflight includes scene.units (#882)
    if tool in ('census', 'preflight'):  # missing maps from the shared enumerator too (#979, #886)
        by_node, scene_missing = _shared_maps(agr, nodes)
        for row in rows:
            row['extra_missing'] = by_node.get(row['key'], [])
        if tool == 'census':
            scene = {'renderer': _renderer(), 'scene_missing': scene_missing}
    if tool in ('ucx_audit', 'preflight'):
        try:
            audit = agr._load_core('ucx_audit_core.py', 'agr_ucx_audit_core')  # shipped slice (MZP)
        except ValueError:  # source checkout: the slice is generated at build time
            from twinqa.geometry import ucx_audit as audit
    ucx_rows = None
    if ucx_export is not None:
        if tool not in ('ucx_audit', 'preflight') or 'error' in ucx_export:
            raise ValueError('invalid UCX export preview selection')
        ucx_rows = [_row(agr, glue, n, scale, sizer) for n in ucx_export['nodes']]
        names = ucx_export['names']
        if set(names) - {r['key'] for r in ucx_rows}:
            raise ValueError('UCX export names refer to missing nodes: {!r}'.format(
                sorted(set(names) - {r['key'] for r in ucx_rows})))
        for row in ucx_rows:
            row['name'] = names.get(row['key'], row['name'])
        if tool == 'ucx_audit':
            rows = ucx_rows
    kw = {'ucx_rows': ucx_rows} if ucx_rows is not None else {}
    found, dropped, summary = core.run(tool, rows, audit, scene=scene, **kw)
    if tool == 'preflight' and ucx_rows is not None:
        # Keep source checks on their original objects; attribute export-UCX findings to the actual copies.
        rows = rows + [r for r in ucx_rows if r['key'] not in {x['key'] for x in rows}]
    report = core.report(tool, rows, found, dropped, summary)
    if select:
        rt.select([n for n, o in zip(nodes, report['objects']) if o['findings']])
    return report
