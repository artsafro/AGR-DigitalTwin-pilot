"""new-case: AGR Tools 1.0 (#1024) agent request (K4) / agent accept gate (K4), 3ds Max side. owned by branch U (improve/issue-1024-agent-bridge).

runtime.edits_100 calls `<function>(ctx, mode, nodes, preview)` for `agent_request` (agent.request), `agent_accept`
(agent.accept). ctx: agr (runtime globals), core (agentbridge_core), edit (edit_core), emax (edit_max), options
(dict of the preview), host (host_max.MaxHost: ObjRef, user props, one undo record). Apply comes only from the panel
(the runtime refuses actor mcp/agent with needs_human). Import pymxs inside functions so this file loads under
plain pytest. No MAXScript globals.

`agent_dock()` is the body of the `agent.dock` button (registered by branch 0 / R): it starts the AGR listener in this
Max (our pipe, main-thread queue on a Qt timer), the agr-mcp daemon for this Max (one per host, Streamable HTTP,
profile `modeller` by default) and opens the Claude dock (src/agr_mcp/max_side/agr_dock.py of the pilot clone).
"""
import hashlib
import json
import os

UNITS = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'kilometers': 1000.0, 'inches': 0.0254,
         'feet': 0.3048, 'miles': 1609.344}


def _rt():
    from pymxs import runtime
    return runtime


# ---- scene state (baseline of the accept gate) ---------------------------------------------------------------------
def _mesh_digest(rt, n):
    if not rt.canConvertTo(n, rt.TriMeshGeometry):
        return None
    m = rt.snapshotAsMesh(n)
    try:
        h = hashlib.sha256()
        nv, nf = int(m.numverts), int(m.numfaces)
        h.update('{} {}|'.format(nv, nf).encode())
        for i in range(1, nv + 1):
            p = rt.getVert(m, i)
            h.update('{:.6f},{:.6f},{:.6f};'.format(float(p.x), float(p.y), float(p.z)).encode())
        for i in range(1, nf + 1):
            f = rt.getFace(m, i)
            h.update('{},{},{},{};'.format(int(f.x), int(f.y), int(f.z), int(rt.getFaceMatID(m, i))).encode())
        return h.hexdigest()
    finally:
        rt.delete(m)


def object_state(rt, n):
    tm = n.transform
    parent, mat = n.parent, n.material
    return {'class': str(rt.classOf(n)),
            'tm': [[round(float(c), 6) for c in (r.x, r.y, r.z)] for r in (tm.row1, tm.row2, tm.row3, tm.row4)],
            'mesh': _mesh_digest(rt, n), 'material': None if mat is None else str(mat.name),
            'parent': None if parent is None else int(parent.inode.handle), 'hidden': bool(n.isHidden),
            'props': str(rt.getUserPropBuffer(n))}


