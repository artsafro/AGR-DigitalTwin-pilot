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


def _press(runtime, tool, names):
    from pymxs import runtime as rt
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
            names = [o['name'] for o in mine if o['name'] != '__scene__' and not str(o['name']).endswith('.geojson')]
            tool = doc['tool']
            if tool == 'geojson':
                targets = [[o['name']] for o in mine]
            else:
                targets = [names]
            for picked in targets:
                try:
                    report = _press(runtime, tool, picked)
                except Exception as exc:  # noqa: BLE001
                    report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
                runs.append({'button': button, 'scene': scene, 'tool': tool, 'names': picked, 'report': report})
            if doc.get('apply_status') and tool != 'geojson':
                apply_tool = {'nudge': 'nudge_apply', 'atlas': 'atlas_apply', 'ucx': 'ucx_apply',
                              'cleanup': 'apply'}[tool]
                try:
                    report = _press(runtime, apply_tool, names)
                    status = report.get('status')
                except Exception as exc:  # noqa: BLE001
                    report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
                    status = 'error'
                runs.append({'button': button, 'scene': scene, 'tool': apply_tool, 'names': names,
                             'report': report, 'apply_expected': doc['apply_status'],
                             'apply_status': status})
    (OUT / 'actual.json').write_text(json.dumps({'schema': 1, 'runs': runs}, ensure_ascii=False, default=str),
                                    encoding='utf-8')
    print('AGR_POLYGON_ACTUAL ' + str(OUT / 'actual.json'))


if __name__ == '__main__':
    main()
