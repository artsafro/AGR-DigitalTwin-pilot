"""Task-to-model gate contract; all generated bundle data is SYNTHETIC."""
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GATES = ("inputs", "parts", "operations", "budgets", "export_readback", "report", "visual", "checker")


def load():
    assert importlib.util.find_spec("dt_ai.procedure") is not None, "Missing task-to-model validator"
    from dt_ai import procedure
    return procedure


def test_each_missing_gate(tmp_path):
    p = load()
    for omitted in GATES:
        job = {"schema_version": "1.0.0", "job_id": "SYNTHETIC", "run_id": "r1",
               "synthetic": True, "path": "standard", "deviations": [],
               "gates": {g: {"status": "missing", "note": "not executed", "evidence": []}
                         for g in GATES if g != omitted}}
        report = p.inspect_job(job, tmp_path)
        assert report["passed"] is False
        assert len(report["gates"]) == 8
        assert omitted in report["errors"][0]


def store(root, name, value):
    path = root / name
    text = json.dumps(value) if not isinstance(value, str) else value
    path.write_text(text, encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def bundle(tmp_path):
    p = load()
    source = store(tmp_path, "source.txt", "SYNTHETIC test source")
    artifact = store(tmp_path, "export.json", {"synthetic": True})
    report = store(tmp_path, "report.md", "# SYNTHETIC test-only report")
    sheet = store(tmp_path, "sheet.html", "SYNTHETIC test-only review page")
    parts = store(tmp_path, "parts.json", {
        "synthetic": True, "object_id": "SYNTH", "source_tier": "B",
        "sources": [{"kind": "synthetic", "reference": "source.txt"}],
        "triangle_budget": {"npm": 10, "vpm": 10},
        "parts": [{"id": "wall", "part_class": "wall", "sources": [{"kind": "object", "reference": "wall"}],
                   "operation": "keep", "triangle_budget": {"npm": 2, "vpm": 2}}],
        "status": "confirmed", "gate1": {"actor": "synthetic test user", "date": "2026-10-20",
                                           "scope": "synthetic_fixture", "note": "TEST ONLY"}})
    gates = {g: {"status": "pass", "note": "SYNTHETIC contract test only", "evidence": []} for g in GATES}
    gates["inputs"]["evidence"] = [source]
    gates["parts"]["evidence"] = [parts]
    gates["report"]["evidence"] = [report]
    for gate in ("operations", "budgets", "export_readback", "visual", "checker"):
        receipt = {"gate": gate, "run_id": "r1", "artifact_sha256": [artifact["sha256"]],
                   "input_evidence": [source], "parts_sha256": parts["sha256"]}
        if gate == "operations":
            receipt.update(operations=["keep"], checks={f"{phase}.{name}": "pass"
                           for phase in ("before", "after") for name in p.INVARIANTS})
        elif gate == "budgets":
            receipt["measurements"] = [{"value": 2, "limit": 10, "comparison": "le", "rule": "synthetic limit"}]
        elif gate == "export_readback":
            receipt.update(clean_process=True, checks={x: "pass" for x in ("topology", "uv", "materials", "transforms")})
        elif gate == "visual":
            receipt.update(decision="approved", actor_role="user", actor="synthetic test user", date="2026-10-20",
                           scope="synthetic_fixture", review_tool="synthetic board", decision_reference="TEST ONLY",
                           sheet=sheet, checks={x: "pass" for x in
                           ("face_orientation", "album_overlay", "source_overlay", "material_legend", "sections")})
        else:
            receipt.update(tool="SINTEZ AGR Checker", complete=True, checks={"synthetic_check": "pass"})
        gates[gate]["evidence"] = [store(tmp_path, f"{gate}.json", receipt)]
    job = {"schema_version": "1.0.0", "job_id": "SYNTHETIC", "run_id": "r1", "synthetic": True,
           "inputs": [source], "artifacts": [artifact], "path": "standard", "deviations": [], "gates": gates}
    return job


def run_cli(bundle, root, *extra):
    path = root / "job.yaml"
    path.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "dt_ai.procedure", str(path), "--root", str(root), *extra],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


