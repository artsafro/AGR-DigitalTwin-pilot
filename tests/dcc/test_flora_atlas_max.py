"""Headless 3ds Max check: one Flora atlas on a synthetic placed scene."""

import hashlib
import importlib.util
import json
import os
import random
import subprocess
import sys
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


def test_job_guards_run_before_pymxs_and_writes():
    source = JOB.read_text(encoding="utf-8")
    main = source.split("def main(", 1)[1].split("\ndef ", 1)[0]
    assert main.index("preflight_job") < main.index("pymxs")
    assert main.index("preflight_job") < main.index("makedirs")
    assert main.index("preflight_job") < main.index("saveMaxFile")
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
