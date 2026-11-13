"""new-case: stage authorized R1 derivation inputs once; never reuse or overwrite a packet."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path('G:/Мой диск/AGR-evidence/1230-kpp1-r1/r1-v002')
EXPECTED = '1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676'


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open('xb') as out:
        out.write(src.read_bytes())
    assert hashlib.sha256(src.read_bytes()).digest() == hashlib.sha256(dst.read_bytes()).digest()


def main(out):
    if hashlib.sha256((SOURCE/'SM_Kpp_1.fbx').read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('source FBX hash changed')
    out.mkdir(parents=True, exist_ok=False)
    for name in ('SM_Kpp_1.fbx','0000_Kpp_1_01.fbx','T_Kpp_1_001_Main_d_1.png','SHA256SUMS.txt'):
        copy(SOURCE/name, out/'source'/name)
    files = ['jobs/KPP1/rerun-1230/textures.json', 'jobs/KPP1/rerun-1230/finishes.json',
        'jobs/KPP1/rerun-1230/parts-schedule-r1-v002.json', 'jobs/KPP1/rerun-1230/RUN-LOG.md',
        'jobs/KPP1/TASK.md', 'jobs/KPP1/STATE.md', 'jobs/KPP1/job.yaml', 'jobs/KPP1/sources.json',
        'jobs/KPP1/LESSONS.md', 'uv.lock', 'routes/npm-oks.md']
    for name in files:
        if name.endswith('TASK.md') and not (ROOT/name).exists():
            continue  # missing in source repository, recorded below, never fabricate one
        copy(ROOT/name, out/'context'/name)
    recipe = out/'jobs/TEC26-OKS/scripts'
    for name in ('finish_map.py','export_safety.py'):
        copy(ROOT/'jobs/TEC26-OKS/scripts'/name, recipe/name)
    copy(ROOT/'jobs/KPP1/scripts/vpm_textures.json', out/'jobs/KPP1/scripts/vpm_textures.json')
    copy(ROOT/'jobs/KPP1/benchmark-1318/recipe/make_textures.py', recipe/'make_textures.py')
    copy(ROOT/'jobs/KPP1/rerun-1230/make_textures.py', recipe/'r1_painter.py')
    copy(ROOT/'jobs/KPP1/rerun-1230/finishes.json', recipe/'finishes.json')
    tex = json.loads((ROOT/'jobs/KPP1/rerun-1230/textures.json').read_text())
    spec = {'address': tex['address'], 'size_full': tex['size'], 'zero_m': 0,
        'source_ids': {}, 'finishes': {}}
    for i,(name,t) in enumerate(tex['finishes'].items(),1):
        spec['finishes'][name] = dict(t, kind='full' if t['P'] else 'placeholder', S=tex['S_m'])
        spec['source_ids'][str(i)] = {'finish': name}
    (out/'spec.json').write_text(json.dumps(spec,indent=2))
    (out/'atlas-config.json').write_text(json.dumps(tex['npm'],indent=2))
    (out/'provenance.json').write_text(json.dumps({'source': str(SOURCE), 'source_sha256': EXPECTED,
        'base_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'scope': 'Derivation only. No source rebuilding. Ordinal source_ids are recovered finish ordinals, not customer IDs.',
        'missing_context': ['jobs/KPP1/TASK.md absent; issue #1318 and D280 define this authorized benchmark scope'],
        'synthetic': False, 'delivery_complete': False},indent=2))
    print('STAGED',out)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
