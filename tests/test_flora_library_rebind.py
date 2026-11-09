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
from functools import partial
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


@pytest.fixture
def no_published_map_reads(monkeypatch):
    """Simulate a clean checkout without modifying any workstation assets."""
    read_bytes = Path.read_bytes

    def read_without_published_assets(path):
        normalized = str(path).replace("\\", "/").lower()
        if normalized.startswith("c:/x/flora-library/"):
            raise FileNotFoundError(f"published assets unavailable in unit tests: {path}")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_without_published_assets)


@pytest.fixture
def synthetic_library(tmp_path, monkeypatch, no_published_map_reads):
    """Synthetic PNGs; only filesystem discovery and the external DCC are replaced.

    Relative map paths keep pytest's temporary ancestors out of the production
    review-folder check. The real planner still validates every slot and folder.
    """
    from PIL import Image

    monkeypatch.chdir(tmp_path)
    maps_root = Path("maps")
    species_root = maps_root / "tilia-cordata"
    species_root.mkdir(parents=True)
    maps = [species_root / f"{slot}-v001.png" for slot in ("diffuse", "opacity")]
    Image.new("RGB", (2, 2), (40, 100, 20)).save(maps[0])
    Image.new("L", (2, 2), 255).save(maps[1])
    rebound = _rebind()
    monkeypatch.setattr(rebound, "MAPS_ROOT", str(maps_root))
    # The production function's default is bound at definition time.
    monkeypatch.setattr(rebound, "plan_bindings", partial(rebound.plan_bindings, maps_root=str(maps_root)))
    monkeypatch.setattr(rebound, "_preserved_paths", lambda plan, source: [source, *(str(path) for path in maps)])
    return rebound, *_production_scene(tmp_path, maps), maps


def _production_scene(tmp_path: Path, maps):
    tmp_path.mkdir(parents=True, exist_ok=True)
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(json.dumps(_catalogue_of(_species(diffuse=str(maps[0]), opacity=str(maps[1])))), encoding="utf-8")
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
def test_production_execute_and_cli_reject_report_aliases_before_dcc(tmp_path, monkeypatch, synthetic_library, alias):
    rebound, catalogue, source, output, report, maps = synthetic_library
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
        **{path: path.read_bytes() for path in maps},
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


def test_production_existing_unrelated_report_is_not_replaced(tmp_path, monkeypatch, synthetic_library):
    rebound, catalogue, source, output, report, maps = synthetic_library
    report.write_bytes(b"KEEP-UNRELATED")
    calls = {"dcc": 0}
    _allow_dcc_to_succeed(monkeypatch, rebound, calls)
    before = {path: path.read_bytes() for path in (catalogue, source, *maps)}
    with pytest.raises(rebound.RebindError):
        rebound.execute(str(catalogue), str(source), str(output), str(report))
    assert calls["dcc"] == 0
    assert rebound.main(_argv(catalogue, source, output, report)) != 0
    assert calls["dcc"] == 0
    assert report.read_bytes() == b"KEEP-UNRELATED"
    for path, payload in before.items():
        assert path.read_bytes() == payload
    assert not output.exists()


