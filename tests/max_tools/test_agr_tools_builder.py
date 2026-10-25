"""new-case: reproducible AGR Tools distribution public builder seam."""
import importlib.util
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def builder():
    path = ROOT / 'tools/max/build_agr_tools.py'
    assert path.is_file(), 'AGR Tools builder is missing'
    spec = importlib.util.spec_from_file_location('agr_builder', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reproducible_installable_archive(tmp_path):
    mod = builder()
    a, b = tmp_path / 'one.mzp', tmp_path / 'two.mzp'
    mod.build(a)
    mod.build(b)
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(a) as z:
        assert z.testzip() is None
        assert {'mzp.run', 'install.ms', 'agr_tools/agr_tools.mcr',
                'agr_tools/startup.ms', 'agr_tools/runtime.py',
                'agr_tools/hygiene_core.py'} <= set(z.namelist())
        assert b'run "install.ms"' in z.read('mzp.run')
        assert b'0.002' in z.read('agr_tools/runtime.py')
        assert b'0.005' in z.read('agr_tools/runtime.py')
