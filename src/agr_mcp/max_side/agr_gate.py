"""new-case: the D108 gate transaction of the agent bridge (#1024 К4, branch U), stdlib only; runs INSIDE 3ds Max.

The agent never writes into the scene itself. agr-mcp (ops_d108.py, server side, numpy + dt_ai.ops) computes a
*plan* for one D108 operation (create a mesh / a marker in the layer AGENT_<req>, set a property) and holds it as a
preview; this module executes such a plan inside Max, on the main thread, as ONE transaction (mcp-review §3.3 п.4-5):

1. the preview is current: same document, same scene fingerprint (`state_hash`) as when it was planned;
2. a human confirmed exactly this preview id (`confirm()`: the «Применить» button of the dock / panel, in this
   process only; nothing that talks to the listener socket can confirm) - else `needs_human`;
3. hashes of every object OUTSIDE the agent layer are taken;
4. one host transaction (Max: theHold.Begin): the actions run;
5. invariants after: objects outside the layer unchanged and no new object outside it; every object in the layer
   follows the contract (contract_core: roles, OPEN_<nnn> markers, agr_opening); a written mesh reads back equal
   to the mesh the server checked with dt_ai.ops (D115 invariants were computed on exactly that mesh);
6. pass -> accept (one undo record, label `AGR agent: <op>`); fail -> cancel, then the hashes are taken again and
   must equal the hashes before (proof of the rollback), the answer is `rolled_back` with a question.
The user's selection is restored in both cases.

The host (`GateHost` below) is injected: agr_maxhost.MaxGateHost on pymxs, a fake scene in the tests. The plan id is
sha256 of the canonical plan, computed the same way on both sides, so the server cannot swap a confirmed plan.
"""
import hashlib
import json
import re
import time

ROLES = ('body', 'opening', 'window', 'glass', 'capsule', 'roof', 'parapet', 'equipment', 'decor', 'helper')
AGENT_LAYER_RE = re.compile(r'^AGENT_([A-Za-z0-9][A-Za-z0-9-]{0,63})$')
OPEN_RE = re.compile(r'^OPEN_(\d{3})$')
OPENING_FIELDS = ('w', 'h', 'sill', 'depth', 'wall', 'corner')
ACTIONS = ('create_mesh', 'create_point', 'set_prop', 'set_face_ids')
PROP_KEYS = ('agr_role', 'agr_opening', 'agr_window_type', 'agr_agent_source', 'agr_agent_op', 'agr_agent_request',
             'agr_agent_preview')
MESH_TOL_M = 1e-4  # read-back tolerance of a written mesh (system-unit round trip)
_CONFIRMED = {}  # preview id -> time of the human confirmation (process memory only)
_REFUSED = []    # ids an apply was refused for (needs_human): the dock shows them as cards to confirm


class GateError(Exception):
    """str() starts with a machine code: stale_preview, needs_human, invalid_plan, scene_mismatch."""

    def __init__(self, code, text):
        super().__init__(code + ': ' + text)
        self.code = code


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode('ascii')).hexdigest()


def plan_id(plan):
    """The preview id of a plan: sha256 of its canonical JSON (server and Max compute it the same way)."""
    return digest(plan)


def state_hash(objects):
    """Fingerprint of a scene from host.objects(): handle -> sha256(state)."""
    return digest(sorted([o['handle'], object_hash(o)] for o in objects))


def object_hash(obj):
    return digest({'name': obj['name'], 'layer': obj['layer'], 'state': obj['state']})


def hashes(objects, outside_of=None):
    """{handle: hash} of every object, or only of objects not in the layer `outside_of`."""
    return {int(o['handle']): object_hash(o) for o in objects if outside_of is None or o['layer'] != outside_of}


# ---- human confirmation (in-process only) -----------------------------------------------------------------------
def confirm(pid):
    """The dock/panel «Применить» button: confirm one preview id. Only code inside Max calls this."""
    if not isinstance(pid, str) or not re.match(r'^[0-9a-f]{64}$', pid):
        raise GateError('invalid_plan', 'preview id must be 64 hex digits')
    _CONFIRMED[pid] = time.time()
    while pid in _REFUSED:
        _REFUSED.remove(pid)
    return pid


def confirmed(pid):
    return pid in _CONFIRMED


def refused():
    """Preview ids an apply asked for without a confirmation (newest last)."""
    return list(_REFUSED)


def forget(pid):
    _CONFIRMED.pop(pid, None)


