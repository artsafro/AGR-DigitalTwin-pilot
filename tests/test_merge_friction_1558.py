"""#1558: merge friction - generated maps keep one side (merge=ours) and are regenerated after the merge;
docs/decisions.md conflict blocks are resolved by tools/decisions_merge.py (union, HEAD wins, id order)."""
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
sys.path.insert(0, str(ROOT / "tools"))
import route_map  # noqa: E402

REGEN = ROOT / "tools" / "architecture" / "regen_after_merge.py"
DMERGE = ROOT / "tools" / "decisions_merge.py"

HEAD_ROWS = "| ID | Date | Decision | Applies to | Source |\n|---|---|---|---|---|\n"


def row(n, text="decision", date="2026-11-16"):
    return f"| D{n:03d} | {date} | {text} | `docs/x.md` | chat |\n"


def run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def git(repo, *args, check=True):
    r = run(["git", *args], cwd=repo)
    if check:
        assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r


def dmerge(path, *extra):
    return run([sys.executable, str(DMERGE), str(path), *extra])


# ---------------------------------------------------------------- generated maps: attributes + merge


def test_gitattributes_mark_exactly_the_generated_maps():
    _, _, files = route_map.render_all(ROOT)
    generated = {p.as_posix() for p in files}
    arch = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs/architecture").iterdir() if p.is_file())
    out = git(ROOT, "check-attr", "merge", "--", *arch).stdout.splitlines()
    marked = {line.split(": ")[0] for line in out if line.endswith(": merge: ours")}
    assert generated <= set(arch)
    assert marked == generated


def _make_repo(tmp_path, with_driver=True):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    shutil.copytree(ROOT / "docs/architecture", repo / "docs/architecture")
    shutil.copy2(ROOT / "docs/decisions.md", repo / "docs/decisions.md")
    shutil.copy2(ROOT / ".gitattributes", repo / ".gitattributes")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    if with_driver:
        r = run([sys.executable, str(REGEN), "--root", str(repo), "--install"])
        assert r.returncode == 0, r.stderr
    return repo


def _edit_and_regen(repo, branch, yaml_name, marker):
    git(repo, "switch", "-q", "-c", branch, "main")
    path = repo / "docs/architecture" / yaml_name
    text = path.read_text(encoding="utf-8")
    assert 'title_ru: "' in text
    path.write_text(text.replace('title_ru: "', f'title_ru: "{marker} ', 1), encoding="utf-8", newline="\n")
    assert route_map.main(["--root", str(repo)]) == 0
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", f"{branch}: edit {yaml_name} + regenerate maps")


def _two_branches(tmp_path, with_driver=True):
    repo = _make_repo(tmp_path, with_driver)
    _edit_and_regen(repo, "a", "ground-contexts.yaml", "Правка А")
    _edit_and_regen(repo, "b", "maf-contexts.yaml", "Правка Б")
    git(repo, "switch", "-q", "a")
    return repo


def _drift(repo):
    _, _, files = route_map.render_all(repo)
    return [rel.as_posix() for rel, text in files.items()
            if (repo / rel).read_bytes() != text.encode("utf-8")]


def test_two_branches_regenerating_maps_merge_without_conflict(tmp_path):
    repo = _two_branches(tmp_path)
    r = git(repo, "merge", "--no-edit", "b", check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "diff", "--name-only", "--diff-filter=U").stdout == ""
    stale = _drift(repo)
    assert stale, "the kept side must be stale before regeneration (else the test proves nothing)"
    assert route_map.main(["--root", str(repo)]) == 0
    assert _drift(repo) == []
    svg = (repo / "docs/architecture/ground-contexts.svg").read_text(encoding="utf-8")
    assert "Правка А" in svg
    assert "Правка Б" in (repo / "docs/architecture/maf-contexts.svg").read_text(encoding="utf-8")


def test_without_driver_the_same_merge_conflicts(tmp_path):
    repo = _two_branches(tmp_path, with_driver=False)
    r = git(repo, "merge", "--no-edit", "b", check=False)
    assert r.returncode != 0
    unmerged = set(git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split())
    _, _, files = route_map.render_all(repo)
    assert unmerged and unmerged <= {p.as_posix() for p in files}
    git(repo, "merge", "--abort")


def test_regen_after_merge_stops_on_a_source_conflict(tmp_path):
    repo = _make_repo(tmp_path)
    _edit_and_regen(repo, "a", "ground-contexts.yaml", "Правка А")
    _edit_and_regen(repo, "b", "ground-contexts.yaml", "Правка Б")
    git(repo, "switch", "-q", "a")
    head = git(repo, "rev-parse", "HEAD").stdout
    r = run([sys.executable, str(REGEN), "--root", str(repo), "--merge", "b", "--no-check"])
    assert r.returncode == 1
    assert "docs/architecture/ground-contexts.yaml" in r.stdout + r.stderr
    assert git(repo, "rev-parse", "HEAD").stdout == head
    git(repo, "merge", "--abort")


