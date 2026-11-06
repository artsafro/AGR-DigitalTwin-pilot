"""Cold retrieval check of assets/manifest.json (issue #1017).

new-case: a cold agent resolves every manifest entry from the manifest alone (local store or the
Drive-for-desktop folder named in the manifest) and hashes it; anything else fails closed.
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COLD_PATH = ROOT / "tools" / "assets" / "cold_check.py"
SYNC_PATH = ROOT / "tools" / "assets" / "sync.py"
MANIFEST_PATH = ROOT / "assets" / "manifest.json"
SCHEMA_PATH = ROOT / "assets" / "manifest.schema.json"
SHARED = "https://drive.google.com/drive/folders/1zKszwxFRWH0DnrXYiFR7SN3bH9Iph2d6?usp=sharing"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = _load("asset_sync_1017", SYNC_PATH)

# id -> (version, sha256, size); grounded in PR #906 session-v001.zip members, the #753 and
# 559-pilot-v010 Drive SHA256SUMS.txt files and jobs/TEC26-OKS/census/sources.json.
NEW_ENTRIES = {
    "ground-vatutino-v015-npm": ("v015", "a2d1b20bb21ee3bf6fa6cc9c595d05d348c936e0611684a582a9476b46e175e0", 1293452),
    "ground-vatutino-v015-vpm": ("v015", "1ced46c362fd4c9cbfcd521d8e4392985980fafb5b2d78e6fe91b0f801ca4e28", 1336940),
    "ground-vatutino-v015-vpm-ucx": ("v015", "f6256077ebabc3be7ca943d03bb7091bc10a0381951ab672ee6309930d7733c2", 2785308),
    "ground-vatutino-v015-npm-textured": ("v015", "17e1ad24557599ec53be2ab77f2906d840f03fd706efcc3fb93c08458749a36b", 20860540),
    "ground-vatutino-v015-vpm-textured": ("v015", "39a45ab7004be8a1cf47a0c85b2d22f83d0e7b9a639c1c324344f5b914d3b188", 2802220),
    "ground-vatutino-v015-npm-max": ("v015", "5771b16fe4e31890baf081d9bcb0eeec5efb5917e62ba0720b23a088d836273b", 2469888),
    "ground-vatutino-v015-vpm-max": ("v015", "d8ab646f3b071bc49dc3e9e95e6f65b6371a62e48bad75401e32a407c6e2c70f", 2744320),
    "tec26-ac08-source-fbx": (None, "9cae468e714118c501dfffa77531aabecd88662c4e34d0be57274d446bb3e5fd", 39792),
    "tec26-ac08-npm": ("v010", "8f0cb8b7e922850eab15198d0bd40cf2ca1e2bfed12e9c4912173b4aef565ab3", 224960),
    "tec26-ac08-vpm": ("v010", "2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb", 654430),
    "tec26-album-pptx": (None, "74e50277df5e2dfde3ba7ab945eb6bab45a8fa8c0207d7aca3a136d9656b78ac", 87990058),
    "tec26-ac08-dwg": (None, "cb90ed375df4fd708b7a69c6d018600347953245f0f6bde396f394bee3e1fa52", 679359),
}


def _cold():
    return _load("asset_cold_check_1017", COLD_PATH)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _doc(entries, drive_folder="AGR-assets"):
    doc = {
        "schema": "asset-store/1",
        "local_root": "C:/x/assets",
        "login": "drive-desktop",
        "drive": "google-drive",
        "rejected_backends": ["dropbox"],
        "assets": entries,
    }
    if drive_folder is not None:
        doc["drive_folder"] = drive_folder
    return doc


def _entry(identifier="a-one", payload=b"bytes-one", path="x/one.bin", **extra):
    entry = {
        "id": identifier,
        "version": "v001",
        "local_path": path,
        "sha256": _sha(payload),
        "size": len(payload),
        "drive_link": SHARED,
        "drive_path": path,
        "licence": None,
        "source": "synthetic test fixture",
    }
    entry.update(extra)
    return entry


def _setup(tmp_path, entries, local=None, drive=None, drive_folder="AGR-assets"):
    """local/drive: {local_path: bytes} written under the local root / <mount>/<drive_folder>."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_doc(entries, drive_folder)), encoding="utf-8")
    root = tmp_path / "store"
    mount = tmp_path / "mount"
    root.mkdir()
    (mount / (drive_folder or "AGR-assets")).mkdir(parents=True)
    for base, files in ((root, local or {}), (mount / (drive_folder or "AGR-assets"), drive or {})):
        for rel, data in files.items():
            target = base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return manifest, root, mount


def _run(tmp_path, entries, **kw):
    manifest, root, mount = _setup(tmp_path, entries, **kw)
    return _cold().check(manifest, root=root, drive_mounts=[mount])


# --- shipped manifest -------------------------------------------------------------------------


