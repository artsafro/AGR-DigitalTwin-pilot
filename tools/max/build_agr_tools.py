"""new-case: deterministic, exclusively published AGR Tools MZP builder.

The dependency-free hygiene slice is generated from our existing checker by AST;
no team source, third-party package or absolute workstation path is distributed.
"""
import argparse
import ast
import hashlib
import io
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'adapters/max/agr_tools'
HYGIENE = ROOT / 'src/twinqa/export_hygiene.py'
NUDGE = ROOT / 'src/dt_ai/geometry/uv_nudge.py'
TILES = ROOT / 'src/dt_ai/geometry/uv.py'
HYGIENE_NAMES = {'ORIGIN', 'UV_NAME', 'CA_OWNERS', 'OBJECT_KEYS', 'MAX_MAP_CHANNEL',
                 '_MAP_LINE', 'InputError', 'parse_udp', '_validate',
                 '_channel1_problem', '_extra_channels', 'repair_plan'}


def hygiene_slice(source=None):
    if source is None:
        source = HYGIENE.read_text(encoding='utf-8')
    nodes = []
    found = set()
    for node in ast.parse(source).body:
        name = getattr(node, 'name', None)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in HYGIENE_NAMES:
            nodes.append(node)
            found.add(name)
    if found != HYGIENE_NAMES:
        raise ValueError(f'hygiene source changed: missing {HYGIENE_NAMES - found}')
    header = ('"""Generated from our export_hygiene.py; new-case: stdlib Max hygiene slice.\n'
              f'Source sha256: {hashlib.sha256(source.encode()).hexdigest()}\n"""\n'
              'import copy\nimport re\n')
    return (header + ast.unparse(ast.Module(body=nodes, type_ignores=[])) + '\n').encode('utf-8')


def _function(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise ValueError('missing function ' + name)


def nudge_slice(nudge_source=None, tile_source=None):
    """Stdlib slice of our uv_nudge.py plus tile_origin. Team-script names are not shipped."""
    if nudge_source is None:
        nudge_source = NUDGE.read_text(encoding='utf-8')
    if tile_source is None:
        tile_source = TILES.read_text(encoding='utf-8')
    nudge_source = nudge_source.replace('\r\n', '\n')
    tile_source = tile_source.replace('\r\n', '\n')
    body = []
    for node in ast.parse(nudge_source).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(getattr(node, 'value', None), ast.Constant):
            continue  # module docstring cites team-script names; the logic below is ours
        body.append(node)
    if not any(isinstance(node, ast.FunctionDef) and node.name == 'nudge_repeating_islands' for node in body):
        raise ValueError('uv_nudge source changed: nudge_repeating_islands missing')
    module = ast.Module(body=[_function(tile_source, 'tile_origin'), *body], type_ignores=[])
    ast.fix_missing_locations(module)
    header = ('"""Generated from our uv_nudge.py; new-case: stdlib integer-tile UV nudge slice.\n'
              f'Source sha256: {hashlib.sha256(nudge_source.encode()).hexdigest()}\n"""\n'
              'from __future__ import annotations\nimport math\nfrom dataclasses import dataclass, field\n')
    return (header + ast.unparse(module) + '\n').encode('utf-8')


def build(output):
    output = Path(output)
    entries, inputs = {}, {}
    for name in ('mzp.run', 'install.ms', 'startup.ms', 'agr_tools.mcr', 'runtime.py', 'bootstrap.py',
                 'README.md', 'atlas_core.py'):
        p = PACKAGE / name
        inputs[p] = p.read_bytes()
        entries[name if name in ('mzp.run', 'install.ms') else 'agr_tools/' + name] = inputs[p].replace(b'\r\n', b'\n')
    inputs[HYGIENE] = HYGIENE.read_bytes()
    inputs[NUDGE] = NUDGE.read_bytes()
    inputs[TILES] = TILES.read_bytes()
    entries['agr_tools/hygiene_core.py'] = hygiene_slice(inputs[HYGIENE].decode('utf-8').replace('\r\n', '\n'))
    entries['agr_tools/uv_nudge_core.py'] = nudge_slice(
        inputs[NUDGE].decode('utf-8').replace('\r\n', '\n'),
        inputs[TILES].decode('utf-8').replace('\r\n', '\n'))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    data = stream.getvalue()
    for path, original in inputs.items():
        if path.read_bytes() != original:
            raise ValueError('input changed during build: ' + str(path))
    # Exclusive creation also refuses aliases/hardlinks to every input and stale outputs.
    with output.open('xb') as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(f'{build(args.output)}  {args.output}')


if __name__ == '__main__':
    main()
