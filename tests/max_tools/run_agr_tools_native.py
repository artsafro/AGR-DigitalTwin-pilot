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
rt.fileIn(str(Path(os.environ.get('AGR_TEST_PACKAGE', ROOT / 'tmp/AGR-Tools-0.3.0.mzp'))))
assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
print('AGR_INSTALL_REGISTERED xView Cleanup MatID Open Nudge NudgeApply Atlas AtlasApply Ucx UcxApply Texel')
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


def make_bitmap(width, height, pixels, name):
    bm = rt.bitmap(width, height, color=rt.color(0, 0, 0, 255))
    for y in range(height):
        row = []
        for x in range(width):
            r, g, b, a = pixels[y * width + x]
            color = rt.color(int(r), int(g), int(b))
            color.a = int(a)
            row.append(color)
        rt.setPixels(bm, rt.point2(0, y), row)
    path = OUT / (name + '.png')
    if path.exists():
        raise AssertionError('bitmap already exists: ' + str(path))
    bm.filename = str(path)
    agr.save_bitmap(bm)
    tex = rt.Bitmaptexture()
    tex.name = name
    tex.filename = str(path)
    return tex


def texture_bitmap(tex):
    bm = None
    try:
        bm = tex.bitmap
    except Exception:
        bm = None
    width = 0
    if bm is not None:
        try:
            width = int(bm.width)
        except Exception:
            width = 0
    if width <= 0:
        bm = rt.openBitMap(str(tex.filename))
    if bm is None:
        raise AssertionError('bitmap did not open: ' + str(tex.filename))
    return bm


def bitmap_pixel(tex, x, y):
    bm = texture_bitmap(tex)
    px = list(rt.getPixels(bm, rt.point2(int(x), int(y)), 1))[0]
    return (int(round(float(px.r))), int(round(float(px.g))), int(round(float(px.b))),
            int(round(float(px.a))), int(bm.width), int(bm.height))


def map_uvs(node):
    count = int(rt.polyop.getNumMapVerts(node, 1))
    out = []
    for index in range(1, count + 1):
        point = rt.polyop.getMapVert(node, 1, index)
        out.append((float(point.x), float(point.y)))
    return out


def sample_uv(tex, u, v):
    bm = texture_bitmap(tex)
    width, height = int(bm.width), int(bm.height)
    x = min(width - 1, max(0, int(u * width + 1e-9)))
    y = min(height - 1, max(0, int((1.0 - v) * height + 1e-9)))
    return bitmap_pixel(tex, x, y)


# getPixels(w*h) stops at one scanline. Row reads still return the whole 8x8 image.
grid = [((x * 20) % 256, (y * 30) % 256, 40, 255 if (x + y) % 2 == 0 else 0) for y in range(8) for x in range(8)]
grid_tex = make_bitmap(8, 8, grid, 'grid8')
grid_bm = texture_bitmap(grid_tex)
span = list(rt.getPixels(grid_bm, rt.point2(0, 0), 64))
one_row = list(rt.getPixels(grid_bm, rt.point2(0, 0), 8))
# Max 2024 returns no pixels when the count crosses the row (measured 0), not the full 8x8 image.
assert len(span) < 64 and len(one_row) == 8, (len(span), len(one_row))
grid_rgb, grid_alpha = agr._bitmap_rgb(grid_tex)
assert len(grid_rgb) == 8 and len(grid_rgb[7]) == 8
assert grid_rgb[7][7] == grid[63][:3] and grid_alpha[7][7] == grid[63][3], (grid_rgb[7][7], grid_alpha[7][7], grid[63])
assert grid_rgb[0][1] == grid[1][:3] and grid_alpha[0][1] == grid[1][3]
results['bitmap_rows'] = {'wide_span': len(span), 'row': len(one_row), 'height': len(grid_rgb),
                           'corner': list(grid_rgb[7][7])}

RED_BLUE_UV = (
    (0.00439453125, 0.995361328125),
    (0.00712890625, 0.995361328125),
    (0.00712890625, 0.99560546875),
    (0.00439453125, 0.99560546875),
)


