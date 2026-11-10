"""new-case: AGR Tools 1.0 (#1024) shared contract: roles, opening/level markers, object references, host adapter.

Owned by branch 0; changed only by a tiny separate PR (SPLIT.md «Владельцы общих модулей»). Stdlib only, no pymxs:
the cores take plain data (ObjRef, dicts), never Max objects, so the same core runs under a Blender adapter later
(BRANCH0-U-L12-ADDENDUM «Ветка 0»: ObjRef instead of a bare handle, HostAdapter for *_max.py).

Contract К1 (#1024 issue body): user property `agr_role` in ROLES, layer `<ROLE>_*`; the opening marker is a Point
helper `OPEN_<nnn>` with role `opening`, user props `agr_window_type` (library id, a string) and `agr_opening`
(JSON: w, h, sill, depth, wall, corner); height helpers `LEVEL_<name>` (D044-D046); working body names
`BODY_<material>_NNN`; the agent writes only into the layer `AGENT_<req-id>` (К4, owner answer 06.11.2026).
"""
import json
import math
import re

CONTRACT_VERSION = 1
ROLES = ('body', 'opening', 'window', 'glass', 'capsule', 'roof', 'parapet', 'equipment', 'decor', 'helper')
ROLE_PROP = 'agr_role'
WINDOW_TYPE_PROP = 'agr_window_type'
OPENING_PROP = 'agr_opening'
PASSPORT_PROP = 'agr_passport'  # scene file property: {"path": ..., "sha256": ...} of jobs/<ID>/passport.json
OPENING_FIELDS = ('w', 'h', 'sill', 'depth', 'wall', 'corner')
OPEN_RE = re.compile(r'^OPEN_(\d{3})$')
LEVEL_RE = re.compile(r'^LEVEL_([A-Za-z0-9]+)$')
BODY_RE = re.compile(r'^BODY_([A-Za-z0-9]+)_(\d{3})$')
AGENT_LAYER_RE = re.compile(r'^AGENT_([A-Za-z0-9][A-Za-z0-9-]{0,63})$')
WINDOW_TYPE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
HOSTS = ('max', 'blender', 'offline')


def check_role(role):
    if role not in ROLES:
        raise ValueError('unknown agr_role {!r}; expected one of {}'.format(role, ', '.join(ROLES)))
    return role


def role_layer(role):
    """Layer name prefix of a role: `body` -> `BODY_`."""
    return check_role(role).upper() + '_'


def opening_name(n):
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 999:
        raise ValueError('opening number must be 1..999: {!r}'.format(n))
    return 'OPEN_{:03d}'.format(n)


def opening_number(name):
    m = OPEN_RE.match(str(name))
    if not m or m.group(1) == '000':
        raise ValueError('not an opening marker name OPEN_<nnn>: {!r}'.format(name))
    return int(m.group(1))


def level_name(name):
    if not LEVEL_RE.match('LEVEL_' + str(name)):
        raise ValueError('level name must be [A-Za-z0-9]+: {!r}'.format(name))
    return 'LEVEL_' + str(name)


def body_name(material, n):
    name = 'BODY_{}_{:03d}'.format(material, n) if isinstance(n, int) and 1 <= n <= 999 else None
    if name is None or not BODY_RE.match(name):
        raise ValueError('working body name BODY_<material>_NNN: {!r} {!r}'.format(material, n))
    return name


def agent_layer(req_id):
    name = 'AGENT_' + str(req_id)
    if not AGENT_LAYER_RE.match(name):
        raise ValueError('agent request id must be [A-Za-z0-9-], 1..64: {!r}'.format(req_id))
    return name


def check_window_type(value):
    if not isinstance(value, str) or not WINDOW_TYPE_RE.match(value):
        raise ValueError('agr_window_type is a library id string: {!r}'.format(value))
    return value


def parse_opening(text):
    """`agr_opening` JSON -> dict with metres > 0 (w, h, depth), sill >= 0, wall and corner as given."""
    try:
        data = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or set(data) != set(OPENING_FIELDS):
        raise ValueError('agr_opening must be a JSON object with exactly {}'.format(', '.join(OPENING_FIELDS)))
    for k in ('w', 'h', 'depth', 'sill'):
        v = data[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or \
                (k != 'sill' and v == 0):
            raise ValueError('agr_opening.{} must be a finite number of metres{}: {!r}'.format(
                k, ' >= 0' if k == 'sill' else ' > 0', v))
    if not isinstance(data['wall'], str) or not data['wall']:
        raise ValueError('agr_opening.wall must name the wall object')
    if not isinstance(data['corner'], bool):
        raise ValueError('agr_opening.corner must be true or false')
    return data


def dump_opening(w, h, sill, depth, wall, corner):
    data = {'w': w, 'h': h, 'sill': sill, 'depth': depth, 'wall': wall, 'corner': corner}
    text = json.dumps(data, sort_keys=True)
    parse_opening(text)
    return text


# ---- object references (host-neutral) -------------------------------------------------------------------------
def obj_ref(host, doc, handle, name):
    """ObjRef: what the cores, the journal and MCP pass instead of a bare handle or a pymxs node.

    host: max | blender | offline; doc: scene path or 'untitled'; handle: the host's stable integer id (Max node
    handle, Blender session uid); name: the object name at the time of the reference (a hint, not the key)."""
    if host not in HOSTS:
        raise ValueError('ObjRef host must be one of {}: {!r}'.format(HOSTS, host))
    if isinstance(handle, bool) or not isinstance(handle, int) or handle < 1:
        raise ValueError('ObjRef handle must be a positive integer: {!r}'.format(handle))
    if not isinstance(doc, str) or not doc or not isinstance(name, str):
        raise ValueError('ObjRef needs doc and name strings')
    return {'host': host, 'doc': doc, 'handle': handle, 'name': name}


def check_ref(ref):
    if not isinstance(ref, dict) or set(ref) != {'host', 'doc', 'handle', 'name'}:
        raise ValueError('ObjRef must be {host, doc, handle, name}: ' + repr(ref)[:120])
    return obj_ref(ref['host'], ref['doc'], ref['handle'], ref['name'])


class HostAdapter:
    """Interface of a host adapter (`host_max.py` for 3ds Max; a `*_bpy.py` adapter later for Blender).

    Cores receive data from it, never host objects. Every method that changes the scene runs inside `undo(label)`
    (one undo record; the runtime's single-undo wrapper on Max). Units: `m_per_unit()` from units.SystemScale,
    never units.decodeValue (IMPL.md)."""
    host = 'offline'

    def doc(self):
        raise NotImplementedError

    def m_per_unit(self):
        raise NotImplementedError

    def refs(self, nodes):
        """Host objects -> [ObjRef]."""
        raise NotImplementedError

    def resolve(self, refs):
        """[ObjRef] -> host objects; an unknown or renamed-away ref is an error naming it."""
        raise NotImplementedError

    def selection(self):
        """[ObjRef] of the current selection."""
        raise NotImplementedError

    def mesh(self, ref):
        """{'verts': [[x, y, z]...] in metres, world space; 'faces': [[i...]...]; 'mat_ids': [...]; 'ref': ref}."""
        raise NotImplementedError

    def get_prop(self, ref, key):
        raise NotImplementedError

    def set_prop(self, ref, key, value):
        raise NotImplementedError

    def role(self, ref):
        value = self.get_prop(ref, ROLE_PROP)
        return None if value in (None, '') else check_role(value)

    def set_role(self, ref, role):
        self.set_prop(ref, ROLE_PROP, check_role(role))

    def undo(self, label):
        """Context manager: one undo record for everything inside."""
        raise NotImplementedError
