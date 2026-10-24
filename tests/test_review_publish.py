"""Visual review publication (#348): Max folder, pending.json, verdict, scratch cleanup."""
import importlib.util
import json
import math
import os
import random
import struct
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "tools" / "review"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"review_{name}", REVIEW / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def review():
    sys.path.insert(0, str(REVIEW))
    return _load("common")


def _png(path: Path, rgb=(20, 40, 60)) -> None:
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"\x00" + bytes(rgb)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _fbx(path: Path, payload: bytes = b"Kaydara FBX Binary\x00") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _snapshot(root: Path) -> dict[str, bytes]:
    found = {}
    if not root.exists():
        return found
    for path in root.rglob("*"):
        if path.is_file():
            found[str(path.resolve())] = path.read_bytes()
    return found


def _publish(review, tmp_path, adapter, **overrides):
    fbx = tmp_path / "in" / "model.fbx"
    _fbx(fbx)
    png = tmp_path / "in" / "view.png"
    _png(png)
    args = dict(
        task="348",
        slug="ground-v014",
        source=fbx,
        what="Проверить масштаб и материалы.",
        pngs=[png],
        review_root=tmp_path / "review",
        adapter=adapter,
        today=datetime(2026, 10, 20).date(),
    )
    args.update(overrides)
    return review.publish(**args)


class FakeAdapter:
    def __init__(self, fail: Exception | None = None):
        self.fail = fail
        self.calls = []

    def build(self, source: Path, max_out: Path, preview_png: Path | None) -> dict:
        self.calls.append((Path(source), Path(max_out), None if preview_png is None else Path(preview_png)))
        if self.fail:
            raise self.fail
        max_out.parent.mkdir(parents=True, exist_ok=True)
        max_out.write_text("FAKEMAX cameras=1 materials=1\n", encoding="utf-8")
        if preview_png is not None and not preview_png.exists():
            _png(preview_png, (1, 2, 3))
        return {"version": "3ds Max 2026 (fake)", "cameras": 1, "materials": 1}


def test_publish_creates_review_folder_and_appends_pending(review, tmp_path):
    adapter = FakeAdapter()
    fbx = tmp_path / "in" / "model.fbx"
    png = tmp_path / "in" / "view.png"
    _fbx(fbx, b"Kaydara FBX Binary\x00ground")
    _png(png)
    root = tmp_path / "review"
    pending = root / "pending.json"
    pending.parent.mkdir(parents=True)
    pending.write_text(
        json.dumps([{"task": "#1", "path": "C:/x/review/old.max", "what": "старое"}], ensure_ascii=False),
        encoding="utf-8",
    )
    before = json.loads(pending.read_text(encoding="utf-8"))
    code = review.publish(
        task="348",
        slug="ground-v014",
        source=fbx,
        what="Проверить Ground v014.",
        pngs=[png],
        review_root=root,
        adapter=adapter,
        today=datetime(2026, 10, 20).date(),
    )
    assert code == 0
    folder = root / "2026-10-20" / "348-ground-v014"
    scene = folder / "348-ground-v014.max"
    assert scene.is_file() and "FAKEMAX" in scene.read_text(encoding="utf-8")
    assert (folder / "view.png").read_bytes() == png.read_bytes()
    readme = (folder / "README.txt").read_text(encoding="utf-8")
    assert "Проверить Ground v014." in readme
    assert "Acceptance points" in readme
    assert "1 unit = 1 m" in readme
    assert "Z-up" in readme
    assert "MSK" in readme
    assert "3ds Max 2026 (fake)" in readme
    assert adapter.calls and adapter.calls[0][0] == fbx.resolve()
    rows = json.loads(pending.read_text(encoding="utf-8"))
    assert rows[0] == before[0]
    assert rows[1]["task"] == "#348"
    assert rows[1]["what"] == "Проверить Ground v014."
    assert rows[1]["path"].endswith("348-ground-v014.max")
    assert rows[1]["path"].startswith(root.resolve().as_posix()) or "348-ground-v014.max" in rows[1]["path"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"source_name": "missing.fbx", "make": False},
        {"what": ""},
        {"what": "   "},
        {"what": "line\nbreak"},
        {"slug": "../outside"},
        {"slug": ".."},
        {"slug": "a/b"},
        {"slug": "a\\b"},
        {"task": ""},
        {"task": "0"},
        {"task": "-1"},
        {"task": "nan"},
        {"task": "inf"},
        {"task": "1.5"},
    ],
)
def test_fail_closed_publish_writes_nothing(review, tmp_path, kwargs):
    root = tmp_path / "review"
    root.mkdir()
    sentinel = root / "pending.json"
    sentinel.write_text("[]", encoding="utf-8")
    fbx = tmp_path / "model.fbx"
    if kwargs.get("make", True):
        _fbx(fbx)
    else:
        fbx = tmp_path / kwargs["source_name"]
    before = _snapshot(root)
    source_before = fbx.read_bytes() if fbx.exists() else None
    with pytest.raises(review.ReviewError):
        review.publish(
            task=kwargs.get("task", "348"),
            slug=kwargs.get("slug", "ground-v014"),
            source=fbx,
            what=kwargs.get("what", "Смотреть модель."),
            pngs=[],
            review_root=root,
            adapter=FakeAdapter(),
            today=datetime(2026, 10, 20).date(),
        )
    assert _snapshot(root) == before
    if source_before is not None:
        assert fbx.read_bytes() == source_before


