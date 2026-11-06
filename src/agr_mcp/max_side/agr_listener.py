"""new-case: the AGR listener inside 3ds Max (#1024 branch U): our own pipe instead of the third-party 3dsmax-mcp.

A background thread serves 127.0.0.1:<ephemeral port>; every request is one JSON line with the instance token (from
the registry file, agr_registry.py) and gets one JSON line back. The socket thread never touches pymxs: work goes into
a queue that the MAIN thread of Max drains (`pump()`, called by a Qt timer in the GUI, or by the caller in batch), as
max_pipe.py did over the 3dsmax-mcp pipe. One job at a time: while a job runs or waits, another write request is
refused at once with `busy` (the daemon serialises its own calls; this guards against any second client).

Kinds (no raw MAXScript unless the listener was started with allow_exec=True for the `dev` profile):
* `status`   - answered by the socket thread: busy, current job id, queue length, doc, pid (the daemon polls it so
               that a lease is never released while Max still works on a timed-out call, mcp-review §2.4.5);
* `bridge`   - max_bridge.call(tool, root_hex, args_hex): every v1/v2 agr-mcp tool, unchanged;
* `gate_read`, `gate_apply` - agr_gate.read / agr_gate.apply on agr_maxhost.MaxGateHost (D108 operations);
* `refused`  - preview ids an apply was refused for (needs_human), for the dock's cards;
* `exec`     - MAXScript text, only with allow_exec (dev profile, never in the dock).
Confirmation of a preview (agr_gate.confirm) is NOT a kind: only code inside this Max process (the dock button) can
confirm.
"""
import hmac
import json
import os
import queue
import secrets
import socket
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agr_gate  # noqa: E402
import agr_registry  # noqa: E402

VERSION = '1.0.0-u1'
MAX_LINE = 64 * 1024 * 1024
KINDS = ('status', 'bridge', 'gate_read', 'gate_apply', 'refused', 'exec')


class Job:
    def __init__(self, req):
        self.req = req
        self.id = str(req.get('id') or secrets.token_hex(6))
        self.done = threading.Event()
        self.answer = None
        self.queued = time.time()
        self.started = None


