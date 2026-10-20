"""tools/qa/xview_parity.py (#370): fail-closed on empty / partial / failed Max dumps; never overwrite the input.

All data is SYNTHETIC (hand-made dumps in the xview_dump.ms format).
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("xview_parity", ROOT / "tools" / "qa" / "xview_parity.py")
xp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xp)

NODE = {"name": "n", "class": "Editable_Poly", "verts_type": "#vertices", "faces_type": "#faces",
        "overlap_vertices": [], "overlap_faces": [], "num_verts": 4, "num_faces": 1,
        "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], "faces": [[1, 2, 3, 4]]}
DUMP = {"m_per_unit": 1, "tol_v_units": 0.002, "tol_f_units": 0.005, "nodes": [NODE]}


def write(tmp_path, dump, name="dump.json"):
    p = tmp_path / name
    p.write_text(json.dumps(dump), encoding="utf-8")
    return p


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_measured_clean_control_exits_zero(tmp_path):
    out = tmp_path / "rep.json"
    assert xp.main([str(write(tmp_path, DUMP)), "--out", str(out)]) == 0
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert len(rows) == 1 and rows[0]["equal"]


def _mut(fn):
    d = copy.deepcopy(DUMP)
    fn(d)
    return d


BAD = {
    "no_nodes": lambda d: d.update(nodes=[]),
    "nodes_missing": lambda d: d.pop("nodes"),
    "no_vertices": lambda d: d["nodes"][0].update(vertices=[], num_verts=0, faces=[], num_faces=0),
    "no_faces": lambda d: d["nodes"][0].update(faces=[], num_faces=0),
    "partial_vertices": lambda d: d["nodes"][0].update(num_verts=5),
    "partial_faces": lambda d: d["nodes"][0].update(num_faces=2),
    "checker_failed_v": lambda d: d["nodes"][0].update(verts_type="#failed"),
    "checker_failed_f": lambda d: d["nodes"][0].update(faces_type="#failed"),
    "checker_result_missing": lambda d: d["nodes"][0].pop("overlap_faces"),
    "result_id_out_of_range": lambda d: d["nodes"][0].update(overlap_faces=[2]),
    "result_id_bool": lambda d: d["nodes"][0].update(overlap_vertices=[True]),
    "face_index_fractional": lambda d: d["nodes"][0].update(faces=[[1, 2.5, 3, 4]]),
    "face_index_bool": lambda d: d["nodes"][0].update(faces=[[True, 2, 3, 4]]),
    "tolerance_nan": lambda d: d.update(tol_f_units=float("nan")),
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_empty_partial_or_failed_dump_exits_nonzero_and_writes_nothing(tmp_path, case):
    out = tmp_path / "rep.json"
    assert xp.main([str(write(tmp_path, _mut(BAD[case]))), "--out", str(out)]) == 2
    assert not out.exists()


def test_out_same_path_is_refused_input_unchanged(tmp_path):
    p = write(tmp_path, DUMP)
    h = sha(p)
    assert xp.main([str(p), "--out", str(p)]) == 2
    assert sha(p) == h


def test_out_hardlink_to_input_is_refused_input_unchanged(tmp_path):
    p = write(tmp_path, DUMP)
    alias = tmp_path / "alias.json"
    os.link(p, alias)
    h = sha(p)
    assert xp.main([str(p), "--out", str(alias)]) == 2
    assert sha(p) == h and sha(alias) == h


def test_out_distinct_existing_file_control_is_written(tmp_path):
    p = write(tmp_path, DUMP)
    other = write(tmp_path, {"old": 1}, "other.json")
    h = sha(p)
    assert xp.main([str(p), "--out", str(other)]) == 0
    assert sha(p) == h and isinstance(json.loads(other.read_text(encoding="utf-8")), list)