def test_missing_png_and_empty_source_write_nothing(review, tmp_path):
    root = tmp_path / "review"
    root.mkdir()
    (root / "pending.json").write_text("[]", encoding="utf-8")
    before = _snapshot(root)
    empty = tmp_path / "empty.fbx"
    empty.write_bytes(b"")
    with pytest.raises(review.ReviewError):
        review.publish(
            task="4",
            slug="empty",
            source=empty,
            what="текст",
            pngs=[],
            review_root=root,
            adapter=FakeAdapter(),
            today=datetime(2026, 10, 20).date(),
        )
    missing_png = tmp_path / "model.fbx"
    _fbx(missing_png)
    with pytest.raises(review.ReviewError):
        review.publish(
            task="4",
            slug="png",
            source=missing_png,
            what="текст",
            pngs=[tmp_path / "nope.png"],
            review_root=root,
            adapter=FakeAdapter(),
            today=datetime(2026, 10, 20).date(),
        )
    assert _snapshot(root) == before
    assert empty.read_bytes() == b""


def test_malformed_pending_is_untouched(review, tmp_path):
    root = tmp_path / "review"
    root.mkdir()
    pending = root / "pending.json"
    raw = b'{"task":'
    pending.write_bytes(raw)
    fbx = tmp_path / "model.fbx"
    _fbx(fbx)
    with pytest.raises(review.ReviewError):
        review.publish(
            task="9",
            slug="ok",
            source=fbx,
            what="текст",
            pngs=[],
            review_root=root,
            adapter=FakeAdapter(),
            today=datetime(2026, 10, 20).date(),
        )
    assert pending.read_bytes() == raw
    assert list(root.iterdir()) == [pending]


def test_output_path_that_resolves_to_input_writes_nothing(review, tmp_path):
    root = tmp_path / "review"
    day = root / "2026-10-20" / "7-same"
    day.mkdir(parents=True)
    source = day / "7-same.max"
    source.write_bytes(b"SOURCE-MAX")
    pending = root / "pending.json"
    pending.write_text("[]", encoding="utf-8")
    png = day / "shot.png"
    _png(png)
    model = tmp_path / "model.fbx"
    _fbx(model)
    before = _snapshot(root)
    with pytest.raises(review.ReviewError):
        review.publish(
            task="7",
            slug="same",
            source=source,
            what="текст",
            pngs=[],
            review_root=root,
            adapter=FakeAdapter(),
            today=datetime(2026, 10, 20).date(),
        )
    with pytest.raises(review.ReviewError):
        review.publish(
            task="7",
            slug="same",
            source=model,
            what="текст",
            pngs=[png],
            review_root=root,
            adapter=FakeAdapter(),
            today=datetime(2026, 10, 20).date(),
        )
    assert _snapshot(root) == before
    assert source.read_bytes() == b"SOURCE-MAX"


