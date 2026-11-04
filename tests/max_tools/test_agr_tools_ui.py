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


def ui_branches():
    """Every tool string runtime.ui() accepts, read from its source."""
    src = (PKG / 'runtime.py').read_text(encoding='utf-8')
    body = src[src.index('def ui(tool):'):src.index('_panel = None')]
    tools = set(re.findall(r"tool == '(\w+)'", body))
    tools |= set(re.findall(r"'(\w+)'", re.search(r"CHECKS_050 = \(([^)]*)\)", src).group(1)))
    tools |= {'xview', 'matid'}
    return tools


def test_every_existing_action_is_in_the_panel_once():
    assert ui_branches() == OLD_TOOLS
    assert {a.tool for a in m.ACTIONS} == OLD_TOOLS
    assert len({a.id for a in m.ACTIONS}) == len(m.ACTIONS) == 17
    assert len({a.macro for a in m.ACTIONS}) == 17
    assert sum(len(acts) for _, acts in m.sections()) == 17
    assert [t for t, _ in m.sections()] == ['Проверки', 'UV и атласы', 'Коллизии UCX', 'Экспорт', 'GeoJSON']
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
        secs = [m.section_accent(i, base, text) for i in range(5)]
        for c in status + secs:
            assert m.contrast(c, base) >= 3.0
        assert len(set(secs)) == 5 and status[0] != status[1]
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
        m.section_accent(5, (0, 0, 0), (255, 255, 255))


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
    assert len(set(ids)) == 1 + 1 + 5 * 2 + 17 and ids.count(m.MENU_ID) == 2  # create + presence check


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
    assert set(got) == set(builder.icon_files()) and len(got) == 2 * 23 * 5
    for rel, data in got.items():
        theme, _, fname = rel.split('/')
        if rel.endswith('.svg'):
            assert data.decode('utf-8') == icons.svg(fname[4:-4], icons.THEMES[theme])
        else:
            assert data == (Path(synthetic_icon_pngs) / rel).read_bytes()


def test_package_contents_is_valid_and_complete():
    root = ET.fromstring(builder.package_contents())
    assert root.tag == 'ApplicationPackage' and root.get('AppVersion') == '0.6.0'
    assert root.get('UpgradeCode') == '{BA2C2E6E-54F9-402E-8875-3D616C9030FD}'
    assert root.get('ProductCode') == m.product_code('0.6.0') != m.product_code('0.5.0')
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
