"""new-case: #1024 branch U native run of the agent bridge in locked batch 3ds Max 2024 on DISPOSABLE scenes.

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the MZP built
from this branch, AGR_PYTHON the branch's venv python (daemon, scenario eval, jsonschema). Installs the MZP into OUT
(no user folders touched; journal, registry, LOCALAPPDATA under OUT), then in the real Max Python:

1. gate_real          agr_gate on agr_maxhost (theHold): a write outside AGENT_<req> rolls back with the hashes
                      restored; a marker + mesh apply is one transaction, the mesh reads back, the selection is kept;
2. one_undo_record    `max undo` once after an apply returns every object hash (measured; batch may lack undo);
3. units_cm           a planned mesh in metres lands in a centimetre scene at x100 and reads back in metres;
4. listener_queue     our listener: a socket thread asks, only the MAIN thread runs pymxs (pump), status answers
                      without the main thread, the bridge call (installed runtime) runs through it; latency;
5. request_scenario   agent.request (panel, preview -> apply: request.json valid by the schema, FBX snapshot sha,
                      layer AGENT_r001), the agr-mcp DAEMON for this Max (subprocess, profile modeller,
                      AGR_MCP_UNSAFE=1 in its env), the К4 eval evals/agent-sim-k4/run.py as the agent (subprocess,
                      real MCP over HTTP), the human presses through files; then agent.accept (panel) -> accept;
6. accept_reject      a second request whose outside object changes -> agent.accept rejects: layer -> _REJECTED,
                      questions.md;
7. polygon_U          stations 1.0.32 / 1.0.33 of test-polygon/stations/U.json pressed as run_inside_max does.
Nothing is saved; the scenes are never written. Timings go to summary.json.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import traceback

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
SIDE = ROOT / 'src' / 'agr_mcp' / 'max_side'
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
PY = os.environ['AGR_PYTHON']
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_MCP_REGISTRY_DIR'] = str(OUT / 'registry')
os.environ['AGR_NO_PROMPT'] = '1'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}, 'timings': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'
sys.path.insert(0, str(SIDE))
import agr_gate  # noqa: E402
import agr_listener  # noqa: E402
import agr_maxhost  # noqa: E402


def check(name, fn):
    t0 = time.time()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['timings'][name] = round(time.time() - t0, 2)


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
    sys.path.insert(0, str(OUT / 'installed'))
    sys.modules.pop('runtime', None)
    import runtime as agr
    return agr


agr = install()
summary['runtime_version'] = agr.VERSION


def fresh(units='meters'):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name(units)
    rt.units.SystemScale = 1.0


def box(name, w, l, h, at, role=None, layer=None):
    b = rt.Box(name=name, width=w, length=l, height=h)
    b.pos = rt.Point3(*at)
    if role:
        rt.setUserProp(b, 'agr_role', role)
    if layer:
        lay = rt.LayerManager.getLayerFromName(layer) or rt.LayerManager.newLayerFromName(layer)
        lay.addNode(b)
    return b


def handle(n):
    return int(n.inode.handle)


def plan(host, actions, op='set_role', rid='r001'):
    return {'op': op, 'request_id': rid, 'layer': 'AGENT_' + rid, 'doc': host.doc(),
            'state_hash': agr_gate.state_hash(host.objects()), 'actions': actions}


BOX = {'verts': [[x, y, z] for z in (0.0, 1.0) for y in (0.0, 1.0) for x in (0.0, 1.0)],
       'tris': [list(t) for a, b, c, d in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2),
                                           (1, 3, 7, 5)) for t in ((a, b, c), (a, c, d))]}
OPENING = json.dumps({'w': 1.2, 'h': 1.5, 'sill': 0.9, 'depth': 0.25, 'wall': 'BODY_Brick_001', 'corner': False},
                     sort_keys=True)


def gate_real():
    fresh()
    body = box('BODY_Brick_001', 4, 3, 6, (0, 0, 0), 'body')
    out = box('SM_Decor_Main', 1, 1, 1, (20, 0, 0), 'decor', 'DECOR_main')
    rt.select(body)
    host = agr_maxhost.MaxGateHost()
    all0 = agr_gate.hashes(host.objects())
    p = plan(host, [{'do': 'set_prop', 'handle': handle(out), 'key': 'agr_role', 'value': 'glass'}])
    agr_gate.confirm(agr_gate.plan_id(p))
    bad = agr_gate.apply(host, p)
    assert bad['status'] == 'rolled_back' and bad['rollback_proved'] is True, bad
    assert [v['code'] for v in bad['violations']] == ['outside_changed'], bad['violations']
    assert str(rt.getUserProp(out, 'agr_role')) == 'decor' and agr_gate.hashes(host.objects()) == all0
    p2 = plan(host, [{'do': 'create_point', 'layer': 'AGENT_r001', 'name': 'OPEN_001', 'pos': [1.0, 0.0, 1.5],
                      'props': {'agr_role': 'opening', 'agr_opening': OPENING}},
                     {'do': 'create_mesh', 'layer': 'AGENT_r001', 'name': 'BODY_Brick_001',
                      'mesh': {'verts': [[v[0] * 4, v[1] * 3, v[2] * 6] for v in BOX['verts']], 'tris': BOX['tris']},
                      'props': {'agr_role': 'body', 'agr_agent_source': str(handle(body))}}], op='mark_opening')
    agr_gate.confirm(agr_gate.plan_id(p2))
    before = agr_gate.hashes(host.objects())
    ok = agr_gate.apply(host, p2)
    assert ok['status'] == 'applied', ok
    layer = sorted(str(n.name) for n in rt.objects if str(n.layer.name) == 'AGENT_r001')
    assert layer == ['BODY_Brick_001', 'OPEN_001'], layer
    assert [handle(n) for n in rt.selection] == [handle(body)], 'selection not restored'
    summary['one_undo_input'] = {'before': before, 'label': ok['undo_label']}
    return {'rolled_back': bad['violations'], 'applied': ok['created'], 'undo_label': ok['undo_label'],
            'gate_s': ok['duration'], 'outside_checked': ok['outside_checked']}


def one_undo_record():
    host = agr_maxhost.MaxGateHost()
    before = summary['one_undo_input']['before']
    after_apply = agr_gate.hashes(host.objects())
    rt.execute('max undo')
    after_undo = agr_gate.hashes(host.objects())
    return {'objects_after_apply': len(after_apply), 'objects_after_undo': len(after_undo),
            'undo_restores_all_hashes': after_undo == before,
            'undo_changed_something': after_undo != after_apply}


def units_cm():
    fresh('centimeters')
    host = agr_maxhost.MaxGateHost()
    mesh = {'verts': [[v[0] * 1, v[1] * 2, v[2] * 3] for v in BOX['verts']], 'tris': BOX['tris']}
    p = plan(host, [{'do': 'create_mesh', 'layer': 'AGENT_r009', 'name': 'BODY_Cm_001', 'mesh': mesh,
                     'props': {'agr_role': 'body'}}], op='keep', rid='r009')
    agr_gate.confirm(agr_gate.plan_id(p))
    ans = agr_gate.apply(host, p)
    assert ans['status'] == 'applied', ans
    n = rt.getNodeByName('BODY_Cm_001')
    bb = n.max
    assert (round(float(bb.x), 3), round(float(bb.y), 3), round(float(bb.z), 3)) == (100.0, 200.0, 300.0), bb
    assert abs(host.m_per_unit() - 0.01) < 1e-12
    return {'max_corner_cm': [float(bb.x), float(bb.y), float(bb.z)]}


def _ask(port, token, req, timeout=60):
    t0 = time.time()
    s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
    s.sendall((json.dumps(dict(req, token=token)) + '\n').encode())
    buf = b''
    while b'\n' not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    s.close()
    return json.loads(buf.split(b'\n')[0]), time.time() - t0


def listener_queue():
    fresh()
    b = box('BODY_Q_001', 2, 2, 2, (0, 0, 0), 'body')
    threads = []

    def factory():
        threads.append(threading.current_thread() is threading.main_thread())
        return agr_maxhost.MaxGateHost()
    lst = agr_listener.Listener(host_factory=factory).start()
    try:
        entry = json.loads((OUT / 'registry' / 'max-{}.json'.format(os.getpid())).read_text(encoding='utf-8'))
        assert entry['port'] == lst.port and entry['token'] == lst.token
        res = {}

        def client():
            res['status'], res['status_s'] = _ask(lst.port, lst.token, {'kind': 'status'})
            lat = []
            for _ in range(5):
                a, dt = _ask(lst.port, lst.token, {'kind': 'gate_read', 'handles': [handle(b)]})
                lat.append(dt)
                res['read'] = a
            res['lat'] = lat
            root = (OUT / 'installed').as_posix().encode().hex()
            args = json.dumps({'scene': 'live', 'handles': [handle(b)], 'check_ids': ['qa.xview']},
                              sort_keys=True).encode().hex()
            res['bridge'], res['bridge_s'] = _ask(lst.port, lst.token, {'kind': 'bridge', 'tool': 'agr_check_run',
                                                                        'root_hex': root, 'args_hex': args}, 600)
            res['exec'], _ = _ask(lst.port, lst.token, {'kind': 'exec', 'code': '1+1'})
        t = threading.Thread(target=client)
        t.start()
        assert lst.pump_until(lambda: not t.is_alive(), 300), 'client did not finish'
        assert res['status']['ok'] and res['read']['ok'], res
        assert len(res['read']['value']['meshes'][str(handle(b))]['tris']) == 12
        assert threads and all(threads), 'pymxs ran off the main thread'
        bridge = json.loads(res['bridge']['value'])
        assert bridge['ok'] and 'qa.xview' in bridge['result']['checks'], bridge
        assert res['exec']['error'].startswith('forbidden'), res['exec']
        lat = sorted(res['lat'])
        return {'status_s': round(res['status_s'], 4), 'gate_read_median_s': round(lat[len(lat) // 2], 4),
                'gate_read_max_s': round(lat[-1], 4), 'bridge_check_run_s': round(res['bridge_s'], 3),
                'max_queue_wait_s': round(lst.stats['max_queue_wait'], 4), 'served': lst.stats['served']}
    finally:
        lst.stop()


def edits(tool, mode, preview, nodes, options):
    return agr.edits_100(tool, mode, preview, nodes, options)


def scene_k4():
    fresh()
    body = box('BODY_Brick_001', 4, 3, 6, (0, 0, 0), 'body')
    a = rt.Box(name='SM_Odd_Main', width=4, length=1, height=3)
    a.pos = rt.Point3(12, 0, 0)
    b2 = rt.Box(width=1, length=4, height=3)
    b2.pos = rt.Point3(10.5, 1.5, 0)
    rt.convertToMesh(a)
    rt.meshop.attach(a, b2)
    out = box('SM_Decor_Main', 1, 1, 1, (20, 0, 0), 'decor', 'DECOR_main')
    return body, a, out


def _ref(n):
    return {'host': 'max', 'doc': 'untitled', 'handle': handle(n), 'name': str(n.name)}


def _wait_daemon(lst, proc, timeout=120):
    path = OUT / 'registry' / 'daemon-{}.json'.format(os.getpid())
    end = time.time() + timeout
    while time.time() < end:
        lst.pump()
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding='utf-8'))
            except ValueError:
                pass
        if proc.poll() is not None:
            raise RuntimeError('daemon exited: ' + (OUT / 'daemon.log').read_text(encoding='utf-8')[-2000:])
        time.sleep(0.05)
    raise RuntimeError('daemon did not register')


def request_scenario():
    body, odd, out = scene_k4()
    jobs = OUT / 'jobs' / 'SYN'
    opt = {'task': 'mark the openings of BODY_Brick_001', 'job_dir': str(jobs), 'project_id': 'SYN',
           'repo': str(ROOT)}
    pv = edits('agent.request', 'preview', None, [body, odd], opt)
    assert pv['status'] == 'pass' and pv['plan']['request_id'] == 'r001', pv
    ap = edits('agent.request', 'apply', pv, [body, odd], None)
    folder = Path(ap['plan']['folder'])
    req_path = folder / 'request.json'
    assert all((folder / f).is_file() for f in ('request.json', 'REQUEST.md', 'command.txt', 'baseline.json',
                                               'snapshot.fbx'))
    assert rt.LayerManager.getLayerFromName('AGENT_r001') is not None
    sha = hashlib.sha256((folder / 'snapshot.fbx').read_bytes()).hexdigest()
    req = json.loads(req_path.read_text(encoding='utf-8'))
    assert req['snapshot']['sha256'] == sha
    v = subprocess.run([PY, '-c', 'import json,sys,jsonschema;jsonschema.validate(json.load(open(sys.argv[1],'
                        'encoding="utf-8")),json.load(open(sys.argv[2],encoding="utf-8")));print("valid")',
                        str(req_path), str(ROOT / 'schemas' / 'AgentRequest.schema.json')],
                       capture_output=True, text=True, timeout=120)
    assert v.stdout.strip() == 'valid', v.stderr[-1500:]
    env = dict(os.environ, AGR_MCP_UNSAFE='1', PYTHONPATH=str(ROOT / 'src'), AGR_MCP_DATA_DIR=str(OUT / 'mcpdata'),
               AGR_MCP_AUDIT=str(OUT / 'audit.jsonl'), AGR_MCP_LOCK_DIR=str(OUT / 'locks'))
    env.pop('VIRTUAL_ENV', None)
    lst = agr_listener.Listener().start()
    log = open(OUT / 'daemon.log', 'w', encoding='utf-8')
    daemon = subprocess.Popen([PY, '-m', 'agr_mcp.max_side.agr_daemon', '--max-pid', str(os.getpid()), '--profile',
                               'modeller'], cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    scen = None
    try:
        t0 = time.time()
        d = _wait_daemon(lst, daemon)
        daemon_s = time.time() - t0
        refs = OUT / 'refs.json'
        refs.write_text(json.dumps({'body': _ref(body), 'odd': _ref(odd), 'outside': _ref(out)}), encoding='utf-8')
        press = OUT / 'press'
        report = OUT / 'agent-sim-k4.json'
        scen = subprocess.Popen([PY, str(ROOT / 'evals' / 'agent-sim-k4' / 'run.py'), '--url', d['url'], '--token',
                                 d['token'], '--request', str(req_path), '--refs', str(refs), '--press-dir',
                                 str(press), '--out', str(report)], cwd=str(ROOT), env=env,
                                stdout=open(OUT / 'scenario.log', 'w', encoding='utf-8'), stderr=subprocess.STDOUT)
        pressed = []
        end = time.time() + 900
        while scen.poll() is None and time.time() < end:
            lst.pump()
            if press.is_dir():
                for f in press.glob('*.press'):
                    pid = f.stem
                    ack = press / (pid + '.ack')
                    if not ack.exists():
                        agr_gate.confirm(pid)  # the human's «Применить», inside this Max
                        ack.write_text('ok', encoding='utf-8')
                        pressed.append(pid[:12])
            time.sleep(0.01)
        if scen.poll() is None:
            scen.kill()
            raise RuntimeError('scenario timed out')
        scenario_s = time.time() - t0 - daemon_s
        rep = json.loads(report.read_text(encoding='utf-8'))
        assert rep['passed'], [r for r in rep['rows'] if not r['passed']]
    finally:
        daemon.terminate()
        try:
            daemon.wait(20)
        except subprocess.TimeoutExpired:
            daemon.kill()
        log.close()
        lst.stop()
    prev = edits('agent.accept', 'preview', None, None, {'request': str(req_path)})
    assert prev['plan']['verdict'] == 'accept', prev
    acc = edits('agent.accept', 'apply', prev, None, None)
    layers = {str(n.name): str(n.layer.name) for n in rt.objects}
    assert (folder / acc['plan']['accepted']).is_file()
    hidden_src = [str(n.name) for n in rt.objects if str(n.layer.name) == 'AGENT_r001_SOURCE' and n.isHidden]
    journal = [json.loads(x) for x in (folder / 'journal.jsonl').read_text(encoding='utf-8').splitlines()]
    scene_journal = sorted((OUT / 'journal').glob('*.jsonl'))
    actors = sorted({json.loads(x)['actor'] for p in scene_journal for x in p.read_text(encoding='utf-8')
                     .splitlines()})
    return {'request': {'files': sorted(os.listdir(folder)), 'snapshot_sha256': sha, 'schema': 'valid'},
            'daemon_start_s': round(daemon_s, 2), 'scenario_s': round(scenario_s, 2), 'presses': pressed,
            'eval_rows': [(r['check'], r['passed']) for r in rep['rows']], 'latency_s': rep['latency_s'],
            'accept': {'status': acc['status'], 'done': acc['plan']['done'], 'ambiguous': acc['plan']['ambiguous']},
            'layers_after': layers, 'hidden_originals': hidden_src,
            'request_journal': [(x['tool'], x['status']) for x in journal], 'journal_actors': actors}


def accept_reject():
    fresh()
    body = box('BODY_Brick_002', 4, 3, 6, (0, 0, 0), 'body')
    out = box('SM_Decor2_Main', 1, 1, 1, (20, 0, 0), 'decor', 'DECOR_main')
    opt = {'task': 'probe the reject path', 'job_dir': str(OUT / 'jobs' / 'SYN2'), 'project_id': 'SYN2',
           'repo': str(ROOT)}
    pv = edits('agent.request', 'preview', None, [body], opt)
    ap = edits('agent.request', 'apply', pv, [body], None)
    req_path = Path(ap['plan']['folder']) / 'request.json'
    lay = rt.LayerManager.getLayerFromName('AGENT_r001')
    p = rt.Point(name='OPEN_001', pos=rt.Point3(1, 0, 1.5))
    rt.setUserProp(p, 'agr_role', 'opening')
    rt.setUserProp(p, 'agr_opening', OPENING)
    lay.addNode(p)
    out.pos = rt.Point3(25, 0, 0)  # someone changed an object outside the agent layer
    prev = edits('agent.accept', 'preview', None, None, {'request': str(req_path)})
    assert prev['plan']['verdict'] == 'reject' and prev['status'] == 'fail', prev
    codes = sorted({f['code'] for o in prev['objects'] for f in o['findings']})
    acc = edits('agent.accept', 'apply', prev, None, None)
    rejected = [str(n.name) for n in rt.objects if str(n.layer.name) == 'AGENT_r001_REJECTED' and n.isHidden]
    q = (req_path.parent / 'questions.md').read_text(encoding='utf-8')
    assert rejected == ['OPEN_001'] and 'outside_changed' in q, (rejected, q[:300])
    return {'codes': codes, 'rejected': rejected, 'status': acc['status'], 'question': q.strip()[:300]}


def polygon_u():
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import build_scene
    rows = []
    for button in ('agent.request', 'agent.accept'):
        doc = json.loads((ROOT / 'test-polygon' / 'expected' / (button + '.json')).read_text(encoding='utf-8'))
        scene = doc['objects'][0]['scene']
        fresh()
        build_scene.build(scene, texture_dir=str(OUT / 'textures'))
        nodes = [rt.getNodeByName(o['name']) for o in doc['objects']]
        assert all(n is not None for n in nodes), doc['objects']
        try:
            rep = agr.edits_100(doc['tool'], 'preview', None, nodes, doc.get('options'))
            got = {o['name']: sorted({f['code'] for f in o['findings']}) for o in rep['objects']}
            err = None
        except Exception as exc:  # noqa: BLE001
            got, err = {}, '{}: {}'.format(type(exc).__name__, exc)
        for o in doc['objects']:
            if err:
                actual, codes = 'error', []
            else:
                codes = got.get(o['name'], [])
                actual = 'fail' if codes else 'pass'
            rows.append({'station': doc['station'], 'button': button, 'name': o['name'], 'expect': o['expect'],
                         'actual': actual, 'codes': codes, 'ok': actual == o['expect'] and codes == o['codes'],
                         'error': err[:200] if err else None})
    assert all(r['ok'] for r in rows), rows
    return rows


check('gate_real', gate_real)
if 'gate_real' in summary['checks']:
    check('one_undo_record', one_undo_record)
check('units_cm', units_cm)
check('listener_queue', listener_queue)
check('request_scenario', request_scenario)
check('accept_reject', accept_reject)
check('polygon_U', polygon_u)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('AGENT_BRIDGE_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native agent bridge failed: see summary.json'