def scene_hashes(rt=None):
    """{str(handle): {'name', 'layer', 'hash'}} of every object of the open scene."""
    rt = rt or _rt()
    out = {}
    for n in rt.objects:
        state = {'name': str(n.name), 'layer': str(n.layer.name), 'state': object_state(rt, n)}
        blob = json.dumps(state, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
        out[str(int(n.inode.handle))] = {'name': state['name'], 'layer': state['layer'],
                                        'hash': hashlib.sha256(blob.encode('ascii')).hexdigest()}
    return out


def _props(rt, n):
    out = {}
    for key in ('agr_role', 'agr_opening', 'agr_window_type', 'agr_agent_source', 'agr_agent_op',
                'agr_agent_request'):
        v = rt.getUserProp(n, key)
        if v is not None:
            out[key] = str(v)
    return out


def _layer_nodes(rt, name):
    return [n for n in rt.objects if str(n.layer.name) == name]


def _layers(rt):
    return [str(rt.LayerManager.getLayer(i).name) for i in range(int(rt.LayerManager.count))]


def _ensure_layer(rt, name):
    layer = rt.LayerManager.getLayerFromName(name)
    return layer if layer is not None else rt.LayerManager.newLayerFromName(name)


def passport(rt=None):
    """(path, data) of the scene's project passport (file property agr_passport), or (None, {})."""
    rt = rt or _rt()
    try:
        i = int(rt.fileProperties.findProperty(rt.name('custom'), 'agr_passport'))
        if i <= 0:
            return None, {}
        prop = json.loads(str(rt.fileProperties.getPropertyValue(rt.name('custom'), i)))
        path = prop.get('path')
        with open(path, encoding='utf-8') as f:
            return path, json.load(f)
    except Exception:  # noqa: BLE001 - no passport yet (branch F): options name the job folder
        return None, {}


def _excerpt(data):
    keys = ('project_id', 'address', 'object', 'stage', 'stages', 'decisions', 'units')
    return {k: data[k] for k in keys if k in data}


# ---- agent.request -------------------------------------------------------------------------------------------------
def _request_targets(ctx, nodes, preview):
    rt = _rt()
    if preview is not None:
        handles = preview['plan']['targets']
        nodes = []
        for h in handles:
            n = rt.maxOps.getNodeByHandle(int(h))
            if n is None or not rt.isValidNode(n):
                raise ctx.edit.StalePreview('object #{} of the preview is gone; run preview again'.format(h))
            nodes.append(n)
    nodes = list(nodes or [])
    if not nodes:
        raise ValueError('agent.request: empty input - select the objects of the task')
    return nodes


def agent_request(ctx, mode, nodes, preview):
    rt = _rt()
    core, edit, host = ctx.core, ctx.edit, ctx.host
    opt = core.options(preview['plan']['options'] if preview is not None else ctx.options)
    nodes = _request_targets(ctx, nodes, preview)
    pp_path, pp = passport(rt)
    job_dir = opt['job_dir'] or (os.path.dirname(pp_path) if pp_path else None)
    if not job_dir:
        raise ValueError('agent.request: options.job_dir (jobs/<ID>) is required while the scene has no passport')
    project_id = opt['project_id'] or pp.get('project_id') or os.path.basename(os.path.normpath(job_dir))
    agent_dir = os.path.join(job_dir, 'agent')
    taken = os.listdir(agent_dir) if os.path.isdir(agent_dir) else []
    rid = opt['request_id'] or (preview['plan']['request_id'] if preview is not None else core.next_request_id(taken))
    folder = os.path.join(agent_dir, rid)
    layer = 'AGENT_' + rid
    if mode == 'preview' and os.path.exists(folder):
        raise FileExistsError('refusing to overwrite: ' + folder)
    refs = host.refs(nodes)
    objects, entries = [], []
    for n, ref in zip(nodes, refs):
        findings = []
        try:
            role = host.role(ref)
        except ValueError as exc:
            role = None
            findings.append(edit.finding('role_unknown', (), str(exc)))
        for code, detail in core.target_findings(str(n.layer.name)):
            findings.append(edit.finding(code, (), detail))
        objects.append({'ref': ref, 'role': role, 'layer': str(n.layer.name)})
        entries.append(edit.entry(ref['handle'], ref['name'], findings))
    markers = sorted(str(n.name) for n in rt.objects
                     if host.contract.OPEN_RE.match(str(n.name)) or host.contract.LEVEL_RE.match(str(n.name)))
    request_path = os.path.join(folder, 'request.json')
    command = core.cli_command(opt['cli'], request_path, opt['repo'])
    baseline = scene_hashes(rt)
    state = {'baseline': baseline, 'targets': [r['handle'] for r in refs], 'folder': folder, 'options': opt}
    extra = {'options': opt, 'request_id': rid, 'project_id': project_id, 'folder': folder, 'layer': layer,
             'targets': [r['handle'] for r in refs], 'command': command}
    files = [os.path.join(folder, f) for f in core.FILES]
    if mode == 'preview':
        return edit.report(core.TOOL_REQUEST, 'preview', entries, done=files + ['layer ' + layer],
                           state_hash=edit.fingerprint(state), extra=extra)
    edit.require_current(preview, state)
    os.makedirs(folder)  # a new folder only (FileExistsError otherwise)
    snap = os.path.join(folder, 'snapshot.fbx')
    before = list(rt.selection)
    try:
        rt.clearSelection()
        rt.select(nodes)
        ok = rt.exportFile(snap, rt.name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
    finally:
        rt.clearSelection()
        live = [n for n in before if rt.isValidNode(n)]
        if live:
            rt.select(live)
    if not ok or not os.path.isfile(snap):
        raise RuntimeError('agent.request: FBX snapshot was not written: ' + snap)
    with open(snap, 'rb') as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    try:
        tail = ctx.agr._journal_core().tail(host.doc(), 20)
    except Exception:  # noqa: BLE001
        tail = []
    req = core.build_request(opt, rid, project_id, objects, markers, 'snapshot.fbx', sha, _excerpt(pp), tail,
                             command)
    text = json.dumps(req, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False)
    edit.write_new(request_path, text.encode('utf-8'))
    edit.write_new(os.path.join(folder, 'REQUEST.md'), core.request_md(req, request_path).encode('utf-8'))
    edit.write_new(os.path.join(folder, 'command.txt'), (command + '\n').encode('utf-8'))
    edit.write_new(os.path.join(folder, 'baseline.json'),
                   json.dumps({'schema': 1, 'request_id': rid, 'doc': host.doc(), 'objects': baseline},
                              sort_keys=True).encode('utf-8'))
    with host.undo('AGR Tools: agent.request ' + rid):
        _ensure_layer(rt, layer)
    return edit.report(core.TOOL_REQUEST, 'apply', entries, done=files + ['layer ' + layer],
                       extra={'request_id': rid, 'folder': folder, 'layer': layer, 'snapshot_sha256': sha,
                              'command': command})


# ---- agent.accept --------------------------------------------------------------------------------------------------
def _request_files(core, opt):
    path = opt.get('request')
    if not path and opt.get('job_dir') and opt.get('request_id'):
        path = os.path.join(opt['job_dir'], 'agent', opt['request_id'], 'request.json')
    if not path or not os.path.isfile(path):
        raise ValueError('agent.accept needs options.request (path of request.json) or job_dir + request_id')
    with open(path, encoding='utf-8') as f:
        req = core.validate_request(json.load(f))
    folder = os.path.dirname(path)
    with open(os.path.join(folder, 'baseline.json'), encoding='utf-8') as f:
        baseline = json.load(f)
    return req, folder, baseline


def agent_accept(ctx, mode, nodes, preview):  # noqa: ARG001 - the gate works on the agent layer, not the selection
    rt = _rt()
    core, edit, host = ctx.core, ctx.edit, ctx.host
    opt = dict(preview['plan']['options'] if preview is not None else ctx.options)
    unknown = set(opt) - {'request', 'job_dir', 'request_id', 'originals'}
    if unknown:
        raise ValueError('unknown agent.accept options: ' + ', '.join(sorted(unknown)))
    originals = opt.get('originals', 'hide')
    req, folder, baseline = _request_files(core, opt)
    rid, layer = req['request_id'], req['result_layer']
    current = scene_hashes(rt)
    violations = core.outside_changes(baseline['objects'], current, layer)
    in_layer = [{'handle': int(n.inode.handle), 'name': str(n.name), 'props': _props(rt, n)}
                for n in _layer_nodes(rt, layer)]
    if not in_layer:
        raise ValueError('agent.accept: empty input - layer {} has no objects'.format(layer))
    contract = core_findings = core.layer_findings(in_layer, host.contract)
    moves, hides, ambiguous = core.accept_plan(rid, in_layer, _layers(rt), originals)
    by = {}
    for h, name, code in violations:
        by.setdefault((h, name), []).append(edit.finding(code, (), 'object outside ' + layer))
    for h, name, code, detail in contract:
        by.setdefault((h, name), []).append(edit.finding(code, (), detail))
    entries = [edit.entry(h, name, f) for (h, name), f in sorted(by.items())]
    verdict = 'reject' if (violations or core_findings) else 'accept'
    state = {'current': current, 'layer': layer, 'options': opt}
    extra = {'options': opt, 'request_id': rid, 'layer': layer, 'verdict': verdict, 'folder': folder}
    amb = ['{} (#{}): {}'.format(n, h, why) for h, n, why in ambiguous]
    if verdict == 'reject':
        done = ['reject: {} -> {}_REJECTED (hidden)'.format(o['name'], layer) for o in in_layer]
    else:
        done = ['{} -> {}'.format(name, to) for _h, name, to in moves] + \
               ['hide original #{} -> {}_SOURCE'.format(h, layer) for h in hides]
    if mode == 'preview':
        return edit.report(core.TOOL_ACCEPT, 'preview', entries, done=done, ambiguous=amb,
                           state_hash=edit.fingerprint(state), extra=extra)
    edit.require_current(preview, state)
    if verdict == 'reject':
        with host.undo('AGR Tools: agent.accept reject ' + rid):
            rej = _ensure_layer(rt, layer + '_REJECTED')
            for o in in_layer:
                n = rt.maxOps.getNodeByHandle(o['handle'])
                rej.addNode(n)
                n.isHidden = True
        with open(os.path.join(folder, 'questions.md'), 'a', encoding='utf-8') as f:
            f.write('\n## agent.accept\n\n' + core.question(rid, [(h, n, c) for h, n, c in violations] +
                                                            [(h, n, c) for h, n, c, _d in contract]) + '\n')
        return edit.report(core.TOOL_ACCEPT, 'apply', entries, done=done, ambiguous=amb,
                           extra={'request_id': rid, 'layer': layer, 'verdict': verdict})
    with host.undo('AGR Tools: agent.accept ' + rid):
        for h, _name, to in moves:
            _ensure_layer(rt, to).addNode(rt.maxOps.getNodeByHandle(h))
        if hides:
            src = _ensure_layer(rt, layer + '_SOURCE')
            for h in hides:
                n = rt.maxOps.getNodeByHandle(h)
                if n is not None and rt.isValidNode(n):
                    src.addNode(n)
                    n.isHidden = True
    record = {'schema': 1, 'request_id': rid, 'doc': host.doc(), 'moved': [[h, n, to] for h, n, to in moves],
              'hidden_originals': hides, 'ambiguous': amb}
    target = edit.new_path(os.path.join(folder, 'accepted.json'), version=True)
    edit.write_new(target, json.dumps(record, ensure_ascii=False, sort_keys=True).encode('utf-8'))
    return edit.report(core.TOOL_ACCEPT, 'apply', entries, done=done, ambiguous=amb,
                       extra={'request_id': rid, 'layer': layer, 'verdict': verdict,
                              'accepted': os.path.basename(target)})


# ---- the dock (agent.dock) -----------------------------------------------------------------------------------------
def _side(repo):
    import sys
    side = os.path.join(repo, 'src', 'agr_mcp', 'max_side')
    if not os.path.isfile(os.path.join(side, 'agr_listener.py')):
        raise ValueError('not a pilot clone with the agent bridge: ' + repo)
    if side not in sys.path:
        sys.path.insert(0, side)
    return side


def listener_start(repo=None, timer=True):
    """Start the AGR listener of this Max (idempotent)."""
    _side(repo or os.environ.get('AGR_PILOT_REPO') or r'C:\agr\AGR-DigitalTwin-pilot')
    import agr_listener
    return agr_listener.start(timer=timer)


def daemon_start(repo, profile='modeller', wait_s=60):
    """The daemon of this Max: the registered one, or a new `uv run ... agr_daemon` process."""
    import subprocess
    import time
    import agr_registry
    pid = os.getpid()

    def mine():
        return next((e for e in agr_registry.entries('daemon') if int(e['pid']) == pid), None)
    found = mine()
    if found:
        return found
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.Popen(['uv', 'run', '--directory', repo, 'python', '-m', 'agr_mcp.max_side.agr_daemon', '--max-pid',
                      str(pid), '--profile', profile], cwd=repo, creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + wait_s
    while time.time() < end:
        found = mine()
        if found:
            return found
        time.sleep(0.25)
    raise RuntimeError('host_unavailable: the agr-mcp daemon did not register in {} s'.format(wait_s))


def agent_dock(repo=None, profile='modeller', auth='local', exe=None):
    """Body of the `agent.dock` button: listener + daemon + the Claude dock."""
    repo = repo or os.environ.get('AGR_PILOT_REPO') or r'C:\agr\AGR-DigitalTwin-pilot'
    listener_start(repo)
    daemon = daemon_start(repo, profile)
    import agr_dock
    return agr_dock.open_dock(repo, daemon, profile=profile, auth=auth, exe=exe)
