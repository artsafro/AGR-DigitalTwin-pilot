"""new-case: #1729 FBX material-map channels of a binary FBX: where the metallic map sits, which embedded maps a Max
FBX import left unconnected, and where to reconnect them (stdlib only; no pymxs, no Blender).

Measured 2026-11-21 (evidence C:/x/ev_t_505f2a0e, docs/domain/fbx-metallic-channel.md):
* 3ds Max 2026.3 FBX export (binary 2014) writes Standardmaterial.specularLevelMap to `SpecularFactor`,
  reflectionMap to `ReflectionColor`, PhysicalMaterial.metalness_map to `3dsMax|Parameters|metalness_map`
  (MAX_STANDARD_EXPORT).
* SINTEZ AGR Checker 1.6.1 (Blender 5.1.2) takes Metallic only from METALLIC_CHANNELS; a map on `SpecularFactor`
  lands on «Specular IOR Level» and 2.5.6 fails («metallic и roughness в паре» + «недопустимая карта»).
* 3ds Max 2026.3 FBX import does not connect a texture on `ReflectionFactor` (the customer Staropetrovskiy Ground
  FBX lost its 7 `_m` maps; it also dropped the Flora `TransparencyFactor` map), so a readback after import is
  required: every embedded map is connected in the scene or listed with its material, channel and role.

Fail closed: a non-binary or truncated FBX raises ValueError naming the file problem; an unknown FBX channel has
role None and is reported by name, never given a default role.
"""
import posixpath
import re
import struct
import zlib

MAGIC = b'Kaydara FBX Binary  \x00\x1a\x00'
# SINTEZ 1.6.1 scripts/fbx_material_sync.py `_SLOT_SOURCES["Metallic"]` (read 2026-11-21, not copied) and the
# Blender importers: the FBX channels a metallic map is read from. SpecularFactor is NOT among them.
METALLIC_CHANNELS = ('ReflectionFactor', 'ReflectionColor', '3dsMax|maps|texmap_reflection',
                     '3dsMax|Parameters|metalness_map')
# FBX channel -> names_core role (import recognition). Channels not listed have no role and are reported.
FBX_ROLES = {
    'DiffuseColor': 'diffuse', '3dsMax|maps|texmap_diffuse': 'diffuse', '3dsMax|Parameters|base_color_map': 'diffuse',
    'ShininessExponent': 'roughness', '3dsMax|Parameters|roughness_map': 'roughness',
    'NormalMap': 'normal', 'Bump': 'normal', '3dsMax|maps|texmap_bump': 'normal', '3dsMax|Parameters|bump_map': 'normal',
    'TransparentColor': 'opacity', 'TransparencyFactor': 'opacity', '3dsMax|Parameters|cutout_map': 'opacity',
    'EmissiveColor': 'emission', '3dsMax|Parameters|emission_map': 'emission',
}
FBX_ROLES.update({c: 'metalness' for c in METALLIC_CHANNELS})
# 3ds Max 2026.3 FBX exporter, Standardmaterial slot -> FBX channel (measured; diffuse/gloss/spec level/reflection).
MAX_STANDARD_EXPORT = {'diffuseMap': 'DiffuseColor', 'glossinessMap': 'ShininessExponent',
                       'specularLevelMap': 'SpecularFactor', 'reflectionMap': 'ReflectionColor'}
# names_core role -> material slot a reconnect writes (the SLOT_TABLE slot of that role, #1729).
RECONNECT_SLOT = {
    'Standardmaterial': {'diffuse': 'diffuseMap', 'roughness': 'glossinessMap', 'metalness': 'reflectionMap',
                         'opacity': 'opacityMap', 'normal': 'bumpMap'},
    'PhysicalMaterial': {'diffuse': 'base_color_map', 'roughness': 'roughness_map', 'metalness': 'metalness_map',
                         'opacity': 'cutout_map', 'normal': 'bump_map', 'emission': 'emission_map'},
}
_M_STEM = re.compile(r'_m(?:_\d+)?(?:[._]1\d{3})?$', re.IGNORECASE)  # NPM `_m` / `_m_<slot>` (+ UDIM)


# ---- binary FBX walk ------------------------------------------------------------------------------------
def _need(at, size, end):
    if size < 0 or at < 0 or at + size > end:
        raise ValueError('truncated FBX node at offset {}'.format(at))


