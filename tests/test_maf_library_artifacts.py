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
    blank = []
    for key, row in rows.items():
        assert row["ok"], (key, row)
        for field in ("max_path", "fbx_path", "preview_path"):
            path = Path(row[field])
            assert path.is_file() and path.stat().st_size > 0, (key, field)
        with Image.open(row["preview_path"]) as image:
            pixels = list(image.convert("RGB").resize((64, 64)).getdata())
        background = pixels[0]
        foreground = sum(
            sum(abs(a - b) for a, b in zip(pixel, background)) > 12
            for pixel in pixels
        )
        if foreground < 8:
            blank.append(key)
    assert not blank, f"blank previews ({len(blank)}): {blank}"