# ---- plan check ---------------------------------------------------------------------------------------------------
def check_plan(plan):
    """Shape of a plan; returns the agent layer name. Never trusts the server beyond this shape."""
    if not isinstance(plan, dict):
        raise GateError('invalid_plan', 'plan must be an object')
    for key in ('op', 'request_id', 'layer', 'doc', 'state_hash', 'actions'):
        if key not in plan:
            raise GateError('invalid_plan', 'plan lacks ' + key)
    m = AGENT_LAYER_RE.match(str(plan['layer']))
    if not m or m.group(1) != plan['request_id']:
        raise GateError('invalid_plan', 'layer must be AGENT_<request_id>: ' + repr(plan['layer']))
    if not isinstance(plan['actions'], list) or not plan['actions']:
        raise GateError('invalid_plan', 'plan has no actions')
    for a in plan['actions']:
        if not isinstance(a, dict) or a.get('do') not in ACTIONS:
            raise GateError('invalid_plan', 'unknown action ' + repr(a)[:80])
        if a['do'] in ('create_mesh', 'create_point') and a.get('layer') != plan['layer']:
            raise GateError('invalid_plan', 'a new object must go into ' + plan['layer'])
        if a['do'] == 'set_prop' and a.get('key') not in PROP_KEYS:
            raise GateError('invalid_plan', 'property outside the agent contract: ' + repr(a.get('key')))
    return plan['layer']


# ---- contract invariants of the layer -----------------------------------------------------------------------------
def contract_findings(layer_objects, props_of):
    """Contract К1/К4 of every object in the agent layer: [{'handle', 'name', 'code', 'detail'}]."""
    out = []
    for o in layer_objects:
        props = props_of(o['handle'])
        role = props.get('agr_role')
        name = o['name']
        if role not in (None, '') and role not in ROLES:
            out.append({'handle': o['handle'], 'name': name, 'code': 'role_unknown', 'detail': str(role)})
        if name.startswith('OPEN_'):
            if not OPEN_RE.match(name) or name == 'OPEN_000':
                out.append({'handle': o['handle'], 'name': name, 'code': 'marker_name', 'detail': 'OPEN_<nnn>'})
            if role != 'opening':
                out.append({'handle': o['handle'], 'name': name, 'code': 'marker_role', 'detail': str(role)})
            problem = opening_problem(props.get('agr_opening'))
            if problem:
                out.append({'handle': o['handle'], 'name': name, 'code': 'marker_opening', 'detail': problem})
        elif role == 'opening':
            out.append({'handle': o['handle'], 'name': name, 'code': 'marker_name', 'detail': 'opening not OPEN_<nnn>'})
    return out


def opening_problem(text):
    """None when `agr_opening` is valid JSON by contract_core.parse_opening, else the reason."""
    try:
        data = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or set(data) != set(OPENING_FIELDS):
        return 'agr_opening must hold exactly ' + ', '.join(OPENING_FIELDS)
    for k in ('w', 'h', 'depth', 'sill'):
        v = data[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float('inf'), float('-inf')) \
                or v < 0 or (k != 'sill' and v == 0):
            return 'agr_opening.' + k + ' must be a finite number of metres'
    if not isinstance(data['wall'], str) or not data['wall'] or not isinstance(data['corner'], bool):
        return 'agr_opening.wall / corner invalid'
    return None


def mesh_mismatch(expected, got, tol=MESH_TOL_M):
    """None when the read-back mesh equals the planned one (same triangles, vertices within tol metres)."""
    if len(expected['verts']) != len(got['verts']) or len(expected['tris']) != len(got['tris']):
        return 'size {}v/{}t, planned {}v/{}t'.format(len(got['verts']), len(got['tris']), len(expected['verts']),
                                                       len(expected['tris']))
    if [list(t) for t in expected['tris']] != [list(t) for t in got['tris']]:
        return 'triangles differ from the plan'
    worst = max((abs(a - b) for va, vb in zip(expected['verts'], got['verts']) for a, b in zip(va, vb)), default=0.0)
    if worst > tol:
        return 'vertex off by {:.6f} m'.format(worst)
    return None


# ---- the transaction ----------------------------------------------------------------------------------------------
def _run(host, plan, created):
    for a in plan['actions']:
        do = a['do']
        if do == 'create_mesh':
            h = host.create_mesh(a['layer'], a['name'], a['mesh']['verts'], a['mesh']['tris'], a.get('props') or {})
            created.append((int(h), a))
        elif do == 'create_point':
            h = host.create_point(a['layer'], a['name'], a['pos'], a.get('props') or {})
            created.append((int(h), a))
        elif do == 'set_prop':
            host.set_prop(int(a['handle']), a['key'], a['value'])
        elif do == 'set_face_ids':
            host.set_face_ids(int(a['handle']), list(a['faces']), int(a['mat_id']))