def atlas_quad(name, tex):
    node = make_uv_quad(name, [(0.1, 0.2), (0.8, 0.2), (0.8, 0.7), (0.1, 0.7)], 'unused=none', 'Wall')
    node.material.diffuseMap = tex
    node.material.diffuse = rt.color(255, 255, 255)
    node.material.opacity = 100
    rt.setUserProp(node, 'AGR_ATLAS_MODE', 'oks')
    rt.setUserProp(node, 'AGR_ATLAS_SIZE', '2048')
    return node


red_blue = [(255, 0, 0, 255)] * 4 + [(0, 0, 255, 255)] * 4
red_tex = make_bitmap(8, 1, red_blue, 'redblue')
red_node = atlas_quad('synthetic_atlas_redblue', red_tex)
red_before = (bitmap_pixel(red_node.material.diffuseMap, 0, 0), bitmap_pixel(red_node.material.diffuseMap, 7, 0))
red_uv_before = map_uvs(red_node)
red_count = len(list(rt.objects))
red_preview = agr.atlas_preview([red_node])
assert red_preview['report']['plan']['cells'] == {'Wall': [0, 0, 24, 19]}, red_preview['report']['plan']['cells']
assert map_uvs(red_node) == red_uv_before
red_copies, _red_after = agr.atlas_apply([red_node], red_preview)
assert map_uvs(red_node) == red_uv_before
assert bitmap_pixel(red_node.material.diffuseMap, 0, 0) == red_before[0]
assert bitmap_pixel(red_node.material.diffuseMap, 7, 0) == red_before[1]
assert int(texture_bitmap(red_node.material.diffuseMap).width) == 8
assert red_copies[0] != red_node
copy_uv = map_uvs(red_copies[0])
for got, exp in zip(copy_uv, RED_BLUE_UV):
    agr.assert_uv_close(got, exp)
copy_tex = red_copies[0].material.diffuseMap
assert int(texture_bitmap(copy_tex).width) == 2048 and int(texture_bitmap(copy_tex).height) == 2048
assert copy_tex != red_node.material.diffuseMap
red_sample = sample_uv(copy_tex, copy_uv[0][0], copy_uv[0][1])
blue_sample = sample_uv(copy_tex, copy_uv[1][0], copy_uv[1][1])
assert red_sample[:3] == (255, 0, 0), red_sample
assert blue_sample[2] > blue_sample[0] and blue_sample[2] > 200, blue_sample
results['atlas_redblue'] = {
    'cells': red_preview['report']['plan']['cells'],
    'copy_uv': copy_uv,
    'source_pixels': [list(p) for p in red_before],
    'atlas_red': list(red_sample),
    'atlas_blue': list(blue_sample),
    'objects_before': red_count,
}

alpha_pixels = [(255, 255, 255, a) for a in (0, 0, 0, 0, 255, 255, 255, 255)]
alpha_tex = make_bitmap(8, 1, alpha_pixels, 'white-alpha')
alpha_node = atlas_quad('synthetic_atlas_alpha', alpha_tex)
alpha_before = bitmap_pixel(alpha_node.material.diffuseMap, 0, 0), bitmap_pixel(alpha_node.material.diffuseMap, 7, 0)
alpha_uv_before = map_uvs(alpha_node)
alpha_preview = agr.atlas_preview([alpha_node])
assert alpha_preview['report']['plan']['cells'] == {'Wall': [0, 0, 24, 19]}, alpha_preview['report']['plan']
assert alpha_preview['images'][0]['kinds']['Wall'] == 'texture'
alpha_copies, _alpha_after = agr.atlas_apply([alpha_node], alpha_preview)
assert map_uvs(alpha_node) == alpha_uv_before
assert bitmap_pixel(alpha_node.material.diffuseMap, 0, 0) == alpha_before[0]
assert bitmap_pixel(alpha_node.material.diffuseMap, 7, 0) == alpha_before[1]
alpha_uv = map_uvs(alpha_copies[0])
for got, exp in zip(alpha_uv, RED_BLUE_UV):
    agr.assert_uv_close(got, exp)
