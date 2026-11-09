"""new-case: headless Max half of the polygon runner. Build, press each shipped button, write actual.json.

Environment: AGR_POLYGON_OUT (new directory), AGR_POLYGON_ROOT (repo). Started by run_polygon.py
through the shared dcc_batch lock. Synthetic scene only.
"""
import json
import os
import sys
import traceback
from pathlib import Path

OUT = Path(os.environ['AGR_POLYGON_OUT'])
ROOT = Path(os.environ['AGR_POLYGON_ROOT'])
POLY = ROOT / 'test-polygon'
sys.path.insert(0, str(POLY / 'build'))
sys.path.insert(0, str(POLY))
sys.path.insert(0, str(ROOT))

import build_scene
import polygon_core as polygon_core


def _runtime():
    import importlib.util
    # Slices live beside this copy. AGR_TOOLS_REPO stays the checkout so export and
    # GeoJSON still find src/twinqa. Nothing is written under the user's bundle.
    stage = polygon_core.stage_tools(OUT / 'stage', ROOT)
    os.environ['AGR_TOOLS_REPO'] = str(ROOT)
    venv = ROOT / '.venv' / 'Scripts' / 'python.exe'
    if venv.is_file():
        os.environ.setdefault('AGR_PYTHON', str(venv))
    path = stage / 'runtime.py'
    spec = importlib.util.spec_from_file_location('agr_tools_runtime', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['agr_tools_runtime'] = mod
    spec.loader.exec_module(mod)
    return mod


def _select(names):
    from pymxs import runtime as rt
    nodes = []
    for name in names:
        node = rt.getNodeByName(name)
        if node is None:
            raise ValueError('missing polygon node: ' + name)
        nodes.append(node)
    if nodes:
        rt.select(nodes)
    else:
        rt.clearSelection()
    return nodes


PER_OBJECT_100 = polygon_core.PER_OBJECT_100


def _press(runtime, tool, names, options=None):
    from pymxs import runtime as rt
    if (tool in getattr(runtime, 'EDITS_100', ()) or tool in getattr(runtime, 'EDITS_090', ())
            or tool in getattr(runtime, 'EDITS_080', ())):
        # stations of the bases 0.8 / 0.9 / 1.0 (#979 / #1024 fragments): the preview report of the row, never an apply
        nodes = _select(names)
        if tool in getattr(runtime, 'EDITS_100', ()):
            run = runtime.edits_100
        elif tool in getattr(runtime, 'EDITS_090', ()):
            run = runtime.edits_090
        else:
            run = runtime.edits_080
        return run(tool, 'preview', None, nodes or None, options)
    if tool == 'geojson':
        path = str(POLY / 'geojson' / names[0])
        return runtime.checks_050('geojson', None, path)
    if tool == 'units':
        return runtime.checks_070('units', None, False)
    nodes = _select(names)
    if tool in runtime.CHECKS_070:
        return runtime.checks_070(tool, nodes or None, False)
    if tool in runtime.CHECKS_050:
        return runtime.checks_050(tool, nodes or None)
    rt.select(nodes)
    return runtime.ui(tool)


def main():
    runtime = _runtime()
    docs = {}
    for path in sorted((POLY / 'expected').glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        if doc.get('shipped'):
            docs[doc['button']] = doc
    runs = []
    scenes = []
    for doc in docs.values():
        for obj in doc['objects']:
            if obj['scene'] not in scenes:
                scenes.append(obj['scene'])
    texture_dir = str(OUT / 'textures')
    for scene in scenes:
        try:
            build_scene.build(scene, texture_dir=texture_dir)
            max_path = OUT / (scene + '.max')
            build_scene.save(max_path)
        except Exception as exc:  # noqa: BLE001 - one broken scene is a recorded error, not a pass
            runs.append({'button': '*', 'scene': scene, 'tool': 'build',
                         'report': {'status': 'error', 'error': traceback.format_exc()[-1500:]}})
            continue
        for button, doc in docs.items():
            mine = [o for o in doc['objects'] if o['scene'] == scene]
            if not mine:
                continue
            names = [o['name'] for o in mine
                     if not o.get('produced') and o['name'] != '__scene__'
                     and not str(o['name']).endswith('.geojson')]
            tool = doc['tool']
            if tool == 'geojson' or tool in PER_OBJECT_100:
                targets = [[n] for n in names] if tool != 'geojson' else [[o['name']] for o in mine]
            else:
                targets = [names]
            for picked in targets:
                try:
                    report = _press(runtime, tool, picked, doc.get('options'))
                except Exception as exc:  # noqa: BLE001
                    report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
                runs.append({'button': button, 'scene': scene, 'tool': tool, 'names': picked, 'report': report})
            if doc.get('apply_status') and tool in ('nudge', 'atlas', 'ucx', 'cleanup'):
                apply_tool = {'nudge': 'nudge_apply', 'atlas': 'atlas_apply', 'ucx': 'ucx_apply',
                              'cleanup': 'apply'}[tool]
                try:
                    report = _press(runtime, apply_tool, names)
                    status = report.get('status')
                except Exception as exc:  # noqa: BLE001
                    report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
                    status = 'error'
                entry = {'button': button, 'scene': scene, 'tool': apply_tool, 'names': names,
                         'report': report, 'apply_expected': doc['apply_status'],
                         'apply_status': status}
                if any(o.get('produced') == 'cleanup_copy' for o in mine):
                    entry['produced'] = 'cleanup_copy'
                runs.append(entry)
        _export_cleaned_copies(runtime, scene, docs, runs)
    (OUT / 'actual.json').write_text(json.dumps({'schema': 1, 'runs': runs}, ensure_ascii=False, default=str),
                                    encoding='utf-8')


# Export settings the user sets on the cleaned copy before the checked export. Cleanup
# clears the user buffer; these keys are held off by the export cleanup gate. 128 px on
# the 6-8 m box gives 16-21 px/m, inside the NPM band 10-40 px/m (texel_core.py).
EXPORT_PASS_PROFILE = 'NPM'
EXPORT_PASS_MAP_PX = 128


def _material_list(node):
    from pymxs import runtime as rt
    mat = node.material
    if mat is None:
        raise RuntimeError('cleanup copy has no material: ' + str(node.name))
    if rt.classOf(mat) == rt.MultiMaterial:
        names = [str(sub.name) for sub in mat.materialList if sub is not None]
    else:
        names = [str(mat.name)]
    if not names:
        raise RuntimeError('cleanup copy has no material names: ' + str(node.name))
    return names


def _set_export_props(node, target):
    from pymxs import runtime as rt
    rt.setUserProp(node, 'AGR_EXPORT_PATH', str(target).replace('\\', '/'))
    rt.setUserProp(node, 'AGR_TEXEL_PROFILE', EXPORT_PASS_PROFILE)
    rt.setUserProp(node, 'AGR_TEXEL_MAP', ';'.join(
        '{}={}'.format(name, EXPORT_PASS_MAP_PX) for name in _material_list(node)))


def _find_copies(source_name):
    from pymxs import runtime as rt
    prefix = source_name + '_AGR_export_'
    return [node for node in rt.objects if str(node.name).startswith(prefix)]


def _export_cleaned_copies(runtime, scene, docs, runs):
    """Checked export of the cleanup copy into a new FBX, then read it back.

    The dirty original stays the FAIL row. This run is the PASS row and is recorded
    even when the copy or the readback is missing, so the miss cannot look like a pass.
    """
    checked = docs.get('export.checked')
    if not checked:
        return
    wanted = [o for o in checked['objects'] if o['scene'] == scene and o.get('produced') == 'export_readback']
    if not wanted:
        return
    apply_runs = [run for run in runs if run.get('button') == 'export.cleanup' and run.get('scene') == scene
                  and run.get('produced') == 'cleanup_copy']
    apply_ok = bool(apply_runs) and all(run.get('apply_status') == 'pass' for run in apply_runs)
    for obj in wanted:
        target = None
        try:
            if not apply_ok:
                raise RuntimeError('cleanup apply did not pass')
            found = _find_copies(obj['source'])
            if len(found) != 1:
                raise RuntimeError('cleanup copy of {}: {}'.format(
                    obj['source'], [str(node.name) for node in found]))
            copy = found[0]
            target = polygon_core.checked_export_target(OUT, str(copy.name))
            target.parent.mkdir(parents=True, exist_ok=True)
            _set_export_props(copy, target)
            nodes = _select([str(copy.name)])
            preview = runtime.export_preview(nodes, str(target))
            if preview.get('status') != 'pass':
                report = preview
            else:
                report = runtime.export_commit(nodes, preview, str(target))
                plan = report.get('plan') if isinstance(report, dict) else None
                readback = plan.get('readback') if isinstance(plan, dict) else None
                if not isinstance(readback, dict) or 'object_count' not in readback:
                    report = {'status': 'error', 'error': 'FBX readback missing', 'plan': plan or {}}
        except (Exception, SystemExit) as exc:  # noqa: BLE001
            report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
        runs.append({
            'button': 'export.checked', 'scene': scene, 'tool': 'export',
            'names': [obj['name']], 'report': report, 'produced': 'export_readback',
            'target': None if target is None else str(target),
        })
    print('AGR_POLYGON_ACTUAL ' + str(OUT / 'actual.json'))


if __name__ == '__main__':
    main()
