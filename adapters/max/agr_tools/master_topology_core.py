"""new-case: read-only pre-export master polygon-degree QA (#1420).

Shared stdlib core for Max AGR Tools and agent CLI. Input is the evaluated working
master BEFORE export triangulation, not delivery readback. Triangles are allowed;
quads are preferred; any n-gon fails (D312). Face IDs are object-local, 1-based.
This check cannot decide whether a triangle could have been avoided.
"""


def check(objects):
    """Count every face; refuse incomplete/ambiguous inventories without a verdict."""
    if not isinstance(objects, list) or not objects:
        raise ValueError('empty or unsupported master object inventory')
    names, rows = set(), []
    for obj in objects:
        if not isinstance(obj, dict) or set(obj) != {'name', 'face_degrees'}:
            raise ValueError('unmapped master object keys: ' + repr(obj))
        name = obj['name']
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError('empty or duplicate master object name: ' + repr(name))
        names.add(name)
        degrees = obj['face_degrees']
        if not isinstance(degrees, list) or not degrees:
            raise ValueError('empty or unsupported faces: ' + name)
        for i, degree in enumerate(degrees, 1):
            if type(degree) is not int or degree < 3:
                raise ValueError(f'invalid face degree: {name} face {i}: {degree!r}')
        tris, quads = degrees.count(3), degrees.count(4)
        ngons = [i for i, d in enumerate(degrees, 1) if d > 4]
        rows.append({'name': name, 'status': 'fail' if ngons else 'pass',
                     'faces': len(degrees), 'triangles': tris,
                     'triangle_share': tris / len(degrees), 'quads': quads,
                     'ngons': len(ngons), 'ngon_face_ids': ngons})
    return {'tool': 'master_topology', 'stage': 'before_export_triangulation',
            'status': 'fail' if any(r['ngons'] for r in rows) else 'pass',
            'objects': rows}