assert alpha_copies[0].material.opacityMap is not None
opaque = sample_uv(alpha_copies[0].material.opacityMap, alpha_uv[1][0], alpha_uv[1][1])
clear = sample_uv(alpha_copies[0].material.opacityMap, alpha_uv[0][0], alpha_uv[0][1])
assert clear[0] == 0, clear
assert opaque[0] > 200, opaque
white = sample_uv(alpha_copies[0].material.diffuseMap, alpha_uv[0][0], alpha_uv[0][1])
assert white[:3] == (255, 255, 255), white
results['atlas_alpha'] = {
    'cells': alpha_preview['report']['plan']['cells'],
    'clear': list(clear),
    'opaque': list(opaque),
    'source_alpha': [alpha_before[0][3], alpha_before[1][3]],
}

opacity_only = make_uv_quad('synthetic_atlas_opacity_only', [(0.1, 0.2), (0.8, 0.2), (0.8, 0.7), (0.1, 0.7)],
                            'unused=none', 'Wall')
opacity_only.material.diffuse = rt.color(20, 140, 40)
opacity_only.material.opacityMap = make_bitmap(8, 1, [(255, 255, 255, 255)] * 8, 'opacity-only')
rt.setUserProp(opacity_only, 'AGR_ATLAS_MODE', 'oks')
rt.setUserProp(opacity_only, 'AGR_ATLAS_SIZE', '2048')
opacity_count = len(list(rt.objects))
results['guards']['atlas_map_d_without_kd'] = raises(
    lambda: agr.atlas_preview([opacity_only]), 'map_d without map_Kd')
assert len(list(rt.objects)) == opacity_count
results['guards']['atlas_map_d_apply_creates_nothing'] = raises(
    lambda: agr.atlas_apply([opacity_only], {'report': {}, 'plans': []}), 'map_d without map_Kd')
assert len(list(rt.objects)) == opacity_count
assert opacity_only.material.diffuseMap is None or str(rt.classOf(opacity_only.material.diffuseMap)) in (
    'undefined', 'UndefinedClass')
results['atlas_opacity_only'] = {'objects': opacity_count, 'created': 0}


def output_files():
    return sorted(path.relative_to(OUT).as_posix() for path in OUT.rglob('*') if path.is_file())


def reject_map_coordinate(node, setting, slot):
    """Preview and apply must name the coordinate and create nothing."""
    before_files = output_files()
    before_count = len(list(rt.objects))
    preview_error = raises(lambda: agr.atlas_preview([node]), 'unsupported map coordinate')
    apply_error = raises(
        lambda: agr.atlas_apply([node], {'report': {}, 'plans': []}), 'unsupported map coordinate')
    assert len(list(rt.objects)) == before_count, 'coordinate rejection created a node'
    assert output_files() == before_files, 'coordinate rejection created a file'
    needle = f'{node.material.name} {slot} {setting}='
    assert needle in preview_error, preview_error
    assert needle in apply_error, apply_error
    return preview_error


def put_coord(tex, setting, value):
    setattr(tex.coords, setting, value)
    return getattr(tex.coords, setting)


# Combined witness: tiled diffuse coordinates must not become a clean untransformed atlas.
witness_pixels = [(255, 255, 255, a) for a in (0, 0, 0, 0, 255, 255, 255, 255)]
witness_tex = make_bitmap(8, 1, witness_pixels, 'witness-tiling')
witness = atlas_quad('synthetic_atlas_coord_witness', witness_tex)
witness.material.name = 'Witness'
witness.material.opacity = 40
put_coord(witness_tex, 'U_Tiling', 2)
witness_files = output_files()
witness_count = len(list(rt.objects))
witness_error = reject_map_coordinate(witness, 'U_Tiling', 'diffuse')
assert witness_error == 'unsupported map coordinate: Witness diffuse U_Tiling=2', witness_error
assert abs(float(witness.material.diffuseMap.coords.U_Tiling) - 2) <= 1e-9
assert abs(float(witness.material.opacity) - 40) <= 1e-9
assert output_files() == witness_files and len(list(rt.objects)) == witness_count
results['atlas_coord_witness'] = {
    'error': witness_error,
    'copies': 0,
    'files': 0,
    'u_tiling': float(witness.material.diffuseMap.coords.U_Tiling),
    'opacity': float(witness.material.opacity),
    'uv': map_uvs(witness),
}

