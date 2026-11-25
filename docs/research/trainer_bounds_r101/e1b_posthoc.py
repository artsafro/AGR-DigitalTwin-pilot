import json, sys
sys.path.insert(0, 'docs/research/trainer_bounds_r101')  # post-hoc, not a verdict input
import measure as M
man = json.load(open('docs/research/trainer_bounds_r101/manifest.json', encoding='utf-8'))
k = man['kpp1']; frame = json.load(open(k['frame'][0], encoding='utf-8'))
rec = json.load(open('docs/research/trainer_bounds_r101/receipt.json', encoding='utf-8'))
key = json.load(open('C:/x/ev_t_5c94d830/series1/rep1/key.json', encoding='utf-8'))
l03, _ = M.read(k['l03_dxf'][0]); l01, _ = M.read(k['l01_dxf'][0])
class F:  # entity filter: drop annotation suffixes
    pass
import ezdxf
def strip(msp):
    return [e for e in msp if not e.dxf.layer.endswith(('-IDEN', '-TEXT', '-NOTE', '-DIMS'))]
fp, c = M.plan_footprint(strip(l03)); z1 = M.facade_top(strip(l01))
rb = M.envelope(fp, 0.0, z1, frame, M.PHYS)
print(json.dumps({'E1b_posthoc': M.T.bounds_step(rb, key), 'faces': M.faces(rb, key), 'counts': dict(c), 'z1': z1}))
