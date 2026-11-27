"""#2024: call_chains.edges resolves static repo-root-anchored `Path` joins (subprocess / importlib callers).

Pattern: n/a | new-case: regression tests for repo-root Path join edges in call_chains.

Acceptance table (PR body) -> tests here:
- the three real Ground research callers reach jobs/VATUTINO-SITE/build_ground.py  -> test_repo_three_ground_callers
- fixture forms: parents[n], parent, HERE.parents, joinpath, str(), Path(a, b), `..` inside root  -> test_resolves_*
- prose, unrelated basename, CWD-relative literal, argument, reassigned name, env value  -> test_no_edge_*
- outside-root (parents too high, `..` past root), missing file, absolute string  -> test_no_edge_*
- existing literal and import edges are kept  -> test_literal_and_import_edges_kept
- brute-force: parents[k] / rest gives an edge iff it lands on the target inside the root  -> test_probe_parents_grid
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import call_chains  # noqa: E402

TARGET = "jobs/SITE/build.py"
CALLER = "tools/methods/ground/caller.py"


def _repo(tmp_path, caller_src, extra=None):
    files = {TARGET: "x = 1\n", "tools/methods/ground/other.py": "y = 1\n", CALLER: caller_src}
    files.update(extra or {})
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return call_chains.edges(tmp_path, CALLER)


def test_repo_three_ground_callers():
    for caller in ("build_variant", "builder_methods_only", "ground_variants"):
        rel = f"tools/methods/ground/{caller}.py"
        assert "jobs/VATUTINO-SITE/build_ground.py" in call_chains.edges(ROOT, rel), rel


@pytest.mark.parametrize("src", [
    # builder_methods_only / ground_variants form: importlib from a module-level name
    'import importlib.util\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parents[3]\n'
    'B = ROOT / "jobs" / "SITE" / "build.py"\n'
    'spec = importlib.util.spec_from_file_location("m", B)\n',
    # build_variant form: HERE.parents[2] and a join inside a function, passed to subprocess
    'import subprocess, sys\nfrom pathlib import Path\nHERE = Path(__file__).resolve().parent\nROOT = HERE.parents[2]\n'
    'def run(v):\n    s = ROOT / "jobs" / "SITE" / "build.py" if v else HERE / "other.py"\n'
    '    subprocess.run([sys.executable, str(s)])\n',
    'from pathlib import Path\nP = Path(__file__).parent.parent.parent.parent.joinpath("jobs", "SITE/build.py")\n',
    'from pathlib import Path\nP = str(Path(Path(__file__).resolve().parents[3], "jobs", "SITE", "build.py"))\n',
    'from pathlib import Path\nJOB = Path(__file__).absolute().parents[3] / "jobs/SITE"\nP = JOB / "build.py"\n',
    'from pathlib import Path\nP = Path(__file__).resolve().parent / ".." / ".." / ".." / "jobs" / "SITE" / "build.py"\n',
    'from pathlib import Path\nNAME = "build.py"\nP = Path(__file__).resolve().parents[3] / "jobs" / "SITE" / NAME\n',
])
def test_resolves_static_repo_root_joins(tmp_path, src):
    assert TARGET in _repo(tmp_path, src)


@pytest.mark.parametrize("src", [
    # prose: a docstring / message naming the file is not a call
    '"""Runs jobs/SITE/build.py unchanged in a fresh process."""\nprint("see build.py in jobs/SITE")\n',
    # unrelated basename: same file name in another folder (sibling of the caller)
    'from pathlib import Path\nP = Path(__file__).resolve().parent / "build.py"\n',
    # CWD-relative literal: not anchored to the repo root
    'from pathlib import Path\nP = Path("jobs") / "SITE" / "build.py"\n',
    # argument / environment / unknown name
    'from pathlib import Path\ndef f(root):\n    return root / "jobs" / "SITE" / "build.py"\n',
    'import os\nfrom pathlib import Path\nP = Path(os.environ["ROOT"]) / "jobs" / "SITE" / "build.py"\n',
    'from pathlib import Path\nP = UNKNOWN / "jobs" / "SITE" / "build.py"\n',
    # reassigned name: not static
    'from pathlib import Path\nROOT = Path(__file__).resolve().parents[3]\nROOT = Path("/elsewhere")\n'
    'P = ROOT / "jobs" / "SITE" / "build.py"\n',
    'from pathlib import Path\nROOT = Path(__file__).resolve().parents[3]\ndef g():\n    ROOT = 1\n'
    'P = ROOT / "jobs" / "SITE" / "build.py"\n',
    # outside the root: parents too high, `..` past the root
    'from pathlib import Path\nP = Path(__file__).resolve().parents[4] / "jobs" / "SITE" / "build.py"\n',
    'from pathlib import Path\nP = Path(__file__).resolve().parents[3] / ".." / "jobs" / "SITE" / "build.py"\n',
    # absolute string replaces the anchor; dynamic index; f-string
    'from pathlib import Path\nP = Path(__file__).resolve().parents[3] / "/jobs/SITE/build.py"\n',
    'from pathlib import Path\nI = 3\nP = Path(__file__).resolve().parents[I] / "jobs" / "SITE" / "build.py"\n',
    'from pathlib import Path\nS = "SITE"\nP = Path(__file__).resolve().parents[3] / "jobs" / f"{S}" / "build.py"\n',
    # missing target file
    'from pathlib import Path\nP = Path(__file__).resolve().parents[3] / "jobs" / "SITE" / "gone.py"\n',
])
def test_no_edge_for_prose_unrelated_unresolved_or_outside(tmp_path, src):
    assert TARGET not in _repo(tmp_path, src)
    assert all(not e.endswith("gone.py") for e in _repo(tmp_path, src))


def test_literal_and_import_edges_kept(tmp_path):
    src = ('import other\nfrom pathlib import Path\nQ = "jobs/SITE/build.py"\n'
           'R = Path(__file__).resolve().parents[3] / "jobs" / "SITE" / "build.py"\n')
    assert _repo(tmp_path, src) == sorted({TARGET, "tools/methods/ground/other.py"})


def test_probe_parents_grid(tmp_path):
    """Brute force: every parents[k] (k 0..6) x every tail; an edge iff the folded path is the target in the root."""
    tails = [("jobs", "SITE", "build.py"), ("lib", "helper.py"), ("tools", "lib", "helper.py"),
             ("..", "jobs", "SITE", "build.py"), ("..", "lib", "helper.py"), ("SITE", "build.py")]
    caller = Path(CALLER)
    checked = 0
    for k in range(7):
        for tail in tails:
            joined = " / ".join(f'"{p}"' for p in tail)
            src = f'from pathlib import Path\nP = Path(__file__).resolve().parents[{k}] / {joined}\n'
            got = set(_repo(tmp_path, src, {"tools/lib/helper.py": "z = 1\n"}))
            # independent oracle: string arithmetic on the caller path
            base = list(caller.parts[:-(k + 1)]) if k + 1 <= len(caller.parts) else None
            want = set()
            if base is not None:
                parts, ok = list(base), True
                for p in tail:
                    if p == "..":
                        ok = ok and bool(parts)
                        parts = parts[:-1]
                    else:
                        parts.append(p)
                cand = "/".join(parts)
                if ok and (tmp_path / cand).is_file() and cand != CALLER:
                    want.add(cand)
            assert got == want, (k, tail, got, want)
            checked += 1
    assert checked == 42
