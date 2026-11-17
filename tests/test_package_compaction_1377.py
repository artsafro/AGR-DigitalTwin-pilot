"""#1377 compaction step 2: one owner of delivery packaging and the delivery-zip guard tightened to it.

Owner: adapters/max/agr_tools/package_core.py (`_write_zip`, #1361), the one ZIP writer behind
`agr package-npm` / `agr package-vpm` and the AGR Tools MZP. The rule now guards jobs/ + tools/ + src/; every
delivery-zip allowlist row names why it stays (`ru`): historical deliveries of finished jobs are never rewritten,
and non-delivery archives (MZP, benchmark, checker research, dev bundle) are not packages. Acceptance table: PR body.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as guard  # noqa: E402
import mini_yaml  # noqa: E402
import route_map  # noqa: E402

OWNER = "adapters/max/agr_tools/package_core.py"
FACADES = ["tools/derive/package_npm.py", "tools/derive/package_vpm.py"]
VPM_PACKAGERS = ["jobs/KPP1/scripts/package_vpm.py", "jobs/PSU275/scripts/package_vpm.py",
                 "jobs/TEC26-OKS/scripts/package_vpm.py"] + [
    f"jobs/elv-tc-vpm/scripts/package_vpm_v00{i}.py" for i in range(1, 7)]
ZIP_W = "import zipfile\nzipfile.ZipFile(p, 'w')\n"


def _contexts():
    return route_map.load_context_maps(ROOT)["contexts"]


def _zip_rows():
    ctxs = _contexts()
    return [d for c in ctxs["contexts"] + [ctxs["shared_kernel"]] for d in c.get("duplicates", [])
            if d.get("rule") == "delivery-zip"]


def _root(tmp_path, files, contexts="contexts:\n  - id: x\n"):
    for top in ("jobs", "tools", "src"):
        (tmp_path / top).mkdir(exist_ok=True)
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    ctx = tmp_path / "contexts.yaml"
    ctx.write_text(contexts, encoding="utf-8")
    return ["--root", str(tmp_path), "--contexts", str(ctx), "--copies-only"]


def _row(at, ru=None, rule="delivery-zip"):
    text = f"contexts:\n  - id: x\n    duplicates:\n      - at: \"{at}\"\n        rule: {rule}\n        issue: \"#1377\"\n"
    return text + (f"        ru: \"{ru}\"\n" if ru is not None else "")


# ---------------------------------------------------------------- owner decision
def test_owner_is_package_core_in_guard_rule_and_context_map():
    ctxs = _contexts()
    assert guard.RULES["delivery-zip"] == OWNER
    assert {r["id"]: r["owner"] for r in ctxs["rules"]}["delivery-zip"] == OWNER
    assert {c["id"]: c["owner"] for c in ctxs["contexts"]}["package"] == OWNER


def test_owner_row_left_the_allowlist():
    allowed = guard.allowlist(_contexts())
    assert [k for k in allowed if k[1] == OWNER] == []


@pytest.mark.parametrize("rel", FACADES)
def test_facades_hold_no_zip_writer_and_call_the_owner(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert [f for f in guard.scan_text(text, rel) if f.rule == "delivery-zip"] == []
    assert "package_core" in text


def test_delivery_zip_guards_jobs_tools_src():
    assert set(guard.GUARDED["delivery-zip"]) == {"jobs", "tools", "src"}


# ---------------------------------------------------------------- listed copies carry a reason
def test_every_delivery_zip_row_names_its_reason_and_this_issue():
    rows = _zip_rows()
    assert len(rows) == 23   # 16 job writers (incl. KPP1 delivered-1371 v008, #1371) + 6 tools/ + 1 src/ non-delivery archives
    assert all(str(d.get("ru", "")).strip() and d["issue"] == "#1377" for d in rows), rows


def test_nine_vpm_packagers_distinguish_candidates_from_finished_jobs():
    rows = {d["at"].split("::")[0]: d for d in _zip_rows()}
    for path in VPM_PACKAGERS:
        expected = ('superseded' if 'elv-tc-vpm' in path and 'v006' not in path else
                    'live-bypass' if 'elv-tc-vpm' in path or 'TEC26-OKS' in path else 'historical')
        assert rows[path]['status'] == expected, path


def test_repo_guard_green_and_route_map_check_green(capsys):
    assert guard.main([]) == 0, capsys.readouterr().out
    assert route_map.main(["--check"]) == 0, capsys.readouterr().out


def test_fresh_process_cli_is_green_twice():
    cmd = [sys.executable, str(ROOT / "tools/architecture/duplicate_guard.py")]
    runs = [subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT) for _ in range(2)]
    assert [r.returncode for r in runs] == [0, 0] and runs[0].stdout == runs[1].stdout == ""


# ---------------------------------------------------------------- guard behaviour (acceptance rows)
@pytest.mark.parametrize("rel", ["tools/x/zipper.py", "src/x/zipper.py", "jobs/J/zipper.py"])
@pytest.mark.parametrize("call", ["zipfile.ZipFile(p, 'w')", "zipfile.ZipFile(p, mode='x')",
                                  "zipfile.ZipFile(p, 'a')", "zipfile.ZipFile(p, m)"])
def test_new_zip_writer_in_tools_src_jobs_is_a_new_copy(tmp_path, rel, call, capsys):
    assert guard.main(_root(tmp_path, {rel: f"import zipfile\n{call}\n"})) == 1
    out = capsys.readouterr().out
    assert f"NEW COPY [delivery-zip] {rel}:" in out and OWNER in out


@pytest.mark.parametrize("call", ["zipfile.ZipFile(p)", "zipfile.ZipFile(p, 'r')", "zipfile.ZipFile(p, mode='r')"])
def test_read_only_zip_in_tools_is_not_a_copy(tmp_path, call):
    assert guard.main(_root(tmp_path, {"tools/x/reader.py": f"import zipfile\n{call}\n"})) == 0


def test_zip_writer_in_adapters_is_not_new(tmp_path, capsys):
    assert guard.main(_root(tmp_path, {"adapters/sketchup/x.py": ZIP_W})) == 0
    assert "NEW COPY" not in capsys.readouterr().out


def test_toolsx_prefix_is_not_guarded(tmp_path):
    assert guard.main(_root(tmp_path, {"toolsx/a.py": ZIP_W, "srcx/a.py": ZIP_W})) == 0


def test_listed_writer_with_reason_is_green(tmp_path):
    assert guard.main(_root(tmp_path, {"tools/x/zipper.py": ZIP_W}, _row("tools/x/zipper.py::<module>", "не пакет"))) == 0


@pytest.mark.parametrize("ru", [None, "", "   "])
def test_delivery_zip_row_without_reason_is_an_error_naming_it(tmp_path, ru, capsys):
    args = _root(tmp_path, {"tools/x/zipper.py": ZIP_W}, _row("tools/x/zipper.py::<module>", ru))
    assert guard.main(args) == 2
    assert "tools/x/zipper.py::<module>" in capsys.readouterr().err


def test_udim_row_without_reason_stays_valid(tmp_path):
    args = _root(tmp_path, {"tools/x/u.py": "t = 1001 + u + 10 * v\n"}, _row("tools/x/u.py::<module>", rule="udim-tile"))
    assert guard.main(args) == 0


def test_stale_tools_row_whose_writer_is_gone_exits_1(tmp_path, capsys):
    args = _root(tmp_path, {"tools/x/zipper.py": "x = 1\n"}, _row("tools/x/zipper.py::<module>", "не пакет"))
    assert guard.main(args) == 1
    assert "STALE ALLOWLIST [delivery-zip] tools/x/zipper.py::<module>" in capsys.readouterr().out


def test_empty_guarded_folders_exit_0(tmp_path):
    assert guard.main(_root(tmp_path, {})) == 0


@pytest.mark.parametrize("top", ["jobs", "tools", "src"])
def test_missing_guarded_folder_is_an_error(tmp_path, top):
    args = _root(tmp_path, {})
    (tmp_path / top).rmdir()
    assert guard.main(args) == 2


def test_route_map_refuses_a_non_russian_reason():
    events, ctxs = mini_yaml.load(ROOT / route_map.EVENTS), _contexts()
    row = next(d for c in ctxs["contexts"] for d in c.get("duplicates", []) if d.get("rule") == "delivery-zip")
    row["ru"] = "historical only"
    with pytest.raises(route_map.SchemaError, match="ru"):
        route_map.check_schema(events, ctxs)
