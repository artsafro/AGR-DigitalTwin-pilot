"""new-case: manual openings CLI over shared stdlib readers, with existing CAD analysis.

No Max/Revit session is contacted. See docs/tools/openings.md for schema and limits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import openings_core as core  # noqa: E402


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _json(raw):
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs)


def _same(a, b):
    return a.resolve() == b.resolve() or (a.exists() and b.exists() and os.path.samefile(a, b))


def _preflight(inputs, output):
    for i, path in enumerate(inputs):
        if _same(path, output):
            raise ValueError('output aliases input: ' + str(path))
        for other in inputs[i + 1:]:
            if _same(path, other):
                raise ValueError('duplicate input paths: ' + str(path))
    if output.exists() or output.is_symlink():
        raise ValueError('output already exists; use a new versioned path')


def run(args):
    """Execute source analysis, call the core and exclusively publish one JSON document."""
    if args.pdf is not None:
        raise ValueError('PDF input: not implemented, needs an agreed sample')
    if args.revit is not None:
        if args.profile != 'KPP1' or args.census is None or args.mapping is not None or args.workdir is not None:
            raise ValueError('Revit requires --profile KPP1 --census DIR; --mapping/--workdir are drawing-only')
        inputs = [args.revit, *(args.census / (g + '.objects.json') for g in ('curtain', 'openings'))]
    else:
        if args.mapping is None or args.census is not None or args.profile is not None:
            raise ValueError('drawing requires --mapping JSON; --census/--profile are Revit-only')
        inputs = [args.dwg if args.dwg is not None else args.dxf, args.mapping]
        if args.dwg is not None and (args.workdir is None or args.workdir.exists()):
            raise ValueError('DWG requires --workdir NEW_ASCII_DIRECTORY')
        if args.dxf is not None and args.workdir is not None:
            raise ValueError('--workdir is DWG-only')
    _preflight(inputs, args.output)
    raw = {p: p.read_bytes() for p in inputs}
    refs = [{'path': str(p.resolve()), 'sha256': hashlib.sha256(data).hexdigest()} for p, data in raw.items()]
    if args.revit is not None:
        side = _json(raw[inputs[0]])
        groups = {g: _json(raw[p]) for g, p in zip(('curtain', 'openings'), inputs[1:])}
        spec, dropped = core.read_revit_openings(side, groups, profile=args.profile)
        result = {'format': 'agr-openings/1', 'source_kind': 'revit', 'status': 'measured', 'units': 'm',
                  'facade_binding': {'profile': 'KPP1', 'frame': 'Revit internal coordinates',
                                     'S': {'plane_y_m': -0.33, 'u': 'x'}, 'N': {'plane_y_m': 11.33, 'u': 'x'},
                                     'W': {'plane_x_m': -0.33, 'u': 'y'}, 'E': {'plane_x_m': 27.33, 'u': 'y'}},
                  'source_refs': refs, 'data': {'spec': spec, 'dropped': dropped,
                      'unlocated_references': [{'elementId': i['elementId'], 'type': i['type'], 'reason': 'no boundingBox'}
                          for t in side['types'] for i in t['instances'] if i.get('boundingBox') is None]}}
    else:
        source = args.dxf
        conversion = None
        if args.dwg is not None:
            if args.dwg.suffix.lower() != '.dwg':
                raise ValueError('--dwg source must be .dwg')
            if _same(args.output, args.workdir) or args.workdir.resolve() in args.output.resolve().parents:
                raise ValueError('output must be outside the private DWG workdir')
            args.workdir.mkdir(parents=True, exist_ok=False)
            source = args.workdir / 'source.dxf'
            receipt = args.workdir / 'conversion.json'
            status = subprocess.run([sys.executable, str(ROOT / 'tools/methods/body/dwg_to_dxf.py'),
                                     str(args.dwg), str(source), str(receipt), '--workdir', str(args.workdir)],
                                    check=False).returncode
            if status != 0:
                raise ValueError('DWG conversion failed with exit ' + str(status) + '; see ' + str(args.workdir))
            conversion = _json(receipt.read_bytes())
            if conversion.get('status') != 'pass':
                raise ValueError('DWG conversion receipt is not pass')
        # Dependencies stay outside openings_core, which can be imported by embedded Max Python.
        from tools.methods.body.facade_openings_from_dxf import extract
        schedule = extract(source, args.mapping)
        binding = _json(raw[args.mapping])['facades']
        result = core.read_drawing_openings(schedule, binding)
        # The core preserves the extractor's refs; verify these bind our original snapshot.
        expected_source = hashlib.sha256(source.read_bytes()).hexdigest()
        if schedule['source']['sha256'] != expected_source or schedule['mapping']['sha256'] != refs[1]['sha256']:
            raise ValueError('drawing snapshot changed during extraction')
        result['source_refs'] = refs + ([schedule['source']] if conversion else [])
        if conversion is not None:
            result['conversion'] = conversion
    text = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    if any(p.read_bytes() != data for p, data in raw.items()):
        raise ValueError('input changed during extraction; nothing published')
    # No predictable partial file, replacement, input deletion, or stale-output reuse.
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    for kind in ('revit', 'dwg', 'dxf', 'pdf'):
        source.add_argument('--' + kind, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--mapping', type=Path)
    parser.add_argument('--census', type=Path)
    parser.add_argument('--profile', choices=['KPP1'])
    parser.add_argument('--workdir', type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args)
        print('measured: ' + result['source_kind'] + '; architectural review required')
        return 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
