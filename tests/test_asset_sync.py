"""Asset store manifest and local/Drive sync (issue #350).

Public seam: tools/assets/sync.py — validate a manifest, dry-run by default,
optional rclone or Drive-for-desktop backend. Checksums and licences are never
invented; a bad entry fails closed.
"""

import hashlib
import importlib.util
import json
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = ROOT / "tools" / "assets" / "sync.py"
MANIFEST_PATH = ROOT / "assets" / "manifest.json"
SCHEMA_PATH = ROOT / "assets" / "manifest.schema.json"

_SPEC = importlib.util.spec_from_file_location("asset_sync", SYNC_PATH)
sync = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sync)

# Grounded in jobs/VATUTINO-SITE/ground-build-v014.md, library/maf/audit.json,
# library/maf/README.md and library/windows/sources/win-typical-max-v001.json.
GROUNDED_SHA256 = {
    "maf-union-max": "beeef9d418e81045bbc4933cc74077acd3d9f7a265319ceb9bf0ff0253050109",
    "maf-npm-blend": "52ef2222b13a7cb4f4c3b728ee27e827cfaeb49499f3e7d7d03a5f7364d661dd",
    "maf-spec-xlsx": "9b4302c16501636fe4a522f54ff16091244ba0b6f20378763b2706d51f1eb2b3",
    "ground-vatutino-npm": "94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef",
    "ground-vatutino-vpm": "a41266757fe39958cae7a40a765b628aa7cbfeb74de48d3c82efc297b9cf75f1",
    "ground-vatutino-vpm-ucx": "a5f7d3963ffbe3003f4dd7d706395a84f30a3548c5281f3402b1c1694cfa3b6c",
}
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(**overrides):
    payload = b"asset-bytes"
    entry = {
        "id": "sample-asset",
        "version": "v001",
        "local_path": "sample/asset.bin",
        "sha256": _sha(payload),
        "size": len(payload),
        "drive_link": "pending",
        "licence": "synthetic-test-licence",
        "source": "tests/test_asset_sync.py synthetic fixture",
    }
    entry.update(overrides)
    return entry, payload


def _document(entries):
    return {
        "schema": "asset-store/1",
        "local_root": "C:/x/assets",
        "login": "pending",
        "drive": "google-drive",
        "rejected_backends": ["dropbox"],
        "assets": entries,
    }


def _write_manifest(tmp_path: Path, entries, payloads):
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_document(entries)), encoding="utf-8")
    root = tmp_path / "assets"
    for entry, payload in zip(entries, payloads):
        if payload is None:
            continue
        path = root / entry["local_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return manifest, root


def _statuses(report):
    return [item["status"] for item in report["assets"]]


def test_schema_requires_acceptance_fields():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    item = schema["properties"]["assets"]["items"]
    required = set(item["required"])
    assert required >= {
        "id",
        "version",
        "local_path",
        "sha256",
        "size",
        "drive_link",
        "licence",
        "source",
    }
    assert schema["properties"]["local_root"]["const"] == "C:/x/assets"
    assert schema["properties"]["rejected_backends"]["items"]["const"] == "dropbox"


def test_shipped_manifest_covers_required_families_without_invented_links():
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in document["assets"]}
    assert document["local_root"] == sync.LOCAL_ROOT
    assert document["login"] == "pending"
    assert document["drive"] == "google-drive"
    assert "dropbox" in document["rejected_backends"]
    for asset_id, digest in GROUNDED_SHA256.items():
        assert by_id[asset_id]["sha256"] == digest
        assert by_id[asset_id]["drive_link"] == "pending"
        assert by_id[asset_id]["licence"] is None
    assert by_id["flora-library"]["version"] == "v003"
    assert by_id["flora-library"]["sha256"] == "9942ae2be37c900c3066d791193eb0470cc08933881d9f72db833d42578dfa74"
    assert by_id["flora-library"]["size"] == 2561364
    assert by_id["windows-win-typical"]["version"] == "v001"
    assert by_id["windows-win-typical"]["size"] == 2564096
    assert by_id["windows-win-typical"]["sha256"] == "59a44f670b392caffd4a09a7082376afe94322da3c2939de77eabda27987a777"
    assert by_id["ground-vatutino-npm"]["version"] == "v014"
    assert by_id["maf-union-max"]["version"] is None
    covered = " ".join(by_id)
    for token in ("maf", "flora", "windows", "ground"):
        assert token in covered


