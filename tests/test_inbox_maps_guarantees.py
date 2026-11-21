"""Synthetic counterexample probes for #1188; no production assets are written."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def intake(tmp_path):
    loader = importlib.util.spec_from_file_location("probe_inbox_maps", ROOT / "tools/materials/inbox_maps.py")
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    assets = tmp_path / "synthetic assets"
    inbox = assets / "_inbox/synthetic"
    inbox.mkdir(parents=True)
    source = inbox / "1.png"
    Image.new("RGB", (256, 256), (57, 93, 141)).save(source)
    original = source.read_bytes()
    (inbox / "manifest.json").write_text(json.dumps({"items": [{
        "msg_id": 1, "file": source.name, "sha256": hashlib.sha256(original).hexdigest()
    }]}), encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"inbox": "_inbox/synthetic", "sources": [{
        "src": 1, "key": "synthetic", "verdict": "synthetic probe",
        "outputs": [{"path": "materials/placeholders/v001/synthetic_r.png", "op": "flat",
                     "size": 128, "map": "r", "profile": "npm"}]
    }]}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    args = ["--spec", str(spec), "--root", str(assets), "--out", str(manifest)]
    return module, args, source, original, assets / "materials/placeholders/v001/synthetic_r.png", manifest


def test_root_hash_and_identical_rerun_preserve_source_and_output(intake):
    module, args, source, original, output, manifest = intake
    assert module.main(args) == 0
    data, modified = output.read_bytes(), output.stat().st_mtime_ns
    assert module.main(args) == 0
    row = json.loads(manifest.read_text(encoding="utf-8"))["maps"][0]
    root = Path(json.loads(manifest.read_text(encoding="utf-8"))["root"])
    assert (root / row["path"]).read_bytes() == data
    assert row["sha256"] == hashlib.sha256(data).hexdigest()
    assert row["bytes"] == len(data)
    assert output.stat().st_mtime_ns == modified
    assert source.read_bytes() == original


@pytest.mark.parametrize("corrupt", [b"different", b"", b"\x89PNG\r\n\x1a\n"])
def test_conflicting_output_is_preserved_without_manifest(intake, corrupt):
    module, args, source, original, output, manifest = intake
    output.parent.mkdir(parents=True)
    output.write_bytes(corrupt)
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        module.main(args)
    assert output.read_bytes() == corrupt
    assert source.read_bytes() == original
    assert not manifest.exists()


def test_changed_source_is_rejected_before_any_output(intake):
    module, args, source, original, output, manifest = intake
    source.write_bytes(original + b"synthetic corruption")
    with pytest.raises(SystemExit, match="inbox sha256 differs"):
        module.main(args)
    assert source.read_bytes() == original + b"synthetic corruption"
    assert not output.exists()
    assert not manifest.exists()
