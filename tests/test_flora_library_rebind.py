"""Rebind Flora library bitmap slots onto published maps (#282).

Synthetic probes below are not a planting schedule, a Max scene or an approval.

Acceptance for the production execute/CLI path guard:

| Probe | Result |
| --- | --- |
| report aliases output MAX | fail/nonzero, neither file written |
| report alias input catalogue | fail/nonzero, catalogue unchanged |
| resolved/case/relative aliases | fail before DCC |
| distinct valid report | success |
"""
import importlib.util
import json
import math
import os
import random
import subprocess
from pathlib import Path

import pytest

from dt_ai.materials import flora_catalogue as fc

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_V003 = "C:/x/flora-library/v003/flora-library-v003.max"
MAPS_ROOT = "C:/x/flora-library/v001/maps"


def _rebind():
    path = ROOT / "tools" / "flora" / "rebind_flora_library_maps.py"
    spec = importlib.util.spec_from_file_location("rebind_flora_library_maps", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalogue():
    return json.loads((ROOT / "library" / "flora" / "catalogue.json").read_text(encoding="utf-8"))


def _species(name="Tilia cordata", material_id=101, vpm=True, diffuse=None, opacity=None, status="approved"):
    slug = fc.slug(name)
    return {
        "latin": name,
        "material_id": material_id,
        "maps": {
            "diffuse": diffuse if diffuse is not None else f"{MAPS_ROOT}/{slug}/diffuse-v001.png",
            "opacity": opacity if opacity is not None else f"{MAPS_ROOT}/{slug}/opacity-v001.png",
            "review_status": status,
            "evidence": "synthetic",
        },
        "objects": {"NPM": f"{fc.slug(name)}_NPM", "VPM": f"{fc.slug(name)}_VPM" if vpm else None},
    }


def _catalogue_of(*species):
    return {"schema": "flora-library-v1", "species": list(species)}


def test_catalogue_readme_and_constant_name_v003_together():
    catalogue = _catalogue()
    readme = (ROOT / "library" / "flora" / "README.md").read_text(encoding="utf-8")
    assert catalogue["library_file"] == LIBRARY_V003
    assert fc.LIBRARY_FILE == LIBRARY_V003
    assert LIBRARY_V003 in readme
    species_ids = [item["material_id"] for item in catalogue["species"]]
    gap_ids = [item["material_id"] for item in catalogue["gaps"]["project_species_shared_stand_in"]]
    assert len(set(species_ids) | set(gap_ids)) == 76
    assert catalogue["counts"]["species"] == 61
    assert catalogue["counts"]["with_vpm"] == 38


def test_real_catalogue_plans_every_published_binding():
    rebound = _rebind()
    plan = rebound.plan_bindings(_catalogue())
    assert len(plan) == 99
    bindings = [(row["diffuse"], row["opacity"]) for row in plan]
    assert len(bindings) * 2 == 198
    ids = {row["material_id"] for row in plan}
    assert ids <= {item["material_id"] for item in _catalogue()["species"]}
    for row in plan:
        for slot in ("diffuse", "opacity"):
            path = row[slot]
            assert path.startswith(MAPS_ROOT + "/")
            assert not rebound.is_review_or_temporary(path)
            assert Path(path).name == f"{slot}-v001.png"


@pytest.mark.parametrize("kind", ["empty", "partial", "unsupported", "nan", "inf", "threshold"])
def test_plan_fails_closed(kind):
    rebound = _rebind()
    species = _species()
    if kind == "empty":
        catalogue = _catalogue_of()
    elif kind == "partial":
        species["maps"]["opacity"] = None
        catalogue = _catalogue_of(species)
    elif kind == "unsupported":
        species["maps"]["review_status"] = "pending_review"
        species["maps"]["diffuse"] = r"C:\x\t_6c48bc9d\maps\batch2\review-batch2-v001\0_d.png"
        catalogue = _catalogue_of(species)
    elif kind == "nan":
        species["material_id"] = float("nan")
        catalogue = _catalogue_of(species)
    elif kind == "inf":
        species["material_id"] = float("inf")
        catalogue = _catalogue_of(species)
    else:
        species["maps"]["diffuse"] = f"{MAPS_ROOT}/tilia-cordata"
        catalogue = _catalogue_of(species)
    with pytest.raises(rebound.RebindError):
        rebound.plan_bindings(catalogue)


def test_review_paths_never_pass_a_brute_force_probe():
    rebound = _rebind()
    rng = random.Random(282)
    roots = (
        r"C:\x\t_6c48bc9d\maps\batch2\review-batch2-v001",
        r"C:\x\temporary\flora",
        r"C:\temp\flora",
        r"C:\tmp\review",
        r"D:\Review\maps",
        MAPS_ROOT + "/../review-batch2-v001",
    )
    names = ("0_d.png", "diffuse-v001.png", "opacity-v001.png", "map.png")
    seen = 0
    for _ in range(400):
        path = str(Path(rng.choice(roots)) / rng.choice(names))
        assert rebound.is_review_or_temporary(path)
        with pytest.raises(rebound.RebindError):
            rebound.assert_published_map(path, "tilia-cordata", "diffuse")
        seen += 1
    assert seen == 400


def test_output_that_resolves_to_an_input_writes_nothing():
    rebound = _rebind()
    source = Path(r"C:\x\flora-library\v002\flora-library-v002.max")
    protected = [
        source,
        Path(r"C:\x\flora-library\v001\flora-library-v001.max"),
        Path(MAPS_ROOT) / "tilia-cordata" / "diffuse-v001.png",
    ]
    variants = [
        source,
        Path(r"C:\x\flora-library\v002\..\v002\flora-library-v002.max"),
        Path(r"C:\x\flora-library\v001\flora-library-v001.max"),
        Path(r"C:\X\FLORA-LIBRARY\V002\FLORA-LIBRARY-V002.MAX"),
        Path(MAPS_ROOT) / "tilia-cordata" / ".." / ".." / ".." / "v002" / "flora-library-v002.max",
        Path(r"C:\x\flora-library\v001\maps\tilia-cordata\diffuse-v001.png"),
        Path(r"C:\x\flora-library\v002\parts\FLORA_Union_v1-part.max"),
    ]
    rng = random.Random(282)
    for _ in range(80):
        variants.append(Path(rng.choice([
            r"C:\x\flora-library\v001",
            r"C:\x\flora-library\v002",
        ])) / rng.choice(["flora-library-v001.max", "flora-library-v002.max", "parts", "maps"]))
    written = []

    def writer(path):
        written.append(path)
        Path(path).write_bytes(b"should-not")

    for variant in variants:
        before = Path(variant).exists()
        with pytest.raises(rebound.RebindError):
            rebound.commit_new_file(variant, protected, writer)
        assert written == []
        if before and Path(variant).is_file():
            assert Path(variant).stat().st_size != 10 or b"should-not" not in Path(variant).read_bytes()[:10]


def test_commit_writes_once_and_refuses_the_second_time(tmp_path):
    rebound = _rebind()
    target = tmp_path / "flora-library-v003.max"
    calls = []

    def writer(path):
        calls.append(path)
        Path(path).write_bytes(b"v003")

    rebound.commit_new_file(target, [tmp_path / "source.max"], writer)
    assert calls == [os.fspath(target)]
    assert target.read_bytes() == b"v003"
    with pytest.raises(rebound.RebindError):
        rebound.commit_new_file(target, [tmp_path / "source.max"], writer)
    assert calls == [os.fspath(target)]
    assert target.read_bytes() == b"v003"


def test_rebind_keeps_ids_and_pivots_and_rejects_bad_snapshots():
    rebound = _rebind()
    plan = rebound.plan_bindings(_catalogue_of(_species(), _species("Betula pendula", 102, vpm=False)))
    records = {}
    for index, row in enumerate(plan):
        records[row["name"]] = {
            "diffuse": r"C:\x\t_6c48bc9d\maps\batch2\review-batch2-v001\0_d.png",
            "opacity": r"C:\x\t_6c48bc9d\maps\batch2\review-batch2-v001\0_o.png",
            "material_ids": [row["material_id"]],
            "pivot": [float(index), 12.0, 0.1],
            "triangles": 100 + index,
        }
    rebound_rows = rebound.rebind_records(records, plan)
    for name, before in records.items():
        after = rebound_rows[name]
        assert after["material_ids"] == before["material_ids"]
        assert after["pivot"] == before["pivot"]
        assert after["triangles"] == before["triangles"]
        assert after["diffuse"].startswith(MAPS_ROOT)
        assert not rebound.is_review_or_temporary(after["diffuse"])
    verdict = rebound.verdict(rebound.measure(rebound_rows, plan))
    assert verdict["passed"] is True
    assert verdict["status"] == "pass"
    assert verdict["objects_found"] == verdict["objects_expected"] == len(plan)
    assert verdict["paths_outside"] == 0
    assert verdict["bindings_matched"] == verdict["bindings_expected"] == len(plan) * 2

    partial = dict(rebound_rows)
    partial.pop(next(iter(partial)))
    assert rebound.verdict(rebound.measure(partial, plan))["passed"] is False
    assert rebound.verdict(rebound.measure({}, plan))["passed"] is False

    nan_row = dict(rebound_rows)
    first = next(iter(nan_row))
    nan_row[first] = dict(nan_row[first], pivot=[float("nan"), 0.0, 0.0])
    with pytest.raises(rebound.RebindError):
        rebound.verdict(rebound.measure(nan_row, plan))
    inf_row = dict(rebound_rows)
    inf_row[first] = dict(rebound_rows[first], triangles=float("inf"))
    with pytest.raises(rebound.RebindError):
        rebound.verdict(rebound.measure(inf_row, plan))


def test_outside_count_at_the_limit_does_not_pass():
    rebound = _rebind()
    assert rebound.exceeds(0, 0) is True
    assert rebound.exceeds(1, 1) is True
    rng = random.Random(282)
    for _ in range(200):
        limit = rng.randint(0, 12)
        value = rng.choice([limit, limit + rng.randint(0, 5), float("nan"), float("inf")])
        if isinstance(value, float) and not math.isfinite(value):
            with pytest.raises(rebound.RebindError):
                rebound.exceeds(value, limit)
        else:
            assert rebound.exceeds(value, limit) is (value >= limit)


def test_asset_hash_guard_rejects_a_changed_byte(tmp_path):
    rebound = _rebind()
    asset = tmp_path / "diffuse-v001.png"
    asset.write_bytes(b"approved-bytes")
    before = rebound.hash_files([asset])
    asset.write_bytes(b"approved-bytes-edited")
    with pytest.raises(rebound.RebindError):
        rebound.assert_hashes_unchanged(before, rebound.hash_files([asset]))
    asset.write_bytes(b"approved-bytes")
    rebound.assert_hashes_unchanged(before, rebound.hash_files([asset]))


_PASS_REPORT = {
    "status": "pass",
    "passed": True,
    "objects_found": 2,
    "objects_expected": 2,
    "bindings_matched": 4,
    "bindings_expected": 4,
    "paths_outside": 0,
}
@pytest.fixture(autouse=True)
def no_published_map_reads(monkeypatch):
    """Simulate a clean checkout without modifying any workstation assets."""
    read_bytes = Path.read_bytes

    def read_without_published_assets(path):
        normalized = str(path).replace("\\", "/").lower()
        if normalized.startswith("c:/x/flora-library/"):
            raise FileNotFoundError(f"published assets unavailable in unit tests: {path}")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_without_published_assets)


