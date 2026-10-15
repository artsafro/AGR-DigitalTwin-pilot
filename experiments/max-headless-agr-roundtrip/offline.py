"""Small binary-FBX 7.4 and OBJ geometry reader; no DCC, not a delivery validator.

FBX scope: geometry with identity object transforms, Z up, metre units. Reject other
coordinate contracts rather than silently treating local coordinates as world.
"""
import struct
import zlib
from pathlib import Path


def read_fbx(path):
    data = Path(path).read_bytes()
    if not data.startswith(b'Kaydara FBX Binary  \x00\x1a\x00'):
        raise ValueError('Binary FBX required')
    version = struct.unpack_from('<I', data, 23)[0]
    if version != 7400:
        raise ValueError('Only binary FBX 7400 supported')
    pos = 27

    def prop():
        nonlocal pos
        kind = chr(data[pos]); pos += 1
        formats = {'Y': 'h', 'C': '?', 'I': 'i', 'F': 'f', 'D': 'd', 'L': 'q'}
        if kind in formats:
            fmt = '<' + formats[kind]
            value = struct.unpack_from(fmt, data, pos)[0]
            pos += struct.calcsize(fmt)
            return value
        if kind in 'SR':
            size = struct.unpack_from('<I', data, pos)[0]; pos += 4
            value = data[pos:pos + size]; pos += size
            return value.decode('utf-8', errors='replace') if kind == 'S' else value
        if kind in 'fdlibc':
            size, encoding, length = struct.unpack_from('<III', data, pos); pos += 12
            raw = data[pos:pos + length]; pos += length
            if encoding == 1:
                raw = zlib.decompress(raw)
            elif encoding != 0:
                raise ValueError('Unsupported array encoding')
            fmt = {'f': 'f', 'd': 'd', 'l': 'q', 'i': 'i', 'b': 'B', 'c': 'B'}[kind]
            return list(struct.unpack('<' + str(size) + fmt, raw))
        raise ValueError('Unknown FBX property: ' + kind)

    def node():
        nonlocal pos
        end, count, length, n = struct.unpack_from('<IIIB', data, pos); pos += 13
        if end == 0:
            return None
        name = data[pos:pos+n].decode('ascii'); pos += n
        values = [prop() for _ in range(count)]
        children = []
        while pos < end:
            child = node()
            if child is None:
                break
            children.append(child)
        pos = end
        return {'name': name, 'values': values, 'children': children}

    roots = []
    while pos < len(data):
        item = node()
        if item is None:
            break
        roots.append(item)

    def named(nodes, name):
        return [n for n in nodes if n['name'] == name]

    settings = named(roots, 'GlobalSettings')[0]
    props = named(settings['children'], 'Properties70')[0]['children']
    settings = {p['values'][0]: p['values'][-1] for p in props}
    if settings['UpAxis'] != 2 or settings['UpAxisSign'] != 1 or settings['UnitScaleFactor'] != 100.0:
        raise ValueError('Expected Z-up metres, got ' + str(settings))
    objects = named(roots, 'Objects')[0]['children']
    connections = named(roots, 'Connections')[0]['children']
    geometry_ids = {n['values'][0] for n in named(objects, 'Geometry')}
    geometry_models = {c['values'][2] for c in connections
                       if c['name'] == 'C' and c['values'][1] in geometry_ids}
    parents = {c['values'][1]: c['values'][2] for c in connections
               if c['name'] == 'C' and c['values'][0] == 'OO'}
    pending = list(geometry_models)
    while pending:
        parent = parents.get(pending.pop(), 0)
        if parent and parent not in geometry_models:
            geometry_models.add(parent)
            pending.append(parent)
    for model in named(objects, 'Model'):
        if model['values'][0] not in geometry_models:
            continue  # LEVEL helpers have translations but no mesh geometry.
        for group in named(model['children'], 'Properties70'):
            for p in group['children']:
                v = p['values']
                if v[0] in ('Lcl Translation', 'Lcl Rotation', 'GeometricTranslation', 'GeometricRotation') and any(abs(float(x)) > 1e-8 for x in v[-3:]):
                    raise ValueError('Nonidentity FBX transform: ' + str(v))
                if v[0] in ('Lcl Scaling', 'GeometricScaling') and any(abs(float(x)-1) > 1e-8 for x in v[-3:]):
                    raise ValueError('Nonidentity FBX scale: ' + str(v))
    meshes = []
    for geo in named(objects, 'Geometry'):
        v = named(geo['children'], 'Vertices')[0]['values'][0]
        indices = named(geo['children'], 'PolygonVertexIndex')[0]['values'][0]
        polygons, face = [], []
        for i in indices:
            face.append(-i - 1 if i < 0 else i)
            if i < 0:
                polygons.append(face); face = []
        triangles = [ [f[0], f[i], f[i+1]] for f in polygons for i in range(1, len(f)-1)]
        meshes.append({'name': str(geo['values'][1]).split('\x00')[0],
                       'vertices': [v[i:i+3] for i in range(0, len(v), 3)],
                       'triangles': triangles, 'polygon_sizes': list(map(len, polygons))})
    if not meshes:
        raise ValueError('No mesh geometry')
    return {'units': 'm', 'meshes': meshes, 'helpers': [], 'fbx_settings': settings}


def read_obj(path):
    vertices, polygons = [], []
    for line in Path(path).read_text(encoding='utf-8', errors='strict').splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == 'v':
            vertices.append([float(x) for x in fields[1:4]])
        elif fields[0] == 'f':
            f = [int(x.split('/')[0]) for x in fields[1:]]
            polygons.append([i-1 if i > 0 else len(vertices)+i for i in f])
    if not vertices or not polygons:
        raise ValueError('Empty OBJ')
    return {'units': 'unspecified', 'helpers': [], 'meshes': [{'name': 'obj', 'vertices': vertices,
             'triangles': [[f[0], f[i], f[i+1]] for f in polygons for i in range(1, len(f)-1)],
             'polygon_sizes': list(map(len, polygons))}]}
