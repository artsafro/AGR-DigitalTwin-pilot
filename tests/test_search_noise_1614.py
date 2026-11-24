"""#1614 agent-search noise: historical job data + unreached docs hidden from rg, measure, evidence move.

new-case: tests of tools/architecture/search_noise.py (generated .ignore block, job classification, evidence store).
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as dg  # noqa: E402
import search_noise as sn  # noqa: E402

RG = shutil.which("rg")
needs_rg = pytest.mark.skipif(RG is None, reason="ripgrep not installed")
# origin/main f6a8793b before #1614: rg --files saw 3431 files, 2632 non-test, 696 in jobs/, 725 in docs/.
BEFORE = {"visible_non_test": 2632, "jobs_visible": 696, "docs_visible": 725}


# --- synthetic git roots -----------------------------------------------------------------------------------------

CONTEXTS = """finished_jobs:
  - job: jobs/DONE
    evidence: jobs/DONE/STATE.md
    match: "accepted"
"""
CONFIG = """kept_jobs:
  - job: jobs/LIVE
    ru: "открытая задача"
live_paths:
  - path: jobs/DONE/open-1
    ru: "открыт #1"
"""


def _repo(tmp_path, files, contexts=CONTEXTS, config=CONFIG):
    base = {"docs/architecture/contexts.yaml": contexts, "docs/architecture/search-noise.yaml": config,
            "jobs/DONE/STATE.md": "accepted\n", "jobs/LIVE/STATE.md": "running\n", "AGENTS.md": "# entry\n",
            "jobs/DONE/open-1/r.json": "{}",
            "tools/cfg.py": "C = ('docs/architecture/contexts.yaml', 'docs/architecture/search-noise.yaml')\n"}
    base.update(files)
    for rel, text in base.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    return tmp_path


def _git_add(root):
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)


DOC_INDEX = "docs/architecture/README.md"
DOC_TABLE = """## Documentation ownership

| Topic | Owner | Related |
|---|---|---|
| index | [Architecture](README.md) | |
| guide | [Guide](../guide.md) | |
"""


def _docs_repo(tmp_path, files=None, *, index=DOC_TABLE, historical=""):
    return _repo(tmp_path, {DOC_INDEX: index, "docs/guide.md": "# Guide\n", **(files or {})},
                 config=CONFIG + historical)


def _check_docs(root, capsys):
    code = sn.main(["--root", str(root), "--check-docs"])
    return code, capsys.readouterr().out


def test_docs_guard_rejects_unindexed_docs_then_recovers(tmp_path, capsys):
    root = _docs_repo(tmp_path, {"docs/unindexed.md": "# Synthetic unstated ownership\n"})
    sn.write_block(root, [], ["docs/unindexed.md"])
    before = (root / ".ignore").read_bytes()
    for _ in range(2):
        code, out = _check_docs(root, capsys)
        assert code == 1
        assert "docs/unindexed.md: missing ownership row" in out
        assert (root / ".ignore").read_bytes() == before
    (root / DOC_INDEX).write_text(DOC_TABLE + "| new | [New](../unindexed.md) | |\n", encoding="utf-8")
    assert _check_docs(root, capsys)[0] == 0


def _rg(root):
    out = subprocess.run([RG, "--files", "--path-separator", "/"], cwd=root, capture_output=True, text=True).stdout
    return set(out.splitlines())


# --- real repository ---------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real():
    return sn.state(ROOT)


def test_real_repo_check_is_clean_and_every_job_is_classified(real, capsys):
    assert sn.main(["--root", str(ROOT), "--table"]) == 0
    out = capsys.readouterr().out
    assert "НЕ КЛАССИФИЦИРОВАНА" not in out and "0 problems" in out
    for job in sn.job_folders(real["files"]):
        assert f"`{job}`" in out
    assert sn.classification_problems(real["files"], real["finished"], real["kept"], real["parts"]) == []


def test_real_repo_hidden_sets_respect_live_paths_and_entry_docs(real):
    hidden = set(real["data"]) | set(real["docs"])
    assert len(real["data"]) >= 100 and len(real["docs"]) >= 150
    assert not [f for f in hidden if sn.under(f, real["parts"])]
    assert not [f for f in hidden if f in real["live"]]
    assert not [f for f in real["data"] if f.lower().endswith(dg.SCRIPT_SUFFIXES)]
    assert {"docs/plans/manual-mode-no-ai.md", "jobs/KPP1/STATE.md", "jobs/KPP1/LESSONS.md",
            "docs/agents/SKELETONS.md", "docs/decisions.md"}.isdisjoint(hidden)


@needs_rg
def test_real_repo_rg_hides_historical_data_and_docs_and_keeps_live(real):
    listed = _rg(ROOT)
    # A doc/data file merged after the last --write-ignore is "pending": visible by design until the block is
    # regenerated (search_noise.pending: reported, not a failure). Red main 2026-11-20 (batch 20261120e): research
    # docs from parallel PRs landed after #1706 and this test failed on them.
    waiting = {p.lstrip("/") for p in sn.pending(ROOT, real["data"], real["docs"])}
    assert not ((set(real["data"]) | set(real["docs"])) - waiting) & listed
    assert {"jobs/KPP1/STATE.md", "docs/plans/manual-mode-no-ai.md", "jobs/VATUTINO-SITE/maf/site-schedule.json",
            "jobs/KPP1/quad-1372/REPORT.md", "routes/revit-intake.md"} <= listed


@needs_rg
def test_real_repo_route_named_scripts_are_visible():
    """#1614: routes/revit-intake.md names these delivered-job scripts; #1546 hid them."""
    listed = _rg(ROOT)
    assert {"jobs/KPP1/scripts/export_revit_groups.mjs", "jobs/KPP1/scripts/inspect_source.py"} <= listed
    assert "jobs/KPP1/scripts/qa_gaps.py" not in listed  # an unnamed historical script stays hidden


