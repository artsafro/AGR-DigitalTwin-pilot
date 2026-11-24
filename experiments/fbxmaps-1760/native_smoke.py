"""new-case: #1760 installed-MZP native smoke, synthetic inputs, headless Max only.
Run with dcc_batch.py max --file <this file>; config.json sits beside this script.
Never installs into APPDATA. Writes only to the configured disposable output.
"""
import base64
import gzip
import hashlib
import importlib.util
import json
import shutil
import struct
import sys
import time
import traceback
import zipfile
from pathlib import Path

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / 'tmp/native-1760/config.json').read_text())
OUT = Path(CFG['output'])
OUT.mkdir(parents=True, exist_ok=False)
report = {'synthetic': True, 'max': str(rt.maxVersion()), 'runs': []}


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


try:
    source = Path(CFG['bundle'])
    original = hashes(source)
    bundle = OUT / 'AGR-Tools.bundle'
    shutil.copytree(source, bundle)
    target = bundle / 'Contents/agr_tools'
    shutil.rmtree(target)
    stage = OUT / 'mzp'
    with zipfile.ZipFile(CFG['mzp']) as z:
        z.extractall(stage)
    startup = OUT / 'startup'
    startup.mkdir()
    rt.AGRToolsInstallRoot = target.as_posix() + '/'
    rt.AGRToolsStartupRoot = startup.as_posix() + '/'
    started = time.perf_counter()
    rt.fileIn(str(stage / 'install.ms'))
    report['install_seconds'] = time.perf_counter() - started
    assert bool(rt.AGRToolsRegistered)
    report['installed_root'] = str(rt.AGRToolsRoot)
    assert Path(str(rt.AGRToolsRoot)).resolve() == target.resolve()
    report['installed_sources_match'] = {}
    for name in ('fbxmaps_core.py', 'fbxmaps_max.py', 'ui_panel.py', 'ui_max.py'):
        match = (target / name).read_text() == (ROOT / 'adapters/max/agr_tools' / name).read_text()
        report['installed_sources_match'][name] = match
        assert match
    # Load the actual installed runtime, never the repo-side adapters.
    spec = importlib.util.spec_from_file_location('smoke_runtime1760', target / 'runtime.py')
    agr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agr)
    fc = agr._load_core('fbxmaps_core.py', 'agr_tools_fbxmaps_core')
    fm = agr._load_core('fbxmaps_max.py', 'agr_tools_fbxmaps_max')
    for name, alias in [('ui_qt.py', 'agr_tools_ui_qt'), ('ui_model.py', 'agr_tools_ui_model'),
                        ('roadmap.py', 'agr_tools_roadmap'), ('params_core.py', 'agr_tools_params_core')]:
        agr._load_core(name, alias)
    ui = agr._load_core('ui_panel.py', 'agr_tools_ui_panel')
    mx = agr._load_core('ui_max.py', 'agr_tools_ui_max')
    backend = mx.MaxBackend(agr, str(target / 'icons'))
    rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1.0
    report['units'] = {'type': str(rt.units.SystemType), 'scale': float(rt.units.SystemScale)}
    fixtures = ROOT / 'tests/fixtures/fbx_metallic_1729'
    # Real native-export synthetic fixtures: Standard reflection, Physical metalness.
    for case in ('stdreflection', 'physmetalness'):
        for repeat in range(3):
            folder = OUT / (case + '-' + str(repeat))
            folder.mkdir()
            fbx = folder / ('0001_Probe1729_' + case + '_Ground.fbx')
            encoded = (fixtures / (fbx.name + '.gz.b64')).read_text()
            raw = gzip.decompress(base64.b64decode(encoded))
            if case == 'stdreflection':
                # Synthetic incident variant: change the native fixture's FBX channel
                # ReflectionColor -> ReflectionFactor, preserving geometry/media.
                assert struct.unpack_from('<I', raw, 23)[0] == 7400
                needle = b'S' + struct.pack('<I', 15) + b'ReflectionColor'
                assert raw.count(needle) == 2  # property definition + final OP connection
                at = raw.rindex(needle)
                patched = bytearray(raw)

                def adjust(pos, limit):
                    while pos + 13 <= limit:
                        end, count, size = struct.unpack_from('<III', raw, pos)
                        if end == 0:
                            break
                        name_size = raw[pos + 12]
                        props = pos + 13 + name_size
                        if end > at:
                            struct.pack_into('<I', patched, pos, end + 1)
                        if props <= at < props + size:
                            struct.pack_into('<I', patched, pos + 8, size + 1)
                        adjust(props + size, end)
                        pos = end

                adjust(27, len(raw))
                raw = bytes(patched[:at]) + b'S' + struct.pack('<I', 16) + b'ReflectionFactor' + bytes(patched[at + len(needle):])
            fbx.write_bytes(raw)
            digest = hashlib.sha256(fbx.read_bytes()).hexdigest()
            rt.resetMaxFile(rt.Name('noPrompt'))
            rt.pluginManager.loadClass(rt.FbxImporter)
            rt.FBXImporterSetParam('Mode', rt.Name('create'))
            started = time.perf_counter()
            assert rt.importFile(str(fbx), rt.Name('noPrompt'), using=rt.FBXIMP)
            import_seconds = time.perf_counter() - started
            rt.select(list(rt.objects))
            before_maps = fm.connected_maps(rt)
            # Imported meshes may be Editable_Mesh: snapshotAsMesh works for both classes.
            def geometry():
                rows = []
                for n in rt.objects:
                    mesh = rt.snapshotAsMesh(n)
                    rows.append({'name': str(n.name), 'verts': [list(rt.getVert(mesh, i))
                                 for i in range(1, int(mesh.numverts) + 1)],
                                 'faces': int(mesh.numfaces), 'transform': str(n.transform)})
                return rows
            before_geometry = geometry()
            prompts = []

            def decline(before, plan):
                prompts.append({'before': before, 'plan': plan})
                return False

            started = time.perf_counter()
            declined = backend.check_fbx_maps(str(fbx), decline)
            decline_seconds = time.perf_counter() - started
            assert fm.connected_maps(rt) == before_maps
            assert declined['after'] is None
            # Keep the initial import for both decline and approval on the same state.
            panel = ui.AgrPanel(backend)
            old_dialog = ui.QtWidgets.QFileDialog.getOpenFileName
            ui.QtWidgets.QFileDialog.getOpenFileName = lambda *a, **k: (str(fbx), '')
            panel._confirm_fbx_maps = lambda before, plan: False
            panel.fbx_maps_button.click()
            assert panel.report is not None
            panel_before = panel.report
            if case == 'stdreflection':
                assert panel_before['status'] == 'fail', panel_before
                assert len(panel_before['objects']) == 1
                panel.resize(1200, 900)
                panel.grab().save(str(folder / 'panel-before.png'))
            panel._confirm_fbx_maps = lambda before, plan: True
            captured = []
            original_check = backend.check_fbx_maps

            def recorded_check(path, confirm):
                result = original_check(path, confirm)
                captured.append(result)
                return result

            backend.check_fbx_maps = recorded_check
            started = time.perf_counter()
            panel.fbx_maps_button.click()
            reconnect_seconds = time.perf_counter() - started
            backend.check_fbx_maps = original_check
            approved = captured[0]
            after = approved['after'] or approved['before']
            assert after['status'] == 'pass' and not approved['failures'], approved
            assert after['connected'] == after['embedded'] == 3
            assert panel.report['status'] == 'pass', panel.report
            if case == 'stdreflection':
                panel.grab().save(str(folder / 'panel-after.png'))
            ui.QtWidgets.QFileDialog.getOpenFileName = old_dialog
            panel.close()
            panel.deleteLater()
            assert geometry() == before_geometry
            assert hashlib.sha256(fbx.read_bytes()).hexdigest() == digest
            report['runs'].append({'geometry_unchanged': True, 'geometry': before_geometry, 'case': case, 'repeat': repeat, 'import_seconds': import_seconds,
                                   'decline_seconds': decline_seconds, 'reconnect_seconds': reconnect_seconds,
                                   'declined': declined, 'approved': approved, 'panel_before': panel_before,
                                   'panel_after': panel.report, 'prompts': prompts})
    report['original_bundle_unchanged'] = hashes(source) == original
    assert report['original_bundle_unchanged']
    report['status'] = 'pass'
except Exception:
    report['status'] = 'error'
    report['error'] = traceback.format_exc()
finally:
    (OUT / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('AGR_NATIVE_1760 ' + json.dumps({'status': report['status'], 'runs': len(report['runs']),
                                         'error': report.get('error'), 'output': str(OUT)}))
