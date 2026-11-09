"""new-case: AGR Tools 0.6.0 panel model, generated entry points, bundle and MAXScript hygiene (#808)."""
import importlib.util
import json
import math
import random
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
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


m = _load(PKG / 'ui_model.py', 'agr_tools_ui_model')
builder = _load(ROOT / 'tools/max/build_agr_tools.py', 'agr_builder_ui')
icons = _load(ROOT / 'tools/max/agr_icons.py', 'agr_icons_ui')

OLD_TOOLS = {'xview', 'cleanup', 'apply', 'matid', 'nudge', 'nudge_apply', 'atlas', 'atlas_apply', 'ucx',
             'ucx_apply', 'texel', 'export', 'names', 'tris', 'textures', 'pivot', 'geojson'}
NEW_070 = {'census', 'units', 'perimeter_drop', 'material_type', 'ucx_audit', 'sets_count', 'fbx_split', 'glass',
           'preflight', 'scene_hygiene', 'xform', 'zero_area'}  # 0.7.0 (#860)
NEW_080 = {'scene.missing_maps', 'model.triangulate', 'tex.format_fix', 'tex.placeholders', 'ucx.triangulate',
           'ucx.rename', 'udim.ids_to_udims', 'qa.names_fix', 'qa.package', 'export.geojson_write',
           'export.ground_fbx', 'export.pivot_place', 'export.zip'}  # 0.8 (#908): tool == plan row id
NEW_090 = {'tex.erm_normal_check', 'tex.finish_map', 'udim.matid_unwrap', 'udim.slots', 'atlas.flora',
           'atlas.groundel', 'place.flora_repair', 'place.maf_checks', 'place.replace', 'place.schedule',
           'place.drop_to_ground', 'qa.address', 'qa.facade_compare', 'qa.normals', 'qa.sintez', 'export.batch',
           'scene.maps_usage', 'light.check', 'qa.procedural_objects'}  # 0.9 (#979): tool == plan row id
ALL_TOOLS = OLD_TOOLS | NEW_070 | NEW_080 | NEW_090


def ui_branches():
    """Every tool string runtime.ui() accepts, read from its source."""
    src = (PKG / 'runtime.py').read_text(encoding='utf-8')
    body = src[src.index('def ui(tool):'):src.index('_panel = None')]
    tools = set(re.findall(r"tool == '(\w+)'", body))
    tools |= set(re.findall(r"'(\w+)'", re.search(r"CHECKS_050 = \(([^)]*)\)", src).group(1)))
    tools |= set(re.findall(r"'(\w+)'", re.search(r"CHECKS_070 = \(([^)]*)\)", src).group(1)))
    tools |= {'xview', 'matid'}
    tools |= set(re.findall(r"'([\w.]+)': \('", re.search(r"EDITS_080 = \{(.*?)\n\}", src, re.S).group(1)))
    tools |= set(re.findall(r"'([\w.]+)': \('", re.search(r"EDITS_090 = \{(.*?)\n\}", src, re.S).group(1)))
    return tools


def test_every_existing_action_is_in_the_panel_once():
    assert ui_branches() == ALL_TOOLS
    assert {a.tool for a in m.ACTIONS} == ALL_TOOLS
    assert len({a.id for a in m.ACTIONS}) == len(m.ACTIONS) == 61
    assert len({a.macro for a in m.ACTIONS}) == 61
    assert sum(len(acts) for _, acts in m.sections()) == 61
    assert [t for t, _ in m.sections()] == ['Проверки', 'UV и атласы', 'Коллизии UCX', 'Экспорт', 'GeoJSON',
                                            'Сдача (копии)', 'Проверить и выделить',
                                            'Исправить — копии / undo / новые файлы']
    assert set(a.icon for a in m.ACTIONS) <= set(icons.names())


def test_tooltips_say_what_and_requirement():
    for a in m.ACTIONS:
        tip = m.tooltip(a)
        assert a.tip in tip and 'Треб.:' in tip and a.reqs
        assert re.search(r'[А-Яа-я]', a.tip), a.tip
        assert '"' not in tip


@pytest.mark.parametrize('bad', ['', 'XVIEW', 'unknown', None, 'cleanup_apply '])
def test_unknown_action_is_an_error_naming_it(bad):
    with pytest.raises(KeyError, match='unknown AGR Tools action'):
        m.action(bad)


def test_cleanup_apply_maps_to_the_runtime_apply_branch():
    assert m.action('cleanup_apply').tool == 'apply' and m.action('apply').id == 'cleanup_apply'


def _report(tool, objs):
    return {'schema': 1, 'tool': tool, 'status': 'fail' if any(f for _, _, f in objs) else 'pass',
            'objects': [{'handle': h, 'name': n, 'findings': f} for h, n, f in objs]}


