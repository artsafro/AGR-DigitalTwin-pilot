"""Pure-Python coverage for the resumable per-object export plan. No 3ds Max."""
import hashlib
import json
import os
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
    key_a = plan.path_key("C:/out/a.max")
    key_b = plan.path_key("C:/out/b.max")
    assert found[key_a]["status"] == "ok"
    assert found[key_a]["bytes"] == 4
    assert found[key_b]["status"] == "ok"
    assert set(found) == {key_a, key_b}
    assert plan.read_log(tmp_path / "missing.jsonl") == {}


def test_append_log_round_trip(tmp_path):
    path = tmp_path / "nested" / "run.jsonl"
    plan.append_log(path, {"output": "C:/out/ё.max", "status": "ok", "bytes": 3})
    plan.append_log(path, {"output": "C:/out/ё.max", "status": "failed", "bytes": 3})
    found = plan.read_log(path)
    assert found[plan.path_key("C:/out/ё.max")]["status"] == "failed"
    text = path.read_text(encoding="utf-8")
    assert "ё.max" in text
    assert text.count("\n") == 2


def _receipt(task, payload: bytes, triangles, materials, status="ok"):
    path = Path(task["output"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "node": task["node"],
        "output": task["output"],
        "format": task["format"],
        "status": status,
        "triangles": triangles,
        "materials": materials,
        "bytes": len(payload),
        "sha256": plan.file_sha256(path),
    }


def test_decide_combinations(tmp_path):
    output = tmp_path / "Box.max"
    task = {"node": "Box", "output": str(output), "format": "max"}
    assert plan.decide(task, {}, 12, 1) == "export"
    payload = b"abcd"
    output.write_bytes(payload)
    assert plan.decide(task, {}, 12, 1) == "export"
    weak = {"status": "ok", "bytes": 4}
    assert plan.decide(task, {plan.path_key(output): weak}, 12, 1) == "export"
    row = _receipt(task, payload, 12, 1)
    log = {plan.path_key(output): row}
    assert plan.decide(task, log, 12, 1) == "verify"
    assert plan.decide(task, log, 12, 1) != "skip"


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
        "bytes": 3, "triangles": 12, "materials": 1, "sha256": plan.file_sha256(box),
    })
    node_file = tmp_path / "nodes.json"
    node_file.write_text(json.dumps(nodes), encoding="utf-8")
    code = plan.main([
        "run", "--scene", str(tmp_path / "copy.max"), "--nodes", str(node_file),
        "--out", str(out), "--format", "max", "--log", str(log), "--dry-run",
    ])
    assert code == 0
    text = capsys.readouterr().out
    assert "verify\tBox\t%s" % planned[0]["output"] in text
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


def _identity_oracle(exists, row, task_node, task_format, expected_tris, expected_mats, actual_size, actual_hash):
    """Independent of plan.decide: verify iff every identity field holds."""
    if not exists or not isinstance(row, dict):
        return False
    if row.get("status") != "ok":
        return False
    if row.get("node") != task_node or row.get("format") != task_format:
        return False
    if type(expected_tris) is not int or type(row.get("triangles")) is not int:
        return False
    if type(expected_mats) is not int or type(row.get("materials")) is not int:
        return False
    if row["triangles"] != expected_tris or row["materials"] != expected_mats:
        return False
    digest = row.get("sha256")
    if type(digest) is not str or digest != actual_hash:
        return False
    if row.get("bytes") != actual_size:
        return False
    return True


