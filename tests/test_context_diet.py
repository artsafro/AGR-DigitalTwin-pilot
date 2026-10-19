"""Kernel C7 context diet: per-card reading list, generated project state, base context < 10k tokens."""
import importlib.util
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "state" / "project_state.py"
BEFORE = ROOT / "tests" / "fixtures" / "context_diet"
CHAR_LIMIT = 40_000  # exactly this many characters fails (tokenizer-free proxy: chars / 4 = 10k)
LINK = __import__("re").compile(r"(?<![A-Za-z0-9_])((?:docs|tools)/[A-Za-z0-9_./-]+\.md)")
ATX = __import__("re").compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")


def _load():
    assert SCRIPT.is_file(), "tools/state/project_state.py is missing"
    spec = importlib.util.spec_from_file_location("project_state", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _raw(path):
    return path.open(encoding="utf-8", newline="").read()


def _headings(text):
    found = []
    for line in text.splitlines():
        match = ATX.match(line)
        if match and (match.group(2) or "").strip():
            found.append((match.group(2) or "").strip())
    return found


def _bullets(text):
    items = []
    current = None
    for line in text.splitlines():
        if line.startswith("- "):
            if current:
                items.append(current)
            current = line
        elif current is not None and line.startswith("  "):
            current += "\n" + line
        else:
            if current:
                items.append(current)
            current = None
    if current:
        items.append(current)
    return items


def _closure_text_and_headings():
    texts = []
    headings = []
    seen = set()
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        texts.append(text)
        headings.extend(_headings(text))
        for link in LINK.findall(text):
            target = (ROOT / link).resolve()
            if target in seen or not target.is_file():
                continue
            seen.add(target)
            linked = target.read_text(encoding="utf-8")
            texts.append(linked)
            headings.extend(_headings(linked))
    return "\n".join(texts), headings


def _largest_area():
    areas = list((ROOT / "docs" / "domain" / "areas").glob("*.md"))
    assert areas
    return max(areas, key=lambda path: len(_raw(path)))


def _run(args, env=None):
    assert SCRIPT.is_file(), "tools/state/project_state.py is missing"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return completed.returncode, completed.stdout, completed.stderr


def _stub_env(bin_dir):
    return {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")}


def _write_stubs(bin_dir, merges, opens, git_code=0, gh_code=0):
    bin_dir.mkdir(parents=True)
    if os.name != "nt":
        import shlex
        for name, filename, code in (("git", "merges.txt", git_code), ("gh", "open.json", gh_code)):
            program = ("import sys; from pathlib import Path; "
                       f"sys.stdout.buffer.write(Path({str(bin_dir / filename)!r}).read_bytes()); "
                       f"sys.exit({code})")
            stub = bin_dir / name
            stub.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -c " + shlex.quote(program) + "\n", encoding="utf-8")
            stub.chmod(0o755)
    (bin_dir / "merges.txt").write_bytes(merges.encode("utf-8"))
    (bin_dir / "open.json").write_bytes(opens.encode("utf-8"))
    (bin_dir / "git.cmd").write_text(
        "@echo off\r\n"
        "if /I \"%~1\"==\"log\" (\r\n"
        "  type \"%~dp0merges.txt\"\r\n"
        f"  exit /b {git_code}\r\n"
        ")\r\n"
        "echo unsupported 1>&2\r\n"
        "exit /b 2\r\n",
        encoding="ascii")
    (bin_dir / "gh.cmd").write_text(
        "@echo off\r\n"
        "if /I \"%~1\"==\"pr\" (\r\n"
        "  type \"%~dp0open.json\"\r\n"
        f"  exit /b {gh_code}\r\n"
        ")\r\n"
        "echo unsupported 1>&2\r\n"
        "exit /b 2\r\n",
        encoding="ascii")


def _fixture(tmp_path, merges, opens, git_code=0, gh_code=0):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / ".git").write_text("gitdir: synthetic\n", encoding="utf-8", newline="\n")
    _write_stubs(tmp_path / "bin", merges, opens, git_code, gh_code)
    return repo


def _generate(tmp_path, repo, output, max_merges=12, max_open=12):
    return _run(
        ["--repo", str(repo), "--output", str(output),
         "--max-merges", str(max_merges), "--max-open", str(max_open)],
        env=_stub_env(tmp_path / "bin"))


def test_agents_reading_list_is_shorter_and_names_the_three_reads():
    before = _raw(BEFORE / "AGENTS.md.before")
    after = _raw(ROOT / "AGENTS.md")
    assert len(after) < len(before)
    assert "docs/domain/areas/<area>.md" in after
    assert "read on demand" in after.lower()
    assert "the card" in after.lower()
    assert "author receipts" in after.lower()
    assert "docs/agents/WORKFLOW.md#before-requesting-review-author" in after


def test_rule_headings_and_bullets_survive_in_the_file_or_a_linked_doc():
    before_agents = (BEFORE / "AGENTS.md.before").read_text(encoding="utf-8")
    before_claude = (BEFORE / "CLAUDE.md.before").read_text(encoding="utf-8")
    required_headings = _headings(before_agents) + _headings(before_claude)
    required_bullets = _bullets(before_agents) + _bullets(before_claude)
    assert required_headings and required_bullets
    text, headings = _closure_text_and_headings()
    missing_headings = [item for item in required_headings if item not in headings]
    # C7 intentionally replaces manual section edits with generation; retain every
    # safety qualifier of that rule rather than demanding the obsolete operation.
    state_rule = next(item for item in required_bullets if item.startswith("- Update `docs/PROJECT_STATE.md`"))
    required_bullets.remove(state_rule)
    flat = " ".join(text.split())
    for qualifier in ("only on `main` after a merge", "≤ 80 lines, fixed sections",
                      "in task branches report state changes in the final summary"):
        assert qualifier in flat
    missing_bullets = [item for item in required_bullets if item not in text]
    ids = sorted(set(__import__("re").findall(r"\bD\d+\b", before_agents + before_claude)))
    assert all(identifier in text for identifier in ids)
    print(f"Before headings: {required_headings}; ids: {ids}")
    print(f"After headings: {[h for h in required_headings if h in headings]}; ids: {ids}")
    print(f"Preserved: {len(required_bullets)} verbatim bullets + generated-state rule safety qualifiers")
    assert missing_headings == []
    assert missing_bullets == []


def test_live_base_context_is_under_the_character_budget():
    area = _largest_area()
    code, out, err = _run([
        "--budget-files", str(ROOT / "AGENTS.md"), str(ROOT / "CLAUDE.md"), str(area)])
    assert code == 0, err
    total = len(_raw(ROOT / "AGENTS.md")) + len(_raw(ROOT / "CLAUDE.md")) + len(_raw(area))
    assert total < CHAR_LIMIT
    assert str(total) in out


def test_budget_threshold_empty_partial_and_nonfinite_fail(tmp_path):
    assert SCRIPT.is_file()
    module = _load()
    totals = [0, -1, 1, 39999, 40000, 40001, float("nan"), float("inf"), float("-inf")]
    for total in totals:
        if not math.isfinite(total) or total <= 0 or total >= CHAR_LIMIT:
            with pytest.raises(module.FailClosed):
                module.check_char_total(total)
        else:
            assert module.check_char_total(total) == total

    for token in ("", "nan", "NaN", "inf", "+inf", "-inf", "Infinity", "-Infinity", "1e309", "40000", "0", "-3", "1.5", "none"):
        code, _out, err = _run(["--budget-chars", token])
        assert code != 0, token
        assert err.strip()
    code, out, err = _run(["--budget-chars", "39999"])
    assert code == 0, err
    assert "39999" in out

    for total, expect in ((39999, 0), (40000, 1), (40001, 1)):
        paths = []
        sizes = (1, 1, total - 2)
        for index, size in enumerate(sizes):
            path = tmp_path / f"b{total}-{index}.md"
            path.write_bytes(b"x" * size)
            paths.append(path)
        code, _out, err = _run(["--budget-files", *(str(path) for path in paths), "--output", str(tmp_path / "nope.md")])
        assert code == expect, (total, err)
        assert not (tmp_path / "nope.md").exists()

    empty = tmp_path / "empty.md"
    blank = tmp_path / "blank.md"
    good = tmp_path / "good.md"
    empty.write_bytes(b"")
    blank.write_bytes(b" \r\n\t")
    good.write_bytes(b"# Area\n")
    for bad in (empty, blank):
        code, _out, err = _run(["--budget-files", str(good), str(good), str(bad)])
        assert code != 0
        assert "empty" in err
    missing = tmp_path / "missing.md"
    code, _out, err = _run(["--budget-files", str(good), str(good), str(missing)])
    assert code != 0
    assert "partial" in err
    code, _out, _err = _run(["--budget-chars", "nan", "--output", str(good)])
    assert code != 0
    assert _raw(good) == "# Area\n"


def test_generated_char_totals_around_the_threshold():
    module = _load()
    rng = random.Random(333)
    samples = {0, 1, CHAR_LIMIT - 1, CHAR_LIMIT, CHAR_LIMIT + 1}
    samples.update(rng.randrange(1, CHAR_LIMIT) for _ in range(40))
    for total in samples:
        if total <= 0 or total >= CHAR_LIMIT:
            with pytest.raises(module.FailClosed):
                module.check_char_total(total)
        else:
            assert module.check_char_total(total) == total
    for bad in (float("nan"), float("inf"), float("-inf"), True, None, "40000", "nan"):
        with pytest.raises(module.FailClosed):
            module.check_char_total(bad)


def test_fixture_repo_generation_is_idempotent_and_declares_itself(tmp_path):
    merges = "\n".join(f"{index:07x}\tAdd merge {index}" for index in range(1, 4)) + "\n"
    opens = (
        '[{"number": 12, "title": "Kernel diet", "headRefName": "task/diet", "isDraft": false},'
        '{"number": 9, "title": "Windows", "headRefName": "task/windows", "isDraft": true}]\n'
    )
    repo = _fixture(tmp_path, merges, opens)
    output = repo / "docs" / "PROJECT_STATE.md"
    code, _out, err = _generate(tmp_path, repo, output)
    assert code == 0, err
    first = output.read_bytes()
    text = first.decode("utf-8")
    assert "Generated by" in text
    assert "python tools/state/project_state.py" in text
    assert text.count("## Goal") == 1
    assert text.count("## In production") == 1
    assert text.count("## Harness") == 1
    assert text.count("## Next step") == 1
    assert text.count("## Links") == 1
    assert "#12 Kernel diet" in text
    assert "draft" in text
    assert len(text.splitlines()) < 80
    code, _out, err = _generate(tmp_path, repo, output)
    assert code == 0, err
    assert output.read_bytes() == first


def test_open_pr_order_does_not_change_output(tmp_path):
    module = _load()
    merges = [("abc1234", "Merge pull request #1")]
    opens = [
        {"number": n, "title": f"PR {n}", "headRefName": f"task/{n}", "isDraft": False}
        for n in (9, 2, 5)
    ]
    assert module.render(merges, opens) == module.render(merges, list(reversed(opens)))


def test_source_failure_then_recovery(tmp_path):
    repo = _fixture(tmp_path, "abc1234\tMerge pull request #1\n", "[]\n")
    output = repo / "docs" / "PROJECT_STATE.md"
    assert _generate(tmp_path, repo, output)[0] == 0
    before = output.read_bytes()
    source = tmp_path / "bin" / "open.json"
    source.write_text("{", encoding="utf-8")
    assert _generate(tmp_path, repo, output)[0] != 0
    assert output.read_bytes() == before
    source.write_text("[]\n", encoding="utf-8")
    assert _generate(tmp_path, repo, output)[0] == 0
    assert output.read_bytes() == before


def test_real_git_fixture_repo_generation(tmp_path):
    repo = tmp_path / "real-repo"
    repo.mkdir()

    def git(*args):
        completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        return completed.stdout.strip()

    git("init", "-b", "main")
    git("config", "user.name", "Synthetic fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("commit", "--allow-empty", "-m", "Synthetic root")
    git("checkout", "-b", "feature")
    git("commit", "--allow-empty", "-m", "Synthetic feature")
    git("checkout", "-b", "nested")
    git("commit", "--allow-empty", "-m", "Synthetic nested feature")
    git("checkout", "feature")
    git("merge", "--no-ff", "nested", "-m", "Non-PR integration")
    git("checkout", "main")
    git("merge", "--no-ff", "feature", "-m", "Merge pull request #333 from fixture/feature")
    _write_stubs(tmp_path / "bin", "", "[]\n")
    (tmp_path / "bin" / "git.cmd").unlink()  # exercise actual git, only gh is synthetic
    (tmp_path / "bin" / "git").unlink(missing_ok=True)
    output = repo / "docs" / "PROJECT_STATE.md"
    assert _generate(tmp_path, repo, output)[0] == 0
    first = output.read_bytes()
    assert git("rev-parse", "--short=7", "HEAD") in first.decode("utf-8")
    assert "#333 from fixture/feature" in first.decode("utf-8")
    assert "Non-PR integration" not in first.decode("utf-8")
    assert _generate(tmp_path, repo, output)[0] == 0
    assert output.read_bytes() == first


def test_checked_in_project_state_names_the_generator():
    text = (ROOT / "docs" / "PROJECT_STATE.md").read_text(encoding="utf-8")
    assert "Generated by" in text
    assert "python tools/state/project_state.py" in text
    assert len(text.splitlines()) < 80


def test_empty_partial_unsupported_and_nonfinite_sources_write_nothing(tmp_path):
    output = tmp_path / "out" / "PROJECT_STATE.md"
    output.parent.mkdir(parents=True)
    cases = [
        ("", "[]\n", 0, 0, "empty"),
        ("no-tab-here\n", "[]\n", 0, 0, "partial"),
        ("abc1234\tSubject\n", '{"number": 1}\n', 0, 0, "partial"),
        ("abc1234\tSubject\n", "[]\n", 2, 0, "unsupported"),
        ("abc1234\tSubject\n", "[]\n", 0, 2, "unsupported"),
        ("abc1234\tNaN\n", "[]\n", 0, 0, "non-finite"),
        ("abc1234\tSubject\n",
         '[{"number": NaN, "title": "T", "headRefName": "b", "isDraft": false}]\n',
         0, 0, "non-finite"),
        ("abc1234\tSubject\n",
         '[{"number": Infinity, "title": "T", "headRefName": "b", "isDraft": false}]\n',
         0, 0, "non-finite"),
    ]
    for index, (merges, opens, git_code, gh_code, reason) in enumerate(cases):
        repo = _fixture(tmp_path / f"c{index}", merges, opens, git_code, gh_code)
        output.write_text("KEEP\n", encoding="utf-8")
        before = output.read_bytes()
        code, _out, err = _generate(tmp_path / f"c{index}", repo, output)
        assert code != 0, reason
        assert reason in err
        assert output.read_bytes() == before


def test_git_metadata_descendant_output_is_refused(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    config = repo / ".git" / "config"
    before = config.read_bytes()
    module = _load()
    with pytest.raises(module.FailClosed, match="output-is-input"):
        module.generate(repo, config, 12, 12)
    assert config.read_bytes() == before


def test_output_path_that_resolves_to_an_input_writes_nothing(tmp_path):
    merges = "abc1234\tSubject one\n"
    opens = '[{"number": 3, "title": "Keep", "headRefName": "task/a", "isDraft": false}]\n'
    repo = _fixture(tmp_path, merges, opens)
    gitdir = repo / ".git"
    before_git = gitdir.read_bytes()
    next_step = repo / "docs" / "PROJECT_STATE.next.md"
    next_step.parent.mkdir(parents=True)
    next_step.write_text("Hand next step.\n", encoding="utf-8", newline="\n")
    before_next = next_step.read_bytes()
    for output in (gitdir, repo / "docs" / ".." / ".git", next_step, repo / "docs" / ".." / "docs" / "PROJECT_STATE.next.md"):
        code, _out, err = _generate(tmp_path, repo, output)
        assert code != 0
        assert "output-is-input" in err
        assert gitdir.read_bytes() == before_git
        assert next_step.read_bytes() == before_next
        assert not (repo / "docs" / "PROJECT_STATE.md").exists()


def test_line_limit_fails_exactly_at_80_and_passes_under_it():
    module = _load()
    boundary = None
    previous = None
    for count in range(0, 90):
        merges = [(f"{index + 1:07x}", f"Subject {index}") for index in range(count)]
        opens = [] if count else [{"number": 1, "title": "Only", "headRefName": "task/a", "isDraft": False}]
        if count == 0:
            merges = [("abc1234", "Solo")]
            opens = []
        try:
            text = module.finalize(module.render(merges, opens))
            result = "pass"
            assert len(text.splitlines()) < 80
            assert text.endswith("\n")
            assert module.finalize(text) == text
        except module.FailClosed as exc:
            result = exc.reason
        if result == "threshold" and boundary is None:
            boundary = count
            break
        previous = result
    assert boundary is not None
    assert previous == "pass"
    merges = [(f"{index + 1:07x}", f"Subject {index}") for index in range(boundary)]
    with pytest.raises(module.FailClosed) as raised:
        module.finalize(module.render(merges, []))
    assert raised.value.reason == "threshold"
    under = [(f"{index + 1:07x}", f"Subject {index}") for index in range(boundary - 1)]
    kept = module.finalize(module.render(under, []))
    assert len(kept.splitlines()) == 79 or len(kept.splitlines()) < 80


def test_generated_records_fail_closed_on_corrupt_fields():
    module = _load()
    rng = random.Random(121)
    for _ in range(25):
        merges = [(f"{rng.randrange(16 ** 7):07x}", f"Subject {rng.randrange(1000)}")
                  for _ in range(rng.randint(1, 4))]
        opens = [{
            "number": rng.randint(1, 5000),
            "title": f"Title {rng.randrange(100)}",
            "headRefName": f"task/{rng.randrange(100)}",
            "isDraft": bool(rng.randrange(2)),
        }]
        text = module.finalize(module.render(merges, module.normalize_opens(opens)))
        assert module.finalize(text) == text
        for corrupt, reason in (
            ({**opens[0], "number": float("nan")}, "non-finite"),
            ({**opens[0], "number": float("inf")}, "non-finite"),
            ({**opens[0], "number": float("-inf")}, "non-finite"),
            ({**opens[0], "title": "NaN"}, "non-finite"),
            ({**opens[0], "title": "inf"}, "non-finite"),
            ({**opens[0], "title": ""}, "partial"),
            ({"number": opens[0]["number"]}, "partial"),
            ({**opens[0], "isDraft": "false"}, "partial"),
            ({**opens[0], "number": True}, "partial"),
            ({**opens[0], "number": 0}, "partial"),
        ):
            with pytest.raises(module.FailClosed) as raised:
                module.normalize_opens([corrupt])
            assert raised.value.reason == reason
        with pytest.raises(module.FailClosed) as raised:
            module.normalize_merges(["\tmissing-sha"])
        assert raised.value.reason == "partial"
        with pytest.raises(module.FailClosed) as raised:
            module.normalize_merges([])
            module.require_sources([], [])
        assert raised.value.reason == "empty"