def test_shipped_manifest_lists_v015_and_ac08_triple_with_grounded_hashes():
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in document["assets"]}
    for asset_id, (version, digest, size) in NEW_ENTRIES.items():
        entry = by_id[asset_id]
        assert (entry["version"], entry["sha256"], entry["size"]) == (version, digest, size), asset_id
        assert entry["drive_link"] == SHARED
        assert entry["drive_path"] == entry["local_path"]
        assert entry["source"].strip() and entry["recorded_path"].strip()
        assert entry["licence"] is None
    assert len(by_id) == len(document["assets"]) == 20
    assert document["drive_folder"] == "AGR-assets"
    assert sync.validate_document(document) == []


def test_schema_declares_optional_drive_folder():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["drive_folder"]["type"] == "string"
    assert "drive_folder" not in schema["required"]


@pytest.mark.parametrize("bad", ["", "  ", "../up", "C:/abs", "/abs", 7, None])
def test_validator_rejects_bad_drive_folder(bad):
    doc = _doc([_entry()], drive_folder=None)
    doc["drive_folder"] = bad
    assert "partial: drive_folder" in sync.validate_document(doc)


# --- cold check --------------------------------------------------------------------------------


def test_match_from_drive_only(tmp_path):
    code, report = _run(tmp_path, [_entry()], drive={"x/one.bin": b"bytes-one"})
    assert code == 0
    assert report["status"] == "match"
    row = report["assets"][0]
    assert row["status"] == "match" and [loc["where"] for loc in row["locations"]] == ["drive"]
    assert row["locations"][0]["sha256"] == _sha(b"bytes-one")


def test_match_from_local_only(tmp_path):
    code, report = _run(tmp_path, [_entry()], local={"x/one.bin": b"bytes-one"})
    assert code == 0 and report["assets"][0]["locations"][0]["where"] == "local"


def test_missing_everywhere_fails(tmp_path):
    code, report = _run(tmp_path, [_entry()])
    assert code == 1 and report["assets"][0]["status"] == "missing"


def test_one_bad_copy_fails_even_when_other_matches(tmp_path):
    code, report = _run(
        tmp_path, [_entry()], local={"x/one.bin": b"bytes-one"}, drive={"x/one.bin": b"bytes-ONE"}
    )
    assert code == 1 and report["assets"][0]["status"] == "mismatch"


def test_size_mismatch_with_forged_hash_fails(tmp_path):
    entry = _entry(size=999)
    code, report = _run(tmp_path, [entry], drive={"x/one.bin": b"bytes-one"})
    assert code == 1 and report["assets"][0]["status"] == "mismatch"


def test_every_entry_reported_and_one_failure_fails_batch(tmp_path):
    good = _entry("a-good", b"good", "g/good.bin")
    bad = _entry("a-bad", b"bad", "g/bad.bin")
    code, report = _run(tmp_path, [good, bad], drive={"g/good.bin": b"good"})
    assert code == 1
    assert {row["id"]: row["status"] for row in report["assets"]} == {"a-good": "match", "a-bad": "missing"}


def test_drive_path_differs_from_local_path(tmp_path):
    entry = _entry(drive_path="d/elsewhere.bin")
    code, _ = _run(tmp_path, [entry], drive={"d/elsewhere.bin": b"bytes-one"})
    assert code == 0
    other = tmp_path / "b"
    other.mkdir()
    code, report = _run(other, [entry], drive={"x/one.bin": b"bytes-one"})
    assert code == 1 and report["assets"][0]["status"] == "missing"


def test_no_drive_folder_means_local_only(tmp_path):
    manifest, root, mount = _setup(tmp_path, [_entry()], drive={"x/one.bin": b"bytes-one"}, drive_folder=None)
    code, report = _cold().check(manifest, root=root, drive_mounts=[mount])
    assert code == 1 and report["assets"][0]["status"] == "missing"


@pytest.mark.parametrize(
    "document",
    [
        {},
        [],
        _doc([]),
        _doc([_entry(sha256="0" * 63)]),
        _doc([_entry(), _entry()]),
        _doc([_entry(path="../escape.bin")]),
        _doc([_entry(size=0)]),
        _doc([_entry(size=float("nan"))]),
    ],
)
def test_invalid_manifest_fails_closed_before_hashing(tmp_path, document):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    code, report = _cold().check(manifest, root=tmp_path, drive_mounts=[tmp_path])
    assert code == 1 and report["status"] == "invalid" and report["errors"] and report["assets"] == []


def test_unreadable_manifest_fails(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{not json", encoding="utf-8")
    code, report = _cold().check(manifest, root=tmp_path, drive_mounts=[])
    assert code == 1 and report["status"] == "invalid"
    code, report = _cold().check(tmp_path / "absent.json", root=tmp_path, drive_mounts=[])
    assert code == 1 and report["status"] == "invalid"


def test_cli_fresh_process_writes_nothing(tmp_path):
    manifest, root, mount = _setup(tmp_path, [_entry()], drive={"x/one.bin": b"bytes-one"})
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    proc = subprocess.run(
        [sys.executable, str(COLD_PATH), "--manifest", str(manifest), "--root", str(root), "--drive-mount", str(mount)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "match"
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before
    proc = subprocess.run(
        [sys.executable, str(COLD_PATH), "--manifest", str(manifest), "--root", str(root), "--drive-mount", str(tmp_path / "nope")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 1 and json.loads(proc.stdout)["assets"][0]["status"] == "missing"
