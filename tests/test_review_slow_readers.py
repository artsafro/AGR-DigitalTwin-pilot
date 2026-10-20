"""Concurrent publication must tolerate slower Windows queue-file readers."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
