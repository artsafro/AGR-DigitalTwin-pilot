"""Standing #13 R0: rejected-vs-accepted calibration of tools/qa/mesh_quality_score.py (OBSERVE).

  python calibrate.py OUT_DIR [--runs 3] [--only ID ...]

Runs the unchanged CLI (default params) RUNS times per input listed in INPUTS, checks each input's
SHA-256 against the frozen value before and after, requires byte-identical score payloads across
repeats (the 'input' block holds only provenance), takes the median score and writes OUT_DIR/r0.json
with every pair margin (accepted - rejected, points). Never writes next to an input; OUT_DIR must be new.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / 'tools' / 'qa' / 'mesh_quality_score.py'
EV = 'G:/Мой диск/AGR-evidence'
B = EV + '/1619-body-training/tower-B'
KPP_CORNERS = ['-17.5,-8.2,-12.5,-3.2', '-17.5,3.5,-12.5,8.5']   # frozen #1616 r4 boxes

# id: (path, sha256, extra CLI args, label)
INPUTS = {
    '63B-v001': ('C:/x/poly63-scratch-b/.poly63_out/63B_Stage1_v001.fbx',
                 'e9ad706c8b37f55c125be98d77e1607cc227d60279e7a794e4ba92276fd3a851', [], 'rejected'),
    '63B-v002': (B + '/v002/63B_Stage1_v002.fbx',
                 'a57cb3fb66e628e6d1fe1272d16bc592604389b52be6cb4af6a4259b75746a9d', [], 'rejected'),
    '63B-v003': (B + '/v003/63B_Stage1_v003.fbx',
                 '83f3289c70a2bf8727cc5a0a8d85d12a8f6e90c803c3c37dfc904856588211aa', [], 'rejected'),
    '63B-v004': (B + '/v004/63B_Stage1_v004.fbx',
                 '6d22c572ab18d9722dcf2296dcca77525ae26265114ba6ff922c3d82f4ce26ae', [], 'rejected'),
    '63B-v005': (B + '/v005/63B_Stage1_v005.fbx',
                 'a387a459a7d2be6c967e533778da37cc560cc532fe94ed470a72d850fc524fd7', [], 'rejected'),
    '63B-v006': (B + '/v006/63B_Stage1_v006.fbx',
                 'b2b26d4448798b1174dfce9b1c7ad1386fd6acc78ce9635553e0e7ed7ba4a455', [], 'rejected'),
    '63B-v007': (B + '/v007/63B_Stage1_v007.fbx',
                 '53189b830418a328f3159172c5c1c7eff826c5a9eff568cad0b9187b63332bd7', [], 'accepted'),
    '63C-v001': (EV + '/1619-body-training/tower-C/v001/63C_stage1_QUAD.fbx',
                 'dcbfc39d5ceed7146c2cb280c727a5755cfec8704a602d34d0f6efce481d2526', [], 'rejected'),
    '63C-v002': (EV + '/1619-body-training/tower-C/v002/63C_stage1_v002_QUAD.fbx',
                 '462ba61b2c379de53a72667635fd0714703764b2409407cc67ff28d8684de1da', [], 'accepted'),
    'KPP1-v003-corners': ('C:/x/ev_1616/inputs/master-quad-v003.blend',
                          'b54c5f72cca60e8cd8cd0401eec7f283ce67d371c1fae6e387d189fae588ab53', [a for z in KPP_CORNERS for a in ('--zone', z)], 'rejected'),
    'KPP1-v003-rest': ('C:/x/ev_1616/inputs/master-quad-v003.blend',
                       'b54c5f72cca60e8cd8cd0401eec7f283ce67d371c1fae6e387d189fae588ab53', [a for z in KPP_CORNERS for a in ('--exclude-zone', z)], 'accepted'),
    'G22-k1-v002': ('C:/x/ev_1619/r2/k1_v002.mq.json',
                    'cbee5a4481d73c80ebe0a4c669393f5404308d112be894011879ae0883588bf9', [], 'rejected'),
    'G22-k1-v003': ('C:/x/ev_1619/r3/k1_v003.mq.json',
                    '0939980dc8e9717657f437d2c840a77e6241f27ea5171ae402677def11f80db1', [], 'accepted'),
}
PAIRS = [('63B-v007', f'63B-v00{i}') for i in range(1, 7)] + [
    ('63C-v002', '63C-v001'), ('KPP1-v003-rest', 'KPP1-v003-corners'), ('G22-k1-v003', 'G22-k1-v002')]
MARGIN = 0.5


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def check(path, frozen):
    got = sha(path)
    if not got.startswith(frozen):
        raise SystemExit(f'hash drift {path}: {got} != {frozen}')
    return got


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    rows = {}
    for key, (path, frozen, extra, label) in INPUTS.items():
        if a.only and key not in a.only:
            continue
        full = check(path, frozen)
        scores, payloads, secs = [], set(), []
        for r in range(a.runs):
            rep = out / f'{key}.run{r + 1}.json'
            t0 = time.perf_counter()
            proc = subprocess.run([sys.executable, str(CLI), path, '--out', str(rep), *extra],
                                  capture_output=True, text=True, cwd=ROOT)
            secs.append(round(time.perf_counter() - t0, 1))
            if proc.returncode not in (0, 1) or not rep.is_file():
                raise SystemExit(f'{key} run {r + 1} exit {proc.returncode}: {proc.stderr[-600:]}')
            d = json.loads(rep.read_text(encoding='utf-8'))
            d.pop('input', None)
            payloads.add(json.dumps(d, sort_keys=True))
            scores.append(d['score'])
        check(path, frozen)
        d = json.loads(next(iter(payloads)))
        rows[key] = {'label': label, 'path': path, 'sha256': full, 'args': extra, 'scores': scores,
                     'median': statistics.median(scores), 'identical_payloads': len(payloads) == 1,
                     'seconds': secs, 'components': d['components'], 'totals': d.get('totals'),
                     'problems': d.get('problems')}
        print(key, label, scores, 'identical' if len(payloads) == 1 else 'DIFFER', secs, flush=True)
    pairs = []
    for acc, rej in PAIRS:
        if acc in rows and rej in rows:
            m = round(rows[acc]['median'] - rows[rej]['median'], 3)
            pairs.append({'accepted': acc, 'rejected': rej, 'margin': m, 'pass': m >= MARGIN})
    verdict = {'margin_required': MARGIN, 'pairs': pairs,
               'min_margin': min((p['margin'] for p in pairs), default=None),
               'calibrated': bool(pairs) and all(p['pass'] for p in pairs)}
    (out / 'r0.json').write_text(json.dumps({'rows': rows, **verdict}, indent=1, ensure_ascii=False),
                                 encoding='utf-8')
    for p in pairs:
        print(p)
    print('min_margin', verdict['min_margin'], 'calibrated', verdict['calibrated'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