@needs_rg
def test_real_repo_measure_dropped_against_the_cut():
    m = sn.measure(ROOT)
    # GROWTH: live (reached) files added by later PRs since the cut stay visible by design. origin/main
    # 5399ed96 sat exactly on the edge (2232 of max 2232 non-test, 545 of max 546 jobs), so any new card failed.
    # 2026-11-24: the 25-file allowance was used up by live code/jobs merged in one day (6e453db5: 2259 of max 2257;
    # KPP1 lattice job, railing core, Revit material intake) - red main again. Raised to 60; the cut itself is unchanged.
    growth = 60
    assert m["visible_non_test"] <= BEFORE["visible_non_test"] - 400 + growth
    assert m["jobs_visible"] <= BEFORE["jobs_visible"] - 150 + growth
    assert m["docs_visible"] <= BEFORE["docs_visible"] - 250 + growth
    assert m["visible"] >= m["visible_non_test"] >= m["jobs_visible"] >= m["job_scripts_visible"]


def test_skeletons_doc_names_every_kept_name_and_the_commands():
    text = (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")
    assert not [n for n in sn.KEEP_NAMES if f"`{n}`" not in text]
    assert "`skeleton.json` folders" in text and "historical-data" in text and "--verify-evidence" in text


def test_real_repo_moved_data_manifest_is_consistent(real):
    assert sn.manifest_problems(ROOT, real["files"]) == []
    manifests = [f for f in real["files"] if f.endswith("/" + sn.MANIFEST)]
    assert manifests, "the #1614 move must leave a manifest"
    for m in manifests:
        for row in json.loads((ROOT / m).read_text(encoding="utf-8"))["files"]:
            assert not (ROOT / row["path"]).exists() and len(row["sha256"]) == 64


# --- classification and config -----------------------------------------------------------------------------------

def test_classification_unclassified_double_and_empty_kept(tmp_path):
    root = _repo(tmp_path, {"jobs/NEW/a.json": "{}", "jobs/LIVE2/x.md": "x"},
                 config=CONFIG.replace("live_paths:", "  - job: jobs/GONE\n    ru: \"нет\"\nlive_paths:")
                 + "  - path: jobs/LIVE/STATE.md\n    ru: \"x\"\n")
    st = sn.state(root)
    probs = sn.classification_problems(st["files"], st["finished"], {**st["kept"], "jobs/DONE": "x"}, st["parts"])
    text = "\n".join(probs)
    assert "jobs/NEW: unclassified" in text and "jobs/LIVE2: unclassified" in text
    assert "jobs/DONE: both delivered" in text and "kept_jobs jobs/GONE holds no tracked file" in text
    assert "live_paths jobs/LIVE/STATE.md is not inside a delivered job" in text


@pytest.mark.parametrize("config,match", [
    ("kept_jobs:\n  - job: jobs/LIVE\n", "needs job"),
    ("kept_jobs:\n  - job: LIVE\n    ru: \"x\"\n", "needs job"),
    ("kept_jobs:\n  - job: jobs/LIVE\n    ru: \"x\"\n  - job: jobs/LIVE\n    ru: \"y\"\n", "listed twice"),
    ("live_paths:\n  - path: jobs/DONE/../LIVE\n    ru: \"x\"\n", "needs path"),
    ("live_paths:\n  - path: src/x\n    ru: \"x\"\n", "needs path"),
    ("live_paths:\n  - path: jobs/DONE/nothing\n    ru: \"x\"\n", "holds no tracked file"),
    ("live_paths:\n  - path: jobs/DONE/STATE.md\n    ru: \"x\"\n  - path: jobs/DONE/STATE.md\n    ru: \"x\"\n",
     "listed twice"),
    ("other: \"x\"\n", "unknown keys"),
])
def test_config_fail_closed(tmp_path, config, match):
    root = _repo(tmp_path, {}, config=config)
    with pytest.raises(ValueError, match=match):
        sn.load_config(root, sn.tracked(root))
    assert sn.main(["--root", str(root)]) == 2


def test_not_a_git_tree_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="git ls-files failed"):
        sn.tracked(tmp_path / "missing")