def test_rows_one_per_finding_or_ok():
    r = _report('xview', [(1, 'A', []), (2, 'B', [{'code': 'overlap_faces', 'ids': [3, 4], 'detail': 'x'},
                                                 {'code': 'overlap_vertices', 'ids': [1]}])])
    rows = m.rows(r)
    assert [(x.name, x.ok, x.code) for x in rows] == [('A', True, 'ok'), ('B', False, 'overlap_faces'),
                                                      ('B', False, 'overlap_vertices')]
    assert m.summary(rows) == 'Ошибок 2 · ОК 1'


@pytest.mark.parametrize('bad', [None, [], {'objects': []}, {'tool': 'x', 'objects': 'no'},
                                 {'tool': 'x', 'objects': [{'name': 'a'}]},
                                 {'tool': 'texel'}, {'tool': 'texel', 'status': 'not_run'}])
def test_rows_fail_closed(bad):
    with pytest.raises(ValueError):
        m.rows(bad)


def test_summary_report_without_objects():
    assert m.rows({'tool': 'export', 'status': 'fail'})[0].ok is False
    assert m.rows({'tool': 'export', 'status': 'pass'})[0].ok is True


def _report_shapes():
    """Every report shape the panel can show: real geojson_report (pass/fail/missing file/crash),
    real export _blank (clean, stopped by a gate, texel-only stop, object findings), readback-failed export,
    batch pass/fail and cancelled partials (clean and dirty), summary-only texel/export reports."""
    checks = _load(PKG / 'checks_core.py', 'agr_checks_core_ui')
    export = _load(PKG / 'export_core.py', 'agr_export_core_ui')
    ok = {'name': 'crs', 'status': 'pass', 'observed': 'EPSG:4326', 'expected': 'EPSG:4326'}
    bad = {'name': 'crs', 'status': 'fail', 'observed': 'x', 'expected': 'y'}
    rev = {'name': 'height', 'status': 'review', 'observed': '?', 'expected': '>0'}
    out = {
        'geojson_pass': checks.geojson_report('C:/x/a.geojson', lambda p: [ok]),
        'geojson_fail': checks.geojson_report('C:/x/a.geojson', lambda p: [bad]),
        'geojson_fail_mixed': checks.geojson_report('C:/x/a.geojson', lambda p: [ok, bad, rev]),
        'geojson_review_only': checks.geojson_report('C:/x/a.geojson', lambda p: [rev]),
        'geojson_no_file': checks.geojson_report('', lambda p: [ok]),
        'geojson_wrong_ext': checks.geojson_report('C:/x/a.txt', lambda p: [ok]),
        'geojson_crash': checks.geojson_report('C:/x/a.geojson', lambda p: 1 / 0),
    }
    clean = [{'handle': 1, 'name': 'A', 'findings': []}]
    dirty = [{'handle': 1, 'name': 'A', 'findings': [{'code': 'out_of_range', 'ids': [1], 'detail': 'x'}]}]
    for key, stopped, findings in (('export_pass', None, clean), ('export_stopped', 'xview', clean),
                                   ('export_stopped_no_objects', 'cleanup', []),
                                   ('export_texel_stop', 'texel', clean), ('export_findings', None, dirty)):
        out[key] = export._blank([], {}, 'C:/x/o.fbx', 'C:/x/o.json', 'd', [], stopped, findings, [], None)
    readback = export._blank([], {}, 'C:/x/o.fbx', 'C:/x/o.json', 'd', [], None, clean, [], None)
    readback['status'] = 'fail'  # export_core: read-back mismatch flips only the status
    out['export_readback_fail'] = readback
    out['batch_pass'] = m.merge('xview', [fake_xview([1, 2, 3])])
    out['batch_fail'] = m.merge('xview', [fake_xview(list(range(1, 15)))])
    for key, nodes in (('cancelled_clean', [1, 2, 3, 4, 5, 6, 8, 9]), ('cancelled_dirty', list(range(1, 30)))):
        state = {'n': 0}

        def cancel(state=state):
            state['n'] += 1
            return state['n'] > 1
        with pytest.raises(m.Cancelled) as exc:
            m.run_batched('xview', fake_xview, nodes, 4 if key == 'cancelled_clean' else 10,
                          lambda d, t: None, cancel)
        out[key] = exc.value.partial
    out['texel_pass'] = {'tool': 'texel', 'status': 'pass'}
    out['texel_fail'] = {'tool': 'texel', 'status': 'fail'}
    return out


def test_rows_fail_report_always_has_error_row():
    """Invariant (#808 review P1): status == 'fail' <=> the table shows >= 1 error row, for every report shape."""
    shapes = _report_shapes()
    assert {k for k, r in shapes.items() if r['status'] == 'fail'} >= {
        'geojson_fail', 'geojson_fail_mixed', 'geojson_review_only', 'geojson_no_file', 'geojson_wrong_ext',
        'geojson_crash', 'export_stopped', 'export_stopped_no_objects', 'export_findings',
        'export_readback_fail', 'batch_fail', 'cancelled_clean', 'cancelled_dirty', 'texel_fail'}
    for key, report in shapes.items():
        rows = m.rows(report)
        bad, _ = m.counts(rows)
        assert (report['status'] == 'fail') == (bad > 0), key