coord_rejections = {}
for case, setting, value, slot in (
    ('u_offset', 'U_Offset', 0.25, 'diffuse'),
    ('v_tiling', 'V_Tiling', 3, 'diffuse'),
    ('u_angle', 'U_Angle', 0.5, 'diffuse'),
    ('u_mirror', 'U_Mirror', True, 'opacity'),
    ('map_channel', 'mapChannel', 2, 'diffuse'),
):
    diffuse = make_bitmap(8, 1, [(255, 0, 0, 255)] * 8, 'coord-' + case)
    node = atlas_quad('synthetic_atlas_coord_' + case, diffuse)
    node.material.name = 'Coord' + case
    if slot == 'opacity':
        opacity = make_bitmap(8, 1, [(128, 128, 128, 255)] * 8, 'coord-' + case + '-opacity')
        node.material.opacityMap = opacity
        target = opacity
    else:
        target = diffuse
    put_coord(target, setting, value)
    message = reject_map_coordinate(node, setting, slot)
    shown = agr.format_map_coordinate_value(getattr(target.coords, setting))
    assert message == f'unsupported map coordinate: {node.material.name} {slot} {setting}={shown}', message
    coord_rejections[case] = message
results['atlas_coord_rejections'] = coord_rejections

for macro in ('AGRToolsNudge', 'AGRToolsAtlas'):
    rt.select(clean_nudge if macro.endswith('Nudge') else atlas_copies[0])
    if macro.endswith('Nudge'):
        rt.setUserProp(clean_nudge, 'AGR_UV_PERIODS', 'brick=none')
    assert rt.macros.run('AGR Tools', macro), macro
results['guards']['registered_uv_buttons'] = 2
# Startup re-registration and repeated install must not overwrite installed files.
rt.AGRToolsRegistered = False
rt.fileIn(str(OUT / 'startup/AGRTools-0.3.0.ms'))
assert rt.AGRToolsRegistered
install_hash = hashlib.sha256((OUT / 'installed/runtime.py').read_bytes()).hexdigest()
results['guards']['repeat_install'] = raises(lambda: rt.fileIn(str(Path(os.environ.get('AGR_TEST_PACKAGE', ROOT / 'tmp/AGR-Tools-0.3.0.mzp')))), 'already exists')
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

# UCX collision and texel readout. Synthetic boxes only; sources are read back unchanged.
rt.units.SystemType = rt.name('meters')
ucx_box = rt.box(name='synthetic_ucx_box', length=1, width=1, height=1)
rt.convertToPoly(ucx_box)
ucx_before = agr.snapshot([ucx_box])
ucx_count = len(list(rt.objects))
ucx_dry = agr.ucx_preview([ucx_box])
assert agr.snapshot([ucx_box]) == ucx_before, 'ucx dry-run mutated its input'
assert len(list(rt.objects)) == ucx_count, 'ucx dry-run created nodes'
assert ucx_dry['report']['plan']['kind'] == 'near-convex-box'
assert ucx_dry['report']['plan']['variant'] == 'single-hull'
assert ucx_dry['report']['plan']['pieces'] == 1 and ucx_dry['report']['plan']['triangles'] == 12
assert findings(ucx_dry['report']) == {}
assert ucx_dry['report']['plan']['names'] == ['UCX_synthetic_ucx_box_01']
ucx_created, ucx_after = agr.ucx_apply([ucx_box], ucx_dry)
assert agr.snapshot([ucx_box]) == ucx_before, 'ucx apply changed the source'
assert len(ucx_created) == 2
assert rt.getNodeByName('UCX_synthetic_ucx_box_01') is not None
assert findings(ucx_after) == {}
bad_kind = rt.box(name='synthetic_ucx_kind', length=1, width=1, height=1)
rt.convertToPoly(bad_kind)
rt.setUserProp(bad_kind, 'AGR_UCX_KIND', 'part-boxes')
kind_count = len(list(rt.objects))
results['guards']['ucx_unmapped_kind'] = raises(lambda: agr.ucx_preview([bad_kind]), 'part-boxes')
assert len(list(rt.objects)) == kind_count