_PUBLISHED_DIFFUSE = Path(r"C:/x/flora-library/v001/maps/tilia-cordata/diffuse-v001.png")
_PUBLISHED_OPACITY = Path(r"C:/x/flora-library/v001/maps/tilia-cordata/opacity-v001.png")


def _production_scene(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(json.dumps(_catalogue_of(_species())), encoding="utf-8")
    source = tmp_path / "source.max"
    source.write_bytes(b"SOURCE-MAX")
    output = tmp_path / "flora-library-v003.max"
    report = tmp_path / "rebind-report.json"
    return catalogue, source, output, report


def _allow_dcc_to_succeed(monkeypatch, rebound, calls):
    def fake_run(command, **kwargs):
        calls["dcc"] += 1
        job = json.loads(Path(kwargs["env"]["FLORA_REBIND_JOB"]).read_text(encoding="utf-8"))
        Path(job["output"]).write_bytes(b"MAX-SCENE")
        report = Path(job["report"])
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(_PASS_REPORT), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(rebound.subprocess, "run", fake_run)


def _argv(catalogue, source, output, report):
    return ["--catalogue", str(catalogue), "--source", str(source), "--output", str(output), "--report", str(report)]


@pytest.mark.parametrize("alias", ["output", "catalogue", "resolved", "case", "relative"])
def test_production_execute_and_cli_reject_report_aliases_before_dcc(tmp_path, monkeypatch, alias):
    rebound = _rebind()
    catalogue, source, output, report = _production_scene(tmp_path)
    if alias == "output":
        report = output
    elif alias == "catalogue":
        report = catalogue
    elif alias == "resolved":
        (tmp_path / "nest").mkdir()
        report = tmp_path / "nest" / ".." / output.name
    elif alias == "case":
        report = tmp_path / "FLORA-LIBRARY-V003.MAX"
    else:
        monkeypatch.chdir(tmp_path)
        report = Path(output.name)
    calls = {"dcc": 0}
    _allow_dcc_to_succeed(monkeypatch, rebound, calls)
    before = {
        catalogue: catalogue.read_bytes(),
        source: source.read_bytes(),
        _PUBLISHED_DIFFUSE: _PUBLISHED_DIFFUSE.read_bytes(),
        _PUBLISHED_OPACITY: _PUBLISHED_OPACITY.read_bytes(),
    }
    with pytest.raises(rebound.RebindError):
        rebound.execute(str(catalogue), str(source), str(output), str(report))
    assert calls["dcc"] == 0
    assert rebound.main(_argv(catalogue, source, output, report)) != 0
    assert calls["dcc"] == 0
    for path, payload in before.items():
        assert path.read_bytes() == payload
    assert not output.exists()
    if alias != "catalogue":
        assert not Path(report).exists()


def test_production_existing_unrelated_report_is_not_replaced(tmp_path, monkeypatch):
    rebound = _rebind()
    catalogue, source, output, report = _production_scene(tmp_path)
    report.write_bytes(b"KEEP-UNRELATED")
    calls = {"dcc": 0}
    _allow_dcc_to_succeed(monkeypatch, rebound, calls)
    catalogue_bytes = catalogue.read_bytes()
    with pytest.raises(rebound.RebindError):
        rebound.execute(str(catalogue), str(source), str(output), str(report))
    assert calls["dcc"] == 0
    assert rebound.main(_argv(catalogue, source, output, report)) != 0
    assert calls["dcc"] == 0
    assert report.read_bytes() == b"KEEP-UNRELATED"
    assert catalogue.read_bytes() == catalogue_bytes
    assert not output.exists()


def test_production_distinct_report_succeeds(tmp_path, monkeypatch):
    rebound = _rebind()
    catalogue, source, output, report = _production_scene(tmp_path)
    calls = {"dcc": 0}
    _allow_dcc_to_succeed(monkeypatch, rebound, calls)
    before = {
        catalogue: catalogue.read_bytes(),
        source: source.read_bytes(),
        _PUBLISHED_DIFFUSE: _PUBLISHED_DIFFUSE.read_bytes(),
        _PUBLISHED_OPACITY: _PUBLISHED_OPACITY.read_bytes(),
    }
    result = rebound.execute(str(catalogue), str(source), str(output), str(report))
    assert result["passed"] is True
    assert result["status"] == "pass"
    assert calls["dcc"] == 1
    assert output.read_bytes() == b"MAX-SCENE"
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["passed"] is True
    assert written["status"] == "pass"
    for path, payload in before.items():
        assert path.read_bytes() == payload

    catalogue2, source2, output2, report2 = _production_scene(tmp_path / "cli")
    assert rebound.main(_argv(catalogue2, source2, output2, report2)) == 0
    assert output2.read_bytes() == b"MAX-SCENE"
    assert json.loads(report2.read_text(encoding="utf-8"))["passed"] is True
    assert catalogue2.read_bytes() == before[catalogue]
