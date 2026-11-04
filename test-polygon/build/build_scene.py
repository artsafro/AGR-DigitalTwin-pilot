"""new-case: build the synthetic AGR Tools polygon inside 3ds Max (pymxs).

Run from build/build_polygon.ms or from test-polygon/build/run_inside_max.py.
The .max file is an output (saveAsVersion 2024). Sources stay in test-polygon/.

Ground rectangles are named `_base_*` on layer `_bases`. Captions are named `_label_*`
on layer `_labels` (hide that layer to hide the text). One top orthographic camera per
base, `_cam_База 0.x`, sits on layer `_cameras` (viewport label -> Cameras). All three are
omitted from checks and from export: the runner drops those name prefixes, and buttons
select named specimens only.
"""
import json
import math
import sys
from pathlib import Path

POLY = Path(__file__).resolve().parents[1]
if str(POLY) not in sys.path:
    sys.path.insert(0, str(POLY))

import polygon_core as core


def _rt():
    from pymxs import runtime
    return runtime


def _base_camera(obj):
    rt = _rt()
    target = rt.Targetobject(name=obj['name'] + '.Target')
    node = rt.Targetcamera(name=obj['name'], target=target)
    node.orthoProjection = True
    _layer(obj['layer']).addNode(target)
    return node


def _layer(name):
    rt = _rt()
    layer = rt.LayerManager.getLayerFromName(name)
    if layer is None:
        layer = rt.LayerManager.newLayerFromName(name)
    return layer


def _local_verts(obj, verts):
    """mesh_of bakes world position into vertices. The node transform applies it once."""
    px, py, pz = obj['pos']
    return [(x - px, y - py, z - pz) for x, y, z in verts]


def _bitmap_path(obj):
    if obj.get('mat') == 'missing' and obj.get('map_path'):
        return str(obj['map_path']).replace('\\', '/')
    tex_key = obj.get('tex')
    if tex_key and tex_key in core.TEXTURES:
        filename, _data = core.TEXTURES[tex_key]
        return str(Path(obj.get('texture_dir') or '') / filename).replace('\\', '/')
    return None


def _mesh(name, verts, tris):
    rt = _rt()
    vertices = rt.Array(*[rt.Point3(*v) for v in verts])
    faces = rt.Array(*[rt.Point3(a + 1, b + 1, c + 1) for a, b, c in tris])
    node = rt.mesh(name=name, vertices=vertices, faces=faces)
    return node


def _empty_poly(name):
    """Editable_Poly has no constructor in Max 2024 or 2026 (Not creatable).

    A box converted to poly, then stripped, is an Editable_Poly with 0 faces.
    """
    rt = _rt()
    node = rt.box(name=name, width=1, length=1, height=1)
    rt.convertToPoly(node)
    safe = str(name).replace('\\', '').replace('"', '')
    rt.execute(
        'polyop.deleteFaces (getNodeByName "{0}") '
        '#{{1..(polyop.getNumFaces (getNodeByName "{0}"))}} delIsoVerts:true'.format(safe))
    return node


def _set_uv(node, uvs, face_uvs):
    rt = _rt()
    rt.setNumTVerts(node, len(uvs))
    for i, (u, v) in enumerate(uvs):
        rt.setTVert(node, i + 1, rt.Point3(float(u), float(v), 0.0))
    rt.buildTVFaces(node)
    for i, face in enumerate(face_uvs):
        rt.setTVFace(node, i + 1, rt.Point3(*(index + 1 for index in face)))
    rt.update(node)


