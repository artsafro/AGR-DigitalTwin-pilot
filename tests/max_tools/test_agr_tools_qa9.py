"""new-case: AGR Tools 0.9 (#979) branch C: qa.address, qa.normals, qa.sintez, qa.procedural_objects (qa9_core.py,
qa9_max.py with a fake pymxs), plain pytest.

Every defect named in docs/experiments/qa.address.md, qa.normals.md (lab L05) and qa.procedural_objects.md (L07)
has a regression test that is RED on a behaviour model of the source and GREEN on qa9_core. The source models are
written from the lab MEASUREMENTS (jobs 20261105-124240-b42ff7fe, 20261105-124436-f26ae9ca, 20261105-124601-94a4eebc,
20261105-125138-6c2ff972, 20261105-123702-11647754), not from GeoAGR code (#853): GeoAGR Check Adress
`GeoAGR.ms:15355-15546`, Double Faces `GeoAGR.ms:49204` (LMB) / `GeoAGR.ms:49149` (RMB).
"""
import copy
import hashlib
import importlib.util
import json
import math
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
STREETS = PKG / 'data/streets'
FIX = Path(__file__).resolve().parent / 'fixtures_qa9'


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load('edit_core.py', 'agr_tools_edit_core_qa9_t')
qc = _load('qa9_core.py', 'agr_tools_qa9_core_t')
qm = _load('qa9_max.py', 'agr_tools_qa9_max_t')
nc = _load('names_core.py', 'agr_tools_names_core')
DIRECTORY = qc.load_directory(str(STREETS))


def red_green(prop, source, impl):
    """The property fails on the source model (RED) and holds on the implementation (GREEN)."""
    assert not prop(source), 'source model already satisfies the property: not a regression'
    assert prop(impl)


def ours(address):
    return qc.check_address(address, DIRECTORY)


# =====================================================================================================
# qa.address — source model: the GeoAGR messages measured per address (lab L05, CSV orig)
# =====================================================================================================
# message kinds: chars, translit, classifier, list, underscore, space, abbr, split, digits, capital, uch_zu
SOURCE_L05 = {
    'Tverskaya_7': [],
    'Tverskaya_7_Str_1': ['classifier'], 'Tverskaya_7_K_2': ['classifier'],
    'Тверская_7': ['chars', 'translit', 'classifier', 'list'],
    'Tverskaya__7': [], '_Tverskaya_7': [], 'Tverskaya_7_': [], '_': [],
    'Tverskaya 7': ['chars', 'translit', 'space', 'underscore'],
    'TverskayaUlicza_7': ['abbr'], 'Qwxz_7': ['classifier', 'list'],
    'Tverskaya_Dom_7': ['classifier'], 'Tverskaya_D_7': ['classifier'],
    'Tverskaya_Uch_7': ['classifier', 'uch_zu', 'list'],
    'Tverskaya_7A': ['digits', 'abbr', 'split'], 'Tverskaya7': ['underscore'],
    'Tverskaya_7' + ''.join('_Str_{}'.format(i) for i in range(1, 41)): ['classifier'],
    'PervyjAvtozavodskijPrd_7': [], 'PervyyAvtozavodskijPrd_7': ['classifier', 'split'],
    '': ['underscore'], 'tverskaya_7': ['capital', 'digits', 'abbr'], 'TVERSKAYA_7': ['classifier'],
    'Parkovaya_7': ['abbr', 'split'], 'Valovaya_7': ['abbr', 'split'], '2jKotelnicheskijPer_7': ['digits'],
    'PosAkulovo_7': [],
}


def source_address(address):
    return SOURCE_L05[address]


# lab «Минимальная приёмка»: address -> expected primary code (None = pass)
ACCEPT = {
    'Tverskaya_7': None, 'Tverskaya_7_Str_1': None, 'Tverskaya_7_K_2': None, 'PervyjAvtozavodskijPrd_7': None,
    'Parkovaya_7': None, 'Valovaya_7': None, '2jKotelnicheskijPer_7': None, 'PosAkulovo_7': None,
    'Тверская_7': 'addr_chars', 'Tverskaya__7': 'addr_parts', '_Tverskaya_7': 'addr_parts',
    'Tverskaya_7_': 'addr_parts', '_': 'addr_parts', '': 'addr_parts', 'Tverskaya 7': 'addr_chars',
    'Tverskaya_7.': 'addr_chars', 'TverskayaUlicza_7': 'addr_abbr', 'Qwxz_7': 'addr_street_unknown',
    'Tverskaya7': 'addr_parts', 'Tverskaya_7A': 'addr_parts', 'Tverskaya_7' + '_Str_1' * 40: 'addr_length',
    'tverskaya_7': 'addr_case', 'TVERSKAYA_7': 'addr_case', 'PervyyAvtozavodskijPrd_7': 'addr_translit',
}


@pytest.mark.parametrize('address,code', sorted(ACCEPT.items()))
def test_address_acceptance_exactly_one_primary_cause(address, code):
    r = ours(address)
    assert r['primary'] == code
    assert r['status'] == ('pass' if code is None else 'fail')
    for m in r['messages']:
        assert set(m) == {'code', 'level', 'token', 'text', 'hint'} and m['level'] in ('error', 'warn')
        assert m['code'] in qc.ADDRESS_CODES


