"""new-case: AGR Tools 1.0.x (#1024) branch BH - Max <-> Blender handoff with materials (handoff_core, no pymxs/bpy).

Named defects of the plain FBX round trip (REPORT 3.12 В«СЂРёСЃРєВ» column, owner answer 06.11.2026 on materials) are RED on
a behaviour model of that round trip (`naive_*`: match by exact name, matIDs as slot order, no sidecar, the material
that FBX brings back) and GREEN on handoff_core:
* H1 Blender clash suffix `X.001` -> the object is В«missingВ» + В«newВ»;            restore_name
* H2 Blender keeps 63 UTF-8 bytes of a (Cyrillic) name;                          restore_name / name_collisions
* H3 Multi/Sub IDs 3/9/12 come back as 1/2/3 (slot order);                       matid_remap
* H4 agr_role / user props are not in the FBX;                                   sidecar (parse_user_props)
* H5 FBX Max smoothing groups -> custom normals only, no sharp edge in Blender;  sharp_edges
* H6 the material comes back as an FBX copy (another class, maps lost);          materials.json + diff_nodes + restore_plan
* H7 unmatched objects of a restore are silently skipped;                        restore_plan reports them
* H8 one (non Multi/Sub) material: FBX drops the face IDs (1..6 -> one slot);  ids_by_centre
* H9 Max exporter triangulates Editable_Mesh / instanced Editable_Poly;         export of Editable_Poly copies,
                                                                                 Preserveinstances off (native)
Plus the tolerances of the table (UV 1e-6, matrix 1e-5, bbox 0.1 mm), the bundle schema mirror and the options.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters' / 'max' / 'agr_tools'


def _load(name):
    spec = importlib.util.spec_from_file_location('bh_test_' + name, PKG / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _load('handoff_core')
SCHEMA = json.loads((ROOT / 'schemas' / 'Handoff.schema.json').read_text(encoding='utf-8'))
ID = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def cube(name='BODY_Brick_001', at=(2.5, -1.3, 0.4), ids=(1, 1, 2, 2, 3, 3), role='body', shift=0.0, ch2=True,
         leader=None, hard=True):
    """A unit cube in metres (6 quads, 12 edges), UV ch1 in 1001, ch2 in 1002."""
    x, y, z = at
    v = [[x + a, y + b, z + c] for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    faces = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    uv1 = [[[0.1 + shift, 0.1], [0.9 + shift, 0.1], [0.9 + shift, 0.9], [0.1 + shift, 0.9]] for _ in faces]
    uvs = {1: uv1}
    if ch2:
        uvs[2] = [[[u + 1.0, w] for u, w in f] for f in uv1]
    mids = []
    if hard:
        edges = {tuple(sorted((f[i], f[(i + 1) % 4]))) for f in faces for i in range(4)}
        mids = [[(v[a][k] + v[b][k]) / 2 for k in range(3)] for a, b in sorted(edges)]
    world = ID + [[x, y, z]]
    return core.finish_facts(name, world, v, faces, list(ids), 12, mids, uvs, role=role, scale=[1, 1, 1],
                             instance_group=leader)


def naive_return(facts, rename=None, ids_as_slots=True, drop_role=True, drop_hard=False):
    """Behaviour model of the plain FBX round trip without the handoff contract."""
    out = copy.deepcopy(facts)
    if rename:
        out['name'] = rename
    if ids_as_slots:
        order = sorted({k[3] for k in out['face_keys']})
        m = {old: i + 1 for i, old in enumerate(order)}
        out['face_keys'] = sorted([k[:3] + [m[k[3]]] + k[4:] for k in out['face_keys']])
        out['mat_hist'] = {str(m[int(k)]): c for k, c in out['mat_hist'].items()}
    if drop_role:
        out['role'] = None
    if drop_hard:
        out['hard'] = []
    return out


# ---- H1 / H2 names -------------------------------------------------------------------------------------------------
def test_h1_blender_suffix_is_red_on_the_naive_match_and_green_with_restore_name():
    ref = [cube()]
    got = [naive_return(ref[0], rename='BODY_Brick_001.001', ids_as_slots=False, drop_role=False)]
    red = core.compare(ref, got)
    assert [d for _n, d in red['names_roles']] == ['missing after the round trip', 'new object (not in the reference)']
    fixed = core.restore_names([g['name'] for g in got], [r['name'] for r in ref])
    assert fixed == {'BODY_Brick_001.001': 'BODY_Brick_001'}
    got[0]['name'] = fixed[got[0]['name']]
    assert core.discrepancy_count(core.compare(ref, got)) == 0


def test_h2_name_cut_to_63_bytes_is_restored_and_collisions_are_named():
    long = 'РЈРіРѕР»РѕРє_РѕС†РёРЅРєРѕРІР°РЅРЅС‹Р№_50x50x5_РїРѕ_РїРµСЂРёРјРµС‚СЂСѓ_РїР°СЂР°РїРµС‚Р°_СЃРµРєС†РёСЏ_' + '0001'
    assert len(long.encode('utf-8')) > 63
    cut = core.blender_name(long)
    assert len(cut.encode('utf-8')) <= 63 and long.startswith(cut)
    assert cut not in [long]  # RED: the naive exact-name match loses it
    assert core.restore_name(cut, [long, 'BODY_Brick_001']) == long
    other = long[:-1] + '2'
    assert core.name_collisions([long, other, 'X']) == [(cut, sorted([long, other]))]
    assert core.restore_name(cut, [long, other]) is None  # two candidates: never guessed


def test_restore_name_keeps_first_come_and_rejects_unknown():
    m = core.restore_names(['A', 'A.001', 'B.002', 'C'], ['A', 'B'])
    assert m == {'A': 'A', 'A.001': None, 'B.002': 'B', 'C': None}


# ---- H3 matID ------------------------------------------------------------------------------------------------------
def test_h3_multisub_ids_with_gaps_come_back_as_slot_order_red_then_remapped_green():
    ref = [cube(ids=(3, 3, 9, 9, 12, 12))]
    got = [naive_return(ref[0], drop_role=False)]
    red = core.compare(ref, got)
    assert red['matid_slots'] and 'matID histogram' in red['matid_slots'][0][1]
    slots = core.slot_table([3, 3, 9, 9, 12, 12], {3: 'KPP1_AR_03', 9: 'KPP1_AR_09', 12: 'KPP1_AR_12'},
                            {3: [1001], 9: [1001], 12: [1001]})
    assert [(s['slot_index'], s['mat_id'], s['library_id'], s['udim']) for s in slots] == \
        [(0, 3, 3, [1001]), (1, 9, 9, [1001]), (2, 12, 12, [1001])]
    mapping, amb = core.matid_remap(slots, {1: 'KPP1_AR_03', 2: 'KPP1_AR_09.001', 3: 'KPP1_AR_12'})
    assert mapping == {1: 3, 2: 9, 3: 12} and amb == []
    fixed = copy.deepcopy(got[0])
    fixed['face_keys'] = sorted([k[:3] + [mapping[k[3]]] + k[4:] for k in fixed['face_keys']])
    fixed['mat_hist'] = {str(mapping[int(k)]): c for k, c in fixed['mat_hist'].items()}
    assert core.discrepancy_count(core.compare(ref, [fixed])) == 0


def test_matid_remap_reports_two_ids_of_one_submaterial_as_ambiguous():
    slots = core.slot_table([1, 2], {1: 'Same', 2: 'Same'})
    mapping, amb = core.matid_remap(slots, {1: 'Same'})
    assert mapping == {} and len(amb) == 1


def test_delivery_ids_are_their_own_udim_and_matid_of_material():
    slots = core.slot_table([1001, 1002], {1001: 'A', 1002: 'B'})
    assert [s['udim'] for s in slots] == [[1001], [1002]] and [s['library_id'] for s in slots] == [None, None]
    assert core.matid_of_material(slots, 'B.001') == 1002 and core.matid_of_material(slots, 'Z') is None
    assert core.matid_of_material(core.slot_table([5, 5], {'*': 'One'}), 'One') == 5


# ---- H4 roles / user props -----------------------------------------------------------------------------------------
def test_h4_role_lost_in_fbx_red_restored_from_sidecar_green():
    ref = [cube()]
    got = [naive_return(ref[0], ids_as_slots=False)]
    assert core.compare(ref, got)['names_roles'] == [('BODY_Brick_001', 'role body -> None')]
    side = core.parse_user_props('agr_role = body\r\nagr_window_type = WT-07\nagr_opening = {"w": 1}\n')
    assert side == {'agr_role': 'body', 'agr_window_type': 'WT-07', 'agr_opening': '{"w": 1}'}
    got[0]['role'] = side['agr_role']
    assert core.discrepancy_count(core.compare(ref, got)) == 0


# ---- H5 hard edges -------------------------------------------------------------------------------------------------
def _cube_normals(smooth):
    """Corner normals of the unit cube: flat per face (hard) or the vertex average (smooth)."""
    v = [[a, b, c] for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    faces = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
    flat = [[-1, 0, 0], [1, 0, 0], [0, -1, 0], [0, 1, 0], [0, 0, -1], [0, 0, 1]]
    if not smooth:
        return faces, [[flat[i]] * 4 for i in range(6)]
    avg = []
    for p in v:
        n = [c - 0.5 for c in p]
        ln = sum(c * c for c in n) ** 0.5
        avg.append([c / ln for c in n])
    return faces, [[avg[i] for i in f] for f in faces]


def test_h5_smoothing_groups_lost_red_then_sharp_edges_from_corner_normals_green():
    ref = [cube()]
    got = [naive_return(ref[0], ids_as_slots=False, drop_role=False, drop_hard=True)]
    assert core.compare(ref, got)['normals'] == [('BODY_Brick_001', 'hard edges 12 -> 0')]
    faces, normals = _cube_normals(smooth=False)
    assert len(core.sharp_edges(faces, normals)) == 12
    faces, normals = _cube_normals(smooth=True)
    assert core.sharp_edges(faces, normals) == set()


# ---- H6 / H7 materials ---------------------------------------------------------------------------------------------
def materials_doc():
    nodes = {
        'n001': {'name': 'BH_Multi', 'class': 'Multimaterial', 'superclass': 'material', 'props': {
            'numsubs': 3, 'materialList': {'$': 'array', 'v': [{'$': 'ref', 'v': 'n002'}, {'$': 'ref', 'v': 'n004'},
                                                               {'$': 'ref', 'v': 'n005'}]},
            'materialIDList': {'$': 'array', 'v': [1, 2, 3]}, 'names': {'$': 'array', 'v': ['', '', '']}}},
        'n002': {'name': 'BH_Cap_Top', 'class': 'Standardmaterial', 'superclass': 'material', 'props': {
            'diffuse': {'$': 'color', 'v': [200.0, 120.0, 80.0, 255.0]}, 'diffuseMap': {'$': 'ref', 'v': 'n003'},
            'shaderType': 1, 'twoSided': False, 'bumpMapAmount': 30.0}},
        'n003': {'name': 'BH_Cap_Top_diffuse', 'class': 'Bitmaptexture', 'superclass': 'textureMap', 'props': {
            'filename': 'C:/maps/bh_diffuse.png', 'bitmap': {'$': 'skip', 'class': 'BitMap'},
            'coords': {'$': 'sub', 'class': 'StandardUVGen', 'props': {'U_Tiling': 2.0, 'mapChannel': 1}}}},
        'n004': {'name': 'BH_Cap_Bottom', 'class': 'Standardmaterial', 'superclass': 'material', 'props': {
            'bumpMap': {'$': 'ref', 'v': 'n006'}, 'bumpMapAmount': 45.0}},
        'n005': {'name': 'BH_Side', 'class': 'Standardmaterial', 'superclass': 'material', 'props': {
            'opacityMap': {'$': 'ref', 'v': 'n007'}, 'diffuseMap': {'$': 'ref', 'v': 'n003'}}},
        'n006': {'name': 'BH_Cap_Bottom_bump', 'class': 'Bitmaptexture', 'superclass': 'textureMap',
                 'props': {'filename': 'C:/maps/bh_bump.png'}},
        'n007': {'name': 'BH_Side_opacity', 'class': 'Bitmaptexture', 'superclass': 'textureMap',
                 'props': {'filename': 'C:/maps/bh_opacity.png'}},
    }
    objects = [{'name': 'BODY_Brick_001', 'role': 'body', 'handle': 5, 'material': 'n001', 'mat_ids': [1, 2, 3]},
               {'name': 'BODY_Brick_002', 'role': 'body', 'handle': 9, 'material': 'n001', 'mat_ids': [1, 2, 3]},
               {'name': 'GLASS_001', 'role': 'glass', 'handle': 7, 'material': None, 'mat_ids': [1]}]
    return core.build_materials({'host': 'max', 'doc': 'C:/x.max', 'app': '3ds Max 26000'}, objects, nodes)


def test_h6_fbx_material_copy_is_red_and_the_rebuilt_graph_is_green():
    doc = materials_doc()
    fbx_copy = {'m1': {'name': 'BH_Multi', 'class': 'PhysicalMaterial', 'superclass': 'material', 'props': {}}}
    assert core.diff_nodes(doc['nodes'], 'n001', fbx_copy, 'm1') == ['BH_Multi: class Multimaterial -> PhysicalMaterial']
    rebuilt = copy.deepcopy(doc['nodes'])
    rebuilt = {('r' + k): v for k, v in rebuilt.items()}
    for v in rebuilt.values():
        for p in v['props'].values():
            _rekey(p)
    rebuilt['rn003']['props']['filename'] = 'c:\\maps\\BH_DIFFUSE.png'   # same file, other spelling
    rebuilt['rn002']['props']['bumpMapAmount'] = 30.0000001
    assert core.diff_nodes(doc['nodes'], 'n001', rebuilt, 'rn001') == []
    rebuilt['rn003']['props']['coords']['props']['U_Tiling'] = 1.0
    rebuilt['rn006']['name'] = 'Map #12'
    diff = core.diff_nodes(doc['nodes'], 'n001', rebuilt, 'rn001')
    assert any('U_Tiling: 2.0 -> 1.0' in d for d in diff) and any('name BH_Cap_Bottom_bump -> Map #12' in d for d in diff)


def _rekey(p):
    if isinstance(p, dict):
        if p.get('$') == 'ref':
            p['v'] = 'r' + p['v']
        for v in p.get('v', []) if p.get('$') == 'array' else []:
            _rekey(v)
        for v in p.get('props', {}).values() if p.get('$') == 'sub' else []:
            _rekey(v)


def test_materials_json_lists_types_multisub_ids_and_map_paths():
    doc = materials_doc()
    assert core.multi_ids(doc['nodes']['n001']) == {1: 'n002', 2: 'n004', 3: 'n005'}
    assert core.sub_names(doc, 'n001') == {1: 'BH_Cap_Top', 2: 'BH_Cap_Bottom', 3: 'BH_Side'}
    assert core.sub_names(doc, 'n002') == {'*': 'BH_Cap_Top'}
    assert [(m['node'], m['path'], m['used_by']) for m in doc['maps']] == [
        ('BH_Cap_Top_diffuse', 'C:/maps/bh_diffuse.png', ['BH_Cap_Top', 'BH_Side']),
        ('BH_Cap_Bottom_bump', 'C:/maps/bh_bump.png', ['BH_Cap_Bottom']),
        ('BH_Side_opacity', 'C:/maps/bh_opacity.png', ['BH_Side'])]
    bad = copy.deepcopy(doc)
    bad['nodes']['n002']['props']['diffuseMap'] = {'$': 'ref', 'v': 'n999'}
    with pytest.raises(ValueError, match='unknown node n999'):
        core.validate_materials(bad)


def test_h7_restore_plan_matches_by_name_and_role_and_reports_the_rest():
    doc = materials_doc()
    targets = [{'handle': 101, 'name': 'BODY_Brick_001.001', 'role': 'body'},
               {'handle': 102, 'name': 'BODY_Brick_002', 'role': 'glass'},     # role differs
               {'handle': 103, 'name': 'Stray_Box', 'role': None}]
    pairs, un_json, un_scene, amb = core.restore_plan(doc['objects'], targets)
    assert [(h, e['name']) for h, e in pairs] == [(101, 'BODY_Brick_001')]
    assert [n for n, _w in un_json] == ['BODY_Brick_002', 'GLASS_001']
    assert [(h, n) for h, n, _w in un_scene] == [(102, 'BODY_Brick_002'), (103, 'Stray_Box')]
    assert amb == []
    # RED model: a restore that matches by exact name only and drops the rest silently
    naive = [t for t in targets if t['name'] in {o['name'] for o in doc['objects']}]
    assert [t['handle'] for t in naive] == [102]
    pairs, un_json, un_scene, amb = core.restore_plan(doc['objects'], [
        {'handle': 1, 'name': 'BODY_Brick_001.001', 'role': 'body'},
        {'handle': 2, 'name': 'BODY_Brick_001.002', 'role': 'body'}])
    assert amb and amb[0][0] == 'BODY_Brick_001'


# ---- table of REPORT 3.12 ------------------------------------------------------------------------------------------
def test_compare_tolerances_of_the_table():
    ref = [cube()]
    ok = copy.deepcopy(ref[0])
    ok['uv']['1']['corners'][0][0] += 5e-7
    ok['world'][3][0] += 5e-6
    ok['bbox'][0][0] += 5e-5
    assert core.discrepancy_count(core.compare(ref, [ok])) == 0
    bad = copy.deepcopy(ref[0])
    bad['uv']['1']['corners'][0][0] += 5e-6
    bad['world'][3][0] += 5e-5
    bad['bbox'][0][0] += 5e-4
    bad['scale'] = [100.0, 100.0, 100.0]
    res = core.compare(ref, [bad])
    assert res['uv_udim'] and res['transform'] and len(res['units']) == 2


def test_compare_topology_uv_channels_tiles_and_instances():
    a, b = cube(leader='BODY_Brick_001'), cube('BODY_Brick_002', at=(5.5, -1.3, 0.4), leader='BODY_Brick_001')
    tri = copy.deepcopy(a)
    tri['faces'], tri['degrees'] = 12, {'3': 12}
    one_ch = cube(ch2=False, leader=None)
    shifted = cube(shift=1.0)
    res = core.compare([a, b], [tri, cube('BODY_Brick_002', at=(5.5, -1.3, 0.4))])
    assert res['topology'] and res['instances'] == [('BODY_Brick_001', "instance group ['BODY_Brick_001', "
                                                                      "'BODY_Brick_002'] lost")]
    assert core.compare([cube()], [one_ch])['uv_udim'][0][1] == "UV channels ['1', '2'] -> ['1']"
    assert any('UDIM [1001] -> [1002]' in d for _n, d in core.compare([cube()], [shifted])['uv_udim'])
    assert core.discrepancy_count(core.compare([a, b], [a, b])) == 0


def test_finish_facts_tiles_hash_and_rows():
    f = cube()
    assert f['uv']['1']['tiles'] == [1001] and f['uv']['2']['tiles'] == [1002]
    assert f['degrees'] == {'4': 6} and f['mat_hist'] == {'1': 2, '2': 2, '3': 2} and len(f['hard']) == 12
    assert core.geometry_hash(f) == core.geometry_hash(copy.deepcopy(f))
    m = [[1, 0, 0, 10], [0, 1, 0, 20], [0, 0, 1, 30], [0, 0, 0, 1]]
    assert core.rows_from_columns(m) == [[1, 0, 0], [0, 1, 0], [0, 0, 1], [10, 20, 30]]
    assert core.udim(0.5, 0.5) == 1001 and core.udim(1.5, 1.5) == 1012 and core.udim(-0.1, 0.2) is None


# ---- schema mirror -------------------------------------------------------------------------------------------------
def _bundle_docs():
    src = {'host': 'max', 'doc': 'C:/x.max', 'app': '3ds Max 26000'}
    a, b = cube(leader='BODY_Brick_001'), cube('BODY_Brick_002', at=(5.5, -1.3, 0.4), leader='BODY_Brick_001')
    sha = '0' * 64
    objs = [core.manifest_object(a, 5, 'BODY_main', core.slot_table([1, 1, 2, 2, 3, 3], {1: 'A', 2: 'B', 3: 'C'}),
                                 None),
            core.manifest_object(b, 9, 'BODY_main', core.slot_table([1, 1, 2, 2, 3, 3], {1: 'A', 2: 'B', 3: 'C'}),
                                 'BODY_Brick_001')]
    man = core.build_manifest(src, {'system': 'centimeters', 'm_per_unit': 0.01, 'system_scale': 1.0},
                              {'file': 'model.fbx', 'sha256': sha}, {'file': 'materials.json', 'sha256': sha}, objs)
    side = core.build_sidecar(src, {'BODY_Brick_001': {'user_props': 'agr_role = body', 'props': {'agr_role': 'body'},
                                                       'hard_edges': 12, 'smoothing': {'groups_bits': [1, 2]}}},
                              [{'name': 'OPEN_001', 'kind': 'opening', 'world': ID + [[0, 0, 0]],
                                'props': {'agr_role': 'opening'}}], None)
    rb = core.build_readback('max', '3ds Max 26000', [a, b])
    return man, side, materials_doc(), rb


def test_schema_mirror_accepts_the_built_documents_and_rejects_what_the_core_rejects():
    man, side, mats, rb = _bundle_docs()
    for doc in (man, side, mats, rb):
        jsonschema.validate(doc, SCHEMA)
    tri = copy.deepcopy(man)
    tri['fbx']['triangulated'] = True
    with pytest.raises(ValueError, match='never triangulated'):
        core.validate_manifest(tri)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(tri, SCHEMA)
    dup = copy.deepcopy(man)
    dup['objects'][1]['instance_of'] = 'Nope'
    with pytest.raises(ValueError, match='instance_of'):
        core.validate_manifest(dup)
    bad_marker = copy.deepcopy(side)
    bad_marker['markers'][0]['kind'] = 'door'
    with pytest.raises(ValueError, match='opening\\|level'):
        core.validate_sidecar(bad_marker)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad_marker, SCHEMA)


def test_options_seq_request_id_and_fbx_settings():
    assert core.next_seq(['001', '002', 'tmp']) == '003' and core.next_seq([]) == '001'
    assert core.request_id_of('C:/jobs/X/handoff/007') == 'bh007'
    with pytest.raises(ValueError, match='unknown handoff.export options: bogus'):
        core.check_options(core.TOOL_EXPORT, {'bogus': 1}, core.EXPORT_OPTIONS)
    params = dict(core.FBX_EXPORT_PARAMS)
    assert params['Triangulate'] is False and params['ConvertUnit'] == 'm' and params['UpAxis'] == 'Z'
    # measured: Preserveinstances on -> instanced Editable_Poly exported as triangles (job 20261106-134044-fbdf80ba)
    assert params['Preserveinstances'] is False and params['SmoothingGroups'] is True
    assert core.TOOLS == ('handoff.export', 'handoff.import', 'handoff.verify', 'handoff.restore_materials')


def test_glue_and_blender_script_load_without_hosts():
    glue = _load('handoff_max')
    for fn in ('handoff_export', 'handoff_import', 'handoff_verify', 'handoff_restore_materials'):
        assert callable(getattr(glue, fn))
    text = (ROOT / 'tools' / 'blender' / 'handoff_blender.py').read_text(encoding='utf-8')
    assert "'use_triangles': False" in text.replace('use_triangles=False', "'use_triangles': False")
    assert 'core.sharp_edges' in text and 'restore_names' in text


def test_h8_single_material_drops_face_ids_red_then_ids_by_centre_green():
    ref = cube(name='GLASS_001', ids=(1, 2, 3, 4, 5, 6), role='glass')
    got = copy.deepcopy(ref)
    got['face_keys'] = sorted([k[:3] + [-1] + k[4:] for k in got['face_keys']])   # one slot: no ID in the FBX
    got['mat_hist'] = {'-1': 6}
    assert core.compare([ref], [got])['matid_slots']
    centres = [k[:3] for k in got['face_keys']]
    centres[0] = [centres[0][0] + 5e-5, centres[0][1], centres[0][2]]            # within 0.1 mm
    ids = core.ids_by_centre(ref['face_keys'], centres)
    assert ids == [k[3] for k in ref['face_keys']]
    assert core.ids_by_centre(ref['face_keys'], [[100.0, 0.0, 0.0]]) == [None]    # an edited face stays unknown
    got['face_keys'] = sorted([c + [i, 4] for c, i in zip([k[:3] for k in got['face_keys']], ids)])
    got['mat_hist'] = ref['mat_hist']
    assert core.discrepancy_count(core.compare([ref], [got])) == 0


def test_point_index_finds_the_nearest_within_tolerance_across_cells():
    idx = core.PointIndex([[0.0, 0.0, 0.0], [0.0009, 0.0, 0.0]], ['a', 'b'])
    assert idx.find([0.00095, 0.0, 0.0], 1e-4) == 'b'
    assert idx.find([0.0004, 0.0, 0.0], 1e-4) is None
    assert idx.find([-0.00005, 0.0, 0.0], 1e-4) == 'a'

def test_compare_is_order_free_where_rounding_swaps_sorted_neighbours():
    # KPP1_Parapet, job 20261106-134538-40e13b6f: 13.83 vs 13.829999 reorder the sorted keys -> false «differs»
    ref = [[13.83, 0.0, 8.2225, 29, 4], [13.83, 0.15, 8.65, 35, 4], [13.83, 0.3, 8.3725, 29, 4]]
    got = [[13.829999, 0.15, 8.65, 35, 4], [13.83, 0.0, 8.2225, 29, 4], [13.83, 0.3, 8.3725, 29, 4]]
    assert not core._close_lists(sorted(ref), sorted(got), 1e-4)        # RED: the pairwise sorted compare
    assert core.multiset_close(ref, got, 1e-4)                           # GREEN
    assert not core.multiset_close(ref, [g[:3] + [9, 4] for g in got], 1e-4)
    assert not core.multiset_close([[0.5, 0.5]], [[0.5, 0.500002]], 1e-6, 2)
