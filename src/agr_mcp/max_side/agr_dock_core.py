"""new-case: logic of the Claude dock inside 3ds Max (#1024 branch U, agent.dock), stdlib only, no Qt.

The dock (agr_dock.py, a thin QDockWidget) runs the local `claude` CLI through QProcess:
    claude -p --input-format stream-json --output-format stream-json --verbose [--resume <session>]
           --mcp-config <daemon config> --strict-mcp-config --tools "" --allowedTools mcp__agr__*
           --permission-mode default
with cwd = the pilot clone. Only the agr-mcp tools exist for the model: no Bash/Read/Edit (built-in tools off with
`--tools ""`), no other MCP server (`--strict-mcp-config`), and the daemon's profile never has agr_exec_unsafe
(`dev` is refused here). The scene context comes from agr_agent_context, not from the prompt.
Auth: `local` (default) = the owner's logged-in Claude Code; `api_key` = the CLI reads ANTHROPIC_API_KEY from the
environment of Max (for colleagues); the key is never written to the repo, the scene or the dock files.

This module: the command line, the stdin message, a parser of the stream-json lines into dock events (text, tool
cards with preview_id, result, session), and the per-document session file for `--resume` after a Max restart.
"""
import json
import os
import re
import tempfile

DOCK_PROFILES = ('observer', 'operator', 'modeller')
AUTH = ('local', 'api_key')
PREVIEW_RE = re.compile(r'\b([0-9a-f]{64})\b')
TOOL_PREFIX = 'mcp__agr__'


def dock_dir(env=None):
    env = os.environ if env is None else env
    base = env.get('AGR_MCP_REGISTRY_DIR')
    if base:
        return os.path.join(os.path.dirname(base.rstrip('\\/')), 'dock')
    return os.path.join(env.get('LOCALAPPDATA') or tempfile.gettempdir(), 'agr-mcp', 'dock')


def command(exe, mcp_config_path, session=None, model=None):
    """argv of the CLI (list; QProcess takes program + args, no shell)."""
    argv = [exe, '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
            '--mcp-config', mcp_config_path, '--strict-mcp-config', '--tools', '',
            '--allowedTools', TOOL_PREFIX + '*', '--permission-mode', 'default']
    if session:
        if not re.match(r'^[A-Za-z0-9-]{8,80}$', str(session)):
            raise ValueError('bad session id ' + repr(session))
        argv += ['--resume', str(session)]
    if model:
        argv += ['--model', str(model)]
    return argv


def environment(base, auth='local'):
    """Environment of the CLI process: `local` drops ANTHROPIC_API_KEY so the owner's login is used; `api_key`
    keeps it (it must already be set for Max); nothing is ever added from the repo or the scene."""
    if auth not in AUTH:
        raise ValueError('auth must be one of {}: {!r}'.format(AUTH, auth))
    env = dict(base)
    if auth == 'local':
        env.pop('ANTHROPIC_API_KEY', None)
    elif not env.get('ANTHROPIC_API_KEY'):
        raise ValueError('auth=api_key needs ANTHROPIC_API_KEY in the environment of 3ds Max')
    env.pop('AGR_MCP_UNSAFE', None)
    return env


def check_profile(profile):
    if profile not in DOCK_PROFILES:
        raise ValueError('the dock runs only {} (never dev / agr_exec_unsafe): {!r}'.format(DOCK_PROFILES, profile))
    return profile


def user_message(text):
    """One stdin line of --input-format stream-json."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('empty message')
    return json.dumps({'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'text', 'text': text}]}},
                      ensure_ascii=False) + '\n'


def write_mcp_config(config, folder=None):
    folder = folder or dock_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'mcp-config-{}.json'.format(os.getpid()))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f)
    return path


# ---- sessions (resume after a Max restart) ----------------------------------------------------------------------
def _sessions_path(folder=None):
    return os.path.join(folder or dock_dir(), 'sessions.json')


def load_session(doc, folder=None):
    try:
        with open(_sessions_path(folder), encoding='utf-8') as f:
            data = json.load(f)
        return data.get(os.path.normcase(doc or 'untitled')) if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save_session(doc, session, folder=None):
    path = _sessions_path(folder)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[os.path.normcase(doc or 'untitled')] = session
    tmp = path + '.partial'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, sort_keys=True)
    os.replace(tmp, path)
    return path


# ---- stream-json -> dock events ---------------------------------------------------------------------------------
class Stream:
    """Feed stdout lines of the CLI; get events:
    ('session', id) | ('text', str) | ('tool', {id, name, input}) | ('tool_result', {id, text, preview_id, status,
    is_error}) | ('result', {is_error, text, session}) | ('error', str)."""

    def __init__(self):
        self.session = None
        self.cards = {}
        self._buf = ''

    def feed_bytes(self, data):
        self._buf += data if isinstance(data, str) else data.decode('utf-8', errors='replace')
        out = []
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            out.extend(self.feed(line))
        return out

    def feed(self, line):
        line = line.strip()
        if not line:
            return []
        try:
            ev = json.loads(line)
        except ValueError:
            return [('error', 'not JSON from the CLI: ' + line[:200])]
        if not isinstance(ev, dict):
            return []
        kind = ev.get('type')
        out = []
        sid = ev.get('session_id')
        if sid and sid != self.session:
            self.session = sid
            out.append(('session', sid))
        if kind == 'assistant':
            for block in (ev.get('message') or {}).get('content') or ():
                if block.get('type') == 'text' and block.get('text'):
                    out.append(('text', block['text']))
                elif block.get('type') == 'tool_use':
                    card = {'id': block.get('id'), 'name': block.get('name'), 'input': block.get('input') or {}}
                    self.cards[card['id']] = card
                    out.append(('tool', card))
        elif kind == 'user':
            for block in (ev.get('message') or {}).get('content') or ():
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    out.append(('tool_result', tool_result(block, ev.get('tool_use_result'))))
        elif kind == 'result':
            out.append(('result', {'is_error': bool(ev.get('is_error')), 'text': ev.get('result') or '',
                                   'session': sid}))
        return out


def tool_result(block, extra=None):
    """A tool_result block -> {id, text, preview_id, status, is_error}; the preview id comes from the envelope."""
    content = block.get('content')
    if isinstance(content, list):
        text = '\n'.join(c.get('text', '') for c in content if isinstance(c, dict))
    else:
        text = str(content or '')
    structured = None
    if isinstance(extra, dict):
        structured = extra.get('structuredContent') or extra
    pid = None
    status = None
    if isinstance(structured, dict):
        pid = structured.get('preview_id')
        status = structured.get('status')
    if pid is None:
        m = re.search(r'preview_id ([0-9a-f]{64})', text)
        pid = m.group(1) if m else None
    if status is None:
        m = re.match(r'\S+: (\w+)', text)
        status = m.group(1) if m else None
    return {'id': block.get('tool_use_id'), 'text': text, 'preview_id': pid, 'status': status,
            'is_error': bool(block.get('is_error'))}


def card_title(card):
    name = str(card.get('name', ''))
    short = name[len(TOOL_PREFIX):] if name.startswith(TOOL_PREFIX) else name
    inp = card.get('input') or {}
    what = inp.get('op') or ''
    ref = inp.get('ref') or {}
    return '{} {} {}'.format(short, what, ref.get('name', '') if isinstance(ref, dict) else '').strip()


def applicable(name, result):
    """A card gets «Применить» only for a held D108 preview."""
    return name.endswith('agr_agent_op_preview') and bool(result.get('preview_id')) and result.get('status') == 'pass'
