"""Headless 3ds Max check: one Flora atlas on a synthetic placed scene."""

import hashlib
import importlib.util
import itertools
import json
import os
import random
import subprocess
import sys
import types
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
MAX_BATCH = Path(r"C:/Program Files/Autodesk/3ds Max 2026/3dsmaxbatch.exe")
DCC_BATCH = Path(r"C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py")
JOB = ROOT / "tools" / "library" / "flora_atlas_max_job.py"
UV = Path(r"C:/Users/artsafro/AppData/Local/Programs/Python/Python313/Scripts/uv.exe")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _png(path: Path, color) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB" if isinstance(color, tuple) else "L", (64, 64), color).save(path)


def _job_module():
    spec = importlib.util.spec_from_file_location("flora_atlas_max_job", JOB)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _spellings(path: Path, rng: random.Random) -> Path:
    parts = list(path.parts)
    out = [parts[0]]
    for part in parts[1:-1]:
        out.append(part)
        if rng.random() < 0.3:
            out.append(".")
        if rng.random() < 0.3:
            out.extend(["zz_missing", ".."])
    name = parts[-1]
    if os.name == "nt":
        name = "".join(char.upper() if rng.random() < 0.5 else char.lower() for char in name)
    return Path(*out, name)


def _snapshot(paths: list[Path]) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in paths if path.exists()}


def _run_job(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(JOB)],
        env=env,
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _job_env(tmp_path: Path, **overrides: str) -> dict:
    scene = tmp_path / "placed.max"
    catalogue = tmp_path / "catalogue.json"
    scene_out = tmp_path / "placed-flora-atlas.max"
    result = tmp_path / "result.json"
    out = tmp_path / "atlas"
    uv = tmp_path / "uv.exe"
    scene.parent.mkdir(parents=True, exist_ok=True)
    scene.write_bytes(b"SCENE-COPY")
    catalogue.write_bytes(b'{"schema":"flora-library-v1","species":[]}')
    uv.write_bytes(b"UV-EXE")
    env = os.environ.copy()
    env.update({
        "AGR_FLORA_SCENE": str(scene),
        "AGR_FLORA_SCENE_OUT": str(scene_out),
        "AGR_FLORA_CATALOGUE": str(catalogue),
        "AGR_FLORA_OUT_DIR": str(out),
        "AGR_FLORA_ADDRESS": "SYNTH",
        "AGR_FLORA_REPO": str(ROOT),
        "AGR_UV": str(uv),
        "AGR_FLORA_RESULT": str(result),
        "AGR_FLORA_SYNTH": "0",
    })
    env.update(overrides)
    return env


def _assert_refused(completed: subprocess.CompletedProcess, before: dict[Path, bytes], absent: list[Path]) -> None:
    assert completed.returncode != 0
    assert "refusing to write" in completed.stderr
    assert "pymxs" not in completed.stderr
    for path, payload in before.items():
        assert path.read_bytes() == payload
    for path in absent:
        assert not path.exists()


def test_job_preflight_refuses_result_scene_and_catalogue_aliases(tmp_path):
    """result==scene, scene_out==catalogue, and spellings of both exit nonzero with bytes unchanged."""
    cases = []
    scene = tmp_path / "placed.max"
    catalogue = tmp_path / "catalogue.json"
    base = _job_env(tmp_path)
    cases.append({**base, "AGR_FLORA_RESULT": base["AGR_FLORA_SCENE"]})
    cases.append({
        **base,
        "AGR_FLORA_RESULT": str(_spellings(scene, random.Random(1))),
    })
    cases.append({**base, "AGR_FLORA_SCENE_OUT": base["AGR_FLORA_CATALOGUE"]})
    cases.append({
        **base,
        "AGR_FLORA_SCENE_OUT": str(_spellings(catalogue, random.Random(2))),
    })
    cases.append({**base, "AGR_FLORA_SCENE_OUT": base["AGR_FLORA_SCENE"]})
    for env in cases:
        before = _snapshot([
            Path(env["AGR_FLORA_SCENE"]),
            Path(env["AGR_FLORA_CATALOGUE"]),
            Path(env["AGR_UV"]),
        ])
        completed = _run_job(env)
        _assert_refused(completed, before, [Path(env["AGR_FLORA_OUT_DIR"])])
        result = Path(env["AGR_FLORA_RESULT"])
        scene_out = Path(env["AGR_FLORA_SCENE_OUT"])
        if result.resolve() != Path(env["AGR_FLORA_SCENE"]).resolve():
            assert not result.exists()
        if scene_out.resolve() != Path(env["AGR_FLORA_CATALOGUE"]).resolve() and scene_out.resolve() != Path(env["AGR_FLORA_SCENE"]).resolve():
            assert not scene_out.exists()


