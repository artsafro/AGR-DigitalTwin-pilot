"""new-case: AGR Tools 0.9 `scene.maps_usage` (#979, branch D): mapsuse_core on a temporary maps folder.

The T08 synthetic (team-audit T08/audit_scene_maps, measured: 12 map files, 2 truly unused) is rebuilt as plain
records: one record per BitmapTexture class instance with its owner nodes, as mapsuse_max.py reads them. The
source model is the hand walker of `audit_scene_maps.ms` (SHA256
e9601693458995c2b7e2cb0bd8ca546175960a83ed969a6802b5273930c4a382) and the basename relink of
`collect_scene_maps.ms` (SHA256 ce77809fe39f52ccf5fa34582f6547db589c4aeff656b4ab4b30897790c97290), written from
the measured behaviour, not from their code (#853). Each defect: RED on the model, GREEN on mapsuse_core.
"""
import ast
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = sys.modules.get('agr_tools_edit_core') or _load(PKG / 'edit_core.py', 'agr_tools_edit_core')
mc = _load(PKG / 'mapsuse_core.py', 'agr_tools_mapsuse_core_t')

# (file, container, owner kind) of the T08 scene; k and l are the two truly unused files
T08 = [('a_std.png', 'Standard', 'geometry'), ('b_multi.png', 'Multimaterial', 'geometry'),
       ('c_blend.png', 'Blend', 'geometry'), ('d_double.png', 'DoubleSided', 'geometry'),
       ('e_shell.png', 'Shell', 'geometry'), ('f_spline.png', 'Standard', 'shape'),
       ('g_env.png', 'environment', None), ('h_proj.png', 'projector', 'light'),
       ('i_moved.png', 'Standard', 'geometry'), ('j_std.jpg', 'Standard', 'geometry')]
EXTRA = ('k_unused.png', 'l_unused.tga')


