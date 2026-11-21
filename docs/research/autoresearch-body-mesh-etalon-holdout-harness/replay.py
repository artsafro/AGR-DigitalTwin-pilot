"""Standing #25: replay pinned #18 holdout.py (unchanged #17 R3) on Artem's G22 etalon bands (OBSERVE only)."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REV18 = '789b2c895ae181ad098dbbd912c183a4393d6990'
HOLDOUT = 'docs/research/autoresearch-body-mesh-holdout-harness/holdout.py'
HOLDOUT_SHA = 'bec61ed41989d5b7b6a6513266c65caa4f692e18a023f9d00c98a4f9d58a0075'
R18_JSON = 'docs/research/autoresearch-body-mesh-holdout-harness/holdout.json'
R18_SHA = '4cd18c20f819cd22caf68c9dc905de474515dd791b86cb073594bcdf58235ae3'
EV = 'C:/x/ev_1619/'
INPUTS = {
    'G22-etalon-k1': (EV + 'r2/etalon_k1.mq.json', '413515339be03d1aa8eb88d23c487ce81f1605eced51d3b822d2919141acefb1'),
    'G22-etalon-k2': (EV + 'r4/etalon_k2.mq.json', '50df5fb7252078a3fc1edc9076b9e0043051f897bb3aa363b2014b404e6f8d0d'),
    'G22-etalon-k3': (EV + 'r1/etalon_k3.mq.json', 'dc389b008673016871591e1cb42f151379b63aa2ffe271590c52b3009a7d4a13'),
    'G22-k3-v006': (EV + 'r1/k3_v006.mq.json', '39d22ea93efd8ff93c9c8542a314b8b2533fc8f5784d2807a7d5d1581a30dab0'),
    'G22-k2-v002r1': (EV + 'r7/k2_v002r1.mq.json', '2e922754e8b77f854627267fc75b1ba9c22c41a7c4713333fc34ba0ffaff431b'),
}
PARITY = 'G22-k2-v002r1'
FIXTURE = [k for k in INPUTS if k != PARITY]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)


def main(out, holdout_sha=HOLDOUT_SHA):
    src, r18 = blob(REV18, HOLDOUT), blob(REV18, R18_JSON)
    if sha(src) != holdout_sha or sha(r18) != R18_SHA:
        raise ValueError('pinned #18 harness or receipt hash mismatch')
    scope: dict[str, Any] = {'__name__': 'ar25_pinned', '__file__': str(ROOT / HOLDOUT)}
    exec(compile(src, f'{REV18}:{HOLDOUT}', 'exec'), scope)
    scope['INPUTS'] = INPUTS
    scope['main'](out)
    res = json.loads((out / 'holdout.json').read_text(encoding='utf-8'))
    old = json.loads(r18)['rows'][PARITY]
    new = res['rows'][PARITY]
    keys = ('dump_sha256', 'totals', 'R0', 'R3', 'local', 'median_drop', 'paired_spread')
    parity = all(old[k] == new[k] for k in keys)
    if not parity:
        raise ValueError('parity row differs from #18')
    rows = {k: res['rows'][k] for k in FIXTURE}
    mx = max(r['median_drop'] for r in rows.values())
    act = {k: {'irregular_faces': r['totals']['irregular_faces'], 'irregular_area': r['totals']['irregular_area'],
               'area': r['totals']['area'], 'local_R3': r['local'], 'R0': r['R0'][0], 'R3': r['R3'][0],
               'median_drop': r['median_drop'], 'paired_spread': r['paired_spread']} for k, r in rows.items()}
    receipt = {'card': 't_99842019', 'pinned_holdout': [REV18, HOLDOUT_SHA], 'pinned_r18_receipt_sha256': R18_SHA,
               'R0_sha256': res['R0_sha256'], 'R3_sha256': res['R3_sha256'], 'parity_row': PARITY,
               'parity': parity, 'fixture': act, 'max_median_drop': mx, 'threshold': 0.5, 'passed': mx <= 0.5,
               'activating_controls': [k for k, a in act.items() if a['irregular_faces'] > 0],
               'holdout_json_sha256': sha((out / 'holdout.json').read_bytes())}
    with (out / 'r25.json').open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(receipt, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({'max_median_drop': mx, 'activating': receipt['activating_controls']}))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
