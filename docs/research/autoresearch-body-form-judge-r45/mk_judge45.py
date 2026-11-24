"""Derive judge45.py from judge41.py: same prompts/flags/models; only variant list, seeds, dirs and pair set change."""
from pathlib import Path

S = Path('C:/x/autoresearch-body-form-r41')
D = Path(__file__).resolve().parent
t = (S / 'judge41.py').read_text(encoding='utf-8')
subs = [
    ('"""Standing #41 judge runner', '"""Standing #45 judge runner (= judge41.py, ladder variants)'),
    ("JDIR = Path('C:/x/j41')", "JDIR = Path('C:/x/j45')"),
    ("VARIANTS = ['A', 'R', 'P_fill', 'P_recess', 'P_corner']",
     "VARIANTS = ['A', 'W_recess', 'W_corner', 'P_recess_0.20', 'P_recess_0.11', 'P_recess_0.06', 'P_recess_0.03',\n"
     "            'P_corner_0.40', 'P_corner_0.20', 'P_corner_0.10', 'P_corner_0.05']\n"
     "LADDER = VARIANTS[3:]"),
    ("rng = random.Random(4141 if kind == 'pair' else 41)", "rng = random.Random(4545 if kind == 'pair' else 45)"),
    ("            for v in VARIANTS[1:]:\n", "            for v in LADDER:\n"),
    ("js = [js[0], js[15]]", "js = [js[0], js[33]]"),
    ("print('JUDGE41_DONE'", "print('JUDGE45_DONE'"),
]
for a, b in subs:
    assert t.count(a) == 1, a
    t = t.replace(a, b)
(D / 'judge45.py').write_text(t, encoding='utf-8')
print('MK_OK')
