"""new-case: registry of live 3ds Max instances with the AGR listener, and of agr-mcp daemons (#1024 branch U).

One file per Max instance: <dir>/max-<pid>.json {pid, port, token, max_version, doc, started, listener}; one file
per daemon: <dir>/daemon-<max pid>.json {pid, port, url, token, profile, started}. <dir> is
%LOCALAPPDATA%/agr-mcp/instances (AGR_MCP_REGISTRY_DIR overrides). Files are created exclusively and removed by
their owner; an entry whose pid is dead is stale and ignored (and removed by `prune`).

Selection (mcp-review §3.4, agr-mcp.md "instance"): the pinned pid (AGR_MCP_MAX_PID / argument) or, when exactly one
live instance exists, that one. Several live instances without a pin -> `instance_ambiguous`; none ->
`host_unavailable`. Never the newest one by guess. Stdlib only: the listener inside Max imports this file too.
"""
import json
import os
import tempfile
import time


class RegistryError(Exception):
    """str() starts with a machine code: host_unavailable, instance_ambiguous, busy."""

    def __init__(self, code, text):
        super().__init__(code + ': ' + text)
        self.code = code


def folder(env=None):
    env = os.environ if env is None else env
    if env.get('AGR_MCP_REGISTRY_DIR'):
        return env['AGR_MCP_REGISTRY_DIR']
    base = env.get('LOCALAPPDATA') or tempfile.gettempdir()
    return os.path.join(base, 'agr-mcp', 'instances')


def alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _path(kind, pid, env=None):
    return os.path.join(folder(env), '{}-{}.json'.format(kind, int(pid)))


def write(kind, pid, entry, env=None, exclusive=True):
    """Create the entry file (exclusive: a live entry of the same pid refuses with busy)."""
    path = _path(kind, pid, env)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = json.dumps(dict(entry, pid=int(entry.get('pid', pid)), kind=kind), sort_keys=True).encode('utf-8')
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0))
        except FileExistsError:
            old = read_file(path)
            owner = (old or {}).get('owner_pid', (old or {}).get('pid'))
            if exclusive and old and alive(owner) and attempt == 0 and int(owner) != os.getpid():
                raise RegistryError('busy', '{} for pid {} already registered by live pid {}: {}'.format(
                    kind, pid, owner, path)) from None
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        return path
    raise RegistryError('busy', 'cannot create ' + path)


def remove(kind, pid, env=None):
    try:
        os.remove(_path(kind, pid, env))
    except OSError:
        pass


def read_file(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def entries(kind='max', env=None, check=alive):
    """Live entries of a kind, oldest first."""
    base = folder(env)
    out = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return out
    for name in names:
        if not (name.startswith(kind + '-') and name.endswith('.json')):
            continue
        data = read_file(os.path.join(base, name))
        if data and check(data.get('owner_pid', data.get('pid'))):
            out.append(data)
    return sorted(out, key=lambda d: d.get('started', 0))


def prune(env=None, check=alive):
    base = folder(env)
    gone = []
    try:
        names = os.listdir(base)
    except OSError:
        return gone
    for name in names:
        if not name.endswith('.json'):
            continue
        path = os.path.join(base, name)
        data = read_file(path)
        if data is None or not check(data.get('owner_pid', data.get('pid'))):
            try:
                os.remove(path)
                gone.append(name)
            except OSError:
                pass
    return gone


def select(pin=None, env=None, check=alive):
    """The Max instance to talk to: the pinned pid, or the only live one."""
    env = os.environ if env is None else env
    pin = pin or env.get('AGR_MCP_MAX_PID') or None
    live = entries('max', env, check)
    if pin:
        for e in live:
            if int(e['pid']) == int(pin):
                return e
        raise RegistryError('host_unavailable', 'no live AGR listener in Max pid {} (open the AGR dock or run '
                            'agentbridge_max.listener_start() in that Max)'.format(pin))
    if not live:
        raise RegistryError('host_unavailable', 'no 3ds Max with the AGR listener is running')
    if len(live) > 1:
        raise RegistryError('instance_ambiguous', 'several Max instances with the AGR listener: pids {}; pin one '
                            'with AGR_MCP_MAX_PID'.format([e['pid'] for e in live]))
    return live[0]


def now():
    return time.time()
