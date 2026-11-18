"""new-case: #1441 council reconciliation against source-backed current entrypoints; no DCC execution."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/architecture'))
import call_chains
import duplicate_guard as guard
import route_map


def rows():
    return guard.rows_of(guard.load_maps(ROOT))


def test_council_responsibilities():
    expected = {
        'jobs/KPP1/scripts/vpm_ucx.py:50': 'own-duty',
        'jobs/PSU275/scripts/vpm_ucx.py:45': 'own-duty',
        'jobs/TEC26-OKS/scripts/ucx_tri_core.py:44': 'wrapper',
        'jobs/TEC26-OKS/scripts/ucx_triangulate_vpm.py:29': 'wrapper',
        'jobs/elv-tc-vpm/scripts/ucx_dev_by_part_v001.py:24': 'own-duty',
        'jobs/elv-tc-vpm/scripts/run_agr_checker_v003.py::<module>': 'own-duty',
    }
    for at, status in expected.items():
        found = [r for r in rows() if r.at == at]
        assert found, at
        assert all(r.status == status for r in found), (at, found)


def test_merged_migrations_keep_the_new_owners_without_reviving_copies():
    current = rows()
    migrated = {
        'jobs/KPP1/scripts/run_agr_checker.py',
        'jobs/TEC26-OKS/scripts/run_agr_checker.py',
        'jobs/KPP1/scripts/qa_master.py',
        'jobs/TEC26-OKS/scripts/qa_master.py',
        'jobs/KPP1/scripts/vpm_uv.py',
        'jobs/TEC26-OKS/scripts/vpm_uv.py',
    }
    # #1593 records the UV wrappers as described path:line rows, not formula copies.
    uv_wrappers = {'jobs/KPP1/scripts/vpm_uv.py', 'jobs/TEC26-OKS/scripts/vpm_uv.py'}
    assert not any(r.rel in migrated - uv_wrappers for r in current)
    assert {r.rel for r in current if r.rel in uv_wrappers} == uv_wrappers
    assert all(r.status == 'wrapper' and not r.rule and r.owner == 'tools/blender/vpm_uv.py'
               for r in current if r.rel in uv_wrappers)
    assert guard.RULES['vpm-uv'] == 'tools/blender/vpm_uv.py'
    uv = next(c for c in guard.load_maps(ROOT)['contexts']['contexts'] if c['id'] == 'vpm-uv')
    assert uv['owner'] == guard.RULES['vpm-uv']
    assert guard.RULES['sintez-checker'] == 'tools/blender/sintez_checker.py'
    assert guard.RULES['master-qa'] == 'tools/blender/qa_master.py'
    assert not any(r.rule == 'udim-tile' and r.step == '#1397' for r in current)
    assert any(r.rule == 'udim-tile' and r.rel == 'tools/source/measure_spec_blender.py'
               and r.status == 'own-duty' for r in current)


def test_current_entrypoints():
    _, chains = call_chains.load_live(ROOT)
    for rel in ('jobs/KPP1/scripts/build_kpp1.py', 'jobs/TEC26-OKS/scripts/package_vpm.py',
                'jobs/TEC26-OKS/scripts/vpm_uv.py', 'jobs/elv-tc-vpm/scripts/package_vpm_v006.py'):
        assert rel in chains, rel
    roof = [r for r in rows() if r.rel == 'jobs/KPP1/scripts/build_kpp1.py' and r.context == 'roof']
    assert roof and roof[0].status == 'wrapper' and roof[0].step is None   # #1381: plate from roof_core.hole_plate


def test_elv_not_delivered():
    maps = guard.load_maps(ROOT)
    assert 'jobs/elv-tc-vpm' not in guard.finished_jobs(ROOT, maps['contexts'])
    assert all(r.status != 'historical' for r in rows() if r.rel.startswith('jobs/elv-tc-vpm/'))
    for version in range(1, 7):
        found = [r for r in rows() if r.at == f'jobs/elv-tc-vpm/scripts/package_vpm_v{version:03d}.py::<module>']
        assert len(found) == 1
        assert found[0].status == ('live-bypass' if version == 6 else 'superseded')
        if version == 6:
            assert found[0].step == '#1377'


def test_missing_owners_present():
    owners = {c['owner'] for c in route_map.load_context_maps(ROOT)['contexts']['contexts']}
    assert {'src/dt_ai/geometry/ucx_build.py', 'jobs/PSU275/scripts/vpm_stage5_oks.py',
            'src/dt_ai/geometry/shell.py', 'adapters/max/agr_tools/vpm_core.py'} <= owners


def test_superseded_is_not_a_live_or_delivered_claim(tmp_path):
    (tmp_path / 'draft.py').write_text('def f():\n    return 1\n', encoding='utf-8')
    (tmp_path / 'owner.py').write_text('def f():\n    return 2\n', encoding='utf-8')
    row = guard.Row('m', 'c', 'owner.py', 'draft.py::f', 'draft.py', 'f', None,
                    'superseded', None, 'Заменён новым кандидатом', '#1441', '', '', 'test')
    assert guard.status_problems(tmp_path, [row], {}, {}, {}, frozenset(), own_duty_baseline=frozenset()) == []
    problems = guard.status_problems(tmp_path, [row], {'draft.py': ['draft.py']},
                                     {'draft.py': 'current command'}, {}, frozenset(), own_duty_baseline=frozenset())
    assert any('superseded' in p and 'live command' in p for p in problems)


def test_superseded_requires_reason():
    with pytest.raises(ValueError, match='superseded needs `why`'):
        guard.rows_of({'m': {'shared_kernel': {'id': 'x', 'duplicates': [
            {'at': 'draft.py::f', 'status': 'superseded'}]}}})


@pytest.mark.parametrize('entry', [{}, {'owner': 'run.py'},
    {'owner': 'run.sh', 'evidence': 'command.sh', 'match': 'run.py'},
    {'owner': './run.py', 'evidence': 'command.sh', 'match': 'run.py'},
    {'owner': 'run.py', 'evidence': 'missing.sh', 'match': 'run.py'},
    {'owner': 'run.py', 'evidence': 'command.sh', 'match': 'stale.py'},
    {'owner': 'run.py', 'evidence': 'command.sh', 'match': ''}])
def test_entrypoints_fail_closed(tmp_path, entry):
    (tmp_path / 'run.py').write_text('pass\n', encoding='utf-8')
    (tmp_path / 'command.sh').write_text('python run.py\n', encoding='utf-8')
    with pytest.raises(ValueError, match='entrypoint'):
        call_chains._route_roots(tmp_path, {}, {'m': {'entrypoints': [entry]}})


def test_entrypoints_evidence_is_required_and_duplicates_are_idempotent(tmp_path):
    (tmp_path / 'run.py').write_text('pass\n', encoding='utf-8')
    (tmp_path / 'command.sh').write_text('python run.py\n', encoding='utf-8')
    entry = {'owner': 'run.py', 'evidence': 'command.sh', 'match': 'python run.py'}
    roots = call_chains._route_roots(tmp_path, {}, {'m': {'entrypoints': [entry, entry]}})
    assert list(roots) == ['run.py']
    (tmp_path / 'command.sh').write_text('python other.py\n', encoding='utf-8')
    with pytest.raises(ValueError, match='entrypoint'):
        call_chains._route_roots(tmp_path, {}, {'m': {'entrypoints': [entry]}})


def test_wrapper_chain_has_real_owner_and_loader_not_just_a_path_mention(tmp_path):
    real_rows = rows()
    for at, owner in [
        ('jobs/TEC26-OKS/scripts/ucx_tri_core.py:44', 'adapters/max/agr_tools/geom_core.py'),
        ('jobs/TEC26-OKS/scripts/ucx_triangulate_vpm.py:29', 'jobs/TEC26-OKS/scripts/ucx_tri_core.py')]:
        found = [r for r in real_rows if r.at == at]
        assert found and all(r.owner == owner for r in found)
        if found[0].status == 'wrapper':
            assert guard.calls_owner(ROOT, found[0])
    (tmp_path / 'probe.py').write_text(
        "PATH = 'owner.py'\ndef diagnostic():\n    print(PATH)\n"
        "def copy():\n    diagnostic()\n    return 1\n", encoding='utf-8')
    row = guard.Row('m', 'c', 'owner.py', 'probe.py::copy', 'probe.py', 'copy', None,
                    'wrapper', None, '', '#1441', '', '', 'test')
    assert not guard.calls_owner(tmp_path, row)


_LOADER_OWNER = 'adapters/max/agr_tools/geom_core.py'


def _loader_is_owner_wrapper(tmp_path, body):
    (tmp_path / 'probe.py').write_text(
        f'import importlib.util\nGC = {_LOADER_OWNER!r}\ndef other():\n'
        + ''.join(f'    {line}\n' for line in body.splitlines())
        + 'def copy():\n    return other().degrees([])\n', encoding='utf-8')
    row = guard.Row('m', 'c', _LOADER_OWNER, 'probe.py::copy', 'probe.py', 'copy', None,
                    'wrapper', None, '', '#1486', '', '', 'test')
    return guard.calls_owner(tmp_path, row)


_LOAD_OWNER = ('spec = importlib.util.spec_from_file_location("g", GC)\n'
               'm = importlib.util.module_from_spec(spec)\n'
               'spec.loader.exec_module(m)\nreturn m')


def test_unrelated_loader_is_not_an_owner_wrapper(tmp_path):
    assert not _loader_is_owner_wrapper(tmp_path, 'print("owner at", GC)\n'
                                        + _LOAD_OWNER.replace('GC', '"other.py"'))


@pytest.mark.parametrize('location', ['GC', repr(_LOADER_OWNER), '"other.py"'])
@pytest.mark.parametrize('module_source', ['spec', 'unrelated'])
@pytest.mark.parametrize('executing_spec', ['spec', 'unrelated'])
@pytest.mark.parametrize('returned', ['m', 'decoy'])
def test_loader_owner_provenance(tmp_path, location, module_source, executing_spec, returned):
    body = (f'spec = importlib.util.spec_from_file_location("g", {location})\n'
            'unrelated = importlib.util.spec_from_file_location("x", "other.py")\n'
            f'm = importlib.util.module_from_spec({module_source})\n'
            'decoy = importlib.util.module_from_spec(unrelated)\n'
            f'{executing_spec}.loader.exec_module(m)\nreturn {returned}')
    expected = location != '"other.py"' and module_source == executing_spec == 'spec' and returned == 'm'
    assert _loader_is_owner_wrapper(tmp_path, body) is expected


@pytest.mark.parametrize('body', [
    'pass',
    _LOAD_OWNER.splitlines()[0] + '\nreturn spec',
    _LOAD_OWNER.replace('spec.loader.exec_module(m)\nreturn m', 'return m\nspec.loader.exec_module(m)'),
    _LOAD_OWNER.replace('return m', 'm = object()\nreturn m'),
    _LOAD_OWNER.replace('spec.loader.exec_module(m)', 'def nested():\n    spec.loader.exec_module(m)'),
    _LOAD_OWNER.replace('"g", GC', 'GC, "other.py"'),
    _LOAD_OWNER.replace('"g", GC', 'GC, 1e999'),
    _LOAD_OWNER.replace('"g", GC', '"g", "not_geom_core.py"'),
])
def test_incomplete_owner_loader(tmp_path, body):
    assert not _loader_is_owner_wrapper(tmp_path, body)


def test_loader_classification_resets(tmp_path):
    for location, expected in [('GC', True), ('"other.py"', False), ('"other.py"', False), ('GC', True)]:
        assert _loader_is_owner_wrapper(tmp_path, _LOAD_OWNER.replace('GC', location)) is expected


def test_module_level_builder_is_an_explicit_owner_not_an_invented_function():
    import route_map
    events, contexts, _ = route_map.render(ROOT)
    assert route_map.verify_references(ROOT, events, contexts) == []
    c = next(c for c in contexts['contexts'] if c['id'] == 'psu-ucx-build')
    assert c['functions'][0]['name'] == '<module>'
    c['functions'][0]['name'] = 'invented_builder'
    assert any('invented_builder' in p for p in route_map.verify_references(ROOT, events, contexts))