def _corner(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    return [rt.point3(x0, y0, z0), rt.point3(x1, y0, z0), rt.point3(x1, y1, z0), rt.point3(x0, y1, z0),
            rt.point3(x0, y0, z1), rt.point3(x1, y0, z1), rt.point3(x1, y1, z1), rt.point3(x0, y1, z1)]

def _passage():
    verts, faces = [], []
    tris = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    for lo, hi in (((0, 0, 0), (4, 1, 3)), ((0, 1, 0), (1, 4, 3))):
        base = len(verts)
        verts.extend(_corner(lo, hi))
        faces.extend(rt.point3(a + base + 1, b + base + 1, c + base + 1) for a, b, c in tris)
    node = rt.mesh(name='synthetic_ucx_passage', vertices=verts, faces=faces)
    rt.convertToPoly(node)
    return node

passage = _passage()
passage_before = agr.snapshot([passage])
passage_count = len(list(rt.objects))
passage_dry = agr.ucx_preview([passage])
assert agr.snapshot([passage]) == passage_before and len(list(rt.objects)) == passage_count
assert passage_dry['report']['plan']['kind'] == 'passage'
assert passage_dry['report']['plan']['variant'] == 'kernel-boxes'
assert passage_dry['report']['plan']['pieces'] == 2 and passage_dry['report']['plan']['triangles'] == 24, passage_dry['report']['plan']
results['ucx'] = {
    'clean_pieces': 1, 'clean_triangles': 12,
    'planted_pieces': passage_dry['report']['plan']['pieces'],
    'planted_triangles': passage_dry['report']['plan']['triangles'],
    'planted_kind': passage_dry['report']['plan']['kind'],
}

def _rel(a, b):
    return abs(a - b) / max(abs(a), abs(b))

texel_clean = make_uv_quad('synthetic_texel_clean', [(0, 0), (1, 0), (1, 1), (0, 1)], 'unused=none', 'brick')
rt.setUserProp(texel_clean, 'AGR_TEXEL_PROFILE', 'VPM')
rt.setUserProp(texel_clean, 'AGR_TEXEL_MAP', 'brick=1024')
texel_before = agr.snapshot([texel_clean])
texel_count = len(list(rt.objects))
texel_ok = agr.texel_preview([texel_clean])
assert agr.snapshot([texel_clean]) == texel_before and len(list(rt.objects)) == texel_count
assert findings(texel_ok['report']) == {}, texel_ok['report']
clean_min = texel_ok['report']['plan']['meshes'][0]['min_px_per_m']
clean_med = texel_ok['report']['plan']['meshes'][0]['median_px_per_m']
assert _rel(clean_min, 1024.0) < 1e-6 and _rel(clean_med, 1024.0) < 1e-6, (clean_min, clean_med)
texel_bad = make_uv_quad('synthetic_texel_planted', [(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)], 'unused=none', 'brick')
rt.setUserProp(texel_bad, 'AGR_TEXEL_PROFILE', 'VPM')
rt.setUserProp(texel_bad, 'AGR_TEXEL_MAP', 'brick=1024')
texel_planted = agr.texel_preview([texel_bad])
assert findings(texel_planted['report']) == {
    'texel_outside': list(range(1, int(rt.polyop.getNumFaces(texel_bad)) + 1))}, texel_planted['report']
planted_min = texel_planted['report']['plan']['meshes'][0]['min_px_per_m']
assert _rel(planted_min, 102.4) < 1e-6, planted_min
assert agr.snapshot([texel_bad]) == agr.snapshot([texel_bad])
missing = make_uv_quad('synthetic_texel_unmapped', [(0, 0), (1, 0), (1, 1), (0, 1)], 'unused=none', 'brick')
rt.setUserProp(missing, 'AGR_TEXEL_PROFILE', 'VPM')
rt.setUserProp(missing, 'AGR_TEXEL_MAP', 'stone=1024')
results['guards']['texel_unmapped'] = raises(lambda: agr.texel_preview([missing]), 'brick')
results['guards']['texel_empty'] = raises(lambda: agr.texel_preview([]), 'empty')
results['guards']['ucx_empty'] = raises(lambda: agr.ucx_preview([]), 'empty')
for macro, node in (('AGRToolsUcx', ucx_box), ('AGRToolsTexel', texel_clean)):
    rt.select(node)
    assert rt.macros.run('AGR Tools', macro), macro
results['texel'] = {'clean_min': clean_min, 'clean_median': clean_med, 'planted_min': planted_min}
results['guards']['registered_ucx_texel_buttons'] = 2

# Review round 1. Synthetic nodes only. Emitted UCX world bounds are read back.
def _wb(node):
    return ([float(node.min.x), float(node.min.y), float(node.min.z)],
            [float(node.max.x), float(node.max.y), float(node.max.z)])

def _near(got, exp, tol=1e-4):
    worst = max(abs(a - b) for left, right in zip(got, exp) for a, b in zip(left, right))
    assert worst < tol, (got, exp, worst)
    assert abs(worst - tol) > tol * 2e-7

def _shift_box(name, kind, position, scale):
    node = rt.box(name=name, length=1, width=1, height=1)
    if kind == 'mesh':
        rt.convertToMesh(node)
    else:
        rt.convertToPoly(node)
    node.position = rt.point3(*position)
    node.scale = rt.point3(*scale)
    return node

review = {}
world = ([19.0, 29.0, 40.0], [21.0, 31.0, 42.0])
for kind in ('mesh', 'poly'):
    node = _shift_box('review_' + kind, kind, (20, 30, 40), (2, 2, 2))
    before = agr.snapshot([node])
    count = len(list(rt.objects))
    verts, _tris = agr._read_world(node)
    read = ([min(p[a] for p in verts) for a in range(3)], [max(p[a] for p in verts) for a in range(3)])
    _near(read, world)
    preview = agr.ucx_preview([node])
    assert len(list(rt.objects)) == count
    created, report = agr.ucx_apply([node], preview)
    emitted = [item for item in created if str(item.name).startswith('UCX_')]
    assert len(emitted) == 1 and report['status'] == 'pass'
    _near(_wb(emitted[0]), world)
    assert agr.snapshot([node]) == before
    review[kind] = {'read': read, 'emitted': _wb(emitted[0]), 'triangles': preview['report']['plan']['triangles']}

plain = _shift_box('review_plain', 'poly', (5, 6, 7), (1, 1, 1))
plain_bounds = ([4.5, 5.5, 7.0], [5.5, 6.5, 8.0])
pread, _ = agr._read_world(plain)
_near(([min(p[a] for p in pread) for a in range(3)], [max(p[a] for p in pread) for a in range(3)]), plain_bounds)
preview = agr.ucx_preview([plain])
_created, _report = agr.ucx_apply([plain], preview)
_near(_wb([item for item in _created if str(item.name).startswith('UCX_')][0]), plain_bounds)
review['plain'] = {'emitted': _wb([item for item in _created if str(item.name).startswith('UCX_')][0])}

xform = rt.box(name='review_xform', length=1, width=1, height=1)
rt.convertToPoly(xform)
modifier = rt.XForm()
rt.addModifier(xform, modifier)
modifier.gizmo.position = rt.point3(10, 0, 0)
xread, _ = agr._read_world(xform)
xbounds = ([min(p[a] for p in xread) for a in range(3)], [max(p[a] for p in xread) for a in range(3)])
_near(xbounds, ([9.5, -0.5, 0.0], [10.5, 0.5, 1.0]))
xpreview = agr.ucx_preview([xform])
xcreated, _xreport = agr.ucx_apply([xform], xpreview)
_near(_wb([item for item in xcreated if str(item.name).startswith('UCX_')][0]), ([9.5, -0.5, 0.0], [10.5, 0.5, 1.0]))
review['modifier'] = {'read': xbounds, 'triangles': xpreview['report']['plan']['triangles']}

# Clipped cube x+y+z <= 2.8, then the same world transform. Hull is 16 triangles, not the 12 of an AABB.
clip_pts = [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
            (1.0, 0.0, 1.0), (1.0, 0.8, 1.0), (0.8, 1.0, 1.0), (0.0, 1.0, 1.0), (1.0, 1.0, 0.8)]
clip_faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (4, 7, 8), (0, 3, 5), (0, 5, 4),
              (3, 2, 9), (3, 9, 6), (3, 6, 5), (2, 1, 8), (2, 8, 7), (2, 7, 9), (1, 0, 4),
              (1, 4, 8), (7, 6, 9)]
