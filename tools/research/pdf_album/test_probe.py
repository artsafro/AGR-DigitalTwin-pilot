"""new-case: fail-closed controls for the disposable PDF research runner."""
import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('pdf_probe', Path(__file__).with_name('probe.py'))

def load():
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