def test_decide_requires_identity_counts_and_hash(tmp_path):
    output = tmp_path / "Box.max"
    payload = b"abcd-identity"
    task = {"node": "Box", "output": str(output), "format": "max"}
    row = _receipt(task, payload, 12, 1)
    key = plan.path_key(output)
    log = {key: row}
    assert plan.decide(task, log, 12, 1) == "verify"

    output.write_bytes(b"X" * len(payload))
    assert plan.decide(task, log, 12, 1) == "export"
    output.write_bytes(payload)

    assert plan.decide(task, log, 11, 1) == "export"
    assert plan.decide(task, log, 12, 2) == "export"
    assert plan.decide({"node": "box", "output": task["output"], "format": "max"}, log, 12, 1) == "export"
    assert plan.decide({"node": "Box", "output": task["output"], "format": "fbx"}, log, 12, 1) == "export"

    missing_sha = dict(row)
    del missing_sha["sha256"]
    assert plan.decide(task, {key: missing_sha}, 12, 1) == "export"

    missing = tmp_path / "gone.max"
    assert plan.decide({"node": "Box", "output": str(missing), "format": "max"}, log, 12, 1) == "export"

    failed = dict(row)
    failed["status"] = "failed"
    assert plan.decide(task, {key: failed}, 12, 1) == "export"

    assert plan.decide(task, log, True, 1) == "export"
    assert plan.decide(task, log, 12, True) == "export"
    bool_tris = dict(row)
    bool_tris["triangles"] = True
    assert plan.decide(task, {key: bool_tris}, 12, 1) == "export"
    bool_mats = dict(row)
    bool_mats["materials"] = False
    assert plan.decide(task, {key: bool_mats}, 12, 1) == "export"

    big = tmp_path / "big.bin"
    size = (1024 * 1024) + 100
    blob = b"ab" * (size // 2)
    if len(blob) < size:
        blob += b"a"
    big.write_bytes(blob[:size])
    assert plan.file_sha256(big) == hashlib.sha256(blob[:size]).hexdigest()
    assert plan.file_sha256(tmp_path / "missing.bin") is None


def test_probe_decide_verify_only_when_all_identity_holds(tmp_path):
    rng = random.Random(224)
    output = tmp_path / "n.max"
    intact = b"receipt-body-224"
    saw_verify = False
    saw_export = False
    nodes = ["Box", "box"]
    formats = ["max", "fbx"]
    counts = [12, 11, True, False]
    for _ in range(2000):
        file_mode = rng.choice(["intact", "missing", "corrupt_same", "corrupt_diff"])
        if file_mode == "missing":
            if output.exists():
                output.unlink()
            exists = False
            actual_hash = None
            actual_size = None
        else:
            if file_mode == "intact":
                data = intact
            elif file_mode == "corrupt_same":
                data = b"X" * len(intact)
            else:
                data = b"Y" * (len(intact) + rng.choice([0, 5]))
            output.write_bytes(data)
            exists = True
            actual_hash = hashlib.sha256(data).hexdigest()
            actual_size = len(data)
        task_node = rng.choice(nodes)
        task_format = rng.choice(formats)
        expected_tris = rng.choice(counts)
        expected_mats = rng.choice([1, 2, True, False])
        if rng.random() < 0.35:
            row_node, row_format = task_node, task_format
            row_tris, row_mats = expected_tris, expected_mats
            status = "ok"
            sha = actual_hash
            nbytes = actual_size
        else:
            row_node = task_node if rng.random() < 0.5 else rng.choice(nodes + ["Other"])
            row_format = task_format if rng.random() < 0.5 else rng.choice(formats)
            row_tris = expected_tris if rng.random() < 0.5 else rng.choice(counts + [1.5])
            row_mats = expected_mats if rng.random() < 0.5 else rng.choice([1, 0, False, 2])
            status = rng.choice(["ok", "failed"])
            sha_mode = rng.choice(["match", "wrong", "omit", "bool"])
            if sha_mode == "match":
                sha = actual_hash
            elif sha_mode == "wrong":
                sha = "0" * 64
            elif sha_mode == "bool":
                sha = True
            else:
                sha = None
            nbytes = actual_size if rng.random() < 0.5 else rng.choice([0, None, True, 4])
        row = {
            "status": status,
            "node": row_node,
            "format": row_format,
            "triangles": row_tris,
            "materials": row_mats,
            "bytes": nbytes,
        }
        if sha is not None:
            row["sha256"] = sha
        task = {"node": task_node, "output": str(output), "format": task_format}
        log = {plan.path_key(output): row}
        action = plan.decide(task, log, expected_tris, expected_mats)
        oracle = _identity_oracle(
            exists, row, task_node, task_format, expected_tris, expected_mats, actual_size, actual_hash,
        )
        if oracle:
            assert action == "verify"
            saw_verify = True
        else:
            assert action == "export"
            saw_export = True
        assert action in ("verify", "export")
    assert saw_verify and saw_export


def test_read_log_keys_are_case_insensitive_paths(tmp_path):
    folder = tmp_path / "Out"
    folder.mkdir()
    target = folder / "Box.MAX"
    target.write_bytes(b"abcd")
    log = tmp_path / "run.jsonl"
    plan.append_log(log, {"output": str(target), "status": "failed", "bytes": 1})
    other = str(folder / "box.max").replace("/", "\\")
    plan.append_log(log, {"output": str(folder / "." / "box.max"), "status": "ok", "bytes": 4})
    plan.append_log(log, {"output": other, "status": "ok", "bytes": 4})
    found = plan.read_log(log)
    key = plan.path_key(target)
    assert key == plan.path_key(folder / "BOX.max")
    assert key == plan.path_key(str(folder) + "/./Box.MAX")
    assert list(found) == [key]
    assert found[key]["status"] == "ok"
    assert found[key]["bytes"] == 4


def test_collision_reorder_and_subset_invalidate_receipts(tmp_path):
    out_dir = str(tmp_path / "out").replace("\\", "/")
    first = plan.plan_outputs(["A", "a"], out_dir, "max")
    assert [Path(task["output"]).stem for task in first] == ["A", "a__2"]
    log_path = tmp_path / "run.jsonl"
    for task, triangles in zip(first, (12, 8)):
        plan.append_log(log_path, _receipt(task, ("%s-%s" % (task["node"], triangles)).encode("utf-8"), triangles, 1))
    found = plan.read_log(log_path)
    again = plan.plan_outputs(["A", "a"], out_dir, "max")
    assert plan.decide(again[0], found, 12, 1) == "verify"
    assert plan.decide(again[1], found, 8, 1) == "verify"

    reordered = plan.plan_outputs(["a", "A"], out_dir, "max")
    assert [Path(task["output"]).stem for task in reordered] == ["a", "A__2"]
    for task in reordered:
        receipt = found.get(plan.path_key(task["output"]))
        assert isinstance(receipt, dict)
        assert receipt.get("node") != task["node"]
        assert plan.decide(task, found, receipt["triangles"], receipt["materials"]) == "export"

    subset = plan.plan_outputs(["a"], out_dir, "max")
    receipt = found.get(plan.path_key(subset[0]["output"]))
    assert receipt["node"] == "A"
    assert plan.decide(subset[0], found, receipt["triangles"], receipt["materials"]) == "export"


def test_preflight_rejects_source_alias(tmp_path):
    folder = tmp_path / "scene"
    folder.mkdir()
    scene = folder / "probe_1.max"
    scene.write_bytes(b"SCENE")
    out_dir = str(folder).replace("\\", "/")
    tasks = plan.plan_outputs(["probe_1"], out_dir, "max")
    assert plan.path_key(tasks[0]["output"]) == plan.path_key(scene)
    log_path = str(tmp_path / "logs" / "run.jsonl")
    spellings = [
        str(scene),
        str(scene).replace("/", "\\"),
        str(scene).replace("\\", "/"),
        str(scene).swapcase(),
        str(folder / "." / "probe_1.max"),
    ]
    for protected in spellings:
        with pytest.raises(ValueError) as exc:
            plan.preflight(tasks, [protected], log_path)
        assert "probe_1.max" in str(exc.value).replace("\\", "/").casefold()

    link = tmp_path / "probe_1_link.max"
    try:
        os.link(scene, link)
    except OSError:
        link = None
    if link is not None:
        with pytest.raises(ValueError) as exc:
            plan.preflight(tasks, [str(link)], log_path)
        assert "probe_1.max" in str(exc.value).replace("\\", "/")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    other = elsewhere / "probe_1.max"
    other.write_bytes(b"OTHER")
    plan.preflight(tasks, [str(other), None, ""], log_path)

    with pytest.raises(ValueError) as exc:
        plan.preflight(tasks, [str(other)], tasks[0]["output"])
    assert "probe_1.max" in str(exc.value).replace("\\", "/")

    with pytest.raises(ValueError) as exc:
        plan.preflight(tasks, [str(other)], str(other))
    assert "probe_1.max" in str(exc.value).replace("\\", "/")

    dup = [
        {"node": "A", "output": str(tmp_path / "dup.max"), "format": "max"},
        {"node": "B", "output": str(tmp_path / "DUP.max"), "format": "max"},
    ]
    with pytest.raises(ValueError):
        plan.preflight(dup, [], log_path)


def test_cli_refuses_output_over_scene(tmp_path, monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise AssertionError("dcc_batch must not run")

    monkeypatch.setattr(plan.subprocess, "run", boom)
    folder = tmp_path / "src"
    folder.mkdir()
    scene = folder / "probe_1.max"
    payload = b"SCENE-BYTES-224"
    scene.write_bytes(payload)
    code = plan.main([
        "run", "--scene", str(scene), "--out", str(folder),
        "--nodes", "probe_1", "--format", "max", "--dry-run",
    ])
    assert code == 2
    assert scene.read_bytes() == payload
    assert not (folder / "batch_export_request.json").exists()
    assert not (folder / "batch_export.jsonl").exists()
    err = capsys.readouterr().err
    assert "probe_1.max" in err.replace("\\", "/")


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


def _link_or_skip(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        pytest.skip("os.link is not supported")


def test_preflight_rejects_metadata_hardlink_to_source(tmp_path):
    folder = tmp_path / "meta"
    folder.mkdir()
    source = folder / "source.max"
    payload = b"SCENE-BYTES-224"
    source.write_bytes(payload)
    tasks = [{"node": "probe_0", "output": str(folder / "exports" / "probe_0.max"), "format": "max"}]

    log_link = folder / "run.jsonl"
    _link_or_skip(source, log_link)
    with pytest.raises(ValueError):
        plan.preflight(tasks, [str(source)], str(log_link))
    assert source.read_bytes() == payload

    request_link = folder / "batch_export_request.json"
    _link_or_skip(source, request_link)
    with pytest.raises(ValueError):
        plan.preflight(tasks, [str(source)], str(folder / "other.jsonl"), writes=[str(request_link)])
    assert source.read_bytes() == payload

    result_link = folder / "dcc_batch_result.json"
    _link_or_skip(source, result_link)
    with pytest.raises(ValueError):
        plan.preflight(tasks, [str(source)], str(folder / "another.jsonl"), writes=[str(result_link)])
    assert source.read_bytes() == payload


def test_preflight_rejects_write_target_pairs(tmp_path):
    folder = tmp_path / "pairs"
    folder.mkdir()
    source = folder / "source.max"
    source.write_bytes(b"SRC")
    output = str(folder / "probe_0.max")
    tasks = [{"node": "probe_0", "output": output, "format": "max"}]
    request = str(folder / "batch_export_request.json")
    log_spelled = request.replace("\\", "/").swapcase()
    assert log_spelled != request
    assert plan.path_key(log_spelled) == plan.path_key(request)
    with pytest.raises(ValueError):
        plan.preflight(tasks, [str(source)], log_spelled, writes=[request])

    result = str(folder / "dcc_batch_result.json")
    result_spelled = result.replace("\\", "/").swapcase()
    assert result_spelled != result
    assert plan.path_key(result_spelled) == plan.path_key(result)
    with pytest.raises(ValueError):
        plan.preflight(tasks, [str(source)], str(folder / "run.jsonl"), writes=[result, result_spelled])

    request_for_output = output.replace("\\", "/").swapcase()
    assert request_for_output != output
    assert plan.path_key(request_for_output) == plan.path_key(output)
    with pytest.raises(ValueError):
        plan.preflight(tasks, [str(source)], str(folder / "run.jsonl"), writes=[request_for_output])

    existing = folder / "linked_out.max"
    existing.write_bytes(b"OUTPUT-BYTES")
    log_link = folder / "linked_log.jsonl"
    _link_or_skip(existing, log_link)
    linked = [{"node": "probe_0", "output": str(existing), "format": "max"}]
    with pytest.raises(ValueError):
        plan.preflight(
            linked, [str(source)], str(log_link),
            writes=[str(folder / "batch_export_request.json"), str(folder / "dcc_batch_result.json")],
        )


def test_preflight_distinct_metadata_paths_pass(tmp_path):
    folder = tmp_path / "same"
    folder.mkdir()
    source = folder / "source.max"
    source.write_bytes(b"SOURCE")
    tasks = [{"node": "probe_0", "output": str(folder / "probe_0.max"), "format": "max"}]
    plan.preflight(
        tasks, [str(source)], str(folder / "run.jsonl"),
        writes=[str(folder / "batch_export_request.json"), str(folder / "dcc_batch_result.json")],
    )

    copied = tmp_path / "copycase"
    copied.mkdir()
    origin = copied / "source.max"
    origin.write_bytes(b"SOURCE")
    request_copy = copied / "batch_export_request.json"
    request_copy.write_bytes(origin.read_bytes())
    plan.preflight(
        [{"node": "probe_0", "output": str(copied / "probe_0.max"), "format": "max"}],
        [str(origin)], str(copied / "run.jsonl"),
        writes=[str(request_copy), str(copied / "dcc_batch_result.json")],
    )


def test_cli_rejects_request_hardlinked_to_source(tmp_path, monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise AssertionError("dcc_batch must not run")

    monkeypatch.setattr(plan.subprocess, "run", boom)
    payload = b"SCENE-BYTES-224"

    def invoke(folder):
        return plan.main([
            "run", "--scene", str(folder / "source.max"),
            "--nodes", "probe_0", "--out", str(folder / "exports"),
            "--format", "max", "--log", str(folder / "run.jsonl"), "--dry-run",
        ])

    linked = tmp_path / "linked-request"
    linked.mkdir()
    source = linked / "source.max"
    source.write_bytes(payload)
    _link_or_skip(source, linked / "batch_export_request.json")
    assert invoke(linked) == 2
    assert source.read_bytes() == payload
    assert not (linked / "run.jsonl").exists()
    assert "colliding path" in capsys.readouterr().err

    linked_log = tmp_path / "linked-log"
    linked_log.mkdir()
    source_log = linked_log / "source.max"
    source_log.write_bytes(payload)
    _link_or_skip(source_log, linked_log / "run.jsonl")
    assert invoke(linked_log) == 2
    assert source_log.read_bytes() == payload

    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "source.max").write_bytes(payload)
    assert invoke(plain) == 0
    request = plain / "batch_export_request.json"
    assert request.is_file()
    assert json.loads(request.read_text(encoding="utf-8"))["nodes"] == ["probe_0"]


def test_cli_rejects_log_equal_to_request_name(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("dcc_batch must not run")

    monkeypatch.setattr(plan.subprocess, "run", boom)
    folder = tmp_path / "log-is-request"
    folder.mkdir()
    scene = folder / "source.max"
    scene.write_bytes(b"SCENE")
    code = plan.main([
        "run", "--scene", str(scene), "--nodes", "probe_0",
        "--out", str(folder / "exports"), "--format", "max",
        "--log", str(folder / "batch_export_request.json"), "--dry-run",
    ])
    assert code == 2
    assert not (folder / "batch_export_request.json").exists()


def _casefold_key(path) -> str:
    text = os.path.normcase(os.path.abspath(str(path))).replace("\\", "/")
    return text.casefold()


def _stat_id(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_dev, st.st_ino)


def _targets_collide(left, right) -> bool:
    if _casefold_key(left) == _casefold_key(right):
        return True
    left_id = _stat_id(left)
    right_id = _stat_id(right)
    if left_id is None or right_id is None:
        return False
    return left_id == right_id


def _spell_path(rng, path: Path) -> str:
    name = path.name
    if rng.random() < 0.5:
        name = "".join(char.swapcase() if char.isalpha() else char for char in name)
    folder = str(path.parent)
    if rng.random() < 0.5:
        folder = folder.replace("\\", "/")
    else:
        folder = folder.replace("/", "\\")
    sep = "/" if rng.random() < 0.5 else "\\"
    middle = sep + "." + sep if rng.random() < 0.3 else sep
    return folder + middle + name


def test_probe_preflight_write_targets(tmp_path):
    rng = random.Random(224)
    payload = b"PROBE-SOURCE-224"
    pool = [
        "run.jsonl", "batch_export_request.json", "dcc_batch_result.json",
        "probe_0.max", "other.max", "notes.txt",
    ]
    links_ok = True
    origin = tmp_path / "link_origin.bin"
    probe = tmp_path / "link_probe.bin"
    origin.write_bytes(payload)
    try:
        os.link(origin, probe)
    except OSError:
        links_ok = False
    if probe.exists():
        probe.unlink()

    verdicts = {True: 0, False: 0}
    for index in range(500):
        case_dir = tmp_path / ("c%d" % index)
        case_dir.mkdir()
        source = case_dir / "source.max"
        source.write_bytes(payload)
        files = {"source.max": source}
        for name in (rng.choice(pool) for _ in range(rng.randint(2, 4))):
            if name in files:
                continue
            dest = case_dir / name
            if links_ok:
                roll = rng.randrange(3)
                if roll == 0:
                    os.link(source, dest)
                elif roll == 1:
                    os.link(rng.choice(list(files.values())), dest)
                else:
                    dest.write_bytes(("distinct-%d-%s" % (index, name)).encode("utf-8"))
            else:
                dest.write_bytes(("distinct-%d-%s" % (index, name)).encode("utf-8"))
            files[name] = dest
        slots = list(files.values())

        fresh = iter(range(10))

        def pick():
            if rng.random() < 0.5:
                return _spell_path(rng, case_dir / ("fresh_%d.bin" % next(fresh)))
            return _spell_path(rng, rng.choice(slots))

        output = pick()
        log_path = pick()
        request = pick()
        result = pick()
        protected = [str(source)]
        if rng.random() < 0.3:
            protected.append(_spell_path(rng, source))
        targets = [output, log_path, request, result]
        expected = False
        for left_index, left in enumerate(targets):
            if _targets_collide(left, source):
                expected = True
            for right in targets[left_index + 1:]:
                if _targets_collide(left, right):
                    expected = True
        raised = False
        try:
            plan.preflight(
                [{"node": "probe_0", "output": output, "format": "max"}],
                protected, log_path, writes=[request, result],
            )
        except ValueError:
            raised = True
        assert raised is expected, (index, expected, output, log_path, request, result)
        assert source.read_bytes() == payload
        verdicts[expected] += 1
    assert verdicts[True] >= 100 and verdicts[False] >= 50, verdicts
