"""Pure-Python coverage for the resumable per-object export plan. No 3ds Max."""
import json
import random
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path():
    """Writable temp dir. The machine's pytest-of-<user> folder currently denies listing."""
    path = Path(tempfile.mkdtemp(prefix="agr-batch-export-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "tools" / "export"
sys.path.insert(0, str(EXPORT))

import batch_export_plan as plan
import report_export_benchmark as report


def test_safe_stem_and_plan_order():
    assert plan.FORMATS == ("max", "fbx")
    assert plan.safe_stem("Hello World") == "Hello_World"
    assert plan.safe_stem("a   b") == "a_b"
    assert plan.safe_stem("a<b>c:d\"e/f\\g|h?i*j") == "a_b_c_d_e_f_g_h_i_j"
    assert plan.safe_stem("a\x00b") == "a_b"
    assert plan.safe_stem("..name..") == "name"
    assert plan.safe_stem("...") == "node"
    assert plan.safe_stem("") == "node"
    assert plan.safe_stem("  .hidden. ") == "_.hidden._"
    assert len(plan.safe_stem("a" * 200)) == 120
    assert plan.safe_stem("a" * 200) == "a" * 120

    rows = plan.plan_outputs(["Zed", "Amy"], "C:/out", "fbx")
    assert [row["node"] for row in rows] == ["Zed", "Amy"]
    assert rows[0]["output"] == "C:/out/Zed.fbx"
    assert rows[1]["output"] == "C:/out/Amy.fbx"
    assert rows[0]["format"] == "fbx"


def test_collision_suffixes_are_deterministic():
    rows = plan.plan_outputs(["A", "a", "A?"], "C:/out", "max")
    stems = [Path(row["output"]).stem for row in rows]
    assert stems == ["A", "a__2", "A_"]
    assert len({stem.casefold() for stem in stems}) == 3
    assert all(row["output"].endswith(".max") for row in rows)

    crowded = plan.plan_outputs(["Box", "box", "BOX"], "D:/lib", "fbx")
    crowded_stems = [Path(row["output"]).stem for row in crowded]
    assert crowded_stems == ["Box", "box__2", "BOX__3"]
    assert {stem.casefold() for stem in crowded_stems} == {"box", "box__2", "box__3"}


def test_plan_rejects_bad_inputs():
    with pytest.raises(ValueError):
        plan.plan_outputs(["A", "A"], "C:/out", "max")
    with pytest.raises(ValueError):
        plan.plan_outputs([""], "C:/out", "max")
    with pytest.raises(ValueError):
        plan.plan_outputs(["A"], "C:/out", "obj")
    with pytest.raises(ValueError):
        plan.plan_outputs(["ok", ""], "C:/out", "max")


def test_read_log_partial_line_and_last_row_wins(tmp_path):
    path = tmp_path / "run.jsonl"
    path.write_text(
        '\n{"output": "C:/out/a.max", "status": "failed"}\n'
        '{"output": "C:/out/a.max", "status": "ok", "bytes": 4}\n'
        '\n{"output": "C:/out/b.max", "status": "ok"}\n'
        '{"output": "C:/out/b.m\n',
        encoding="utf-8",
    )
    found = plan.read_log(path)
    assert found["C:/out/a.max"]["status"] == "ok"
    assert found["C:/out/a.max"]["bytes"] == 4
    assert found["C:/out/b.max"]["status"] == "ok"
    assert set(found) == {"C:/out/a.max", "C:/out/b.max"}
    assert plan.read_log(tmp_path / "missing.jsonl") == {}


def test_append_log_round_trip(tmp_path):
    path = tmp_path / "nested" / "run.jsonl"
    plan.append_log(path, {"output": "C:/out/ё.max", "status": "ok", "bytes": 3})
    plan.append_log(path, {"output": "C:/out/ё.max", "status": "failed", "bytes": 3})
    found = plan.read_log(path)
    assert found["C:/out/ё.max"]["status"] == "failed"
    text = path.read_text(encoding="utf-8")
    assert "ё.max" in text
    assert text.count("\n") == 2


def test_decide_combinations(tmp_path):
    output = tmp_path / "Box.max"
    task = {"node": "Box", "output": str(output), "format": "max"}
    assert plan.decide(task, {str(output): {"status": "ok", "bytes": 4}}) == "export"

    output.write_bytes(b"abcd")
    assert plan.decide(task, {}) == "verify"
    assert plan.decide(task, {str(output): {"status": "failed", "bytes": 4}}) == "verify"
    assert plan.decide(task, {str(output): {"status": "ok", "bytes": 1}}) == "verify"
    assert plan.decide(task, {str(output): {"status": "ok"}}) == "verify"
    assert plan.decide(task, {str(output): {"status": "ok", "bytes": 4}}) == "skip"


def test_readback_verdict_negatives_and_ok():
    assert plan.readback_verdict(10, 10, 2, 2, True, None) == ("ok", None)
    assert plan.readback_verdict(10, 10, 2, 2, True, "") == ("ok", None)
    negatives = [
        plan.readback_verdict(None, 10, 2, 2, True),
        plan.readback_verdict(True, True, 1, 1, True),
        plan.readback_verdict(10, 9, 2, 2, True),
        plan.readback_verdict(10, 10, 2, 1, True),
        plan.readback_verdict(10, 10, 2, 2, False),
        plan.readback_verdict(10, 10, 2, 2, True, "boom"),
        plan.readback_verdict(0, 0, 1, 1, True),
        plan.readback_verdict(10, 10, 2,0, 2, True),
    ]
    for status, reason in negatives:
        assert status == "failed"
        assert reason


def test_stats_and_projection():
    assert plan.stats([]) == {"n": 0, "median": None, "p90": None, "min": None, "max": None, "total": None}
    assert plan.stats([1.23456]) == {
        "n": 1, "median": 1.2346, "p90": 1.2346, "min": 1.2346, "max": 1.2346, "total": 1.2346,
    }
    ten = plan.stats([10, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    assert ten == {"n": 10, "median": 5.5, "p90": 9.0, "min": 1.0, "max": 10.0, "total": 55.0}
    assert plan.projection(1.5, 136) == 204.0
    assert plan.projection(2, 931) == 1862


def test_request_round_trip_and_validation(tmp_path):
    path = tmp_path / "req.json"
    plan.write_request(path, None, ["A", "B"], "C:/out", "max", "C:/out/run.jsonl")
    loaded = plan.load_request(path)
    assert loaded["scene"] is None
    assert loaded["nodes"] == ["A", "B"]
    assert loaded["format"] == "max"
    assert loaded["out_dir"] == "C:/out"
    assert loaded["log_path"] == "C:/out/run.jsonl"
    with pytest.raises(ValueError):
        plan.write_request(path, None, ["A"], "C:/out", "obj", "C:/out/run.jsonl")
    with pytest.raises(ValueError):
        plan.write_request(path, None, [1], "C:/out", "max", "C:/out/run.jsonl")
    with pytest.raises(ValueError):
        plan.write_request(path, None, ["A"], None, "max", "C:/out/run.jsonl")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "max", "nodes": ["A"], "out_dir": "C:/o", "log_path": 3}), encoding="utf-8")
    with pytest.raises(ValueError):
        plan.load_request(bad)


def test_cli_dry_run_prints_decide(tmp_path, monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise AssertionError("dcc_batch must not run")

    monkeypatch.setattr(plan.subprocess, "run", boom)
    out = tmp_path / "exports"
    log = tmp_path / "logs" / "run.jsonl"
    nodes = ["Box", "Sphere"]
    planned = plan.plan_outputs(nodes, plan._slash(out), "max")
    box = Path(planned[0]["output"])
    box.parent.mkdir(parents=True)
    box.write_bytes(b"xyz")
    log.parent.mkdir(parents=True)
    plan.append_log(log, {
        "node": "Box", "output": planned[0]["output"], "format": "max", "status": "ok",
        "bytes": 3,
    })
    node_file = tmp_path / "nodes.json"
    node_file.write_text(json.dumps(nodes), encoding="utf-8")
    code = plan.main([
        "run", "--scene", str(tmp_path / "copy.max"), "--nodes", str(node_file),
        "--out", str(out), "--format", "max", "--log", str(log), "--dry-run",
    ])
    assert code == 0
    text = capsys.readouterr().out
    assert "skip\tBox\t%s" % planned[0]["output"] in text
    assert "export\tSphere\t%s" % planned[1]["output"] in text
    request = log.with_name("batch_export_request.json")
    assert request.is_file()
    loaded = plan.load_request(request)
    assert loaded["nodes"] == nodes
    assert loaded["format"] == "max"
    assert loaded["scene"]


def test_cli_refuses_repository_output(capsys):
    inside = ROOT / "tools" / "export" / "_batch_export_should_not_exist"
    code = plan.main([
        "run", "--nodes", "A,B", "--out", str(inside), "--format", "max", "--dry-run",
    ])
    assert code == 2
    assert not inside.exists()
    err = capsys.readouterr().err
    assert "repository" in err


def test_report_render_table_and_projection():
    bench = {
        "summary": {
            "b_fbx": {
                "4": {
                    "seconds": {"n": 4, "median": 2.0, "p90": 2.5, "min": 1.0, "max": 3.0, "total": 8.0},
                    "export_s": {"n": 4, "median": 1.5, "p90": 1.6, "min": 1.0, "max": 1.7, "total": 6.0},
                    "ok": 4,
                    "failed": 0,
                    "budget_hit": False,
                }
            },
            "a_savenodes": {
                "4": {
                    "seconds": {"n": 4, "median": 9.0, "p90": 9.0, "min": 9.0, "max": 9.0, "total": 36.0},
                    "export_s": {"n": 4, "median": 8.0, "p90": 8.0, "min": 8.0, "max": 8.0, "total": 32.0},
                    "ok": 3,
                    "failed": 1,
                    "budget_hit": False,
                }
            },
        },
        "extras": {"d_gc": {"4": {"light_s": 0.1, "full_s": 0.2}}},
    }
    text = report.render(bench)
    assert "| route | N | objects ok/total | median s | p90 s | median export-only s | projected 136 Flora | projected 931 MAF |" in text
    assert "| b_fbx | 4 | 4/4 | 2.0 | 2.5 | 1.5 | 4m 32s / 272s | 31m 2s / 1862s |" in text
    assert "d_gc" in text
    assert "fastest all-ok route: b_fbx" in text


def _independent_ok(expected_tris, got_tris, expected_mats, got_mats, exists, error):
    counts = (expected_tris, got_tris, expected_mats, got_mats)
    return (
        exists is True
        and not error
        and all(type(value) is int for value in counts)
        and expected_tris > 0
        and got_tris == expected_tris
        and got_mats == expected_mats
    )


def test_probe_readback_verdict_never_ok_when_failed():
    rng = random.Random(224)
    pool = [None, True, False, 0, 1, 2, -1, 5, "x", 1.0, 8]
    errors = [None, "", "boom", 0, False]
    for _ in range(5000):
        values = [rng.choice(pool) for _ in range(4)]
        exists = rng.choice([True, False])
        error = rng.choice(errors)
        status, reason = plan.readback_verdict(*values, exists, error)
        ok = _independent_ok(*values, exists, error)
        if ok:
            assert status == "ok" and reason is None
        else:
            assert status == "failed"
            assert status != "ok"


def test_probe_decide_skip_only_when_file_ok_and_bytes_match(tmp_path):
    rng = random.Random(224)
    for index in range(2000):
        exists = rng.choice([True, False])
        size = rng.randint(0, 8)
        mode = rng.choice(["absent", "ok", "failed", "ok_wrong", "ok_missing_bytes"])
        output = tmp_path / ("f%d.bin" % index)
        if exists:
            output.write_bytes(b"x" * size)
        elif output.exists():
            output.unlink()
        task = {"node": "n", "output": str(output), "format": "max"}
        log = {}
        if mode == "ok":
            log[str(output)] = {"status": "ok", "bytes": size}
        elif mode == "failed":
            log[str(output)] = {"status": "failed", "bytes": size}
        elif mode == "ok_wrong":
            log[str(output)] = {"status": "ok", "bytes": size + 3}
        elif mode == "ok_missing_bytes":
            log[str(output)] = {"status": "ok"}
        action = plan.decide(task, log)
        should_skip = exists and mode == "ok"
        if should_skip:
            assert action == "skip"
        else:
            assert action != "skip"
        if not exists:
            assert action == "export"
            assert action != "skip"


class FakeMxsArray:
    """pymxs Array: 0-based sequence, plus a MAXScript ``count`` that is not a valid index."""

    def __init__(self, items):
        self._items = list(items)
        self.count = len(self._items)

    def __getitem__(self, index):
        if not isinstance(index, int) or index < 0 or index >= len(self._items):
            raise IndexError("Index out of range")
        return self._items[index]

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)


def test_parse_triple_reads_pymxs_array_zero_based():
    assert plan.parse_triple(FakeMxsArray([True, 20000, 1])) == (True, 20000, 1)
    assert plan.parse_triple(FakeMxsArray(["false", 3, 4])) == (False, 3, 4)
    assert plan.parse_triple(FakeMxsArray(["undefined", 5, 6])) == (False, 5, 6)
    assert plan.parse_triple((True, 7, 8)) == (True, 7, 8)
    assert plan.parse_triple([False, 9, 10]) == (False, 9, 10)
    assert plan.parse_triple(["false", 1, 2]) == (False, 1, 2)
    assert plan.parse_triple(["undefined", 1, 2]) == (False, 1, 2)
    with pytest.raises(TypeError):
        plan.parse_triple(FakeMxsArray([1, 2]))
    with pytest.raises(TypeError):
        plan.parse_triple((1, 2))
    with pytest.raises(IndexError):
        FakeMxsArray([True, 20000, 1])[3]


def test_probe_plan_outputs_unique_inside_dir(tmp_path):
    rng = random.Random(224)
    pool = list("AabB<>:\"/\\|?* \t._-") + ["ё", "Я", "Ω"]
    out = tmp_path / "dest"
    for _list_index in range(500):
        count = rng.randint(1, 24)
        names = []
        seen = set()
        while len(names) < count:
            length = rng.randint(1, 12)
            chars = []
            for _ in range(length):
                if rng.random() < 0.25:
                    chars.append(chr(rng.randint(0x0400, 0x04FF)))
                else:
                    chars.append(rng.choice(pool))
            name = "".join(chars)
            if name == "" or name in seen:
                continue
            seen.add(name)
            names.append(name)
            variant = name.swapcase()
            if rng.random() < 0.3 and variant != name and variant not in seen:
                seen.add(variant)
                names.append(variant)
                if len(names) >= count:
                    break
        fmt = rng.choice(plan.FORMATS)
        prefix = str(out).replace("\\", "/")
        rows = plan.plan_outputs(names, prefix, fmt)
        assert [row["node"] for row in rows] == names
        stems = []
        for row in rows:
            assert row["output"].startswith(prefix + "/")
            assert row["output"].endswith("." + fmt)
            assert row["format"] == fmt
            relative = row["output"][len(prefix) + 1:]
            assert "/" not in relative
            stems.append(Path(row["output"]).stem.casefold())
        assert len(stems) == len(set(stems))
