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


def build(output):
    output = Path(output)
    entries, inputs = {}, {}
    for name in ('mzp.run', 'install.ms', 'startup.ms', 'agr_tools.mcr', 'runtime.py', 'bootstrap.py', 'README.md'):
        p = PACKAGE / name
        inputs[p] = p.read_bytes()
        entries[name if name in ('mzp.run', 'install.ms') else 'agr_tools/' + name] = inputs[p].replace(b'\r\n', b'\n')
    inputs[HYGIENE] = HYGIENE.read_bytes()
    entries['agr_tools/hygiene_core.py'] = hygiene_slice(inputs[HYGIENE].decode('utf-8').replace('\r\n', '\n'))
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