def test_job_preflight_refuses_existing_scene_out(tmp_path):
    env = _job_env(tmp_path)
    scene_out = Path(env["AGR_FLORA_SCENE_OUT"])
    scene_out.write_bytes(b"EXISTING-SCENE-OUT")
    before = _snapshot([
        Path(env["AGR_FLORA_SCENE"]),
        Path(env["AGR_FLORA_CATALOGUE"]),
        scene_out,
        Path(env["AGR_UV"]),
    ])
    completed = _run_job(env)
    _assert_refused(completed, before, [Path(env["AGR_FLORA_OUT_DIR"]), Path(env["AGR_FLORA_RESULT"])])

    spelled = _spellings(scene_out, random.Random(3))
    spelled_env = dict(env)
    spelled_env["AGR_FLORA_SCENE_OUT"] = str(spelled)
    completed = _run_job(spelled_env)
    _assert_refused(completed, before, [Path(env["AGR_FLORA_OUT_DIR"]), Path(env["AGR_FLORA_RESULT"])])


def test_job_preflight_refuses_synthetic_input_overwrite(tmp_path):
    """Synth mode must not overwrite an existing scene file or the catalogue."""
    env = _job_env(tmp_path, AGR_FLORA_SYNTH="1")
    scene = Path(env["AGR_FLORA_SCENE"])
    catalogue = Path(env["AGR_FLORA_CATALOGUE"])
    before = _snapshot([scene, catalogue, Path(env["AGR_UV"])])
    completed = _run_job(env)
    _assert_refused(
        completed,
        before,
        [Path(env["AGR_FLORA_SCENE_OUT"]), Path(env["AGR_FLORA_OUT_DIR"]), Path(env["AGR_FLORA_RESULT"])],
    )

    alias = _job_env(tmp_path / "alias", AGR_FLORA_SYNTH="1")
    alias["AGR_FLORA_SCENE"] = alias["AGR_FLORA_CATALOGUE"]
    catalogue_alias = Path(alias["AGR_FLORA_CATALOGUE"])
    payload = catalogue_alias.read_bytes()
    completed = _run_job(alias)
    _assert_refused(
        completed,
        {catalogue_alias: payload, Path(alias["AGR_UV"]): Path(alias["AGR_UV"]).read_bytes()},
        [Path(alias["AGR_FLORA_SCENE_OUT"]), Path(alias["AGR_FLORA_OUT_DIR"]), Path(alias["AGR_FLORA_RESULT"])],
    )
    assert catalogue_alias.read_bytes() == payload


def test_job_preflight_refuses_hard_link_and_planned_atlas_alias(tmp_path):
    env = _job_env(tmp_path)
    scene = Path(env["AGR_FLORA_SCENE"])
    result = Path(env["AGR_FLORA_RESULT"])
    try:
        os.link(scene, result)
    except OSError as exc:
        pytest.skip(f"hard links are not available: {exc}")
    before = _snapshot([scene, Path(env["AGR_FLORA_CATALOGUE"]), Path(env["AGR_UV"])])
    completed = _run_job(env)
    _assert_refused(completed, before, [Path(env["AGR_FLORA_OUT_DIR"])])
    assert result.read_bytes() == scene.read_bytes()

    planned = tmp_path / "planned"
    diffuse = planned / "T_SYNTH_Flora_d_1.png"
    diffuse.parent.mkdir()
    diffuse.write_bytes(b"CATALOGUE-BYTES")
    planned_env = _job_env(tmp_path / "planned-env")
    planned_env["AGR_FLORA_CATALOGUE"] = str(diffuse)
    planned_env["AGR_FLORA_OUT_DIR"] = str(planned)
    completed = _run_job(planned_env)
    assert completed.returncode != 0
    assert "refusing to write" in completed.stderr
    assert "pymxs" not in completed.stderr
    assert diffuse.read_bytes() == b"CATALOGUE-BYTES"
    assert not (planned / "flora-atlas.json").exists()
    assert not (planned / "placed-scene.json").exists()