def test_adapter_failure_leaves_no_folder(review, tmp_path):
    root = tmp_path / "review"
    before = _snapshot(root)
    with pytest.raises(review.ReviewError):
        _publish(review, tmp_path, FakeAdapter(fail=review.ReviewError("import failed")), review_root=root)
    assert _snapshot(root) == before


def test_second_publish_same_slug_keeps_one_entry(review, tmp_path):
    adapter = FakeAdapter()
    root = tmp_path / "review"
    assert _publish(review, tmp_path, adapter, review_root=root) == 0
    pending = root / "pending.json"
    raw = pending.read_bytes()
    before = _snapshot(root)
    with pytest.raises(review.ReviewError):
        _publish(review, tmp_path, adapter, review_root=root)
    assert pending.read_bytes() == raw
    assert _snapshot(root) == before
    assert len(json.loads(raw)) == 1


def test_atomic_replace_failure_restores_pending_and_folder(review, tmp_path, monkeypatch):
    root = tmp_path / "review"
    root.mkdir()
    pending = root / "pending.json"
    original = '[{"task": "#2", "path": "C:/x/review/keep.max", "what": "keep"}]'
    pending.write_text(original, encoding="utf-8")
    real = os.replace

    def boom(src, dst):
        if str(dst).endswith("pending.json"):
            raise OSError("replace failed")
        return real(src, dst)

    monkeypatch.setattr(review.os, "replace", boom)
    with pytest.raises(review.ReviewError):
        _publish(review, tmp_path, FakeAdapter(), review_root=root)
    assert pending.read_text(encoding="utf-8") == original
    assert not (root / "2026-10-20").exists()


def test_verdict_updates_one_entry_and_rejects_unknown(review, tmp_path):
    root = tmp_path / "review"
    _publish(review, tmp_path, FakeAdapter(), review_root=root, task="11", slug="flora")
    _publish(review, tmp_path, FakeAdapter(), review_root=root, task="12", slug="other", what="Другое.")
    code = review.verdict(task="11", status="changes", note="Сдвинуть камеру.", review_root=root)
    assert code == 0
    rows = json.loads((root / "pending.json").read_text(encoding="utf-8"))
    changed = next(row for row in rows if row["task"] == "#11")
    other = next(row for row in rows if row["task"] == "#12")
    assert changed["status"] == "changes" and changed["note"] == "Сдвинуть камеру."
    assert changed["what"] == "Проверить масштаб и материалы."
    assert "status" not in other and other["what"] == "Другое."
    raw = (root / "pending.json").read_bytes()
    with pytest.raises(review.ReviewError):
        review.verdict(task="99", status="ok", note="нет", review_root=root)
    assert (root / "pending.json").read_bytes() == raw
    for status, note in (("maybe", "x"), ("ok", ""), ("ok", "   "), ("ok", "a\nb"), ("nan", "x")):
        with pytest.raises(review.ReviewError):
            review.verdict(task="11", status=status, note=note, review_root=root)
        assert (root / "pending.json").read_bytes() == raw


def test_default_roots_are_the_review_store(review):
    assert review.REVIEW_ROOT.as_posix().casefold() == "c:/x/review"
    assert review.SCRATCH_ROOT.as_posix().casefold() == "c:/x"
    assert review.FLORA_LIBRARY.as_posix().casefold() == "c:/x/flora-library"


def _age(path: Path, when: datetime):
    path.mkdir(parents=True, exist_ok=True)
    stamp = when.timestamp()
    os.utime(path, (stamp, stamp))


