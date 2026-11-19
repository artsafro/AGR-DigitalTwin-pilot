"""new-case: reproducible, immutable KPP1 packaging diagnostic run (#1361).

No geometry/DCC edit: verified cold-run bytes are copied into a NEW directory.
Ground and GeoJSON are deliberately NOT fabricated. Diagnostic NPM exits 1.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/derive'))
from export_meta import write_meta

COLD = Path('G:/Мой диск/AGR-evidence/1313-kpp1-cold-run-3')
THUMB = Path('G:/Мой диск/AGR-evidence/1255-kpp1-msk77/site-v004/thumbnail_256.jpg')


def digest(path):
    return hashlib.file_digest(open(path, 'rb'), 'sha256').hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('out', type=Path)
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError(out)
    expected = {}
    for line in (ROOT / 'jobs/KPP1/cold-run-1313/evidence-SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        sha, path = line.split('  ', 1)
        expected[Path(path).resolve()] = sha
    sources = [COLD / 'derive-v001/export/fbx/0000_Kpp_1_01.fbx',
               COLD / 'package-vpm-v001/pkg/SM_Kpp_1.fbx',
               COLD / 'derive-v001/readback.json',
               *sorted((COLD / 'package-vpm-v001/textures').glob('*.png'))]
    # site-1255/evidence-SHA256SUMS.txt, real rendered thumbnail (no invented image).
    expected[THUMB] = 'f4d594d22629304226c3fc7740003d5136251113739a065f6cde93e67351f384'
    for path in [*sources, THUMB]:
        if path not in expected or digest(path) != expected[path]:
            raise ValueError(f'cold-run source missing/stale: {path}')
    out.mkdir(parents=True)
    copies = []

    def copy(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(source, 'rb') as inp, open(target, 'xb') as dest:
            shutil.copyfileobj(inp, dest)
        shutil.copystat(source, target)
        if digest(source) != digest(target):
            raise ValueError(f'copy differs: {source}')
        copies.append({'source': str(source), 'copy': str(target), 'sha256': digest(source)})

    npm = out / 'npm/fbx'
    vpm = out / 'vpm/pkg'
    copy(sources[0], npm / sources[0].name)
    copy(sources[1], vpm / sources[1].name)
    for source in sources[3:]:
        copy(source, out / 'vpm/textures' / source.name)
    copy(THUMB, out / 'vpm/thumbnail_256.jpg')
    readback = json.loads(sources[2].read_text(encoding='utf-8'))
    top = max(m['bounds_m'][1][2] for m in readback['meshes'])
    for profile, pkg, maximum, origin in (
        ('npm', npm, top, str(sources[2]) + ': meshes[].bounds_m maximum Z, cold-run hash verified'),
        ('vpm', vpm, 8.65, 'jobs/KPP1/site-1255/REPORT.md:73; approved R1 model top rounded to 2 decimals; not V013 bounds evidence'),
    ):
        record = {'address': 'Kpp_1', 'h_otn_model_max_z_m': maximum,
                  'thumbnail': str(out / 'vpm/thumbnail_256.jpg'), 'profile': profile,
                  'exported_files': [next(pkg.glob('*.fbx')).name]}
        record['provenance'] = {
            'address': 'cold-run FBX filename; Kpp_1 naming placeholder, legal address unknown (STATE.md:77-78); question: confirm delivery address token',
            'h_otn_model_max_z_m': origin,
            'thumbnail': str(THUMB) + '; copied unchanged; site-v004 REPORT.md:60 real render',
            'profile': 'cold-run-1313/RUN-LOG.md:45; NPM derived vs approved R1 VPM',
            'exported_files': 'verified cold-run-1313/evidence-SHA256SUMS.txt; copied unchanged'}
        write_meta(pkg.parent / 'export_meta.json', record)
        (out / f'{profile}-export_meta.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    runs = []

    def run(label, cmd):
        result = subprocess.run([str(x) for x in cmd], cwd=ROOT, capture_output=True,
                                env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        (out / (label + '.stdout')).write_bytes(result.stdout)
        (out / (label + '.stderr')).write_bytes(result.stderr)
        runs.append({'label': label, 'command': [str(x) for x in cmd], 'exit_code': result.returncode})
        return result

    for profile, fbx in [('npm', npm / sources[0].name), ('vpm', vpm / sources[1].name)]:
        run(profile + '-before', [sys.executable, '-m', 'dt_ai.cli.agr', 'validate', fbx, '--profile', profile, '--json'])
    for label, cmd, expected_exit in (
        ('npm-package', [sys.executable, '-m', 'dt_ai.cli.agr', 'package-npm', npm, '--allow-incomplete'], 1),
        ('vpm-package', [sys.executable, '-m', 'dt_ai.cli.agr', 'package-vpm', vpm, out / 'vpm/textures', '--no-geojson'], 0),
    ):
        result = run(label, cmd)
        if result.returncode != expected_exit:
            raise RuntimeError(f'{label}: exit {result.returncode}, inspect {label}.stderr')
    for profile, target in [('npm', out / 'npm/0000_Kpp_1.zip'), ('vpm', out / 'vpm/SM_Kpp_1.zip')]:
        run(profile + '-after', [sys.executable, '-m', 'dt_ai.cli.agr', 'validate', target, '--profile', profile, '--json'])
    for source in [*sources, THUMB]:
        if digest(source) != expected[source]:
            raise ValueError(f'source changed during run: {source}')
    (out / 'run.json').write_text(json.dumps({'passed': False, 'copies': copies, 'runs': runs}, ensure_ascii=False, indent=2), encoding='utf-8')
    paths = sorted(p for p in out.rglob('*') if p.is_file())
    (out / 'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.relative_to(out).as_posix()}\n' for p in paths), encoding='utf-8')
    print(json.dumps({'out': str(out), 'copied_files': len(copies), 'runs': runs, 'passed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
