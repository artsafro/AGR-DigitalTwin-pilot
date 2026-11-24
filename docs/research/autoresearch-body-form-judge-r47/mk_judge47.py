"""Derive judge47.py from judge41.py: same prompts/flags/models; only variant list, seeds, dirs and pair set change."""
from pathlib import Path

S = Path('C:/x/autoresearch-body-form-r41')
D = Path(__file__).resolve().parent
t = (S / 'judge41.py').read_text(encoding='utf-8')
subs = [
    ('"""Standing #41 judge runner', '"""Standing #47 judge runner (= judge41.py, mesh-only variants + AA control)'),
    ("JDIR = Path('C:/x/j41')", "JDIR = Path('C:/x/j47')"),
    ("VARIANTS = ['A', 'R', 'P_fill', 'P_recess', 'P_corner']",
     "VARIANTS = ['A', 'N_tri', 'N_sub', 'N_jit_0.005', 'N_jit_0.020']"),
    ("rng = random.Random(4141 if kind == 'pair' else 41)", "rng = random.Random(4747 if kind == 'pair' else 47)"),
    ("            for v in VARIANTS[1:]:\n", "            for v in VARIANTS[1:] + ['A']:   # #47: A vs A = forced-choice control\n"),
    ("print('JUDGE41_DONE'", "print('JUDGE47_DONE'"),
]
for a, b in subs:
    assert t.count(a) == 1, a
    t = t.replace(a, b)
(D / 'judge47.py').write_text(t, encoding='utf-8')
print('MK_OK')
