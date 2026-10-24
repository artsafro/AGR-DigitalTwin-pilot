"""#528 shared Max xView runner: contract of tools/qa/xview_dump.ms and the parity wrapper.

Max is not launched. SYNTHETIC files only. The .ms text must name the measured behaviour
(load .max, never save, decode 5 mm / 2 mm, weld on Editable Mesh). Python probes cover
SHA-256 copies, the inclusive 2 mm weld, and fail-closed path / key / material rules.
"""
import ctypes
import hashlib
import importlib.util
import json
import math
import os
import random
from ctypes import wintypes
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("xview_parity", ROOT / "tools" / "qa" / "xview_parity.py")
xp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xp)

MS = ROOT / "tools" / "qa" / "xview_dump.ms"
REVIEW = ROOT / "jobs" / "vyatskaya-tow02" / "scripts" / "xview_review.ms"
CAPS = ROOT / "docs" / "agents" / "CAPABILITIES.md"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_ms_loads_max_never_saves_and_decodes_millimetres():
    text = MS.read_text(encoding="utf-8")
    assert "loadMaxFile" in text and "useFileUnits:true" in text and "quiet:true" in text
    assert 'units.decodeValue "5mm"' in text and 'units.decodeValue "2mm"' in text
    assert "meshop.weldVertsByThreshold" in text
    assert 'mode != "weld"' in text
    assert "saveMaxFile" not in text and "saveNodes" not in text
    assert "SHA256" in text and "Copy" in text
    assert "flagged" in text or "facesCheck" in text
    # Failure is a file the wrapper can see; done.txt is removed only after the alias guard.
    assert "failed.txt" in text
    assert "System.Environment" in text
    assert text.find("deleteFile doneP") != -1
    assert text.find("deleteFile doneP") < text.find("for j in jobs do")


def test_review_header_points_at_shared_runner():
    text = REVIEW.read_text(encoding="utf-8")
    assert "tools/qa/xview_dump.ms" in text.splitlines()[0] or "tools/qa/xview_dump.ms" in text[:500]


def test_capabilities_lists_the_runner():
    text = CAPS.read_text(encoding="utf-8")
    assert "tools/qa/xview_dump.ms" in text
    assert "2mm" in text and ".max" in text


def test_stage_keeps_sha256_and_does_not_delete_source(tmp_path):
    rng = random.Random(528)
    temp = tmp_path / "ascii_temp"
    temp.mkdir()
    for i in range(12):
        folder = tmp_path / f"модель_{i}"
        folder.mkdir()
        src = folder / f"f{i}.max"
        src.write_bytes(rng.randbytes(rng.randint(1, 3000)))
        before = src.read_bytes()
        staged = xp.stage_input(src, temp)
        assert sha(staged) == sha(src) == hashlib.sha256(before).hexdigest()
        assert src.read_bytes() == before
        assert str(staged).encode("ascii")
        assert staged.resolve() != src.resolve()


def test_ascii_source_is_not_copied_or_deleted(tmp_path):
    src = tmp_path / "plain.max"
    src.write_bytes(b"abc")
    staged = xp.stage_input(src, tmp_path / "t")
    assert staged.resolve() == src.resolve()
    assert src.read_bytes() == b"abc"


def test_stage_refuses_temp_that_is_the_source(tmp_path):
    src = tmp_path / "a.max"
    src.write_bytes(b"abc")
    temp = tmp_path / "t"
    temp.mkdir()
    dest = temp / f"xv_{sha(src)}.max"
    os.link(src, dest)
    with pytest.raises(xp.DumpError, match="alias"):
        xp.stage_input(src, temp)
    assert src.read_bytes() == b"abc"


def test_weld_includes_exactly_2mm_and_matches_brute_predicate():
    samples = [i * 1e-6 for i in range(0, 3001)]
    samples += [0.0, 0.002, math.nextafter(0.002, 0.0), math.nextafter(0.002, 1.0)]
    for d in samples:
        assert xp.weld_includes(d) is (d <= 0.002)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, "2mm"])
def test_weld_non_finite_is_an_error(bad):
    with pytest.raises(xp.DumpError):
        xp.weld_includes(bad)


def test_changed_bytes_are_not_a_clean_load():
    with pytest.raises(xp.DumpError, match="changed"):
        xp.require_unchanged("aa" * 32, "bb" * 32)
    xp.require_unchanged("ab" * 32, "ab" * 32)


def test_distinct_paths_match_brute_force(tmp_path):
    files = []
    for i in range(5):
        p = tmp_path / f"f{i}.json"
        p.write_text(str(i), encoding="utf-8")
        files.append(p)
    link = tmp_path / "link.json"
    os.link(files[0], link)

    def clashes(mapping):
        items = list(mapping.items())
        bad = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i][1], items[j][1]
                same = a.resolve() == b.resolve() or (a.exists() and b.exists() and os.path.samefile(a, b))
                if same:
                    bad.append((items[i][0], items[j][0]))
        return bad

    rng = random.Random(7)
    pool = files + [link]
    roles = ["input", "output", "report", "temp"]
    for _ in range(40):
        mapping = {role: rng.choice(pool) for role in roles}
        got = clashes(mapping)
        if got:
            with pytest.raises(xp.DumpError):
                xp.require_distinct(mapping)
        else:
            xp.require_distinct(mapping)


def _scene():
    return [
        {"name": "small", "faces": 3, "kind": "mesh"},
        {"name": "big", "faces": 9, "kind": "mesh"},
        {"name": "cam", "faces": 0, "kind": "other"},
        {"name": "empty", "faces": 0, "kind": "mesh"},
    ]


def test_omitted_node_is_largest_and_every_other_is_dropped():
    chosen, dropped = xp.select_node(_scene(), "")
    assert chosen["name"] == "big"
    names = {d["name"]: d["reason"] for d in dropped}
    assert set(names) == {"small", "cam", "empty"}
    assert names["cam"] == "not a mesh"
    assert names["empty"] == "empty mesh"
    assert names["small"] == "not selected"