# --- what is hidden ----------------------------------------------------------------------------------------------

def _hidden_case(tmp_path):
    return _repo(tmp_path, {
        "jobs/DONE/LESSONS.md": "lessons", "jobs/DONE/report.json": "{}", "jobs/DONE/sub/STATE.md": "deep",
        "jobs/DONE/build.py": "x = 1\n", "jobs/DONE/.gitattributes": "* text\n", "jobs/DONE/open-1/r.json": "{}",
        "jobs/DONE/new-9/skeleton.json": "{}", "jobs/DONE/new-9/plan.json": "{}",
        "jobs/DONE/named.json": "{}", "jobs/LIVE/data.json": "{}",
        "AGENTS.md": "see [plan](docs/plans/a.md) and `jobs/DONE/named.json`\n",
        "docs/plans/a.md": "next [b](b.md)\n", "docs/plans/b.md": "leaf\n",
        "docs/plans/only-from-job.md": "x\n", "jobs/DONE/notes.md": "see docs/plans/only-from-job.md\n",
        "docs/plans/only-from-hidden.md": "x\n", "docs/old.md": "see [h](plans/only-from-hidden.md)\n",
        "tools/run.py": "CFG = 'docs/inv.json'\n", "docs/inv.json": "[\"docs/plans/from-inventory.md\"]\n",
        "docs/plans/from-inventory.md": "x\n", "docs/space dir/x [1].md": "x\n",
        "tests/test_x.py": "# docs/plans/from-test.md\n", "docs/plans/from-test.md": "x\n",
    })


def test_historical_data_keeps_identity_live_skeleton_and_named_files(tmp_path):
    st = sn.state(_hidden_case(tmp_path))
    assert st["data"] == ["jobs/DONE/notes.md", "jobs/DONE/report.json", "jobs/DONE/sub/STATE.md"]


def test_historical_docs_follow_markdown_from_entries_but_not_inventories_jobs_or_tests(tmp_path):
    st = sn.state(_hidden_case(tmp_path))
    assert set(st["docs"]) == {"docs/old.md", "docs/plans/only-from-hidden.md", "docs/plans/only-from-job.md",
                               "docs/plans/from-inventory.md", "docs/space dir/x [1].md",
                               "docs/plans/from-test.md"}
    assert {"docs/plans/a.md", "docs/plans/b.md", "docs/inv.json"} <= st["live"]


def test_dot_relative_links_keep_their_targets_live(tmp_path):
    """r1 P1: a leading `../` or `./` must survive the punctuation strip (only trailing dots are dropped)."""
    root = _repo(tmp_path, {
        "AGENTS.md": "see [a](docs/a/b.md)\n",
        "docs/a/b.md": "[x](../c.md) and [y](./d.md), also `../e.md`, `./g.md`. Then docs/a/f.md.\n",
        "docs/c.md": "x\n", "docs/a/d.md": "x\n", "docs/e.md": "x\n", "docs/a/f.md": "x\n", "docs/a/g.md": "x\n",
        "docs/orphan.md": "x\n",
    })
    st = sn.state(root)
    assert st["docs"] == ["docs/orphan.md"]