clip = rt.mesh(name='review_clipped', vertices=[rt.point3(*p) for p in clip_pts],
               faces=[rt.point3(a + 1, b + 1, c + 1) for a, b, c in clip_faces])
rt.convertToPoly(clip)
clip.position = rt.point3(20, 30, 40)
clip.scale = rt.point3(2, 2, 2)
cpreview = agr.ucx_preview([clip])
assert cpreview['report']['plan']['triangles'] == 16, cpreview['report']['plan']
assert cpreview['report']['plan']['kind'] == 'near-convex-box'
ccreated, creport = agr.ucx_apply([clip], cpreview)
cemitted = [item for item in ccreated if str(item.name).startswith('UCX_')]
assert len(cemitted) == 1 and creport['status'] == 'pass'
emitted_mesh = rt.snapshotAsMesh(cemitted[0])
assert int(emitted_mesh.numfaces) == 16, int(emitted_mesh.numfaces)
# The clipped cube sits on 0..1, so scale 2 about the origin plus (20,30,40) is not the centred box.
_near(_wb(cemitted[0]), ([20.0, 30.0, 40.0], [22.0, 32.0, 42.0]))
review['clipped'] = {'triangles': 16, 'emitted': _wb(cemitted[0]),
                     'faces': int(emitted_mesh.numfaces)}