def _props(data, start, end, count):
    out, at = [], start
    for _ in range(count):
        _need(at, 1, end)
        code = chr(data[at])
        at += 1
        if code in 'YCIFDL':
            size = {'Y': 2, 'C': 1, 'I': 4, 'F': 4, 'D': 8, 'L': 8}[code]
            _need(at, size, end)
            fmt = {'Y': '<h', 'C': '<B', 'I': '<i', 'F': '<f', 'D': '<d', 'L': '<q'}[code]
            out.append(struct.unpack_from(fmt, data, at)[0])
            at += size
        elif code in 'SR':
            _need(at, 4, end)
            n = struct.unpack_from('<I', data, at)[0]
            at += 4
            _need(at, n, end)
            out.append(data[at:at + n] if code == 'R' else data[at:at + n].decode('utf-8', 'replace'))
            at += n
        elif code in 'fdlib':
            _need(at, 12, end)
            _n, enc, size = struct.unpack_from('<III', data, at)
            at += 12
            _need(at, size, end)
            at += size
            out.append(None)
        else:
            raise ValueError('unknown FBX property type {!r} at offset {}'.format(code, at - 1))
    return out


def _nodes(data, start, end, version):
    wide = version >= 7500
    hlen = 25 if wide else 13
    at = start
    while at < end:
        _need(at, hlen, end)
        if data[at:at + hlen] == b'\x00' * hlen:
            return
        stop, count, plen = struct.unpack_from('<QQQ' if wide else '<III', data, at)
        nlen = data[at + hlen - 1]
        name_at = at + hlen
        if stop <= at or stop > end or name_at + nlen + plen > stop:
            raise ValueError('truncated FBX node at offset {}'.format(at))
        props_at = name_at + nlen
        yield {'name': data[name_at:props_at].decode('latin-1'), 'count': count, 'props_at': props_at,
               'props_end': props_at + plen, 'end': stop}
        at = stop


def _version(data):
    if len(data) < 27 or data[:23] != MAGIC:
        raise ValueError('not a binary FBX (ASCII or unknown header): its maps cannot be read')
    return struct.unpack_from('<I', data, 23)[0]


def _base(path):
    return posixpath.basename(str(path or '').replace('\\', '/'))


def read_material_maps(data):
    """{'materials': {material: [{'channel', 'file', 'role'}]}, 'embedded': {basename_lower: {'file', 'bytes'}},
    'conflicts': [...]} of a binary FBX (bytes). 'role' is FBX_ROLES[channel] or None (reported, not guessed)."""
    version = _version(data)
    top = {n['name']: n for n in _nodes(data, 27, len(data), version)}
    if 'Objects' not in top or 'Connections' not in top:
        raise ValueError('FBX has no Objects/Connections section')
    objs = {}
    for o in _nodes(data, top['Objects']['props_end'], top['Objects']['end'], version):
        if o['name'] not in ('Material', 'Texture', 'Video'):
            continue
        p = _props(data, o['props_at'], o['props_end'], o['count'])
        rec = {'kind': o['name'], 'name': str(p[1]).split('\x00')[0], 'file': None, 'content': None}
        for c in _nodes(data, o['props_end'], o['end'], version):
            if c['name'] in ('RelativeFilename', 'FileName', 'Filename', 'Content'):
                v = _props(data, c['props_at'], c['props_end'], c['count'])
                if not v:
                    continue
                if c['name'] == 'Content':
                    rec['content'] = v[0] if isinstance(v[0], bytes) else None
                elif v[0] and (rec['file'] is None or c['name'] == 'RelativeFilename'):
                    rec['file'] = str(v[0])
        objs[p[0]] = rec
    links, video_of = [], {}
    for c in _nodes(data, top['Connections']['props_end'], top['Connections']['end'], version):
        p = _props(data, c['props_at'], c['props_end'], c['count'])
        if len(p) < 3 or p[1] not in objs or p[2] not in objs:
            continue
        child, parent = objs[p[1]], objs[p[2]]
        if p[0] == 'OO' and child['kind'] == 'Video' and parent['kind'] == 'Texture':
            video_of[p[2]] = child
        elif p[0] == 'OP' and child['kind'] == 'Texture' and parent['kind'] == 'Material' and len(p) > 3:
            links.append((parent['name'], str(p[3]), p[1]))
    materials = {o['name']: [] for o in objs.values() if o['kind'] == 'Material'}
    for mat, channel, tex_id in links:
        tex = objs[tex_id]
        f = (video_of.get(tex_id) or {}).get('file') or tex['file']
        materials[mat].append({'channel': channel, 'file': _base(f), 'role': FBX_ROLES.get(channel)})
    embedded, conflicts = {}, []
    for o in objs.values():
        if o['kind'] != 'Video' or not o['content']:
            continue
        key = _base(o['file']).lower()
        h = zlib.crc32(o['content'])
        if key in embedded and embedded[key]['crc32'] != h:
            conflicts.append('{}: embedded twice with different content'.format(_base(o['file'])))
        embedded.setdefault(key, {'file': _base(o['file']), 'bytes': len(o['content']), 'crc32': h})
    return {'materials': materials, 'embedded': embedded, 'conflicts': conflicts}


def read_fbx(path):
    with open(path, 'rb') as f:
        return read_material_maps(f.read())


