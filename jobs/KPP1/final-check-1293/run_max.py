"""new-case: #1293 installed AGR Tools check-only characterization on copied FBX.

Run through dcc_batch.py max --file <this file>. Configuration is tmp/final1293/config.json.
No installed code is changed. GeoJSON uses the macro's explicit-path checker seam
instead of its interactive chooser. Other rows invoke the registered macros once.
"""
import hashlib
import json
from pathlib import Path
import sys
import traceback

TOOLS = ('XView', 'MatID', 'Names', 'Tris', 'Textures', 'Pivot', 'Texel', 'Ucx', 'Atlas', 'Export', 'Geojson')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_config(config):
    if not isinstance(config, dict) or not {'inputs', 'output'} <= set(config) or set(config) - {'inputs', 'output', 'tools'}:
        raise ValueError('partial or unsupported config')
    rows, tools = config['inputs'], config.get('tools', list(TOOLS))
    if not isinstance(rows, list) or not rows or not isinstance(tools, list) or not tools:
        raise ValueError('empty inputs or tools')
    if any(not isinstance(t, str) or t not in TOOLS for t in tools) or len(set(tools)) != len(tools):
        raise ValueError('unsupported or duplicate check')
    output = config['output']
    if not isinstance(output, str) or not output.strip():
        raise ValueError('invalid output path')
    paths, profiles = [], []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'profile', 'fbx', 'geojson'}:
            raise ValueError('partial input row')
        if row['profile'] not in ('npm', 'vpm'):
            raise ValueError('unsupported profile')
        if any(not isinstance(row[k], str) or not row[k].strip() for k in ('fbx', 'geojson')):
            raise ValueError('invalid input path')
        if not Path(row['fbx']).is_file():
            raise ValueError('missing FBX: ' + row['fbx'])
        paths.append(Path(row['fbx']))
        profiles.append(row['profile'])
    outputs = [Path(output)] + [Path(output).with_name(Path(output).stem + '-' + r['profile'] + '-' + t + '.json')
                               for r in rows for t in tools]
    keys = [str(p.resolve()).casefold() for p in paths + outputs]
    if len(set(keys)) != len(keys) or len(set(profiles)) != len(profiles):
        raise ValueError('aliased input/output or duplicate profile')
    for out in outputs:
        if out.exists():
            raise FileExistsError(out)


def main():
    root = Path(__file__).resolve().parents[3]
    config = json.loads((root / 'tmp/final1293/config.json').read_text(encoding='utf-8'))
    validate_config(config)
    from pymxs import runtime as rt
    import __main__
    agr = __main__.agr_tools_runtime
    output = Path(config['output'])
    if output.exists():
        raise FileExistsError(output)
    inputs = [Path(row['fbx']) for row in config['inputs']]
    if len({str(p.resolve()).casefold() for p in inputs + [output]}) != len(inputs) + 1:
        raise ValueError('aliased input/output')
    hashes = {str(p): digest(p) for p in inputs}
    if agr.VERSION != '1.1.0':
        raise ValueError('unexpected AGR Tools version: ' + agr.VERSION)
    result = {'agr_version': agr.VERSION, 'runtime': agr.__file__, 'runtime_sha256': digest(agr.__file__),
              'max_version': str(rt.maxVersion()), 'inputs_before': hashes, 'profiles': []}
    original_ui = agr.ui
    for row in config['inputs']:
        rt.resetMaxFile(rt.Name('noPrompt'))
        rt.units.SystemType = rt.Name('meters')
        rt.units.SystemScale = 1.0
        rt.pluginManager.loadClass(rt.FbxImporter)
        rt.FBXImporterSetParam('Mode', rt.Name('create'))
        if not rt.importFile(row['fbx'], rt.Name('noPrompt'), using=rt.FBXIMP):
            raise RuntimeError('FBX import failed: ' + row['fbx'])
        nodes = list(rt.geometry)
        if not nodes:
            raise ValueError('empty imported geometry')
        rt.select(nodes)
        before = agr.snapshot(nodes)
        record = {'profile': row['profile'], 'file': row['fbx'], 'unit_m': agr._unit_m(),
                  'nodes': [{'name': str(n.name), 'props': str(rt.getUserPropBuffer(n))} for n in nodes], 'checks': {}}
        result['profiles'].append(record)
        for tool in config.get('tools', TOOLS):
            if tool not in TOOLS:
                raise ValueError('unsupported check: ' + repr(tool))
            checkpoint = output.with_name(output.stem + '-' + row['profile'] + '-' + tool + '.json')
            if checkpoint.exists():
                raise FileExistsError(checkpoint)
            rt.select(nodes)  # xView selects offenders; each macro needs the complete FBX scope.
            entry = {'status': 'error', 'invocation': 'macro'}
            record['checks'][tool] = entry
            def capture(key):
                report = original_ui(key)
                entry['report'] = report
                entry['status'] = report['status']
                return report
            agr.ui = capture
            try:
                if tool == 'Geojson':
                    entry['invocation'] = 'checks_050 explicit path (no file chooser)'
                    report = agr.checks_050('geojson', path=row['geojson'])
                    entry.update(report=report, status=report['status'])
                else:
                    # Export is first-press only even if startup state changes.
                    if tool == 'Export':
                        agr._export = None
                        agr._export_key = None
                    rt.macros.run('AGR Tools', 'AGRTools' + tool)
                    if 'report' not in entry:
                        raise RuntimeError('macro returned without a captured report')
            except Exception as exc:
                entry.update(status='error', error=repr(exc), traceback=traceback.format_exc())
            finally:
                agr.ui = original_ui
            entry['scene_unchanged'] = agr.snapshot(nodes) == before
            if not entry['scene_unchanged']:
                raise RuntimeError('scene changed by ' + tool)
            with checkpoint.open('x', encoding='utf-8') as handle:
                json.dump({'profile': row['profile'], 'tool': tool, **entry}, handle, indent=2, allow_nan=False)
            print('FINAL1293', row['profile'], tool, entry['status'])
        record['scene_unchanged'] = agr.snapshot(nodes) == before
    result['inputs_after'] = {str(p): digest(p) for p in inputs}
    if result['inputs_after'] != hashes:
        raise RuntimeError('input files changed')
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print('FINAL1293_COMPLETE', str(output))


if __name__ == '__main__':
    main()