def test_probe_job_path_aliases_never_write(tmp_path):
    job = _job_module()
    rng = random.Random(217)
    scene = tmp_path / "sub" / "Placed.max"
    scene.parent.mkdir()
    scene.write_bytes(b"SCENE-COPY")
    catalogue = tmp_path / "sub" / "catalogue.json"
    catalogue.write_bytes(b"CATALOGUE")
    uv = tmp_path / "uv.exe"
    uv.write_bytes(b"UV-EXE")
    for seed in range(32):
        variant = random.Random(seed)
        env = _job_env(tmp_path / f"probe-{seed}")
        env["AGR_FLORA_SCENE"] = str(scene)
        env["AGR_FLORA_CATALOGUE"] = str(catalogue)
        env["AGR_UV"] = str(uv)
        kind = variant.randrange(4)
        if kind == 0:
            env["AGR_FLORA_RESULT"] = str(_spellings(scene, rng))
        elif kind == 1:
            env["AGR_FLORA_SCENE_OUT"] = str(_spellings(catalogue, rng))
        elif kind == 2:
            env["AGR_FLORA_SYNTH"] = "1"
            env["AGR_FLORA_SCENE"] = str(_spellings(scene, rng))
        else:
            env["AGR_FLORA_SCENE_OUT"] = str(_spellings(Path(env["AGR_FLORA_SCENE"]), rng))
        watched = [
            scene,
            catalogue,
            uv,
            Path(env["AGR_FLORA_SCENE"]),
            Path(env["AGR_FLORA_CATALOGUE"]),
            Path(env["AGR_FLORA_RESULT"]),
            Path(env["AGR_FLORA_SCENE_OUT"]),
            Path(env["AGR_UV"]),
        ]
        before = _snapshot(watched)
        with pytest.raises(RuntimeError, match="refusing to write"):
            job.preflight_job(env)
        assert _snapshot(watched) == before
        for path in watched:
            if path not in before:
                assert not path.exists()
        assert not Path(env["AGR_FLORA_OUT_DIR"]).exists()


def test_preflight_distinct_paths_write_nothing(tmp_path):
    job = _job_module()
    env = _job_env(tmp_path)
    scene = Path(env["AGR_FLORA_SCENE"])
    scene.unlink()
    env["AGR_FLORA_SYNTH"] = "1"
    before = _snapshot([Path(env["AGR_FLORA_CATALOGUE"]), Path(env["AGR_UV"])])
    plan = job.preflight_job(env)
    assert plan["synth"] is True
    assert Path(plan["scene_out"]) == Path(env["AGR_FLORA_SCENE_OUT"])
    assert _snapshot([Path(env["AGR_FLORA_CATALOGUE"]), Path(env["AGR_UV"])]) == before
    assert not Path(env["AGR_FLORA_OUT_DIR"]).exists()
    assert not Path(env["AGR_FLORA_SCENE_OUT"]).exists()
    assert not Path(env["AGR_FLORA_RESULT"]).exists()
    assert not scene.exists()


