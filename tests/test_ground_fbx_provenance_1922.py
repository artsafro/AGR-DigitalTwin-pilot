"""new-case: Ground producer provenance across synthetic FBX round trips, without Blender."""
import hashlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from adapters.max.agr_tools.build_manifest import write_export_derivation
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
    state = NS(export_count=0, on_export=lambda: None, on_import=lambda _: None, result=result, mesh=mesh,
               export_status={'FINISHED'})

    def load(filepath):
        path = Path(filepath)
        assert path.is_file()
        state.on_import(path)
        return {'FINISHED'}

    def export(filepath, **_kw):
        state.export_count += 1
        Path(filepath).write_bytes(f'synthetic-export-{state.export_count}'.encode())
        state.on_export()
        return state.export_status

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

    master = write_json(tmp_path / 'mesh.json', {'verts': [[x + OFFSET[0], y + OFFSET[1], z]
                                                         for x, y, z in (v.co for v in mesh.data.vertices)]})
    write_export_derivation([src], master, tmp_path, role='ground')
    return NS(source=src, placement=placement, spec=spec, state=state, collision=collision, bind=bind,
              master=master)


@pytest.mark.parametrize('crs', ['SYNTHETIC_LOCAL', 'DWG WCS metres; CRS unspecified by user, no transform'])
def test_off_origin_build_ucx_bind_and_bind_only(pipeline, tmp_path, crs):
    src = pipeline.source
    pipeline.placement['crs'] = crs
    write_json(side(src, 'placement'), pipeline.placement)
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


@pytest.mark.parametrize('producer', ['collision', 'bind'])
@pytest.mark.parametrize('bad,reason', [
    ('missing-placement', 'missing placement'), ('missing-meta', 'stale export record'),
    ('stale-fbx', 'stale export record'), ('stale-placement', 'stale placement FBX digest'),
    ('legacy-stale-origin', 'legacy placement origin'), ('missing-master', 'legacy Ground master'),
    ('stale-master', 'legacy Ground master'), ('missing-derivation', 'legacy placement derivation'),
    ('other-file', 'names another FBX'), ('empty', 'unsupported placement fields'),
    ('partial', 'unsupported placement fields'), ('unsupported', 'unsupported or non-finite'),
    ('nan', 'unsupported or non-finite'), ('inf', 'unsupported or non-finite'),
    ('pivot-limit', 'pivot differs'), ('frame-limit', 'frame differs'),
    ('wrong-address', 'does not identify the Ground'), ('truncated-meta', 'stale export record'),
])
def test_bad_evidence_is_unknown(pipeline, tmp_path, capsys, producer, bad, reason):
    src = pipeline.source
    place, meta = side(src, 'placement'), side(src, 'export_meta')
    if bad == 'missing-placement':
        place.unlink()
    elif bad == 'missing-meta':
        meta.unlink()
    elif bad == 'stale-fbx':
        src.write_bytes(b'changed FBX')
    elif bad == 'stale-placement':
        write_json(place, dict(pipeline.placement, fbx_sha256='a' * 64))
    elif bad == 'legacy-stale-origin':
        write_json(place, dict(pipeline.placement, origin_msk77_xyz=[87, -90, 0]))
    elif bad == 'missing-master':
        pipeline.master.unlink()
    elif bad == 'stale-master':
        write_json(pipeline.master, {'verts': [[2, 3, 4]]})
    elif bad == 'missing-derivation':
        side(src, 'derivation').unlink()
    elif bad == 'frame-limit':
        def change(path):
            if path != src:
                pipeline.state.mesh.location = (0.0001, 0, 0)
        pipeline.state.on_import = change
    elif bad == 'wrong-address':
        write_json(meta, dict(load_meta(meta), address='Other_Ground'))
    elif bad == 'truncated-meta':
        meta.write_text('{"profile":"vpm",', encoding='utf-8')
    else:
        fields = {'other-file': {'fbx': str(tmp_path / 'previous.fbx')},
                  'unsupported': {'crs': 'guessed'}, 'nan': {'origin_msk77_xyz': [float('nan'), -90, 0]},
                  'inf': {'origin_msk77_xyz': [float('inf'), -90, 0]},
                  'pivot-limit': {'object_location': [0.0001, 0, 0]}}
        payload = {} if bad == 'empty' else {'crs': 'SYNTHETIC_LOCAL'} if bad == 'partial' else {
            **pipeline.placement, **fields[bad]}
        write_json(place, payload)

    out = tmp_path / 'SM_New_Ground.fbx'
    getattr(pipeline, producer)(src, out)
    assert out.is_file()
    assert not side(out, 'placement').exists()
    record = load_meta(side(out, 'export_meta'))
    assert record['exported_sha256'] == {out.name: sha(out)}
    if producer == 'collision':
        report = json.loads(side(out, 'ucx_build').read_text(encoding='utf-8'))
        assert report['placement']['status'] == 'unknown'
        assert reason in report['placement']['reason']
        if bad in ('missing-meta', 'stale-fbx', 'wrong-address', 'truncated-meta'):
            assert record['profile'] == 'unknown'  # despite the output's VPM-looking name
            assert 'explicit exporter' not in record['provenance']['profile']
    else:
        assert 'placement: unknown: ' in (log := capsys.readouterr().out) and reason in log


