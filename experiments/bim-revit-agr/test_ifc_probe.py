"""Reader and fault checks for the synthetic IFC probe. No fabricated measurements."""

import hashlib, inspect, json, os, subprocess, sys, textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ifc_probe

CASES = [(name, units) for name in ("case-box", "case-bend", "case-step") for units in ("m", "mm")]
FAULTS = [("no-void", "missing host"), ("no-fill", "missing fill"), ("no-contain", "missing containment")]


def _spec(name, floors):
    eye = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    return {"id": name, "spec_version": "0.3", "profile": "npm_min",
            "frame": {"object": name, "source": "synthetic", "to_object": eye},
            "levels": [{"name": "L0", "elev_m": 0.0}, {"name": "L1", "elev_m": 3.0}, {"name": "roof", "elev_m": 6.0}],
            "floors": floors, "roof": {"parapet_h_m": 0.0}}


def _ids(ledger):
    return sorted(row["global_id"] for row in ledger["slabs"] + ledger["walls"] + ledger["openings"] + ledger["windows"])


@pytest.fixture(scope="module")
def job(tmp_path_factory):
    root = tmp_path_factory.mktemp("ifcjob")
    inputs, out = root / "inputs", root / "out"
    opening = {"wall": 0, "x_m": 1.0, "sill_m": 0.8, "w_m": 1.2, "h_m": 1.4}
    specs = {
        "case-box": _spec("case-box", [
            {"level": "L0", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]], "openings": [opening]},
            {"level": "L1", "typical_of": "L0", "repeat_to": "L1"}]),
        "case-bend": _spec("case-bend", [
            {"level": "L0", "contour": [[0, 0], [5, 0], [5, 1], [1, 1], [1, 4], [0, 4]], "openings": [opening]},
            {"level": "L1", "contour": [[0, 0], [5, 0], [5, 2], [0, 2]], "openings": [
                {"wall": 1, "x_m": 0.4, "sill_m": 0.5, "w_m": 1.0, "h_m": 1.1}]}]),
        "case-step": _spec("case-step", [
            {"level": "L0", "contour": [[0, 0], [6, 0], [5, 2], [1, 3]], "openings": [opening]},
            {"level": "L1", "contour": [[1, 1], [4, 1], [3, 3]], "openings": [
                {"wall": 0, "x_m": 0.5, "sill_m": 0.9, "w_m": 1.0, "h_m": 1.0}]}]),
    }
    before = {}
    for name, body in specs.items():
        path = inputs / name / "spec.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(body), encoding="utf-8")
        before[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    ifc_probe.run(inputs, out, repeats=3)
    after = {name: hashlib.sha256((inputs / name / "spec.json").read_bytes()).hexdigest() for name in before}
    assert after == before
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["spec_sha256"] == before
    return out, results


def test_reader_takes_only_a_path():
    assert list(inspect.signature(ifc_probe.read_ledger).parameters) == ["path"]


def test_out_refused(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "marker.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        ifc_probe.run(tmp_path / "missing", out, repeats=3)
    assert (out / "marker.txt").read_text(encoding="utf-8") == "keep"


def test_repeats_before_output(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        ifc_probe.run(tmp_path / "missing", out, repeats=1)
    assert not out.exists()


def test_delivery_never_passes(job):
    _, results = job
    assert results["delivery_passed"] is False and results["speedup_claimed"] is False
    assert "real Revit export" in results["unsupported"]
    assert all(len(item["samples"]) == 3 for item in results["spec_validate_s"].values())


@pytest.mark.parametrize("name,units", CASES)
def test_clean_case(job, name, units):
    out, results = job
    row = next(c for c in results["cases"] if c["id"] == name and c["units"] == units and c["arm"] == "clean")
    assert row["within_tolerance"] and row["counts_ok"] and len(row["intake_s"]) >= 3
    ledger = ifc_probe.read_ledger(out / "ifc" / f"{name}-{units}.ifc")
    assert ledger["issues"] == [] and ledger["schema"] == "IFC4" and ledger["synthetic_root"]
    assert abs(ledger["unit_scale_m"] - (1.0 if units == "m" else 0.001)) < 1e-12
    digest = hashlib.sha256((out / "ifc" / f"{name}-{units}.ifc").read_bytes()).hexdigest()
    saved = json.loads((out / "ledgers" / f"{name}-{units}.json").read_text(encoding="utf-8"))
    assert ledger["sha256"] == digest == row["samples"]["sha256"] == saved["sha256"]
    storeys = {item["name"]: item for item in ledger["storeys"]}
    assert abs(storeys["L0"]["world_m"][0] - 100) < 1e-3
    assert abs(storeys["L0"]["world_m"][1] + 50) < 1e-3 and abs(storeys["L0"]["world_m"][2] - 7) < 1e-3
    assert storeys["roof"]["world_m"][2] > storeys["L0"]["world_m"][2] + 1
    for slab in ledger["slabs"]:
        level = slab["name"].split(":", 1)[1]
        assert abs(storeys[level]["world_m"][2] - slab["bbox_min"][2] - 0.20) < 1e-3
        assert abs(storeys[level]["world_m"][2] - slab["bbox_max"][2]) < 1e-3
    assert any(w["volume_cut_m3"] < w["volume_uncut_m3"] - 1e-6 for w in ledger["walls"])
    windows = {item["name"].replace("window", "opening", 1): item for item in ledger["windows"]}
    for opening in ledger["openings"]:
        fill = windows[opening["name"]]
        assert (opening["bbox_min"], opening["bbox_max"]) != (fill["bbox_min"], fill["bbox_max"])
        assert opening["host_id"] and opening["fill_id"]


@pytest.mark.parametrize("field", ["host_id", "fill_id", "storey_id"])
def test_wrong_but_existing_association_is_rejected(job, field):
    out, _ = job
    ledger = ifc_probe.read_ledger(out / "ifc" / "case-box-m.ifc")
    spec = ifc_probe.Spec.model_validate_json((out.parent / "inputs/case-box/spec.json").read_text())
    if field == "storey_id":
        ledger["slabs"][0][field] = ledger["storeys"][-1]["global_id"]
    else:
        ledger["openings"][0][field] = ledger["openings"][1][field]
    assert not ifc_probe.compare(spec, ledger)["counts_ok"]


@pytest.mark.parametrize("name,units,arm,prefix", [(n, u, a, p) for n, u in CASES for a, p in FAULTS])
def test_missing_relation(job, name, units, arm, prefix):
    out, results = job
    row = next(c for c in results["cases"] if c["id"] == name and c["units"] == units and c["arm"] == arm)
    assert row["fault_ok"] and row["global_ids_kept"] and len(row["intake_s"]) == 1
    ledger = ifc_probe.read_ledger(out / "ifc" / f"{name}-{units}-{arm}.ifc")
    clean = json.loads((out / "ledgers" / f"{name}-{units}.json").read_text(encoding="utf-8"))
    other = tuple({"missing host", "missing fill", "missing containment"} - {prefix})
    assert sum(i.startswith(prefix) for i in ledger["issues"]) == 1
    assert not any(i.startswith(other) for i in ledger["issues"])
    assert ledger["sha256"] != clean["sha256"] and _ids(ledger) == _ids(clean)


@pytest.mark.parametrize("debug_env_mode", ["absent", "empty", "caller_path"])
@pytest.mark.parametrize("legacy_target_mode", ["absent", "file_collision"])
@pytest.mark.parametrize("order", ["cardinality_first", "probe_first"])
def test_collection_preserves_caller_temp_policy(tmp_path, debug_env_mode, legacy_target_mode, order):
    child_temp_root = tmp_path / "caller_temp_root"
    child_temp_root.mkdir(parents=True, exist_ok=True)
    sentinel_path = child_temp_root / "sentinel.txt"
    sentinel_content = f"sentinel-payload-{debug_env_mode}-{legacy_target_mode}-{order}"
    sentinel_path.write_text(sentinel_content, encoding="utf-8")

    if legacy_target_mode == "file_collision":
        legacy_file = child_temp_root / "pytest_temp_dir"
        legacy_file.write_text("file collision blocking mkdir", encoding="utf-8")

    child_basetemp = tmp_path / "child_basetemp"
    child_basetemp.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["TMP"] = str(child_temp_root)
    env["TEMP"] = str(child_temp_root)
    env["TMPDIR"] = str(child_temp_root)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    if debug_env_mode == "absent":
        env.pop("PYTEST_DEBUG_TEMPROOT", None)
    elif debug_env_mode == "empty":
        env["PYTEST_DEBUG_TEMPROOT"] = ""
    elif debug_env_mode == "caller_path":
        caller_debug_root = tmp_path / "caller_debug_temproot"
        caller_debug_root.mkdir(parents=True, exist_ok=True)
        env["PYTEST_DEBUG_TEMPROOT"] = str(caller_debug_root)

    cardinality_mod = Path(__file__).resolve().parent / "test_relation_cardinality.py"
    probe_mod = Path(__file__).resolve()
    assert cardinality_mod.is_file(), f"Missing module: {cardinality_mod}"
    assert probe_mod.is_file(), f"Missing module: {probe_mod}"

    if order == "cardinality_first":
        modules = [str(cardinality_mod), str(probe_mod)]
    else:
        modules = [str(probe_mod), str(cardinality_mod)]

    child_code = textwrap.dedent("""
        import os, sys, tempfile, pytest
        from pathlib import Path

        def snapshot_dir(root: Path) -> dict:
            items = {}
            if not root.exists():
                return items
            for p in sorted(root.rglob("*")):
                rel = p.relative_to(root).as_posix()
                if p.is_dir():
                    items[rel] = ("dir",)
                elif p.is_file():
                    items[rel] = ("file", p.read_bytes())
                else:
                    items[rel] = ("other",)
            return items

        mod1, mod2, basetemp_dir, temp_root_str = sys.argv[1:]
        temp_root = Path(temp_root_str).resolve()
        current_temp = Path(tempfile.gettempdir()).resolve()
        assert os.path.normcase(str(current_temp)) == os.path.normcase(str(temp_root)), (
            f"tempfile.gettempdir() mismatch: {current_temp} != {temp_root}"
        )

        initial_debug_env = os.environ.get("PYTEST_DEBUG_TEMPROOT")
        initial_snapshot = snapshot_dir(temp_root)

        pytest_args = [
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--basetemp={basetemp_dir}",
            mod1,
            mod2,
        ]

        for i in range(2):
            ret = pytest.main(pytest_args)
            assert ret == 0, f"pytest.main collection {i + 1} returned exit code {ret}"
            assert os.environ.get("PYTEST_DEBUG_TEMPROOT") == initial_debug_env, (
                f"PYTEST_DEBUG_TEMPROOT altered after collection {i + 1}: "
                f"expected {initial_debug_env!r}, got {os.environ.get('PYTEST_DEBUG_TEMPROOT')!r}"
            )
            snap = snapshot_dir(temp_root)
            assert snap == initial_snapshot, (
                f"Caller temp root snapshot changed after collection {i + 1}: "
                f"diff={set(snap.items()) ^ set(initial_snapshot.items())}"
            )
    """)

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            child_code,
            modules[0],
            modules[1],
            str(child_basetemp),
            str(child_temp_root),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"Child collection process failed with exit code {proc.returncode}.\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}"
    )
    assert sentinel_path.read_text(encoding="utf-8") == sentinel_content
    if legacy_target_mode == "file_collision":
        assert legacy_file.is_file()
        assert legacy_file.read_text(encoding="utf-8") == "file collision blocking mkdir"
    else:
        assert not (child_temp_root / "pytest_temp_dir").exists()