def test_missing_node_is_named_and_not_replaced_by_the_largest():
    with pytest.raises(xp.DumpError, match="missing-node"):
        xp.select_node(_scene(), "missing-node")


def test_empty_target_mesh_is_an_error():
    with pytest.raises(xp.DumpError, match="empty"):
        xp.select_node(_scene(), "empty")


def test_unmapped_material_and_slot_are_named():
    with pytest.raises(xp.DumpError, match="Brick"):
        xp.select_node(_scene(), "big", material="Brick", materials=["Glass"])
    with pytest.raises(xp.DumpError, match="9"):
        xp.select_node(_scene(), "big", slot="9", slots=[1, 2])


def test_prepare_unknown_key_mode_and_suffix_name_the_offender(tmp_path):
    src = tmp_path / "m.fbx"
    src.write_bytes(b"fbx")
    out = tmp_path / "out"
    temp = tmp_path / "temp"
    with pytest.raises(xp.DumpError, match="tolerance"):
        xp.prepare_run([{"label": "a", "path": src, "tolerance": 1}], out, temp)
    with pytest.raises(xp.DumpError, match="weldx"):
        xp.prepare_run([{"label": "a", "path": src, "mode": "weldx"}], out, temp)
    bad = tmp_path / "m.obj"
    bad.write_bytes(b"obj")
    with pytest.raises(xp.DumpError, match="m.obj"):
        xp.prepare_run([{"label": "a", "path": bad}], out, temp)
    assert not out.exists()


def test_prepare_refuses_output_that_is_the_input(tmp_path):
    src = tmp_path / "m.max"
    src.write_bytes(b"scene")
    out = tmp_path / "out"
    out.mkdir()
    os.link(src, out / "m.max.json")
    h = sha(src)
    with pytest.raises(xp.DumpError, match="alias"):
        xp.prepare_run([{"label": "m.max", "path": src, "mode": "plain"}], out, tmp_path / "temp")
    assert sha(src) == h
    assert not (out / "jobs.txt").exists()


def _review(**over):
    face = [49, 1, 0.25, [1.0, 2.0, 3.0]]
    dump = {
        "dump_version": 2,
        "label": "t",
        "path": "C:/ascii/model.fbx",
        "saved": False,
        "sha256_before": "ab" * 32,
        "sha256_after": "ab" * 32,
        "node": "big",
        "scene": [["big", "Editable_Poly", 4], ["small", "Editable_mesh", 1]],
        "dropped": [{"name": "small", "reason": "not selected"}],
        "tolFaces": 0.005,
        "tolVerts": 0.002,
        "verticesCheck": {"count": 0, "items": []},
        "facesCheck": {"count": 1, "items": [face]},
    }
    dump.update(over)
    return dump