@pytest.mark.parametrize('profile_why', ['filename grammar (not delivery QA)', 'legacy default vpm'])
def test_inherited_profile_stays_nonexplicit_and_does_not_override_plan(pipeline, tmp_path, profile_why):
    src = pipeline.source
    path = side(src, 'export_meta')
    meta = load_meta(path)
    meta['provenance']['profile'] = profile_why
    write_json(path, meta)
    collision = tmp_path / 'collision.fbx'
    assert pipeline.collision(src, collision) == 0
    inherited = load_meta(side(collision, 'export_meta'))
    assert inherited['profile'] == 'vpm'
    assert 'inherited from' in inherited['provenance']['profile']
    assert 'explicit exporter profile argument' not in inherited['provenance']['profile']
    pipeline.spec['profile'] = 'npm'
    out = tmp_path / 'result.fbx'
    pipeline.bind(collision, out)
    assert load_meta(side(out, 'export_meta'))['profile'] == 'npm'
    assert json.loads(side(out, 'placement').read_text())['origin_msk77_xyz'] == OFFSET


@pytest.mark.parametrize('conflict', ['canonical', 'explicit-upstream', 'unsupported', 'missing'])
def test_binder_profile_conflict_before_export(pipeline, tmp_path, conflict):
    out = tmp_path / 'result.fbx'
    pattern = 'contradict' if conflict in ('canonical', 'explicit-upstream') else 'explicit profile'
    if conflict == 'canonical':
        write_json(tmp_path / 'export_meta.json', {'address': 'Sample_Ground', 'h_otn_model_max_z_m': 4,
                                                  'thumbnail': 'unknown', 'profile': 'npm'})
    elif conflict == 'missing':
        del pipeline.spec['profile']
    else:
        pipeline.spec['profile'] = {'explicit-upstream': 'npm', 'unsupported': 'unknown'}[conflict]
    with pytest.raises(ValueError, match=pattern):
        pipeline.bind(pipeline.source, out)
    assert pipeline.state.export_count == 0
    assert not list(tmp_path.glob('result.fbx*'))


@pytest.mark.parametrize('producer', ['collision', 'bind'])
@pytest.mark.parametrize('suffix', ['', '.export_meta.json', '.placement.json', 'alias', 'hardlink'])
def test_existing_output_or_alias_leaves_evidence_unchanged(pipeline, tmp_path, producer, suffix):
    source = pipeline.source
    out = tmp_path / 'result.fbx'
    if suffix == 'alias':
        out = tmp_path / 'unused' / '..' / source.name
        victim = source
    elif suffix == 'hardlink':
        os.link(source, out)
        victim = out
    else:
        victim = out.with_name(out.name + suffix)
        victim.write_bytes(b'pre-existing evidence')
    original = victim.read_bytes()
    if producer == 'collision':
        assert pipeline.collision(source, out) == 4
    else:
        with pytest.raises(ValueError, match='overwrite|alias'):
            pipeline.bind(source, out)
    assert pipeline.state.export_count == 0
    assert victim.read_bytes() == original
    assert source.read_bytes() == b'synthetic-source-fbx'
    assert set(tmp_path.glob('result.fbx*')) <= {victim}


@pytest.mark.parametrize('producer', ['collision', 'bind'])
@pytest.mark.parametrize('event', ['late-output', 'late-sidecar', 'late-omitted', 'final-link', 'changed-source',
                                  'changed-placement', 'changed-master', 'cancelled'])
