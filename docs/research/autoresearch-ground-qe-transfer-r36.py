"""Read-only paired-profile replay of the pinned standing #35 scorer."""
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REV = 'ec403b83113d89f6b8a98f648421a33a17819603'
SOURCE = 'docs/research/autoresearch-ground-short-edges-r35'
COPIES = Path('C:/x/ground-etalons/standing-32')
CAP = 240
PAIRS = dict(Skolkovo='A2', COD='A3', Donskoy='A4')


def blob(path):
    return subprocess.check_output(['git', 'show', f'{REV}:{path}'], cwd=ROOT)


def sums(path):
    return {name.lstrip('*'): h for h, name in (line.split() for line in path.read_text().splitlines() if line.strip())}


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    private = out / 'temp'
    private.mkdir()
    for k in ('TEMP', 'TMP', 'TMPDIR'):
        os.environ[k] = str(private)
    source = blob(SOURCE + '.py')
    prev = json.loads(blob(SOURCE + '.json'))
    r = {'__file__': str(ROOT / (SOURCE + '.py')), '__name__': 'r35'}
    exec(compile(source, r['__file__'], 'exec'), r)
    from dt_ai.core.blender_runner import BLENDER_VERSION, DEFAULT_BLENDER, run_blender
    from tools.materials.npm_atlas_udim import read_obj

    g, sha = r['xview_gate'], r['sha']
    rows, pairs = {}, {}
    report = dict(hypothesis='inconclusive', variant='unchanged #35 Qe, paired VPM transfer',
                  scorer_revision=REV, rows=rows, pairs=pairs)
    start = time.monotonic()

    def checks(p, inject=False):
        runs = [r['measure'](p) for _ in range(3)]
        q = [z['Qe'] for z in runs]
        c = runs[0]
        rigid = r['measure'](r['rigid']([p])[0])
        row = dict(clean_runs=runs, median_Qe=statistics.median(q), spread=max(q)-min(q), rigid=rigid,
                   stable=all(z == c for z in runs) and all(c[k] == rigid[k] for k in ('E', 'T')))
        if inject:
            pp, moved = r['inject'](p)
            z = r['measure'](pp)
            row['injected'] = dict(moved=moved, **z, delta_E=z['E']-c['E'], ok=z['E']-c['E'] >= 25 and z['T'] == c['T'])
        return row

    def fresh(name, profile, anchor, hashes):
        key = f'{name}_{profile}'
        fbx = COPIES / f'{key}_Ground.fbx'
        row = rows[key] = dict(source=fbx.as_posix(), input_sha256=hashes[fbx.name])
        if sha(fbx) != row['input_sha256']:
            raise ValueError(f'Input hash mismatch: {key}')
        dest = out / key
        dest.mkdir()
        staged = dest / fbx.name
        staged.write_bytes(fbx.read_bytes())
        if sha(staged) != row['input_sha256']:
            raise ValueError(f'Staging mismatch: {key}')
        blend, npz, meta = (dest / n for n in ('scene.blend', 'parts.npz', 'manifest.json'))

        def timeout():
            return min(45, CAP - (time.monotonic()-start))

        run_blender(r['HARNESS'] / 'fbx_to_blend.py', [staged, blend], outputs=[blend], cwd=dest,
                    executable=DEFAULT_BLENDER, timeout=timeout(), log_path=dest / 'import.log')
        dump = run_blender(g.DUMP_SCRIPT, [blend, npz, meta], outputs=[npz], output_json=meta, cwd=dest,
                           executable=DEFAULT_BLENDER, timeout=timeout(), log_path=dest / 'dump.log')
        parts, units = g.to_metres(g.load_npz(npz), dump)
        path = dest / 'metres.npz'
        g.save_npz(path, parts)
        row.update(dump=f'{key}/metres.npz', dump_sha256=sha(path), manifest_sha256=sha(meta),
                   census=[p.name for p in parts], units=units, blender=dump.get('blender'), dropped=dump.get('dropped'))
        if row['blender'] != BLENDER_VERSION or row['dropped']:
            raise ValueError(f'Unexpected Blender version or dropped parts: {key}')
        if sha(staged) != row['input_sha256'] or sha(fbx) != row['input_sha256']:
            raise ValueError(f'Input changed after readback: {key}')
        row.update(checks(r['ground'](path), inject=True))
        if profile == 'NPM':
            row['parity35'] = row['clean_runs'] == prev['rows'][anchor]['clean_runs']

    try:
        hashes = sums(COPIES / 'SHA256SUMS.txt')
        report['fbx_manifest_sha256'] = sha(COPIES / 'SHA256SUMS.txt')
        for name, anchor in PAIRS.items():
            for profile in ('NPM', 'VPM'):
                fresh(name, profile, anchor, hashes)
            pairs[name] = rows[f'{name}_VPM']['median_Qe'] - rows[f'{name}_NPM']['median_Qe']
            if name == 'Skolkovo':
                report['first_pair_seconds'] = time.monotonic()-start
                if 4 * report['first_pair_seconds'] > CAP:
                    raise TimeoutError('First pair exceeds frozen budget projection')
        for name, digest in sums(r['HARNESS'] / 'dumps.sha256').items():
            key = name.split('_')[0]
            path = r['DUMPS'] / name
            if sha(path) != digest:
                raise ValueError(f'Dump hash mismatch: {key}')
            row = rows[key] = checks(r['ground'](path), inject=key == 'A1')
            row.update(dump=path.as_posix(), dump_sha256=digest,
                       parity35=row['clean_runs'] == prev['rows'][key]['clean_runs'] and
                       row['median_Qe'] == prev['rows'][key]['median_Qe'])
        if len(rows) != 19 or time.monotonic()-start > CAP:
            raise TimeoutError('Frozen series incomplete or over budget')
        accepted = {k: v for k, v in rows.items() if not k.startswith('F')}
        a = max(v['median_Qe'] for v in accepted.values())
        f = min(v['median_Qe'] for k, v in rows.items() if k.startswith('F'))
        sep = f > a and f >= 2 * max(1, a)
        parity = all(v.get('parity35', True) for v in rows.values())
        stable = all(v['stable'] and v.get('injected', {}).get('ok', True) for v in rows.values())
        fires = [k for k, v in accepted.items() if v['clean_runs'][0]['E'] > 0]
        report.update(max_accepted=a, min_sil13=f, margin=f-a, separation=sep, parity=parity, stability=stable,
                      accepted_control_fires=fires or 'not measured',
                      hypothesis='confirmed' if sep and parity and stable else 'refuted')
        if report['hypothesis'] == 'confirmed':
            p, h = r['CORE']
            if sha(p) != h:
                raise ValueError('Core OBJ hash mismatch')
            mesh, _ = read_obj(p)
            reps = [r['measure'](r['Part'](p.stem, r['np'].asarray(mesh.vertices), mesh.faces, r['np'].zeros(3)))
                    for _ in range(3)]
            report['core'] = dict(path=p.as_posix(), sha256=h, clean_runs=reps,
                                  median_Qe=statistics.median(z['Qe'] for z in reps),
                                  parity35=reps == prev['core']['clean_runs'])
    except (OSError, ValueError, RuntimeError) as exc:
        report['unavailable'] = getattr(exc, 'envelope', str(exc))
    finally:
        report['seconds'] = time.monotonic()-start
        (out / 'receipt.json').write_bytes((json.dumps(report, indent=2) + '\n').encode())
    print({k: v for k, v in report.items() if k != 'rows'}, flush=True)
    return 0 if report['hypothesis'] != 'inconclusive' else 2


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1]).resolve()))
