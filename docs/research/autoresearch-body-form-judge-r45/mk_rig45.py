"""Derive rig45.py from rig41.py (only the size parameter changes) and copy the frozen inputs."""
import shutil
from pathlib import Path

S = Path('C:/x/autoresearch-body-form-r41')
D = Path(__file__).resolve().parent
(D / 'inputs').mkdir(exist_ok=True)
shutil.copyfile(S / 'inputs/A.fbx', D / 'inputs/A.fbx')
shutil.copyfile(S / 'compose41.py', D / 'compose41.py')
t = (S / 'rig41.py').read_text(encoding='utf-8')
subs = [
    ("root, src, variant, out = sys.argv[sys.argv.index('--') + 1:]",
     "root, src, variant, param, out = sys.argv[sys.argv.index('--') + 1:]\n"
     "param = float(param)   # #45: recess depth / chamfer leg (m); ignored for A"),
    ("(0.6, 2.4), (-0.05, 0.13), z0, z1)", "(0.6, 2.4), (-0.05, param), z0, z1)"),
    ("'depth': 0.13}", "'depth': param}"),
    ("    leg = 0.8\n", "    leg = param\n"),
    ("Usage: blender ... --python rig41.py -- ROOT FBX VARIANT OUTDIR",
     "Usage: blender ... --python rig45.py -- ROOT FBX VARIANT PARAM OUTDIR (#45: rig41 + size param)"),
]
for a, b in subs:
    assert t.count(a) == 1, a
    t = t.replace(a, b)
(D / 'rig45.py').write_text(t, encoding='utf-8')
print('MK_OK')