def test_production_distinct_report_succeeds(tmp_path, monkeypatch, synthetic_library):
    rebound, catalogue, source, output, report, maps = synthetic_library
    calls = {"dcc": 0}
    _allow_dcc_to_succeed(monkeypatch, rebound, calls)
    before = {
        catalogue: catalogue.read_bytes(),
        source: source.read_bytes(),
        **{path: path.read_bytes() for path in maps},
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

    catalogue2, source2, output2, report2 = _production_scene(tmp_path / "cli", maps)
    assert rebound.main(_argv(catalogue2, source2, output2, report2)) == 0
    assert output2.read_bytes() == b"MAX-SCENE"
    assert json.loads(report2.read_text(encoding="utf-8"))["passed"] is True
    assert catalogue2.read_bytes() == before[catalogue]
    assert source2.read_bytes() == before[source]
    assert calls["dcc"] == 2
    for path, payload in before.items():
        assert path.read_bytes() == payload


def test_production_generated_input_aliases_write_nothing(tmp_path, monkeypatch, synthetic_library):
    rebound, catalogue, source, output, report, maps = synthetic_library
    calls = {"dcc": 0}
    _allow_dcc_to_succeed(monkeypatch, rebound, calls)
    protected = (catalogue, source, *maps)
    before = {path: path.read_bytes() for path in protected}
    rng = random.Random(312)
    for _ in range(48):
        target = rng.choice(protected)
        absolute = target.resolve()
        alias = rng.choice([
            target,
            Path(str(absolute).upper()),
            absolute.parent / "nested" / ".." / absolute.name,
            Path(os.path.relpath(absolute)),
        ])
        with pytest.raises(rebound.RebindError):
            rebound.execute(str(catalogue), str(source), str(alias), str(report))
        assert rebound.main(_argv(catalogue, source, alias, report)) != 0
        assert calls["dcc"] == 0
        assert not output.exists() and not report.exists()
        for path, payload in before.items():
            assert path.read_bytes() == payload


@pytest.mark.parametrize("missing", [(0,), (1,), (0, 1)])
def test_production_missing_synthetic_maps_fail_closed(monkeypatch, synthetic_library, missing):
    rebound, catalogue, source, output, report, maps = synthetic_library
    for index in missing:
        maps[index].unlink()
    calls = {"dcc": 0}
    _allow_dcc_to_succeed(monkeypatch, rebound, calls)
    with pytest.raises(rebound.RebindError, match="published map is missing"):
        rebound.execute(str(catalogue), str(source), str(output), str(report))
    assert rebound.main(_argv(catalogue, source, output, report)) != 0
    assert calls["dcc"] == 0
    assert not output.exists() and not report.exists()


@pytest.mark.dcc
@pytest.mark.max
def test_published_library_readback(tmp_path):
    """Opt-in native Max readback on a copy; never rebind or save the published scene."""
    import shutil
    import sys

    if os.environ.get("DT_FLORA_LIBRARY_INTEGRATION") != "1":
        pytest.skip("requires DT_FLORA_LIBRARY_INTEGRATION=1, 3ds Max 2026, dcc_batch.py and published Flora v003/maps")
    rebound = _rebind()
    plan = rebound.plan_bindings(_catalogue())
    assets = [Path(LIBRARY_V003), *(Path(row[slot]) for row in plan for slot in ("diffuse", "opacity"))]
    required = [Path(rebound.DCC_BATCH), Path("C:/Program Files/Autodesk/3ds Max 2026/3dsmaxbatch.exe"), *assets]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        pytest.skip("missing integration prerequisites: " + ", ".join(dict.fromkeys(missing)))
    before = rebound.hash_files(assets)
    scene_copy = tmp_path / "published-copy.max"
    shutil.copy2(LIBRARY_V003, scene_copy)
    script = tmp_path / "readback.py"
    report = tmp_path / "readback.json"
    module_path = ROOT / "tools/flora/rebind_flora_library_maps.py"
    script.write_text(
        "import importlib.util, json\n"
        "from pymxs import runtime as rt\n"
        f"spec = importlib.util.spec_from_file_location('rebind', {str(module_path)!r})\n"
        "module = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n"
        f"plan = {plan!r}\n"
        "result = module.verdict(module.measure(module._snapshot(rt), plan))\n"
        f"with open({str(report)!r}, 'w') as handle: json.dump(result, handle)\n",
        encoding="utf-8",
    )
    completed = subprocess.run([
        sys.executable, rebound.DCC_BATCH, "max", "--file", str(script),
        "--scene", str(scene_copy), "--version", "2026", "--timeout", "900",
        "--out", str(tmp_path / "dcc-batch.json"),
    ], capture_output=True, text=True, timeout=960)
    rebound.assert_hashes_unchanged(before, rebound.hash_files(assets))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["passed"] is True
    assert result["objects_found"] == result["objects_expected"] == 99
    assert result["bindings_matched"] == result["bindings_expected"] == 198
    assert result["paths_outside"] == 0
