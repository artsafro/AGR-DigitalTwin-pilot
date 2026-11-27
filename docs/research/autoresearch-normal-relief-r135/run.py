"""#135 replay: preflight hashes, 3 fresh render runs, score, frozen verdict, receipt (OBSERVE).

uv run --frozen python docs/research/autoresearch-normal-relief-r135/run.py <new out dir> [--runs 3]
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score  # noqa: E402

BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
EVID = Path('G:/Мой диск/AGR-evidence/1326-stylobate-course-grid')
DESK = Path('C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/build/textures')
BLENDS = {'source': EVID / 'normal-v166/inputs/1326_source_v001.blend',
          'v045': EVID / 'cut-v045/stylobate_cut_candidate_v045.blend',
          'v096': EVID / 'normal-v096/stylobate_two_tiles_textured_v096.blend'}
PINS = {
    BLENDS['v045']: '38979c31de1d23086d7b67078ca5b14343cd3db51c70cf4a89b3b0dd61a7bad6',
    BLENDS['v096']: '070f292765d09756b2d82acffe7e5a5047e16ad9847e081c74bc1d66f02fea58',
    BLENDS['source']: 'e3fdb9193706059fd75bd42819280f140f512c6cc8a206e905b819fc3ce64a18',
    EVID / 'cut-v014/T_1326_Stylo_Diffuse.1001.png': '46b271f2fec85802b9ba54a9fba379c91545794bbd5e3c92f6e57529f0a6192e',
    EVID / 'cut-v014/T_1326_Stylo_Normal.1001.png': '5c5887d426b71c786e8f9784449e36a379a9e07ae451b08eb21a32bd87d2e428',
    EVID / 'normal-v092/T_1326_Stylo_Diffuse.1001.png': '4f5b1cd7abd46bad3465bc127a56b62dcdd640dcdf16f61f7d9731c95e93af4e',
    EVID / 'normal-v092/T_1326_Stylo_Diffuse.1002.png': '78d5a0e6809d49c4a22fff82d9c1132745ecfa27af5e4f96cc01fde503ca83fe',
    EVID / 'normal-v092/T_1326_Stylo_Normal.1001.png': 'a594651923ea7e9f2f82cc6d726f1afb2639a50598ba87055cec55e2cccba38a',
    EVID / 'normal-v092/T_1326_Stylo_Normal.1002.png': 'e191115f2062ef9340354a9b4093b50f3706fb87b9c9f0fa8af044f73202d138',
    DESK / 'T_K3_StyloBrick_Diffuse.png': 'ff846d8e4f97eb9df4f9f1b069cacc5c3f67b86c323945e7c4d379f06e0a884d',
    DESK / 'T_K3_StyloBrick_Normal.png': 'fee4b9729673835c524130eaf562a088d5560322c0e370feb89bb1a8f93b847b',
}
SHOTS = ['straight-wall', 'corner', 'floor-join', 'niche', 'joint-stripe']
CANDS = ['N0', 'v045', 'v096', 'P1', 'P2']


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def preflight():
    bad = {str(p): (sha(p) if p.exists() else 'missing') for p, h in PINS.items()
           if not p.exists() or sha(p) != h}
    if bad:
        raise SystemExit(f'preflight refused: {bad}')
    return {str(p): h for p, h in PINS.items()}


def one_run(out: Path):
    out.mkdir(parents=True)
    t0 = time.perf_counter()
    for kind, blend in BLENDS.items():
        cp = subprocess.run([str(BLENDER), '-b', '--factory-startup', str(blend), '--python',
                             str(HERE / 'render.py'), '--', '--kind', kind, '--out', str(out)],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
        (out / f'blender_{kind}.log').write_text(cp.stdout[-20000:] + cp.stderr[-5000:], encoding='utf-8')
        if cp.returncode or f'R135_RENDER_DONE {kind}' not in cp.stdout:
            raise SystemExit(f'render failed: {kind} rc={cp.returncode}; see {out}/blender_{kind}.log')
    wall = time.perf_counter() - t0
    res = {}
    for mode in ('relief', 'full'):
        for cand in CANDS:
            for shot in SHOTS:
                res[f'{mode}/{cand}/{shot}'] = score.shot_score(out / f'{cand}_{mode}_{shot}.png',
                                                                out / f'S_{mode}_{shot}.png')
    return wall, res


def version_score(res, mode, cand):
    vals = [res[f'{mode}/{cand}/{s}']['score'] for s in SHOTS if res[f'{mode}/{cand}/{s}']['status'] == 'measured']
    return (max(vals) if vals else None), len(vals)


def verdict(res):
    V = {c: version_score(res, 'relief', c) for c in CANDS}
    measured = [s for s in SHOTS if res[f'relief/v045/{s}']['status'] == 'measured'
                and res[f'relief/v096/{s}']['status'] == 'measured']
    wins = [s for s in measured if res[f'relief/v045/{s}']['score'] > res[f'relief/v096/{s}']['score']]
    v45, v96, p1, p2 = V['v045'][0], V['v096'][0], V['P1'][0], V['P2'][0]
    stripe = res['relief/v045/joint-stripe']
    checks = {
        'margin_ge_0.10': None if None in (v45, v96) else v45 - v96 >= 0.10,
        'shots_ge_4_of_measured': len(measured) >= 4 and len(wins) >= 4,
        'stripe_signed_negative': None if stripe['status'] != 'measured' else stripe['signed_median'] < 0,
        'N0_zero': all(res[f'relief/N0/{s}']['score'] is not None and res[f'relief/N0/{s}']['score'] <= 1e-9
                       for s in SHOTS),
        'P1_fires': None if None in (p1, v96) else p1 > v96 + 0.10,
        'P2_monotone': None if None in (p1, p2, v96) else v96 <= p2 <= p1 + 0.05,
    }
    return dict(V={k: v[0] for k, v in V.items()}, measured_shots=len(measured), v045_wins=wins, checks=checks)


def main():
    out = Path(sys.argv[1]).resolve()
    runs = int(sys.argv[sys.argv.index('--runs') + 1]) if '--runs' in sys.argv else 3
    if out.exists():
        raise SystemExit(f'{out} exists; use a new dir')
    if any(str(out).startswith(str(p.parent)) for p in PINS):
        raise SystemExit('out dir must not be inside an input dir')
    pins = preflight()
    out.mkdir(parents=True)
    rows = []
    for k in range(1, runs + 1):
        wall, res = one_run(out / f'run{k}')
        rows.append(dict(run=k, wall_s=round(wall, 3), verdict=verdict(res), shots=res))
        print(f'run{k} wall={wall:.1f}s V={rows[-1]["verdict"]["V"]}', flush=True)
    keys = rows[0]['shots'].keys()
    spread = max((max(r['shots'][k]['score'] for r in rows) - min(r['shots'][k]['score'] for r in rows))
                 for k in keys if all(r['shots'][k]['score'] is not None for r in rows))
    v = rows[0]['verdict']
    stable = spread <= 1e-9 and all(r['verdict'] == v for r in rows)
    calib = all(v['checks'][c] is True for c in ('margin_ge_0.10', 'shots_ge_4_of_measured',
                                                  'stripe_signed_negative'))
    witnesses = all(v['checks'][c] is True for c in ('N0_zero', 'P1_fires', 'P2_monotone'))
    h = 'inconclusive (unstable)' if not stable else (
        'confirmed' if calib and witnesses else 'inconclusive (witness)' if calib else 'refuted')
    rec = dict(card='t_33b1b86c', round=135, hypothesis='H135', result=h, stable=stable, max_paired_spread=spread,
               pins=pins, blender=str(BLENDER), runs=rows)
    p = out / 'receipt.json'
    p.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding='utf-8')
    print('H135', h, 'spread', spread, 'receipt', p, sha(p))


if __name__ == '__main__':
    main()
