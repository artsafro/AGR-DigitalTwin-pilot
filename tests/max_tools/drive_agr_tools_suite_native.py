"""new-case: driver of the #860 native smoke: optional Light theme (Max's own ame-light.clrx), restored after.

python tests/max_tools/drive_agr_tools_suite_native.py --pkg <extracted MZP>/agr_tools --out <new dir>
       [--version 2026] [--light]
Runs run_agr_tools_suite_native.py through the shared headless runner (dcc_batch.py, its session lock);
the user's MaxStartUI.clrx is backed up into --out and written back in `finally` (byte-identical check).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from dt_ai.core.max_env import max_child_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DCC = Path('C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--version', default='2026')
    ap.add_argument('--light', action='store_true')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    ui = Path(os.environ['LOCALAPPDATA']) / 'Autodesk' / '3dsMax' / '{} - 64bit'.format(a.version) / 'ENU' / 'en-US' / 'UI'
    clrx = ui / 'MaxStartUI.clrx'
    log = {'version': a.version, 'light': a.light}
    backup = clrx.read_bytes() if clrx.is_file() else None
    try:
        if a.light:
            if backup is None:
                sys.exit('no MaxStartUI.clrx to switch')
            (a.out / 'MaxStartUI.clrx.backup').write_bytes(backup)
            clrx.write_bytes((Path('C:/Program Files/Autodesk') / ('3ds Max ' + a.version) / 'en-US' / 'UI'
                              / 'ame-light.clrx').read_bytes())
        env = dict(max_child_env(), AGR_860_PKG=a.pkg, AGR_860_OUT=str(a.out / 'smoke'))
        proc = subprocess.run([sys.executable, str(DCC), 'max', '--file',
                               str(ROOT / 'tests/max_tools/run_agr_tools_suite_native.py'), '--version', a.version,
                               '--out', str(a.out / 'max.log')], env=env, capture_output=True, timeout=1500)
        log['dcc_exit'] = proc.returncode
    finally:
        if a.light and backup is not None:
            clrx.write_bytes(backup)
            log['clrx_restored'] = hashlib.sha256(clrx.read_bytes()).hexdigest() == hashlib.sha256(backup).hexdigest()
    (a.out / 'drive_log.json').write_text(json.dumps(log, indent=1), encoding='utf-8')
    print(json.dumps(log))


if __name__ == '__main__':
    main()
