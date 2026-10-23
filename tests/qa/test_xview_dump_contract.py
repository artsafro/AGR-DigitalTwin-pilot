"""#528 shared Max xView runner: contract of tools/qa/xview_dump.ms and the parity wrapper.

Max is not launched. SYNTHETIC files only. The .ms text must name the measured behaviour
(load .max, never save, decode 5 mm / 2 mm, weld on Editable Mesh). Python probes cover
SHA-256 copies, the inclusive 2 mm weld, and fail-closed path / key / material rules.
"""
import hashlib
import importlib.util
import json
import math
import os
import random
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