@pytest.mark.parametrize('address,hint', [('Tverskaya_Dom_7', 'D опускается'), ('Tverskaya_D_7', 'D опускается'),
                                          ('Tverskaya_Uch_7', 'Uch → ZU')])
def test_address_warnings_d_dom_uch(address, hint):
    r = ours(address)
    assert r['status'] == 'pass' and r['primary'] is None
    warns = [m for m in r['messages'] if m['level'] == 'warn']
    assert len(warns) == 1 and hint in warns[0]['text'] and warns[0]['code'] == 'addr_abbr'


def test_defect_d1_house_parts_at_token_2_3_are_not_streets():
    for a in ('Tverskaya_7_Str_1', 'Tverskaya_7_K_2'):
        red_green(lambda r: not r, source_address(a), [m for m in ours(a)['messages'] if m['level'] == 'error'])


def test_defect_d2_empty_tokens_are_seen():
    for a in ('Tverskaya__7', '_Tverskaya_7', 'Tverskaya_7_', '_'):
        red_green(lambda r: r == 'fail', 'fail' if source_address(a) else 'pass', ours(a)['status'])


def test_defect_d3_length_is_checked():
    a = 'Tverskaya_7' + ''.join('_Str_{}'.format(i) for i in range(1, 41))
    assert len(a) > qc.ADDRESS_MAX
    red_green(lambda kinds: 'length' in kinds, source_address(a),
              ['length' if m['code'] == 'addr_length' else m['code'] for m in ours(a)['messages']])
    assert ours(a)['primary'] == 'addr_length'
    assert ours('Tverskaya_7_Str_1' * 1)['status'] == 'pass'


def test_defect_d4_whole_token_not_substring():
    for a in ('Parkovaya_7', 'Valovaya_7'):
        red_green(lambda r: not r, source_address(a), [m for m in ours(a)['messages'] if m['level'] == 'error'])


def test_defect_d5_numeral_171n_is_not_digits_apart():
    red_green(lambda r: not r, source_address('2jKotelnicheskijPer_7'), ours('2jKotelnicheskijPer_7')['messages'])


def test_defect_d6_d7_case_is_one_message_not_a_cascade():
    for a in ('tverskaya_7', 'TVERSKAYA_7'):
        red_green(lambda kinds: kinds == ['addr_case'], ['capital' if k == 'capital' else 'addr_' + k
                                                         for k in source_address(a)],
                  [m['code'] for m in ours(a)['messages']])


def test_defect_d8_space_is_a_character_not_translit():
    red_green(lambda kinds: kinds == ['addr_chars'], ['addr_' + k for k in source_address('Tverskaya 7')],
              [m['code'] for m in ours('Tverskaya 7')['messages']])
    assert ours('Tverskaya 7')['messages'][0]['hint'] == 'Tverskaya_7'


def test_defect_d9_d_dom_uch_reached_at_position_2_3():
    for a in ('Tverskaya_Dom_7', 'Tverskaya_D_7', 'Tverskaya_Uch_7'):
        red_green(lambda r: 'classifier' not in r and r != [],
                  source_address(a), ['warn' for m in ours(a)['messages'] if m['level'] == 'warn'])


def test_defect_d12_digits_apart_runs_without_underscore():
    red_green(lambda kinds: 'digits' in kinds, source_address('Tverskaya7'),
              ['digits' if 'цифры' in m['text'] else m['code'] for m in ours('Tverskaya7')['messages']])


def test_defect_d13_machine_result_and_report(tmp_path):
    items = [(1, 'SM_Tverskaya_7_Main', 'Tverskaya_7'), (2, 'SM_Tverskaya__7_Main', 'Tverskaya__7'),
             (3, 'SM_Tverskaya_Dom_7_Main', 'Tverskaya_Dom_7')]
    r = qc.address_report(ec, items, DIRECTORY, 'h')
    ec.validate_report(r)
    assert r['status'] == 'fail' and r['plan']['read_only'] is True
    by = {o['name']: o['findings'] for o in r['objects']}
    assert by['SM_Tverskaya_7_Main'] == [] and by['SM_Tverskaya_Dom_7_Main'] == []
    assert [f['code'] for f in by['SM_Tverskaya__7_Main']] == ['addr_parts']
    assert r['plan']['warnings'] == [{'name': 'SM_Tverskaya_Dom_7_Main', 'address': 'Tverskaya_Dom_7',
                                      'code': 'addr_abbr', 'text': qc.HOUSE_WARN['Dom']}]
    assert json.loads(json.dumps(r)) == r
    with pytest.raises(ValueError, match='empty input'):
        qc.address_report(ec, [], DIRECTORY, 'h')


def test_translit_y_vs_j_is_reported_with_the_directory_form():
    r = ours('PervyyAvtozavodskijPrd_7')
    assert r['messages'][0]['hint'] == 'PervyjAvtozavodskijPrd'
    assert ours('PervyjAvtozavodskijPrd_7')['status'] == 'pass'
    # names_core (qa.names_fix, owner E1) gives й -> y: the shared table is the source of the free-text hint
    assert nc.clean_text('Улица')[0] == 'Ulitsa'
    assert ours('Неизвестная_7')['messages'][0]['hint'] == nc.clean_text('Неизвестная_7')[0]
    assert ours('Тверская_7')['messages'][0]['hint'] == 'Tverskaya_7'  # directory street, not the square


