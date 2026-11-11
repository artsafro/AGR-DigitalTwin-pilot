"""new-case: fail-closed controls for the disposable PDF research runner."""
import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('pdf_probe', Path(__file__).with_name('probe.py'))

def load():
    assert SPEC is not None and SPEC.loader is not None
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    return module

@pytest.mark.parametrize('pages', [[], [0], [-1], [1, 1], [True], [float('nan')], [float('inf')], [2]])
def test_bad_selection(pages):
    with pytest.raises(ValueError):
        load().validate_pages(pages, 1)

@pytest.mark.parametrize('offset', [1, 1.001, float('nan'), float('inf')])
def test_text_threshold_fails_closed(offset):
    assert load().score_numeric(6000 + offset, 6000, 1) is False

def test_valid_selection_and_score():
    assert load().validate_pages([1], 1) == [1]
    assert load().score_numeric(6000, 6000, 1)

@pytest.mark.parametrize('alias', ['same', 'relative', 'hardlink', 'case'])
def test_output_alias_does_not_change_source(tmp_path, alias):
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'original bytes')
    target = source
    if alias == 'relative':
        target = source.parent / '.' / source.name
    elif alias == 'hardlink':
        target = tmp_path / 'linked.pdf'
        target.hardlink_to(source)
    elif alias == 'case':
        target = source.with_name('SOURCE.PDF')
    with pytest.raises((ValueError, FileExistsError)):
        load().reserve_output(source, target)
    assert source.read_bytes() == b'original bytes'

def test_existing_output_not_clobbered(tmp_path):
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'input')
    output = tmp_path / 'result'
    output.mkdir()
    (output / 'sentinel.partial').write_bytes(b'other writer')
    with pytest.raises(FileExistsError):
        load().reserve_output(source, output)
    assert (output / 'sentinel.partial').read_bytes() == b'other writer'


def load_summary():
    spec = importlib.util.spec_from_file_location('summary', Path(__file__).with_name('summarize.py'))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('text,expected', [('цвет сосна, RAL 1001', 1), ('RAL 10010', 0), ('RAL 1002', 0)])
def test_ral_scoring_boundaries(text, expected):
    result = load_summary().hits([{'code': 'RAL 1001', 'page': 18}], {18: [text]}, 'code')
    assert result['correct'] == expected


@pytest.mark.parametrize('text,expected', [('52 600', 1), ('152600', 0), ('526001', 0), ('52600.1', 0)])
def test_dimension_scoring_boundaries(text, expected):
    result = load_summary().hits([{'value': 52600, 'page': 18}], {18: [text]}, 'value')
    assert result['correct'] == expected


def test_absence_is_not_perfect_score():
    result = load_summary().hits([], {}, 'value')
    assert result['share'] is None


@pytest.mark.parametrize('route_status', ['fail', 'review', 'not_run', 'unknown', 'observed'])
def test_partial_or_failing_receipt_rejected(tmp_path, route_status):
    import json
    root = tmp_path
    (root / 'elv-inventory.json').write_text(json.dumps({'source': 'x', 'sha256': 'a', 'bytes': 1,
        'pages': 2, 'metadata': {}, 'ocg': {}, 'embedded_files': [], 'index': []}))
    folder = root / 'elv-A-all-v001'
    folder.mkdir()
    (folder / 'result.json').write_text(json.dumps({'sha256': 'a', 'input_unchanged': True,
        'status': route_status, 'pages_requested': [1], 'pages': [{'reference': {'pdf_page': 1, 'pdf_sha256': 'a'}}]}))
    with pytest.raises(ValueError, match='stale, partial or invalid'):
        load_summary().make_summary(root, 'elv', {})


@pytest.mark.parametrize('mode', ['empty', 'corrupt', 'duplicate', 'out_of_range', 'alias', 'unsupported'])
def test_fresh_cli_refuses_invalid_input_without_writes(tmp_path, mode):
    import subprocess
    import sys
    pymupdf = pytest.importorskip('pymupdf')
    source = tmp_path / 'synthetic-control.pdf'
    if mode in ('empty', 'corrupt', 'unsupported'):
        source.write_bytes({'empty': b'', 'corrupt': b'%PDF-1.7\ntruncated', 'unsupported': b'not a PDF'}[mode])
    else:
        with pymupdf.open() as doc:
            doc.new_page().insert_text((40, 40), 'SYNTHETIC CONTROL 6000')
            doc.save(source)
    before = source.read_bytes()
    output = source if mode == 'alias' else tmp_path / 'new-output'
    pages = ['1', '1'] if mode == 'duplicate' else ['2'] if mode == 'out_of_range' else ['1']
    command = [sys.executable, str(Path(__file__).with_name('probe.py')), '--pdf', str(source),
               '--out', str(output), '--route', 'A', '--pages', *pages]
    result = subprocess.run(command, capture_output=True, timeout=30)
    assert result.returncode != 0
    assert source.read_bytes() == before
    if output != source:
        assert not output.exists()


def test_input_mutation_is_invalid_receipt(tmp_path, monkeypatch):
    import json
    import sys
    pymupdf = pytest.importorskip('pymupdf')
    import dt_ai.album.reader as reader
    source = tmp_path / 'synthetic-mutation.pdf'
    output = tmp_path / 'new-output'
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40, 40), 'SYNTHETIC CONTROL')
        doc.save(source)
    real_read = reader.read_page
    def mutate_after_read(*args, **kwargs):
        result = real_read(*args, **kwargs)
        with source.open('ab') as stream:
            stream.write(b'\n% SYNTHETIC INPUT MUTATION')
        return result
    monkeypatch.setattr(reader, 'read_page', mutate_after_read)
    monkeypatch.setattr(sys, 'argv', ['probe', '--pdf', str(source), '--out', str(output), '--route', 'A', '--pages', '1'])
    with pytest.raises(RuntimeError, match='source changed'):
        load().main()
    receipt = json.loads((output / 'result.json').read_text(encoding='utf-8'))
    assert receipt['status'] == 'invalid_input_changed'
    assert receipt['input_unchanged'] is False