# Retained acceptance rows (three placed species, one atlas). Previous cases stay in
# tests/test_flora_atlas_from_scene.py::test_regression_multispecies_acceptance_rows.
# - 101 Tilia cordata, UVs [[0,0],[1,0],[1,1],[0,1]], material id kept
# - 201 Spiraea japonica, UVs [[0,0],[1,0],[0.25,1]], material id kept
# - 401 Lavandula angustifolia, UVs [[0,0],[1,0],[0,1]], material id kept
# Boundary 0 and 1 are accepted. UV u=2 is rejected. One material, ids survive.
# Review round 2 rows (private synthetic files; refuse before any write):
# - AGR_FLORA_RESULT = catalogue.species[0].maps.diffuse
# - AGR_FLORA_RESULT = catalogue.species[0].maps.opacity
# - catalogue.species[0].maps.diffuse = <AGR_FLORA_OUT_DIR>/placed-scene.json
_ACCEPTANCE_FACES = (
    (101, "Tilia cordata", "tree", (220, 40, 40), [[0, 0], [1, 0], [1, 1], [0, 1]]),
    (201, "Spiraea japonica", "bush", (40, 160, 60), [[0, 0], [1, 0], [0.25, 1]]),
    (401, "Lavandula angustifolia", "flower", (90, 40, 160), [[0, 0], [1, 0], [0, 1]]),
)


def _placed_library(root: Path):
    """Three-species catalogue with diffuse, opacity and a library binary."""

    library = root / "flora-library.max"
    library.parent.mkdir(parents=True, exist_ok=True)
    library.write_bytes(b"LIBRARY-MAX")
    species = []
    objects = []
    for material_id, latin, kind, color, uvs in _ACCEPTANCE_FACES:
        slug = latin.split()[0].lower()
        diffuse = root / "maps" / slug / "diffuse.png"
        opacity = root / "maps" / slug / "opacity.png"
        _png(diffuse, color)
        _png(opacity, 255)
        species.append({
            "material_id": material_id,
            "latin": latin,
            "type": kind,
            "maps": {
                "diffuse": str(diffuse),
                "opacity": str(opacity),
                "review_status": "approved",
            },
        })
        objects.append({"name": latin, "faces": [{"material_id": material_id, "uvs": uvs}]})
    catalogue = root / "catalogue.json"
    catalogue.write_text(json.dumps({
        "schema": "flora-library-v1",
        "library_file": str(library),
        "species": species,
    }), encoding="utf-8")
    inventory = {"schema": "flora-placed-v1", "objects": objects}
    paths = {
        "diffuse": Path(species[0]["maps"]["diffuse"]),
        "opacity": Path(species[0]["maps"]["opacity"]),
        "library": library,
        "catalogue": catalogue,
    }
    return catalogue, paths, inventory


def _call_main(job, env, inventory):
    runtime = types.SimpleNamespace(
        Name=staticmethod(lambda value: value),
        objects=[],
        loadMaxFile=staticmethod(lambda *args, **kwargs: True),
        saveMaxFile=staticmethod(lambda path, quiet=True: Path(path).write_bytes(b"NEW-MAX") or True),
        resetMaxFile=staticmethod(lambda *args, **kwargs: None),
    )
    saved = dict(os.environ)
    sys.modules["pymxs"] = types.SimpleNamespace(runtime=runtime)
    job.flora_nodes = lambda rt: ["flora-node"]
    job.dump_scene = lambda rt, nodes: inventory
    job.pack = lambda *args, **kwargs: {
        "species_count": 3,
        "fill_percent": 0.1724,
        "scale_factor": 1,
        "atlas_count": 1,
        "atlas_size": 2048,
        "warnings": [],
        "material": {"name": "M_SYNTH_Flora_1", "diffuse": "d", "opacity": "o"},
        "ids": [{"material_id": row[0], "uv": [0, 0, 1, 1]} for row in _ACCEPTANCE_FACES],
    }
    job.apply_atlas = lambda *args, **kwargs: None
    job.read_back = lambda *args, **kwargs: {
        "material_ids": [101, 201, 401],
        "uv_ok": True,
        "one_material": True,
    }
    os.environ.clear()
    os.environ.update(env)
    try:
        job.main()
    finally:
        os.environ.clear()
        os.environ.update(saved)
        sys.modules.pop("pymxs", None)