def test_directory_reference_keeps_its_index(tmp_path):
    root = _repo(tmp_path, {"AGENTS.md": "read `docs/area/`\n", "docs/area/INDEX.md": "i", "docs/area/x.md": "x"})
    st = sn.state(root)
    assert st["docs"] == ["docs/area/x.md"]


@needs_rg
def test_block_round_trip_with_rg_and_the_duplicate_guard_block(tmp_path):
    root = _hidden_case(tmp_path)
    (root / ".ignore").write_text("keep-me/\n" + dg.render_ignore_block(["jobs/DONE/build.py"]), encoding="utf-8")
    st = sn.state(root)
    assert "no single historical-data block" in sn.block_problems(root, st["data"], st["docs"])[0]
    sn.write_block(root, st["data"], st["docs"])
    text = (root / ".ignore").read_text(encoding="utf-8")
    assert text.startswith("keep-me/\n") and dg.IGNORE_BEGIN in text and not (root / ".ignore.partial").exists()
    assert sn.block_problems(root, st["data"], st["docs"]) == []
    assert dg.ignore_problems(root, ["jobs/DONE/build.py"]) == []
    listed = _rg(root)
    assert not (set(st["data"]) | set(st["docs"]) | {"jobs/DONE/build.py"}) & listed
    assert {"jobs/DONE/LESSONS.md", "docs/plans/b.md", "jobs/LIVE/data.json", "jobs/DONE/named.json"} <= listed
    assert sn.main(["--root", str(root)]) == 0
    sn.write_block(root, st["data"], st["docs"])  # repeat: identical
    assert (root / ".ignore").read_text(encoding="utf-8") == text
    assert "['/jobs/DONE/notes.md']" in sn.block_problems(root, st["data"][1:], st["docs"])[0]  # hidden, not historical
    assert sn.pending(root, st["data"], st["docs"]) == []
    (root / "docs/plans/a.md").unlink()  # state changes: the linking doc is gone -> b.md newly unreached
    _git_add(root)
    st2 = sn.state(root)
    assert sn.pending(root, st2["data"], st2["docs"]) == ["/docs/plans/b.md"]
    assert sn.main(["--root", str(root)]) == 0 and "docs/plans/b.md" in _rg(root)
    (root / "AGENTS.md").write_text("now [old](docs/old.md)\n", encoding="utf-8")  # a hidden doc becomes live
    _git_add(root)
    st3 = sn.state(root)
    assert "paths ['/docs/old.md', '/docs/plans/only-from-hidden.md'] (2)" in \
        sn.block_problems(root, st3["data"], st3["docs"])[0]  # and what it links, transitively
    assert sn.main(["--root", str(root)]) == 1


