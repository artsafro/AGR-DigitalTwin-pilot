"""Additional public-boundary regressions for review publication (synthetic data)."""
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest

from test_review_publish import FakeAdapter, _fbx, _png, _load


@pytest.fixture
def review():
    return _load("common")


def publish(review, root, source, slug="safe"):
    return review.publish(task="348", slug=slug, source=source, what="Проверить модель.",
                          pngs=[], review_root=root, adapter=FakeAdapter(), today=date(2026, 10, 20))


def test_hardlink_pending_alias_is_untouched(review, tmp_path):
    root = tmp_path / "review"
    root.mkdir()
    source = tmp_path / "model.max"
    source.write_bytes(b"[]")
    os.link(source, root / "pending.json")
    with pytest.raises(review.ReviewError):
        publish(review, root, source)
    assert source.read_bytes() == b"[]"
    assert list(root.iterdir()) == [root / "pending.json"]


def test_symlink_escape_writes_nothing(review, tmp_path):
    root = tmp_path / "review"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    try:
        (root / "2026-10-20").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    source = tmp_path / "model.fbx"
    _fbx(source)
    with pytest.raises(review.ReviewError):
        publish(review, root, source)
    assert not list(outside.iterdir())
    assert not (root / "pending.json").exists()


@pytest.mark.parametrize("raw", [b'[NaN]', b'[{"task":"#1","task":"#2"}]', b'[{"path":Infinity}]'])
def test_invalid_json_preserves_bytes(review, tmp_path, raw):
    root = tmp_path / "review"
    root.mkdir()
    (root / "pending.json").write_bytes(raw)
    source = tmp_path / "model.fbx"
    _fbx(source)
    with pytest.raises(review.ReviewError):
        publish(review, root, source)
    assert (root / "pending.json").read_bytes() == raw
    assert list(root.iterdir()) == [root / "pending.json"]


def test_parallel_append_preserves_all_entries(review, tmp_path):
    root = tmp_path / "review"
    source = tmp_path / "model.fbx"
    _fbx(source)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: publish(review, root, source, f"parallel-{i}"), range(24)))
    assert results == [0] * 24
    rows = json.loads((root / "pending.json").read_text(encoding="utf-8"))
    assert len(rows) == 24
    assert len({row["path"] for row in rows}) == 24


def test_cleanup_ignores_files_and_resolves_relative_manifest_paths(review, tmp_path):
    from datetime import datetime
    scratch = tmp_path / "x"
    scratch.mkdir()
    file = scratch / "t_file"
    file.write_bytes(b"keep")
    ground = scratch / "t_assets" / "surface"
    ground.mkdir(parents=True)
    (ground / "keep").write_bytes(b"keep")
    manifest = tmp_path / "library.json"
    manifest.write_text(json.dumps({"scene": "x/t_assets/surface/model.max"}), encoding="utf-8")
    os.utime(file, (0, 0))
    os.utime(ground.parent, (0, 0))
    assert review.cleanup(days=1, scratch=scratch, manifests=[manifest], now=datetime.now(), apply=True) == []
    assert file.read_bytes() == b"keep"
    assert (ground / "keep").read_bytes() == b"keep"


def test_render_failure_never_fabricates_preview():
    """A missing renderer is an error, not an invented image of the asset."""
    job = _load("max_job")
    class Runtime:
        def execute(self, code):
            raise RuntimeError("renderer unavailable")
    with pytest.raises(RuntimeError, match="renderer unavailable"):
        job.render_preview(Runtime(), Path("missing.png"))
