"""new-case: immutable-input executable around explicit course-grid page cores.

Usage: python -m tools.materials.course_grid_pages --recipe recipe.json
       --out new-layout.json --report new-report.json

This writes a candidate plan, NEVER a native/map/QA/visual acceptance receipt.
DCC construction, source appearance baking and independent readback are separate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from adapters.max.agr_tools.seams_core import assemble_support_pages


def _json(raw):
    def invalid(value):
        raise ValueError(f'nonfinite JSON: {value}')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(raw, parse_constant=invalid, object_pairs_hook=unique)


def _digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _distinct(paths):
    for i, path in enumerate(paths):
        for other in paths[:i]:
            if (str(path.resolve()).casefold() == str(other.resolve()).casefold()
                    or path.exists() and other.exists() and os.path.samefile(path, other)):
                raise ValueError(f'path alias or duplicated input: {path} / {other}')


def _reference(value, root):
    if (not isinstance(value, dict) or set(value) != {'path', 'sha256'}
            or not isinstance(value['path'], str) or not value['path']
            or not isinstance(value['sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', value['sha256'])):
        raise ValueError(f'invalid immutable input reference: {value}')
    path = Path(value['path'])
    if not path.is_absolute():
        path = root / path
    return path, value['sha256']


def run(recipe_path, output, report):
    recipe_path, output, report = map(Path, (recipe_path, output, report))
    recipe_bytes = recipe_path.read_bytes()
    recipe = _json(recipe_bytes)
    required = {'schema', 'decision', 'tile_budget', 'tile_px', 'texel_px_m', 'inputs', 'source_hashes'}
    if not isinstance(recipe, dict) or set(recipe) != required or recipe['schema'] != 'course-grid-pages/1':
        raise ValueError('unsupported/partial course-grid-pages recipe')
    if not isinstance(recipe['decision'], str) or not recipe['decision'].strip():
        raise ValueError('missing explicit budget decision reference')
    names = {'partitions', 'brick_fold', 'placements'}
    if not isinstance(recipe['inputs'], dict) or set(recipe['inputs']) != names:
        raise ValueError(f'unmapped plan inputs: {recipe["inputs"]}')
    if not isinstance(recipe['source_hashes'], list) or not recipe['source_hashes']:
        raise ValueError('empty source_hashes')
    refs = {name: _reference(value, recipe_path.parent) for name, value in recipe['inputs'].items()}
    sources = [_reference(value, recipe_path.parent) for value in recipe['source_hashes']]
    partials = [Path(str(output) + '.partial'), Path(str(report) + '.partial')]
    all_inputs = [recipe_path] + [p for p, _ in refs.values()] + [p for p, _ in sources]
    _distinct(all_inputs + [output, report] + partials)
    if any(p.exists() for p in [output, report] + partials):
        raise ValueError('output/report/partial already exists')
    def verify():
        if recipe_path.read_bytes() != recipe_bytes:
            raise ValueError('recipe changed during planning')
        for path, expected in list(refs.values()) + sources:
            if _digest(path) != expected:
                raise ValueError(f'stale/changed input hash: {path}')
    verify()
    loaded = {}
    for name, (path, expected) in refs.items():
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f'input changed while reading: {path}')
        loaded[name] = _json(raw)
    plan = assemble_support_pages(loaded['partitions'], loaded['brick_fold'], loaded['placements'],
                                 texel_px_m=recipe['texel_px_m'], tile_px=recipe['tile_px'],
                                 tile_budget=recipe['tile_budget'])
    plan['decision'] = recipe['decision']
    verify()  # a parsed immutable snapshot is not evidence that current sources stayed frozen
    encoded = json.dumps(plan, allow_nan=False, indent=2).encode('utf-8') + b'\n'
    receipt = dict(passed=False, status='candidate_plan_written_not_native_or_qa',
                   decision=recipe['decision'], recipe_sha256=hashlib.sha256(recipe_bytes).hexdigest(),
                   layout_sha256=hashlib.sha256(encoded).hexdigest(), source_hashes_verified=len(sources),
                   source_faces=plan['source_faces'], support_members=plan['support_members'],
                   tile_budget=recipe['tile_budget'], out=str(output.resolve()))
    encoded_report = json.dumps(receipt, allow_nan=False, indent=2).encode('utf-8') + b'\n'
    created = []
    try:
        for path, raw in zip(partials, (encoded, encoded_report)):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                created.append(path); stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        verify()
        # Exclusive destination opens never clobber a competing writer's output.
        # A crash can leave an incomplete output; only the separately hashed
        # report identifies the completed candidate, never a QA pass.
        for destination, raw in ((output, encoded), (report, encoded_report)):
            with destination.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    finally:
        for path in created:
            path.unlink()  # only our exclusively-created temp files, never an input
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.recipe, args.out, args.report)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f'course_grid_pages: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
