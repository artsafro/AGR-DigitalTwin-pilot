"""new-case: OBSERVE loop for the master mesh quality score (#1616) - proposes and logs, never retains.

  uv run python tools/qa/mesh_quality_observe.py SRC.blend RUN_DIR [--angles 80,60,45,30]

Round 0 measures the source; each next round runs the candidate hook
``tools/blender/split_welded_parts_candidate.py`` with one parameter on a copy, measures it with
tools/qa/mesh_quality_score.py (same zones) and KEEPS it as the incumbent only if the score
improves. Every round is appended to RUN_DIR/observe-log.jsonl with what it WOULD change in the
skeleton (a body-stage ``after`` hook, docs/agents/SKELETONS.md); nothing is written to the
skeleton, the job or the source. Retaining a change is a normal PR + review (OBSERVE rule).
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools' / 'qa'))
import mesh_quality_score as mqs  # noqa: E402  (report: docs/research/mesh-quality-1616/REPORT.md)

CORNERS = [[-17.5, -8.2, -12.5, -3.2], [-17.5, 3.5, -12.5, 8.5]]   # KPP1 SW / NW corner posts (#1563 sheet)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('run_dir')
    ap.add_argument('--angles', default='80,60,45,30')
    ap.add_argument('--blender', default=None)
    a = ap.parse_args(argv)
    src, run = Path(a.src).resolve(), Path(a.run_dir).resolve()
    if run.exists():
        raise SystemExit('run dir exists; use a new one: ' + str(run))
    if run == src.parent or src.parent in run.parents:
        raise SystemExit('run dir inside the source directory')
    run.mkdir(parents=True)
    before = sha(src)
    from dt_ai.core.blender_runner import blender_executable
    log = run / 'observe-log.jsonl'
    base = mqs.run(src, run / 'round-00-score.json', zones=CORNERS, blender=a.blender)
    best = {'round': 0, 'score': base['score'], 'master': str(src)}
    rows = [{'round': 0, 'candidate': 'baseline (no hook)', 'score': base['score'], 'components': base['components'],
             'kept': True, 'master': str(src), 'master_sha256': before}]
    for i, angle in enumerate([float(x) for x in a.angles.split(',')], start=1):
        out = run / f'round-{i:02d}'
        cmd = [blender_executable(a.blender), '--background', '--factory-startup', '--disable-autoexec',
               '--python', str(ROOT / 'tools' / 'blender' / 'split_welded_parts_candidate.py'), '--', str(src), str(out), repr(angle)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        fbx = out / 'master.fbx'
        if proc.returncode != 0 or not fbx.is_file():
            rows.append({'round': i, 'candidate': f'split_welded_parts angle={angle}', 'error': proc.stderr[-400:],
                         'kept': False})
            continue
        rep = mqs.run(fbx, run / f'round-{i:02d}-score.json', zones=CORNERS, blender=a.blender)
        kept = rep['score'] > best['score']
        if kept:
            best = {'round': i, 'score': rep['score'], 'master': str(fbx)}
        rows.append({'round': i, 'candidate': f'split_welded_parts angle={angle}', 'score': rep['score'],
                     'delta_vs_baseline': round(rep['score'] - base['score'], 3), 'components': rep['components'],
                     'hook': json.loads((out / 'hook.json').read_text(encoding='utf-8'))['split_edges'],
                     'kept': kept, 'master': str(fbx), 'master_sha256': sha(fbx),
                     'would_change': ('skeletons.json jobs/KPP1 hooks += {"script": "hooks/split_welded_parts.py", '
                                      f'"stage": "body", "point": "after"}} with angle_deg={angle}')})
    if sha(src) != before:
        raise SystemExit('source changed during the loop')
    with log.open('x', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    (run / 'incumbent.json').write_text(json.dumps(best, indent=2), encoding='utf-8')
    for r in rows:
        print(r['round'], r['candidate'], r.get('score'), 'KEEP' if r['kept'] else 'discard')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