def _assert_ids_and_uvs(job, inventory):
    assert [face["material_id"] for obj in inventory["objects"] for face in obj["faces"]] == [101, 201, 401]
    job.reject_unsupported_uvs(inventory)
    outside = {
        "schema": "flora-placed-v1",
        "objects": [{"name": "bad", "faces": [{"material_id": 101, "uvs": [[0, 0], [2, 0], [0, 1]]}]}],
    }
    with pytest.raises(RuntimeError, match="unsupported UV"):
        job.reject_unsupported_uvs(outside)


def test_regression_catalogue_maps_survive_every_job_write(tmp_path):
    """Receipt, inventory and scene outputs must not replace catalogue maps or the library file."""

    job = _job_module()
    cases = ("result_diffuse", "result_opacity", "inventory_diffuse")
    for mode in cases:
        root = tmp_path / mode
        catalogue, paths, inventory = _placed_library(root)
        _assert_ids_and_uvs(job, inventory)
        env = _job_env(root / "job")
        env["AGR_FLORA_CATALOGUE"] = str(catalogue)
        source = paths["opacity" if mode == "result_opacity" else "diffuse"]
        if mode == "inventory_diffuse":
            out = Path(env["AGR_FLORA_OUT_DIR"])
            out.mkdir(parents=True, exist_ok=True)
            alias = out / "placed-scene.json"
            alias.write_bytes(source.read_bytes())
            data = json.loads(catalogue.read_text(encoding="utf-8"))
            data["species"][0]["maps"]["diffuse"] = str(alias)
            catalogue.write_text(json.dumps(data), encoding="utf-8")
            source = alias
        else:
            env["AGR_FLORA_RESULT"] = str(source)
        protected = {
            paths["diffuse"]: paths["diffuse"].read_bytes(),
            paths["opacity"]: paths["opacity"].read_bytes(),
            paths["library"]: paths["library"].read_bytes(),
            catalogue: catalogue.read_bytes(),
            Path(env["AGR_FLORA_SCENE"]): Path(env["AGR_FLORA_SCENE"]).read_bytes(),
            source: source.read_bytes(),
        }
        absent = [
            Path(env["AGR_FLORA_SCENE_OUT"]),
            Path(env["AGR_FLORA_OUT_DIR"]) / "flora-atlas.json",
            Path(env["AGR_FLORA_OUT_DIR"]) / "T_SYNTH_Flora_d_1.png",
            Path(env["AGR_FLORA_OUT_DIR"]) / "T_SYNTH_Flora_o_1.png",
        ]
        if mode != "inventory_diffuse":
            absent.append(Path(env["AGR_FLORA_OUT_DIR"]) / "placed-scene.json")
        result = Path(env["AGR_FLORA_RESULT"])
        if result.resolve() != source.resolve():
            absent.append(result)
        with pytest.raises(RuntimeError, match="refusing to write"):
            _call_main(job, env, inventory)
        for path, payload in protected.items():
            assert path.read_bytes() == payload
        for path in absent:
            assert not path.exists()
        assert [face["material_id"] for obj in inventory["objects"] for face in obj["faces"]] == [101, 201, 401]


def test_probe_catalogue_inputs_never_alias_planned_writes(tmp_path):
    """Every catalogue map and the library file stays clear of every planned write, including spellings."""

    job = _job_module()
    kinds = ("diffuse", "opacity", "library")
    slots = (
        "result",
        "scene_out",
        "placed-scene.json",
        "flora-atlas.json",
        "T_SYNTH_Flora_d_1.png",
        "T_SYNTH_Flora_o_1.png",
    )
    seen = 0
    for index, (kind, slot) in enumerate(itertools.product(kinds, slots)):
        seen += 1
        root = tmp_path / f"alias-{index}"
        catalogue, paths, _inventory = _placed_library(root)
        env = _job_env(root / "job")
        env["AGR_FLORA_CATALOGUE"] = str(catalogue)
        target = paths[kind]
        payload = target.read_bytes()
        rng = random.Random(1000 + index)
        if slot in ("result", "scene_out"):
            env["AGR_FLORA_RESULT" if slot == "result" else "AGR_FLORA_SCENE_OUT"] = str(_spellings(target, rng))
            watched = target
        else:
            planned = Path(env["AGR_FLORA_OUT_DIR"]) / slot
            planned.parent.mkdir(parents=True, exist_ok=True)
            planned.write_bytes(payload)
            data = json.loads(catalogue.read_text(encoding="utf-8"))
            spelled = str(_spellings(planned, rng))
            if kind == "library":
                data["library_file"] = spelled
            else:
                data["species"][0]["maps"][kind] = spelled
            catalogue.write_text(json.dumps(data), encoding="utf-8")
            watched = planned
        before = watched.read_bytes()
        library_before = paths["library"].read_bytes()
        with pytest.raises(RuntimeError, match="refusing to write"):
            job.preflight_job(env)
        assert watched.read_bytes() == before
        assert paths["library"].read_bytes() == library_before
        assert catalogue.read_bytes()
        if slot in ("result", "scene_out"):
            assert not Path(env["AGR_FLORA_OUT_DIR"]).exists()
    assert seen == 18


