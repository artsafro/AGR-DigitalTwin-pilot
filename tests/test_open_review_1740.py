"""new-case: `agr open-review FILE` - the `review-scene` skeleton stage (#1740).

Acceptance table (every row is a test):
- FBX stage output, Max free             -> copy C:/x/review-<job>/<stem>_review_v001.fbx, NEW Max 2026 process -> test_fbx_opens_copy_in_new_max
- max-live lock held (live, unexpired)   -> Blender fallback, lock bytes untouched                       -> test_max_busy_falls_back_to_blender
- unreadable lock body                   -> counted as held (Blender), never removed                     -> test_unreadable_lock_is_busy
- stale lock (dead pid)                  -> Max, the lock is NOT reclaimed by open-review                -> test_stale_lock_is_not_reclaimed
- Max executable missing                 -> Blender fallback with the reason                             -> test_max_missing_falls_back_to_blender
- .max scene while Max busy              -> error, nothing written, nothing launched                     -> test_native_max_scene_when_busy_fails_closed
- occupied Max import-script name        -> error, foreign file unchanged, nothing launched              -> test_occupied_import_script_refused
- explicit --app max while busy          -> error (no new Max next to a held live session)               -> test_explicit_max_refused_when_busy
- .blend                                 -> Blender only                                                 -> test_blend_goes_to_blender
- repeat on same stage                   -> v001, v002; earlier copies unchanged                         -> test_repeat_gets_next_version
- never opens the original (brute force) -> launched args never name the source, source sha unchanged    -> test_never_opens_original_probe
- empty/partial/unsupported/no consent/bad job/missing -> error, no write, no launch                       -> test_fail_closed
- prepare-only                           -> copy made, nothing launched, no consent needed               -> test_prepare_only
- fresh-process CLI `agr open-review`    -> exit 0 prepared JSON / exit 1 on missing file                -> test_cli_fresh_process
- skeleton: review-scene calls agr open-review in oks-npm and oks-vpm, not a gap -> test_skeleton_*
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/open_review_scene.py'
FBX = b'Kaydara FBX Binary  \x00\x1a\x00' + b'synthetic fbx payload'
MAXH = bytes.fromhex('d0cf11e0a1b11ae1') + b'0000synthetic max'
BLEND = b'BLENDER-v501synthetic blend'


def load():
    spec = importlib.util.spec_from_file_location('open_review_scene_1740', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def env(tmp_path, monkeypatch):
    locks = tmp_path / 'locks'
    locks.mkdir()
    monkeypatch.setenv('AGR_MCP_LOCK_DIR', str(locks))
    exes = {}
    for app in ('max', 'blender'):
        exe = tmp_path / f'{app}.exe'
        exe.write_bytes(b'fixture')
        exes[app] = exe
    module = load()
    calls = []
    monkeypatch.setattr(module, 'subprocess', SimpleNamespace(  # module-local: real subprocess stays usable
        DEVNULL=subprocess.DEVNULL, Popen=lambda args, **kw: calls.append(args) or SimpleNamespace(pid=4242)))
    return SimpleNamespace(m=module, calls=calls, exes=exes, locks=locks, root=tmp_path / 'x', tmp=tmp_path)


def stage(env, name='63A_Stage2_v001.fbx', data=FBX, job='63A'):
    path = env.tmp / 'jobs' / job / 'stage2' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def run(env, source, **kw):
    kw.setdefault('approved', True)
    return env.m.review(source, root=env.root, executables=env.exes, **kw)


def hold_lock(env, body=None):
    lock = env.locks / 'agr-3dsmax-live.lock'
    lock.write_text(json.dumps(body if body is not None else
                               {'pid': os.getpid(), 'until': time.time() + 600, 'card': 'artem'}))
    return lock


def launched_text(args):
    """The launch command plus the Max startup script it runs (what the new process will open)."""
    text = ' '.join(args)
    if '-U' in args:
        text += '\n' + Path(args[args.index('-U') + 2]).read_text(encoding='utf-8')
    return text


def test_fbx_opens_copy_in_new_max(env):
    source = stage(env)
    before = sha(source)
    result = run(env, source)
    out = env.root / 'review-63A' / '63A_Stage2_v001_review_v001.fbx'
    assert result['status'] == 'launched' and result['app'] == 'max' and result['path'] == str(out.resolve())
    assert out.read_bytes() == source.read_bytes() and sha(source) == before
    assert len(env.calls) == 1 and env.calls[0][0] == str(env.exes['max'].resolve())
    assert env.calls[0][1:3] == ['-U', 'MAXScript'] and '-mxs' not in env.calls[0]   # -mxs quits Max after the string
    text = launched_text(env.calls[0])
    assert str(source) not in text and f'importFile @"{out.resolve()}" #noPrompt' in text
    assert result['original'] == str(source.resolve()) and result['acceptance'] == 'not_measured'


def test_occupied_import_script_refused(env):
    source = stage(env)
    folder = env.root / 'review-63A'
    folder.mkdir(parents=True)
    script = folder / '63A_Stage2_v001_review_v001.open.ms'
    script.write_text('-- someone else\n')
    with pytest.raises(ValueError, match='occupied'):
        run(env, source)
    assert script.read_text() == '-- someone else\n' and env.calls == []
    assert sorted(p.name for p in folder.iterdir()) == [script.name]


def test_max_busy_falls_back_to_blender(env):
    lock = hold_lock(env)
    raw = lock.read_bytes()
    result = run(env, stage(env))
    assert result['app'] == 'blender' and 'max-live lock held' in result['app_reason']
    assert env.calls[0][0] == str(env.exes['blender'].resolve()) and '--disable-autoexec' in env.calls[0]
    assert lock.read_bytes() == raw


def test_unreadable_lock_is_busy(env):
    lock = env.locks / 'agr-3dsmax-live.lock'
    lock.write_bytes(b'\x00garbage')
    assert run(env, stage(env))['app'] == 'blender'
    assert lock.read_bytes() == b'\x00garbage'


def test_stale_lock_is_not_reclaimed(env):
    lock = hold_lock(env, {'pid': 999999999, 'until': time.time() + 600})
    raw = lock.read_bytes()
    assert run(env, stage(env))['app'] == 'max'
    assert lock.read_bytes() == raw


def test_max_missing_falls_back_to_blender(env):
    env.exes['max'] = env.tmp / 'missing' / '3dsmax.exe'
    result = run(env, stage(env))
    assert result['app'] == 'blender' and 'not found' in result['app_reason']


def test_native_max_scene_when_busy_fails_closed(env):
    hold_lock(env)
    source = stage(env, 'scene_v003.max', MAXH)
    with pytest.raises(ValueError, match='max-live lock held'):
        run(env, source)
    assert not env.root.exists() and env.calls == []


def test_explicit_max_refused_when_busy(env):
    hold_lock(env)
    with pytest.raises(ValueError, match='max-live lock held'):
        run(env, stage(env), app='max')
    assert not env.root.exists() and env.calls == []


def test_blend_goes_to_blender(env):
    result = run(env, stage(env, 'body_v005.blend', BLEND))
    assert result['app'] == 'blender' and env.calls[0][-1] == result['path']
    with pytest.raises(ValueError, match='blender'):
        run(env, stage(env, 'body_v006.blend', BLEND), app='max')


def test_repeat_gets_next_version(env):
    source = stage(env)
    first = Path(run(env, source)['path'])
    first_bytes = first.read_bytes()
    second = Path(run(env, source)['path'])
    assert first.name.endswith('_review_v001.fbx') and second.name.endswith('_review_v002.fbx')
    assert first.read_bytes() == first_bytes


def test_never_opens_original_probe(env):
    rng = random.Random(1740)
    kinds = [('.fbx', FBX), ('.blend', BLEND), ('.max', MAXH)]
    checked = 0
    for i in range(40):
        suffix, data = rng.choice(kinds)
        busy = rng.random() < 0.5 and suffix != '.max'
        lock = env.locks / 'agr-3dsmax-live.lock'
        if busy:
            hold_lock(env)
        elif lock.exists():
            lock.unlink()
        if rng.random() < 0.3:   # the source already sits in the review folder (copy of a copy)
            source = env.root / 'review-63A' / f'in{i}_review_v00{rng.randint(1, 3)}{suffix}'
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(data)
            job = '63A'
        else:
            source, job = stage(env, f's{i}_v001{suffix}', data, job=f'J{i % 3}'), None
        before = sha(source)
        env.calls.clear()
        result = run(env, source, job=job)
        args = launched_text(env.calls[0])
        src, out = source.resolve(), Path(result['path'])
        assert out != src and str(src) not in args and src.as_posix() not in args
        assert (str(out) in args or out.as_posix() in args) and sha(source) == before and sha(out) == before
        checked += 1
    assert checked == 40


@pytest.mark.parametrize('case', ['empty', 'partial', 'unsupported', 'nosuffix', 'no-consent',
                                  'bad-job', 'dotdot-job', 'no-job', 'missing', 'wrong-header'])
def test_fail_closed(env, case):
    kw = {}
    if case == 'empty':
        source = stage(env, data=b'')
    elif case == 'partial':
        source = stage(env, data=b'Kaydara')
    elif case == 'unsupported':
        source = stage(env, 'x_v001.obj', b'v 0 0 0\n' * 4)
    elif case == 'nosuffix':
        source = stage(env, 'x_v001', FBX)
    elif case == 'no-consent':
        source, kw = stage(env), {'approved': False}
    elif case == 'bad-job':
        source, kw = stage(env), {'job': 'a/b'}
    elif case == 'dotdot-job':
        source, kw = stage(env), {'job': '..'}
    elif case == 'no-job':
        source = env.tmp / 'loose' / 'x_v001.fbx'
        source.parent.mkdir()
        source.write_bytes(FBX)
    elif case == 'missing':
        source = env.tmp / 'jobs' / '63A' / 'none.fbx'
    else:
        source = stage(env, data=BLEND)
    with pytest.raises((ValueError, OSError)):
        run(env, source, **kw)
    assert not env.root.exists() and env.calls == []


def test_prepare_only(env):
    source = stage(env)
    result = run(env, source, approved=False, prepare_only=True)
    assert result['status'] == 'prepared' and env.calls == []
    assert Path(result['path']).read_bytes() == source.read_bytes()


def test_cli_fresh_process(env):
    source = stage(env)
    cmd = [sys.executable, '-m', 'dt_ai.cli.agr', 'open-review', str(source), '--prepare-only',
           '--review-root', str(env.root)]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result['status'] == 'prepared' and Path(result['path']).parent == (env.root / 'review-63A').resolve()
    missing = subprocess.run(cmd[:4] + [str(env.tmp / 'jobs/63A/none.fbx'), '--prepare-only', '--review-root',
                                        str(env.root)], capture_output=True, text=True, timeout=120)
    assert missing.returncode == 1 and json.loads(missing.stdout)['status'] == 'error'


def test_agr_help_lists_open_review(capsys):
    agr = importlib.import_module('dt_ai.cli.agr')
    assert agr.main(['--help']) == 0
    assert 'open-review' in capsys.readouterr().out


SK = json.loads((ROOT / 'docs/agents/skeletons.json').read_text(encoding='utf-8'))


def test_skeleton_review_scene_calls_open_review():
    st = SK['stages']['review-scene']
    assert st['gap'] is None and 'agr open-review' in st['calls']
    assert 'tools/open_review_scene.py' in st['owners'] and 'review' in st['entry_defs']


@pytest.mark.parametrize('cell', ['oks-npm', 'oks-vpm'])
def test_skeleton_review_scene_in_oks_cells_before_checker(cell):
    stages = SK['cells'][cell]['stages']
    assert stages.index('review-scene') == stages.index('validate') + 1
    assert stages.index('review-scene') < stages.index('checker')


def test_skeleton_doc_rows():
    doc = (ROOT / 'docs/agents/SKELETONS-stages.md').read_text(encoding='utf-8')
    gaps = (ROOT / 'docs/agents/SKELETONS.md').read_text(encoding='utf-8').split('## Пробелы', 1)[1]  # #1895 index
    assert '`review-scene`' not in gaps
    for cell in ('### `oks-vpm`', '### `oks-npm`'):
        section = doc.split(cell, 1)[1].split('\n### ', 1)[0]
        assert '`review-scene`' in section and 'agr open-review' in section