def test_cleanup_dry_run_is_default_and_apply_deletes_only_old_scratch(review, tmp_path):
    scratch = tmp_path / "x"
    now = datetime(2026, 10, 20, 12, 0, 0)
    old = now - timedelta(days=3)
    (scratch / "t_old").mkdir(parents=True)
    (scratch / "t_old" / "note.txt").write_text("gone", encoding="utf-8")
    (scratch / "ci-receipt-old").mkdir(parents=True)
    (scratch / "t_young").mkdir(parents=True)
    _age(scratch / "t_old", old)
    _age(scratch / "ci-receipt-old", old)
    _age(scratch / "t_young", now - timedelta(days=0.5))
    listed = review.cleanup(days=2, scratch=scratch, manifests=[], now=now, apply=False)
    names = {path.name for path in listed}
    assert names == {"t_old", "ci-receipt-old"}
    assert (scratch / "t_old" / "note.txt").is_file()
    deleted = review.cleanup(days=2, scratch=scratch, manifests=[], now=now, apply=True)
    assert {path.name for path in deleted} == names
    assert not (scratch / "t_old").exists()
    assert not (scratch / "ci-receipt-old").exists()
    assert (scratch / "t_young").is_dir()


def test_exact_threshold_nan_and_empty_days_do_not_delete(review, tmp_path):
    scratch = tmp_path / "x"
    now = datetime(2026, 10, 20, 12, 0, 0)
    exact = scratch / "t_exact"
    older = scratch / "t_older"
    exact.mkdir(parents=True)
    older.mkdir(parents=True)
    (exact / "keep.txt").write_text("exact", encoding="utf-8")
    (older / "keep.txt").write_text("older", encoding="utf-8")
    _age(exact, now - timedelta(days=2))
    _age(older, now - timedelta(days=2, seconds=1))
    selected = review.cleanup(days=2, scratch=scratch, manifests=[], now=now, apply=False)
    assert [path.name for path in selected] == ["t_older"]
    for bad in (0, -1, math.nan, math.inf, -math.inf):
        with pytest.raises(review.ReviewError):
            review.cleanup(days=bad, scratch=scratch, manifests=[], now=now, apply=True)
    assert (exact / "keep.txt").read_text(encoding="utf-8") == "exact"
    assert older.is_dir()


def test_cleanup_never_touches_review_flora_or_manifest_ground(review, tmp_path):
    scratch = tmp_path / "x"
    now = datetime(2026, 10, 20, 12, 0, 0)
    old = now - timedelta(days=9)
    review_dir = scratch / "review"
    flora = scratch / "flora-library"
    ground = scratch / "t_groundlib" / "ground_v001"
    decoy = scratch / "t_delete"
    for path in (review_dir, flora, ground, decoy):
        path.mkdir(parents=True, exist_ok=True)
        (path / "keep.txt").write_text(path.name, encoding="utf-8")
        _age(path, old)
        if path.parent != scratch:
            _age(path.parent, old)
    manifest = tmp_path / "library.json"
    manifest.write_text(json.dumps({"scene": str(ground / "library.max")}), encoding="utf-8")
    broken = tmp_path / "broken.json"
    broken.write_bytes(b"[")
    with pytest.raises(review.ReviewError):
        review.cleanup(days=1, scratch=scratch, manifests=[broken], now=now, apply=True)
    assert (decoy / "keep.txt").is_file()
    listed = review.cleanup(days=1, scratch=scratch, manifests=[manifest], now=now, apply=True)
    assert [path.name for path in listed] == ["t_delete"]
    assert (review_dir / "keep.txt").is_file()
    assert (flora / "keep.txt").is_file()
    assert (ground / "keep.txt").is_file()
    assert not decoy.exists()
    maf = scratch / "t_maflib" / "library" / "max"
    maf.mkdir(parents=True)
    (maf / "keep.txt").write_text("maf", encoding="utf-8")
    _age(maf, old)
    _age(maf.parent, old)
    _age(scratch / "t_maflib", old)
    maf_manifest = tmp_path / "maf.json"
    maf_manifest.write_text(json.dumps({"max_path": str(maf / "MAF_0001.max")}), encoding="utf-8")
    again = review.cleanup(days=1, scratch=scratch, manifests=[manifest, maf_manifest], now=now, apply=True)
    assert again == []
    assert (maf / "keep.txt").read_text(encoding="utf-8") == "maf"
    assert (ground / "keep.txt").is_file()


