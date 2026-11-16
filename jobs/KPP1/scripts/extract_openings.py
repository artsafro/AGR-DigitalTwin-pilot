"""Derive the legacy KPP1 openings spec through the shared stdlib openings core.

Usage: python extract_openings.py <source_dir> <census_dir>
Outputs: openings_spec.json and openings_dropped.json, unchanged legacy field layout.
KPP1 facade thresholds and door-height convention are an explicit source profile,
not generic Revit defaults. Family matching retains the #1336 Latin-C fix.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from adapters.max.agr_tools.openings_core import norm, read_revit_openings  # noqa: E402,F401


def main(src, cen):
    inputs = [Path(src) / 'curtain.export.json', *(Path(cen) / (g + '.objects.json') for g in ('curtain', 'openings'))]
    outputs = [Path(cen) / name for name in ('openings_spec.json', 'openings_dropped.json')]
    for output in outputs:
        if output.exists() or output.is_symlink() or any(output.resolve() == p.resolve() for p in inputs):
            raise ValueError('output exists or aliases input: ' + str(output))
    if outputs[0].resolve() == outputs[1].resolve():
        raise ValueError('legacy outputs alias each other')
    raw = {path: path.read_bytes() for path in inputs}
    side = json.loads(raw[inputs[0]].decode('utf-8-sig'))
    groups = {g: json.loads(raw[p].decode('utf-8')) for g, p in zip(('curtain', 'openings'), inputs[1:])}
    spec, dropped = read_revit_openings(side, groups, profile='KPP1')
    if any(path.read_bytes() != data for path, data in raw.items()):
        raise ValueError('input changed during extraction')
    for path, value in zip(outputs, (spec, dropped)):
        with path.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=1)
    for f, v in spec.items():
        print(f, {k: len(x) for k, x in v.items()},
              'bays', sum(len(s['bays']) for s in v['surrounds']),
              'windows', sum(len(b['windows']) for s in v['surrounds'] for b in s['bays']),
              'glass', sum(len(b['glass']) for s in v['surrounds'] for b in s['bays']))
    unknown = sum(d['reason'].startswith('unknown family') for d in dropped)
    print('dropped', len(dropped), 'of', sum(map(len, groups.values())), 'objects; unknown families in bays:', unknown)


if __name__ == '__main__':
    main(*sys.argv[1:3])
