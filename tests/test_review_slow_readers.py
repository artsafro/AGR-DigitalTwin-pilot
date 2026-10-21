"""Concurrent publication must tolerate slower Windows queue-file readers."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest

from test_review_publish import FakeAdapter, _fbx, _load


def test_parallel_publish_preserves_rows_with_slow_queue_readers(tmp_path, monkeypatch):
    review = _load('common')
    root = tmp_path / 'review'
    root.mkdir()
    pending = root / 'pending.json'
    pending.write_text('[]', encoding='utf-8')
    source = tmp_path / 'model.fbx'
    _fbx(source)
    real_read = Path.read_text

    def slow_read(path, *args, **kwargs):
        if path == pending:
            # Keep the native read handle open, as with a slower disk/virus scan.
            with path.open('r', encoding=kwargs.get('encoding', 'utf-8')) as handle:
                time.sleep(0.04)
                return handle.read()
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', slow_read)

    def publish(i):
        from datetime import date
        return review.publish(task='348', slug=f'slow-{i}', source=source,
                              what='Проверка.', pngs=[], review_root=root,
                              adapter=FakeAdapter(), today=date(2026, 10, 20))

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(publish, range(24))) == [0] * 24
    assert len(json.loads(real_read(pending, encoding='utf-8'))) == 24


def test_lock_acquire_retries_transient_windows_permissionerror(tmp_path, monkeypatch):
    review = _load('common')
    root = tmp_path / 'review'
    root.mkdir()
    pending = root / 'pending.json'
    pending.write_text('[]', encoding='utf-8')
    source = tmp_path / 'model.fbx'
    _fbx(source)
    lock = root / '.pending-lock'
    real_mkdir = Path.mkdir
    injected = {'count': 0}
    gate = threading.Lock()

    def flaky_mkdir(self, *args, **kwargs):
        if (self == lock or self.name == '.pending-lock') and not args and not kwargs:
            with gate:
                if injected['count'] < 4:
                    injected['count'] += 1
                    raise PermissionError(13, 'Access is denied', '.pending-lock')
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', flaky_mkdir)

    def publish(i):
        return review.publish(task='348', slug=f'retry-{i}', source=source,
                              what='Проверка.', pngs=[], review_root=root,
                              adapter=FakeAdapter(), today=date(2026, 10, 20))

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(publish, range(24))) == [0] * 24
    assert injected['count'] == 4
    assert len(json.loads(pending.read_text(encoding='utf-8'))) == 24


def test_stale_lock_fails_closed_without_writing(tmp_path, monkeypatch):
    review = _load('common')
    root = tmp_path / 'review'
    root.mkdir()
    pending = root / 'pending.json'
    pending.write_text('[]', encoding='utf-8')
    before = pending.read_bytes()
    source = tmp_path / 'model.fbx'
    _fbx(source)
    lock = root / '.pending-lock'
    lock.mkdir()
    real_mkdir = Path.mkdir

    def busy_mkdir(self, *args, **kwargs):
        if self == lock and not args and not kwargs:
            raise FileExistsError
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', busy_mkdir)
    calls = {'n': 0}

    def monotonic():
        calls['n'] += 1
        return 0.0 if calls['n'] == 1 else 1000.0

    monkeypatch.setattr(review.time, 'monotonic', monotonic)
    monkeypatch.setattr(review.time, 'sleep', lambda _seconds: None)

    with pytest.raises(review.ReviewError, match='busy'):
        review.publish(task='348', slug='stale', source=source, what='Проверка.',
                       pngs=[], review_root=root, adapter=FakeAdapter(),
                       today=date(2026, 10, 20))
    assert pending.read_bytes() == before
    assert sorted(path.name for path in root.iterdir()) == ['.pending-lock', 'pending.json']
