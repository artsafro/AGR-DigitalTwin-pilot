"""new-case: synthetic PDF intake accounting and immutable deterministic publication."""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

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


def test_dense_page_keeps_header_and_explicit_uninspected_region(tmp_path):
    intake = intake_module()
    source = tmp_path / 'dense.pdf'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((20, 20), 'Synthetic dense page header')
        shape = page.new_shape()
        for i in range(20001):
            shape.draw_rect(fitz.Rect(i % 500, 100 + i % 300, i % 500 + 1, 102 + i % 300))
            shape.finish(fill=(0, 0, 0))
        shape.commit()
        doc.save(source)
    intake.index_album(source, tmp_path / 'out', page_budget_s=30)
    page = json.loads((tmp_path / 'out/album_index.json').read_bytes())['pages'][0]
    assert page['status'] == 'partial'
    assert page['reason'] == 'dense_display_list_cutoff'
    assert any(r['indicator'] == 'text' for r in page['regions'])
    fallback = [r for r in page['regions'] if r['reason'] == 'dense_display_list_cutoff']
    assert len(fallback) == 1
    assert fallback[0]['route'] == 'ocr_vision'
    assert fallback[0]['operations'] >= 20001


def test_artifacts_validate_strict_schemas(tmp_path):
    import jsonschema
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', 1)
    intake.index_album(source, tmp_path / 'out')
    for filename, schema_name in [('album_index.json', 'AlbumIndex'), ('manifest.json', 'AlbumManifest')]:
        schema = json.loads(Path(f'schemas/{schema_name}.schema.json').read_text('utf8'))
        artifact = json.loads((tmp_path / 'out' / filename).read_bytes())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(artifact, schema)
        artifact['unexpected'] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(artifact, schema)


@pytest.mark.parametrize('budget', [0, -1, float('nan'), float('inf'), float('-inf'), True, '1'])
def test_invalid_budget_writes_nothing(tmp_path, budget):
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', 1)
    with pytest.raises(ValueError, match='finite and positive'):
        intake.index_album(source, tmp_path / 'out', page_budget_s=budget)
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('mode', ['same', 'hardlink', 'existing_directory', 'relative_alias'])
def test_output_aliases_reuse_and_stale_receipts_are_refused(tmp_path, mode, monkeypatch):
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', 1)
    original = source.read_bytes()
    output = source
    if mode == 'hardlink':
        output = tmp_path / 'linked.pdf'
        output.hardlink_to(source)
    elif mode == 'existing_directory':
        output = tmp_path / 'old'
        output.mkdir()
        (output / 'manifest.json').write_text('{"passed":true}')
    elif mode == 'relative_alias':
        monkeypatch.chdir(tmp_path)
        output = Path('source.pdf')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    with pytest.raises(FileExistsError):
        intake.index_album(source, output)
    assert source.read_bytes() == original
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    if mode == 'existing_directory':
        assert (output / 'manifest.json').read_text() == '{"passed":true}'


def test_budget_cut_accounts_every_page_and_leaves_no_workers(tmp_path):
    import multiprocessing
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', 4)
    manifest = intake.index_album(source, tmp_path / 'out', page_budget_s=0.000001)
    assert manifest['passed'] is False and manifest['status'] == 'partial'
    pages = json.loads((tmp_path / 'out/album_index.json').read_bytes())['pages']
    assert [p['pdf_page'] for p in pages] == [1, 2, 3, 4]
    assert all(p['reason'] == 'page_budget_exhausted' for p in pages)
    assert not multiprocessing.active_children()
    assert not list((tmp_path / 'out').glob('.workers-*'))


