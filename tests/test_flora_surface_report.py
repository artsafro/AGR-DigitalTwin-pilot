"""Flora NPM/VPM surface-identity report: every species row, fail-closed, report only (#305)."""
import json

import pytest

from dt_ai.materials import flora_surface_report as report


def square(size=1.0):
    a, b, c, d = [0, 0, 0], [size, 0, 0], [size, size, 0], [0, size, 0]
    return [[a, b, c], [a, c, d]]


def quad_grid(size=1.0):
    h = size / 2
    faces = []
    for x0, y0 in ((0, 0), (h, 0), (0, h), (h, h)):
        x1, y1 = x0 + h, y0 + h
        faces += [[[x0, y0, 0], [x1, y0, 0], [x1, y1, 0]], [[x0, y0, 0], [x1, y1, 0], [x0, y1, 0]]]
    return faces


def species(latin, vpm=True):
    stem = latin.replace(" ", "_")
    return {
        "material_id": 101,
        "latin": latin,
        "objects": {"NPM": f"{stem}_NPM", "VPM": f"{stem}_VPM"},
        "vpm": {"entry_id": "x"} if vpm else None,
        "vpm_status": "available" if vpm else "none",
        "vpm_identity": "unverified" if vpm else None,
    }


def catalogue():
    return {"species": [species("Alpha a"), species("Beta b"), species("Gamma c", vpm=False),
                        species("Delta d"), species("Eps e")]}


def faces():
    holed = [f for f in quad_grid() if f != quad_grid()[0]]
    return {
        "entries": {
            "Alpha_a_NPM": {"triangles": square()},
            "Alpha_a_VPM": {"triangles": quad_grid()},
            "Beta_b_NPM": {"triangles": square()},
            "Beta_b_VPM": {"triangles": holed},
            "Gamma_c_NPM": {"triangles": square()},
            "Delta_d_NPM": {"triangles": square()},
            "Delta_d_VPM": {"triangles": [[[0, 0, 0], [1, 0, 0], [1, 1, float("nan")]]]},
        },
        "failures": [{"object": "Eps_e_VPM", "reason": "0 nodes match"}],
    }


def test_every_species_has_one_row_with_its_verdict():
    doc = report.build_report(catalogue(), faces())
    verdicts = {row["latin"]: row["verdict"] for row in doc["pairs"]}
    assert verdicts == {"Alpha a": "same", "Beta b": "different", "Gamma c": "no_vpm",
                        "Delta d": "error", "Eps e": "error"}
    assert doc["counts"] == {"species": 5, "same": 1, "different": 1, "unverified": 0, "error": 2, "no_vpm": 1}
    eps = next(row for row in doc["pairs"] if row["latin"] == "Eps e")
    assert "Eps_e_VPM" in eps["reason"] and "0 nodes match" in eps["reason"]


def test_missing_npm_faces_is_error_not_dropped():
    dump = faces()
    del dump["entries"]["Alpha_a_NPM"]
    doc = report.build_report(catalogue(), dump)
    assert [row["verdict"] for row in doc["pairs"]][0] == "error"
    assert len(doc["pairs"]) == 5


def test_empty_face_dump_gives_error_rows_never_same():
    doc = report.build_report(catalogue(), {"entries": {}, "failures": []})
    assert doc["counts"]["same"] == 0
    assert doc["counts"]["error"] == 4 and doc["counts"]["no_vpm"] == 1


@pytest.mark.parametrize("bad_catalogue, bad_faces", [
    ({}, None),
    ({"species": "x"}, None),
    ({"species": [1]}, None),
    (None, {"failures": []}),
    (None, {"entries": {}}),
    (None, []),
])
def test_malformed_inputs_raise(bad_catalogue, bad_faces):
    with pytest.raises(report.ReportError):
        report.build_report(bad_catalogue if bad_catalogue is not None else catalogue(),
                            bad_faces if bad_faces is not None else faces())


def _write_inputs(tmp_path):
    cat = tmp_path / "catalogue.json"
    dump = tmp_path / "faces.json"
    cat.write_text(json.dumps(catalogue()), encoding="utf-8")
    dump.write_text(json.dumps(faces()), encoding="utf-8")
    return cat, dump


def test_cli_writes_report_and_leaves_catalogue_unchanged(tmp_path):
    cat, dump = _write_inputs(tmp_path)
    before = cat.read_bytes()
    out = tmp_path / "out" / "report.json"
    assert report.main(["--catalogue", str(cat), "--faces", str(dump), "--out", str(out)]) == 0
    assert cat.read_bytes() == before
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["schema"] == report.SCHEMA
    assert len(doc["pairs"]) == 5
    assert len(doc["sources"]["catalogue_sha256"]) == 64


@pytest.mark.parametrize("target", ["catalogue", "faces"])
def test_cli_refuses_out_that_resolves_to_an_input(tmp_path, target):
    cat, dump = _write_inputs(tmp_path)
    victim = cat if target == "catalogue" else dump
    before = victim.read_bytes()
    alias = tmp_path / "sub" / ".." / victim.name
    assert report.main(["--catalogue", str(cat), "--faces", str(dump), "--out", str(alias)]) != 0
    assert victim.read_bytes() == before


def test_cli_bad_input_exits_nonzero_and_writes_nothing(tmp_path):
    cat, dump = _write_inputs(tmp_path)
    dump.write_text("{}", encoding="utf-8")
    out = tmp_path / "report.json"
    assert report.main(["--catalogue", str(cat), "--faces", str(dump), "--out", str(out)]) == 1
    assert not out.exists()


def test_committed_report_covers_every_catalogue_species():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    cat = json.loads((root / "library/flora/catalogue.json").read_text(encoding="utf-8"))
    doc = json.loads((root / "library/flora/vpm-surface-identity.json").read_text(encoding="utf-8"))
    assert doc["schema"] == report.SCHEMA
    assert [row["latin"] for row in doc["pairs"]] == [item["latin"] for item in cat["species"]]
    for row, item in zip(doc["pairs"], cat["species"]):
        assert (row["verdict"] == "no_vpm") == (item["vpm"] is None)
        assert row["verdict"] in report.ROW_VERDICTS
    assert doc["counts"]["species"] == len(cat["species"])
    assert all(item["vpm_identity"] in (None, "unverified") for item in cat["species"])