def test_shipped_manifest_accepts_documented_sources():
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert sync.validate_document(document) == []


def test_dry_run_is_default_and_writes_nothing(tmp_path):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    out = tmp_path / "report.json"
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    code, report = sync.execute(manifest, root=root, out=out)
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert code == 0
    assert report["dry_run"] is True
    assert report["assets"][0]["status"] == "match"
    assert report["assets"][0]["drive_link"] == "pending"
    assert after == before
    assert not out.exists()


def test_sha256_mismatch_exits_nonzero_and_writes_nothing(tmp_path):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload + b"x"])
    out = tmp_path / "report.json"
    code, report = sync.execute(manifest, root=root, apply=True, out=out)
    assert code != 0
    assert report["assets"][0]["status"] not in {"pass", "not_run", "match"}
    assert any("sha256_mismatch" in error for error in report["errors"])
    assert not out.exists()


def test_provenance_requires_at_least_one_nonblank_field():
    for licence in (None, "", "   ", "known-rights"):
        for source in (None, "", "   ", "verified-origin"):
            entry, _ = _entry(licence=licence, source=source)
            errors = sync.validate_document(_document([entry]))
            assert bool(errors) == (not str(licence or "").strip() and not str(source or "").strip())


def test_absent_credentials_keep_links_pending(tmp_path, monkeypatch):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    monkeypatch.setattr(sync, "which_rclone", lambda: None)
    monkeypatch.setattr(sync, "drive_desktop_root", lambda explicit=None: None)
    for backend in ("local", "rclone", "drive-desktop"):
        code, report = sync.execute(manifest, root=root, backend=backend)
        assert code == 0
        assert report["credentials"] == "absent"
        assert report["assets"][0]["drive_link"] == "pending"


def test_output_path_that_resolves_to_input_writes_nothing(tmp_path):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    original = manifest.read_bytes()
    alias = manifest.parent / "manifest.json"
    code, report = sync.execute(manifest, root=root, apply=True, out=alias)
    assert code != 0
    assert any("output_aliases_input" in error for error in report["errors"])
    assert manifest.read_bytes() == original
    asset = root / entry["local_path"]
    asset_bytes = asset.read_bytes()
    code, report = sync.execute(manifest, root=root, apply=True, out=asset)
    assert code != 0
    assert asset.read_bytes() == asset_bytes


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"schema": "asset-store/1", "local_root": "C:/x/assets", "assets": []},
        {"assets": [{"id": "only-id"}]},
    ],
)
def test_empty_or_partial_document_fails(document):
    errors = sync.validate_document(document)
    assert errors
    assert all("pass" not in error and "not_run" not in error for error in errors)


def test_unsupported_backend_and_dropbox_fail(tmp_path):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    for backend in ("dropbox", "s3", "unsupported"):
        code, report = sync.execute(manifest, root=root, backend=backend)
        assert code != 0
        assert any("unsupported_backend" in error for error in report["errors"])
        assert _statuses(report) != ["pass"]


def test_nan_inf_and_exact_zero_size_fail(tmp_path):
    for bad_size in (float("nan"), float("inf"), float("-inf"), 0):
        entry, payload = _entry(size=bad_size)
        errors = sync.validate_document(_document([entry]))
        assert errors
        if bad_size == 0:
            assert any("size_at_threshold" in error for error in errors)
        else:
            assert any("size_not_finite" in error for error in errors)
    entry, _payload = _entry(size=0, sha256=EMPTY_SHA256, local_path="empty.bin")
    manifest, root = _write_manifest(tmp_path, [entry], [b""])
    out = tmp_path / "should-not-exist.json"
    code, report = sync.execute(manifest, root=root, apply=True, out=out)
    assert code != 0
    assert report["assets"][0]["status"] not in {"pass", "not_run", "match"}
    assert not out.exists()


def test_one_byte_above_size_threshold_matches(tmp_path):
    entry, _payload = _entry(size=1, sha256=_sha(b"a"), local_path="one.bin")
    manifest, root = _write_manifest(tmp_path, [entry], [b"a"])
    code, report = sync.execute(manifest, root=root)
    assert code == 0
    assert report["assets"][0]["status"] == "match"