# ---- export side: the metallic map must sit on a SINTEZ metallic channel --------------------------------
def is_metal_file(name):
    stem = posixpath.splitext(_base(name))[0]
    return bool(_M_STEM.search(stem))


def metallic_channel_findings(doc):
    """[{'material', 'file', 'channel', 'reason'}]: an `_m` map on a channel SINTEZ does not read as Metallic
    (SpecularFactor is «Specular IOR Level» there: 2.5.6 fails), or any map on SpecularFactor. Empty = pass."""
    out = []
    for mat in sorted(doc['materials']):
        for link in doc['materials'][mat]:
            ch = link['channel']
            if ch in METALLIC_CHANNELS:
                continue
            if ch == 'SpecularFactor' or is_metal_file(link['file']):
                out.append({'material': mat, 'file': link['file'], 'channel': ch,
                            'reason': '{} on {}: SINTEZ 2.5.6 reads Metallic only from {}'.format(
                                link['file'], ch, ', '.join(METALLIC_CHANNELS))})
    return out


def export_channel(slot):
    """FBX channel the Max 2026 exporter writes a Standardmaterial slot to; an unmeasured slot is an error."""
    if slot not in MAX_STANDARD_EXPORT:
        raise KeyError('Standardmaterial slot {!r}: FBX export channel not measured'.format(slot))
    return MAX_STANDARD_EXPORT[slot]


# ---- import side: every embedded map is connected or listed ---------------------------------------------
def unconnected_embedded(doc, connected):
    """Embedded maps of the FBX that the scene does not use. `connected`: iterable of file paths (any folder) or
    rows {'file': path} of the maps connected in the scene after the import. Each row:
    {'file', 'materials': [(material, channel, role)], 'role'} (role None when its channel has none)."""
    if connected is None:
        raise ValueError('connected maps of the scene are required (None given)')
    used = {_base(r['file'] if isinstance(r, dict) else r).lower() for r in connected}
    users = {}
    for mat in sorted(doc['materials']):
        for link in doc['materials'][mat]:
            users.setdefault(link['file'].lower(), []).append((mat, link['channel'], link['role']))
    rows = []
    for key in sorted(doc['embedded']):
        if key in used:
            continue
        who = users.get(key, [])
        roles = sorted({r for _m, _c, r in who if r})
        rows.append({'file': doc['embedded'][key]['file'], 'materials': who,
                     'role': roles[0] if len(roles) == 1 else None})
    return rows


def reconnect_plan(rows, scene_materials):
    """Plan reconnecting unconnected maps. scene_materials: {material name: {'class', 'slots': {slot: file|None}}}.
    -> {'connect': [{'material', 'slot', 'file', 'role', 'channel'}], 'failures': [{'file', 'reason'}]}.
    A map with no role, a material missing in the scene, an unsupported class or an occupied slot is a failure."""
    plan = {'connect': [], 'failures': []}
    for row in rows:
        if not row['materials']:
            plan['failures'].append({'file': row['file'], 'reason': 'embedded but used by no FBX material'})
        for mat, channel, role in row['materials']:
            sm = scene_materials.get(mat)
            if role is None:
                plan['failures'].append({'file': row['file'], 'reason': '{}: FBX channel {} has no map role'.format(
                    mat, channel)})
            elif sm is None:
                plan['failures'].append({'file': row['file'], 'reason': 'material {} not in the scene'.format(mat)})
            elif sm.get('class') not in RECONNECT_SLOT or role not in RECONNECT_SLOT[sm['class']]:
                plan['failures'].append({'file': row['file'], 'reason': '{}: class {} has no {} slot'.format(
                    mat, sm.get('class'), role)})
            else:
                slot = RECONNECT_SLOT[sm['class']][role]
                held = (sm.get('slots') or {}).get(slot)
                if held and _base(held).lower() != row['file'].lower():
                    plan['failures'].append({'file': row['file'], 'reason': '{}.{} already holds {}'.format(
                        mat, slot, _base(held))})
                else:
                    plan['connect'].append({'material': mat, 'slot': slot, 'file': row['file'], 'role': role,
                                            'channel': channel})
    return plan


def import_readback(doc, connected):
    """Readback after a customer FBX import: {'embedded', 'connected', 'unconnected': rows, 'conflicts', 'status',
    'passed'}. status 'pass' only when maps are embedded and all are connected; an FBX without embedded maps is
    'no_embedded_maps' (nothing proven, not a pass)."""
    rows = unconnected_embedded(doc, connected)
    status = 'no_embedded_maps' if not doc['embedded'] else 'fail' if rows or doc['conflicts'] else 'pass'
    return {'embedded': len(doc['embedded']), 'connected': len(doc['embedded']) - len(rows), 'unconnected': rows,
            'conflicts': list(doc['conflicts']), 'status': status, 'passed': status == 'pass'}
