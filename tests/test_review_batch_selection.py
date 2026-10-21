"""Review adapter selection keeps the user's safe-mode live document untouched."""
import sys
from pathlib import Path


def test_default_adapter_uses_authorized_headless_even_with_live_max(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'review'))
    import max_adapter
    calls = []

    def live_probe(args):
        calls.append(args)
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout='{"status":"success","result":{"success":true}}')

    monkeypatch.setattr(max_adapter, '_call', live_probe)
    monkeypatch.setattr(max_adapter, 'max_batch_path', lambda: Path('C:/Program Files/Autodesk/3ds Max 2026/3dsmaxbatch.exe'))
    adapter = max_adapter.default_adapter()
    assert type(adapter) is max_adapter.BatchAdapter
    assert not calls, 'headless publication must not access the user live bridge'
