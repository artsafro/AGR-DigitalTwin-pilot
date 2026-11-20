"""OBSERVE candidate R2 (standing #5): range-index text runs before ``_span_gap``.

Built from the live ``dt_ai/album/binding.py`` text by exact, count-checked replacement and executed as a
separate in-memory module. Nothing on disk under ``src/`` is touched.
"""
from pathlib import Path
import types

from dt_ai.album import binding

INDEX = '''    spans = []
    # R2 (OBSERVE): along-axis index of the non-authorizer usable runs, one per text direction.
    # The window only narrows which runs reach _span_gap; _span_gap still decides every hit.
    import bisect as _bisect
    _pool = [(i, r) for i, r in usable if i not in authorizers]
    _maxpad = max([2 * r.size for _, r in _pool if r.size == r.size], default=0)
    _rows: dict[str, list[tuple[float, int, R.TextRun]]] = {"horizontal": [], "vertical": []}
    for i, r in _pool:
        cx, cy = R._center(r.bbox)
        if abs(r.dir[1]) <= 1e-6 and r.dir[0] > 0 and cx == cx:
            _rows["horizontal"].append((cx, i, r))
        elif abs(r.dir[0]) <= 1e-6 and abs(r.dir[1]) > 0.99 and cy == cy:
            _rows["vertical"].append((cy, i, r))
    for _v in _rows.values():
        _v.sort(key=lambda t: (t[0], t[1]))
    _keys = {k: [t[0] for t in v] for k, v in _rows.items()}

    def _window(sp: dict[str, Any], pad: float) -> list[tuple[int, R.TextRun]]:
        keys, rows = _keys[sp["orientation"]], _rows[sp["orientation"]]
        lo = _bisect.bisect_left(keys, sp["a"] - pad)
        hi = _bisect.bisect_right(keys, sp["b"] + pad)
        return [(i, r) for _, i, r in rows[lo:hi]]
'''

REPLACEMENTS = [
    ('    spans = []\n', INDEX),
    ('        return sorted((g, i) for i, r in usable if i not in authorizers\n',
     '        return sorted((g, i) for i, r in _window(sp, 0.0)\n'),
    ('        strict, padded = [], []\n        for i, r in usable:\n            if i in authorizers:\n'
     '                continue\n',
     '        strict, padded = [], []\n'
     '        for i, r in _window(sp, _maxpad if sp["b"] - sp["a"] < _maxpad else 0.0):\n'),
]


def build() -> types.ModuleType:
    text = Path(binding.__file__).read_text(encoding='utf-8')
    for old, new in REPLACEMENTS:
        if text.count(old) != 1:
            raise RuntimeError(f'R2 anchor not unique in binding.py: {old[:60]!r}')
        text = text.replace(old, new)
    mod = types.ModuleType('dt_ai.album._ar_candidate_r2')
    mod.__file__ = '<ar_candidate_r2>'
    exec(compile(text, '<ar_candidate_r2>', 'exec'), mod.__dict__)
    return mod
