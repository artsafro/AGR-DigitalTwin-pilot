"""new-case: driver for the #808 native UI run: lock, install bundle, interactive Max, uninstall, leftovers.

python tests/max_tools/drive_agr_tools_ui_native.py --bundle <AGR-Tools zip> --out <new dir> [--version 2026]
Uses the shared live-Max lock (%LOCALAPPDATA%/Temp/agr-3dsmax-live.lock); refuses when 3dsmax.exe runs.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = Path(os.environ['LOCALAPPDATA']) / 'Temp' / 'agr-3dsmax-live.lock'


def snapshot(folder):
    if not folder.exists():
        return {}
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def ini_has_section(ini):
    if not ini.is_file():
        return False
    raw = ini.read_bytes()
    text = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8', errors='replace')
    return '[agrtools]' in text.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bundle', type=Path, default=None, help='AGR-Tools.zip; omit with --no-bundle')
    ap.add_argument('--no-bundle', action='store_true', help='quit baseline without AGR Tools (#868)')
    ap.add_argument('--steps', default=None, help="AGR_UI_STEPS for the run script ('' = none); default all")
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--version', default='2026')
    ap.add_argument('--timeout', type=int, default=1200)
    ap.add_argument('--keep-ini', action='store_true', help='leave [AGRTools] for the next session (phase 1)')
    ap.add_argument('--light', action='store_true', help='start Max in the Light theme (clrx patched, restored)')
    ap.add_argument('--leave-area', default='', help='dock area the session leaves the panel in (1/2/4/8)')
    ap.add_argument('--expect-area', default='', help='dock area the previous session left')
    a = ap.parse_args()
    if a.no_bundle == (a.bundle is not None):
        ap.error('give exactly one of --bundle and --no-bundle')
    a.out.mkdir(parents=True, exist_ok=False)
    running = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq 3dsmax.exe'], capture_output=True).stdout.decode('ascii', 'replace')
    if '3dsmax.exe' in running:
        sys.exit('3dsmax.exe is running; refuse')
    if LOCK.exists():
        info = json.loads(LOCK.read_text(encoding='utf-8'))
        if time.time() < info.get('until', 0) and info.get('card') != 't_9f5c4106':
            sys.exit('live lock busy: ' + str(info))
    LOCK.write_text(json.dumps({'card': 't_9f5c4106', 'until': time.time() + a.timeout + 300, 'pid': os.getpid()}))
    spec = importlib.util.spec_from_file_location('b', ROOT / 'tools/max/build_agr_tools.py')
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    plugins = Path(os.environ['APPDATA']) / 'Autodesk' / 'ApplicationPlugins'
    ini = Path(os.environ['LOCALAPPDATA']) / 'Autodesk' / '3dsMax' / '{} - 64bit'.format(a.version) / 'ENU' / '3dsMax.ini'
    log = {'bundle_sha256': hashlib.sha256(a.bundle.read_bytes()).hexdigest() if a.bundle else None,
           'plugins_dir': str(plugins), 'steps': a.steps}
    try:
        plugins.mkdir(parents=True, exist_ok=True)
        before = snapshot(plugins)
        log['ini_section_before'] = ini_has_section(ini)
        if a.no_bundle and (plugins / b.BUNDLE).exists():
            raise FileExistsError('--no-bundle but installed: ' + str(plugins / b.BUNDLE))
        log['installed'] = 0 if a.no_bundle else len(b.install_bundle(a.bundle, plugins))
        exe = Path(r'C:\Program Files\Autodesk\3ds Max {}\3dsmax.exe'.format(a.version))
        env = dict(os.environ, AGR_UI_OUT=str(a.out), AGR_UI_LEAVE_AREA=a.leave_area,
                   AGR_UI_EXPECT_AREA=a.expect_area)
        if a.steps is not None:
            env['AGR_UI_STEPS'] = a.steps
        clrx = ini.parent / 'en-US' / 'UI' / 'MaxStartUI.clrx'
        if a.light:
            backup = clrx.read_bytes()
            (a.out / 'MaxStartUI.clrx.backup').write_bytes(backup)
            light = exe.parent / 'en-US' / 'UI' / 'ame-light.clrx'  # Max's own Light colour file
            clrx.write_bytes(light.read_bytes())
            log['theme_patched'] = str(clrx)
        t0 = time.time()
        proc = subprocess.run([str(exe), '-silent', '-U', 'PythonHost',
                               str(ROOT / 'tests/max_tools/run_agr_tools_ui_native.py')],
                              env=env, timeout=a.timeout)
        log['max_exit'] = proc.returncode
        log['max_seconds'] = round(time.time() - t0, 1)
        log['ini_section_after_run'] = ini_has_section(ini)
    finally:
        if a.light and (a.out / 'MaxStartUI.clrx.backup').exists():
            clrx.write_bytes((a.out / 'MaxStartUI.clrx.backup').read_bytes())
            log['theme_restored'] = clrx.read_bytes().count(b'<appFrameColorTheme value="0" />') == 1
        removed = (b.uninstall_bundle(plugins, [] if a.keep_ini else [ini])
                   if (plugins / b.BUNDLE).exists() and not a.no_bundle else [])
        log['ini_cleaned'] = removed
        after = snapshot(plugins)
        log['leftover_files'] = sorted(set(after) ^ set(before))
        log['changed_files'] = sorted(k for k in set(after) & set(before) if after[k] != before[k])
        log['ini_section_after_uninstall'] = ini_has_section(ini)
        LOCK.unlink(missing_ok=True)
        (a.out / 'install_log.json').write_text(json.dumps(log, indent=1), encoding='utf-8')
        print(json.dumps(log))


if __name__ == '__main__':
    main()
