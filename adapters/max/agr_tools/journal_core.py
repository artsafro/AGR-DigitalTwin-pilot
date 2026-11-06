"""new-case: AGR Tools 1.0 (#1024) journal of panel actions (contract K1), stdlib only. Stub of branch 0; owned by branch F (improve/issue-1024-passport).

Branch 0 ships the minimal working `append` so the runtime hook journals every call of edits_080 / edits_090 /
edits_100 and of MCP from day one (one panel/MCP journal, BRANCH0-U-L12-ADDENDUM). Branch F owns the rest: the copy
into jobs/<ID>/journal.jsonl when the passport is saved, the tail in the passport, the weekly summary (tail 1.x).
One line per run: ts, tool, mode, status, counts, preview_sha, duration, actor (panel | mcp | agent), doc.
File: %LOCALAPPDATA%\\AGRTools\\journal\\<sha1(scene)>.jsonl (AGR_JOURNAL_DIR overrides the folder, for tests).
"""
import hashlib
import json
import os
import time

ACTORS = ('panel', 'mcp', 'agent')
FIELDS = ('ts', 'tool', 'mode', 'status', 'counts', 'preview_sha', 'duration', 'actor', 'doc')


def journal_dir():
    base = os.environ.get('AGR_JOURNAL_DIR')
    if base:
        return base
    return os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'AGRTools', 'journal')


def scene_key(scene):
    if not scene or scene in ('<untitled>', 'untitled'):
        return 'untitled'
    return hashlib.sha1(os.path.normcase(os.path.abspath(scene)).encode('utf-8')).hexdigest()


def journal_path(scene, folder=None):
    return os.path.join(folder or journal_dir(), scene_key(scene) + '.jsonl')


def record(tool, mode, status, counts=None, preview_sha=None, duration=0.0, actor='panel', doc=None, ts=None):
    if actor not in ACTORS:
        raise ValueError('journal actor must be one of {}: {!r}'.format(ACTORS, actor))
    return {'ts': ts or time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'tool': str(tool), 'mode': str(mode),
            'status': str(status), 'counts': dict(counts or {}), 'preview_sha': preview_sha,
            'duration': round(float(duration), 3), 'actor': actor, 'doc': doc or 'untitled'}


def append(rec, scene=None, folder=None):
    """Append one JSON line (opened in append mode; a line is written in one call). Returns the file path."""
    missing = [f for f in FIELDS if f not in rec]
    if missing:
        raise ValueError('journal record lacks ' + ', '.join(missing))
    path = journal_path(scene if scene is not None else rec.get('doc'), folder)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n'
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line)
    return path


def tail(scene=None, n=20, folder=None):
    path = journal_path(scene, folder)
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


# ---- branch F: the copy into the project and the tail of the passport (K1) ------------------------------------
def read_lines(path):
    """(records, bad line numbers) of a journal file; a missing file is ([], [])."""
    if not os.path.isfile(path):
        return [], []
    good, bad = [], []
    with open(path, encoding='utf-8') as f:
        for i, line in enumerate(f.read().splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                bad.append(i)
                continue
            if isinstance(rec, dict) and all(k in rec for k in FIELDS):
                good.append(rec)
            else:
                bad.append(i)
    return good, bad


def copy_to(scene, dest, folder=None):
    """Copy the scene's journal into the project (jobs/<ID>/journal.jsonl) when the passport is saved.

    The project copy only grows: its existing lines stay first and in order, the panel lines it does not hold yet
    are appended in their order (a scene saved under a new name has a new panel journal; both end up in the
    project). Written to `<dest>.partial`, then replaced. Returns {'path', 'lines', 'added', 'tail'}
    (tail: the last 20 records for the passport)."""
    src = journal_path(scene, folder)
    new = []
    if os.path.isfile(src):
        with open(src, encoding='utf-8') as f:
            new = [x for x in f.read().splitlines() if x.strip()]
    old = []
    if os.path.isfile(dest):
        with open(dest, encoding='utf-8') as f:
            old = [x for x in f.read().splitlines() if x.strip()]
    have = set(old)
    added = [x for x in new if x not in have]
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    tmp = dest + '.partial'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(''.join(x + '\n' for x in old + added))
    os.replace(tmp, dest)
    records, _bad = read_lines(dest)
    return {'path': dest, 'lines': len(records), 'added': len(added), 'tail': records[-20:]}