def _violations(host, plan, layer, outside_before, created):
    after = host.objects()
    outside_after = hashes(after, outside_of=layer)
    out = []
    for h, before in sorted(outside_before.items()):
        now = outside_after.get(h)
        if now is None:
            out.append({'handle': h, 'code': 'outside_deleted', 'detail': 'object outside ' + layer + ' disappeared'})
        elif now != before:
            out.append({'handle': h, 'code': 'outside_changed', 'detail': 'object outside ' + layer + ' changed'})
    for h in sorted(set(outside_after) - set(outside_before)):
        out.append({'handle': h, 'code': 'outside_created', 'detail': 'new object outside ' + layer})
    in_layer = [o for o in after if o['layer'] == layer]
    for f in contract_findings(in_layer, host.props):
        out.append(f)
    for h, a in created:
        if a['do'] == 'create_mesh':
            problem = mesh_mismatch(a['mesh'], host.mesh(h))
            if problem:
                out.append({'handle': h, 'code': 'mesh_readback', 'detail': problem})
    return out, after


def question(plan, violations):
    lines = ['{} ({}): the gate rolled the operation back.'.format(plan['op'], plan.get('summary') or plan['layer'])]
    for v in violations[:10]:
        lines.append('- {} #{}: {}'.format(v['code'], v.get('handle'), v.get('detail', '')))
    lines.append('What should the agent do instead? (Only objects in {} may change.)'.format(plan['layer']))
    return '\n'.join(lines)


def apply(host, plan, pid=None):
    """Execute a confirmed plan as one transaction. Returns the gate answer (never raises for a violation)."""
    layer = check_plan(plan)
    pid = pid or plan_id(plan)
    if pid != plan_id(plan):
        raise GateError('invalid_plan', 'preview id does not match the plan')
    if host.doc() != plan['doc']:
        raise GateError('stale_preview', 'document changed since the preview: {} -> {}'.format(plan['doc'],
                                                                                             host.doc()))
    before = host.objects()
    if state_hash(before) != plan['state_hash']:
        raise GateError('stale_preview', 'scene changed since the preview; run the preview again')
    if not confirmed(pid):
        if pid not in _REFUSED:
            _REFUSED.append(pid)
        raise GateError('needs_human', 'press «Применить» for this preview in the AGR Tools dock/panel')
    t0 = time.time()
    selection = host.selection()
    outside_before = hashes(before, outside_of=layer)
    all_before = hashes(before)
    created = []
    label = 'AGR agent: ' + str(plan['op'])
    host.ensure_layer(layer)  # inside the transaction below would also be fine; a layer is not an object
    host.begin()
    error = None
    try:
        _run(host, plan, created)
        violations, after = _violations(host, plan, layer, outside_before, created)
    except Exception as exc:  # noqa: BLE001 - an action that throws is a violation, rolled back like any other
        error = '{}: {}'.format(type(exc).__name__, exc)
        violations = [{'handle': None, 'code': 'action_error', 'detail': error[:300]}]
        after = None
    if violations:
        host.cancel()
        restored = hashes(host.objects())
        proved = restored == all_before
        status = 'rolled_back'
        answer = {'status': status, 'violations': violations, 'rollback_proved': proved,
                  'question': question(plan, violations), 'created': []}
    else:
        host.accept(label)
        answer = {'status': 'applied', 'violations': [], 'rollback_proved': None, 'question': None,
                  'created': [{'handle': h, 'name': a['name']} for h, a in created],
                  'state_hash_after': state_hash(after)}
    host.restore_selection(selection)
    forget(pid)
    answer.update({'preview_id': pid, 'op': plan['op'], 'layer': layer, 'undo_label': label if not violations else None,
                   'outside_checked': len(outside_before), 'duration': round(time.time() - t0, 3),
                   'nested_hold': bool(getattr(host, 'nested', False))})
    return answer


def read(host, handles, neighbours=()):
    """What the server needs to plan an operation: doc, state hash, objects, meshes of handles (+ neighbours)."""
    objs = host.objects()
    known = {int(o['handle']) for o in objs}
    meshes = {}
    for h in list(handles) + list(neighbours):
        if int(h) not in known:
            raise GateError('unknown_handle', 'unknown node handle ' + str(h))
        meshes[str(int(h))] = host.mesh(int(h))
    return {'doc': host.doc(), 'state_hash': state_hash(objs), 'm_per_unit': host.m_per_unit(),
            'objects': [{'handle': o['handle'], 'name': o['name'], 'layer': o['layer'],
                         'props': host.props(o['handle'])} for o in objs],
            'meshes': meshes}
