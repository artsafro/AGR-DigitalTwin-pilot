"""new-case: build or open the AGR Tools polygon and compare every shipped button with expected/.

Exit code is the number of mismatches (`count`). A known-bug row is not a mismatch and does
not change the exit code: `report.json` field `known_bug` and the summary line count it
apart. Missing expected entry, an unmapped button, an empty result, NaN/Inf, not_run and a
produced pass row that was not run are mismatches. Output, report and temp must not resolve
to the sources. Nothing here deletes an input.

    python test-polygon/run_polygon.py --out <new dir> [--version 2024]
    python test-polygon/run_polygon.py --out <new dir> --actual <actual.json>

The Max half goes through hermes dcc_batch.py (the shared session lock). Live Max is optional
for the offline tests; this script is what a later run uses.

This runner does not install or remove AGR-Tools.bundle. A future install must wrap the
copy under %APPDATA%\\Autodesk\\ApplicationPlugins with polygon_core.preserve_user_bundle
so the operator's bytes are moved aside and restored in finally, never deleted.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

POLY = Path(__file__).resolve().parent
ROOT = POLY.parent
sys.path.insert(0, str(POLY))

import polygon_core as core

DCC = Path('C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py')


def default_out():
    drive = Path('G:/Мой диск/AGR-evidence/test-polygon')
    if Path('G:/').exists():
        return drive
    return Path('C:/x/test-polygon')


def _jobs():
    jobs = []
    for path in sorted((POLY / 'expected').glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        if not doc.get('shipped'):
            continue
        scenes = []
        for obj in doc['objects']:
            if obj['scene'] not in scenes:
                scenes.append(obj['scene'])
        for scene in scenes:
            jobs.append((doc['button'], scene))
    return jobs


def _geojson_as_object(name, report):
    """Turn a plan-level GeoJSON report into one object row named by the file."""
    if not isinstance(report, dict) or report.get('status') == 'error':
        return report
    codes = core._scene_codes(report)
    if not isinstance(codes, list):
        return report
    return {'status': 'fail' if codes else 'pass', 'objects': [
        {'name': name, 'findings': [{'code': code, 'ids': [], 'detail': ''} for code in codes]}]}


def compare_actual(actual):
    """actual: {'runs': [{button, scene, tool, report, ...}, ...]}. Unmapped button is an error."""
    if not isinstance(actual, dict) or not isinstance(actual.get('runs'), list):
        raise ValueError('actual.json has no runs list')
    mismatches = []
    seen = set()
    seen_produced = set()
    for run in actual['runs']:
        button = run.get('button')
        if button == '*':
            mismatches.append({'kind': 'error', 'button': 'build', 'scene': run.get('scene'),
                               'name': '', 'detail': str(run.get('report'))})
            continue
        try:
            doc = core.load_expected(button)
        except KeyError as exc:
            raise KeyError('unmapped button: ' + str(button)) from exc
        scene = run.get('scene')
        seen.add((button, scene, run.get('tool')))
        produced = run.get('produced')
        if produced:
            seen_produced.add((button, scene, produced))
            expected = [o for o in doc['objects'] if o['scene'] == scene and o.get('produced') == produced]
            report = core.bind_produced(expected, run.get('report'))
            for item in core.compare_report(expected, report):
                item['button'] = button
                item['scene'] = scene
                mismatches.append(item)
            if run.get('apply_expected') and run.get('apply_status') != run['apply_expected']:
                mismatches.append({'kind': 'apply', 'button': button, 'scene': scene, 'name': '',
                                   'detail': 'apply expected {} got {}'.format(
                                       run['apply_expected'], run.get('apply_status'))})
            continue
        if run.get('apply_expected'):
            got = run.get('apply_status')
            if got != run['apply_expected']:
                mismatches.append({'kind': 'apply', 'button': button, 'scene': scene, 'name': '',
                                   'detail': 'apply expected {} got {}'.format(run['apply_expected'], got)})
            continue
        expected = [o for o in doc['objects'] if o['scene'] == scene and not o.get('produced')]
        report = run.get('report')
        if run.get('tool') == 'geojson':
            names = run.get('names') or []
            if len(names) == 1:
                expected = [o for o in expected if o['name'] == names[0]]
                report = _geojson_as_object(names[0], report)
        for item in core.compare_report(expected, report):
            item['button'] = button
            item['scene'] = scene
            mismatches.append(item)
    for button, scene in _jobs():
        pressed = any(run.get('button') == button and run.get('scene') == scene for run in actual['runs'])
        if not pressed:
            mismatches.append({'kind': 'missing', 'button': button, 'scene': scene, 'name': '',
                               'detail': 'button was not pressed'})
            continue
        doc = core.load_expected(button)
        kinds = sorted({o['produced'] for o in doc['objects'] if o['scene'] == scene and o.get('produced')})
        for kind in kinds:
            if (button, scene, kind) not in seen_produced:
                detail = 'produced {} was not run'.format(kind)
                if kind == 'export_readback':
                    detail = 'produced export_readback was not run (readback)'
                mismatches.append({'kind': 'missing', 'button': button, 'scene': scene, 'name': '',
                                   'detail': detail})
    return mismatches


def live_codes(actual):
    """(button, scene, name) -> codes from actual.json. Produced copies use expected names."""
    live = {}
    if not isinstance(actual, dict):
        return live
    for run in actual.get('runs') or []:
        button, scene = run.get('button'), run.get('scene')
        if not button or button == '*':
            continue
        try:
            doc = core.load_expected(button)
        except KeyError:
            continue
        report = run.get('report')
        produced = run.get('produced')
        if produced:
            expected = [o for o in doc['objects'] if o['scene'] == scene and o.get('produced') == produced]
            report = core.bind_produced(expected, report)
        codes = core.actual_codes(report)
        if not codes:
            continue
        for name, got in codes.items():
            live[(button, scene, name)] = got
    return live


def _table(mismatches, jobs, live=None):
    return core.render_table(core.group_runs(jobs, mismatches, live), mismatches)


def main(argv=None):
    parser = argparse.ArgumentParser(description='AGR Tools test polygon')
    parser.add_argument('--out', type=Path, default=None)
    parser.add_argument('--version', default='2024')
    parser.add_argument('--actual', type=Path, default=None, help='compare this actual.json and do not start Max')
    parser.add_argument('--no-max', action='store_true', help='write textures and FBX only')
    args = parser.parse_args(argv)
    out = (args.out or default_out()).resolve()
    report_path = out / 'report.json'
    temp_path = out / 'temp'
    core.check_paths(POLY, out, report_path, temp_path)
    out.mkdir(parents=True, exist_ok=True)
    core.generate_outputs(out)
    if args.no_max and args.actual is None:
        print(json.dumps({'out': str(out), 'max': False}))
        return 0
    if args.actual is None:
        if not DCC.is_file():
            raise SystemExit('shared DCC lock runner is missing: ' + str(DCC))
        env = dict(os.environ, AGR_POLYGON_OUT=str(out), AGR_POLYGON_ROOT=str(ROOT))
        proc = subprocess.run([sys.executable, str(DCC), 'max', '--file',
                               str(POLY / 'build' / 'run_inside_max.py'), '--version', args.version,
                               '--out', str(out / 'max.log')], env=env)
        actual_path = out / 'actual.json'
        if proc.returncode != 0 or not actual_path.is_file():
            mismatches = [{'kind': 'empty', 'button': '*', 'scene': '', 'name': '',
                           'detail': 'Max produced no actual.json (exit {})'.format(proc.returncode)}]
            return _finish(out, mismatches, _jobs(), None)
        actual = json.loads(actual_path.read_text(encoding='utf-8'))
    else:
        actual = json.loads(args.actual.read_text(encoding='utf-8'))
    mismatches = compare_actual(actual)
    return _finish(out, mismatches, _jobs(), live_codes(actual))


def _known_count(grouped):
    return sum(1 for base in grouped for spec in base['stations'] for row in spec['rows'] if row.get('known_bug'))


def _finish(out, mismatches, jobs, live):
    """Write report.json and table.txt. Exit code is the mismatch count, not known_bug."""
    grouped = core.group_runs(jobs, mismatches, live)
    known = _known_count(grouped)
    payload = {
        'schema': 2, 'mismatches': mismatches, 'count': len(mismatches),
        'known_bug': known, 'bases': grouped,
    }
    (out / 'report.json').write_text(json.dumps(payload, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (out / 'table.txt').write_text(core.render_table(grouped, mismatches), encoding='utf-8')
    print('mismatches {} known_bug {}'.format(len(mismatches), known))
    return len(mismatches)


if __name__ == '__main__':
    sys.exit(main())