def test_random_mismatches_never_pass_or_write(tmp_path):
    rng = random.Random(350)
    for index in range(48):
        body = bytes(rng.getrandbits(8) for _ in range(rng.randint(1, 24)))
        lied = bytes(rng.getrandbits(8) for _ in range(len(body)))
        if lied == body:
            lied += b"\x01"
        entry, _payload = _entry(
            id=f"probe-{index}",
            local_path=f"probe/{index}.bin",
            sha256=_sha(body),
            size=len(body),
        )
        case = tmp_path / f"case-{index}"
        manifest, root = _write_manifest(case, [entry], [lied])
        out = case / "out.json"
        code, report = sync.execute(manifest, root=root, apply=True, out=out)
        assert code != 0
        assert report["assets"][0]["status"] not in {"pass", "not_run", "match"}
        assert not out.exists()


def test_random_dry_runs_write_nothing_and_never_prompt(tmp_path, monkeypatch):
    prompts = {"count": 0}
    monkeypatch.setattr(sync, "prompt_for_login", lambda: prompts.__setitem__("count", prompts["count"] + 1))
    rng = random.Random(351)
    for index in range(32):
        body = bytes(rng.getrandbits(8) for _ in range(rng.randint(1, 16)))
        entry, _payload = _entry(
            id=f"ok-{index}",
            local_path=f"ok/{index}.bin",
            sha256=_sha(body),
            size=len(body),
        )
        case = tmp_path / f"ok-{index}"
        manifest, root = _write_manifest(case, [entry], [body])
        before = list(case.rglob("*"))
        code, report = sync.execute(manifest, root=root, backend=rng.choice(["local", "rclone", "drive-desktop"]))
        assert code == 0
        assert report["dry_run"] is True
        assert report["assets"][0]["drive_link"] == "pending"
        assert list(case.rglob("*")) == before
    assert prompts["count"] == 0


def test_declared_hash_without_local_file_fails(tmp_path):
    entry, _payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [None])
    code, report = sync.execute(manifest, root=root)
    assert code != 0
    assert any("missing_file" in error for error in report["errors"])
    assert report["assets"][0]["status"] not in {"pass", "not_run", "match"}


@pytest.mark.parametrize("apply", [False, True])
def test_drive_desktop_copies_only_on_apply(tmp_path, apply):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    drive = tmp_path / "drive"
    drive.mkdir()
    code, report = sync.execute(manifest, root=root, backend="drive-desktop", drive_root=drive, apply=apply)
    target = drive / entry["local_path"]
    assert code == 0
    assert target.exists() == apply
    if apply:
        assert target.read_bytes() == payload
    assert report["assets"][0]["drive_link"] == "pending"


