"""new-case: process-level offline asset-store regression; synthetic bytes only."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def test_local_cli_offline_dry_run(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    payload = b"synthetic asset CLI regression #350"
    (root / "sample.bin").write_bytes(payload)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": "asset-store/1", "local_root": "C:/x/assets",
        "login": "pending", "drive": "google-drive", "rejected_backends": ["dropbox"],
        "assets": [{
            "id": "sample", "version": "v001", "local_path": "sample.bin",
            "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload),
            "drive_link": "pending", "licence": None,
            "source": "synthetic test fixture",
        }],
    }), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "tools/assets/sync.py"
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = subprocess.run([sys.executable, str(script), "--manifest", str(manifest),
                             "--root", str(root), "--out", str(tmp_path / "report.json")],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["dry_run"] is True
    assert report["assets"][0]["status"] == "match"
    assert report["assets"][0]["drive_link"] == "pending"
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