@pytest.mark.parametrize('case', ['empty_file', 'corrupt', 'encrypted', 'empty_page', 'unsupported'])
def test_fail_closed_inputs(tmp_path, case):
    intake = intake_module()
    source = tmp_path / 'source.pdf'
    if case == 'empty_file':
        source.write_bytes(b'')
    elif case == 'corrupt':
        source.write_bytes(b'%PDF-1.4\nnot a document')
    elif case == 'unsupported':
        from PIL import Image
        Image.new('RGB', (4, 4)).save(source, format='PNG')
    else:
        with fitz.open() as doc:
            doc.new_page()
            options = dict(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='secret') if case == 'encrypted' else {}
            doc.save(source, **options)
    original = source.read_bytes()
    if case == 'empty_page':
        manifest = intake.index_album(source, tmp_path / 'out')
        assert manifest['status'] == 'partial' and manifest['passed'] is False
        page = json.loads((tmp_path / 'out/album_index.json').read_bytes())['pages'][0]
        assert page['reason'] == 'empty_page'
    else:
        with pytest.raises(intake.AlbumReadError):
            intake.index_album(source, tmp_path / 'out')
        assert not (tmp_path / 'out/manifest.json').exists()
    assert source.read_bytes() == original


def test_source_mutation_during_run_never_publishes_receipt(tmp_path, monkeypatch):
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', 1)
    original = source.read_bytes()
    real = intake._budgeted_page
    def mutate(*args):
        result = real(*args)
        source.write_bytes(original + b'\n% changed')
        return result
    monkeypatch.setattr(intake, '_budgeted_page', mutate)
    with pytest.raises(intake.AlbumReadError, match='source_changed'):
        intake.index_album(source, tmp_path / 'out')
    assert not (tmp_path / 'out/manifest.json').exists()
    assert (tmp_path / 'out/source.pdf').read_bytes() == original


def test_mixed_regions_original_labels_and_table_routing(tmp_path):
    import io
    from PIL import Image
    intake = intake_module()
    source = tmp_path / 'mixed.pdf'
    raster = io.BytesIO()
    Image.new('RGB', (20, 20), 'black').save(raster, format='PNG')
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((30, 30), 'Sheet 12: Specification')
        page.insert_text((30, 60), '69600 + 17800 = 87450; RAL 9003')
        page.draw_rect(fitz.Rect(50, 200, 55, 208), fill=(0, 0, 0))
        page.draw_line((30, 250), (500, 250))
        page.insert_image(fitz.Rect(100, 300, 400, 600), stream=raster.getvalue())
        doc.save(source)
    intake.index_album(source, tmp_path / 'out')
    page = json.loads((tmp_path / 'out/album_index.json').read_bytes())['pages'][0]
    assert page['printed_sheet'] == '12'
    routes = {(r['indicator'], r['route']) for r in page['regions']}
    assert {('text', 'vector_read'), ('text', 'table_extraction'),
            ('vector', 'vector_read'), ('raster', 'ocr_vision'),
            ('outline_candidate', 'ocr_vision')} <= routes
    assert any('69600 + 17800 = 87450' in (r['label'] or '') for r in page['regions'])
    table_rois = [r['bbox'] for r in page['regions'] if r['route'] == 'table_extraction']
    value_box = next(r['bbox'] for r in page['regions'] if '69600' in (r['label'] or ''))
    assert any(b[0] <= value_box[0] and b[1] <= value_box[1] and b[2] >= value_box[2] and b[3] >= value_box[3] for b in table_rois)
    assert all(r['reason'] and len(r['bbox']) == 4 for r in page['regions'])


@pytest.mark.parametrize('count', [19999, 20000, 20001])
def test_exact_density_threshold_is_partial_not_certified(tmp_path, monkeypatch, count):
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', 1)
    monkeypatch.setattr(fitz.Page, 'get_bboxlog', lambda self: [('fill-path', (1, 1, 2, 2))] * count)
    page = intake._inspect_page(source, 1)
    assert page['status'] == ('partial' if count >= 20000 else 'indexed')


@pytest.mark.parametrize('count', range(1, 9))
def test_generated_page_accounting_and_unique_regions(tmp_path, count):
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', count)
    intake.index_album(source, tmp_path / 'out')
    index = json.loads((tmp_path / 'out/album_index.json').read_bytes())
    assert [p['pdf_page'] for p in index['pages']] == list(range(1, count + 1))
    ids = [r['region_id'] for p in index['pages'] for r in p['regions']]
    assert len(ids) == len(set(ids))
    assert all(p['scale'] == 'unknown' and p['units'] is None for p in index['pages'])