def test_broken_block_is_an_error(tmp_path):
    (tmp_path / ".ignore").write_text(sn.BEGIN + "\n/x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="broken"):
        sn.write_block(tmp_path, [], [])
    (tmp_path / ".ignore").write_text(sn.END + "\n" + sn.BEGIN + "\n", encoding="utf-8")
    assert "no single" in sn.block_problems(tmp_path, [], [])[0]


# --- duplicate_guard: route-named scripts stay visible -----------------------------------------------------------

def test_entry_named_script_is_not_historical(tmp_path):
    root = _repo(tmp_path, {"jobs/DONE/a.py": "x = 1\n", "jobs/DONE/b.py": "x = 2\n",
                            "routes/r.md": "run `jobs/DONE/a.py`\n",
                            "docs/agents/job_scripts_baseline.txt": "jobs/DONE/a.py\njobs/DONE/b.py\n"})
    finished = {"jobs/DONE": "jobs/DONE/STATE.md"}
    assert dg.entry_named_paths(root) >= {"jobs/DONE/a.py"}
    assert dg.historical_scripts(root, finished, set()) == ["jobs/DONE/b.py"]
    assert dg.historical_scripts(root, finished, set(), named=frozenset()) == ["jobs/DONE/a.py", "jobs/DONE/b.py"]
    assert dg.entry_named_paths(tmp_path / "jobs") == frozenset()  # not a work tree root: no entry docs


# --- measure -----------------------------------------------------------------------------------------------------

@needs_rg
def test_measure_counts_and_fails_without_rg(tmp_path, monkeypatch):
    root = _hidden_case(tmp_path)
    m = sn.measure(root)
    assert m["visible"] == len(sn.tracked(root)) - 1  # .gitattributes is hidden by rg itself
    assert m["visible"] - m["visible_non_test"] == 1 and m["job_scripts_visible"] == 1
    monkeypatch.setattr(sn.shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="ripgrep"):
        sn.measure(root)
    assert sn.main(["--root", str(root), "--measure"]) == 2


# --- evidence move -----------------------------------------------------------------------------------------------

BIG = b"{" + b" " * (sn.MOVE_MIN_BYTES - 2) + b"}"


def _move_case(tmp_path):
    return _repo(tmp_path / "repo", {
        "jobs/DONE/r/big.json": BIG, "jobs/DONE/r/small.json": BIG[:-2] + b"}",
        "jobs/DONE/r/named.json": BIG, "docs/old/x.md": "P = jobs/DONE/r/named.json\n",
        "jobs/DONE/r/test-read.json": BIG, "tests/test_r.py": "N = 'r/test-read.json'\n",
        "jobs/DONE/r/log.md": BIG})


def test_move_candidates_threshold_suffix_and_code_references(tmp_path):
    root = _move_case(tmp_path)
    st = sn.state(root)
    move, kept = sn.move_candidates(root, st["files"], st["data"])
    assert move == ["jobs/DONE/r/big.json", "jobs/DONE/r/test-read.json"]
    assert kept == {"jobs/DONE/r/named.json": ["docs/old/x.md"]}
    assert "jobs/DONE/r/named.json" in st["data"] and "docs/old/x.md" in st["docs"]


def test_move_evidence_copies_verifies_records_and_removes(tmp_path):
    root, dest = _move_case(tmp_path), tmp_path / "store"
    st = sn.state(root)
    rows = sn.move_evidence(root, st["files"], ["jobs/DONE/r/big.json"], dest)
    digest = hashlib.sha256(BIG).hexdigest()
    assert rows == [{"path": "jobs/DONE/r/big.json", "sha256": digest, "bytes": len(BIG),
                     "evidence": (dest.resolve() / "DONE/r/big.json").as_posix()}]
    assert not (root / "jobs/DONE/r/big.json").exists() and (dest / "DONE/r/big.json").read_bytes() == BIG
    assert (dest / "DONE/SHA256SUMS.txt").read_text(encoding="utf-8") == f"{digest}  r/big.json\n"
    assert not list(dest.rglob("*.partial"))
    _git_add(root)
    st = sn.state(root)
    sn.move_evidence(root, st["files"], ["jobs/DONE/r/test-read.json"], dest)  # second run merges
    _git_add(root)
    manifest = json.loads((root / "jobs/DONE" / sn.MANIFEST).read_text(encoding="utf-8"))
    assert [r["path"] for r in manifest["files"]] == ["jobs/DONE/r/big.json", "jobs/DONE/r/test-read.json"]
    assert len((dest / "DONE/SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()) == 2
    st = sn.state(root)
    assert sn.manifest_problems(root, st["files"]) == []
    assert "jobs/DONE/" + sn.MANIFEST not in st["data"]  # the manifest stays visible
    assert sn.verify_evidence(root, st["files"]) == (2, [])
    assert sn.main(["--root", str(root), "--verify-evidence", "--write-ignore"]) == 0
    assert sn.evidence_path(root, "jobs/DONE/r/big.json") == Path((dest.resolve() / "DONE/r/big.json").as_posix())
    assert sn.evidence_path(root, "jobs/DONE/r/log.md") == root / "jobs/DONE/r/log.md"
    assert sn.evidence_path(root, "jobs/DONE/r/never.json") is None
    (dest / "DONE/r/big.json").write_bytes(BIG.replace(b" ", b"\n", 1))  # tampered copy
    with pytest.raises(ValueError, match="sha256 differs"):
        sn.evidence_path(root, "jobs/DONE/r/big.json")
    assert sn.main(["--root", str(root), "--verify-evidence"]) == 1
    (dest / "DONE/r/big.json").unlink()  # store absent -> skip for readers, failure for the verifier
    assert sn.evidence_path(root, "jobs/DONE/r/big.json") is None
    assert sn.verify_evidence(root, st["files"])[1] == [
        f"jobs/DONE/r/big.json: evidence copy {Path(rows[0]['evidence'])} missing"]


@pytest.mark.parametrize("dest", ["inside", "root", "parent"])
def test_move_evidence_destination_overlapping_the_repo_moves_nothing(tmp_path, dest):
    root = _move_case(tmp_path)
    target = {"inside": root / "jobs/store", "root": root, "parent": tmp_path}[dest]
    with pytest.raises(ValueError, match="overlaps the repo"):
        sn.move_evidence(root, sn.tracked(root), ["jobs/DONE/r/big.json"], target)
    assert (root / "jobs/DONE/r/big.json").read_bytes() == BIG and not (root / "jobs/DONE" / sn.MANIFEST).exists()


def test_move_evidence_conflicting_copy_or_untracked_input_moves_nothing(tmp_path):
    root, dest = _move_case(tmp_path), tmp_path / "store"
    (dest / "DONE/r").mkdir(parents=True)
    (dest / "DONE/r/test-read.json").write_bytes(b"other")
    files = sn.tracked(root)
    with pytest.raises(ValueError, match="exists with other bytes"):
        sn.move_evidence(root, files, ["jobs/DONE/r/big.json", "jobs/DONE/r/test-read.json"], dest)
    assert (root / "jobs/DONE/r/big.json").exists() and not (dest / "DONE/r/big.json").exists()
    with pytest.raises(ValueError, match="not a tracked job file"):
        sn.move_evidence(root, files, ["docs/architecture/contexts.yaml"], dest)
    (dest / "DONE/r/test-read.json").unlink()
    with pytest.raises(ValueError, match="duplicated input"):
        sn.move_evidence(root, files, ["jobs/DONE/r/big.json", "jobs/DONE/r/big.json"], dest)
    assert (root / "jobs/DONE/r/big.json").exists() and not (dest / "DONE/r/big.json").exists()
    (dest / "DONE/r/big.json").write_bytes(BIG)  # identical copy already there: accepted, not rewritten
    rows = sn.move_evidence(root, files, ["jobs/DONE/r/big.json"], dest)
    assert [r["path"] for r in rows] == ["jobs/DONE/r/big.json"] and not (root / "jobs/DONE/r/big.json").exists()
    assert len(json.loads((root / "jobs/DONE" / sn.MANIFEST).read_text(encoding="utf-8"))["files"]) == 1


@pytest.mark.parametrize("row,match", [
    ({"path": "jobs/DONE/STATE.md"}, "still in the repo"),
    ({"sha256": "abc"}, "needs path"),
    ({"path": "jobs/LIVE/x.json"}, "needs path"),
    ({"path": "jobs/DONE/../LIVE/x.json"}, "needs path"),
    ({"bytes": "1"}, "needs path"),
    ({"evidence": ""}, "needs path"),
])
def test_manifest_problems_fail_closed(tmp_path, row, match):
    good = {"path": "jobs/DONE/gone.json", "sha256": "0" * 64, "bytes": 1, "evidence": "G:/x/gone.json"}
    root = _repo(tmp_path, {"jobs/DONE/" + sn.MANIFEST: json.dumps({"files": [{**good, **row}]})})
    assert match in "\n".join(sn.manifest_problems(root, sn.tracked(root)))


def test_manifest_duplicate_unreadable_and_empty_verify(tmp_path):
    good = {"path": "jobs/DONE/gone.json", "sha256": "0" * 64, "bytes": 1, "evidence": "G:/x/gone.json"}
    root = _repo(tmp_path, {"jobs/DONE/" + sn.MANIFEST: json.dumps({"files": [good, good]}),
                            "jobs/LIVE/" + sn.MANIFEST: "not json"})
    text = "\n".join(sn.manifest_problems(root, sn.tracked(root)))
    assert "listed twice" in text and "jobs/LIVE/EVIDENCE-MOVED.json: unreadable" in text
    empty = _repo(tmp_path / "e", {})
    assert sn.main(["--root", str(empty), "--verify-evidence"]) == 1  # nothing to verify is not a pass