def test_probe_hardlinked_catalogue_inputs_never_write(tmp_path):
    """A hard link of a diffuse, opacity or library file is still an input."""

    job = _job_module()
    seen = 0
    for index, (kind, slot) in enumerate(itertools.product(("diffuse", "opacity", "library"), ("result", "inventory"))):
        root = tmp_path / f"link-{index}"
        catalogue, paths, _inventory = _placed_library(root)
        env = _job_env(root / "job")
        env["AGR_FLORA_CATALOGUE"] = str(catalogue)
        source = paths[kind]
        try:
            if slot == "result":
                link = root / f"{kind}-result-link"
                os.link(source, link)
                env["AGR_FLORA_RESULT"] = str(link)
                watched = source
            else:
                link = Path(env["AGR_FLORA_OUT_DIR"]) / "placed-scene.json"
                link.parent.mkdir(parents=True, exist_ok=True)
                os.link(source, link)
                watched = source
        except OSError as exc:
            pytest.skip(f"hard links are not available: {exc}")
        before = watched.read_bytes()
        with pytest.raises(RuntimeError, match="refusing to write"):
            job.preflight_job(env)
        assert watched.read_bytes() == before
        assert link.read_bytes() == before
        assert not Path(env["AGR_FLORA_SCENE_OUT"]).exists()
        seen += 1
    assert seen == 6


def test_unsupported_catalogue_map_refuses_before_write(tmp_path):
    """A non-path catalogue map is not a successful preflight and creates nothing."""

    job = _job_module()
    env = _job_env(tmp_path)
    catalogue = Path(env["AGR_FLORA_CATALOGUE"])
    catalogue.write_text(json.dumps({
        "schema": "flora-library-v1",
        "library_file": 1,
        "species": [{"maps": {"diffuse": "", "opacity": None}}],
    }), encoding="utf-8")
    payload = catalogue.read_bytes()
    with pytest.raises(RuntimeError, match="refusing to write"):
        job.preflight_job(env)
    assert catalogue.read_bytes() == payload
    assert not Path(env["AGR_FLORA_OUT_DIR"]).exists()
    assert not Path(env["AGR_FLORA_RESULT"]).exists()
    assert not Path(env["AGR_FLORA_SCENE_OUT"]).exists()


def test_job_guards_run_before_pymxs_and_writes():
    source = JOB.read_text(encoding="utf-8")
    main = source.split("def main(", 1)[1].split("\ndef ", 1)[0]
    assert main.index("preflight_job") < main.index("pymxs")
    assert main.index("preflight_job") < main.index("makedirs")
    assert main.index("preflight_job") < main.index("saveMaxFile")
    preflight = source.split("def preflight_job(", 1)[1].split("\ndef ", 1)[0]
    assert preflight.index("catalogue_library_inputs") < preflight.index("_refuse_aliased_writes")
    assert main.index("reject_unsupported_uvs") < main.index("makedirs")
    assert main.index("reject_unsupported_uvs") < main.rindex("saveMaxFile")