def test_fresh_process_cli_rejects_input_alias_and_returns_partial_nonzero(tmp_path):
    source = synthetic_pdf(tmp_path / 'source.pdf', 2)
    original = source.read_bytes()
    command = [sys.executable, '-m', 'dt_ai.album.intake', str(source), '--output']
    alias = subprocess.run(command + [str(source)], capture_output=True, text=True)
    assert alias.returncode == 2 and source.read_bytes() == original
    output = tmp_path / 'out'
    result = subprocess.run(command + [str(output), '--page-budget-s', '0.000001'], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)['passed'] is False
    assert json.loads((output / 'manifest.json').read_bytes())['accounted_pages'] == 2


def test_fresh_process_cli_success_and_duplicate_run_refusal(tmp_path):
    source = synthetic_pdf(tmp_path / 'source.pdf', 1)
    output = tmp_path / 'out'
    command = [sys.executable, '-m', 'dt_ai.album.intake', str(source), '--output', str(output)]
    success = subprocess.run(command, capture_output=True, text=True)
    assert success.returncode == 0 and json.loads(success.stdout)['passed'] is False
    original = (output / 'manifest.json').read_bytes()
    duplicate = subprocess.run(command, capture_output=True, text=True)
    assert duplicate.returncode == 2
    assert (output / 'manifest.json').read_bytes() == original


def test_precreated_publication_hardlink_and_partial_sentinel_not_clobbered(tmp_path, monkeypatch):
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', 1)
    original = source.read_bytes()
    output = tmp_path / 'out'
    real = intake._budgeted_page
    def collide(*args):
        page = real(*args)
        (output / 'album_index.json').hardlink_to(source)
        (output / 'album_index.json.partial').write_bytes(b'foreign sentinel')
        return page
    monkeypatch.setattr(intake, '_budgeted_page', collide)
    with pytest.raises(FileExistsError):
        intake.index_album(source, output)
    assert source.read_bytes() == original
    assert (output / 'album_index.json.partial').read_bytes() == b'foreign sentinel'
    assert not (output / 'manifest.json').exists()


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_display_bbox_is_an_error(tmp_path, monkeypatch, bad):
    intake = intake_module()
    source = synthetic_pdf(tmp_path / 'source.pdf', 1)
    monkeypatch.setattr(fitz.Page, 'get_bboxlog', lambda self: [('fill-path', (bad, 1, 2, 2))])
    with pytest.raises(ValueError, match='nonfinite region bbox'):
        intake._inspect_page(source, 1)


@pytest.mark.job
@pytest.mark.parametrize('album', ['elv', 'cod20207', 'tec26'])
def test_real_corpus_frozen_kind_accounting(tmp_path, album):
    intake = intake_module()
    source = Path('C:/x/pdf-album-research/t_5b23c219') / f'{album}.pdf'
    if not source.is_file():
        pytest.skip('read-only research corpus not mounted')
    reference = json.loads((Path('tools/research/pdf_album/results') / f'{album}.json').read_text('utf8'))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == reference['sha256']
    intake.index_album(source, tmp_path / 'out')
    index = json.loads((tmp_path / 'out/album_index.json').read_bytes())
    assert [p['pdf_page'] for p in index['pages']] == list(range(1, reference['pages'] + 1))
    assert [p['kind'] for p in index['pages']] == [p['kind_candidate'].replace('3D view', '3D') for p in reference['index']]
    if album == 'cod20207':
        for page in index['pages'][:4]:
            assert {'text', 'outline_candidate', 'raster'} <= {r['indicator'] for r in page['regions']}
    if album == 'tec26':
        assert index['pages'][1]['status'] == 'partial'
        assert index['pages'][1]['reason'] == 'dense_display_list_cutoff'