def _material(obj):
    rt = _rt()
    mode = obj.get('mat') or 'std'
    if mode == 'none':
        return None
    if mode == 'many':
        multi = rt.multimaterial(numsubs=41)
        multi.name = 'M_Polygon_013_Many'
        for i in range(41):
            sub = rt.Standardmaterial()
            sub.name = 'M_{}{}_001_Main_1'.format(chr(ord('A') + i // 26), chr(ord('A') + i % 26))
            multi.materialList[i] = sub
        return multi
    if mode == 'ray':
        mat = rt.RaytraceMaterial()
    else:
        mat = rt.Standardmaterial()
    mat.name = obj.get('mat_name') or 'M_Polygon_001_Main_1'
    mat.diffuse = rt.Color(180, 160, 140)
    if mode == 'glass':
        mat.opacity = float(obj.get('opacity') or 0.5) * 100.0
    if mode == 'missing' and obj.get('map_path'):
        tex = rt.Bitmaptexture()
        tex.filename = obj['map_path']
        mat.diffuseMap = tex
    tex_key = obj.get('tex')
    if tex_key and tex_key in core.TEXTURES:
        filename, _data = core.TEXTURES[tex_key]
        tex = rt.Bitmaptexture()
        tex.filename = str(Path(obj.get('texture_dir') or '') / filename)
        mat.diffuseMap = tex
    return mat


def _props(node, obj):
    rt = _rt()
    lines = ['AGR_TEST=' + obj['AGR_TEST']]
    if obj.get('fbx'):
        lines.append('AGR_EXPORT_PATH=' + core.fbx_path(obj['fbx']))
    if obj.get('superclass') == 'geometry':
        lines.append('AGR_ZERO_M=' + str(obj.get('zero', 0.0)))
    if obj.get('superclass') == 'geometry' and obj.get('mesh') != 'empty':
        # Channel Info stores the channel name in the user buffer. Unnamed channel 1
        # is a cleanup finding; the polygon's cleanup specimens are already named UV.
        lines.append('MapChannel:1 = UV')
    mat = obj.get('mat_name')
    if obj.get('uv_periods') and mat:
        lines.append('AGR_UV_PERIODS={}={}'.format(mat, obj['uv_periods']))
    if obj.get('atlas'):
        lines.append('AGR_ATLAS_MODE=oks')
        lines.append('AGR_ATLAS_SIZE=1024')
    if obj.get('texel_px') and mat:
        lines.append('AGR_TEXEL_PROFILE=NPM')
        lines.append('AGR_TEXEL_MAP={}={}'.format(mat, obj['texel_px']))
    rt.setUserPropBuffer(node, '\r\n'.join(lines) + '\r\n')


def _make(obj):
    rt = _rt()
    kind = obj['superclass']
    if kind == 'camera' and obj.get('camera_span'):
        node = _base_camera(obj)
    elif kind == 'camera':
        node = rt.FreeCamera(name=obj['name'])
    elif kind == 'light':
        node = rt.Omnilight(name=obj['name'])
    elif kind == 'helper':
        node = rt.Dummy(name=obj['name'])
    elif kind == 'shape':
        node = rt.Text(name=obj['name'])
        # Max Text breaks lines on CR LF only; a bare LF is dropped.
        node.text = (obj.get('text') or obj['name']).replace('\r\n', '\n').replace('\n', '\r\n')
        node.size = obj.get('text_size') or (0.35 if str(obj['name']).startswith('_label_') else 1.5)
        node.wirecolor = rt.Color(20, 20, 20)
    else:
        verts, tris = core.mesh_of(obj)
        if obj['mesh'] == 'empty' or not tris:
            node = _empty_poly(obj['name'])
        else:
            node = _mesh(obj['name'], _local_verts(obj, verts), tris)
            if obj['mesh'] == 'quad' or obj.get('uv_shift') or obj.get('texel_px') or obj.get('atlas'):
                shift = float(obj.get('uv_shift') or 0.0)
                uvs = [(u + shift, v) for u, v in ((0, 0), (1, 0), (1, 1), (0, 1))]
                faces = [(0, 1, 2), (0, 2, 3)]
            else:
                # One inset island, same as the texture prediction, so a real map is measurable.
                uvs = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
                faces = [(0, 1, 2) if i % 2 == 0 else (0, 2, 3) for i in range(len(tris))]
            _set_uv(node, uvs, faces)
            # A fresh TriMesh only has map channels 0 and 1. Channel 2 is out of range until numMaps grows.
            if obj.get('extra_channel'):
                if int(rt.meshop.getNumMaps(node)) < 3:
                    rt.meshop.setNumMaps(node, 3)
                rt.meshop.setMapSupport(node, 2, True)
                rt.meshop.setNumMapVerts(node, 2, 1)
            # TriMesh is not an Editable_Poly. convertToPoly is the creatable path in Max 2024 and 2026.
            rt.convertToPoly(node)
        if obj.get('matid'):
            count = int(rt.polyop.getNumFaces(node))
            for face in range(1, count + 1):
                rt.polyop.setFaceMatID(node, face, int(obj['matid']))
    node.pos = rt.Point3(*obj['pos'])
    if obj.get('anchor') == 'top_left':
        # A Text shape is centred on its pivot; move it so its top-left corner is at pos.
        node.pos = rt.Point3(obj['pos'][0] + (node.pos.x - node.min.x),
                             obj['pos'][1] - (node.max.y - node.pos.y), obj['pos'][2])
    if kind == 'camera' and obj.get('camera_span'):
        span_x, span_y = obj['camera_span']
        # Ortho width = 2 * distance * tan(fov / 2); fit the larger of width and 16:9 height.
        fit = max(span_x, span_y * 16.0 / 9.0) * 1.08
        height = fit * 2.0 + 20.0
        node.pos = rt.Point3(obj['pos'][0], obj['pos'][1] - 0.001, height)
        node.target.pos = rt.Point3(obj['pos'][0], obj['pos'][1], 0.0)
        node.fov = math.degrees(2.0 * math.atan((fit / 2.0) / height))
    if obj.get('scale') and obj['scale'] != [1.0, 1.0, 1.0]:
        node.scale = rt.Point3(*obj['scale'])
    mat = _material(obj)
    # One diffuse colour per base, readable in the top view. Captions stay on `_labels`.
    if obj.get('colour'):
        mat = rt.Standardmaterial()
        mat.name = obj['name'] + '_colour'
        mat.diffuse = rt.Color(*obj['colour'])
        mat.showInViewport = True
        node.wirecolor = mat.diffuse
    if mat is not None and kind == 'geometry':
        node.material = mat
    if obj.get('modifiers'):
        rt.addModifier(node, rt.Bend())
    if obj.get('pivot') is not None:
        node.pivot = rt.Point3(*obj['pivot'])
    bitmap = _bitmap_path(obj)
    if bitmap and kind == 'geometry' and node.material is not None:
        # A Bitmaptexture whose file is missing is dropped by the pymxs property set.
        # MAXScript keeps the filename so census can report missing_map.
        safe_name = str(obj['name']).replace('"', '')
        safe_path = bitmap.replace('"', '')
        rt.execute(
            '(getNodeByName "{0}").material.diffuseMap = Bitmaptexture fileName:"{1}"'.format(
                safe_name, safe_path))
    if obj.get('animated'):
        safe_name = str(obj['name']).replace('"', '')
        rt.execute(
            'animate on ('
            'at time 0 (getNodeByName "{0}").pos = (getNodeByName "{0}").pos; '
            'at time 10 (getNodeByName "{0}").pos = (getNodeByName "{0}").pos + [0,0,0.2]'
            ')'.format(safe_name))
    _props(node, obj)
    _layer(obj['layer']).addNode(node)
    return node


def _units(scene):
    rt = _rt()
    if scene == 'cm_units':
        rt.units.SystemType = rt.Name('centimeters')
    else:
        rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1.0
    rt.fileInGamma = 1.0
    rt.fileOutGamma = 1.0


def build(scene, texture_dir=''):
    """Reset the session and build one variant. Returns the created nodes by name."""
    rt = _rt()
    rt.resetMaxFile(rt.Name('noPrompt'))
    _units(scene)
    catalog = json.loads((POLY / 'catalog.json').read_text(encoding='utf-8'))
    made = {}
    if scene == 'empty':
        return made
    if scene == 'cm_units':
        box = rt.Box(name='SM_Polygon_Cm_Main', width=2, length=2, height=2)
        box.pos = rt.Point3(0, 0, 0)
        units = next(item for item in core.stations() if item['button'] == 'scene.units')
        rt.setUserPropBuffer(box, 'AGR_TEST=station={};scene.units=fail\r\n'.format(units['id']))
        _layer('База ' + units['version']).addNode(box)
        made[box.name] = box
        return made
    for obj in catalog['objects']:
        if obj['scene'] != scene:
            continue
        obj = dict(obj, texture_dir=texture_dir)
        made[obj['name']] = _make(obj)
    for obj in catalog['objects']:
        if obj['scene'] == scene and obj.get('parent'):
            child = made.get(obj['name'])
            parent = made.get(obj['parent'])
            if child is not None and parent is not None:
                child.parent = parent
    _start_view(made)
    return made


def _start_view(made):
    """Open the scene looking at База 0.1 through its top camera (UI Max; batch has no viewport)."""
    rt = _rt()
    cams = sorted(name for name in made if str(name).startswith('_cam_'))
    if not cams:
        return
    try:
        rt.viewport.setLayout(rt.Name('layout_1'))
        rt.viewport.setCamera(made[cams[0]])
    except Exception:  # noqa: BLE001 - 3dsmaxbatch: no viewports to set
        pass


def save(path):
    """Write a 2024-format .max. The path must already be a new output, not a source."""
    target = str(Path(path).resolve()).replace('\\', '/')
    _rt().execute('saveMaxFile "{}" saveAsVersion:2024 quiet:true'.format(target))
