"""#298 delivery evidence summary -> JSON for the D125 sheet. new-case: job-local reader of run_delivery outputs.

  uv run python jobs/VATUTINO-SITE/summarize_delivery.py C:/x/t_5e2eb833/v007 [sintez-diag.json ...] > summary.json
Reads only files the run wrote (assembly/readback/validate/SINTEZ); computes nothing about the model itself.
"""
import json
import sys
from collections import Counter
from pathlib import Path


def stages(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = d['stages'].items() if isinstance(d['stages'], dict) else [(s.get('id') or s.get('code'), s) for s in d['stages']]
    out = {}
    for code, s in rows:
        bad = [{'status': f['status'], 'name': f['name'], 'observed': str(f.get('observed'))[:200],
                'expected': str(f.get('expected'))[:120]} for f in s.get('findings', []) if f.get('status') in ('fail', 'review')]
        out[code] = {'status': s.get('status'), 'findings': bad}
    return {'passed': d['passed'], 'exit_code': d['exit_code'], 'counts': d['machine_stage_counts'],
            'manual_reviews_pending': d['manual_reviews_pending'], 'stages': out}


def sintez(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    res = {'extension': d.get('extension'), 'address_detected': d.get('address_detected'), 'has_hp': d.get('has_hp'),
           'has_lp': d.get('has_lp'), 'error': d.get('error'), 'messages': d.get('messages')}
    for prof in ('hp', 'lp'):
        items = d.get(prof) or []
        res[prof] = {'counts': dict(Counter(i['state'] for i in items)),
                     'failed': [{'req': i['req_num'], 'name': i['name'], 'errors': str(i.get('errors'))[:300]}
                                for i in items if i['state'] not in ('verified', 'undefined')]}
    return res


def readback(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    return [{'name': m['name'], 'triangles': m['triangles'], 'materials': len(m['materials']),
             'location': m['location'], 'rotation_euler_deg': [round(x, 6) for x in m['rotation_euler_deg']],
             'scale': m['scale'], 'bounds_m': [[round(x, 3) for x in b] for b in m['bounds_m']]} for m in d['meshes']], \
        len(d.get('images', [])), [o if isinstance(o, str) else o.get('name') for o in d.get('other_objects', [])][:5]


def main():
    root = Path(sys.argv[1])
    out = {'run': str(root), 'hashes': json.loads((root / 'hashes.json').read_text()),
           'commands': [{'label': c['label'], 'exit_code': c['exit_code']} for c in json.loads((root / 'commands.json').read_text())]}
    for p in ('npm', 'vpm'):
        a = json.loads((root / p / 'assembly.json').read_text())
        rb, images, other = readback(root / f'readback-{p}.json')
        out[p] = {'triangles': a['triangles'], 'total': sum(a['triangles'].values()), 'readback': rb, 'images': images,
                  'other_objects': other, 'validate': stages(root / f'validate-{p}.stdout'),
                  'validate_scene': stages(root / f'validate-scene-{p}.stdout'), 'sintez': sintez(root / f'sintez-{p}.json'),
                  'vpm_slots': len(a.get('vpm_slots', []))}
    for extra in sys.argv[2:]:
        out.setdefault('sintez_extra', {})[extra] = sintez(extra)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