def test_rows_geojson_fail_rows_name_each_failed_check():
    r = _report_shapes()['geojson_fail_mixed']
    bad = [x for x in m.rows(r) if not x.ok]
    assert [(x.check, x.code) for x in bad] == [('geojson', 'crs'), ('geojson', 'height: review')]
    assert 'x' in bad[0].detail and 'y' in bad[0].detail
    assert m.summary(m.rows(r)).startswith('Ошибок 2')


def test_rows_cancelled_and_stopped_say_why():
    s = _report_shapes()
    assert [x.code for x in m.rows(s['cancelled_clean']) if not x.ok] == ['cancelled']
    assert [x.code for x in m.rows(s['export_stopped']) if not x.ok] == ['stopped']
    assert 'xview' in [x.detail for x in m.rows(s['export_stopped']) if not x.ok][0]


@pytest.mark.parametrize('bad', [
    {'tool': 'xview', 'status': 'pass', 'objects': [{'handle': 1, 'name': 'A', 'findings': [{'code': 'c'}]}]},
    {'tool': 'xview', 'status': 'not_run', 'objects': []},
    {'tool': 'xview', 'objects': []},
    {'tool': 'geojson', 'status': 'pass', 'objects': [], 'plan': {'findings': [{'name': 'crs', 'status': 'fail'}]}},
])
def test_rows_inconsistent_or_unknown_status_raises(bad):
    with pytest.raises(ValueError):
        m.rows(bad)


def fake_xview(chunk):
    return _report('xview', [(h, 'N%d' % h, [] if h % 7 else [{'code': 'overlap_faces', 'ids': [h]}])
                             for h in chunk])


def test_batched_run_equals_one_shot_for_random_sizes():
    rnd = random.Random(808)
    for _ in range(200):
        n, size = rnd.randint(1, 1200), rnd.randint(1, 60)
        nodes = list(range(1, n + 1))
        seen = []
        got = m.run_batched('xview', fake_xview, nodes, size, lambda d, t: seen.append((d, t)), lambda: False)
        assert got == m.merge('xview', [fake_xview(nodes)])
        assert seen[0] == (0, n) and seen[-1] == (n, n)
        assert [d for d, _ in seen] == sorted(d for d, _ in seen)
        assert len(seen) == math.ceil(n / size) + 1


def test_cancel_stops_before_next_chunk_and_never_passes():
    calls = []
    state = {'n': 0}

    def cancelled():
        state['n'] += 1
        return state['n'] > 3

    with pytest.raises(m.Cancelled) as exc:
        m.run_batched('xview', lambda c: calls.append(c) or fake_xview(c), list(range(1, 1001)), 25,
                      lambda d, t: None, cancelled)
    assert len(calls) == 3 and exc.value.done == 75
    assert len(exc.value.partial['objects']) == 75
    # fail-closed: every finished chunk is clean, still the cancelled report is never 'pass'
    with pytest.raises(m.Cancelled) as clean_exc:
        flags = iter([False, True])
        m.run_batched('xview', lambda c: _report('xview', [(h, 'N', []) for h in c]), [1, 2, 3], 1,
                      lambda d, t: None, lambda: next(flags))
    assert clean_exc.value.partial['status'] == 'fail'
    assert clean_exc.value.partial['cancelled'] == {'done': 1, 'total': 3}
    assert m.rows(clean_exc.value.partial)[0].ok is True  # row itself is clean; the report is not a pass
    with pytest.raises(m.Cancelled) as first:
        m.run_batched('xview', fake_xview, [1, 2], 1, lambda d, t: None, lambda: True)
    assert first.value.partial is None and first.value.done == 0


def test_batched_fail_closed():
    with pytest.raises(ValueError, match='empty'):
        m.run_batched('xview', fake_xview, [], 5, lambda d, t: None, lambda: False)
    with pytest.raises(ValueError, match='chunk size'):
        m.chunks([1], 0)
    with pytest.raises(ValueError, match='duplicate handle'):
        m.run_batched('xview', fake_xview, [1, 1], 1, lambda d, t: None, lambda: False)
    with pytest.raises(ValueError, match='another tool'):
        m.merge('xview', [_report('matid', [])])


def test_percent_bounds():
    assert m.percent(0, 0) == 0 and m.percent(5, 10) == 50 and m.percent(11, 10) == 100
    assert m.percent(-1, 10) == 0