def test_job_rejects_unsupported_uv_examples():
    job = _job_module()
    for uvs in ([[0, 0], [2, 0], [0, 1]], [[-1, 0], [1, 0], [0, 1]]):
        inventory = {"objects": [{"name": "a", "faces": [{"material_id": 101, "uvs": uvs}]}]}
        with pytest.raises(RuntimeError, match="unsupported UV"):
            job.reject_unsupported_uvs(inventory)
    job.reject_unsupported_uvs({
        "objects": [{"name": "a", "faces": [{"material_id": 101, "uvs": [[0, 0], [1, 0], [0, 1]]}]}],
    })


@pytest.mark.dcc
@pytest.mark.skipif(
    not MAX_BATCH.exists() or not DCC_BATCH.exists() or not UV.exists(),
    reason="3ds Max 2026, dcc_batch.py or uv is not installed",
)
def test_synth_scene_one_flora_atlas(tmp_path):
    maps = tmp_path / "maps"
    species = [
        ("Tilia cordata", "tree", 101, (180, 40, 40)),
        ("Spiraea japonica", "bush", 201, (40, 140, 60)),
        ("Lavandula angustifolia", "flower", 401, (90, 40, 160)),
    ]
    rows = []
    for latin, kind, material_id, color in species:
        slug = latin.lower().replace(" ", "-")
        diffuse = maps / slug / "diffuse-v001.png"
        opacity = maps / slug / "opacity-v001.png"
        _png(diffuse, color)
        _png(opacity, 255)
        rows.append({
            "material_id": material_id,
            "latin": latin,
            "type": kind,
            "maps": {
                "diffuse": str(diffuse),
                "opacity": str(opacity),
                "review_status": "approved",
            },
        })
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(json.dumps({
        "schema": "flora-library-v1",
        "species": rows,
    }), encoding="utf-8")
    out = tmp_path / "atlas"
    scene = tmp_path / "placed.max"
    scene_out = tmp_path / "placed-flora-atlas.max"
    result = tmp_path / "result.json"
    env = os.environ.copy()
    env.update({
        "AGR_FLORA_SCENE": str(scene),
        "AGR_FLORA_SCENE_OUT": str(scene_out),
        "AGR_FLORA_CATALOGUE": str(catalogue),
        "AGR_FLORA_OUT_DIR": str(out),
        "AGR_FLORA_ADDRESS": "SYNTH",
        "AGR_FLORA_REPO": str(ROOT),
        "AGR_UV": str(UV),
        "AGR_FLORA_RESULT": str(result),
        "AGR_FLORA_SYNTH": "1",
    })
    completed = subprocess.run(
        [
            sys.executable,
            str(DCC_BATCH),
            "max",
            "--file",
            str(JOB),
            "--timeout",
            "600",
            "--card",
            "t_ddb898a1",
            "--out",
            str(tmp_path / "dcc.json"),
        ],
        env=env,
        check=False,
        cwd=str(ROOT),
    )
    assert result.is_file(), completed.returncode
    receipt = json.loads(result.read_text(encoding="utf-8"))
    assert receipt["species_count"] == 3
    assert receipt["atlas_count"] == 1
    assert receipt["atlas_size"] == 2048
    assert receipt["scale_factor"] == 1
    assert 0 < receipt["fill_percent"] < 5
    assert receipt["uv_ok"] is True
    assert receipt["one_material"] is True
    assert receipt["material_name"] == "M_SYNTH_Flora_1"
    assert receipt["material_ids"] == [101, 201, 401]
    assert receipt["scene_sha256_before"] == receipt["scene_sha256_after"]
    assert _sha256(scene) == receipt["scene_sha256_after"]
    assert scene_out.is_file()
    assert scene.resolve() != scene_out.resolve()
    pngs = sorted(path.name for path in out.glob("*.png"))
    assert pngs == ["T_SYNTH_Flora_d_1.png", "T_SYNTH_Flora_o_1.png"]
    report = json.loads((out / "flora-atlas.json").read_text(encoding="utf-8"))
    assert [row["species"] for row in report["ids"]] == [item[0] for item in species]
