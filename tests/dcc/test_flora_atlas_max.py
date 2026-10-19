"""Headless 3ds Max check: one Flora atlas on a synthetic placed scene."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image


pytestmark = pytest.mark.dcc

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