def write(path, data=b'x'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def exists(p):
    return os.path.isfile(p)


@pytest.fixture
def t08(tmp_path):
    maps = tmp_path / 'scene' / 'maps'
    for name, _, _ in T08:
        write(maps / name, name.encode())
    for name in EXTRA:
        write(maps / name, name.encode())
    # i_moved.png: the scene reads the same picture from another folder (a copy made before a relink)
    other = write(tmp_path / 'old' / 'i_moved.png', b'i_moved.png')
    records = []
    for i, (name, container, kind) in enumerate(T08):
        path = other if name == 'i_moved.png' else str(maps / name)
        owners = [] if kind is None else [{'handle': 10 + i, 'node': 'N_' + name.split('.')[0], 'material': container,
                                           'map': 'Map #' + str(i), 'hidden': False, 'kind': kind}]
        records.append({'path': path, 'owners': owners, 'source': 'environment' if kind is None else 'class_instance'})
    return maps, records


def files(maps):
    return mc.list_folder(str(maps))


def run(records, maps, scope=None):
    result = mc.usage(records, files(maps), exists, sha)
    owners = sorted({(o['handle'], o['node']) for r in records for o in r['owners']})
    return result, mc.maps_report(ec, result, scope or owners, [str(maps)], 'state')


# ---- source models (measured behaviour) -----------------------------------------------------------------
def walker_used(records):
    """audit_scene_maps.ms :34-77 (T08, measured): materials of GeometryClass nodes, walked through
    Multimaterial / materialList / getSubTexmap only; full path compare."""
    out = set()
    for r in records:
        for o in r['owners']:
            if o.get('kind') == 'geometry' and o['material'] in ('Standard', 'Multimaterial'):
                out.add(r['path'])
    return out


def walker_extra(records, folder_files):
    used = walker_used(records)
    return [f for f in folder_files if f not in used]


def collect_resolve(missing_path, folder_files):
    """collect_scene_maps.ms :111-124 (T08, measured): a missing map is replaced by any same-basename file."""
    return next((f for f in folder_files if os.path.basename(f) == os.path.basename(missing_path)), None)


# ---- T08 acceptance -------------------------------------------------------------------------------------
def test_t08_exactly_two_extra_files(t08):
    maps, records = t08
    result, report = run(records, maps)
    assert sorted(os.path.basename(r['path']) for r in result['extra']) == sorted(EXTRA)
    assert [r['item'] for r in report['plan']['ambiguous']] == [r['path'] for r in result['extra']]
    assert result['missing'] == [] and report['plan']['summary'] == {'used': 10, 'missing': 0, 'extra': 2,
                                                                      'copies': 1}
    assert report['status'] == 'fail' and all(not o['findings'] for o in report['objects'])  # extras: person decides


def test_red_hand_walker_reports_false_extras(t08):
    maps, records = t08
    false = set(walker_extra(records, files(maps))) - {str(maps / n) for n in EXTRA}
    names = {os.path.basename(f) for f in false}
    assert {'c_blend.png', 'd_double.png', 'e_shell.png', 'f_spline.png', 'g_env.png', 'h_proj.png',
            'i_moved.png'} <= names  # RED: T08 measured 6 false «unused» (Blend, DoubleSided, spline, env, moved)
    assert not ({os.path.basename(r['path']) for r in run(records, maps)[0]['extra']} & names)


def test_red_full_path_compare_marks_a_relinked_or_moved_file_extra(t08):
    maps, records = t08
    assert str(maps / 'i_moved.png') in walker_extra(records, files(maps))  # RED
    result, _ = run(records, maps)
    assert [(os.path.basename(c['path']), c['same_as']) for c in result['copies']] == [
        ('i_moved.png', next(r['path'] for r in records if r['path'].endswith('i_moved.png')))]


def test_paths_are_compared_normalised(tmp_path):
    maps = tmp_path / 'Maps'
    real = write(maps / 'T_A_d_1.png')
    odd = str(tmp_path / 'x' / '..' / 'MAPS' / 'T_A_D_1.PNG').replace('\\', '/')
    rec = [{'path': odd, 'owners': [{'handle': 5, 'node': 'SM_A_Main', 'material': 'M', 'map': 'm', 'hidden': False}],
            'source': 'class_instance'}]
    result, report = run(rec, maps)
    assert result['extra'] == [] and result['missing'] == [] and report['status'] == 'pass'
    assert mc.norm(real) == mc.norm(odd)


def test_same_name_with_other_content_is_extra_with_a_note(tmp_path):
    maps = tmp_path / 'maps'
    write(maps / 'wall.png', b'one')
    used = write(tmp_path / 'lib' / 'wall.png', b'two')
    rec = [{'path': used, 'owners': [{'handle': 5, 'node': 'SM_A_Main', 'material': 'M', 'map': 'm', 'hidden': False}],
            'source': 'class_instance'}]
    result, _ = run(rec, maps)
    assert [os.path.basename(r['path']) for r in result['extra']] == ['wall.png']
    assert 'другим содержимым' in result['extra'][0]['note']


def test_red_missing_map_is_never_silently_replaced_by_a_namesake(tmp_path):
    maps = tmp_path / 'maps'
    namesake = write(maps / 'e_moved.png', b'e')
    gone = str(tmp_path / 'gone' / 'e_moved.png')
    assert collect_resolve(gone, files(maps)) == namesake  # RED: T08 collect relinked it by basename, silently
    rec = [{'path': gone, 'owners': [{'handle': 7, 'node': 'SM_E_Main', 'material': 'M', 'map': 'm', 'hidden': False}],
            'source': 'material'}]
    result, report = run(rec, maps)
    assert [r['path'] for r in result['missing']] == [gone] and result['missing'][0]['candidates'] == [namesake]
    assert [r['path'] for r in result['extra']] == [namesake] and 'кандидат' in result['extra'][0]['note']
    assert [(o['name'], [f['code'] for f in o['findings']]) for o in report['objects']] == [('SM_E_Main', ['map_missing'])]


def test_missing_map_without_owner_node_is_ambiguous(tmp_path):
    maps = tmp_path / 'maps'
    write(maps / 'ok.png')
    rec = [{'path': str(maps / 'ok.png'), 'owners': [{'handle': 3, 'node': 'SM_Ok_Main', 'material': 'M', 'map': 'm',
                                                      'hidden': False}], 'source': 'class_instance'},
           {'path': str(tmp_path / 'nowhere.png'), 'owners': [], 'source': 'asset_manager'}]
    result, report = run(rec, maps)
    assert [a['kind'] for a in report['plan']['ambiguous']] == ['missing_unowned']
    assert report['status'] == 'fail' and [o['findings'] for o in report['objects']] == [[]]


def test_udim_tiles_on_disk_are_used(tmp_path):
    maps = tmp_path / 'maps'
    for t in (1001, 1002):
        write(maps / 'T_A_d_1.{}.png'.format(t))
    write(maps / 'T_B_d_1.1001.png')
    rec = [{'path': str(maps / 'T_A_d_1.<UDIM>.png'), 'owners': [{'handle': 3, 'node': 'SM_A_Main', 'material': 'M',
                                                                  'map': 'm', 'hidden': False}], 'source': 'material'}]
    result, _ = run(rec, maps)
    assert [os.path.basename(p) for p in result['used'][0]['tiles']] == ['T_A_d_1.1001.png', 'T_A_d_1.1002.png']
    assert [os.path.basename(r['path']) for r in result['extra']] == ['T_B_d_1.1001.png']


def test_proxies_and_non_images_are_not_maps(tmp_path):
    maps = tmp_path / 'maps'
    for name in ('tree.cgeo', 'rock.vrmesh', 'notes.txt', 'a.png'):
        write(maps / name)
    assert [os.path.basename(f) for f in files(maps)] == ['a.png']
    assert [os.path.basename(f) for f in mc.list_folder(str(tmp_path), recursive=True)] == ['a.png']
    assert mc.list_folder(str(tmp_path), recursive=False) == []


def test_scope_limits_objects_but_not_usage(t08):
    maps, records = t08
    result, report = run(records, maps, scope=[(10, 'N_a_std')])
    assert [o['name'] for o in report['objects']] == ['N_a_std'] and len(result['extra']) == 2


def test_disk_is_unchanged_and_there_is_no_delete(t08, tmp_path):
    maps, records = t08
    before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    run(records, maps)
    after = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    assert before == after
    for name in ('mapsuse_core.py', 'mapsuse_max.py'):
        tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
        called = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, 'id', '')
                  for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not called & {'remove', 'unlink', 'deleteFile', 'rmtree', 'rename', 'replace', 'move'}, name
        assert 'open' not in called or name == 'mapsuse_max.py'  # the glue opens files only to hash ('rb')


def test_glue_uses_the_shared_enumerator_and_class_instances():
    src = (PKG / 'mapsuse_max.py').read_text(encoding='utf-8')
    assert "_load_core('tex_max.py'" in src and 'texmax._scene_maps(texcore' in src
    assert 'getClassInstances(rt.BitmapTexture)' in src and 'refs.dependentNodes' in src
    assert 'environmentMap' in src


def test_options_are_validated():
    assert mc.maps_options(None) == {'folders': None, 'recursive': True}
    for bad in ({'x': 1}, {'folders': []}, {'folders': 'C:/maps'}, {'recursive': 'yes'}, {'folders': ['']}):
        with pytest.raises(ValueError):
            mc.maps_options(bad)


def test_report_contract(t08):
    maps, records = t08
    _, report = run(records, maps)
    ec.validate_report(report)
    assert report['tool'] == 'scene.maps_usage' and report['plan']['read_only'] and report['plan']['deletes'] is False
    assert report['plan']['table'][0].startswith('status |')