def test_fresh_process_cli(bundle, tmp_path):
    completed = run_cli(bundle, tmp_path)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads(completed.stdout)
    assert result["passed"] is True
    assert len(result["gates"]) == 8
    assert all(row["ready"] for row in result["gates"])


def test_complete_synthetic_walk(bundle, tmp_path):
    assert load().inspect_job(bundle, tmp_path)["passed"] is True
    job = tmp_path / "job.yaml"
    job.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    assert load().main([str(job), "--root", str(tmp_path)]) == 0


@pytest.mark.parametrize("gate", GATES)
def test_missing_gate_cli(bundle, tmp_path, gate):
    del bundle["gates"][gate]
    path = tmp_path / "job.yaml"
    path.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    assert load().main([str(path), "--root", str(tmp_path)]) == 1


def test_gate_map_order(bundle, tmp_path):
    expected = load().inspect_job(bundle, tmp_path)
    bundle["gates"] = dict(reversed(list(bundle["gates"].items())))
    assert load().inspect_job(bundle, tmp_path) == expected


def test_reset_receipts(bundle, tmp_path):
    bundle["run_id"] = "r2"
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert next(r for r in result["gates"] if r["gate"] == "operations")["status"] == "fail"


def test_repeated_walk(bundle, tmp_path):
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    results = [load().inspect_job(bundle, tmp_path) for _ in range(3)]
    assert results[0] == results[1] == results[2]
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("raw", ["", "null", "{}", "[]", "schema_version: 2", ".nan", ".inf",
                               "gates: 3", "gates: {inputs: null}", "a: 1\na: 2"])
def test_invalid_contract(tmp_path, raw):
    path = tmp_path / "job.yaml"
    path.write_text(raw, encoding="utf-8")
    assert load().main([str(path), "--root", str(tmp_path)]) == 1


@pytest.mark.parametrize("value,limit,comparison,passed", [
    (float("nan"), 10, "le", False), (float("inf"), 10, "le", False),
    (1, float("inf"), "le", False), (10, 10, "lt", False), (10, 10, "le", True),
    (11, 10, "le", False), (-1, 10, "le", False), (True, 10, "le", False), (1, 10, "unknown", False)])