def simulate_gaps(costs, budget):
    """Gaps closed by the same object_pump decision the panel uses.

    One object is atomic. Empty, partial and unsupported cost lists are an error
    before any gap is returned.
    """
    if isinstance(costs, (str, bytes)) or not isinstance(costs, (list, tuple)):
        raise ValueError('unsupported pump costs')
    if len(costs) == 0:
        raise ValueError('empty pump costs')
    since = estimate = 0.0
    groups = []
    group = []
    open_gap = 0.0
    for raw in costs:
        pump, since, estimate = m.object_pump(since, estimate, raw, budget)
        spent = m.check_pump_cost(raw)
        open_gap += spent
        group.append(spent)
        if pump:
            groups.append((open_gap, group))
            open_gap = 0.0
            group = []
    if group:
        groups.append((open_gap, group))
    if not groups:
        groups.append((0.0, []))
    return groups


def test_pump_gaps_is_absent_from_the_bundle():
    """The offline slicer must not ship: the panel decides with object_pump."""
    text = (PKG / 'ui_model.py').read_text(encoding='utf-8')
    assert 'pump_gaps' not in text
    assert not hasattr(m, 'pump_gaps')


def test_event_pumps_follow_elapsed_cost_not_object_count():
    """Invariant: the panel pumps by object_pump, on elapsed cost, not object count.

    A huge cost is atomic, so a gap is at most the budget plus that one object.
    Sequences whose costs are small (each one fits in the headroom under the
    0.1 s limit, or an equal per-object cost under that limit) stay strictly
    under PUMP_GAP_LIMIT_S. The panel budget itself stays strictly under the limit.

    Probe: the same generated sequences as before, plus a brute force of mixed,
    headroom-small and equal costs. Empty, partial, unsupported, NaN/inf,
    negative, bool and a budget sitting on the limit are errors from object_pump.
    """
    budget = m.PUMP_BUDGET_S
    assert budget < m.PUMP_GAP_LIMIT_S
    headroom = m.PUMP_GAP_LIMIT_S - budget
    assert headroom > 0.0
    scale = math.nextafter(m.PUMP_GAP_LIMIT_S, 0.0)
    rnd = random.Random(868)
    sequences = []
    mixed = [0.0, 0.0, rnd.random() * (scale * 0.5), 50.0, 0.0, scale * 0.99, 1e3]
    for _ in range(30):
        sequences.append([rnd.choice((0.0, rnd.random() * scale * 0.5, 80.0)) for _ in range(40)])
    sequences.append(mixed)
    sequences.append([0.0] * 20)
    sequences.append([50.0])
    sequences.append([0.06] * 25)  # one count-based chunk: 1.5 s if pumped every 25
    brute = random.Random(898)
    for _ in range(40):
        sequences.append([
            brute.choice((0.0, brute.random() * headroom, brute.choice((50.0, 80.0, 1e3, 1e6))))
            for _ in range(brute.randint(1, 48))
        ])
    small_sequences = [[0.0] * 20]
    for _ in range(40):
        small_sequences.append([brute.random() * headroom for _ in range(brute.randint(1, 80))])
    equal_costs = [0.06]
    for _ in range(15):
        equal_costs.append(brute.random() * math.nextafter(m.PUMP_GAP_LIMIT_S, 0.0))
    for cost in equal_costs:
        small_sequences.append([cost] * 25)
    probed = 0
    for costs in sequences:
        groups = simulate_gaps(costs, budget)
        assert groups, costs[:4]
        for gap, group in groups:
            one = max(group) if group else 0.0
            assert gap <= budget + one
        probed += 1
    for costs in small_sequences:
        groups = simulate_gaps(costs, budget)
        assert groups
        assert max(gap for gap, _ in groups) < m.PUMP_GAP_LIMIT_S
        for gap, group in groups:
            one = max(group) if group else 0.0
            assert gap <= budget + one
        probed += 1
    chunk = [0.06] * 25
    assert sum(chunk) == pytest.approx(1.5)
    timed = simulate_gaps(chunk, budget)
    assert max(gap for gap, _ in timed) < m.PUMP_GAP_LIMIT_S
    assert max(gap for gap, _ in timed) < sum(chunk)
    # Halves that sum to the budget still close as separate atomic objects.
    # One object whose cost equals the budget is kept whole: the gap is that
    # object, which is the budget plus nothing further, not a sliced remainder.
    half = budget / 2.0
    exact = simulate_gaps([half, half], budget)
    assert max(gap for gap, _ in exact) < budget
    assert sum(gap for gap, _ in exact) == pytest.approx(budget)
    on_budget = simulate_gaps([budget], budget)
    assert on_budget == [(budget, [budget])]
    assert on_budget[0][0] <= budget + budget
    probed += 2
    bad_budgets = (0, 0.0, m.PUMP_GAP_LIMIT_S, 1e9, float('nan'), float('inf'), float('-inf'),
                   True, False, '0.05', None, [], (), {'budget': budget})
    budget_errors = 0
    for bad in bad_budgets:
        with pytest.raises(ValueError):
            m.object_pump(0.0, 0.0, 0.01, bad)
        with pytest.raises(ValueError):
            m.check_pump_budget(bad)
        budget_errors += 1
    assert budget_errors == len(bad_budgets)
    # Exactly the limit, then the next ulps above it, and 0 then the next ulps below.
    edge = m.PUMP_GAP_LIMIT_S
    below = 0.0
    for _ in range(24):
        with pytest.raises(ValueError):
            m.object_pump(0.0, 0.0, 0.01, edge)
        with pytest.raises(ValueError):
            m.check_pump_budget(edge)
        edge = math.nextafter(edge, math.inf)
        with pytest.raises(ValueError):
            m.object_pump(0.0, 0.0, 0.01, below)
        below = math.nextafter(below, -math.inf)
        budget_errors += 1
    just_under = math.nextafter(m.PUMP_GAP_LIMIT_S, 0.0)
    assert m.check_pump_budget(just_under) == just_under
    assert m.object_pump(0.0, 0.0, 0.0, just_under) == (False, 0.0, 0.0)
    bad_costs = (float('nan'), float('inf'), float('-inf'), -0.01,
                 math.nextafter(0.0, -math.inf), True, False, None, '0', [], (), (0.01,),
                 {'cost': 0.01})
    cost_errors = 0
    for bad in bad_costs:
        for args in ((bad, 0.0, 0.01), (0.0, bad, 0.01), (0.0, 0.0, bad)):
            with pytest.raises(ValueError):
                m.object_pump(*args, budget)
            cost_errors += 1
        with pytest.raises(ValueError):
            m.check_pump_cost(bad)
        cost_errors += 1
    unsupported_lists = ('', b'', None, 0.05, {'costs': [0.01]}, (), [])
    for bad in unsupported_lists:
        with pytest.raises(ValueError):
            simulate_gaps(bad, budget)
        cost_errors += 1
    with pytest.raises(ValueError):
        simulate_gaps([0.01, float('nan')], budget)
    with pytest.raises(ValueError):
        simulate_gaps([0.01, True], budget)
    cost_errors += 2
    assert cost_errors == len(bad_costs) * 4 + len(unsupported_lists) + 2
    assert probed == len(sequences) + len(small_sequences) + 2


