"""new-case: source-bound roof library extraction plan, not a semantic classifier or delivery gate."""

import re


def validate_plan(doc):
    """Validate explicit source bindings before any native output is created.

    A face is claimed once per source object. Material slots are explicit local
    indices, never inferred AGR IDs. No dimension or equipment-type guessing.
    """
    if not isinstance(doc, dict) or set(doc) != {'schema', 'source_sha256', 'assets'}:
        raise ValueError('schema: expected schema, source_sha256 and assets')
    if doc['schema'] != 'roof-extraction/1':
        raise ValueError('unsupported schema')
    if not isinstance(doc['source_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', doc['source_sha256']):
        raise ValueError('source_sha256: expected lowercase SHA-256')
    if not isinstance(doc['assets'], list) or not doc['assets']:
        raise ValueError('assets: expected a nonempty list')
    ids, components, claims = set(), set(), set()
    keys = {'id', 'name', 'component', 'faces', 'source_object', 'triangles', 'material_slot'}
    for row in doc['assets']:
        if not isinstance(row, dict) or set(row) != keys:
            actual = set(row) if isinstance(row, dict) else set()
            raise ValueError(f'asset keys: missing {sorted(keys-actual)}, unknown {sorted(actual-keys)}')
        if not isinstance(row['id'], str) or not re.fullmatch('[A-Za-z0-9_-]+', row['id']):
            raise ValueError('asset id: unsafe or empty')
        for field in ('name', 'component', 'source_object'):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f'{row["id"]}: empty {field}')
        for field, seen in [('id', ids), ('component', components)]:
            value = row[field].casefold()
            if value in seen:
                raise ValueError(f'duplicate {field}: {row[field]}')
            seen.add(value)
        if type(row['triangles']) is not int or row['triangles'] <= 0:
            raise ValueError(f'{row["id"]}: invalid triangles')
        if type(row['material_slot']) is not int or row['material_slot'] < 0:
            raise ValueError(f'{row["id"]}: invalid material_slot')
        faces = row['faces']
        if not isinstance(faces, list) or not faces or any(type(f) is not int or f < 0 for f in faces):
            raise ValueError(f'{row["id"]}: invalid faces')
        for face in faces:
            claim = (row['source_object'], face)
            if claim in claims:
                raise ValueError(f'{row["id"]}: duplicate/overlapping face {face}')
            claims.add(claim)
    return doc
