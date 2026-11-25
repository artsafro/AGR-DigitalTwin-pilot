"""new-case: synthetic acceptance and refusal probes for the offline OKS sheet."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FONT = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf"
if os.name != "nt":
    FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def put(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path):
    scene = tmp_path / "synthetic.fbx"
    scene.write_bytes(b"synthetic fixture: scene identity only")
    split = tmp_path / "split.json"
    plan = tmp_path / "recipe.json"
    evidence = tmp_path / "reference.json"
    put(evidence, {"synthetic": True})
    s = {
        "schema": "agr-oks-split/1", "status": "accepted", "object": "Учебный ОКС",
        "scene_sha256": sha(scene), "approval_ref": "Synthetic fixture acceptance",
        "layers": ["01_ТЕЛО", "04_ВИТРАЖИ", "09_ВНУТРЕННЕЕ"],
        "objects": [
            {"name": str(i), "layer": layer, "family": family}
            for i, (layer, family) in enumerate([
                ("01_ТЕЛО", "Стена"), ("01_ТЕЛО", "Стена"), ("04_ВИТРАЖИ", "Панель"),
                ("04_ВИТРАЖИ", "Шов"), ("09_ВНУТРЕННЕЕ", "Панель"),
            ])
        ],
    }
    put(split, s)
    p = {
        "schema": "agr-oks-modelling-recipe/1", "split_sha256": sha(split), "profile": "npm",
        "simplification_cm": 7, "simplification": "Плоские стены; мелкие ниши объединить; декор — примитивы.",
        "typical_floors": "Этажи 2–4: один модуль; первый — отдельно.",
        "expected_triangles": 1000, "planning_ceiling_triangles": 150000,
        "comparison": "Учебное сравнение, не реальный объект.",
        "rows": [
            dict(layer=layer, family=family, representation=mode, reason="Учебный пример")
            for layer, family, mode in [
                ("01_ТЕЛО", "Стена", "geometry"), ("04_ВИТРАЖИ", "Панель", "inset"),
                ("04_ВИТРАЖИ", "Шов", "texture"), ("09_ВНУТРЕННЕЕ", "Панель", "not_shown"),
            ]
        ],
    }
    put(plan, p)
    return scene, split, plan, evidence, s, p


def cli(inputs, out, *extra):
    scene, split, recipe, evidence, _, _ = inputs
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "tools/methods/body/modelling_plan.py"),
         str(split), str(scene), str(recipe), str(out), "--font", str(FONT),
         "--evidence", str(evidence), *extra], cwd=out.parent, capture_output=True,
        encoding="utf-8", check=False,
    )


def test_accepted_split_fresh_cli(inputs, tmp_path):
    out = tmp_path / "sheet"
    result = cli(inputs, out)
    assert result.returncode == 0, result.stderr
    data = json.loads((out / "modelling_plan.json").read_bytes())
    assert data["status"] == "pending_picture_acceptance"
    assert data["split_status"] == "accepted"
    assert data["inputs"]["split"]["sha256"] == sha(inputs[1])
    assert data["inputs"]["evidence"]["sha256"] == sha(inputs[3])
    assert [(r["representation"], r["objects"]) for r in data["rows"]] == [
        ("geometry", ["0", "1"]), ("inset", ["2"]), ("texture", ["3"]), ("not_shown", ["4"]),
    ]
    assert data["layers"] == inputs[-2]["layers"]
    assert data["expected_triangles"] == 1000
    with Image.open(out / "modelling_plan.png") as image:
        assert image.format == "PNG" and image.width >= 1500 and image.height >= 500
        assert image.getextrema()[0][0] != image.getextrema()[0][1]


def test_preview_requires_opt_in(inputs, tmp_path):
    _, split, recipe, _, s, p = inputs
    s.update(status="proposed", approval_ref=None)
    put(split, s)
    p["split_sha256"] = sha(split)
    put(recipe, p)
    out = tmp_path / "sheet"
    assert cli(inputs, out).returncode == 2
    assert not out.exists()
    result = cli(inputs, out, "--preview")
    assert result.returncode == 0, result.stderr
    assert json.loads((out / "modelling_plan.json").read_bytes())["status"] == "draft_unaccepted_split"


@pytest.mark.parametrize(("where", "key", "value", "hint"), [
    ("split", "objects", [], "objects"), ("split", "layers", [], "layers"),
    ("split", "status", "failed", "status"), ("split", "approval_ref", None, "approval_ref"),
    ("split", "scene_sha256", "0" * 64, "scene_sha256"),
    ("split", "object", None, "object"),
    ("recipe", "split_sha256", "0" * 64, "split_sha256"),
    ("recipe", "simplification_cm", float("nan"), "NaN"),
    ("recipe", "simplification_cm", float("inf"), "Infinity"),
    ("recipe", "expected_triangles", 150000, "ceiling"),
    ("recipe", "planning_ceiling_triangles", 150001, "ceiling"),
    ("recipe", "typical_floors", "", "typical_floors"),
    ("recipe", "rows", "missing", "Шов"),
    ("recipe", "rows", "extra", "Лишнее"),
    ("recipe", "rows", "duplicate", "duplicate"),
    ("recipe", "rows", "unsupported", "representation"),
    ("recipe", "rows", "truncated", "reason"),
    ("split", "objects", "duplicate", "duplicate"),
    ("split", "objects", "unknown", "99_НЕТ"),
    ("split", "objects", "unresolved", "00_РЕШИТЬ_ЧЕЛОВЕКУ"),
])
def test_invalid_does_not_publish(inputs, tmp_path, where, key, value, hint):
    from tools.methods.body.modelling_plan import generate

    scene, split, recipe, evidence, s, p = inputs
    if value == "missing":
        p["rows"].pop(2)
    elif value == "extra":
        p["rows"].append(dict(p["rows"][0], family="Лишнее"))
    elif value == "duplicate":
        doc = s if where == "split" else p
        doc[key].append(dict(doc[key][0]))
    elif value == "unsupported":
        p["rows"][-1]["representation"] = "pass"
    elif value == "truncated":
        del p["rows"][-1]["reason"]
    elif value in ("unknown", "unresolved"):
        layer = "99_НЕТ" if value == "unknown" else "00_РЕШИТЬ_ЧЕЛОВЕКУ"
        s["objects"][-1]["layer"] = layer
        if value == "unresolved":
            s["layers"].append(layer)
    else:
        (s if where == "split" else p)[key] = value
    put(split, s)
    if where == "split":
        p["split_sha256"] = sha(split)
    put(recipe, p)
    out = tmp_path / "sheet"
    with pytest.raises(ValueError, match=hint):
        generate(split, scene, recipe, out, font=FONT, evidence=evidence)
    assert not out.exists()


def test_output_collisions_and_reset(inputs, tmp_path):
    scene, split, recipe, *_ = inputs
    first = tmp_path / "first"
    assert cli(inputs, first).returncode == 0
    original = {p: sha(p) for p in (scene, split, recipe, *first.iterdir())}
    assert cli(inputs, first).returncode == 2
    assert cli(inputs, split).returncode == 2
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "modelling_plan.json").hardlink_to(split)
    partial = occupied / "modelling_plan.png.partial"
    partial.write_bytes(b"foreign partial")
    assert cli(inputs, occupied).returncode == 2
    assert partial.read_bytes() == b"foreign partial"
    assert not (occupied / "modelling_plan.png").exists()
    assert {p: sha(p) for p in original} == original
    assert cli(inputs, tmp_path / "reset").returncode == 0


def test_rechecks_input_before_publication(inputs, tmp_path, monkeypatch):
    from tools.methods.body import modelling_plan

    scene, split, recipe, evidence, *_ = inputs
    render = modelling_plan.render_sheet

    def change(*args, **kwargs):
        png = render(*args, **kwargs)
        recipe.write_bytes(recipe.read_bytes() + b"\n")
        return png

    monkeypatch.setattr(modelling_plan, "render_sheet", change)
    out = tmp_path / "sheet"
    with pytest.raises(ValueError, match="changed.*recipe"):
        modelling_plan.generate(split, scene, recipe, out, font=FONT, evidence=evidence)
    assert not out.exists()