def test_rclone_copy_and_private_link(tmp_path, monkeypatch):
    import subprocess

    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    monkeypatch.setattr(sync, "which_rclone", lambda: "rclone")
    monkeypatch.setenv("AGR_RCLONE_REMOTE", "gdrive:AGR-assets")
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[1] == "lsjson":
            return subprocess.CompletedProcess(args, 0, json.dumps({"ID": "test", "Size": len(payload), "Hashes": {"md5": hashlib.md5(payload).hexdigest()}}), "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    code, report = sync.execute(manifest, root=root, backend="rclone")
    assert code == 0 and calls == []
    code, report = sync.execute(manifest, root=root, backend="rclone", apply=True)
    assert code == 0
    assert [call[1] for call in calls] == ["copyto", "lsjson"]
    assert calls[0][-1] == "gdrive:AGR-assets/sample/asset.bin"
    assert "--ignore-existing" in calls[0]
    assert "--stat" in calls[1] and "--hash" in calls[1]
    assert report["assets"][0]["drive_link"] == "https://drive.google.com/file/d/test/view"


def test_backend_failure_is_nonzero(tmp_path, monkeypatch):
    import subprocess

    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    monkeypatch.setattr(sync, "which_rclone", lambda: "rclone")
    monkeypatch.setenv("AGR_RCLONE_REMOTE", "gdrive:assets")
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", "offline"))
    code, report = sync.execute(manifest, root=root, backend="rclone", apply=True)
    assert code != 0
    assert report["errors"]


@pytest.mark.parametrize("target_kind", ["asset", "hardlink", "missing-asset", "drive-target"])
def test_aliases_reject_before_any_copy(tmp_path, target_kind):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    drive = tmp_path / "drive"
    drive.mkdir()
    asset = root / entry["local_path"]
    target = asset
    if target_kind == "hardlink":
        target = tmp_path / "alias.json"
        target.hardlink_to(asset)
    elif target_kind == "missing-asset":
        asset.unlink()
    elif target_kind == "drive-target":
        target = drive / entry["local_path"]
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    code, report = sync.execute(manifest, root=root, backend="drive-desktop", drive_root=drive, apply=True, out=target)
    assert code != 0
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_drive_root_aliases_local_store_rejected(tmp_path):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    code, report = sync.execute(manifest, root=root, backend="drive-desktop", drive_root=root, apply=True)
    assert code != 0
    assert (root / entry["local_path"]).read_bytes() == payload


@pytest.mark.parametrize("mutation", ["missing-login", "wrong-drive", "unknown-field", "bad-licence-type", "duplicate-path", "backslash-traversal"])
def test_malformed_inventory_is_rejected(tmp_path, mutation):
    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    document = json.loads(manifest.read_text())
    if mutation == "missing-login":
        del document["login"]
    elif mutation == "wrong-drive":
        document["drive"] = "dropbox"
    elif mutation == "unknown-field":
        document["typo"] = True
    elif mutation == "bad-licence-type":
        document["assets"][0]["licence"] = 123
    elif mutation == "duplicate-path":
        document["assets"].append(dict(entry, id="other-id"))
    else:
        document["assets"][0]["local_path"] = "..\\\\escape.bin"
    manifest.write_text(json.dumps(document))
    code, report = sync.execute(manifest, root=root)
    assert code != 0


@pytest.mark.parametrize("metadata", [{}, [], {"Hashes": None}, {"Size": 10, "Hashes": {}},
                                         {"Size": 10, "Hashes": {"md5": "0" * 32}},
                                         {"Size": float("nan"), "Hashes": {}},
                                         {"Size": float("inf"), "Hashes": {}},
                                         {"Size": 0, "Hashes": {}}, "truncated"])
def test_rclone_invalid_remote_evidence_fails(tmp_path, monkeypatch, metadata):
    import subprocess

    entry, payload = _entry()
    manifest, root = _write_manifest(tmp_path, [entry], [payload])
    monkeypatch.setattr(sync, "which_rclone", lambda: "rclone")
    monkeypatch.setenv("AGR_RCLONE_REMOTE", "gdrive:assets")
    def run(args, **kwargs):
        output = "{" if metadata == "truncated" else json.dumps(metadata)
        return subprocess.CompletedProcess(args, 0, output if args[1] == "lsjson" else "", "")
    monkeypatch.setattr(subprocess, "run", run)
    out = tmp_path / "report.json"
    code, report = sync.execute(manifest, root=root, backend="rclone", apply=True, out=out)
    assert code != 0
    assert report["assets"][0]["status"] == "error"
    assert not out.exists()


def test_desktop_generated_repeat_and_conflict_preserve_bytes(tmp_path):
    rng = random.Random(352)
    for index in range(12):
        entry, _ = _entry()
        body = rng.randbytes(32)
        entry.update(sha256=_sha(body), size=len(body))
        case = tmp_path / str(index)
        manifest, root = _write_manifest(case, [entry], [body])
        drive = case / "drive"
        drive.mkdir()
        for _ in range(2):
            code, report = sync.execute(manifest, root=root, backend="drive-desktop", drive_root=drive, apply=True)
            assert code == 0
            assert (drive / entry["local_path"]).read_bytes() == body
        changed = body + b"changed"
        (root / entry["local_path"]).write_bytes(changed)
        entry.update(sha256=_sha(changed), size=len(changed))
        manifest.write_text(json.dumps(_document([entry])))
        code, report = sync.execute(manifest, root=root, backend="drive-desktop", drive_root=drive, apply=True)
        assert code != 0
        assert (drive / entry["local_path"]).read_bytes() == body


def test_truncated_manifest_file_fails(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{", encoding="utf-8")
    code, report = sync.execute(manifest, root=tmp_path / "assets")
    assert code != 0
    assert report["assets"] == []
    assert report["errors"]
