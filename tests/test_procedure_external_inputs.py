"""External-input manifests and LF receipts in the job walker (#1202, KPP1 cold-run F2).

All files here are SYNTHETIC temp files except the read-only checks of the committed
KPP1 source registry.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai import procedure as p

ROOT = Path(__file__).resolve().parents[1]
GATES = p.GATES
TAG = "external-inputs/1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put(root: Path, name: str, data: bytes) -> dict:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": name, "sha256": sha(data)}


def foreign_absolute() -> str:
    """An absolute path of the *other* OS flavour: never reachable here."""
    return "/nonexistent-agr/synthetic.dwg" if os.name == "nt" else "C:/nonexistent-agr/synthetic.dwg"


def make_repo(tmp_path, rows, status="review", declare=True, manifest_extra=None):
    repo, ext = tmp_path / "repo", tmp_path / "external"
    repo.mkdir()
    ext.mkdir()
    manifest = {"manifest": TAG, "job": "SYNTHETIC", "synthetic": True, "files": rows(ext)}
    manifest.update(manifest_extra or {})
    ref = put(repo, "jobs/S/inputs-manifest.json", json.dumps(manifest).encode())
    if declare:
        ref["manifest"] = TAG
    job = {"schema_version": "1.0.0", "job_id": "SYNTHETIC", "run_id": "r1", "synthetic": True,
           "path": "standard", "inputs": [ref], "artifacts": [], "deviations": [],
           "gates": {g: {"status": "missing", "note": "SYNTHETIC", "evidence": []} for g in GATES}}
    job["gates"]["inputs"] = {"status": status, "note": "SYNTHETIC", "evidence": [ref]}
    return repo, ext, job


def ext_file(ext: Path, name: str, data: bytes, recorded: str | None = None) -> dict:
    path = ext / name
    path.write_bytes(data)
    return {"path": path.as_posix(), "sha256": recorded or sha(data), "role": "SYNTHETIC"}


def inputs_row(report):
    return next(row for row in report["gates"] if row["gate"] == "inputs")


def statuses(report):
    return [(r["path"].rsplit("/", 1)[-1], r["status"]) for r in inputs_row(report)["external_inputs"]]


# --- the three acceptance cases -------------------------------------------------------------

def test_reachable_equal_row(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a.dwg", b"SYNTHETIC A")], status="pass")
    report = p.inspect_job(job, repo)
    row = inputs_row(report)
    assert statuses(report) == [("a.dwg", "equal")]
    assert row["errors"] == [] and row["status"] == "pass" and row["ready"] is True
    assert row["evidence_exists"] == [{"path": "jobs/S/inputs-manifest.json", "verified": True}]


def test_reachable_mismatch_row_is_a_hash_failure(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a.dwg", b"SYNTHETIC A", "0" * 64)],
                             status="pass")
    report = p.inspect_job(job, repo)
    row = inputs_row(report)
    assert statuses(report) == [("a.dwg", "mismatch")]
    assert row["external_inputs"][0]["actual_sha256"] == sha(b"SYNTHETIC A")
    assert row["status"] == "fail" and any("external input hash mismatch" in e for e in row["errors"])
    assert report["passed"] is False


def test_unreachable_row_is_reported_not_failed_not_passed(tmp_path):
    def rows(ext):
        return [ext_file(ext, "a.dwg", b"SYNTHETIC A"),
                {"path": (ext / "gone.dwg").as_posix(), "sha256": "1" * 64},
                {"path": foreign_absolute(), "sha256": "2" * 64}]
    repo, _, job = make_repo(tmp_path, rows, status="pass")
    report = p.inspect_job(job, repo)
    row = inputs_row(report)
    assert statuses(report) == [("a.dwg", "equal"), ("gone.dwg", "unreachable"), ("synthetic.dwg", "unreachable")]
    assert row["errors"] == []  # not a hash failure ...
    assert row["status"] == "review" and row["ready"] is False  # ... and not a silent pass
    assert row["unreachable"] == 2
    assert all("reason" in r for r in row["external_inputs"][1:])


def test_review_gate_keeps_its_status_and_lists_rows(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a.dwg", b"A"),
                                                    {"path": foreign_absolute(), "sha256": "2" * 64}])
    row = inputs_row(p.inspect_job(job, repo))
    assert row["status"] == "review" and row["errors"] == []
    assert [r["status"] for r in row["external_inputs"]] == ["equal", "unreachable"]


# --- fail-closed probes ---------------------------------------------------------------------

@pytest.mark.parametrize("label,rows,extra", [
    ("empty files", lambda ext: [], None),
    ("files not a list", lambda ext: {"a": 1}, None),
    ("missing sha", lambda ext: [{"path": (ext / "a").as_posix()}], None),
    ("short sha", lambda ext: [{"path": (ext / "a").as_posix(), "sha256": "abc"}], None),
    ("upper sha", lambda ext: [{"path": (ext / "a").as_posix(), "sha256": "A" * 64}], None),
    ("relative path", lambda ext: [{"path": "jobs/S/a.dwg", "sha256": "1" * 64}], None),
    ("empty path", lambda ext: [{"path": "", "sha256": "1" * 64}], None),
    ("duplicate path", lambda ext: [{"path": (ext / "a").as_posix(), "sha256": "1" * 64},
                                    {"path": (ext / "a").as_posix(), "sha256": "1" * 64}], None),
    ("duplicate alias", lambda ext: [{"path": (ext / "a").as_posix(), "sha256": "1" * 64},
                                     {"path": str(ext / "x" / ".." / "a"), "sha256": "1" * 64}], None),
    ("wrong tag", lambda ext: [{"path": (ext / "a").as_posix(), "sha256": "1" * 64}],
     {"manifest": "external-inputs/2"}),
])
def test_malformed_manifest_fails(tmp_path, label, rows, extra):
    repo, _, job = make_repo(tmp_path, rows, status="review", manifest_extra=extra)
    report = p.inspect_job(job, repo)
    row = inputs_row(report)
    assert row["status"] == "fail", label
    assert any("external-inputs manifest" in e for e in row["errors"]), (label, row["errors"])
    assert report["passed"] is False


def test_nan_in_manifest_fails(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a", b"A")])
    path = repo / "jobs/S/inputs-manifest.json"
    data = path.read_text().replace('"synthetic": true', '"synthetic": NaN').encode()
    path.write_bytes(data)
    job["inputs"][0]["sha256"] = job["gates"]["inputs"]["evidence"][0]["sha256"] = sha(data)
    row = inputs_row(p.inspect_job(job, repo))
    assert row["status"] == "fail" and any("external-inputs manifest" in e for e in row["errors"])


def test_directory_row_is_an_error_not_unreachable(tmp_path):
    repo, ext, job = make_repo(tmp_path, lambda ext: [{"path": ext.as_posix(), "sha256": "1" * 64}])
    row = inputs_row(p.inspect_job(job, repo))
    assert row["status"] == "fail" and any("not a regular file" in e for e in row["errors"])


def test_undeclared_manifest_is_rejected(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a", b"A")], declare=False)
    row = inputs_row(p.inspect_job(job, repo))
    assert row["status"] == "fail" and any("undeclared external-inputs manifest" in e for e in row["errors"])


def test_declared_on_a_plain_file_is_rejected(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a", b"A")])
    plain = put(repo, "jobs/S/object.json", b'{"synthetic": true}')
    plain["manifest"] = TAG
    job["inputs"] = job["gates"]["inputs"]["evidence"] = [plain]
    row = inputs_row(p.inspect_job(job, repo))
    assert row["status"] == "fail" and any("external-inputs manifest" in e for e in row["errors"])


@pytest.mark.parametrize("gate", ["parts", "report"])
def test_manifest_only_in_inputs_role(tmp_path, gate):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a", b"A")])
    job["gates"][gate] = {"status": "review", "note": "SYNTHETIC", "evidence": [dict(job["inputs"][0])]}
    row = next(r for r in p.inspect_job(job, repo)["gates"] if r["gate"] == gate)
    assert row["status"] == "fail" and any("only in the inputs role" in e for e in row["errors"])


def test_manifest_hash_mismatch_does_not_expand(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a", b"A")])
    (repo / "jobs/S/inputs-manifest.json").write_bytes(b'{"manifest": "external-inputs/1", "files": []}')
    row = inputs_row(p.inspect_job(job, repo))
    assert row["status"] == "fail" and any("hash mismatch: jobs/S/" in e for e in row["errors"])
    assert row.get("external_inputs", []) == []


def test_unknown_manifest_tag_on_evidence_is_schema_error(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a", b"A")])
    job["inputs"][0]["manifest"] = "external-inputs/9"
    assert p.inspect_job(job, repo)["errors"]


def test_brute_force_status_partition(tmp_path):
    """Generated probe: every row ends in exactly one status, in input order, none dropped."""
    import random
    rng = random.Random(1202)
    for trial in range(40):
        kinds = [rng.choice(["equal", "mismatch", "unreachable"]) for _ in range(rng.randint(1, 6))]

        def rows(ext, kinds=kinds):
            out = []
            for i, kind in enumerate(kinds):
                if kind == "unreachable":
                    out.append({"path": (ext / f"missing{i}.bin").as_posix(), "sha256": "3" * 64})
                else:
                    out.append(ext_file(ext, f"f{i}.bin", f"SYNTHETIC {trial} {i}".encode(),
                                        None if kind == "equal" else "4" * 64))
            return out
        sub = tmp_path / str(trial)
        sub.mkdir()
        repo, _, job = make_repo(sub, rows, status="pass")
        report = p.inspect_job(job, repo)
        row = inputs_row(report)
        assert [r["status"] for r in row["external_inputs"]] == kinds
        expected = "fail" if "mismatch" in kinds else ("review" if "unreachable" in kinds else "pass")
        assert row["status"] == expected
        assert report["passed"] is False  # later gates are missing in every trial


# --- CLI: LF receipts, output never aliases an external input --------------------------------

def run_cli(repo, job, out, cwd=None):
    (repo / "job.yaml").write_text(json.dumps(job), encoding="utf-8")
    return subprocess.run([sys.executable, "-m", "dt_ai.procedure", str(repo / "job.yaml"), "--root", str(repo),
                           "--output", str(out)], capture_output=True, text=True, cwd=cwd, timeout=120)


def test_walk_output_is_lf_only(tmp_path):
    repo, _, job = make_repo(tmp_path, lambda ext: [ext_file(ext, "a", b"A")])
    out = tmp_path / "walk" / "walk-v001.json"
    proc = run_cli(repo, job, out)
    assert proc.returncode == 1, proc.stderr  # later gates missing
    data = out.read_bytes()
    assert b"\r\n" not in data and b"\r" not in data and data.endswith(b"}\n")
    assert json.loads(data)["gates"][0]["external_inputs"][0]["status"] == "equal"


def test_core_write_json_is_lf_only(tmp_path):
    from dt_ai.core.io import write_json
    out = tmp_path / "receipt.json"
    write_json(out, {"gate": "SYNTHETIC", "lines": ["a", "b"]})
    assert b"\r\n" not in out.read_bytes()


def test_output_aliasing_an_external_input_is_refused(tmp_path):
    target = {}

    def rows(ext):
        target["path"] = ext / "walk.json"
        return [{"path": target["path"].as_posix(), "sha256": "5" * 64}]
    repo, _, job = make_repo(tmp_path, rows)
    proc = run_cli(repo, job, target["path"])
    assert proc.returncode == 1 and "aliases" in proc.stdout
    assert not target["path"].exists()


# --- KPP1 source registry ----------------------------------------------------------------------

def test_kpp1_source_registry_matches_cold_run_manifest():
    registry = json.loads((ROOT / "jobs/KPP1/sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "jobs/KPP1/cold-run-1172/inputs-manifest.json").read_text(encoding="utf-8"))
    assert registry["manifest"] == TAG and registry["job"] == "KPP1" and registry["synthetic"] is False
    assert [(r["path"], r["sha256"]) for r in registry["files"]] == \
        [(r["path"], r["sha256"]) for r in manifest["files"]]
    for row in registry["files"]:
        assert row["location"] in ("asset-store", "named-folder")
        assert (row["location"] == "asset-store") == row["path"].startswith(registry["asset_store"])
    p.parse_external_manifest(json.dumps(registry).encode())  # the walker accepts the registry format


def test_kpp1_job_declares_its_manifest():
    job = p._read(ROOT / "jobs/KPP1/job.yaml")
    declared = [ref for ref in job["inputs"] if ref.get("manifest") == TAG]
    assert [ref["path"] for ref in declared] == ["jobs/KPP1/cold-run-1172/inputs-manifest.json"]


def test_procedure_documents_store_lf_and_fresh_walk():
    text = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    for fact in ("named asset store", "G:/Мой диск/AGR-assets/", "jobs/<ID>/sources.json",
                 "manifest: external-inputs/1", "unreachable", "LF", "git worktree add --detach"):
        assert fact in text, fact
