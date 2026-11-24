"""Native readback of each delivery driver's FBX write boundary on the same crease.

Exercise the actual operator call and all its options, not the surrounding
model preparation. Existing route tests cover full driver invocations.
"""
from pathlib import Path

import pytest

from dt_ai.core.blender_runner import blender_executable, run_blender

ROOT = Path(__file__).resolve().parents[2]
WRITERS = (
    'tools/derive/export_npm.py',
    'tools/blender/ground_json_to_fbx.py',
    'tools/blender/ucx_build.py',
    'tools/blender/ucx_resolve.py',
    'tools/blender/maf_gen_bench_build.py',
    'tools/blender/maf_site_set_build.py',
    'tools/materials/bind_ground_textures_blender.py',
)

DRIVER = '''\
import ast
import json
from pathlib import Path
import sys

import bpy
from io_scene_fbx import parse_fbx


def only(parent, tag):
    node, = (el for el in parent.elems if el.id == tag)
    return node


def write_probe(writer, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new('crease')
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)], [],
                     [(0, 1, 2), (1, 0, 3), (1, 3, 4)])
    mesh.update()
    for face in mesh.polygons:
        face.use_smooth = True
    for edge in mesh.edges:
        edge.use_edge_sharp = set(edge.vertices) == {1, 3}
    obj = bpy.data.objects.new('crease', mesh)
    bpy.context.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.scene.unit_settings.system = 'METRIC'

    tree = ast.parse(writer.read_text(encoding='utf-8'), filename=str(writer))
    call, = (n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and ast.unparse(n.func) == 'bpy.ops.export_scene.fbx')
    # Inject only the destination and the binder's texture embedding flag. The
    # smoothing option comes from the actual driver and is never set here.
    result = eval(compile(ast.Expression(call), str(writer), 'eval'),
                  dict(bpy=bpy, fbx=str(path), out=str(path), fbx_out=path, out_fbx=path, embed=False))
    assert result == {'FINISHED'}, result
    root, version = parse_fbx.parse(str(path))
    geom = only(only(root, b'Objects'), b'Geometry')
    smoothing = only(geom, b'LayerElementSmoothing')
    return dict(version=version,
                mapping=only(smoothing, b'MappingInformationType').props[0].decode(),
                reference=only(smoothing, b'ReferenceInformationType').props[0].decode(),
                polygon_vertices=list(only(geom, b'PolygonVertexIndex').props[0]),
                masks=list(only(smoothing, b'Smoothing').props[0]))

out, *writers = map(Path, sys.argv[sys.argv.index('--') + 1:])
report = {str(writer): write_probe(writer, out.parent / (writer.stem + '.fbx')) for writer in writers}
with out.open('x', encoding='utf-8') as stream:
    json.dump(report, stream)
'''


@pytest.fixture(scope='module')
def native_readback(tmp_path_factory):
    if not Path(blender_executable()).is_file():
        pytest.skip('Pinned Blender is not installed (opt-in Blender test)')
    work = tmp_path_factory.mktemp('delivery-smoothing')
    script = work / 'probe.py'
    script.write_text(DRIVER, encoding='utf-8')
    report = work / 'masks.json'
    return run_blender(script, [report, *(ROOT / path for path in WRITERS)], output_json=report,
                       log_path=work / 'blender.log', timeout=120)


@pytest.mark.blender
@pytest.mark.parametrize('writer', WRITERS, ids=lambda path: Path(path).stem)
def test_delivery_fbx_preserves_polygon_smoothing_groups(writer, native_readback):
    data = native_readback[str(ROOT / writer)]
    assert data['version'] == 7400
    assert (data['mapping'], data['reference']) == ('ByPolygon', 'Direct')
    assert data['polygon_vertices'] == [0, 1, -3, 1, 0, -4, 1, 3, -5]
    a, b, c = data['masks']
    assert a & b, f"authored smooth edge lost: {data['masks']}"
    assert c and not b & c, f"authored sharp edge lost: {data['masks']}"