def test_street_type_unabbreviated_and_separate():
    assert ours('TverskayaUlitsa_7')['primary'] == 'addr_abbr'
    assert ours('PervyjAvtozavodskijProezd_7')['primary'] == 'addr_abbr'
    assert ours('Tverskaya_Ul_7')['primary'] == 'addr_parts'
    assert ours('TverskayaUl_7')['status'] == 'pass'
    assert ours('Tverskaya_7_str_1')['primary'] == 'addr_case'
    assert ours('Tverskaya_7_Str')['primary'] == 'addr_parts'
    assert ours('Tverskaya_7_A')['status'] == 'pass'  # литера


def test_address_of_name():
    assert qc.address_of_name('SM_Tverskaya_7_Main') == 'Tverskaya_7'
    assert qc.address_of_name('SM_Tverskaya_7_001_MainGlass') == 'Tverskaya_7'
    assert qc.address_of_name('SM_Lenina_101_Main') == 'Lenina_101'
    assert qc.address_of_name('SM_Tverskaya__7_Ground') == 'Tverskaya__7'
    assert qc.address_of_name('UCX_SM_Tverskaya_7_Main_001') is None
    assert qc.address_of_name('Box001') is None


# ---- dictionary: open sources, strict loading (D10, D11) ---------------------------------------------------
def test_street_files_match_provenance():
    prov = (STREETS / 'PROVENANCE.md').read_text(encoding='utf-8')
    assert 'Владелец: ветка **C**' in prov
    for name in qc.STREET_FILES:
        raw = (STREETS / name).read_bytes()
        rows = raw.count(b'\n') - 1
        sha = hashlib.sha256(raw).hexdigest()
        assert '| `{}` | `{}` | {} |'.format(name, sha, rows) in prov, name
        assert not raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw
    assert DIRECTORY.count['streets'] > 5000 and DIRECTORY.count['settlements'] > 300
    skipped = sum(1 for line in (STREETS / 'omk_um.tsv').read_text(encoding='utf-8').splitlines()[1:]
                  if '№' in line)
    assert '{} проектируемых проездов с «№»'.format(skipped) in prov
    assert not list(STREETS.glob('*.csv')), 'GeoAGR CSV must not be copied (#853)'


def test_defect_d10_d11_broken_dictionary_is_an_error_not_a_verdict(tmp_path):
    good = {n: (STREETS / n).read_bytes() for n in qc.STREET_FILES}
    cases = {
        'cp1251': lambda d: d.__setitem__('omk_um.tsv', good['omk_um.tsv'].decode('utf-8').encode('cp1251', 'replace')),
        'bom': lambda d: d.__setitem__('omk_um.tsv', b'\xef\xbb\xbf' + good['omk_um.tsv']),
        'header': lambda d: d.__setitem__('settlements_wikidata.tsv', b'x\ty\n1\t2\n'),
        'missing': lambda d: d.pop('omk_um.tsv'),
        'empty': lambda d: d.__setitem__('omk_um.tsv', good['omk_um.tsv'].split(b'\n')[0] + b'\n'),
    }
    for word, mutate in cases.items():
        folder = tmp_path / word
        folder.mkdir()
        files = dict(good)
        mutate(files)
        for n, b in files.items():
            (folder / n).write_bytes(b)
        with pytest.raises(ValueError, match='street dictionary'):
            qc.load_directory(str(folder))
    # the source model: CP1251 silently drops the «не сокращены» rule and the address passes (L05 D10)
    red_green(lambda verdict: verdict == 'error', 'pass', 'error')


