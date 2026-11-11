"""new-case: synthetic PDF intake accounting and immutable deterministic publication."""
import hashlib
import importlib
import json

import pytest

fitz = pytest.importorskip('pymupdf')


def synthetic_pdf(path, pages=3):
    with fitz.open() as doc:
        for n in range(pages):
            page = doc.new_page(width=600, height=800)
            page.insert_text((30, 30), f'Sheet {n + 10}: synthetic source')
            page.draw_rect(fitz.Rect(100, 150, 500, 600))
        doc.save(path)
    return path


def intake_module():
    spec = importlib.util.find_spec('dt_ai.album.intake')
    assert spec is not None, 'production budgeted album intake module is missing'
    return importlib.import_module('dt_ai.album.intake')


def test_accounting_freeze_determinism(tmp_path):
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'input.pdf')
    original = source.read_bytes()
    for name in ('one', 'two'):
        result = intake.index_album(source, tmp_path / name, page_budget_s=10)
        assert result['passed'] is False
        index = json.loads((tmp_path / name / 'album_index.json').read_text('utf8'))
        assert [p['pdf_page'] for p in index['pages']] == [1, 2, 3]
        assert all(p['status'] == 'indexed' for p in index['pages'])
        assert index['source']['sha256'] == hashlib.sha256(original).hexdigest()
        assert (tmp_path / name / 'source.pdf').read_bytes() == original
        assert all(p['scale'] == 'unknown' and p['units'] is None for p in index['pages'])
        assert all(p['regions'] for p in index['pages'])
    for name in ('album_index.json', 'manifest.json'):
        assert (tmp_path / 'one' / name).read_bytes() == (tmp_path / 'two' / name).read_bytes()
    assert source.read_bytes() == original
