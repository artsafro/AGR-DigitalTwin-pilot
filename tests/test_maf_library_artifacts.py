"""Opt-in real-output regression for issue #183; no user binaries are fixtures.

Set AGR_MAF_VERIFY_BUILT to a build JSONL to check every final artifact. This
is an internal-library check, not NPM/VPM delivery acceptance.
"""
import json
import os
from pathlib import Path

import pytest
from PIL import Image


def test_real_maf_library_artifacts():
    manifest = os.environ.get("AGR_MAF_VERIFY_BUILT")
    if not manifest:
        pytest.skip("set AGR_MAF_VERIFY_BUILT for the local DCC library")
    rows = {}
    for line in Path(manifest).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        rows[row["id"]] = row
    assert rows, "empty build manifest"
    plan_path = os.environ.get("AGR_MAF_VERIFY_PLAN")
    if plan_path:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        expected = {entry["id"]: entry for entry in plan["entries"]}
        assert set(rows) == set(expected), "missing or extra MAF outputs"
        for key, row in rows.items():
            assert row["tris_built"] == expected[key]["tris"], key
    for field in ("max_path", "fbx_path", "preview_path"):
        assert len({row[field] for row in rows.values()}) == len(rows), field
    blank = []
    for key, row in rows.items():
        assert row["ok"], (key, row)
        for field in ("max_path", "fbx_path", "preview_path"):
            path = Path(row[field])
            assert path.is_file() and path.stat().st_size > 0, (key, field)
        with Image.open(row["preview_path"]) as image:
            thumb = image.convert("RGB").resize((64, 64))
            pixels = [thumb.getpixel((x, y)) for y in range(64) for x in range(64)]
        background = pixels[0]
        foreground = sum(
            sum(abs(a - b) for a, b in zip(pixel, background)) > 12
            for pixel in pixels
        )
        if foreground < 8:
            blank.append(key)
    assert not blank, f"blank previews ({len(blank)}): {blank}"


def test_native_maf_library_renderability():
    path = os.environ.get("AGR_MAF_VERIFY_NATIVE")
    if not path:
        pytest.skip("set AGR_MAF_VERIFY_NATIVE for native Max readback")
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["entries"]
    assert rows
    disabled = [row["id"] for row in rows if not row["renderable"]]
    assert not disabled, f"library objects saved non-renderable: {disabled}"
    assert all(row["meshes"] == 1 for row in rows)