def test_cancel_set_inside_a_chunk_waits_for_the_next_boundary():
    """Cancel is read only between chunks. A flag set inside a chunk still merges that chunk.

    The following chunk is not started: status is fail and Cancelled carries the partial.
    """
    rnd = random.Random(898)
    probed = 0
    for _ in range(40):
        size = rnd.randint(1, 25)
        chunk_count = rnd.randint(2, 8)
        fire = rnd.randrange(chunk_count - 1)
        total = size * chunk_count
        nodes = list(range(1, total + 1))
        flag = {'on': False, 'seen': 0}
        calls = []

        def fn(chunk, flag=flag, calls=calls, fire=fire):
            calls.append(list(chunk))
            if flag['seen'] == fire:
                flag['on'] = True
            flag['seen'] += 1
            return fake_xview(chunk)

        with pytest.raises(m.Cancelled) as exc:
            m.run_batched('xview', fn, nodes, size, lambda d, t: None, lambda flag=flag: flag['on'])
        done = (fire + 1) * size
        assert len(calls) == fire + 1
        assert exc.value.done == done
        assert len(exc.value.partial['objects']) == done
        assert exc.value.partial['status'] == 'fail'
        assert exc.value.partial['cancelled'] == {'done': done, 'total': total}
        assert calls[-1] == nodes[fire * size:(fire + 1) * size]
        assert [o['handle'] for o in exc.value.partial['objects']] == nodes[:done]
        probed += 1
    assert probed == 40


@pytest.mark.parametrize('text', ['', 'not json', '[]', 'null', '{"area": 3}', '{"area": true}',
                                  '{"floating": "yes"}', '{"geometry": "@@@"}', '{"area": NaN}'])
def test_dock_state_bad_input_gives_default(text):
    s = m.parse_dock(text)
    assert s['area'] in m.DOCK_AREAS and isinstance(s['floating'], bool)
    if text in ('', 'not json', '[]', 'null', '{"area": 3}', '{"area": true}'):
        assert s == m.DEFAULT_DOCK


def test_dock_state_round_trip():
    s = {'floating': True, 'area': 1, 'geometry': 'AAEC', 'visible': False}
    assert json.loads(m.dump_dock(s)) == s


def _palettes():
    yield (46, 46, 46), (220, 220, 220)    # Max dark
    yield (240, 240, 240), (32, 32, 32)    # Max light
    rnd = random.Random(8)
    for _ in range(300):
        dark = rnd.random() < 0.5
        base = tuple(rnd.randint(0, 70) if dark else rnd.randint(190, 255) for _ in range(3))
        text = tuple(rnd.randint(190, 255) if dark else rnd.randint(0, 60) for _ in range(3))
        yield base, text


