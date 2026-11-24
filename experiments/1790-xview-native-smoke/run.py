"""Reproduce #1790 and verify #1798 using serialized dcc_batch sessions only."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BATCH = Path('C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py')
WORK = Path(os.environ['TEMP']) / 'agr-3dsmax-t_14809b3f'
EVIDENCE = ROOT / 'experiments/1790-xview-native-smoke/results.json'


def snapshot(paths):
    result = {}
    for root in paths:
        for p in sorted(root.rglob('*')):
            if p.is_file():
                s = p.stat()
                result[str(p.relative_to(WORK))] = {
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                    'size': s.st_size, 'mtime_ns': s.st_mtime_ns,
                }
    return result


def batch(script, label, env=None):
    out = WORK / (label + '.json')
    command = [sys.executable, str(BATCH), 'max', '--version', '2026',
               '--card', 't_14809b3f', '--file', str(script), '--out', str(out)]
    p = subprocess.run(command, env=env, capture_output=True, text=True, timeout=1900)
    if p.returncode == 3:
        raise RuntimeError('Max busy after lock wait; no bypass')
    if not out.exists():
        raise RuntimeError(p.stdout[-1500:] + p.stderr[-1500:])
    return p.returncode, json.loads(out.read_text(encoding='utf-8'))


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    inputs = WORK / 'inputs'
    inputs.mkdir(exist_ok=True)
    scene = inputs / 'synthetic.max'
    prep = WORK / 'prepare.ms'
    prep.write_text('resetMaxFile #noPrompt\nunits.systemType = #millimeters\n'
                    'units.systemScale = 1\n'
                    'o = box name:"synthetic_box" width:100 length:100 height:100\n'
                    'convertToPoly o\n'
                    f'saveMaxFile @"{scene.as_posix()}" quiet:true\n'
                    'format "SYNTHETIC_READY version=% units=% scale=% faces=% verts=%\\n" '
                    '(maxVersion()) units.systemType units.systemScale '
                    '(polyop.getNumFaces o) (polyop.getNumVerts o)\n', encoding='utf-8')
    code, setup = batch(prep, 'setup')
    assert code == 0 and 'SYNTHETIC_READY' in setup['log'], setup
    baseline = WORK / 'baseline.ms'
    baseline.write_bytes(subprocess.check_output(
        ['git', 'show', 'd453175c^:tools/qa/xview_dump.ms'], cwd=ROOT))
    current = ROOT / 'tools/qa/xview_dump.ms'
    records = []
    for implementation, source, cases in [
        ('baseline', baseline, ['valid']),
        ('merged', current, ['absent', 'partial', 'valid']),
    ]:
        for case in cases:
            for repeat in range(3):
                label = f'{implementation}-{case}-{repeat+1}'
                case_dir = WORK / label
                output, stage = case_dir / 'output', case_dir / 'stage'
                output.mkdir(parents=True, exist_ok=False)
                stage.mkdir()
                if case != 'absent':
                    jobs = '#nonce:native1790\n'
                    jobs += (f'box|{scene.as_posix()}|synthetic_box|plain||\n'
                             if case == 'valid' else 'box|partial\n')
                    (output / 'jobs.txt').write_text(jobs, encoding='utf-8')
                for name in ['box.json', 'report.jsonl', 'done.txt', 'failed.txt']:
                    (output / name).write_text('STALE_SENTINEL_' + name, encoding='ascii')
                (stage / 'sentinel.txt').write_text('NO_STAGE_WRITE', encoding='ascii')
                before = snapshot([inputs, output, stage])
                env = dict(os.environ, XVIEW_OUT=str(output), XVIEW_TEMP=str(stage))
                code, result = batch(source, label, env)
                after = snapshot([inputs, output, stage])
                errors = [line.strip() for line in result['log'].splitlines()
                          if 'XVIEW_' in line]
                expected = ('XVIEW_UNSUPPORTED_MAX_VERSION' if implementation == 'merged'
                            else 'Operation is not supported on this platform')
                record = dict(implementation=implementation, case=case, repeat=repeat+1,
                              wrapper_exit=code, native_exit=result['exit_code'],
                              seconds=result['seconds'], errors=errors,
                              unchanged=before == after, inventory=before,
                              expected_diagnostic=expected,
                              passed=code != 0 and result['exit_code'] != 0
                              and expected in result['log'] and before == after)
                records.append(record)
                print(json.dumps({k: v for k, v in record.items() if k != 'inventory'}), flush=True)
                EVIDENCE.write_text(json.dumps(dict(setup=setup, records=records), indent=2), encoding='utf-8')
    summary = {}
    for implementation, case in sorted({(r['implementation'], r['case']) for r in records}):
        rows = [r for r in records if r['implementation'] == implementation and r['case'] == case]
        summary[implementation + '-' + case] = dict(
            median_seconds=statistics.median(r['seconds'] for r in rows),
            passed=sum(r['passed'] for r in rows), runs=len(rows))
    EVIDENCE.write_text(json.dumps(dict(setup=setup, records=records, summary=summary), indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)
    assert all(r['passed'] for r in records), 'Native contract failed'


if __name__ == '__main__':
    main()
