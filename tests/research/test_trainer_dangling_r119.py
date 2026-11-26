"""#119 OBSERVE harness: dangling route references in a synthetic practice tree (no git, no stored runs)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("r119", ROOT / "docs/research/trainer_dangling_r119/measure.py")
assert spec is not None and spec.loader is not None
r119 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r119)

HEAD_FILES = ["routes/a.md", "tools/x/live.py", "jobs/J/hooks/hidden_tool.py", "jobs/J/README.md",
              "jobs/K/hooks/dup.py", "tools/y/dup.py"]


def _tree(tmp_path, route_text, other_text=""):
    for rel in ("routes/a.md", "tools/x/live.py", "tools/y/dup.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x\n", encoding="utf-8")
    (tmp_path / "routes/a.md").write_text(route_text, encoding="utf-8")
    (tmp_path / "docs/research").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/research/n.md").write_text(other_text, encoding="utf-8")
    by_base = {}
    for f in HEAD_FILES:
        by_base.setdefault(f.rsplit("/", 1)[-1], []).append(f)
    r119.head_files.__defaults__[0]["fake"] = (set(HEAD_FILES), by_base)
    return r119.m119(tmp_path, "fake")


def test_counts_hidden_full_path_backslash_and_bare_tool(tmp_path):
    r = _tree(tmp_path, "run `jobs/J/README.md`; then jobs\\J\\README.md; and hidden_tool.py\n")
    assert r["dangling"] == ["jobs/J/README.md", "jobs/J/hooks/hidden_tool.py"]
    assert (r["M119"], r["M119_tools"]) == (2, 1)


def test_ignores_existing_stale_partial_and_non_route(tmp_path):
    r = _tree(tmp_path, "`tools/x/live.py` `tools/none/gone.py` dup.py README.md\n",
              other_text="run `jobs/J/README.md`\n")
    assert r["M119"] == 0  # dup.py has a live copy; README.md bare is not a tool; n.md is not route-critical
    assert r["stale"] == 1


def test_suffix_name_resolves_against_head_paths(tmp_path):
    r = _tree(tmp_path, "see hooks/hidden_tool.py and hooks/dup.py and y/dup.py\n")
    # hooks/dup.py matches only jobs/K/hooks/dup.py (absent); y/dup.py matches the live tools/y/dup.py
    assert r["dangling"] == ["jobs/J/hooks/hidden_tool.py", "jobs/K/hooks/dup.py"]
