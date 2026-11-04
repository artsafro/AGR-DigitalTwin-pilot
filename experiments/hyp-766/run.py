"""Bounded #766 experiment. Run prepare, native (inside Max), then compare.
All dumps stay in a fresh card-owned scratch directory; production code unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import statistics
import sys
import time
from pathlib import Path

STATES = {
    'S00_source': {'AC08_body': 143, 'AC08_knob': 24, 'AC08_plate': 13},
    'S12_join_parts_AC08_body_AC08_plate': {'AC08_body_J_AC08_plate': 156, 'AC08_knob': 24},
    'S14_join_parts_AC08_body_AC08_knob': {'AC08_body_J_AC08_knob': 167, 'AC08_plate': 13},
}
REPO = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def prepare(work, source):
    work.mkdir(parents=True, exist_ok=False)
    manifest = REPO / 'jobs/TEC26-OKS/AC08/kernel-ops-v001/evidence/DRIVE-SHA256SUMS-v002.txt'
    hashes = {line.split(' *./')[1]: line.split()[0] for line in manifest.read_text().splitlines()}
    receipt = []
    for state in STATES:
        for folder, ext in [('fbx', '.fbx'), ('readback', '.json')]:
            rel = folder + '/' + state + ext
            src, dst = source / rel, work / rel
            dst.parent.mkdir(exist_ok=True)
            shutil.copyfile(src, dst)
            assert digest(src) == digest(dst) == hashes[rel], rel
            receipt.append({'source': str(src), 'copy': str(dst), 'sha256': hashes[rel]})
    write(work / 'inputs.json', receipt)
    # Driver and prediction are frozen before native execution.
    write(work / 'frozen.json', {'states': STATES, 'driver_sha256': digest(Path(__file__)),
          'tol_m': [.002, .005], 'imports': 2, 'max_symmetric_difference': 0,
          'delivery_passed': False})
    wrapper = work / 'native.ms'
    code = 'import runpy; runpy.run_path(' + repr(str(Path(__file__).resolve())) + ", run_name='hyp766')['native'](" + repr(str(work)) + ')'
    # Python is available on this live bridge (safeMode=false). Restore even on failure.
    wrapper.write_text('holdMaxFile()\ntry (python.Execute ' + json.dumps(code) + ') catch (format "HYP766_ERROR %\\n" (getCurrentException()))\nfetchMaxFile quiet:true\n', encoding='utf-8')
    print('PREPARED', work, 'hashes', len(receipt))


def native(work):
    import pymxs
    rt = pymxs.runtime
    work = Path(work)
    result = {'application': '3ds Max live', 'max_version': list(rt.maxVersion()),
              'python': platform.python_version(), 'initial_document': str(rt.maxFilePath) + str(rt.maxFileName),
              'initial_units': [str(rt.units.SystemType), float(rt.units.SystemScale)],
              'delivery_passed': False, 'imports': [], 'failures': []}
    old_units = rt.units.SystemType, rt.units.SystemScale
    old_v, old_f = rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance
    start = time.perf_counter()
    try:
        rt.units.SystemType = rt.Name('meters')
        rt.units.SystemScale = 1.0
        result['units'] = [str(rt.units.SystemType), float(rt.units.SystemScale)]
        meter = float(rt.units.decodeValue('1m'))
        result['native_units_per_metre'] = meter
        assert meter == 1.0
        checkers = {str(rt.xViewChecker.getCheckerName(i)): i for i in range(1, int(rt.xViewChecker.getNumCheckers()) + 1)}
        result['checkers'] = checkers
        for rep in range(2):
            for state, expected in STATES.items():
                rt.delete(rt.objects)
                rt.FBXImporterSetParam('ResetImport')
                rt.FBXImporterSetParam('Mode', rt.Name('create'))
                rt.FBXImporterSetParam('ConvertUnit', 'm')
                rt.FBXImporterSetParam('SmoothingGroups', True)
                rt.FBXImporterSetParam('Animation', False)
                t0 = time.perf_counter()
                ok = rt.importFile(str(work / 'fbx' / (state + '.fbx')), rt.Name('noPrompt'), using=rt.FBXIMP)
                item = {'state': state, 'rep': rep + 1, 'import_ok': bool(ok), 'import_s': time.perf_counter() - t0,
                        'm_per_unit': 1, 'tol_v_units': .002, 'tol_f_units': .005, 'nodes': [], 'failures': []}
                result['imports'].append(item)
                item['inventory'] = [[str(o.name), str(rt.classOf(o))] for o in rt.objects]
                nodes = list(rt.geometry)
                if sorted(str(o.name) for o in nodes) != sorted(expected):
                    item['failures'].append('inventory mismatch')
                for o in nodes:
                    n = {'name': str(o.name), 'class': str(rt.classOf(o))}
                    item['nodes'].append(n)
                    # No conversion: a representation mismatch is a rejection, not repaired.
                    if rt.classOf(o) != rt.Editable_Poly:
                        n['error'] = 'not Editable_Poly'
                        continue
                    def arrays():
                        return ([[float(c) for c in rt.polyop.getVert(o, i)] for i in range(1, int(rt.polyop.getNumVerts(o)) + 1)],
                                [[int(v) for v in rt.polyop.getFaceVerts(o, i)] for i in range(1, int(rt.polyop.getNumFaces(o)) + 1)])
                    n['vertices'], n['faces'] = arrays()
                    n['num_verts'], n['num_faces'] = len(n['vertices']), len(n['faces'])
                    n['bbox_m'] = [[float(c) for c in o.min], [float(c) for c in o.max]]
                    n['expected_faces'] = expected.get(n['name'])
                    if n['num_faces'] != n['expected_faces']:
                        n['error'] = 'polygon count mismatch'
                    rt.clearSelection()
                    rt.select(o)
                    rt.execute('max modify mode')
                    rt.OverlappingVertices.tolerance = rt.units.decodeValue('2mm')
                    rt.OverlappingFaces.tolerance = rt.units.decodeValue('5mm')
                    for label, prefix, selection in [('Overlapping Vertices', 'verts', rt.polyop.getVertSelection),
                                                      ('Overlapping Faces', 'faces', rt.polyop.getFaceSelection)]:
                        t0 = time.perf_counter()
                        rt.polyop.setVertSelection(o, rt.BitArray())
                        rt.polyop.setFaceSelection(o, rt.BitArray())
                        rt.xViewChecker.activeIndex = checkers[label]
                        rt.xViewChecker.on = True
                        rt.xViewChecker.runCheck(rt.currentTime)
                        native_kind = rt.xViewChecker.getCurrentReturnVal()
                        # pymxs Name.__str__ omits '#'; validate the native enum first.
                        expected_kind = rt.Name('Vertices' if prefix == 'verts' else 'Faces')
                        kind = '#' + str(native_kind)
                        n[prefix + '_native_enum_valid'] = native_kind == expected_kind
                        count = int(rt.xViewChecker.getCurrentOutputCount())
                        if count > 0:
                            rt.xViewChecker.selectResults(rt.currentTime)
                        ids = [int(i) for i in selection(o)] if count > 0 else []
                        rt.xViewChecker.on = False
                        n[prefix + '_type'] = kind
                        n['overlap_vertices' if prefix == 'verts' else 'overlap_faces'] = ids
                        n[prefix + '_count'] = count
                        n[prefix + '_seconds'] = time.perf_counter() - t0
                        if kind.lower() != ('#vertices' if prefix == 'verts' else '#faces') or len(ids) != count:
                            n['error'] = 'checker type/count failure: ' + label
                    n['geometry_unchanged'] = arrays() == (n['vertices'], n['faces'])
                write(work / 'native.json', result)
    except Exception as exc:
        result['failures'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        rt.xViewChecker.on = False
        rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance = old_v, old_f
        rt.units.SystemType, rt.units.SystemScale = old_units
        result['seconds'] = time.perf_counter() - start
        write(work / 'native.json', result)
        print('HYP766_NATIVE', len(result['imports']), result['failures'])


def compare(work, baseline_only=False):
    import numpy as np
    sys.path.insert(0, str(REPO / 'src'))
    spec = importlib.util.spec_from_file_location('parity', REPO / 'tools/qa/xview_parity.py')
    parity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parity)
    result = {'python': platform.python_version(), 'numpy': np.__version__, 'baseline': [], 'native': []}
    # Current code baseline on companion arrays, not a native ID correspondence claim.
    for state in STATES:
        meshes = json.loads((work / 'readback' / (state + '.json')).read_text())['meshes']
        for mesh in meshes:
            g = mesh['face_geometry']
            poly = parity.PolyMesh(np.array(g['vertices']), tuple(tuple(f) for f in g['polygons']))
            timings = []
            for _ in range(3):
                t0 = time.perf_counter()
                r = parity.part_report(mesh['name'], poly, parity.XviewTolerance())
                timings.append(time.perf_counter() - t0)
            result['baseline'].append({'state': state, 'node': mesh['name'], 'verts': len(r.vertices),
                                       'faces': len(r.xview_faces), 'median_s': statistics.median(timings)})
    if baseline_only:
        write(work / 'baseline.json', result)
        print(json.dumps(result, indent=1))
        return
    native_data = json.loads((work / 'native.json').read_text())
    for item in native_data['imports']:
        row = {'state': item['state'], 'rep': item['rep'], 'failures': item['failures'], 'rows': []}
        for node in item['nodes']:
            if 'error' in node:
                row['failures'].append(node['name'] + ': ' + node['error'])
            if 'vertices' not in node:
                continue
            timings = []
            try:
                for _ in range(3):
                    t0 = time.perf_counter()
                    rows = parity.compare({**item, 'nodes': [node]})
                    timings.append(time.perf_counter() - t0)
                row['rows'].append({**rows[0], 'median_s': statistics.median(timings)})
            except Exception as exc:
                row['failures'].append(node['name'] + ': ' + str(exc))
        result['native'].append(row)
    result['hashes_unchanged'] = all(digest(Path(p[k])) == p['sha256'] for p in json.loads((work / 'inputs.json').read_text()) for k in ('source', 'copy'))
    result['repeat_equal'] = len(native_data['imports']) == 6 and all(
        a['inventory'] == b['inventory'] and
        [{k: v for k, v in n.items() if not k.endswith('_seconds')} for n in a['nodes']] ==
        [{k: v for k, v in n.items() if not k.endswith('_seconds')} for n in b['nodes']]
        for a, b in zip(native_data['imports'][:3], native_data['imports'][3:]))
    write(work / 'comparison.json', result)
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('stage', choices=['prepare', 'compare'])
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--source', type=Path, default=Path('G:/Мой диск/AGR-evidence/752-ac08-kernel-ops/v002'))
    args = ap.parse_args()
    if args.stage == 'prepare':
        prepare(args.work, args.source)
    else:
        compare(args.work)