class Listener:
    def __init__(self, allow_exec=False, host_factory=None, bridge=None, env=None, max_version=None):
        self.allow_exec = bool(allow_exec)
        self.token = secrets.token_hex(16)
        self.env = os.environ if env is None else env
        self.host_factory = host_factory
        self.bridge = bridge
        self.max_version = max_version
        self.jobs = queue.Queue()
        self.current = None
        self.lock = threading.Lock()
        self.sock = None
        self.thread = None
        self.port = None
        self.doc = 'untitled'
        self.stats = {'served': 0, 'refused_busy': 0, 'max_queue_wait': 0.0}
        self._stop = threading.Event()
        self._timer = None

    # -- lifecycle -----------------------------------------------------------------------------------------------
    def start(self, port=0, register=True):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', int(port)))
        s.listen(8)
        s.settimeout(0.2)
        self.sock, self.port = s, s.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, name='agr-listener', daemon=True)
        self.thread.start()
        if register:
            agr_registry.write('max', os.getpid(), self.entry(), self.env)
        return self

    def entry(self):
        return {'pid': os.getpid(), 'port': self.port, 'token': self.token, 'max_version': self.max_version,
                'doc': self.doc, 'started': time.time(), 'listener': VERSION, 'exec': self.allow_exec}

    def stop(self):
        self._stop.set()
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:  # noqa: BLE001
                pass
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        agr_registry.remove('max', os.getpid(), self.env)

    def start_timer(self, interval_ms=30):
        """GUI Max: drain the queue from a Qt timer on the main thread (PySide6 in Max 2025+, PySide2 in 2024)."""
        try:
            from PySide6 import QtCore
        except ImportError:
            from PySide2 import QtCore
        t = QtCore.QTimer()
        t.setInterval(int(interval_ms))
        t.timeout.connect(self.pump)
        t.start()
        self._timer = t
        return t

    # -- socket thread -------------------------------------------------------------------------------------------
    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _addr = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        try:
            conn.settimeout(None)
            req = json.loads(_read_line(conn))
            ans = self.handle(req)
        except Exception as exc:  # noqa: BLE001
            ans = {'ok': False, 'error': 'invalid_request: {}: {}'.format(type(exc).__name__, exc)}
        try:
            conn.sendall((json.dumps(ans, allow_nan=False, default=str) + '\n').encode('utf-8'))
        except OSError:
            pass  # the client went away (timeout); the job result is still kept in stats
        finally:
            conn.close()

    def handle(self, req, wait=True):
        """Socket-thread entry (also used directly by in-process tests)."""
        if not isinstance(req, dict) or not hmac.compare_digest(str(req.get('token', '')), self.token):
            return {'ok': False, 'error': 'forbidden: bad or missing instance token'}
        kind = req.get('kind')
        if kind not in KINDS:
            return {'ok': False, 'error': 'invalid_request: unknown kind ' + repr(kind)}
        if kind == 'status':
            return self.status()
        if kind == 'refused':
            return {'ok': True, 'refused': agr_gate.refused()}
        if kind == 'exec' and not self.allow_exec:
            return {'ok': False, 'error': 'forbidden: exec is off (dev profile only, never in the dock)'}
        with self.lock:
            if self.current is not None or not self.jobs.empty():
                self.stats['refused_busy'] += 1
                cur = self.current.id if self.current else None
                return {'ok': False, 'error': 'busy: Max is running job {}'.format(cur), 'busy': True}
            job = Job(req)
            self.current = job
            self.jobs.put(job)
        if not wait:
            return job
        job.done.wait()
        return job.answer

    def status(self):
        with self.lock:
            cur = self.current
            return {'ok': True, 'busy': cur is not None, 'current': cur.id if cur else None,
                    'queued': self.jobs.qsize(), 'doc': self.doc, 'pid': os.getpid(), 'listener': VERSION,
                    'stats': dict(self.stats)}

    # -- main thread ---------------------------------------------------------------------------------------------
    def pump(self, budget_s=0.0):
        """Run queued jobs on the calling (main) thread. Returns the number of jobs run."""
        n = 0
        end = time.time() + budget_s
        while True:
            try:
                job = self.jobs.get_nowait()
            except queue.Empty:
                break
            job.started = time.time()
            self.stats['max_queue_wait'] = max(self.stats['max_queue_wait'], job.started - job.queued)
            try:
                job.answer = self.run(job.req)
            except Exception as exc:  # noqa: BLE001 - every failure becomes a named error for the client
                job.answer = {'ok': False, 'error': _error_text(exc), 'trace': traceback.format_exc()[-1500:]}
            job.answer.setdefault('job', job.id)
            job.answer['main_thread_s'] = round(time.time() - job.started, 4)
            with self.lock:
                self.current = None
                self.stats['served'] += 1
            job.done.set()
            n += 1
            if time.time() >= end:
                break
        self._refresh_doc()
        return n

    def pump_until(self, predicate, timeout_s=60.0, step_s=0.01):
        """Batch Max (no Qt loop): drain on this thread until predicate() is true."""
        end = time.time() + timeout_s
        while time.time() < end:
            self.pump()
            if predicate():
                return True
            time.sleep(step_s)
        return False

    def _refresh_doc(self):
        try:
            self.doc = self._host().doc()
        except Exception:  # noqa: BLE001
            pass

    def _host(self):
        if self.host_factory is not None:
            return self.host_factory()
        import agr_maxhost
        return agr_maxhost.MaxGateHost()

    def _bridge(self):
        if self.bridge is not None:
            return self.bridge
        import max_bridge
        return max_bridge

    def run(self, req):
        kind = req['kind']
        if kind == 'bridge':
            value = self._bridge().call(str(req['tool']), str(req['root_hex']), str(req['args_hex']))
            return {'ok': True, 'value': value}
        if kind == 'gate_read':
            return {'ok': True, 'value': agr_gate.read(self._host(), req.get('handles') or [],
                                                      req.get('neighbours') or [])}
        if kind == 'gate_apply':
            return {'ok': True, 'value': agr_gate.apply(self._host(), req['plan'], req.get('preview_id'))}
        if kind == 'exec':
            from pymxs import runtime as rt
            return {'ok': True, 'value': str(rt.execute(str(req['code'])))}
        raise ValueError('unknown kind ' + repr(kind))


def _error_text(exc):
    """'<code>: text' for errors that carry a machine code (GateError, BridgeError), else 'Type: text'."""
    code = getattr(exc, 'code', None)
    if code and str(exc).startswith(str(code) + ':'):
        return str(exc)
    return '{}: {}'.format(type(exc).__name__, exc)


def _read_line(conn):
    buf = bytearray()
    while True:
        chunk = conn.recv(65536)
        if not chunk:
            break
        buf += chunk
        if b'\n' in chunk:
            break
        if len(buf) > MAX_LINE:
            raise ValueError('request too large')
    return buf.split(b'\n', 1)[0].decode('utf-8')


_ACTIVE = {}


def start(allow_exec=False, timer=True, **kw):
    """Start (or return) this process's listener. GUI: timer=True drains on the Qt main loop."""
    if _ACTIVE.get('listener') is not None:
        return _ACTIVE['listener']
    try:
        from pymxs import runtime as rt
        version = list(rt.maxVersion())[:3]
    except Exception:  # noqa: BLE001
        version = None
    lst = Listener(allow_exec=allow_exec, max_version=version, **kw).start()
    if timer:
        lst.start_timer()
    _ACTIVE['listener'] = lst
    return lst


def active():
    return _ACTIVE.get('listener')


def stop():
    lst = _ACTIVE.pop('listener', None)
    if lst is not None:
        lst.stop()