def test_accents_contrast_and_distinct_for_every_palette():
    import colorsys
    for base, text in _palettes():
        status = [m.accent(k, base, text) for k in ('error', 'ok')]
        secs = [m.section_accent(i, base, text) for i in range(8)]
        for c in status + secs:
            assert m.contrast(c, base) >= 3.0
        assert len(set(secs)) == 8 and status[0] != status[1]
        for c in secs:
            h = colorsys.rgb_to_hls(*(v / 255 for v in c))[0] * 360
            assert min(m.hue_gap(h, s) for s in m.STATUS_HUES_DEG) >= 25


def test_section_hues_keep_away_from_status_hues():
    for h in m.SECTION_HUES:
        assert min(m.hue_gap(h, s) for s in m.STATUS_HUES_DEG) >= 30


@pytest.mark.parametrize('bad', [(float('nan'), 0, 0), (float('inf'), 0, 0), (-1, 0, 0), (256, 0, 0), (True, 0, 0)])
def test_accent_rejects_bad_palette(bad):
    with pytest.raises(ValueError):
        m.accent('error', bad, (255, 255, 255))
    with pytest.raises(KeyError):
        m.accent('blue', (0, 0, 0), (255, 255, 255))
    with pytest.raises(KeyError):
        m.section_accent(8, (0, 0, 0), (255, 255, 255))


def test_theme_name():
    assert m.theme_name((68, 68, 68)) == 'Dark' and m.theme_name((211, 211, 211)) == 'Light'


# ---- generated MAXScript ----------------------------------------------------------------------------
def _crlf_free(path):
    return path.read_bytes().replace(b'\r\n', b'\n')


def test_committed_macros_and_menu_are_generated_and_utf8_bom():
    assert _crlf_free(PKG / 'agr_tools.mcr') == b'\xef\xbb\xbf' + m.macros_ms().encode('utf-8')
    assert _crlf_free(PKG / 'menu.ms') == b'\xef\xbb\xbf' + m.menu_ms().encode('utf-8')


def test_every_action_has_a_macro_with_icon_and_menu_entry():
    mcr, menu = m.macros_ms(), m.menu_ms()
    for a in m.ACTIONS:
        assert re.search(r'macroScript {} category:"AGR Tools" .* iconName:"AgrIcons/agr_{}"'.format(a.macro, a.icon),
                         mcr)
        assert "ui('{}')".format(a.tool) in mcr
        assert '"{}`AGR Tools"'.format(a.macro) in menu
        assert 'on b_{} pressed do'.format(a.id) in mcr  # classic rollout fallback (Max 2024)
    assert 'agr_tools_runtime.panel()' in mcr and 'AGRToolsClassic' in mcr
    assert '#cuiRegisterMenus' in menu and 'id:#agrTools' in menu and 'removeScripts id:#agrTools' in menu
    ids = re.findall(r'"([0-9a-f]{8}-[0-9a-f-]{27})"', menu)
    # menu, open, 8 sections (separator + submenu), 61 actions; 1.0 (#1024): separator + submenu, 11 stage
    # submenus, 33 stage actions; 1.1: +4 handoff stage actions and the «Claude-док» entry in the agent submenu
    assert len(set(ids)) == 1 + 1 + 8 * 2 + 61 + 2 + 11 + 33 + 4 + 1 and ids.count(m.MENU_ID) == 2  # create + presence