def full_result(label, nonce, **over):
    """One complete native result, as xview_dump.ms writes it, plus the run nonce."""
    data = _review(label=label)
    data.update({
        "nonce": nonce,
        "path": "C:/ascii/model.fbx",
        "units": "meters",
        "systemScale": 1.0,
        "sourceClass": "Editable_Poly",
        "weldedVerts": -1,
        "faces": 4,
        "verts": 8,
        "tris": 4,
        "ngons": 0,
        "bbox": [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
        "verticesCheck": {
            "name": "Overlapping Vertices", "type": "#Vertices", "count": 0, "items": [],
            "text": "", "seconds": 0.0,
        },
        "facesCheck": {
            "name": "Overlapping Faces", "type": "#Faces", "count": 1,
            "items": [[49, 1, 0.25, [1.0, 2.0, 3.0]]], "text": "", "seconds": 0.1,
        },
    })
    data.update(over)
    return data


REQUIRED_RESULT_KEYS = (
    "dump_version", "nonce", "label", "path", "saved", "sha256_before", "sha256_after",
    "units", "systemScale", "tolFaces", "tolVerts", "scene", "dropped", "node",
    "sourceClass", "weldedVerts", "faces", "verts", "tris", "ngons", "bbox",
    "verticesCheck", "facesCheck",
)


def test_validate_review_accepts_a_complete_dump(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps(_review()), encoding="utf-8")
    out = tmp_path / "out.json"
    assert xp.main([str(src), "--validate-review", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["node"] == "big"
    assert sha(src) == hashlib.sha256(json.dumps(_review()).encode("utf-8")).hexdigest()


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(facesCheck={"count": 1, "items": []}),
    lambda d: d.update(verticesCheck={"count": 0}),
    lambda d: d["facesCheck"]["items"][0].__setitem__(2, float("nan")),
    lambda d: d["facesCheck"]["items"][0].__setitem__(3, [1.0, float("inf"), 0.0]),
    lambda d: d.update(tolVerts=0),
    lambda d: d.update(tolFaces=float("nan")),
    lambda d: d.update(saved=True),
    lambda d: d.update(sha256_after="cd" * 32),
    lambda d: d.update(node="nope"),
    lambda d: d.update(dropped=[]),
    lambda d: d.update(scene=[]),
    lambda d: d.pop("facesCheck"),
])
def test_partial_nan_or_threshold_review_exits_nonzero_and_writes_nothing(tmp_path, mutate):
    dump = _review()
    mutate(dump)
    src = tmp_path / "in.json"
    src.write_text(json.dumps(dump), encoding="utf-8")
    out = tmp_path / "out.json"
    assert xp.main([str(src), "--validate-review", "--out", str(out)]) == 2
    assert not out.exists()
    assert sha(src) == hashlib.sha256(json.dumps(dump).encode("utf-8")).hexdigest()


def test_validate_review_refuses_out_that_is_the_input(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps(_review()), encoding="utf-8")
    h = sha(src)
    assert xp.main([str(src), "--validate-review", "--out", str(src)]) == 2
    assert sha(src) == h


def _job_file(dirpath, name, payload):
    path = dirpath / name
    path.write_bytes(payload)
    return path


def test_prepare_refuses_jobs_txt_hardlink_of_the_input(tmp_path):
    src = _job_file(tmp_path, "source.max", b"SCENE")
    out = tmp_path / "out"
    out.mkdir()
    os.link(src, out / "jobs.txt")
    with pytest.raises(xp.DumpError, match="alias"):
        xp.prepare_run([{"label": "a", "path": src, "mode": "plain"}], out, tmp_path / "temp")
    assert src.read_bytes() == b"SCENE"
    assert (out / "jobs.txt").read_bytes() == b"SCENE"


def test_prepare_refuses_duplicate_labels(tmp_path):
    a = _job_file(tmp_path, "a.max", b"A")
    b = _job_file(tmp_path, "b.max", b"B")
    out = tmp_path / "out"
    with pytest.raises(xp.DumpError, match="same"):
        xp.prepare_run(
            [{"label": "same", "path": a}, {"label": "same", "path": b}],
            out, tmp_path / "temp")
    assert a.read_bytes() == b"A" and b.read_bytes() == b"B"
    assert not (out / "jobs.txt").exists()


def test_prepare_refuses_duplicate_labels_ignoring_case(tmp_path):
    a = _job_file(tmp_path, "a.max", b"A")
    b = _job_file(tmp_path, "b.fbx", b"B")
    out = tmp_path / "out"
    with pytest.raises(xp.DumpError, match="[Ss]ame"):
        xp.prepare_run(
            [{"label": "Same", "path": a}, {"label": "same", "path": b}],
            out, tmp_path / "temp")
    assert not (out / "jobs.txt").exists()


def test_prepare_refuses_cross_job_output_alias(tmp_path):
    a = _job_file(tmp_path, "a.max", b"AAA")
    b = _job_file(tmp_path, "b.max", b"BBB")
    out = tmp_path / "out"
    out.mkdir()
    os.link(a, out / "b.json")
    with pytest.raises(xp.DumpError, match="alias"):
        xp.prepare_run(
            [{"label": "a", "path": a}, {"label": "b", "path": b}],
            out, tmp_path / "temp")
    assert a.read_bytes() == b"AAA" and b.read_bytes() == b"BBB"
    assert (out / "b.json").read_bytes() == b"AAA"
    assert not (out / "jobs.txt").exists()


def test_prepare_distinct_paths_still_pass(tmp_path):
    a = _job_file(tmp_path, "a.max", b"AAA")
    b = _job_file(tmp_path, "b.fbx", b"BBB")
    out = tmp_path / "out"
    result = xp.prepare_run(
        [{"label": "one", "path": a, "mode": "plain"},
         {"label": "two", "path": b, "mode": "weld"}],
        out, tmp_path / "temp")
    lines = [ln for ln in (out / "jobs.txt").read_text(encoding="ascii").splitlines() if ln]
    assert lines[0].startswith("#nonce:")
    assert [ln.split("|", 1)[0] for ln in lines[1:]] == ["one", "two"]
    assert a.read_bytes() == b"AAA" and b.read_bytes() == b"BBB"
    assert not (out / "done.txt").exists()
    assert result["jobs_file"] == out / "jobs.txt"
    assert result["nonce"] == lines[0].split(":", 1)[1]


def test_prepare_allows_duplicated_input_when_labels_differ(tmp_path):
    src = _job_file(tmp_path, "m.max", b"same-bytes")
    out = tmp_path / "out"
    xp.prepare_run(
        [{"label": "one", "path": src}, {"label": "two", "path": src, "mode": "plain"}],
        out, tmp_path / "temp")
    lines = [ln for ln in (out / "jobs.txt").read_text(encoding="ascii").splitlines() if ln]
    assert lines[0].startswith("#nonce:")
    assert [ln.split("|", 1)[0] for ln in lines[1:]] == ["one", "two"]
    assert lines[1].split("|")[1] == lines[2].split("|")[1]
    assert src.read_bytes() == b"same-bytes"
    assert not (out / "done.txt").exists()


def test_prepare_empty_jobs_are_an_error(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(xp.DumpError, match="no inputs"):
        xp.prepare_run([], out, tmp_path / "temp")
    assert not out.exists()


def test_prepare_refuses_done_txt_that_aliases_an_input(tmp_path):
    src = _job_file(tmp_path, "source.max", b"SCENE")
    out = tmp_path / "out"
    out.mkdir()
    os.link(src, out / "done.txt")
    (out / "a.json").write_text("keep-me", encoding="utf-8")
    (out / "report.jsonl").write_text("keep-report\n", encoding="utf-8")
    with pytest.raises(xp.DumpError, match="alias"):
        xp.prepare_run([{"label": "a", "path": src}], out, tmp_path / "temp")
    assert src.read_bytes() == b"SCENE"
    assert (out / "done.txt").read_bytes() == b"SCENE"
    assert (out / "a.json").read_text(encoding="utf-8") == "keep-me"
    assert (out / "report.jsonl").read_text(encoding="utf-8") == "keep-report\n"
    assert not (out / "jobs.txt").exists()


def test_prepare_refuses_staged_temp_that_aliases_another_input(tmp_path):
    folder = tmp_path / "модель"
    folder.mkdir()
    src_bytes = os.urandom(32)
    other_bytes = os.urandom(32)
    src = _job_file(folder, "a.max", src_bytes)
    other = _job_file(tmp_path, "b.max", other_bytes)
    temp = tmp_path / "temp"
    temp.mkdir()
    dest = temp / f"xv_{sha(src)}.max"
    os.link(other, dest)
    out = tmp_path / "out"
    with pytest.raises(xp.DumpError, match="alias"):
        xp.prepare_run(
            [{"label": "a", "path": src}, {"label": "b", "path": other}],
            out, temp)
    assert src.read_bytes() == src_bytes
    assert other.read_bytes() == other_bytes
    assert dest.read_bytes() == other_bytes
    assert not (out / "jobs.txt").exists()


def test_repeat_after_success_drops_stale_done_and_partial_is_not_success(tmp_path):
    src = _job_file(tmp_path, "m.max", b"v1")
    other = _job_file(tmp_path, "n.fbx", b"v2")
    out = tmp_path / "out"
    out.mkdir()
    (out / "done.txt").write_text("ok", encoding="ascii")
    (out / "a.json").write_text('{"old": true}', encoding="utf-8")
    (out / "b.json").write_text('{"old": true}', encoding="utf-8")
    (out / "report.jsonl").write_text('{"label":"a"}\n', encoding="utf-8")
    (out / "keep.json").write_text("stay", encoding="utf-8")
    xp.prepare_run(
        [{"label": "a", "path": src}, {"label": "b", "path": other}],
        out, tmp_path / "temp")
    assert not (out / "done.txt").exists()
    assert not (out / "a.json").exists()
    assert not (out / "b.json").exists()
    assert not (out / "report.jsonl").exists()
    assert (out / "keep.json").read_text(encoding="utf-8") == "stay"
    assert (out / "jobs.txt").is_file()
    assert src.read_bytes() == b"v1" and other.read_bytes() == b"v2"
    (out / "a.json").write_text("{}", encoding="utf-8")
    (out / "failed.txt").write_text("b failed", encoding="utf-8")
    with pytest.raises(xp.DumpError, match="b"):
        xp.check_run(out, ["a", "b"])
    assert not (out / "done.txt").exists()


def test_prepare_failure_clears_success(tmp_path):
    """A valid run, then prepare_run(mode='bad'), leaves nothing check_run can accept."""
    src = _job_file(tmp_path, "m.max", b"SCENE")
    out = tmp_path / "out"
    xp.prepare_run([{"label": "a", "path": src, "mode": "plain"}], out, tmp_path / "temp")
    nonce = "abc12345"
    (out / "jobs.txt").write_text(f"#nonce:{nonce}\na|{src}||plain||\n", encoding="utf-8")
    (out / "a.json").write_text(json.dumps(full_result("a", nonce)), encoding="utf-8")
    (out / "done.txt").write_text(nonce + "\n", encoding="ascii")
    assert xp.check_run(out, ["a"])["a"]["nonce"] == nonce
    with pytest.raises(xp.DumpError):
        xp.prepare_run([{"label": "a", "path": src, "mode": "bad"}], out, tmp_path / "temp")
    assert src.read_bytes() == b"SCENE"
    assert not (out / "done.txt").exists()
    with pytest.raises(xp.DumpError):
        xp.check_run(out, ["a"])


def test_bad_mode_still_refuses_hardlinked_done_before_any_delete(tmp_path):
    src = _job_file(tmp_path, "source.max", b"SCENE")
    out = tmp_path / "out"
    out.mkdir()
    os.link(src, out / "done.txt")
    with pytest.raises(xp.DumpError, match="alias"):
        xp.prepare_run([{"label": "a", "path": src, "mode": "bad"}], out, tmp_path / "temp")
    assert src.read_bytes() == b"SCENE"
    assert (out / "done.txt").read_bytes() == b"SCENE"
    assert not (out / "jobs.txt").exists()


def test_check_run_accepts_only_a_complete_success(tmp_path):
    src = _job_file(tmp_path, "m.max", b"SCENE")
    out = tmp_path / "out"
    rec = xp.prepare_run(
        [{"label": "a", "path": src, "mode": "plain"}, {"label": "b", "path": src, "mode": "weld"}],
        out, tmp_path / "temp")
    nonce = rec["nonce"]
    for label in ("a", "b"):
        (out / f"{label}.json").write_text(json.dumps(full_result(label, nonce)), encoding="utf-8")
    (out / "done.txt").write_text(nonce + "\n", encoding="ascii")
    got = xp.check_run(out, ["a", "b"])
    assert got["a"]["label"] == "a" and got["b"]["nonce"] == nonce
    assert set(REQUIRED_RESULT_KEYS) <= set(got["a"])
    (out / "failed.txt").write_text("late", encoding="utf-8")
    with pytest.raises(xp.DumpError):
        xp.check_run(out, ["a", "b"])


def test_check_run_names_every_missing_label(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    nonce = "abc12345"
    (out / "jobs.txt").write_text(
        f"#nonce:{nonce}\na|C:/ascii/a.fbx||plain||\nb|C:/ascii/b.fbx||plain||\n"
        f"c|C:/ascii/c.fbx||plain||\n", encoding="utf-8")
    (out / "done.txt").write_text(nonce + "\n", encoding="ascii")
    (out / "a.json").write_text(json.dumps(full_result("a", nonce)), encoding="utf-8")
    (out / "c.json").write_text("{", encoding="utf-8")
    with pytest.raises(xp.DumpError, match="b") as ei:
        xp.check_run(out, ["a", "b", "c"])
    assert "c" in str(ei.value)


def _link_or_skip(src, dest):
    try:
        os.link(src, dest)
    except OSError:
        return False
    return True


def test_probe_never_overwrites_input(tmp_path):
    rng = random.Random(5281)
    n = 60
    kept = 0
    modes = ["", "plain", "weld", "weldpoly", "bad"]
    for i in range(n):
        root = tmp_path / f"t{i}"
        root.mkdir()
        out = root / "out"
        out.mkdir()
        blobs = []
        srcs = []
        jobs = []
        njob = rng.randint(1, 4)
        for j in range(njob):
            raw = rng.randbytes(rng.randint(1, 80))
            if rng.random() < 0.25:
                folder = root / f"модель_{j}"
                folder.mkdir()
                path = _job_file(folder, f"f{j}.max", raw)
            else:
                path = _job_file(root, f"f{j}.fbx", raw)
            srcs.append(path)
            blobs.append(raw)
            jobs.append({"label": rng.choice(["a", "b", "same", "Same", f"j{j}"]),
                         "path": path, "mode": rng.choice(modes)})
        kind = i % 6
        if kind == 0:
            _link_or_skip(srcs[0], out / "jobs.txt")
        elif kind == 1:
            _link_or_skip(srcs[0], out / "done.txt")
        elif kind == 2:
            _link_or_skip(srcs[0], out / "report.jsonl")
        elif kind == 3 and njob > 1:
            _link_or_skip(srcs[0], out / f"{jobs[1]['label']}.json")
        elif kind == 4:
            (out / "done.txt").write_text("stale", encoding="ascii")
            (out / f"{jobs[0]['label']}.json").write_text("{}", encoding="utf-8")
            (out / "report.jsonl").write_text("{}\n", encoding="utf-8")
        try:
            xp.prepare_run(jobs, out, root / "temp")
        except xp.DumpError:
            pass
        if all(path.read_bytes() == raw for path, raw in zip(srcs, blobs)):
            kept += 1
    assert kept == n, f"never overwrite input: {kept}/{n}"


def test_probe_at_most_one_output_per_label(tmp_path):
    rng = random.Random(5282)
    n = 60
    ok = 0
    pool = ["aa", "bb", "same", "Same", "AA"]
    for i in range(n):
        root = tmp_path / f"t{i}"
        root.mkdir()
        out = root / "out"
        jobs = []
        srcs = []
        blobs = []
        njob = rng.randint(1, 4)
        for j in range(njob):
            raw = rng.randbytes(rng.randint(1, 40))
            path = _job_file(root, f"f{j}.max", raw)
            srcs.append(path)
            blobs.append(raw)
            jobs.append({"label": rng.choice(pool + [f"n{j}"]), "path": path,
                         "mode": rng.choice(["plain", "weld", ""])})
        out.mkdir()
        if i % 5 == 0 and _link_or_skip(srcs[0], out / "jobs.txt"):
            existed, before = True, (out / "jobs.txt").read_bytes()
        else:
            existed, before = False, None
        try:
            xp.prepare_run(jobs, out, root / "temp")
            lines = [ln for ln in (out / "jobs.txt").read_text(encoding="ascii").splitlines() if ln]
            stems = [ln.split("|", 1)[0].casefold() for ln in lines]
            good = len(stems) == len(set(stems))
        except xp.DumpError:
            if existed:
                good = (out / "jobs.txt").read_bytes() == before
            else:
                good = not (out / "jobs.txt").exists()
        counts = {}
        if out.exists():
            for path in out.glob("*.json"):
                counts[path.name.casefold()] = counts.get(path.name.casefold(), 0) + 1
        if good and all(v <= 1 for v in counts.values()) and all(
                path.read_bytes() == raw for path, raw in zip(srcs, blobs)):
            ok += 1
    assert ok == n, f"at most one output per label: {ok}/{n}"


def _oracle_success(obj, nonce, label):
    """Independent reading of a native success object. Does not call check_run."""
    if not isinstance(obj, dict) or "error" in obj:
        return False
    if obj.get("nonce") != nonce or obj.get("label") != label or obj.get("saved") is not False:
        return False
    if obj.get("dump_version") != 2:
        return False
    if any(key not in obj for key in REQUIRED_RESULT_KEYS):
        return False
    before, after = obj.get("sha256_before"), obj.get("sha256_after")
    if not isinstance(before, str) or before != after or len(before) != 64:
        return False
    for key in ("tolFaces", "tolVerts", "systemScale"):
        value = obj.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return False
        if key != "systemScale" and value <= 0:
            return False
    if not obj.get("node") or not isinstance(obj.get("scene"), list) or not obj["scene"]:
        return False
    if not isinstance(obj.get("dropped"), list):
        return False
    names = []
    for row in obj["scene"]:
        if not isinstance(row, list) or not row or not isinstance(row[0], str):
            return False
        names.append(row[0])
    if obj["node"] not in names:
        return False
    dropped = []
    for row in obj["dropped"]:
        if not isinstance(row, dict) or "name" not in row or "reason" not in row:
            return False
        dropped.append(row["name"])
    if obj["node"] in dropped:
        return False
    if any(name != obj["node"] and name not in dropped for name in names):
        return False
    for check, width in (("verticesCheck", 2), ("facesCheck", 4)):
        block = obj.get(check)
        if not isinstance(block, dict):
            return False
        count, items = block.get("count"), block.get("items")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            return False
        if not isinstance(items, list) or len(items) != count:
            return False
        for item in items:
            if not isinstance(item, list) or len(item) != width:
                return False
            if isinstance(item[0], bool) or not isinstance(item[0], int) or item[0] < 1:
                return False
    return True


def test_probe_done_only_on_all_success(tmp_path):
    rng = random.Random(5283)
    n = 48
    ok = 0
    nonce = "abc12345"
    mutations = ("ok", "drop", "error", "saved", "tol0", "label", "nonce", "partial-items", "nan-file")
    for i in range(n):
        root = tmp_path / f"t{i}"
        out = root / "out"
        out.mkdir(parents=True)
        label = "a"
        kind = mutations[i % len(mutations)]
        payload = full_result(label, nonce)
        write_done = True
        done_text = nonce + "\n"
        failed = False
        raw = None
        if kind == "drop":
            payload.pop(rng.choice(REQUIRED_RESULT_KEYS))
        elif kind == "error":
            payload["error"] = "checker failed"
        elif kind == "saved":
            payload["saved"] = True
        elif kind == "tol0":
            payload["tolVerts"] = 0
        elif kind == "label":
            payload["label"] = "wrong"
        elif kind == "nonce":
            payload["nonce"] = "deadbeef"
        elif kind == "partial-items":
            payload["facesCheck"] = {"name": "Overlapping Faces", "type": "#Faces", "count": 1, "items": [],
                                     "text": "", "seconds": 0.1}
        elif kind == "nan-file":
            raw = '{"tolFaces": NaN}'
        if i % 5 == 0:
            write_done = False
        if i % 7 == 0:
            failed = True
        if i % 11 == 0:
            done_text = "othernonce\n"
        (out / "jobs.txt").write_text(f"#nonce:{nonce}\n{label}|C:/ascii/a.fbx||plain||\n", encoding="utf-8")
        if raw is None:
            (out / f"{label}.json").write_text(json.dumps(payload), encoding="utf-8")
            parsed = payload
        else:
            (out / f"{label}.json").write_text(raw, encoding="utf-8")
            parsed = None
        if write_done:
            (out / "done.txt").write_text(done_text, encoding="ascii")
        if failed:
            (out / "failed.txt").write_text("job failed", encoding="utf-8")
        oracle = (
            write_done and not failed and done_text.strip() == nonce
            and _oracle_success(parsed, nonce, label)
        )
        try:
            xp.check_run(out, [label])
            got = True
        except xp.DumpError:
            got = False
        except Exception:
            got = None
        if (got is True) == oracle and got is not None:
            ok += 1
    assert ok == n, f"done only on full schema and this nonce: {ok}/{n}"


def _jobs_text(nonce, rows):
    lines = [f"#nonce:{nonce}"]
    for label, path, node, mode, material, slot in rows:
        lines.append("|".join([label, str(path), node, mode, material, slot]))
    return "\n".join(lines) + "\n"


def _snapshot(paths):
    found = {}
    for path in paths:
        if path.is_file():
            found[str(path)] = path.read_bytes()
    return found


def test_prepare_rejects_separators_before_write(tmp_path):
    src = _job_file(tmp_path, "m.max", b"SCENE")
    out = tmp_path / "out"
    cases = [
        {"label": "a\nb", "path": src},
        {"label": "a|b", "path": src},
        {"label": "a", "path": src, "node": "n|weld\ninjected"},
        {"label": "a", "path": src, "slot": "1|2"},
        {"label": "a", "path": src, "material": "brick\rglass"},
    ]
    for job in cases:
        with pytest.raises(xp.DumpError, match="bad field"):
            xp.prepare_run([job], out, tmp_path / "temp")
        assert src.read_bytes() == b"SCENE"
        assert not (out / "jobs.txt").exists()


def test_prepare_names_unmapped_slot(tmp_path):
    src = _job_file(tmp_path, "m.max", b"SCENE")
    out = tmp_path / "out"
    with pytest.raises(xp.DumpError, match="glass"):
        xp.prepare_run([{"label": "a", "path": src, "slot": "glass"}], out, tmp_path / "temp")
    assert not out.exists()
    with pytest.raises(xp.DumpError, match="0"):
        xp.prepare_run([{"label": "a", "path": src, "slot": "0"}], out, tmp_path / "temp")
    xp.prepare_run([{"label": "a", "path": src, "slot": "2", "mode": "plain"}], out, tmp_path / "temp")
    body = (out / "jobs.txt").read_text(encoding="ascii")
    assert body.splitlines()[1].split("|")[5] == "2"


def test_prepare_receipt_passes_native_preflight(tmp_path):
    a = _job_file(tmp_path, "a.max", b"AAA")
    b = _job_file(tmp_path, "b.fbx", b"BBB")
    out = tmp_path / "out"
    temp = tmp_path / "temp"
    rec = xp.prepare_run(
        [{"label": "one", "path": a, "mode": "plain", "slot": "1"},
         {"label": "two", "path": b, "node": "013", "mode": "weld"}],
        out, temp)
    got = xp.preflight_jobs_txt(rec["jobs_file"], out, temp)
    assert got["nonce"] == rec["nonce"]
    assert [job["label"] for job in got["jobs"]] == ["one", "two"]
    assert got["jobs"][0]["slot"] == "1"
    assert got["jobs"][1]["node"] == "013"


def test_preflight_rejects_hardlink_output_and_duplicate_label(tmp_path):
    src = _job_file(tmp_path, "source.max", b"SCENE")
    other = _job_file(tmp_path, "other.max", b"OTHER")
    out = tmp_path / "out"
    out.mkdir()
    os.link(src, out / "a.json")
    nonce = "abc12345"
    (out / "jobs.txt").write_text(
        _jobs_text(nonce, [("a", src, "", "plain", "", ""), ("b", other, "", "plain", "", "")]),
        encoding="utf-8")
    before = _snapshot([src, other, out / "a.json", out / "jobs.txt"])
    with pytest.raises(xp.DumpError, match="alias"):
        xp.preflight_jobs_txt(out / "jobs.txt", out, tmp_path / "temp")
    assert _snapshot([src, other, out / "a.json", out / "jobs.txt"]) == before
    assert not (out / "done.txt").exists()
    assert not (out / "failed.txt").exists()

    (out / "a.json").unlink()
    (out / "jobs.txt").write_text(
        _jobs_text(nonce, [("Same", src, "", "plain", "", ""), ("same", other, "", "weld", "", "")]),
        encoding="utf-8")
    with pytest.raises(xp.DumpError, match="[Ss]ame"):
        xp.preflight_jobs_txt(out / "jobs.txt", out, tmp_path / "temp")
    assert src.read_bytes() == b"SCENE"
    assert not (out / "done.txt").exists()


def test_preflight_rejects_cross_job_hardlink(tmp_path):
    a = _job_file(tmp_path, "a.max", b"AAA")
    b = _job_file(tmp_path, "b.max", b"BBB")
    out = tmp_path / "out"
    out.mkdir()
    os.link(a, out / "b.json")
    (out / "jobs.txt").write_text(
        _jobs_text("abc12345", [("a", a, "", "plain", "", ""), ("b", b, "", "plain", "", "")]),
        encoding="utf-8")
    with pytest.raises(xp.DumpError, match="alias"):
        xp.preflight_jobs_txt(out / "jobs.txt", out, tmp_path / "temp")
    assert a.read_bytes() == b"AAA" and b.read_bytes() == b"BBB"
    assert (out / "b.json").read_bytes() == b"AAA"
    assert not (out / "failed.txt").exists()


def test_preflight_rejects_staging_hardlink(tmp_path):
    folder = tmp_path / "модель"
    folder.mkdir()
    src = _job_file(folder, "a.max", os.urandom(24))
    other = _job_file(tmp_path, "b.max", os.urandom(24))
    temp = tmp_path / "temp"
    temp.mkdir()
    dest = temp / f"xv_{sha(src)}.max"
    os.link(other, dest)
    out = tmp_path / "out"
    out.mkdir()
    (out / "jobs.txt").write_text(
        _jobs_text("abc12345", [("a", src, "", "plain", "", ""), ("b", other, "", "plain", "", "")]),
        encoding="utf-8")
    other_bytes = other.read_bytes()
    with pytest.raises(xp.DumpError, match="alias"):
        xp.preflight_jobs_txt(out / "jobs.txt", out, temp)
    assert other.read_bytes() == other_bytes
    assert dest.read_bytes() == other_bytes
    assert src.read_bytes()
    assert not (out / "failed.txt").exists()
    assert not (out / "a.json").exists()


def test_preflight_empty_jobs_txt_writes_nothing(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "jobs.txt").write_text("", encoding="ascii")
    with pytest.raises(xp.DumpError, match="nonce|no inputs"):
        xp.preflight_jobs_txt(out / "jobs.txt", out, tmp_path / "temp")
    assert list(out.iterdir()) == [out / "jobs.txt"]
    assert not (tmp_path / "temp").exists()


def test_preflight_rejects_wrong_field_count_and_does_not_delete_input(tmp_path):
    src = _job_file(tmp_path, "source.max", b"SCENE")
    out = tmp_path / "out"
    out.mkdir()
    os.link(src, out / "jobs.txt")
    with pytest.raises(xp.DumpError):
        xp.preflight_jobs_txt(out / "jobs.txt", out, tmp_path / "temp")
    assert src.read_bytes() == b"SCENE"
    assert (out / "jobs.txt").read_bytes() == b"SCENE"

    (out / "jobs.txt").write_text("#nonce:abc12345\na|C:/ascii/a.fbx|plain\n", encoding="ascii")
    with pytest.raises(xp.DumpError, match="field count"):
        xp.preflight_jobs_txt(out / "jobs.txt", out, tmp_path / "temp")
    assert not (out / "failed.txt").exists()


def test_parse_job_line_reads_slot_and_rejects_short_line():
    got = xp.parse_job_line(r"a|C:/ascii/a.fbx|013|weld|Brick|2")
    assert got["slot"] == "2" and got["node"] == "013" and got["material"] == "Brick"
    with pytest.raises(xp.DumpError, match="field count"):
        xp.parse_job_line(r"a|C:/ascii/a.fbx|013|weld|Brick")
    with pytest.raises(xp.DumpError, match="bad field"):
        xp.parse_job_line("a|C:/ascii/a.fbx|n|weld\ninjected||")


def test_ms_preflight_precedes_writes():
    text = MS.read_text(encoding="utf-8")
    pre = text.rfind("xv_preflight ")
    assert pre > 0
    assert "GetFileInformationByHandle" in text
    assert "duplicate label" in text
    assert "#nonce:" in text
    assert '\\"nonce\\":' in text
    assert "j.count >= 6" in text
    assert "j.count > 6" not in text
    assert "unmapped slot" in text
    assert 'mode:"w"' not in text
    assert pre < text.find("ready = true", pre) < text.find("createFile", pre)
    assert text.find("deleteFile", pre) > pre
    assert text.find("xv_stage", pre) > pre
    assert ".Copy" not in text[pre:]
    catch_at = text.rfind(") catch (")
    assert pre < catch_at
    assert text.find("ready", catch_at) < text.find("xv_write_failed", catch_at)


def test_repeat_run_rotates_nonce(tmp_path):
    src = _job_file(tmp_path, "m.max", b"v1")
    out = tmp_path / "out"
    temp = tmp_path / "temp"
    first = xp.prepare_run([{"label": "a", "path": src}], out, temp)
    (out / "a.json").write_text(json.dumps(full_result("a", first["nonce"])), encoding="utf-8")
    (out / "done.txt").write_text(first["nonce"] + "\n", encoding="ascii")
    assert xp.check_run(out, ["a"])["a"]["nonce"] == first["nonce"]
    second = xp.prepare_run([{"label": "a", "path": src, "mode": "weld"}], out, temp)
    assert second["nonce"] != first["nonce"]
    assert not (out / "done.txt").exists()
    assert not (out / "a.json").exists()
    assert src.read_bytes() == b"v1"
    (out / "done.txt").write_text(first["nonce"] + "\n", encoding="ascii")
    (out / "a.json").write_text(json.dumps(full_result("a", first["nonce"])), encoding="utf-8")
    with pytest.raises(xp.DumpError, match="stale"):
        xp.check_run(out, ["a"])


def test_check_run_rejects_error_null_incomplete_mismatch_and_stale(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    nonce = "abc12345"
    (out / "jobs.txt").write_text(f"#nonce:{nonce}\na|C:/ascii/a.fbx||plain||\n", encoding="utf-8")
    cases = {
        "empty": "{}",
        "error": json.dumps({"error": "checker failed"}),
        "null": "null",
        "wrong": json.dumps({"label": "wrong", "saved": True}),
        "partial": json.dumps({"label": "a", "saved": False, "nonce": nonce}),
        "threshold": json.dumps(full_result("a", nonce, tolFaces=0)),
    }
    for name, body in cases.items():
        (out / "a.json").write_text(body, encoding="utf-8")
        (out / "done.txt").write_text(nonce + "\n", encoding="ascii")
        before = (out / "a.json").read_bytes()
        with pytest.raises(xp.DumpError):
            xp.check_run(out, ["a"])
        assert (out / "a.json").read_bytes() == before, name
    (out / "a.json").write_text(json.dumps(full_result("a", nonce)), encoding="utf-8")
    (out / "done.txt").write_text("othernonce\n", encoding="ascii")
    with pytest.raises(xp.DumpError, match="stale"):
        xp.check_run(out, ["a"])
    assert set(xp.NATIVE_KEYS) == set(REQUIRED_RESULT_KEYS)


def _ntfs_id(path):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.GetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = wintypes.BOOL

    class Info(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    handle = kernel32.CreateFileW(os.fspath(path), 0x80000000, 0x7, None, 3, 0x02000000, None)
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), str(path))
    info = Info()
    try:
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise OSError(ctypes.get_last_error(), str(path))
        return (info.dwVolumeSerialNumber, info.nFileIndexHigh, info.nFileIndexLow)
    finally:
        kernel32.CloseHandle(handle)


def _same_ntfs(a, b):
    if os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b)):
        return True
    if not (os.path.exists(a) and os.path.exists(b)):
        return False
    return _ntfs_id(a) == _ntfs_id(b)


def test_probe_preflight_inode_identity(tmp_path):
    rng = random.Random(5284)
    n = 32
    ok = 0
    roles = [None, "a.json", "b.json", "done.txt", "report.jsonl", "failed.txt"]
    for i in range(n):
        root = tmp_path / f"t{i}"
        out = root / "out"
        out.mkdir(parents=True)
        a = _job_file(root, "a.max", rng.randbytes(16))
        b = _job_file(root, "b.max", rng.randbytes(16))
        duplicate = i % 5 == 0
        labels = ("a", "a") if duplicate else ("a", "b")
        role = None if duplicate else roles[i % len(roles)]
        if role:
            os.link(a, out / role)
        (out / "jobs.txt").write_text(
            _jobs_text("abc12345", [
                (labels[0], a, "", "plain", "", ""),
                (labels[1], b, "", "weld", "", ""),
            ]), encoding="utf-8")
        inputs = [a, b]
        managed = [out / "a.json", out / "b.json", out / "jobs.txt", out / "done.txt",
                   out / "report.jsonl", out / "failed.txt"]
        conflict = labels[0].casefold() == labels[1].casefold()
        if not conflict:
            for managed_path in managed:
                if any(_same_ntfs(managed_path, src) for src in inputs):
                    conflict = True
        before = {path.name: path.read_bytes() for path in out.iterdir() if path.is_file()}
        before.update({"a": a.read_bytes(), "b": b.read_bytes()})
        try:
            xp.preflight_jobs_txt(out / "jobs.txt", out, root / "temp")
            got = True
        except xp.DumpError:
            got = False
        after = {path.name: path.read_bytes() for path in out.iterdir() if path.is_file()}
        after.update({"a": a.read_bytes(), "b": b.read_bytes()})
        if got is (not conflict) and before == after and not (root / "temp").exists():
            ok += 1
    assert ok == n, f"preflight inode identity: {ok}/{n}"


def test_probe_fields_reject_controls(tmp_path):
    rng = random.Random(5285)
    n = 40
    ok = 0
    alphabet = list("abcdn") + ["|", "\n", "\r", "\t"]
    for i in range(n):
        root = tmp_path / f"t{i}"
        root.mkdir()
        src = _job_file(root, "m.max", b"SCENE")
        blob = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 6)))
        if not any(ch.isalpha() for ch in blob):
            blob = "a" + blob
        target = "label" if i % 2 == 0 else "node"
        bad = any(ord(ch) < 32 or ch == "|" for ch in blob)
        if target == "label" and (bad is False) and blob in {".", ".."}:
            bad = True
        job = {"label": blob if target == "label" else "a", "path": src, "mode": "plain"}
        if target == "node":
            job["node"] = blob
        out = root / "out"
        try:
            xp.prepare_run([job], out, root / "temp")
            got = True
        except xp.DumpError:
            got = False
        written = (out / "jobs.txt").exists()
        if (got is not bad) and (written is got) and src.read_bytes() == b"SCENE":
            ok += 1
    assert ok == n, f"field controls: {ok}/{n}"


def test_probe_slot_binding():
    rng = random.Random(5286)
    n = 80
    ok = 0
    for _ in range(n):
        sub = rng.randint(1, 6)
        present = [rng.random() < 0.7 for _ in range(sub)]
        if rng.random() < 0.5:
            slot = ""
        elif rng.random() < 0.5:
            slot = str(rng.randint(1, sub + 2))
        else:
            slot = rng.choice(["0", "01", "glass", "2mm", "1\n", "|"])
        if slot == "":
            expect = ""
        elif (not slot.isdigit()) or slot[0] == "0":
            expect = None
        else:
            ident = int(slot)
            expect = None if ident < 1 or ident > sub or not present[ident - 1] else slot
        try:
            got = xp.bind_slot(slot, sub, present)
        except xp.DumpError as exc:
            got = None
            assert slot in str(exc) or repr(slot) in str(exc)
        if got == expect:
            ok += 1
    assert ok == n, f"slot binding: {ok}/{n}"
