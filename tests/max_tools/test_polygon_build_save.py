"""Polygon stand: build_scene.save leaves the written 2024 file as the current scene in every Max version (PR #1042).

Max 2026 treats `saveMaxFile ... saveAsVersion:2024` as "save a copy": the open scene stays untitled and
tex.finish_map / tex.placeholders refuse. save() must then reopen the written file; in Max 2024 it must not.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'test-polygon' / 'build' / 'build_scene.py'


def _load():
    spec = importlib.util.spec_from_file_location('polygon_build_scene_under_test', BUILD)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeRt:
    def __init__(self, makes_current):
        self.makes_current = makes_current
        self.maxFilePath = ''
        self.maxFileName = ''
        self.calls = []

    def execute(self, code):
        self.calls.append(code)
        path = code.split('"')[1]
        if code.startswith('loadMaxFile') or (code.startswith('saveMaxFile') and self.makes_current):
            folder, _, name = path.rpartition('/')
            self.maxFilePath, self.maxFileName = folder + '/', name


def test_save_2024_keeps_current_without_reload(tmp_path, monkeypatch):
    mod = _load()
    rt = FakeRt(makes_current=True)
    monkeypatch.setattr(mod, '_rt', lambda: rt)
    mod.save(tmp_path / 'polygon_all.max')
    assert len(rt.calls) == 1 and rt.calls[0].startswith('saveMaxFile') and 'saveAsVersion:2024' in rt.calls[0]


def test_save_2026_reopens_written_file(tmp_path, monkeypatch):
    mod = _load()
    rt = FakeRt(makes_current=False)
    monkeypatch.setattr(mod, '_rt', lambda: rt)
    target = tmp_path / 'polygon_all.max'
    mod.save(target)
    assert [c.split(' ')[0] for c in rt.calls] == ['saveMaxFile', 'loadMaxFile']
    assert rt.maxFileName == 'polygon_all.max'
    assert Path(rt.maxFilePath + rt.maxFileName).resolve() == target.resolve()