def _append_rows(repo, rows):
    path = repo / "docs/decisions.md"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    last = max(i for i, line in enumerate(lines) if line.startswith("| D"))
    lines[last + 1:last + 1] = rows
    path.write_text("".join(lines), encoding="utf-8", newline="\n")


def test_regen_after_merge_cli_resolves_maps_and_decisions(tmp_path):
    repo = _make_repo(tmp_path)
    _edit_and_regen(repo, "a", "ground-contexts.yaml", "Правка А")
    _append_rows(repo, [row(901, "ours row")])
    git(repo, "commit", "-q", "-am", "a: D901")
    _edit_and_regen(repo, "b", "maf-contexts.yaml", "Правка Б")
    _append_rows(repo, [row(902, "theirs row")])
    git(repo, "commit", "-q", "-am", "b: D902")
    git(repo, "switch", "-q", "a")
    r = run([sys.executable, str(REGEN), "--root", str(repo), "--merge", "b", "--no-check"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "status", "--porcelain").stdout == ""
    assert len(git(repo, "log", "-1", "--format=%P").stdout.split()) == 2
    text = (repo / "docs/decisions.md").read_text(encoding="utf-8")
    assert "<<<<<<<" not in text and text.index("| D901 |") < text.index("| D902 |")
    assert _drift(repo) == []


def test_workflow_names_both_tools():
    text = (ROOT / "docs/agents/WORKFLOW.md").read_text(encoding="utf-8")
    assert "tools/architecture/regen_after_merge.py" in text
    assert "tools/decisions_merge.py" in text


# ---------------------------------------------------------------- decisions_merge


def _conflict(ours, theirs, base=None, before=None, after="\n[a]: https://example.invalid/a\n"):
    before = before if before is not None else row(1, "first")
    mid = f"||||||| base\n{base}" if base is not None else ""
    return ("# Decision log\n\n" + HEAD_ROWS + before + "<<<<<<< HEAD\n" + ours + mid + "=======\n" + theirs
            + ">>>>>>> b\n" + after)


def _ids(text):
    return [line.split(" | ")[0][2:] for line in text.splitlines() if line.startswith("| D")]


def test_two_sided_rows_resolve_in_id_order(tmp_path):
    p = tmp_path / "decisions.md"
    p.write_text(_conflict(row(4, "ours"), row(2, "theirs") + row(3, "theirs3")), encoding="utf-8")
    r = dmerge(p)
    assert r.returncode == 0, r.stdout + r.stderr
    text = p.read_text(encoding="utf-8")
    assert "<<<<<<<" not in text and "=======" not in text and ">>>>>>>" not in text
    assert _ids(text) == ["D001", "D002", "D003", "D004"]
    assert text.endswith("\n[a]: https://example.invalid/a\n")


def test_diff3_base_section_is_ignored(tmp_path):
    p = tmp_path / "decisions.md"
    p.write_text(_conflict(row(2, "ours"), row(3, "theirs"), base=""), encoding="utf-8")
    assert dmerge(p).returncode == 0
    assert _ids(p.read_text(encoding="utf-8")) == ["D001", "D002", "D003"]


def test_same_id_collision_reported_head_wins(tmp_path):
    p = tmp_path / "decisions.md"
    p.write_text(_conflict(row(2, "ours text"), row(2, "theirs text") + row(3, "other")), encoding="utf-8")
    r = dmerge(p)
    assert r.returncode == 1
    text = p.read_text(encoding="utf-8")
    assert "ours text" in text and "theirs text" not in text and "<<<<<<<" not in text
    assert _ids(text) == ["D001", "D002", "D003"]
    assert "D002" in r.stdout and "theirs text" in r.stdout and "renumber" in r.stdout


def test_identical_rows_dedupe(tmp_path):
    p = tmp_path / "decisions.md"
    p.write_text(_conflict(row(2, "same"), row(2, "same") + row(3, "x")), encoding="utf-8")
    assert dmerge(p).returncode == 0
    assert _ids(p.read_text(encoding="utf-8")) == ["D001", "D002", "D003"]


def test_no_markers_is_noop(tmp_path):
    p = tmp_path / "decisions.md"
    data = ("# Decision log\n\n" + HEAD_ROWS + row(1) + row(2)).encode()
    p.write_bytes(data)
    assert dmerge(p).returncode == 0
    assert p.read_bytes() == data


@pytest.mark.parametrize("name,content", [
    ("empty", ""),
    ("no_table", "# Decision log\n\nno rows here\n"),
    ("unterminated", "# Decision log\n\n" + HEAD_ROWS + row(1) + "<<<<<<< HEAD\n" + row(2) + "=======\n" + row(3)),
    ("non_row_text", _conflict(row(2) + "ours prose\n", row(3) + "theirs prose\n")),
    ("row_after_prose", _conflict("prose\n" + row(2), "prose\n" + row(3))),
    ("out_of_order", _conflict(row(2), row(3), before=row(1) + row(5))),
    ("dup_outside_block", _conflict(row(2, "new"), row(3), before=row(1) + row(2, "old"))),
    ("dup_inside_one_side", _conflict(row(2, "x") + row(2, "y"), row(3))),
    ("stray_separator", "# Decision log\n\n" + HEAD_ROWS + row(1) + "=======\n"),
])
def test_fail_closed_inputs_write_nothing(tmp_path, name, content):
    p = tmp_path / "decisions.md"
    p.write_bytes(content.encode("utf-8"))
    r = dmerge(p)
    assert r.returncode == 2, (name, r.stdout, r.stderr)
    assert p.read_bytes() == content.encode("utf-8")
    assert not list(tmp_path.glob("*.partial"))


def test_missing_file_is_an_error(tmp_path):
    assert dmerge(tmp_path / "absent.md").returncode == 2


def test_foreign_partial_is_kept_and_nothing_written(tmp_path):
    p = tmp_path / "decisions.md"
    data = _conflict(row(2), row(3)).encode()
    p.write_bytes(data)
    (tmp_path / "decisions.md.partial").write_bytes(b"foreign")
    assert dmerge(p).returncode == 2
    assert p.read_bytes() == data
    assert (tmp_path / "decisions.md.partial").read_bytes() == b"foreign"


def test_regen_after_merge_stops_on_a_decision_collision(tmp_path):
    repo = _make_repo(tmp_path)
    git(repo, "switch", "-q", "-c", "a")
    _append_rows(repo, [row(901, "ours row")])
    git(repo, "commit", "-q", "-am", "a")
    git(repo, "switch", "-q", "-c", "b", "main")
    _append_rows(repo, [row(901, "theirs row")])
    git(repo, "commit", "-q", "-am", "b")
    git(repo, "switch", "-q", "a")
    head = git(repo, "rev-parse", "HEAD").stdout
    r = run([sys.executable, str(REGEN), "--root", str(repo), "--merge", "b", "--no-check"])
    assert r.returncode == 1
    assert "COLLISION D901" in r.stdout and "theirs row" in r.stdout
    assert git(repo, "rev-parse", "HEAD").stdout == head
    git(repo, "merge", "--abort")


def test_link_reference_union_and_conflict(tmp_path):
    p = tmp_path / "decisions.md"
    body = "# Decision log\n\n" + HEAD_ROWS + row(1) + "\n"
    p.write_text(body + "<<<<<<< HEAD\n[a]: https://e/a\n=======\n[b]: https://e/b\n>>>>>>> b\n", encoding="utf-8")
    assert dmerge(p).returncode == 0
    assert p.read_text(encoding="utf-8").endswith("[a]: https://e/a\n[b]: https://e/b\n")
    bad = body + "<<<<<<< HEAD\n[a]: https://e/a\n=======\n[a]: https://e/OTHER\n>>>>>>> b\n"
    p.write_text(bad, encoding="utf-8")
    assert dmerge(p).returncode == 2
    assert p.read_text(encoding="utf-8") == bad


def test_generated_probe_rows_preserved(tmp_path):
    import decisions_merge as dm
    for seed in range(300):
        rnd = random.Random(seed)
        ids = rnd.sample(range(10, 60), rnd.randint(0, 12))
        ours, theirs = {}, {}
        for n in ids:
            side = rnd.choice(["o", "t", "both_same", "both_diff"])
            if side in ("o", "both_same", "both_diff"):
                ours[n] = row(n, f"o{n}")
            if side in ("t", "both_same"):
                theirs[n] = row(n, f"o{n}")
            if side == "both_diff":
                theirs[n] = row(n, f"t{n}")
            if side == "t":
                theirs[n] = row(n, f"t{n}")
        if not ours and not theirs:
            continue
        o = "".join(ours[k] for k in rnd.sample(sorted(ours), len(ours)))
        t = "".join(theirs[k] for k in rnd.sample(sorted(theirs), len(theirs)))
        text, collisions = dm.resolve_text(_conflict(o, t, before=row(1)))
        got = _ids(text)
        assert got == sorted(set(got)) and len(got) == len(set(got)), seed
        expect = {1} | set(ours) | set(theirs)
        assert got == [f"D{n:03d}" for n in sorted(expect)], seed
        for n, line in ours.items():
            assert line in text, seed
        reported = {c.id for c in collisions}
        assert reported == {n for n in theirs if n in ours and theirs[n] != ours[n]}, seed
        for n in set(theirs) - set(ours):
            assert theirs[n] in text, seed
