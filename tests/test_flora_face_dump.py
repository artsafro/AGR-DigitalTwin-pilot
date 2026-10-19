"""Input protection of the headless-Max Flora face dump (#305, review round 1 P1-2). Scratch files only."""
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = b"private synthetic library sentinel"


def _module():
    spec = importlib.util.spec_from_file_location("flora_face_dump", ROOT / "tools/flora/dump_flora_library_faces.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _job(module, source, out):
    return {"library": str(source), "library_sha256": module.file_sha256(source), "objects": ["A"], "out": str(out)}


@pytest.fixture
def fake_max(monkeypatch):
    calls = []
    runtime = types.SimpleNamespace(
        Name=lambda value: value,
        resetMaxFile=lambda *args: calls.append("reset"),
        loadMaxFile=lambda *args, **kwargs: calls.append("load") or True,
        objects=[types.SimpleNamespace(name="A")],
    )
    monkeypatch.setitem(sys.modules, "pymxs", types.SimpleNamespace(runtime=runtime))
    return calls


def _alias(kind, source, tmp_path):
    out = tmp_path / "out.json"
    if kind == "hardlink":
        os.link(source, out)
    elif kind == "dotted":
        out = tmp_path / "sub" / ".." / source.name
        (tmp_path / "sub").mkdir()
    elif kind == "case":
        out = Path(str(source).upper()) if os.name == "nt" else source
    return out


@pytest.mark.parametrize("kind", ["hardlink", "dotted", "case"])
def test_write_faces_rejects_output_alias_of_library_and_keeps_bytes(tmp_path, fake_max, kind):
    module = _module()
    source = tmp_path / "private-copy.max"
    source.write_bytes(SENTINEL)
    out = _alias(kind, source, tmp_path)
    module._triangles = lambda rt, node: [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]]
    with pytest.raises(RuntimeError, match="resolves to"):
        module.write_faces(_job(module, source, out))
    assert source.read_bytes() == SENTINEL
    assert fake_max == []  # rejected before Max loads anything


def test_write_faces_rejects_output_alias_of_job_file(tmp_path, fake_max, monkeypatch):
    module = _module()
    source = tmp_path / "private-copy.max"
    source.write_bytes(SENTINEL)
    job_path = tmp_path / "job.json"
    out = tmp_path / "out.json"
    job = _job(module, source, out)
    job_path.write_text(json.dumps(job), encoding="utf-8")
    os.link(job_path, out)
    before = job_path.read_bytes()
    monkeypatch.setenv("FLORA_FACES_JOB", str(job_path))
    with pytest.raises(RuntimeError, match="resolves to"):
        module.main()
    assert job_path.read_bytes() == before
    assert source.read_bytes() == SENTINEL
    assert fake_max == []


def test_write_faces_distinct_output_control(tmp_path, fake_max):
    module = _module()
    source = tmp_path / "private-copy.max"
    source.write_bytes(SENTINEL)
    out = tmp_path / "dump" / "faces.json"
    module._triangles = lambda rt, node: [[[0, 0, 0], [1, 0, 0], [0, 1, 0]]]
    document = module.write_faces(_job(module, source, out))
    assert source.read_bytes() == SENTINEL
    assert json.loads(out.read_text(encoding="utf-8"))["entries"] == document["entries"]
    assert list(document["entries"]) == ["A"] and document["failures"] == []
    assert fake_max == ["reset", "load"]
