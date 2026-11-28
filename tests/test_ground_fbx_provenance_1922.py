"""new-case: Ground producer provenance across synthetic FBX round trips, without Blender."""
import hashlib
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from adapters.max.agr_tools.export_meta import load_meta, record_export

ROOT = Path(__file__).resolve().parents[1]
UCX = ROOT / 'tools/blender/ucx_build.py'
BIND = ROOT / 'tools/materials/bind_ground_textures_blender.py'
OFFSET = [1254.25, -362.5, 0.0]
GROUND = 'SM_Sample_Ground'


def side(path, suffix):
    return path.with_name(path.name + '.' + suffix + '.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


class Matrix(tuple):
    def __matmul__(self, xyz):
        return Point(sum(row[i] * xyz[i] for i in range(3)) + row[3] for row in self[:3])


class Point(tuple):
    z = property(lambda self: self[2])


IDENTITY = Matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    src = tmp_path / 'source.fbx'
    src.write_bytes(b'synthetic-source-fbx')
    placement = {'fbx': str(src), 'crs': 'SYNTHETIC_LOCAL', 'origin_msk77_xyz': OFFSET,
                 'mesh_xyz = msk77_xyz - origin_msk77_xyz': True, 'object_location': [0.0, 0.0, 0.0]}
    write_json(side(src, 'placement'), placement)
    preview = tmp_path / 'previous.jpg'
    preview.write_bytes(b'previous preview')
    record_export(src, source='synthetic build', top=4, address='Sample_Ground', profile='vpm', thumbnail=preview)
    mesh = NS(name=GROUND, type='MESH', matrix_world=IDENTITY, location=(0, 0, 0),
              data=NS(vertices=[NS(co=p) for p in [(-1, -1, 3), (1, -1, 4), (-1, 1, 3)]],
                      loop_triangles=[0], calc_loop_triangles=lambda: None), select_set=lambda _: None)
    piece = NS(name='UCX_' + GROUND + '_001', data=mesh.data, select_set=lambda _: None)
    result = NS(pieces=[piece], triangles=1, budget=15000, cell_m=16, gap_m=.005, angle_deg=0,
                attempts=[], max_vertical_dev_m=0, footprint_overhang_bound_m=0, uncovered_strip_m=0,
                within_tol=True)
    scene = NS(objects=[mesh])
    state = NS(export_count=0, on_export=lambda: None, on_import=lambda _: None, result=result, mesh=mesh)

    def load(filepath):
        path = Path(filepath)
        assert path.is_file()
        state.on_import(path)
        return {'FINISHED'}

    def export(filepath, **_kw):
        state.export_count += 1
        Path(filepath).write_bytes(f'synthetic-export-{state.export_count}'.encode())
        state.on_export()
        return {'FINISHED'}

    bpy = NS(app=NS(version_string='synthetic'), context=NS(scene=scene), data=NS(materials=[]), ops=NS(
        wm=NS(read_factory_settings=lambda **_: None, open_mainfile=lambda filepath: load(filepath)),
        import_scene=NS(fbx=load), export_scene=NS(fbx=export), object=NS(select_all=lambda **_: None)))
    monkeypatch.setitem(sys.modules, 'bpy', bpy)
    ucx = runpy.run_path(str(UCX))
    monkeypatch.setitem(ucx['main'].__globals__, 'build_into_scene', lambda *_, **__: ([piece], result))
    socket = NS(links=[])
    bsdf = NS(type='BSDF_PRINCIPLED', inputs={'Base Color': socket})

    class Nodes(list):
        def new(self, _):
            return NS(outputs={'Color': object()})

    material = NS(name='M_Sample_Ground_Paving', node_tree=NS(nodes=Nodes([bsdf]), links=NS(new=lambda *_: None)))
    bpy.data.images = NS(load=lambda _: NS(colorspace_settings=NS(), pack=lambda: None))
    bpy.data.materials.append(material)
    (tmp_path / 'diffuse.png').write_bytes(b'synthetic diffuse')

    spec = {'profile': 'vpm', 'texture_root': str(tmp_path),
            'bindings': [{'material': material.name, 'file': 'diffuse.png'}]}

    def collision(source, output, target='Ground'):
        monkeypatch.setattr(sys, 'argv', [str(UCX), '--', str(source), str(output), target])
        return ucx['main']()

    def bind(source, output):
        plan = write_json(tmp_path / 'plan.json', spec)
        monkeypatch.setattr(sys, 'argv', [str(BIND), '--', 'bind', str(source), str(plan), str(output)])
        runpy.run_path(str(BIND), run_name='__main__')

    return NS(source=src, placement=placement, spec=spec, state=state, collision=collision, bind=bind)


def test_off_origin_build_ucx_bind_and_bind_only(pipeline, tmp_path):
    src = pipeline.source
    collision = tmp_path / 'collision.fbx'
    final = tmp_path / 'final.fbx'
    bind_only = tmp_path / 'bind_only.fbx'
    original = {p: p.read_bytes() for p in (src, side(src, 'placement'), side(src, 'export_meta'))}
    assert pipeline.collision(src, collision) == 0
    assert load_meta(side(collision, 'export_meta'))['thumbnail'] == 'unknown'
    pipeline.bind(collision, final)
    thumb = tmp_path / 'fresh.jpg'
    thumb.write_bytes(b'synthetic sourced preview for bind only')
    pipeline.spec['thumbnail'] = thumb.name
    pipeline.bind(src, bind_only)
    for old, out, expected_thumbnail in [(src, collision, 'unknown'), (collision, final, 'unknown'),
                                          (src, bind_only, str(thumb))]:
        placement_path = side(out, 'placement')
        placement = json.loads(placement_path.read_text(encoding='utf-8'))
        meta_path = side(out, 'export_meta')
        meta = load_meta(meta_path)
        assert placement == dict(pipeline.placement, fbx=str(out), fbx_sha256=sha(out))
        assert meta['exported_sha256'] == {out.name: sha(out)}
        assert sha(out) != sha(old) == meta['master_sha256']
        assert meta['h_otn_model_max_z_m'] == 4
        assert meta['profile'] == 'vpm'
        assert meta['thumbnail'] == expected_thumbnail
        print(f'{old.name}: {side(old, "placement").name}, {side(old, "export_meta").name}, {sha(old)} -> '
              f'{out.name}: {placement_path.name}, {meta_path.name}, {sha(out)}, {placement["origin_msk77_xyz"]}')
    assert {p: p.read_bytes() for p in original} == original
