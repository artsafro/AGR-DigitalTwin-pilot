"""new-case: synthetic-only installed-MZP acceptance in locked batch Max.

Run via dcc_batch.py; AGR_TEST_OUTPUT must name a NEW directory, never a scene.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
print('AGR_NATIVE_START version={} file={} units={}'.format(rt.maxVersion()[0], rt.maxFileName, rt.units.SystemType))
assert rt.maxVersion()[0] in (26000, 28000)
assert not rt.maxFileName, 'only an empty batch document is allowed'
rt.units.SystemType = rt.name('meters')

# No user scripts/startup folders are modified during headless installation.
rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
rt.makeDir(rt.AGRToolsStartupRoot, all=True)
rt.fileIn(str(Path(os.environ.get('AGR_TEST_PACKAGE', ROOT / 'tmp/AGR-Tools-0.2.0.mzp'))))
assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
print('AGR_INSTALL_REGISTERED xView Cleanup MatID Open Nudge NudgeApply Atlas AtlasApply')
sys.path.insert(0, str(OUT / 'installed'))
import runtime as agr


def findings(report):
    agr.parse_report(json.dumps(report))
    return {f['code']: f['ids'] for o in report['objects'] for f in o['findings']}


def raises(fn, word):
    try:
        fn()
    except (ValueError, RuntimeError) as e:
        assert word.lower() in str(e).lower(), str(e)
        return str(e)
    raise AssertionError('expected rejection: ' + word)


clean = rt.box(name='synthetic_clean', length=1, width=1, height=1, mapcoords=True)
rt.convertToPoly(clean)
clean.material = rt.standardMaterial(name='synthetic_material')
rt.setUserPropBuffer(clean, 'MapChannel:1 = UV\r\n')
rt.saveMaxFile(str(OUT / 'fixture-source.max'), quiet=True)
shutil.copyfile(OUT / 'fixture-source.max', OUT / 'fixture-copy.max')
source_hash = hashlib.sha256((OUT / 'fixture-source.max').read_bytes()).hexdigest()
rt.loadMaxFile(str(OUT / 'fixture-copy.max'), quiet=True)
clean = rt.getNodeByName('synthetic_clean')
results = {'clean': {}, 'defective': {}, 'guards': {}}
for tool in ('xview', 'matid'):
    report = getattr(agr, tool)([clean])
    assert findings(report) == {}, report
    results['clean'][tool] = report
preview = agr.cleanup_preview([clean])
assert findings(preview['report']) == {}, preview
results['clean']['cleanup'] = preview['report']

bad = rt.mesh(name='synthetic_planted', vertices=[rt.point3(0,0,0),rt.point3(1,0,0),rt.point3(0,1,0),
              rt.point3(0,0,0.001),rt.point3(1,0,0.001),rt.point3(0,1,0.001)],
              faces=[rt.point3(1,2,3),rt.point3(4,5,6)])
rt.convertToPoly(bad)
rt.polyop.setMapSupport(bad, 1, True)
rt.polyop.setMapSupport(bad, 2, True)
rt.polyop.setFaceMatID(bad, 1, 1001)
rt.polyop.setFaceMatID(bad, 2, 2)
bad.material = rt.multiMaterial(numsubs=2)
bad.material.materialList[0] = rt.standardMaterial()
bad.material.materialList[1] = None
rt.setUserPropBuffer(bad, 'note=planted\r\nMapChannel:1 = wrong\r\nMapChannel:2 = extra\r\n')
rt.execute('global AGRSyntheticCA = attributes AGRSyntheticCA (parameters p (value type:#float default:7.0))')
rt.custAttributes.add(bad.baseObject, rt.AGRSyntheticCA)
rt.execute('custAttributes.add (getNodeByName "synthetic_planted") AGRSyntheticCA baseObject:false')
rt.addModifier(bad, rt.bend())
rt.custAttributes.add(bad.modifiers[0], rt.AGRSyntheticCA)
rt.custAttributes.add(bad.material.materialList[0], rt.AGRSyntheticCA)
report = agr.xview([bad])
assert findings(report) == {'overlap_vertices': [1,2,3,4,5,6], 'overlap_faces': [1,2]}, report
assert list(rt.selection) == [bad]
results['defective']['xview'] = report
report = agr.matid([bad])
assert findings(report) == {'udim_id': [1], 'empty_slot': [1,2]}, report
results['defective']['matid'] = report
before = agr.snapshot([bad])
preview = agr.cleanup_preview([bad])
assert agr.snapshot([bad]) == before, 'dry-run mutated its input'
assert set(findings(preview['report'])) == {'remove_custom_attributes', 'clear_user_defined_lines',
                                         'delete_map_channels', 'rename_map_channel_1'}, preview
results['defective']['cleanup'] = preview['report']
copies, after = agr.cleanup_apply([bad], preview)
assert agr.snapshot([bad]) == before, 'cleanup changed originals/shared material'
assert findings(after) == {}, after
assert len(copies) == 1 and copies[0] != bad
copy_state = agr.snapshot(copies)[0]
for key in ('vertices', 'faces', 'ids'):
    assert copy_state['geometry'][key] == before[0]['geometry'][key], key
assert copy_state['geometry']['maps']['1'] == before[0]['geometry']['maps']['1']
results['defective']['cleanup_after'] = after
rt.setUserPropBuffer(bad, 'changed after preview')
count = len(list(rt.objects))
results['guards']['stale_preview'] = raises(lambda: agr.cleanup_apply([bad], preview), 'stale')
assert len(list(rt.objects)) == count
for tool in (agr.xview, agr.matid, agr.cleanup_preview):
    results['guards'][tool.__name__ + '_empty'] = raises(lambda: tool([]), 'empty')
    results['guards'][tool.__name__ + '_duplicate'] = raises(lambda: tool([clean, clean]), 'duplicate')
# Exercise registered button macros, not only imported Python cores.
for macro in ('AGRToolsXView', 'AGRToolsCleanup', 'AGRToolsMatID'):
    rt.select(clean)
    assert rt.macros.run('AGR Tools', macro), macro
results['guards']['registered_buttons'] = 3
# Exactly-at-threshold is not allowed to become a false clean verdict.
edge = rt.mesh(name='synthetic_boundary', vertices=[rt.point3(0,0,0),rt.point3(1,0,0),rt.point3(0,1,0),
               rt.point3(0,0,0.002),rt.point3(10,0,2),rt.point3(0,10,2)],
               faces=[rt.point3(1,2,3),rt.point3(4,5,6)])
rt.convertToPoly(edge)
results['guards']['vertex_at_2mm'] = raises(lambda: agr.xview([edge]), 'threshold')
# Repeated/reset, unsupported and missing-data controls; preserve native units/tolerances.
prior = (rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance)
rt.units.SystemType = rt.name('millimeters')
scaled = rt.copy(bad)
# Geometry remains expressed in current system units: scale to the same metre distances.
rt.scale(scaled, rt.point3(1000,1000,1000))
assert findings(agr.xview([scaled])) == {'overlap_vertices': [1,2,3,4,5,6], 'overlap_faces': [1,2]}
assert (rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance) == prior
rt.units.SystemType = rt.name('meters')
results['guards']['millimeter_units'] = True
for mid in (999, 1000, 1001, 1002):
    rt.polyop.setFaceMatID(clean, 1, mid)
    assert findings(agr.matid([clean])) == ({'udim_id': [1]} if mid >= 1001 else {})
rt.polyop.setFaceMatID(clean, 1, 1)
results['guards']['material_boundary'] = 4
clean.material = None
assert findings(agr.matid([clean])) == {'missing_material': [1,2,3,4,5,6]}
clean.material = rt.standardMaterial()
helper = rt.point()
empty = rt.mesh(vertices=[], faces=[])
rt.setNumFaces(empty, 0)
rt.setNumVerts(empty, 0)
rt.update(empty)
assert int(empty.numfaces) == 0 and int(empty.numverts) == 0
for tool in (agr.xview, agr.matid, agr.cleanup_preview):
    results['guards'][tool.__name__ + '_unsupported'] = raises(lambda: tool([helper]), 'unsupported')
    results['guards'][tool.__name__ + '_empty_mesh'] = raises(lambda: tool([empty]), 'empty')
# Missing channel is an error, not a guessed UV repair.
rt.polyop.setMapSupport(clean, 1, False)
results['guards']['missing_uv'] = raises(lambda: agr.cleanup_preview([clean]), 'missing')
rt.polyop.setMapSupport(clean, 1, True)
rt.polyop.defaultMapFaces(clean, 1)


def map_array(indices):
    return rt.execute('#(' + ','.join(str(int(i)) for i in indices) + ')')


def make_uv_quad(name, uvs, periods, material='brick'):
    node = rt.mesh(name=name, vertices=[rt.point3(0, 0, 0), rt.point3(1, 0, 0), rt.point3(1, 1, 0), rt.point3(0, 1, 0)],
                   faces=[rt.point3(1, 2, 3), rt.point3(1, 3, 4)])
    rt.convertToPoly(node)
    rt.polyop.setMapSupport(node, 1, True)
    rt.polyop.setNumMapVerts(node, 1, 4)
    for index, uv in enumerate(uvs, 1):
        rt.polyop.setMapVert(node, 1, index, rt.point3(float(uv[0]), float(uv[1]), 0))
    face_count = int(rt.polyop.getNumFaces(node))
    if face_count == 1:
        rt.polyop.setMapFace(node, 1, 1, map_array((1, 2, 3, 4)))
    elif face_count == 2:
        rt.polyop.setMapFace(node, 1, 1, map_array((1, 2, 3)))
        rt.polyop.setMapFace(node, 1, 2, map_array((1, 3, 4)))
    else:
        raise AssertionError('unexpected synthetic face count: ' + str(face_count))
    node.material = rt.standardMaterial(name=material)
    rt.setUserProp(node, 'AGR_UV_PERIODS', periods)
    return node


planted_uv = [(3.2, -1.8), (3.7, -1.8), (3.7, -1.3), (3.2, -1.3)]
nudged = make_uv_quad('synthetic_nudge_planted', planted_uv, 'brick=1,1')
before_nudge = agr.snapshot([nudged])
nudge_preview = agr.nudge_preview([nudged])
assert agr.snapshot([nudged]) == before_nudge, 'nudge dry-run mutated its input'
assert findings(nudge_preview['report']) == {
    'tile_move': list(range(1, int(rt.polyop.getNumFaces(nudged)) + 1))}, nudge_preview['report']
assert nudge_preview['report']['plan']['islands'][0]['steps'] == [-3, 2]
assert nudge_preview['report']['plan']['dropped'] == []
nudge_copies, nudge_after = agr.nudge_apply([nudged], nudge_preview)
assert agr.snapshot([nudged]) == before_nudge, 'nudge apply changed the source'
assert nudge_copies[0] != nudged
readback = [(round(p[0], 6), round(p[1], 6)) for p in agr.nudge_preview([nudge_copies[0]])['state'][0]['uvs']]
assert readback == [(0.2, 0.2), (0.7, 0.2), (0.7, 0.7), (0.2, 0.7)], readback
clean_nudge = make_uv_quad('synthetic_nudge_clean', planted_uv, 'brick=none')
clean_before = [tuple(p) for p in agr.nudge_preview([clean_nudge])['state'][0]['uvs']]
assert findings(agr.nudge_preview([clean_nudge])['report']) == {}
assert [tuple(p) for p in agr.nudge_preview([clean_nudge])['state'][0]['uvs']] == clean_before
results['nudge'] = {'planted_steps': [-3, 2], 'readback': readback, 'clean_findings': {}}
results['guards']['nudge_unmapped'] = raises(lambda: agr.nudge_preview([
    make_uv_quad('synthetic_nudge_unmapped', planted_uv, 'other=1,1')]), 'brick')
results['guards']['nudge_empty'] = raises(lambda: agr.nudge_preview([]), 'empty')
rt.setUserProp(nudged, 'AGR_UV_PERIODS', 'brick=0.5,0.5')
count = len(list(rt.objects))
results['guards']['nudge_stale'] = raises(lambda: agr.nudge_apply([nudged], nudge_preview), 'stale')
assert len(list(rt.objects)) == count
rt.setUserProp(nudged, 'AGR_UV_PERIODS', 'brick=1,1')
# UDIM -> NPM atlas on one triangulated quad. Parity with the Python tool is checked
# from the saved input/output coordinates after this process (no numpy in Max).
atlas_node = make_uv_quad('synthetic_atlas_planted', [(0.1, 0.2), (0.8, 0.2), (0.8, 0.7), (0.1, 0.7)], 'unused=none', 'Grass')
atlas_node.material.diffuse = rt.color(20, 140, 40)
rt.setUserProp(atlas_node, 'AGR_ATLAS_MODE', 'ground')
rt.setUserProp(atlas_node, 'AGR_ATLAS_SIZE', '2048')
# The quad above is 1 m, not the 4 x 3 m parity quad. Rebuild vertex positions.
for index, point in enumerate(((0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0)), 1):
    rt.polyop.setVert(atlas_node, index, rt.point3(*point))
atlas_before = agr.snapshot([atlas_node])
atlas_preview = agr.atlas_preview([atlas_node])
assert agr.snapshot([atlas_node]) == atlas_before, 'atlas dry-run mutated its input'
assert atlas_preview['report']['plan']['tiles'] == [1001], atlas_preview['report']
assert findings(atlas_preview['report']) == {
    'atlas_cell': list(range(1, len(atlas_preview['state'][0]['faces']) + 1))}, atlas_preview['report']
assert atlas_preview['report']['plan']['dropped'] == []
atlas_copies, atlas_after = agr.atlas_apply([atlas_node], atlas_preview)
assert agr.snapshot([atlas_node]) == atlas_before, 'atlas apply changed the source'
clean_atlas = agr.atlas_preview(atlas_copies)
assert findings(clean_atlas['report']) == {}, clean_atlas['report']
cross = make_uv_quad('synthetic_atlas_cross', [(0.2, 0.2), (1.2, 0.2), (1.2, 0.8), (0.2, 0.8)], 'unused=none', 'Grass')
rt.setUserProp(cross, 'AGR_ATLAS_MODE', 'ground')
rt.setUserProp(cross, 'AGR_ATLAS_SIZE', '2048')
results['guards']['atlas_cross'] = raises(lambda: agr.atlas_preview([cross]), 'crosses a UDIM')
results['guards']['atlas_unmapped_mode'] = raises(lambda: agr.atlas_preview([clean_nudge]), 'mode')
bare = make_uv_quad('synthetic_atlas_bare', [(0.1, 0.2), (0.8, 0.2), (0.8, 0.7), (0.1, 0.7)], 'unused=none', 'Missing')
bare.material = None
rt.setUserProp(bare, 'AGR_ATLAS_MODE', 'ground')
rt.setUserProp(bare, 'AGR_ATLAS_SIZE', '2048')
results['guards']['atlas_missing_material'] = raises(lambda: agr.atlas_preview([bare]), 'missing material')
state = atlas_preview['state'][0]
copy_state = agr.atlas_preview(atlas_copies)['state'][0]
results['atlas'] = {
    'tiles': atlas_preview['report']['plan']['tiles'],
    'cells': atlas_preview['report']['plan']['cells'],
    'vertices': state['vertices'], 'uvs': state['uvs'], 'faces': state['faces'],
    'face_uvs': state['face_uvs'], 'materials': ['Grass'] * len(state['faces']),
    'color': [20, 140, 40], 'copy_uvs': copy_state['uvs'], 'copy_face_uvs': copy_state['face_uvs'],
    'clean_findings': findings(clean_atlas['report'])}
for macro in ('AGRToolsNudge', 'AGRToolsAtlas'):
    rt.select(clean_nudge if macro.endswith('Nudge') else atlas_copies[0])
    if macro.endswith('Nudge'):
        rt.setUserProp(clean_nudge, 'AGR_UV_PERIODS', 'brick=none')
    assert rt.macros.run('AGR Tools', macro), macro
results['guards']['registered_uv_buttons'] = 2
# Startup re-registration and repeated install must not overwrite installed files.
rt.AGRToolsRegistered = False
rt.fileIn(str(OUT / 'startup/AGRTools-0.2.0.ms'))
assert rt.AGRToolsRegistered
install_hash = hashlib.sha256((OUT / 'installed/runtime.py').read_bytes()).hexdigest()
results['guards']['repeat_install'] = raises(lambda: rt.fileIn(str(Path(os.environ.get('AGR_TEST_PACKAGE', ROOT / 'tmp/AGR-Tools-0.2.0.mzp')))), 'already exists')
assert hashlib.sha256((OUT / 'installed/runtime.py').read_bytes()).hexdigest() == install_hash
assert hashlib.sha256((OUT / 'fixture-source.max').read_bytes()).hexdigest() == source_hash
results['version'] = list(rt.maxVersion())
results['source_sha256'] = source_hash
# R1: native xView must measure physical, not unbaked object-space distances.
# Exercise the installed package, including the earlier boundary/unit guards.
transform_results = []
for units, factor in (('meters', 1), ('millimeters', 1000)):
    rt.units.SystemType = rt.name(units)
    for case, scale, parent_scale in (
        ('identity', (1, 1, 1), None),
        ('uniform_small', (.1, .1, .1), None),
        ('uniform_large', (10, 10, 10), None),
        ('nonuniform_small', (2, .5, .1), None),
        ('nonuniform_large', (.5, 2, 10), None),
        ('mirrored', (-2, .5, .1), None),
        ('parent_small', (1, 1, 1), (2, .5, .1)),
        ('parent_large', (1, 1, 1), (-.5, 2, 10)),
        ('parent_shear', (1, 1, 1), (2, .5, .1)),
        ('mirrored_z', (2, .5, -1), None),
    ):
        for gap_mm in (1, 2, 4.99, 5, 5.01, 10):
            z_scale = abs(scale[2] * (parent_scale[2] if parent_scale else 1))
            gap = gap_mm / 1000 * factor / z_scale
            n = rt.mesh(name='synthetic_transform_' + case,
                        vertices=[rt.point3(0,0,0), rt.point3(factor,0,0), rt.point3(0,factor,0),
                                  rt.point3(0,0,gap), rt.point3(factor,0,gap), rt.point3(0,factor,gap)],
                        faces=[rt.point3(1,2,3), rt.point3(4,5,6)])
            rt.convertToPoly(n)
            parent = None
            if parent_scale:
                parent = rt.point(name='synthetic_parent')
                n.parent = parent
                if case == 'parent_shear':
                    rt.rotate(n, rt.angleaxis(45, rt.point3(0, 0, 1)))
                rt.scale(parent, rt.point3(*parent_scale))
            rt.scale(n, rt.point3(*scale))
            before = agr.snapshot([n])
            transforms = (str(n.transform), str(n.objectTransform), str(n.parent),
                          str(parent.transform) if parent else None)
            count = len(list(rt.objects))
            tolerances = (rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance)
            measured_mm = float(rt.distance(rt.polyop.getVert(n, 1), rt.polyop.getVert(n, 4))) / factor * 1000
            assert abs(measured_mm - gap_mm) < .0001
            row = {'case': case, 'units': units, 'gap_mm': gap_mm, 'measured_mm': measured_mm}
            try:
                if gap_mm == 2:
                    row['error'] = raises(lambda: agr.xview([n]), 'threshold')
                elif gap_mm == 5:
                    try:
                        row['report'] = agr.xview([n])
                    except (ValueError, RuntimeError) as e:
                        assert 'threshold' in str(e).lower(), str(e)
                        row['error'] = str(e)
                    else:
                        assert findings(row['report']) == {'overlap_faces': [1,2]}, row['report']
                else:
                    row['report'] = agr.xview([n])
                    expected = ({'overlap_vertices': [1,2,3,4,5,6], 'overlap_faces': [1,2]} if gap_mm == 1
                                else {'overlap_faces': [1,2]} if gap_mm <= 5 else {})
                    assert findings(row['report']) == expected, row['report']
                    assert list(rt.selection) == ([n] if gap_mm <= 5 else [])
                row['passed'] = True
            except AssertionError as e:
                row['passed'] = False
                row['failure'] = str(e)
            assert agr.snapshot([n]) == before, 'xView changed source geometry/attributes'
            assert transforms == (str(n.transform), str(n.objectTransform), str(n.parent),
                                  str(parent.transform) if parent else None), 'xView changed transforms/hierarchy'
            assert count == len(list(rt.objects)), 'xView leaked temporary geometry'
            assert tolerances == (rt.OverlappingVertices.tolerance, rt.OverlappingFaces.tolerance)
            transform_results.append(row)
            rt.delete(n)
            if parent:
                rt.delete(parent)
rt.units.SystemType = rt.name('meters')
with (OUT / 'transform-results.json').open('x', encoding='utf-8') as f:
    json.dump(transform_results, f, indent=2)
assert all(row['passed'] for row in transform_results), 'physical-distance transform regressions: ' + str([r for r in transform_results if not r['passed']])
results['guards']['physical_distance_transforms'] = len(transform_results)
with (OUT / 'results.json').open('x', encoding='utf-8') as f:
    json.dump(results, f, indent=2, default=str, allow_nan=False)
    print('AGR_NATIVE_COMPLETE clean=3 planted=3 dry_run_unchanged=true originals_unchanged=true')