def test_every_10_stage_action_has_a_disabled_macro_icon_and_menu_entry():
    mcr, menu = m.macros_ms(), m.menu_ms()
    # release 1.0.0 (#1024 R): all 33 rows ship (Q #1085 merged before R); the wip branch below stays tested
    assert len(m.ACTIONS_100) == 33 + 4 and {a.tool for a in m.ACTIONS_100 if a.wip} == set(m.WIP_100) == set()
    wip_body = '\n'.join(m.macro_100(m.ACTIONS_100[0]._replace(wip=True, tip=m.WIP_TIP)))
    assert '\n    on isEnabled return false\n' in wip_body and 'python.Execute' not in wip_body
    blocks = mcr.split('\nmacroScript ')
    for a in m.ACTIONS_100:
        body = [b for b in blocks if b.startswith(a.macro + ' ')]
        assert len(body) == 1, a.macro
        body = body[0]
        head = 'в работе, #1024' if a.wip else m.stage_tip(a.tool)
        assert re.match(r'{} category:"AGR Tools" .* tooltip:"{} .* iconName:"AgrIcons/agr_{}"'.format(
            a.macro, re.escape(head), a.icon), body), a.macro
        assert a.icon in icons.names() and icons.svg(a.icon, '#000000').startswith('<svg'), a.icon
        assert 'b_{} '.format(a.id) not in mcr  # not in the classic rollout (0.x actions only)
        assert '"{}`AGR Tools"'.format(a.macro) in menu
        entry = 'form_ui' if a.tool in m.FORM_100 else 'edit_ui'  # 1.1: parameter-form buttons open the form first
        released = '(on execute do python.Execute "agr_tools_runtime.{}(\'{}\')")'.format(entry, a.tool)
        if a.wip:  # greyed (isEnabled false) and execute only says so; it never reaches python / an edit
            assert '\n    on isEnabled return false\n' in body and 'messageBox' in body and 'python.Execute' not in body
            assert '{} ({}): в работе, #1024'.format(a.label, a.tool) in body
        else:  # released: one press = runtime.edit_ui (preview, then apply on the same selection)
            assert released in body and 'isEnabled' not in body and 'messageBox' not in body
        assert m.macro_100(a._replace(wip=False))[1] == released
    sub = menu[menu.index(m.MENU_100):]
    order = [re.search(r'"(AGRTools\w+)`AGR Tools"', ln).group(1) for ln in sub.splitlines() if 'CreateAction' in ln]
    # station order 1.0.1..1.0.33, then 1.1.1..1.1.4, stage by stage; the «Claude-док» entry (no plan row) closes the
    # agent submenu, which is the last stage
    assert order == [a.macro for a in m.ACTIONS_100] + [m.DOCK_MACRO]
    assert m.DOCK_ICON in icons.names() and 'macroScript {} category:"AGR Tools"'.format(m.DOCK_MACRO) in mcr
    for i, (sid, label, _icon, rows) in enumerate(m.STAGES_100):
        assert '    local t{} = c100.CreateSubMenu'.format(i) in sub and '"{}"'.format(m.stage_title(sid, label)) in sub
        for rid in rows:
            assert '    t{}.CreateAction'.format(i) in sub and m.BY_TOOL[rid].macro in sub


MS_FILES = ('agr_tools.mcr', 'menu.ms', 'startup.ms', 'install.ms')


def _strip_strings(text):
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', re.sub(r'--[^\n]*', '', text))


def test_maxscript_pitfalls_no_tooltip_reads_and_no_undeclared_assignments():
    allowed = set(m.DOCUMENTED_GLOBALS) | {'AGRToolsInstallRoot', 'AGRToolsStartupRoot'}
    for name in MS_FILES:
        text = _strip_strings((PKG / name).read_text(encoding='utf-8-sig'))
        assert not re.search(r'\.tooltip\b(?!\s*=)', text, re.I), name
        declared = set(re.findall(r'\b(?:local|global)\s+(\w+)', text, re.I))
        for g in re.findall(r'\bglobal\s+([\w ,]+)', text, re.I):
            declared |= {x.strip() for x in g.split(',')}
        declared |= set(re.findall(r'\bfor\s+(\w+)\s+in\b', text, re.I))
        assigned = set(re.findall(r'(?<![\w.])([A-Za-z_]\w*)\s*=(?!=)', text))
        assigned -= {'id', 'all', 'to', 'width', 'category', 'tooltip', 'buttonText', 'iconName'}
        lower = {d.lower() for d in declared}
        undeclared = {a for a in assigned if a.lower() not in lower}
        assert not undeclared, (name, undeclared)
        globals_ = set()
        for g in re.findall(r'\bglobal\s+([\w ,]+)', text, re.I):
            globals_ |= {x.strip() for x in g.split(',')}
        assert globals_ <= allowed, (name, globals_ - allowed)
        assert not re.search(r'\bfn\s+\w+', text) or name == 'menu.ms', name


# ---- bundle -------------------------------------------------------------------------------------------
def test_icon_entries_svg_from_generator_and_png_from_dir(synthetic_icon_pngs):
    got = builder.icon_entries()
    assert set(got) == set(builder.icon_files()) and len(got) == 2 * len(icons.names()) * 5 == 2 * 105 * 5
    for rel, data in got.items():
        theme, _, fname = rel.split('/')
        if rel.endswith('.svg'):
            assert data.decode('utf-8') == icons.svg(fname[4:-4], icons.THEMES[theme])
        else:
            assert data == (Path(synthetic_icon_pngs) / rel).read_bytes()


def test_package_contents_is_valid_and_complete():
    root = ET.fromstring(builder.package_contents())
    assert root.tag == 'ApplicationPackage' and root.get('AppVersion') == '1.1.0'
    assert root.get('UpgradeCode') == '{BA2C2E6E-54F9-402E-8875-3D616C9030FD}'
    assert root.get('ProductCode') == m.product_code('1.1.0') != m.product_code('1.0.0')
    descs = {c.get('Description'): c.find('ComponentEntry').get('ModuleName') for c in root.iter('Components')}
    assert descs == {'macroscripts parts': './Contents/agr_tools/agr_tools.mcr',
                     'post-start-up scripts parts': './Contents/agr_tools/startup.ms',
                     'dark icon paths parts': './Contents/agr_tools/icons/Dark',
                     'light icon paths parts': './Contents/agr_tools/icons/Light'}