stale = rt.box(name='review_stale', length=1, width=1, height=1)
rt.convertToPoly(stale)
stale_preview = agr.ucx_preview([stale])
stale_count = len(list(rt.objects))
stale.position = rt.point3(10, 0, 0)
results['guards']['ucx_stale_preview'] = raises(lambda: agr.ucx_apply([stale], stale_preview), 'stale')
assert len(list(rt.objects)) == stale_count
review['stale_nodes'] = 0

named = rt.box(name='name_control', length=1, width=1, height=1)
rt.convertToPoly(named)
first, first_report = agr.ucx_apply([named], agr.ucx_preview([named]))
assert [str(item.name) for item in first] == ['name_control_AGR_ucx_', 'UCX_name_control_01']
assert first_report['status'] == 'pass'
name_count = len(list(rt.objects))
results['guards']['ucx_occupied_name'] = raises(lambda: agr.ucx_apply([named], agr.ucx_preview([named])), 'occupied name')
assert len(list(rt.objects)) == name_count
assert 'name_control' in results['guards']['ucx_occupied_name']

planted_src = rt.box(name='occupied_src', length=1, width=1, height=1)
rt.convertToPoly(planted_src)
rt.box(name='UCX_occupied_src_01', length=0.2, width=0.2, height=0.2)
planted_count = len(list(rt.objects))
results['guards']['ucx_existing_name'] = raises(lambda: agr.ucx_apply([planted_src], agr.ucx_preview([planted_src])), 'UCX_occupied_src_01')
assert len(list(rt.objects)) == planted_count

left = rt.box(name='same_name', length=1, width=1, height=1)
right = rt.box(name='same_name', length=1, width=1, height=1)
rt.convertToPoly(left)
rt.convertToPoly(right)
same_count = len(list(rt.objects))
results['guards']['ucx_same_name_selection'] = raises(
    lambda: agr.ucx_apply([left, right], agr.ucx_preview([left, right])), 'same_name_AGR_ucx_')
assert len(list(rt.objects)) == same_count
review['names'] = {'second_apply_nodes': 0, 'existing_name_nodes': 0, 'same_name_nodes': 0}
results['review'] = review
print('AGR_REVIEW_R1 mesh=1 poly=1 plain=1 modifier=1 clipped_tris=16 stale=1 names=1')
with (OUT / 'results.json').open('x', encoding='utf-8') as f:
    json.dump(results, f, indent=2, default=str, allow_nan=False)
    print('AGR_NATIVE_UCX_TEXEL clean=2 planted=2 dry_run_unchanged=true originals_unchanged=true texel_read_only=true')
    print('AGR_NATIVE_COMPLETE clean=3 planted=3 dry_run_unchanged=true originals_unchanged=true')