def test_budget_boundaries(bundle, tmp_path, value, limit, comparison, passed):
    ref = bundle["gates"]["budgets"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt["measurements"][0].update(value=value, limit=limit, comparison=comparison)
    bundle["gates"]["budgets"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert load().inspect_job(bundle, tmp_path)["passed"] is passed


@pytest.mark.parametrize("gate", ("parts", "operations", "budgets", "export_readback", "visual", "checker"))
def test_unrelated_receipts(bundle, tmp_path, gate):
    bundle["gates"][gate]["evidence"] = [bundle["inputs"][0]]
    assert not load().inspect_job(bundle, tmp_path)["passed"]


@pytest.mark.parametrize("mode", ("job", "source", "receipt", "hardlink", "resolved", "missing_input", "missing_sheet"))
def test_output_alias(bundle, tmp_path, mode):
    path = tmp_path / "job.yaml"
    if mode == "missing_input":
        (tmp_path / "source.txt").unlink()
    if mode == "missing_sheet":
        (tmp_path / "sheet.html").unlink()
    path.write_text(yaml.safe_dump(bundle), encoding="utf-8")
    output = {"job": path, "source": tmp_path / "source.txt", "receipt": tmp_path / "checker.json",
              "resolved": tmp_path / "." / "source.txt", "missing_input": tmp_path / "source.txt", "missing_sheet": tmp_path / "sheet.html"}.get(mode)
    if mode == "hardlink":
        output = tmp_path / "alias.yaml"
        os.link(path, output)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    assert load().main([str(path), "--root", str(tmp_path), "--output", str(output)]) == 1
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


def test_deviations(bundle, tmp_path):
    log = {"gate": "operations", "what_failed": "synthetic failure", "what_was_tried": "synthetic alternative",
           "new_tool_written": "none", "result": "synthetic success"}
    bundle.update(path="deviation", deviations=[log])
    assert load().inspect_job(bundle, tmp_path)["passed"]
    for field in log:
        broken = copy.deepcopy(bundle)
        del broken["deviations"][0][field]
        assert not load().inspect_job(broken, tmp_path)["passed"]
    for gate in GATES:
        broken = copy.deepcopy(bundle)
        broken["gates"][gate] = {"status": "missing", "note": "not run", "evidence": []}
        assert not load().inspect_job(broken, tmp_path)["passed"]


def test_evidence_integrity(bundle, tmp_path):
    for name in ("source.txt", "parts.json", "export.json", "sheet.html"):
        path = tmp_path / name
        old = path.read_bytes()
        path.write_bytes(b"changed")
        assert not load().inspect_job(bundle, tmp_path)["passed"]
        path.write_bytes(old)


def test_repository_walks():
    for name in ("KERNEL-SYNTHETIC", "VATUTINO-SITE"):
        job = yaml.safe_load((ROOT / "jobs" / name / "job.yaml").read_text(encoding="utf-8"))
        result = load().inspect_job(job, ROOT)
        assert not result["passed"] and not result["errors"]
        assert [r["gate"] for r in result["gates"]] == list(GATES)
        assert result["gates"][0]["status"] == ("pass" if name == "KERNEL-SYNTHETIC" else "review")
        assert any(e["verified"] for row in result["gates"] for e in row["evidence_exists"])
        assert not any(row["errors"] for row in result["gates"])
        assert {row["gate"] for row in result["gates"] if row["status"] == "missing"} >= {"visual", "checker"}


def test_playbook_and_schema():
    p = load()
    schema = json.loads((ROOT / "schemas/JobChecklist.schema.json").read_text(encoding="utf-8"))
    assert schema == p.JobChecklist.model_json_schema()
    text = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    for name in GATES + ("what_failed", "what_was_tried", "new_tool_written", "result"):
        assert name in text
    assert "docs/procedure/TASK_TO_MODEL.md" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")

@pytest.mark.parametrize("field,bad", [("operations", "keep"), ("operations", {"keep": "pass"}),
                                      ("operations", [""]), ("checks", {"": "pass"})])
def test_malformed_operation_receipt(bundle, tmp_path, field, bad):
    ref = bundle["gates"]["operations"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt[field] = bad
    bundle["gates"]["operations"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert not load().inspect_job(bundle, tmp_path)["passed"]


def test_mandatory_d129_checks(bundle, tmp_path):
    # D129 remains mandatory even while its producers are being implemented.
    for name in ("quad_dominance", "texel_ready"):
        for phase in ("before", "after"):
            candidate = copy.deepcopy(bundle)
            ref = candidate["gates"]["operations"]["evidence"][0]
            receipt = json.loads((tmp_path / ref["path"]).read_text())
            receipt["checks"].pop(f"{phase}.{name}", None)
            candidate["gates"]["operations"]["evidence"] = [store(tmp_path, "d129-bad.json", receipt)]
            assert not load().inspect_job(candidate, tmp_path)["passed"]


def test_generated_gate_subsets(bundle, tmp_path):
    # Exhaust every presence subset, not just the eight one-at-a-time omissions.
    p = load()
    for bits in range(256):
        candidate = copy.deepcopy(bundle)
        candidate["gates"] = {g: v for i, (g, v) in enumerate(candidate["gates"].items()) if bits & (1 << i)}
        assert p.inspect_job(candidate, tmp_path)["passed"] is (bits == 255)


def test_generated_required_checks(bundle, tmp_path):
    p = load()
    for gate in ("operations", "export_readback", "visual"):
        ref = bundle["gates"][gate]["evidence"][0]
        receipt = json.loads((tmp_path / ref["path"]).read_text())
        for check in receipt["checks"]:
            candidate = copy.deepcopy(bundle)
            bad = copy.deepcopy(receipt)
            del bad["checks"][check]
            candidate["gates"][gate]["evidence"] = [store(tmp_path, "bad.json", bad)]
            assert not p.inspect_job(candidate, tmp_path)["passed"]


RECEIPT_GATES = ("operations", "budgets", "export_readback", "visual", "checker")


def rebind_receipts(bundle, root):
    """Synthetic test producer only; real producers must rerun their actual checks."""
    for gate in RECEIPT_GATES:
        ref = bundle["gates"][gate]["evidence"][0]
        receipt = json.loads((root / ref["path"]).read_text())
        receipt.update(input_evidence=bundle["inputs"],
                       parts_sha256=bundle["gates"]["parts"]["evidence"][0]["sha256"])
        bundle["gates"][gate]["evidence"] = [store(root, ref["path"], receipt)]


def test_source_identity_binding(bundle, tmp_path):
    # Unchanged bytes, even when rewritten, keep the same identity and still pass.
    bundle["inputs"] = [store(tmp_path, "source.txt", "SYNTHETIC test source")]
    bundle["gates"]["inputs"]["evidence"] = copy.deepcopy(bundle["inputs"])
    assert run_cli(bundle, tmp_path).returncode == 0
    bundle["inputs"] = [store(tmp_path, "source.txt", "SYNTHETIC changed source")]
    bundle["gates"]["inputs"]["evidence"] = copy.deepcopy(bundle["inputs"])
    completed = run_cli(bundle, tmp_path)
    assert completed.returncode == 1, completed.stdout
    result = json.loads(completed.stdout)
    assert result["passed"] is False
    for row in result["gates"]:
        if row["gate"] in RECEIPT_GATES:
            assert row["status"] == "fail" and any("input" in e for e in row["errors"])
    rebind_receipts(bundle, tmp_path)
    assert run_cli(bundle, tmp_path).returncode == 0


def test_parts_identity_binding(bundle, tmp_path):
    assert run_cli(bundle, tmp_path).returncode == 0
    ref = bundle["gates"]["parts"]["evidence"][0]
    parts = json.loads((tmp_path / ref["path"]).read_text())
    parts["gate1"]["note"] = "SYNTHETIC new confirmed version"
    bundle["gates"]["parts"]["evidence"] = [store(tmp_path, ref["path"], parts)]
    completed = run_cli(bundle, tmp_path)
    assert completed.returncode == 1, completed.stdout
    result = json.loads(completed.stdout)
    for row in result["gates"]:
        if row["gate"] in RECEIPT_GATES:
            assert row["status"] == "fail" and any("parts" in e for e in row["errors"])
    rebind_receipts(bundle, tmp_path)
    assert run_cli(bundle, tmp_path).returncode == 0


def test_generated_receipt_identity_fields(bundle, tmp_path):
    # 5 gates x 2 identity fields x 5 invalid shapes, plus renamed source paths.
    for gate in RECEIPT_GATES:
        ref = bundle["gates"][gate]["evidence"][0]
        original = json.loads((tmp_path / ref["path"]).read_text())
        for field in ("input_evidence", "parts_sha256"):
            for bad_value in ("missing", None, [], {}, "0" * 64):
                candidate = copy.deepcopy(bundle)
                bad = copy.deepcopy(original)
                if bad_value == "missing":
                    del bad[field]
                else:
                    bad[field] = bad_value
                candidate["gates"][gate]["evidence"] = [store(tmp_path, "bad-binding.json", bad)]
                result = load().inspect_job(candidate, tmp_path)
                assert not result["passed"]
                assert next(r for r in result["gates"] if r["gate"] == gate)["status"] == "fail"
    # Exact inventory includes the path, not just the bytes or the run ID.
    bundle["inputs"][0] = store(tmp_path, "renamed.txt", "SYNTHETIC test source")
    bundle["gates"]["inputs"]["evidence"] = copy.deepcopy(bundle["inputs"])
    assert run_cli(bundle, tmp_path).returncode == 1


@pytest.mark.parametrize("identity", ("source", "parts"))
@pytest.mark.parametrize("status", ("fail", "review", "not_run"))
def test_combined_receipt_regressions(bundle, tmp_path, identity, status):
    assert run_cli(bundle, tmp_path).returncode == 0
    if identity == "source":
        bundle["inputs"] = [store(tmp_path, "source.txt", "SYNTHETIC revised source")]
        bundle["gates"]["inputs"]["evidence"] = copy.deepcopy(bundle["inputs"])
    else:
        ref = bundle["gates"]["parts"]["evidence"][0]
        parts = json.loads((tmp_path / ref["path"]).read_text())
        parts["gate1"]["note"] += " revised"
        bundle["gates"]["parts"]["evidence"] = [store(tmp_path, ref["path"], parts)]
    assert run_cli(bundle, tmp_path).returncode == 1
    rebind_receipts(bundle, tmp_path)
    assert run_cli(bundle, tmp_path).returncode == 0

    ref = bundle["gates"]["budgets"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt["checks"] = {"mandatory_texture_budget": status}
    bundle["gates"]["budgets"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    completed = run_cli(bundle, tmp_path)
    assert completed.returncode == 1
    assert next(row for row in json.loads(completed.stdout)["gates"]
                if row["gate"] == "budgets")["status"] == "fail"

    receipt["checks"]["mandatory_texture_budget"] = "pass"
    receipt["measurements"][0].update(value=10, limit=10, comparison="lt")
    bundle["gates"]["budgets"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert run_cli(bundle, tmp_path).returncode == 1
    receipt["measurements"][0]["comparison"] = "le"
    bundle["gates"]["budgets"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert run_cli(bundle, tmp_path).returncode == 0

    ref = bundle["gates"]["operations"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    del receipt["checks"]["after.texel_ready"]
    bundle["gates"]["operations"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert run_cli(bundle, tmp_path).returncode == 1
    # The previous output guard must also survive the newly bound receipt format.
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    assert run_cli(bundle, tmp_path, "--output", str(tmp_path / "source.txt")).returncode == 1
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("mutation", ("add", "remove", "reorder", "path"))
def test_inventory_identity_changes(bundle, tmp_path, mutation):
    bundle["inputs"].append(store(tmp_path, "second-source.txt", "SYNTHETIC second source"))
    bundle["gates"]["inputs"]["evidence"] = copy.deepcopy(bundle["inputs"])
    rebind_receipts(bundle, tmp_path)
    assert run_cli(bundle, tmp_path).returncode == 0
    if mutation == "add":
        bundle["inputs"].append(store(tmp_path, "third-source.txt", "SYNTHETIC third source"))
    elif mutation == "remove":
        bundle["inputs"].pop()
    elif mutation == "reorder":
        bundle["inputs"].reverse()
    else:
        bundle["inputs"][0] = store(tmp_path, "alias-source.txt", "SYNTHETIC test source")
    bundle["gates"]["inputs"]["evidence"] = copy.deepcopy(bundle["inputs"])
    assert run_cli(bundle, tmp_path).returncode == 1


@pytest.mark.parametrize("checks", [
    {"mandatory_texture_budget": status} for status in ("fail", "review", "not_run", "unsupported")
] + [{}, None, [], "pass", {"": "pass"}, {"   ": "pass"}, {1: "pass"}])
def test_budget_declared_checks(bundle, tmp_path, checks):
    ref = bundle["gates"]["budgets"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt["checks"] = checks
    # YAML preserves integer keys; JSON would coerce them into valid string IDs.
    bundle["gates"]["budgets"]["evidence"] = [store(tmp_path, ref["path"], yaml.safe_dump(receipt))]
    completed = run_cli(bundle, tmp_path)
    assert completed.returncode == 1, completed.stdout
    result = json.loads(completed.stdout)
    assert result["passed"] is False
    assert next(row for row in result["gates"] if row["gate"] == "budgets")["status"] == "fail"


def test_budget_declared_pass_control(bundle, tmp_path):
    ref = bundle["gates"]["budgets"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt["checks"] = {"mandatory_texture_budget": "pass"}
    bundle["gates"]["budgets"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert run_cli(bundle, tmp_path).returncode == 0


@pytest.mark.parametrize("status", ("fail", "review", "not_run"))
def test_checker_not_measured_never_passes(bundle, tmp_path, status):
    ref = bundle["gates"]["checker"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt["checks"]["synthetic_check"] = status
    bundle["gates"]["checker"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert not load().inspect_job(bundle, tmp_path)["passed"]



# --- #387: source evidence pinned to an immutable commit, generated artifacts to the working tree ---
SOURCE_SUFFIXES = (".py", ".cs", ".ps1", ".ms", ".js", ".ts")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=SYNTHETIC", "-c", "user.email=synthetic@test",
                           "-c", "commit.gpgsign=false", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def commit_all(root, message="SYNTHETIC"):
    if not (root / ".git").exists():
        git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


def pin_source(bundle, root):
    """Pin the SYNTHETIC source input to a commit and rebind every receipt to the pinned inventory."""
    commit = commit_all(root)
    pinned = dict(bundle["inputs"][0], commit=commit)
    bundle["inputs"] = [pinned]
    bundle["gates"]["inputs"]["evidence"] = [pinned]
    for gate in ("operations", "budgets", "export_readback", "visual", "checker"):
        ref = bundle["gates"][gate]["evidence"][0]
        receipt = json.loads((root / ref["path"]).read_text())
        receipt["input_evidence"] = [pinned]
        bundle["gates"][gate]["evidence"] = [store(root, ref["path"], receipt)]
    return commit


def errors(result):
    return [e for row in result["gates"] for e in row["errors"]] + result["errors"]


def test_pinned_source_survives_worktree_edit(bundle, tmp_path):
    """(a) editing a commit-pinned source file in the working tree does not fail the walk."""
    pin_source(bundle, tmp_path)
    assert load().inspect_job(bundle, tmp_path)["passed"] is True
    (tmp_path / "source.txt").write_text("edited after the pinned commit", encoding="utf-8")
    commit_all(tmp_path, "later edit")  # also a later commit of the same path
    result = load().inspect_job(bundle, tmp_path)
    assert result["passed"] is True, errors(result)
    (tmp_path / "source.txt").unlink()  # even a deleted working-tree copy: the pinned blob is the evidence
    assert load().inspect_job(bundle, tmp_path)["passed"] is True
    completed = run_cli(bundle, tmp_path)  # fresh process
    assert completed.returncode == 0, completed.stdout


def test_receipt_binds_pinned_commit(bundle, tmp_path):
    commit = pin_source(bundle, tmp_path)
    ref = bundle["gates"]["operations"]["evidence"][0]
    receipt = json.loads((tmp_path / ref["path"]).read_text())
    receipt["input_evidence"] = [{k: v for k, v in bundle["inputs"][0].items() if k != "commit"}]
    bundle["gates"]["operations"]["evidence"] = [store(tmp_path, ref["path"], receipt)]
    assert not load().inspect_job(bundle, tmp_path)["passed"]
    assert commit


@pytest.mark.parametrize("case", ["missing_commit", "wrong_sha", "absent_path", "not_ancestor", "no_git"])
def test_pinned_source_wrong_revision_fails(bundle, tmp_path, case):
    """(b) a wrong commit, blob or path is an error, never a pass."""
    commit = pin_source(bundle, tmp_path)
    ref = bundle["gates"]["inputs"]["evidence"][0]
    if case == "missing_commit":
        ref["commit"] = "0" * 40
    elif case == "wrong_sha":
        ref["sha256"] = hashlib.sha256(b"other").hexdigest()
    elif case == "absent_path":
        ref["path"] = "never-committed.txt"
        (tmp_path / "never-committed.txt").write_text("SYNTHETIC", encoding="utf-8")
    elif case == "not_ancestor":
        git(tmp_path, "checkout", "-q", "-b", "side")
        (tmp_path / "source.txt").write_text("side branch", encoding="utf-8")
        side = commit_all(tmp_path, "side")
        git(tmp_path, "checkout", "-q", commit)
        git(tmp_path, "checkout", "-q", "-B", "main_line")
        ref["commit"] = side
        ref["sha256"] = hashlib.sha256(b"side branch").hexdigest()
    else:
        (tmp_path / ".git").rename(tmp_path / "moved-git-dir")  # rmtree trips on read-only objects on Windows
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert result["gates"][0]["status"] == "fail" and result["gates"][0]["errors"], result["gates"][0]


@pytest.mark.parametrize("commit", ["HEAD", "main", "abc1234", "A" * 40, "", " " + "0" * 40, 40])
def test_pinned_commit_must_be_full_object_id(bundle, tmp_path, commit):
    """Mutable refs (HEAD, branch names) and abbreviations are not immutable revisions."""
    pin_source(bundle, tmp_path)
    bundle["gates"]["inputs"]["evidence"][0]["commit"] = commit
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"] and result["errors"]


def test_generated_artifact_edit_still_fails(bundle, tmp_path):
    """(c) working-tree sha256 stays mandatory for generated artifacts beside pinned sources."""
    pin_source(bundle, tmp_path)
    for name in ("export.json", "report.md", "parts.json", "sheet.html"):
        path = tmp_path / name
        old = path.read_bytes()
        path.write_bytes(old + b" edited")
        assert not load().inspect_job(bundle, tmp_path)["passed"], name
        path.write_bytes(old)
    assert load().inspect_job(bundle, tmp_path)["passed"] is True


def test_repository_source_evidence_is_pinned():
    """Every source-code reference in the committed jobs names a commit, so later edits cannot turn main red."""
    for name in ("KERNEL-SYNTHETIC", "VATUTINO-SITE"):
        job = yaml.safe_load((ROOT / "jobs" / name / "job.yaml").read_text(encoding="utf-8"))
        refs = list(job["inputs"]) + list(job["artifacts"])
        refs += [ref for gate in job["gates"].values() for ref in gate["evidence"]]
        sources = [ref for ref in refs if ref["path"].endswith(SOURCE_SUFFIXES)]
        assert sources, name
        assert all(ref.get("commit") for ref in sources), [r["path"] for r in sources if not r.get("commit")]
        generated = [ref for ref in refs if not ref["path"].endswith(SOURCE_SUFFIXES)]
        assert generated and not any(ref.get("commit") for ref in generated), name


def pin_generated(bundle, root, witness, commit):
    """Add ``commit`` to one generated artifact/receipt/part/report reference and return its path."""
    if witness == "export":
        ref = bundle["artifacts"][0]
    elif witness == "report":
        ref = bundle["gates"]["report"]["evidence"][0]
    elif witness == "operations":
        ref = bundle["gates"]["operations"]["evidence"][0]
    else:  # parts
        ref = bundle["gates"]["parts"]["evidence"][0]
    ref["commit"] = commit
    return root / ref["path"]


@pytest.mark.parametrize("witness", ("export", "report", "operations", "parts"))
def test_generated_evidence_rejects_pinned_commit(bundle, tmp_path, witness):
    # P1 regression: a valid ancestor commit on a generated artifact/receipt/part/report must not
    # substitute historical bytes for current delivery evidence; current bytes stay mandatory.
    commit = commit_all(tmp_path)
    path = pin_generated(bundle, tmp_path, witness, commit)
    path.write_bytes(b"CORRUPTED GENERATED ARTIFACT")
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert any("pinned commit not allowed" in e for e in errors(result)), errors(result)
    completed = run_cli(bundle, tmp_path)
    assert completed.returncode == 1, completed.stdout
    assert "pinned commit not allowed" in completed.stdout


@pytest.mark.parametrize("witness", ("export", "report", "operations", "parts"))
def test_generated_evidence_clean_controls(bundle, tmp_path, witness):
    # Clean control: without commit the generated evidence passes on its current bytes; adding
    # commit (even without corrupting) is itself rejected fail-closed.
    commit = commit_all(tmp_path)
    assert load().inspect_job(bundle, tmp_path)["passed"] is True
    pin_generated(bundle, tmp_path, witness, commit)
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert any("pinned commit not allowed" in e for e in errors(result))
    assert commit


def test_generated_report_role_rejects_source_like_suffix(bundle, tmp_path):
    # Role beats suffix: a generated report renamed to a source suffix still rejects commit.
    commit = commit_all(tmp_path)
    ref = bundle["gates"]["report"]["evidence"][0]
    data = (tmp_path / ref["path"]).read_bytes()
    (tmp_path / ref["path"]).unlink()
    ref.update(path="report.py", sha256=hashlib.sha256(data).hexdigest(), commit=commit)
    (tmp_path / "report.py").write_bytes(data)
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert any("pinned commit not allowed for report evidence" in e for e in errors(result))


def test_generated_artifact_role_rejects_source_like_suffix(bundle, tmp_path):
    # An exported artifact named like source must still be working-tree verified (role rule).
    commit = commit_all(tmp_path)
    artifact = bundle["artifacts"][0]
    data = (tmp_path / artifact["path"]).read_bytes()
    (tmp_path / artifact["path"]).unlink()
    (tmp_path / "export.py").write_bytes(data)
    artifact.update(path="export.py", commit=commit)  # sha256 unchanged: same bytes
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert any("pinned commit not allowed for artifact evidence" in e for e in errors(result))


@pytest.mark.parametrize("role", ("operations", "parts"))
@pytest.mark.parametrize("suffix", SOURCE_SUFFIXES)
def test_generated_primary_rejects_pinned_commit_any_suffix(bundle, tmp_path, role, suffix):
    # Round-2 P1: the primary parsed contract/receipt is a generated semantic role. Renaming it
    # to a source-like suffix and pinning it must not substitute historical bytes for current
    # evidence; the corrupted working-tree file must still be reported and fail the walk.
    ref = bundle["gates"][role]["evidence"][0]
    (tmp_path / ref["path"]).rename(tmp_path / (role + suffix))
    ref["path"] = role + suffix
    assert load().inspect_job(bundle, tmp_path)["passed"] is True  # clean unpinned control
    ref["commit"] = commit_all(tmp_path)
    (tmp_path / (role + suffix)).write_bytes(b"CORRUPTED GENERATED EVIDENCE")
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert any("pinned commit not allowed for generated" in e for e in errors(result)), errors(result)
    completed = run_cli(bundle, tmp_path)
    assert completed.returncode == 1, completed.stdout
    assert "pinned commit not allowed" in completed.stdout


@pytest.mark.parametrize("role", ("operations", "parts"))
@pytest.mark.parametrize("suffix", SOURCE_SUFFIXES)
def test_generated_primary_clean_unpinned_control(bundle, tmp_path, role, suffix):
    # Clean control: renaming the generated primary to a source suffix WITHOUT a commit still
    # passes on its current bytes; eligibility is decided by semantic role, not by suffix.
    ref = bundle["gates"][role]["evidence"][0]
    (tmp_path / ref["path"]).rename(tmp_path / (role + suffix))
    ref["path"] = role + suffix
    result = load().inspect_job(bundle, tmp_path)
    assert result["passed"] is True, errors(result)


def test_combined_pinned_source_with_generated_primary(bundle, tmp_path):
    # Combined control: a pinned source input and a generated primary renamed to a source
    # suffix coexist; the source pin stays green while only the generated primary fails.
    pin_source(bundle, tmp_path)
    ref = bundle["gates"]["operations"]["evidence"][0]
    (tmp_path / ref["path"]).rename(tmp_path / "operations.py")
    ref["path"] = "operations.py"
    commit = commit_all(tmp_path)
    ref["commit"] = commit
    (tmp_path / "operations.py").write_bytes(b"CORRUPTED GENERATED EVIDENCE")
    result = load().inspect_job(bundle, tmp_path)
    assert not result["passed"]
    assert any("pinned commit not allowed for generated operations" in e for e in errors(result))
    inputs_row = next(r for r in result["gates"] if r["gate"] == "inputs")
    assert inputs_row["status"] == "pass" and not inputs_row["errors"]