# =====================================================================================================
# qa.normals — source models from lab L05 (Double Faces LMB / RMB)
# =====================================================================================================
def box(o=(0, 0, 0), s=(1, 1, 1), flip=False):
    x, y, z = o
    a, b, c = s
    v = [(x, y, z), (x + a, y, z), (x + a, y + b, z), (x, y + b, z), (x, y, z + c), (x + a, y, z + c),
         (x + a, y + b, z + c), (x, y + b, z + c)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7),
         (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    if flip:
        f = [(p, r, q) for p, q, r in f]
    return v, f


def l_shape():
    """Non-convex closed L volume (outward): 3x1x1 bar + 1x2x1 leg, as one welded surface."""
    pts = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
    v = [(x, y, 0) for x, y in pts] + [(x, y, 1) for x, y in pts]
    f = [(0, 3, 1), (1, 3, 2), (0, 5, 3), (3, 5, 4)]  # bottom, normal -z
    f += [(6, 7, 9), (7, 8, 9), (6, 9, 11), (9, 10, 11)]  # top, +z
    for i in range(6):
        j = (i + 1) % 6
        f += [(i, j, j + 6), (i, j + 6, i + 6)]
    return v, f


def quad(z=0.0, tilt=0.0, size=1.0, flip=False, off=0.0):
    t = math.radians(tilt)
    h = size / 2
    v = [(x + off, y * math.cos(t), z + y * math.sin(t)) for x, y in ((-h, -h), (h, -h), (h, h), (-h, h))]
    f = [(0, 1, 2), (0, 2, 3)]
    if flip:
        f = [(p, r, q) for p, q, r in f]
    return v, f


def merge(*parts):
    v, f, ids = [], [], []
    for k, (pv, pf) in enumerate(parts):
        n = len(v)
        v += pv
        f += [(a + n, b + n, c + n) for a, b, c in pf]
    return v, f


def poly_ids(f):
    return [i // 2 + 1 for i in range(len(f))]  # two triangles per quad face


def run_normals(vf, scale=1.0, double_sided=False, model='vpm', sg=1):
    v, f = vf
    obj = {'handle': 1, 'name': 'SM_X_Main', 'verts': [(x * scale, y * scale, z * scale) for x, y, z in v],
           'faces': f, 'sg': [sg] * len(f), 'face_ids': poly_ids(f), 'double_sided': double_sided}
    found, info = qc.mesh_normals(obj, qc.normals_options({'model': model}))
    return found


def codes(found):
    return sorted(c for c, _, _ in found)


def source_double_faces_lmb(vf, units_per_m):
    """GeoAGR LMB (lab L05 job …124601…): thresholds in SYSTEM units (plane gap 0.02, vertex pair 0.04); each face
    is compared with the FIRST face of every other element only. Returns the number of pairs found."""
    v, f = vf
    v = [(x * units_per_m, y * units_per_m, z * units_per_m) for x, y, z in v]
    quads = [f[i:i + 2] for i in range(0, len(f), 2)]  # one element per quad in these fixtures
    found = 0
    for a in range(len(quads)):
        b = next((k for k in range(len(quads)) if k != a), None)
        for k in range(len(quads)):
            if k == a:
                continue
            first_of_k = quads[k][0]
            pa = [v[i] for i in quads[a][0]]
            pb = [v[i] for i in first_of_k]
            gap = abs(sum(pb[j][2] for j in range(3)) / 3 - sum(pa[j][2] for j in range(3)) / 3)
            near = all(min(math.dist(p, q) for q in pb) <= 0.04 for p in pa)
            if gap <= 0.02 and near and k > a:
                found += 1
            break  # only the first other element is compared (the order defect)
    return found


def test_defect_thresholds_in_system_units_cm_scene_misses_1mm():
    pair = merge(quad(0), quad(0.001))
    red_green(lambda n: n == 1, source_double_faces_lmb(pair, 100.0), len(run_normals(pair, scale=1.0)))
    # metres and centimetres give the same findings (the glue converts to metres)
    assert codes(run_normals(pair)) == ['double_face']


def test_defect_one_pair_per_face_misses_by_element_order():
    acb = merge(quad(0), quad(0, off=10), quad(0.001))
    red_green(lambda n: n >= 1, source_double_faces_lmb(acb, 1.0), len(run_normals(acb)))
    assert [ids for c, ids, _ in run_normals(acb)] == [[1, 3]]  # both faces of the pair (A and B)


@pytest.mark.parametrize('size', [1.0, 0.2])
@pytest.mark.parametrize('tilt', [0.0, 5.0])
@pytest.mark.parametrize('gap,hit', [(0.0, True), (0.001, True), (0.02, False), (0.05, False)])
def test_double_face_gap_matrix_same_in_metres(size, tilt, gap, hit):
    """L05 acceptance: pairs found exactly where the gap is below the metric threshold (5 mm, VPM-2.3-13; 2 cm is
    the allowed co-directional band), for both face sizes and 0°/5°; the angle does not depend on face size."""
    pair = merge(quad(0, size=size), quad(gap, tilt, size=size))
    assert (codes(run_normals(pair)) == ['double_face']) is hit


def source_inward_rmb(vf):
    """GeoAGR RMB (lab L05 job …125138…): a face is 'inward' when its normal points against the direction from the
    centre of the OBJECT bbox to the face centre. Returns the inward face count."""
    v, f = vf
    lo = [min(p[k] for p in v) for k in range(3)]
    hi = [max(p[k] for p in v) for k in range(3)]
    c = [(lo[k] + hi[k]) / 2 for k in range(3)]
    n_in = 0
    for a, b, d in f:
        p, q, r = v[a], v[b], v[d]
        n = qc._cross(qc._sub(q, p), qc._sub(r, p))
        fc = [(p[k] + q[k] + r[k]) / 3 for k in range(3)]
        if qc._dot(n, qc._sub(fc, c)) < 0:
            n_in += 1
    return n_in


def inward(vf):
    return sum(len(ids) for c, ids, _ in run_normals(vf) if c == 'normal_inward')


def test_defect_rmb_bbox_centre_false_inward_on_l_volume():
    red_green(lambda n: n == 0, source_inward_rmb(l_shape()), inward(l_shape()))


def test_defect_rmb_two_boxes_only_the_flipped_one():
    two = merge(box(), box((5, 0, 0), flip=True))
    far = merge(box(), box((20, 0, 0)))
    red_green(lambda n: n == 0, source_inward_rmb(far), inward(far))
    found = [ids for c, ids, _ in run_normals(two) if c == 'normal_inward']
    assert found == [[7, 8, 9, 10, 11, 12]]  # only the second box, its 6 faces


def test_inward_acceptance():
    assert inward(box()) == 0 and inward(l_shape()) == 0
    assert inward(box(flip=True)) == 6
    v, f = box()
    f[0], f[1] = (f[0][0], f[0][2], f[0][1]), (f[1][0], f[1][2], f[1][1])
    assert [ids for c, ids, _ in run_normals((v, f)) if c == 'normal_inward'] == [[1]]


def test_glass_and_flora_second_side():
    assert codes(run_normals(quad(0), double_sided=True)) == ['missing_double_side']
    assert codes(run_normals(merge(quad(0), quad(-0.005, flip=True)), double_sided=True)) == []
    assert codes(run_normals(merge(quad(0), quad(-0.001, flip=True)), double_sided=True)) == ['double_side_offset']
    # NPM-2.3-13: opacity polygons are one-sided in NPM: a second side is a double face, a single card passes
    assert codes(run_normals(merge(quad(0), quad(-0.005, flip=True)), double_sided=True, model='npm')) == ['double_face']
    assert codes(run_normals(quad(0), double_sided=True, model='npm')) == []
    # a closed pane (thin box) has both sides by construction
    assert codes(run_normals(box(s=(1, 1, 0.004)), double_sided=True)) == []
    # back-to-back faces where no second side belongs
    assert codes(run_normals(merge(quad(0), quad(-0.001, flip=True)))) == ['double_face']


def test_smoothing_groups():
    assert codes(run_normals(box(), sg=0)) == ['sg_none']
    assert codes(run_normals(box(), sg=1)) == []


def test_normals_options_and_report():
    with pytest.raises(ValueError, match='unknown'):
        qc.normals_options({'gap': 1})
    with pytest.raises(ValueError, match='positive'):
        qc.normals_options({'same_min_m': -1})
    v, f = box(flip=True)
    obj = {'handle': 7, 'name': 'SM_Bad_Main', 'verts': v, 'faces': f, 'sg': [1] * 12, 'face_ids': poly_ids(f)}
    r = qc.normals_report(ec, [obj], qc.normals_options({}), 'h')
    ec.validate_report(r)
    assert r['status'] == 'fail' and r['objects'][0]['findings'][0]['ids'] == [1, 2, 3, 4, 5, 6]
    assert r['plan']['units'] == 'm' and r['plan']['thresholds']['same_min_m'] == 0.005
    with pytest.raises(ValueError, match='empty'):
        qc.normals_report(ec, [], qc.normals_options({}), 'h')


# =====================================================================================================
# qa.sintez
# =====================================================================================================
def sintez_doc(**states):
    """{req: (state, errors, recs)} on the hp side; everything else verified."""
    rows = []
    for req in ('2.3.18', '2.3.11', '2.3.8', '2.3.17', '2.10.1'):
        st, e, r = states.get(req, ('verified', 0, 0))
        rows.append({'category': 'c', 'req_num': req, 'name': 'r' + req, 'state': st, 'auto': True,
                     'errors_count': e, 'errors': '', 'recommendations_count': r, 'recommendations': ''})
    return {'extension': 'sintez_agr_checker', 'error': None, 'hp': rows, 'lp': []}


def preflight(objects):
    return {'schema': 1, 'tool': 'preflight', 'status': 'fail' if any(c for _, _, c in objects) else 'pass',
            'objects': [{'handle': h, 'name': n, 'findings': [{'code': c, 'ids': [], 'detail': c} for c in cs]}
                        for h, n, cs in objects], 'plan': {}}


def package(triangulated=True):
    np_ = [] if triangulated else ['fail: triangulated: SM_X.fbx: [\'SM_X_Main\']']
    return {'schema': 1, 'tool': 'qa.package', 'status': 'pass', 'objects': [],
            'plan': {'reports': [{'stages': [{'id': 'V003', 'check': 'x', 'gate': 'x', 'status': 'pass',
                                              'non_pass': np_}]}]}}


def test_sintez_acceptance_one_mismatch_on_2_3_17_fails_with_the_rule():
    s = qc.sintez_verdicts(sintez_doc(**{'2.3.17': ('failed', 3, 0)}))
    rows = qc.sintez_compare(s, preflight([(1, 'SM_X_Main', [])]), package(True))
    r = qc.sintez_report(ec, rows, 'h')
    ec.validate_report(r)
    bad = [(o['name'], f['code']) for o in r['objects'] for f in o['findings']]
    assert bad == [('SINTEZ hp 2.3.17', 'sintez_mismatch')] and r['status'] == 'fail'
    assert '2.3.17' in r['objects'][[o['name'] for o in r['objects']].index('SINTEZ hp 2.3.17')]['findings'][0]['detail']


def test_sintez_acceptance_full_agreement_passes():
    s = qc.sintez_verdicts(sintez_doc(**{'2.3.17': ('failed', 3, 0)}))
    r = qc.sintez_report(ec, qc.sintez_compare(s, preflight([(1, 'SM_X_Main', [])]), package(False)), 'h')
    assert r['status'] == 'pass' and r['plan']['summary']['mismatch'] == 0
    assert {(t['req'], t['ours'], t['sintez']) for t in r['plan']['table']} >= {('2.3.17', 'fail', 'fail'),
                                                                                ('2.3.18', 'pass', 'pass')}


def test_sintez_scene_mode_findings_on_the_culprits():
    s = qc.sintez_verdicts(sintez_doc())  # SINTEZ: transforms fine
    pre = preflight([(1, 'SM_A_Main', []), (2, 'SM_B_Main', ['xform_scale'])])
    r = qc.sintez_report(ec, qc.sintez_compare(s, pre), 'h', nodes=[(1, 'SM_A_Main'), (2, 'SM_B_Main')])
    assert [(o['name'], [f['code'] for f in o['findings']]) for o in r['objects']] == \
        [('SM_A_Main', []), ('SM_B_Main', ['sintez_mismatch'])]


def test_sintez_unmatched_fail_and_review_and_broken_reports():
    s = qc.sintez_verdicts(sintez_doc(**{'2.10.1': ('failed', 1, 0), '2.3.18': ('failed', 0, 2)}))
    rows = qc.sintez_compare(s, preflight([(1, 'SM_X_Main', [])]))
    by = {r['req']: r for r in rows}
    assert by['2.10.1']['ours'] == 'not_measured' and by['2.3.18']['sintez'] == 'review'
    r = qc.sintez_report(ec, rows, 'h')
    assert sorted(f['code'] for o in r['objects'] for f in o['findings']) == ['sintez_unmatched']
    with pytest.raises(ValueError, match='run error'):
        qc.sintez_verdicts(dict(sintez_doc(), error='boom'))
    with pytest.raises(ValueError, match='hp and lp'):
        qc.sintez_verdicts({'hp': []})
    with pytest.raises(ValueError, match='verified with errors'):
        qc.sintez_verdicts(sintez_doc(**{'2.3.8': ('verified', 2, 0)}))
    with pytest.raises(ValueError, match='our report'):
        qc.sintez_compare(s)
    with pytest.raises(ValueError, match='qa.preflight'):
        qc.sintez_compare(s, {'tool': 'qa.names'})


def test_sintez_fixtures_for_the_polygon_are_valid():
    for name in ('sintez_hp_all_verified.json', 'sintez_hp_2_3_17_failed.json'):
        qc.sintez_verdicts(json.loads((FIX / name).read_text(encoding='utf-8')))


# =====================================================================================================
# qa.procedural_objects
# =====================================================================================================
CLASSES = qc.load_classes(str(PKG / 'data/procedural_classes.json'))


def scene_rows():
    return [{'handle': 1, 'name': 'Box_Ok', 'cls': 'Editable_Poly', 'superclass': 'GeometryClass'},
            {'handle': 2, 'name': 'Scatter_1', 'cls': 'ChaosScatter', 'superclass': 'GeometryClass'},
            {'handle': 3, 'name': 'People', 'cls': 'Crowd', 'superclass': 'helper', 'hidden': True},
            {'handle': 4, 'name': 'Forest_X', 'cls': 'Missing_GeomObject', 'superclass': 'GeometryClass'},
            {'handle': 5, 'name': 'Flow01', 'cls': 'Flow', 'superclass': 'GeometryClass'},
            {'handle': 6, 'name': 'Idle01', 'cls': 'IdleAreaObj', 'superclass': 'GeometryClass'}]


def test_procedural_classes_are_data_with_the_l07_list():
    names = {e['class'] for e in CLASSES.values()}
    assert {'ChaosScatter', 'CScatter', 'Flow', 'IdleAreaObj', 'Crowd', 'ScatterGeometry'} <= names
    assert {'Forest_Pro', 'Forest_Lite', 'RailClone_Pro', 'RailClone_Lite', 'MultiScatter', 'tyFlow', 'tyCache'} <= names
    assert all(e['measured'] for e in CLASSES.values() if e['class'] in
               ('ChaosScatter', 'CScatter', 'Flow', 'IdleAreaObj', 'Crowd', 'ScatterGeometry'))
    src = (PKG / 'qa9_core.py').read_text(encoding='utf-8')
    assert 'ChaosScatter' not in src and 'Forest_Pro' not in src  # the list is data, not code


def source_tris_route(rows):
    """L07: what the scene/FBX triangle route sees (qa.tris, export ok): ChaosScatter 0 tris, IdleArea 0 -> nothing
    to flag; the export reports success with 0 objects (job 20261105-123702-11647754)."""
    return []  # the triangle/readback route has no procedural check: nothing is flagged, the FBX is just empty


def test_l07_scatter_lost_silently_is_caught_before_export():
    hits, products = qc.procedural_scan(scene_rows(), CLASSES, {'chaosscatter', 'flow', 'idleareaobj', 'crowd'})
    red_green(lambda found: 2 in found, source_tris_route(scene_rows()), [h['handle'] for h in hits])
    by = {h['handle']: h['code'] for h in hits}
    assert by == {2: 'proc_object', 3: 'proc_object', 4: 'proc_missing_plugin', 5: 'proc_object', 6: 'proc_object'}
    st = {p['product']: p['status'] for p in products}
    assert st['Chaos Scatter'] == 'установлен' and st['Forest Pack Pro'] == 'плагин не установлен'


def test_procedural_report_is_the_stable_list_for_export_batch():
    rows = scene_rows()
    hits, products = qc.procedural_scan(rows, CLASSES, set())
    r = qc.procedural_report(ec, rows, hits, products, 'h')
    ec.validate_report(r)
    assert r['status'] == 'fail'
    assert [p['handle'] for p in r['plan']['procedural']] == [2, 3, 4, 5, 6] == r['plan']['blocking']
    assert set(r['plan']['procedural'][0]) == {'handle', 'name', 'class', 'superclass', 'product', 'code', 'hidden',
                                               'frozen'}
    assert r['plan']['procedural'][1]['hidden'] is True
    assert r['plan']['warnings'] == [qc.TRIS_WARNING] and 'qa.tris' in qc.TRIS_WARNING
    clean = [rows[0]]
    rc = qc.procedural_report(ec, clean, [], products, 'h')
    assert rc['status'] == 'pass' and rc['plan']['procedural'] == [] and rc['plan']['warnings'] == []
    with pytest.raises(ValueError, match='empty'):
        qc.procedural_report(ec, [], [], products, 'h')


def test_procedural_classes_file_is_strict(tmp_path):
    good = json.loads((PKG / 'data/procedural_classes.json').read_text(encoding='utf-8'))
    for mutate, word in ((lambda d: d.update(owner='D'), 'owner'), (lambda d: d.update(classes=[]), 'owner'),
                         (lambda d: d['classes'].append(dict(d['classes'][0])), 'duplicate'),
                         (lambda d: d['classes'].append({'class': 'Missing_X', 'product': 'p', 'measured': False,
                                                         'source': 's'}), 'bad class'),
                         (lambda d: d['classes'][0].pop('source'), 'class entry')):
        doc = copy.deepcopy(good)
        mutate(doc)
        p = tmp_path / 'c.json'
        p.write_text(json.dumps(doc), encoding='utf-8')
        with pytest.raises(ValueError, match=word):
            qc.load_classes(str(p))


# =====================================================================================================
# glue with a fake pymxs
# =====================================================================================================
class _P:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _Mesh:
    def __init__(self, v, f, sg):
        self.v, self.f, self.sg = v, f, sg
        self.numverts, self.numfaces = len(v), len(f)


class _Layer:
    isHidden = False


class _Node:
    def __init__(self, handle, name, cls='Editable_Mesh', superclass='GeometryClass', mesh=None, sg=1):
        self.handle, self.name, self.cls, self.superclass = handle, name, cls, superclass
        self.mesh = mesh
        self.sg = sg
        self.isHidden = False
        self.isFrozen = False
        self.layer = _Layer()
        self.material = None


class _Classes:
    def __init__(self, names):
        self.classes = names


class FakeRT:
    TriMeshGeometry = 'TriMeshGeometry'
    Editable_Poly = 'Editable_Poly'
    Multimaterial = 'Multimaterial'
    undefined = None

    def __init__(self, nodes, unit='meters', scale=1.0):
        self.nodes = nodes
        self.selection = []
        self.units = types.SimpleNamespace(SystemType=unit, SystemScale=scale)
        self.GeometryClass = _Classes(['Box', 'ChaosScatter', 'Flow', 'IdleAreaObj'])
        self.helper = _Classes(['Dummy', 'Crowd'])
        self.writes = []

    @property
    def geometry(self):
        return [n for n in self.nodes if n.superclass == 'GeometryClass']

    @property
    def objects(self):
        return list(self.nodes)

    def isValidNode(self, n):
        return True

    def getHandleByAnim(self, n):
        return n.handle

    def getAnimByHandle(self, h):
        return next(n for n in self.nodes if n.handle == h)

    def canConvertTo(self, n, t):
        return n.mesh is not None

    def snapshotAsMesh(self, n):
        v, f = n.mesh
        return _Mesh(v, f, n.sg)

    def getVert(self, m, i):
        return _P(*m.v[i - 1])

    def getFace(self, m, i):
        a, b, c = m.f[i - 1]
        return _P(a + 1, b + 1, c + 1)

    def getFaceSmoothGroup(self, m, i):
        return m.sg

    def delete(self, m):
        pass

    def classOf(self, n):
        return n.cls

    def superClassOf(self, n):
        return n.superclass

    def __setattr__(self, key, value):
        if key in ('renderers', 'viewport', 'NitrousGraphicsManager') or (hasattr(self, 'writes') and key == 'selection'
                                                                          and value != []):
            raise AssertionError('read-only button wrote ' + key)
        object.__setattr__(self, key, value)


@pytest.fixture
def fake(monkeypatch):
    holder = {}

    def install(nodes, unit='meters', scale=1.0):
        rt = FakeRT(nodes, unit, scale)
        mod = types.ModuleType('pymxs')
        mod.runtime = rt
        monkeypatch.setitem(sys.modules, 'pymxs', mod)
        holder['rt'] = rt
        return rt
    return install


def _ctx(core, options, agr=None):
    emax = types.SimpleNamespace(snapshot=lambda nodes: [[n.handle, n.name] for n in nodes])
    return types.SimpleNamespace(agr=agr, core=core, edit=ec, emax=emax, options=dict(options))


def _scaled(vf, k):
    v, f = vf
    return [(x * k, y * k, z * k) for x, y, z in v], f


def test_glue_normals_metres_and_centimetres_agree(fake):
    scenes = {}
    for unit, k in (('meters', 1.0), ('centimeters', 100.0)):
        fake([_Node(1, 'SM_Pair_Main', mesh=_scaled(merge(quad(0), quad(0.001)), k)),
              _Node(2, 'SM_Box_Main', mesh=_scaled(box(flip=True), k)),
              _Node(3, 'SM_Glass_001_MainGlass', mesh=_scaled(quad(0), k)),
              _Node(4, 'Light01', superclass='light')], unit=unit)
        r = qm.qa_normals(_ctx(qc, {}), 'preview', None, None)
        ec.check_preview('qa.normals', r)
        scenes[unit] = [(o['name'], [(f['code'], f['ids']) for f in o['findings']]) for o in r['objects']]
        assert r['plan']['m_per_unit'] == pytest.approx(1.0 / k)
    assert scenes['meters'] == scenes['centimeters']
    assert scenes['meters'] == [('SM_Pair_Main', [('double_face', [1, 2, 3, 4])]),
                                ('SM_Box_Main', [('normal_inward', list(range(1, 13)))]),
                                ('SM_Glass_001_MainGlass', [('missing_double_side', [1, 2])])]


def test_glue_units_never_use_decode_value(fake):
    rt = fake([], unit='centimeters', scale=1.0)
    rt.units.decodeValue = lambda s: (_ for _ in ()).throw(AssertionError('decodeValue used'))
    assert qm.metres_per_unit(rt) == 0.01
    rt.units.SystemType = 'parsecs'
    with pytest.raises(ValueError, match='unmapped'):
        qm.metres_per_unit(rt)
    src = (PKG / 'qa9_max.py').read_text(encoding='utf-8') + (PKG / 'facade_max.py').read_text(encoding='utf-8')
    assert 'decodeValue(' not in src


def test_glue_address_scene_and_options(fake):
    fake([_Node(1, 'SM_Tverskaya_7_Main'), _Node(2, 'SM_Tverskaya__7_001_Main'), _Node(3, 'UCX_SM_Tverskaya_7_Main_001')])
    r = qm.qa_address(_ctx(qc, {}), 'preview', None, None)
    assert [(o['name'], [f['code'] for f in o['findings']]) for o in r['objects']] == \
        [('SM_Tverskaya_7_Main', []), ('SM_Tverskaya__7_001_Main', ['addr_parts'])]
    assert [s['item'] for s in r['plan']['skipped']] == ['UCX_SM_Tverskaya_7_Main_001']
    r2 = qm.qa_address(_ctx(qc, {'addresses': ['Tverskaya_7', 'Qwxz_7']}), 'preview', None, None)
    assert [o['handle'] for o in r2['objects']] == [1, 2] and r2['plan']['source'] == 'options'
    with pytest.raises(ValueError, match='unknown'):
        qm.qa_address(_ctx(qc, {'x': 1}), 'preview', None, None)
    with pytest.raises(ValueError, match='read-only'):
        qm.qa_address(_ctx(qc, {}), 'apply', None, {})


def test_glue_sintez_runs_preflight_on_the_scene(fake, tmp_path):
    fake([_Node(1, 'SM_A_Main'), _Node(2, 'SM_B_Main')])
    calls = []

    def checks_070(tool, nodes, select):
        calls.append((tool, nodes, select))
        return preflight([(1, 'SM_A_Main', []), (2, 'SM_B_Main', ['xform_rotation'])])
    agr = types.SimpleNamespace(checks_070=checks_070)
    r = qm.qa_sintez(_ctx(qc, {'sintez': str(FIX / 'sintez_hp_all_verified.json')}, agr), 'preview', None, None)
    assert calls == [('preflight', None, False)]
    assert [(o['name'], [f['code'] for f in o['findings']]) for o in r['objects']] == \
        [('SM_A_Main', []), ('SM_B_Main', ['sintez_mismatch'])]
    with pytest.raises(ValueError, match='options.sintez'):
        qm.qa_sintez(_ctx(qc, {}, agr), 'preview', None, None)


def test_glue_procedural_all_objects_and_runtime_contract_for_export_batch(fake, monkeypatch):
    nodes = [_Node(1, 'Box_Ok', 'Editable_Poly'), _Node(2, 'Scatter_1', 'ChaosScatter'),
             _Node(3, 'People', 'Crowd', 'helper'), _Node(4, 'Lost', 'Missing_GeomObject')]
    rt = fake(nodes)
    rt.selection = []
    rtm = _load('runtime.py', 'agr_runtime_qa9_t')
    r = rtm.edits_090('qa.procedural_objects', 'preview')
    assert r['tool'] == 'qa.procedural_objects' and r['status'] == 'fail'
    assert [(p['handle'], p['class'], p['code']) for p in r['plan']['procedural']] == \
        [(2, 'ChaosScatter', 'proc_object'), (3, 'Crowd', 'proc_object'), (4, 'Missing_GeomObject', 'proc_missing_plugin')]
    assert r['plan']['blocking'] == [2, 3, 4]
    st = {p['product']: p['status'] for p in r['plan']['products']}
    assert st['Chaos Scatter'] == 'установлен' and st['tyFlow'] == 'плагин не установлен'
    with pytest.raises(ValueError, match='read-only'):
        rtm.edits_090('qa.procedural_objects', 'apply', r)
    clean = rtm.edits_090('qa.procedural_objects', 'preview', nodes=[nodes[0]])
    assert clean['status'] == 'pass' and clean['plan']['procedural'] == []
