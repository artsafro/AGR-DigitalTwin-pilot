"""Research artifact checks, not geometry or proposed agr CLI certification.

Pattern: n/a | new-case: independent source-blob census and draft research checks for #1296.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "docs/research/reuse-1296/measure.py"


def analyzer():
    assert ANALYZER.is_file(), "Missing reproducible research inventory analyzer"
    spec = importlib.util.spec_from_file_location("reuse_1296", ANALYZER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_covers_scripts_not_config():
    m = analyzer()
    paths = ["jobs/A/scripts/export.py", "jobs/A/scripts/settings.json",
             "tools/example.sh", "adapters/max/agr_tools/core.py",
             "src/dt_ai/cli/main.py", "src/dt_ai/ordinary.py", "tools/git-hooks/pre-commit"]
    texts = {p: "print('ok')" for p in paths}
    texts[paths[-1]] = "#!/usr/bin/env bash\nexit 0\n"
    assert m.select_paths(paths, texts) == [paths[i] for i in (0, 2, 3, 4, 6)]


def test_duplicate_names_and_content_are_independent():
    m = analyzer()
    assert m.name_key("jobs/A/scripts/package_vpm_v003.py") == "package_vpm"
    source = "\n".join(f"value_{i} = transform(point_{i}, 12.0)" for i in range(30))
    near = source.replace("12.0", "24.0") + "\nprint(result)"
    pairs = m.duplicate_pairs({"a.py": source, "b.py": near, "c.py": "print('unrelated')"})
    assert any(p["left"] == "a.py" and p["right"] == "b.py" and p["kind"] == "content" for p in pairs)
    assert not any(p["right"] == "c.py" for p in pairs)
    assert m.duplicate_pairs({"a.py": "", "b.py": ""}) == []


def test_static_facts_keep_evidence_and_unknowns():
    m = analyzer()
    text = '\"\"\"Export source mesh to FBX.\"\"\"\nimport bpy\nfrom dt_ai.core.io import write_json\nparser.add_argument("--source")\nbpy.ops.export_scene.fbx(filepath=out)\n'
    row = m.facts("jobs/A/scripts/export.py", text)
    assert row["purpose"] == "Export source mesh to FBX."
    assert "Blender" in row["dcc"]
    assert "--source" in row["parameters"]
    assert "export_scene" in row["outputs"]
    assert "dt_ai.core.io" in row["imports"]
    assert m.facts("tools/empty.py", "")["inputs"] == "not declared statically"


def test_inventory_matches_independent_git_blob_stream():
    import csv
    import hashlib
    import json
    import subprocess
    data = ROOT / "docs/research/reuse-1296/data"
    meta = json.loads((data / "snapshot.json").read_text())
    rows = list(csv.DictReader((data / "inventory.csv").open(encoding="utf-8")))
    ref = meta["source_ref"]
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", ref,
                                    "jobs", "tools", "src/dt_ai", "adapters/max/agr_tools"], cwd=ROOT, text=True).splitlines()
    stream = subprocess.check_output(["git", "cat-file", "--batch"], cwd=ROOT,
                                     input="".join(f"{ref}:{p}\n" for p in names).encode())
    blobs, offset = {}, 0
    for p in names:
        end = stream.index(b"\n", offset)
        size = int(stream[offset:end].split()[-1])
        blobs[p] = stream[end + 1:end + 1 + size]
        offset = end + 2 + size
    suffixes = {".py", ".ms", ".mcr", ".sh", ".ps1", ".mjs", ".js", ".cs", ".run"}
    expected = set()
    for p, b in blobs.items():
        if Path(p).suffix.lower() not in suffixes and not b.startswith(b"#!"):
            continue
        if p.startswith("jobs/") and (len(p.split("/")) < 4 or p.split("/")[2] != "scripts"):
            continue
        if p.startswith("src/") and not (p.startswith("src/dt_ai/cli/") or b"__main__" in b):
            continue
        expected.add(p)
    assert len(rows) == len({r["path"] for r in rows}) == 656
    assert {r["path"] for r in rows} == expected
    assert all(hashlib.sha256(blobs[r["path"]]).hexdigest() == r["sha256"] for r in rows)
    assert all(r[k] for r in rows for k in ("purpose", "inputs", "outputs", "dcc", "job_references", "shared_coverage"))
    assert sum(r["scope"] == "job" for r in rows) == 290
    assert meta["rows"] == len(rows)


def test_research_cli_fresh_process_and_no_clobber(tmp_path):
    import subprocess
    import sys
    script = str(ANALYZER)
    data = ROOT / "docs/research/reuse-1296/data"
    check = subprocess.run([sys.executable, script, "--ref", "bef05228", "--out", str(data), "--check"],
                           cwd=ROOT, capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr
    guard = tmp_path / "input.py"
    guard.write_text("immutable input")
    bad = subprocess.run([sys.executable, script, "--ref", "bef05228", "--out", str(guard)],
                         cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode != 0
    assert guard.read_text() == "immutable input"
    assert list(tmp_path.iterdir()) == [guard]
    alias = tmp_path / "ALIAS.py"
    alias.hardlink_to(guard)
    refused = subprocess.run([sys.executable, script, "--ref", "bef05228", "--out", str(alias)],
                             cwd=ROOT, capture_output=True, text=True)
    assert refused.returncode != 0 and guard.read_text() == "immutable input"
    assert alias.read_bytes() == guard.read_bytes()
    missing = subprocess.run([sys.executable, script, "--ref", "missing-1296-ref", "--out", str(tmp_path / "new")],
                             cwd=ROOT, capture_output=True, text=True)
    assert missing.returncode != 0 and not (tmp_path / "new").exists()


def test_empty_partial_and_unsupported_are_not_pass_claims():
    import pytest
    m = analyzer()
    assert m.select_paths([], {}) == []
    assert m.select_paths(["tools/config.json"], {"tools/config.json": "{}"}) == []
    assert "AST unsupported" in m.facts("tools/bad.py", "def (")["purpose"]
    assert m.facts("tools/untrusted.py", "raise RuntimeError('must not execute')")["inputs"] == "not declared statically"
    for threshold in (float("nan"), float("inf"), -1, 0, 1.01):
        with pytest.raises(ValueError):
            m.duplicate_pairs({}, threshold)
    source = "\n".join(f"value_{i} = transform(point_{i}, 12)" for i in range(20))
    pairs = m.duplicate_pairs({"a.py": source, "b.py": source}, threshold=1)
    assert pairs[0]["kind"] == "exact" and pairs[0]["similarity"] == 1


def test_route_and_research_links_and_scope():
    import re
    docs = [ROOT / "routes/npm-oks.md", ROOT / "docs/research/reuse-1296/report.md",
            ROOT / "docs/research/reuse-1296/benchmark.md"]
    for p in docs:
        text = p.read_text(encoding="utf-8")
        for dest in re.findall(r"\]\(([^)]+)\)", text):
            if not dest.startswith(("https:", "http:", "#")):
                assert (p.parent / dest.split("#")[0]).exists(), (p, dest)
        if p.name != "npm-oks.md":
            assert "Questions for Artem" in text
    route = docs[0].read_text(encoding="utf-8")
    assert "Accepted route shape [D271]" in route and "passed=true" in route
    assert "Accepted scope and remaining benchmark gate" in route
    assert "#1280" in route and "#1281" in route and "#1292" in route
    assert not (ROOT / "routes/vpm-ground.md").exists()
    benchmark = docs[2].read_text(encoding="utf-8")
    assert "Track A" in benchmark and "Track B" in benchmark and "<= $10" in benchmark
    assert all(term in benchmark for term in ("Claude", "Codex", "Kimi", "new_code_lines", "billed_usd", "not executed"))
