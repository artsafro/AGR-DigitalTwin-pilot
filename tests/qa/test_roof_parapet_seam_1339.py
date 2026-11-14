"""Issue #1339: roof/parapet seam - R6 recipe step and the K01 evidence runner (jobs/KPP1/seam-1339)."""
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

from dt_ai.geometry import from_spec
from dt_ai.geometry.from_spec import BuildInputs
from dt_ai.spec.model import Spec
import run_benchmark

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "jobs/KPP1/seam-1339/measure_roof_seam.py"
R6 = ROOT / "docs/procedure/node-r6-oks-body-facade.md"
FIXTURE = json.loads((ROOT / "tests/fixtures/spec-b01-v0.3.json").read_text(encoding="utf-8"))
INPUTS = dict(parapet_thickness_m=0.3, facade_id=3, reveal_id=6, roof_id=21, opening_id=11)


def load():
    spec = importlib.util.spec_from_file_location("measure_roof_seam_1339", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def seam():
    return load()


def roof_z():
    return next(lv["elev_m"] for lv in FIXTURE["levels"] if lv["name"] == "roof")


# --- recipe text -----------------------------------------------------------------------------------------

def seam_step():
    text = R6.read_text(encoding="utf-8")
    steps = re.findall(r"^(\d+)\. (.+)$", text, re.M)
    hits = [s for _, s in steps if "parapet" in s and "seal" in s]
    assert len(hits) == 1, hits
    return text, hits[0]


def test_r6_has_one_seam_step_with_tuck_from_the_spec_and_evidence():
    text, step = seam_step()
    for clause in ("own plate", "plate_overlap_m", "plate_gap_m", "D038", "D039", "11 mm", "not a default"):
        assert clause in step, clause
    for link in ("../../jobs/PSU275/STATE.md", "../../jobs/KPP1/seam-1339/README.md",
                 "../domain/patterns/roof-inset-plane.md"):
        assert f"]({link})" in step, link
    assert "## Definition of done" in text


def test_r6_seam_done_criteria_name_quads_t_junctions_and_closed_shell():
    text = R6.read_text(encoding="utf-8")
    done = text.split("## Definition of done", 1)[1]
    for clause in ("quads", "T-junctions 0", "slabs_not_inset", "two open loops", "non-manifold 0"):
        assert clause in done, clause


def test_evidence_readme_numbers_match_the_committed_report():
    folder = SCRIPT.parent
    report = json.loads((folder / "seam-report.json").read_text(encoding="utf-8"))
    rows = {r["variant"]: r for r in report["variants"]}
    assert set(rows) == {"welded", "separate"}
    readme = (folder / "README.md").read_text(encoding="utf-8")
    for row in rows.values():
        assert row["stopped"] is None
        assert f"{row['readback']['quads']:,}".replace(",", " ") in readme
    assert rows["separate"]["readback"]["quads"] < rows["welded"]["readback"]["quads"]
    assert rows["separate"]["readback"]["t_junctions"] == 0
    assert rows["separate"]["mesh"]["status"] == "pass" and rows["welded"]["mesh"]["status"] == "fail"


# --- the runner: engines --------------------------------------------------------------------------------

def test_welded_engine_welds_the_roof_and_the_separate_one_insets_it(seam):
    spec = Spec.model_validate(FIXTURE)
    welded = seam.welded_engine()
    after = from_spec.build(spec, BuildInputs(**INPUTS))
    before = welded.build(Spec.model_validate(FIXTURE), welded.BuildInputs(**INPUTS))
    z = roof_z()
    m_after, m_before = seam.measure(after, z), seam.measure(before, z)
    assert m_after["t_junctions"] == 0 and m_before["t_junctions"] == 0
    assert m_after["quads"] < m_before["quads"]               # facade cuts no longer cross the roof
    assert m_after["roof_band_triangles"] < m_before["roof_band_triangles"]
    plate = [v for v in after["meshes"][0]["vertices"] if abs(v[2] - (z + FIXTURE.get("plate_gap_m", 0.005))) < 1e-6]
    assert plate, "the separate variant has no plate above the roof level"
    assert not [v for v in before["meshes"][0]["vertices"] if abs(v[2] - (z + 0.005)) < 1e-6]


def test_welded_engine_fails_closed_when_the_line_is_not_there_once(seam, monkeypatch, tmp_path):
    src = Path(from_spec.__file__).read_text(encoding="utf-8")
    for n, text in ((0, src.replace(seam.WELD_FROM, "")), (2, src + "\n" + seam.WELD_FROM)):
        fake = tmp_path / f"from_spec_{n}.py"
        fake.write_text(text, encoding="utf-8")
        monkeypatch.setattr(seam.from_spec, "__file__", str(fake))
        with pytest.raises(RuntimeError, match=f"occurs {n} times"):
            seam.welded_engine()


def test_engine_swaps_and_restores_run_benchmark_and_rejects_unknown_variants(seam):
    saved = run_benchmark.build, run_benchmark.BuildInputs, run_benchmark.BuildError
    with seam.engine("welded"):
        assert run_benchmark.build is not saved[0]
        assert run_benchmark.BuildError.__module__ == run_benchmark.build.__module__
    assert (run_benchmark.build, run_benchmark.BuildInputs, run_benchmark.BuildError) == saved
    with pytest.raises(RuntimeError):
        with seam.engine("separate"):
            raise RuntimeError("inside")
    assert (run_benchmark.build, run_benchmark.BuildInputs, run_benchmark.BuildError) == saved
    for bad in ("", "Welded", "both", None):
        with pytest.raises(ValueError, match="unknown variant"):
            with seam.engine(bad):
                pass


# --- the runner: measure fails closed ---------------------------------------------------------------------

def quad_dump(z=1.0, extra=()):
    verts = [[0, 0, z], [1, 0, z], [1, 1, z], [0, 1, z], *extra]
    return {"meshes": [{"name": "body", "vertices": verts, "triangles": [[0, 1, 2], [0, 2, 3]],
                        "polygon_sizes": [4]}]}


@pytest.mark.parametrize("dump, z, message", [
    ({"meshes": []}, 1.0, "one mesh 'body'"),
    ({"meshes": [{"name": "decor", "vertices": [[0, 0, 0]], "triangles": [[0, 0, 0]]}]}, 1.0, "one mesh 'body'"),
    ({"meshes": [{"name": "body"}, {"name": "body"}]}, 1.0, "one mesh 'body'"),
    ({"meshes": [{"name": "body", "vertices": [], "triangles": []}]}, 1.0, "empty"),
    (quad_dump(z=math.nan), 1.0, "non-finite"),
    (quad_dump(extra=[[math.inf, 0, 0]]), 1.0, "non-finite"),
    (quad_dump(), math.nan, "not a finite"),
    (quad_dump(), math.inf, "not a finite"),
    (quad_dump(), None, "not a finite"),
])
def test_measure_rejects_missing_empty_and_non_finite_input(seam, dump, z, message):
    with pytest.raises(ValueError, match=message):
        seam.measure(dump, z)


def test_measure_roof_band_is_inclusive_at_the_threshold_and_excludes_beyond(seam):
    at = seam.measure(quad_dump(z=seam.ROOF_BAND_M), 0.0)
    beyond = seam.measure(quad_dump(z=seam.ROOF_BAND_M + 1e-3), 0.0)
    assert (at["roof_band_triangles"], beyond["roof_band_triangles"]) == (2, 0)
    assert at["quads"] == 1 and at["t_junctions"] == 0


def test_measure_counts_a_t_junction(seam):
    # two quads side by side; the right one is split in two, its middle vertex lies on the left quad's edge
    verts = [[0, 0, 0], [1, 0, 0], [1, 2, 0], [0, 2, 0], [2, 0, 0], [2, 1, 0], [1, 1, 0], [2, 2, 0]]
    tris = [[0, 1, 2], [0, 2, 3], [1, 4, 5], [1, 5, 6], [6, 5, 7], [6, 7, 2]]
    dump = {"meshes": [{"name": "body", "vertices": verts, "triangles": tris, "polygon_sizes": [4, 4, 4]}]}
    assert seam.measure(dump, 5.0)["t_junctions"] >= 1


# --- the runner: CLI paths --------------------------------------------------------------------------------

def test_cli_never_writes_into_or_over_the_etalon(seam, tmp_path):
    etalon = tmp_path / "copy" / "SM_Kpp_1.fbx"
    etalon.parent.mkdir()
    etalon.write_bytes(b"fbx")
    before = sorted(p.name for p in tmp_path.rglob("*"))
    for out in (etalon, etalon.parent, tmp_path, tmp_path / "copy" / ".." / "copy"):
        assert seam.main(["--etalon", str(etalon), "--output", str(out), "--blender", "none"]) == 2
    assert seam.main(["--etalon", str(tmp_path / "missing.fbx"), "--output", str(tmp_path / "new")]) == 2
    assert sorted(p.name for p in tmp_path.rglob("*")) == before
    assert etalon.read_bytes() == b"fbx"
