"""new-case: host driver for the polygon visual guide (interactive 3ds Max, real screenshots).

    python test-polygon/build/guide_drive.py --scene <polygon_all.max> --out <new dir> [--version 2026]

Refuses when any 3dsmax.exe runs (never touches a user's session) or the shared live-Max
lock is held; writes the lock for its run and removes it after. Uses the AGR Tools that
is installed for the user (no install/uninstall, the user's bundle is not touched).
Opens a COPY of the scene; the copy and the screenshots go to --out only.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from dt_ai.core.max_env import max_child_env  # noqa: E402

HERE = Path(__file__).resolve().parent
LIVE_LOCK = Path(os.environ.get('LOCALAPPDATA', '')) / 'Temp' / 'agr-3dsmax-live.lock'
SESSION_LOCK = Path(os.environ.get('LOCALAPPDATA', '')) / 'Temp' / 'agr-max-session.lock'


def max_running():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq 3dsmax.exe'], capture_output=True).stdout
    return b'3dsmax.exe' in out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--version', default='2026')
    ap.add_argument('--timeout', type=int, default=900)
    a = ap.parse_args(argv)
    scene = a.scene.resolve()
    out = a.out.resolve()
    if not scene.is_file():
        sys.exit('scene not found: ' + str(scene))
    if out == scene.parent or scene.is_relative_to(out):
        sys.exit('out must be a new folder that does not hold the scene')
    out.mkdir(parents=True, exist_ok=False)
    if max_running():
        sys.exit('3dsmax.exe is running; refuse (close Max, then rerun)')
    for lock in (LIVE_LOCK, SESSION_LOCK):
        if lock.exists():
            sys.exit('lock held: {} {}'.format(lock, lock.read_text(encoding='utf-8', errors='replace')[:200]))
    copy = out / ('guide_' + scene.name)
    shutil.copy2(scene, copy)
    LIVE_LOCK.write_text(json.dumps({'card': os.environ.get('HERMES_KANBAN_TASK', 'manual'),
                                     'until': time.time() + a.timeout + 300, 'pid': os.getpid()}))
    try:
        exe = Path(r'C:\Program Files\Autodesk\3ds Max {}\3dsmax.exe'.format(a.version))
        env = dict(max_child_env(), AGR_GUIDE_SCENE=str(copy), AGR_GUIDE_OUT=str(out))
        t0 = time.time()
        try:
            proc = subprocess.run([str(exe), '-silent', '-U', 'PythonHost', str(HERE / 'guide_inside.py')],
                                  env=env, timeout=a.timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 'timeout'
        shots = json.loads((out / 'shots.json').read_text(encoding='utf-8')) if (out / 'shots.json').is_file() else []
        print(json.dumps({'max_exit': code, 'seconds': round(time.time() - t0, 1), 'shots': len(shots),
                          'out': str(out)}))
        return 0 if shots else 1
    finally:
        LIVE_LOCK.unlink(missing_ok=True)


if __name__ == '__main__':
    sys.exit(main())