def test_bundle_reproducible_and_install_uninstall_leaves_nothing(tmp_path):
    a, b = tmp_path / 'a.zip', tmp_path / 'b.zip'
    assert builder.build_bundle(a) == builder.build_bundle(b)
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(a) as z:
        names = set(z.namelist())
    assert 'AGR-Tools.bundle/PackageContents.xml' in names
    for rel in ('agr_tools.mcr', 'startup.ms', 'menu.ms', 'ui_panel.py', 'runtime.py', 'hygiene_core.py',
                'icons/Dark/AgrIcons/agr_xview_24.png', 'icons/Light/AgrIcons/agr_geojson_48.png'):
        assert 'AGR-Tools.bundle/Contents/agr_tools/' + rel in names
    assert not any(n.endswith(('mzp.run', 'install.ms')) for n in names)
    for p in (ModuleNames := [c.find('ComponentEntry').get('ModuleName')
                              for c in ET.fromstring(builder.package_contents()).iter('Components')]):
        assert any(n.startswith('AGR-Tools.bundle/' + p[2:]) for n in names), p
    plugins = tmp_path / 'ApplicationPlugins'
    plugins.mkdir()
    (plugins / 'Other.bundle').mkdir()
    (plugins / 'Other.bundle' / 'keep.txt').write_text('x')
    ini = tmp_path / '3dsMax.ini'
    ini.write_text('[Directories]\nX=1\n[AGRTools]\ndock={"area": 1}\n[Other]\nY=2\n', encoding='utf-8')
    before = sorted(p.relative_to(plugins).as_posix() for p in plugins.rglob('*'))
    builder.install_bundle(a, plugins)
    with pytest.raises(FileExistsError):
        builder.install_bundle(a, plugins)
    assert builder.uninstall_bundle(plugins, [ini]) == [str(ini)]
    assert sorted(p.relative_to(plugins).as_posix() for p in plugins.rglob('*')) == before
    assert ini.read_text(encoding='utf-8') == '[Directories]\nX=1\n[Other]\nY=2\n'
    with pytest.raises(FileNotFoundError):
        builder.uninstall_bundle(plugins, [ini])


def test_install_refuses_foreign_or_unsafe_archives(tmp_path):
    for member in ('evil.txt', 'AGR-Tools.bundle/../evil.txt', 'Other.bundle/x'):
        z = tmp_path / ('bad%d.zip' % abs(hash(member)))
        with zipfile.ZipFile(z, 'w') as f:
            f.writestr(member, 'x')
        with pytest.raises(ValueError):
            builder.install_bundle(z, tmp_path / 'plugins')
        assert not (tmp_path / 'evil.txt').exists()


def test_bundle_output_never_overwrites_an_input(tmp_path):
    for target in (PKG / 'runtime.py', PKG / 'menu.ms'):
        before = target.read_bytes()
        with pytest.raises(FileExistsError):
            builder.build_bundle(target)
        assert target.read_bytes() == before


def test_builder_rejects_missing_extra_or_fake_png_icons(tmp_path, synthetic_icon_pngs):
    import shutil
    src = tmp_path / 'png'
    shutil.copytree(synthetic_icon_pngs, src)
    (src / 'Light/AgrIcons/agr_pivot_30.png').unlink()
    with pytest.raises(ValueError, match='missing Light/AgrIcons/agr_pivot_30.png'):
        builder.icon_entries(src)
    (src / 'Light/AgrIcons/agr_pivot_30.png').write_bytes(b'not a png')
    with pytest.raises(ValueError, match='not a PNG'):
        builder.icon_entries(src)
    shutil.copy(src / 'Dark/AgrIcons/agr_xview_24.png', src / 'Dark/AgrIcons/agr_xview_99.png')
    (src / 'Light/AgrIcons/agr_pivot_30.png').write_bytes((src / 'Dark/AgrIcons/agr_xview_24.png').read_bytes())
    with pytest.raises(ValueError, match='extra'):
        builder.icon_entries(src)


def test_install_ms_thresholds_match_the_archive(tmp_path):
    """Native run found `files.count < 21` against 20 shipped files: tie the guard to the archive."""
    out = tmp_path / 'a.mzp'
    builder.build(out)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    top = [n for n in names if n.startswith('agr_tools/') and n.count('/') == 1]
    install = (PKG / 'install.ms').read_text(encoding='utf-8')
    assert 'if files.count < {} do'.format(len(top)) in install
    required = re.search(r'local required = #\(([^)]*)\)', install).group(1)
    assert sorted(re.findall(r'"([^"]+)"', required)) == sorted(n.split('/')[1] for n in top)
    for theme in ('Dark', 'Light'):
        pngs = [n for n in names if n.startswith('agr_tools/icons/{}/AgrIcons/'.format(theme)) and n.endswith('.png')]
        assert 'if icons.count < {} do'.format(len(pngs)) in install