def test_brute_force_escapes_and_protected_names(review, tmp_path):
    """Every never/at-most guarantee: generated inputs stay out of the write and delete sets."""
    rng = random.Random(348)
    root = tmp_path / "review"
    root.mkdir()
    (root / "pending.json").write_text("[]", encoding="utf-8")
    fbx = tmp_path / "model.fbx"
    _fbx(fbx)
    before = _snapshot(root)
    slugs = ["../out", "..\\out", "a/b", "a\\b", ".", "..", "con", "nul", "", " ", "slug.", ".slug", "Has Space"]
    for i in range(48):
        slugs.append(rng.choice(["../", "..\\", "/", "\\", ":"]) + f"n{i}")
    failures = 0
    for slug in slugs:
        with pytest.raises(review.ReviewError):
            review.publish(
                task="3",
                slug=slug,
                source=fbx,
                what="текст",
                pngs=[],
                review_root=root,
                adapter=FakeAdapter(),
                today=datetime(2026, 10, 20).date(),
            )
        failures += 1
    assert failures == len(slugs)
    assert _snapshot(root) == before

    scratch = tmp_path / "scratch"
    now = datetime(2026, 10, 20, tzinfo=timezone.utc).replace(tzinfo=None)
    old = now - timedelta(days=5)
    protected = []
    deletable = []
    flora = scratch / "flora-library"
    review_dir = scratch / "review"
    flora.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    (flora / "a.txt").write_text("f", encoding="utf-8")
    (review_dir / "a.txt").write_text("r", encoding="utf-8")
    _age(flora, old)
    _age(review_dir, old)
    ground_dirs = []
    for i in range(24):
        kind = rng.choice(["t", "ci", "ground", "reviewish", "other"])
        if kind == "t":
            path = scratch / f"t_work_{i}"
            deletable.append(path)
        elif kind == "ci":
            path = scratch / f"ci-receipt-{i}"
            deletable.append(path)
        elif kind == "ground":
            path = scratch / f"t_lib_{i}" / "ground_pack"
            ground_dirs.append(path)
            protected.append(path)
        elif kind == "reviewish":
            path = scratch / "review" / f"t_{i}"
            protected.append(path)
        else:
            path = scratch / f"notes-{i}"
            protected.append(path)
        path.mkdir(parents=True, exist_ok=True)
        (path / "f.txt").write_text("x", encoding="utf-8")
        _age(path, old)
        if path.parent != scratch and path.parent.parent == scratch:
            _age(path.parent, old)
    manifest = tmp_path / "grounds.json"
    manifest.write_text(
        json.dumps({"grounds": [str(path / "scene.max") for path in ground_dirs]}),
        encoding="utf-8",
    )
    deleted = review.cleanup(days=1, scratch=scratch, manifests=[manifest], now=now, apply=True)
    deleted_resolved = {path.resolve() for path in deleted}
    for path in deletable:
        assert path.resolve() in deleted_resolved
        assert not path.exists()
    for path in protected + [flora, review_dir]:
        assert path.resolve() not in deleted_resolved
        assert (path / "f.txt").is_file() or (path / "a.txt").is_file()
    assert len(deleted) == len(deletable)


@pytest.mark.max
def test_max_dependent_merge_skips_when_max_absent(review, tmp_path):
    adapter_mod = _load("max_adapter")
    if adapter_mod.max_batch_path() is None:
        pytest.skip("3ds Max is not installed")
    out = tmp_path / "scene.max"
    preview = tmp_path / "preview.png"
    result = adapter_mod.default_adapter().selftest(tmp_path / "work", out, preview)
    assert result["cameras"] >= 1
    assert result["materials"] >= 1
    assert out.is_file() and out.stat().st_size > 0
    assert preview.is_file() and preview.read_bytes().startswith(b"\x89PNG")


def test_max_job_source_merges_fbx_and_sets_a_camera():
    source = (REVIEW / "max_job.py").read_text(encoding="utf-8")
    assert "importFile" in source and "FBXIMP" in source
    assert "saveMaxFile" in source
    assert "Review_Camera" in source
    assert "meters" in source
