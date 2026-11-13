"""Headless DWG -> DXF readback (#1203): works on a copy, records hashes, never hands AutoCAD the original.

Pattern: new-case: tests for the headless AutoCAD DWG->DXF readback (fake accoreconsole runner).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "methods" / "body" / "dwg_to_dxf.py"
_spec = importlib.util.spec_from_file_location("dwg_to_dxf", TOOL)
dd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dd)

DXF_TEXT = "  0\r\nSECTION\r\n  2\r\nHEADER\r\n  0\r\nENDSEC\r\n  0\r\nEOF\r\n"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _source(tmp_path: Path, name: str = "Лист L03 без подписей.dwg") -> Path:
    src_dir = tmp_path / "Downloads"
    src_dir.mkdir(parents=True)
    src = src_dir / name
    src.write_bytes(b"AC1032" + bytes(range(256)) * 4)
    return src


class FakeAcc:
    """Stands in for accoreconsole: reads the script, writes the DXF it names (or misbehaves)."""

    def __init__(self, mode: str = "ok"):
        self.mode = mode
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append([str(c) for c in cmd])
        script = Path(cmd[cmd.index("/s") + 1]).read_text(encoding="ascii").splitlines()
        target = Path(script[1])
        if self.mode == "ok":
            target.write_text(DXF_TEXT, encoding="ascii", newline="")
        elif self.mode == "garbage":
            target.write_bytes(b"not a dxf")
        elif self.mode == "touch_source":
            self.source.write_bytes(b"changed by someone else")
            target.write_text(DXF_TEXT, encoding="ascii", newline="")
        elif self.mode == "touch_copy":
            Path(cmd[cmd.index("/i") + 1]).write_bytes(b"changed")
            target.write_text(DXF_TEXT, encoding="ascii", newline="")
        code = 1 if self.mode == "exit1" else 0
        return subprocess.CompletedProcess(cmd, code, stdout="done".encode("utf-16-le"), stderr=b"")


def _args(src, work, **extra):
    out = work / "dxf" / "L03.dxf"
    rec = work / "L03.readback.json"
    argv = [str(src), str(out), str(rec), "--workdir", str(work), "--accoreconsole", str(work / "acc.exe")]
    for k, v in extra.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    return argv, out, rec


def test_script_is_the_cold_run_dxfout_sequence():
    assert dd.build_script(Path("C:/x/kpp1/dxf/L03.dxf")) == (
        "_.DXFOUT\r\nC:/x/kpp1/dxf/L03.dxf\r\n_V\r\n_2018\r\n16\r\n_.QUIT\r\n_Y\r\n")


def test_dry_run_needs_no_autocad_and_writes_nothing(tmp_path, capsys):
    src = _source(tmp_path)
    work = tmp_path / "x" / "kpp1"
    argv, out, rec = _args(src, work)
    before = sorted(p for p in tmp_path.rglob("*"))
    assert dd.main([*argv, "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert sorted(p for p in tmp_path.rglob("*")) == before and not work.exists()
    assert plan["dry_run"] is True
    assert plan["source"] == {"path": str(src), "sha256": _sha(src)}
    cmd = plan["command"]
    assert cmd[1] == "/i" and cmd[3] == "/s"
    assert Path(cmd[2]).parent == work and Path(cmd[2]) != src
    assert str(src) not in " ".join(cmd) and str(src) not in plan["script"]
    assert plan["script"].startswith("_.DXFOUT\r\n" + str(out).replace("\\", "/") + "\r\n_V\r\n_2018\r\n16")


def test_run_copies_hashes_and_hands_autocad_only_the_copy(tmp_path):
    src = _source(tmp_path)
    work = tmp_path / "x" / "kpp1"
    argv, out, rec = _args(src, work)
    (work).mkdir(parents=True)
    (work / "acc.exe").write_bytes(b"")
    fake = FakeAcc()
    src_sha = _sha(src)
    assert dd.main(argv, runner=fake) == 0
    assert _sha(src) == src_sha
    receipt = json.loads(rec.read_text(encoding="utf-8"))
    assert receipt["status"] == "pass"
    assert receipt["source"]["sha256"] == src_sha == receipt["copy"]["sha256"]
    assert receipt["source_sha256_after"] == src_sha
    assert receipt["dxf"]["sha256"] == _sha(out) and receipt["dxf"]["bytes"] == out.stat().st_size
    assert receipt["returncode"] == 0 and receipt["script"] == dd.build_script(out)
    (call,) = fake.calls
    assert call[2] == receipt["copy"]["path"] and str(src) not in " ".join(call)
    assert Path(call[2]).read_bytes() == src.read_bytes()


def test_failing_readbacks_are_failures_never_pass(tmp_path):
    for i, mode in enumerate(("nothing", "garbage", "exit1", "touch_copy", "touch_source")):
        src = _source(tmp_path / str(i))
        work = tmp_path / str(i) / "work"
        work.mkdir(parents=True)
        (work / "acc.exe").write_bytes(b"")
        argv, out, rec = _args(src, work)
        fake = FakeAcc(mode)
        fake.source = src
        code = dd.main(argv, runner=fake)
        receipt = json.loads(rec.read_text(encoding="utf-8"))
        assert code == 3 and receipt["status"] == "fail" and receipt["reason"], (mode, receipt)


def test_refusals_write_nothing_and_never_touch_the_source(tmp_path, capsys):
    src = _source(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "acc.exe").write_bytes(b"")
    src_bytes = src.read_bytes()
    existing = work / "old.dxf"
    existing.write_text("old", encoding="ascii")
    (work / "old.dwg").write_bytes(b"old copy")
    cases = {
        "dxf is the source": [str(src), str(work / "a.dxf.json")],
        "receipt is the source": [str(work / "b.dxf"), str(src)],
        "dxf exists": [str(existing), str(work / "c.json")],
        "dxf is the receipt": [str(work / "d.dxf"), str(work / "d.dxf")],
        "receipt is the copy": [str(work / "e.dxf"), str(work / "e.dwg"), "--copy-name", "e.dwg"],
        "copy exists": [str(work / "f.dxf"), str(work / "f.json"), "--copy-name", "old.dwg"],
    }
    for name, rest in cases.items():
        before = sorted(p.name for p in work.iterdir())
        fake = FakeAcc()
        code = dd.main([str(src), *rest, "--workdir", str(work), "--accoreconsole", str(work / "acc.exe")],
                       runner=fake)
        assert code == 4, (name, capsys.readouterr().err)
        assert sorted(p.name for p in work.iterdir()) == before, name
        assert fake.calls == [] and src.read_bytes() == src_bytes, name
    # the source folder as workdir with the source name as the copy name is the source itself
    code = dd.main([str(src), str(work / "g.dxf"), str(work / "g.json"), "--workdir", str(src.parent),
                    "--copy-name", src.name, "--accoreconsole", str(work / "acc.exe")], runner=FakeAcc())
    assert code == 4 and src.read_bytes() == src_bytes


def test_bad_inputs_are_errors_naming_them(tmp_path, capsys):
    src = _source(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "acc.exe").write_bytes(b"")
    notdwg = tmp_path / "plan.dxf"
    notdwg.write_text("x", encoding="ascii")
    acc = ["--workdir", str(work), "--accoreconsole", str(work / "acc.exe")]
    cases = [
        ([str(tmp_path / "missing.dwg"), str(work / "a.dxf"), str(work / "a.json"), *acc], "missing.dwg"),
        ([str(notdwg), str(work / "b.dxf"), str(work / "b.json"), *acc], "plan.dxf"),
        ([str(src), str(work / "c.txt"), str(work / "c.json"), *acc], "c.txt"),
        ([str(src), str(work / "с кир.dxf"), str(work / "d.json"), *acc], "с кир.dxf"),
        ([str(src), str(work / "e e.dxf"), str(work / "e.json"), *acc], "e e.dxf"),
        ([str(src), str(work / "f.dxf"), str(work / "f.json"), "--workdir", str(work),
          "--accoreconsole", str(work / "nope.exe")], "nope.exe"),
        ([str(src), str(work / "g.dxf"), str(work / "g.json"), *acc, "--copy-name", "g;x.dwg"], "g;x.dwg"),
        ([str(src), str(work / "h.dxf"), str(work / "h.json"), *acc, "--timeout", "nan"], "timeout"),
    ]
    for argv, named in cases:
        before = sorted(p.name for p in work.iterdir())
        fake = FakeAcc()
        code = dd.main(argv, runner=fake)
        err = capsys.readouterr().err
        assert code == 2 and named in err, (argv, err)
        assert fake.calls == [] and sorted(p.name for p in work.iterdir()) == before


def test_original_never_reaches_autocad_brute_force(tmp_path):
    """Probe: generated source/workdir/name layouts; the runner argv and script never name the source."""
    rng = random.Random(1203)
    checked = 0
    for i in range(20):
        base = tmp_path / f"case{i}"
        src = _source(base, rng.choice(["L03.dwg", "Лист 3.dwg", "a b.DWG", "plan.dwg"]))
        work = base / rng.choice(["w", "x/kpp1", "deep/er/w"])
        work.mkdir(parents=True)
        (work / "acc.exe").write_bytes(b"")
        argv, out, rec = _args(src, work)
        fake = FakeAcc()
        assert dd.main(argv, runner=fake) == 0
        (call,) = fake.calls
        script = Path(call[4]).read_text(encoding="ascii")
        assert str(src) not in " ".join(call) and str(src) not in script
        assert not dd.same_file(Path(call[2]), src)
        assert json.loads(rec.read_text(encoding="utf-8"))["source"]["sha256"] == _sha(src)
        checked += 1
    assert checked == 20


@pytest.mark.parametrize("inherited_encoding", ["utf-8", "cp1251", "ascii", "utf-16"])
def test_cli_dry_run_in_a_fresh_process(tmp_path, monkeypatch, inherited_encoding):
    # Detached Windows workers need not inherit the interactive shell's UTF-8 settings.
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONIOENCODING", inherited_encoding)
    src = _source(tmp_path)
    work = tmp_path / "w"
    argv, out, rec = _args(src, work)
    proc = subprocess.run([sys.executable, str(TOOL), *argv, "--dry-run"], capture_output=True, text=True,
                          encoding="utf-8", cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["source"]["sha256"] == _sha(src) and not work.exists()