def test_no_success_bundle_after_late_conflict_or_cancel(pipeline, tmp_path, monkeypatch, producer, event):
    source = pipeline.source
    out = tmp_path / 'result.fbx'
    place, meta = side(out, 'placement'), side(out, 'export_meta')
    late = {'late-output': out, 'late-sidecar': meta, 'late-omitted': place, 'final-link': out}.get(event)
    note = b'foreign write during export'
    if event == 'final-link':
        link = os.link

        def competing_link(staged, destination):
            if destination == out:
                link(source, out)  # Race inside publication, after the last preflight.
            link(staged, destination)

        monkeypatch.setattr(os, 'link', competing_link)
    elif late is not None:
        pipeline.state.on_export = lambda: late.write_bytes(note)
        if event == 'late-omitted':
            side(source, 'placement').unlink()
    elif event == 'changed-source':
        pipeline.state.on_export = lambda: source.write_bytes(note)
    elif event == 'changed-placement':
        pipeline.state.on_export = lambda: side(source, 'placement').write_bytes(note)
    elif event == 'changed-master':
        pipeline.state.on_export = lambda: pipeline.master.write_bytes(note)
    else:
        pipeline.state.export_status = {'CANCELLED'}  # even if the exporter wrote bytes
    if producer == 'collision':
        assert pipeline.collision(source, out) == 2
        assert json.loads(side(out, 'ucx_build').read_text())['ok'] is False
    else:
        with pytest.raises((ValueError, FileExistsError)):
            pipeline.bind(source, out)
    if late is not None:
        assert late.read_bytes() == (source.read_bytes() if event == 'final-link' else note)
    assert out.exists() == (late == out)
    assert place.exists() == (late == place)
    assert meta.exists() == (late == meta)
    assert not any(p.is_dir() for p in tmp_path.iterdir())


@pytest.mark.parametrize('driver', [UCX, BIND])
def test_fresh_cli_input_alias_writes_nothing(pipeline, tmp_path, driver):
    src = pipeline.source
    if driver == UCX:
        args = [str(driver), '--', str(src), str(src), 'Ground']
        prefix = [sys.executable, '-I']
    else:
        args = [str(driver), '--', 'bind', str(src), str(tmp_path / 'absent_plan.json'), str(src)]
        prefix = [sys.executable, '-I', '-c', 'import runpy, sys, types; sys.modules["bpy"] = types.ModuleType("bpy"); '
                  'sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name="__main__")']
    before = {p.name: sha(p) for p in tmp_path.iterdir()}
    result = subprocess.run([*prefix, *args], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == (4 if driver == UCX else 1), result.stderr
    assert ('input path' if driver == UCX else 'input alias') in result.stderr
    assert {p.name: sha(p) for p in tmp_path.iterdir()} == before


def test_unrelated_blend_ucx_still_writes_only_fbx_and_report(pipeline, tmp_path):
    src = tmp_path / 'scene.blend'
    src.write_bytes(b'synthetic scene')
    out = tmp_path / 'result.fbx'
    pipeline.state.result.within_tol = False
    assert pipeline.collision(src, out) == 3
    assert set(tmp_path.glob('result.fbx*')) == {out, side(out, 'ucx_build')}
    assert json.loads(side(out, 'ucx_build').read_text())['within_tol'] is False


@pytest.mark.parametrize('changed', ['plan', 'thumbnail', 'canonical'])
def test_binding_provenance_inputs_cannot_change_during_export(pipeline, tmp_path, changed):
    out = tmp_path / 'result.fbx'
    thumb = tmp_path / 'current.jpg'
    thumb.write_bytes(b'provided preview')
    pipeline.spec['thumbnail'] = thumb.name
    victim = {'plan': tmp_path / 'plan.json', 'thumbnail': thumb, 'canonical': tmp_path / 'export_meta.json'}[changed]
    replacement = b'{"profile":"npm","address":"Sample_Ground","h_otn_model_max_z_m":4,"thumbnail":"unknown"}'
    pipeline.state.on_export = lambda: victim.write_bytes(replacement)
    with pytest.raises(ValueError, match='changed during export|contradicts'):
        pipeline.bind(pipeline.source, out)
    assert victim.read_bytes() == replacement
    assert not list(tmp_path.glob('result.fbx*'))


def test_absent_output_cannot_be_referenced_as_input_texture(pipeline, tmp_path):
    out = tmp_path / 'result.fbx'
    pipeline.spec['bindings'][0]['file'] = side(out, 'placement').name
    with pytest.raises(ValueError, match='input alias'):
        pipeline.bind(pipeline.source, out)
    assert not list(tmp_path.glob('result.fbx*'))


@pytest.mark.parametrize('kind', ['previous.jpg', 'missing.jpg', '', 'duplicate', 'unmapped', 'empty'])
def test_binder_rejects_unusable_thumbnail_or_binding(pipeline, tmp_path, capsys, kind):
    out = tmp_path / 'result.fbx'
    if kind == 'duplicate':
        pipeline.spec['bindings'] *= 2
    elif kind == 'unmapped':
        pipeline.spec['bindings'][0]['material'] = 'NoSuchSlot'
    elif kind == 'empty':
        pipeline.spec['bindings'].clear()
    else:
        pipeline.spec['thumbnail'] = kind
    if kind == 'unmapped':
        with pytest.raises(SystemExit) as exc:
            pipeline.bind(pipeline.source, out)
        assert exc.value.code == 2 and 'NoSuchSlot' in capsys.readouterr().err
    else:
        with pytest.raises(ValueError, match='thumbnail|duplicate binding|nonempty bindings'):
            pipeline.bind(pipeline.source, out)
    assert not list(tmp_path.glob('result.fbx*'))
