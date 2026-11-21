"""new-case: synthetic public-seam fallback regression; no customer image in git."""
import importlib
import json
import pytest


@pytest.mark.parametrize('regions', [[], [{}], [dict(id='a', page=0, bbox=[0,0,1,1], kind='dimension')],
    [dict(id='a', page=1, bbox=[0,0,0,1], kind='dimension')],
    [dict(id='a', page=1, bbox=[0,0,float('nan'),1], kind='dimension')],
    [dict(id='a', page=1, bbox=[0,0,float('inf'),1], kind='dimension')],
    [dict(id='a', page=1, bbox=[0,0,1,1], kind='unsupported')],
    [dict(id='a', page=True, bbox=[0,0,1,1], kind='material')]])
def test_invalid_regions_write_nothing(tmp_path, regions):
    from dt_ai.album.fallback import run_fallback
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'synthetic')
    output = tmp_path / 'out'
    with pytest.raises(ValueError):
        run_fallback(source, output, regions, ocr=None, vision=None)
    assert not output.exists()
    assert source.read_bytes() == b'synthetic'


def test_roi_disagreement_is_not_geometry(tmp_path):
    fallback = importlib.import_module('dt_ai.album.fallback')
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'synthetic backend input')
    region = dict(id='chain', page=1, bbox=[0, 0, 100, 100], kind='dimension')
    def ocr(pdf, roi):
        return {'text': '87450', 'engine': 'synthetic OCR', 'seconds': 0.1}
    def vision(pdf, roi, text):
        return {'text': '87400', 'engine': 'synthetic vision', 'input_tokens': 10,
                'output_tokens': 2, 'seconds': 0.2}
    result = fallback.run_fallback(source, tmp_path / 'out', [region], ocr=ocr, vision=vision)
    assert result['passed'] is False
    observation = result['regions'][0]
    assert observation['ocr']['text'] == '87450'
    assert observation['vision']['text'] == '87400'
    assert observation['measured_geometry'] is None
    questions = json.loads((tmp_path / 'out/questions.json').read_text())
    assert questions['questions'][0]['bbox'] == [0, 0, 100, 100]
    assert 'ocr_vision_disagreement' in questions['questions'][0]['reasons']
    assert questions['questions'][0]['page'] == 1


def fake_ocr(pdf, roi):
    return dict(text='', engine='synthetic', seconds=0.1)


def fake_vision(pdf, roi, text):
    return dict(text='', engine='synthetic', input_tokens=10, output_tokens=2, seconds=0.2)


def roi(ident='a'):
    return dict(id=ident, page=1, bbox=[0, 0, 10 if ident=='a' else 11, 10], kind='material')


def test_budget_and_usage(tmp_path):
    from dt_ai.album.fallback import run_fallback
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'synthetic')
    result = run_fallback(source, tmp_path/'out', [roi(), roi('b')], ocr=fake_ocr,
                          vision=fake_vision, max_calls_per_page=1)
    assert result['pages'][0]['input_tokens'] == 10
    assert result['pages'][0]['output_tokens'] == 2
    assert result['pages'][0]['vision_seconds'] == 0.2
    assert result['regions'][1]['vision']['status'] == 'budget_excluded'
    assert len(result['regions']) == 2
    questions = json.loads((tmp_path/'out/questions.json').read_text())['questions']
    assert 'vision_budget_excluded' in questions[1]['reasons']
    assert 'missing_value' in questions[0]['reasons']


@pytest.mark.parametrize('field,value', [('input_tokens',0), ('output_tokens',float('nan')),
    ('seconds',float('inf')), ('seconds',0), ('input_tokens',True)])
def test_invalid_metering_is_question_not_success(tmp_path, field, value):
    from dt_ai.album.fallback import run_fallback
    source = tmp_path/'source.pdf'
    source.write_bytes(b'synthetic')
    def bad(pdf, r, text):
        result = fake_vision(pdf,r,text)
        result['text'] = 'original rejected label'
        result[field] = value
        return result
    result = run_fallback(source,tmp_path/'out',[roi()],ocr=fake_ocr,vision=bad)
    assert result['regions'][0]['vision']['status'] == 'failed'
    assert result['passed'] is False
    assert result['pages'][0]['input_tokens'] is None
    assert result['regions'][0]['vision']['text'] == 'original rejected label'


def test_output_and_mutation_guards(tmp_path):
    from dt_ai.album.fallback import run_fallback
    source = tmp_path/'source.pdf'
    source.write_bytes(b'synthetic')
    for output in [source, tmp_path, tmp_path/'alias.pdf']:
        if output.name == 'alias.pdf':
            output.hardlink_to(source)
        with pytest.raises((ValueError, FileExistsError)):
            run_fallback(source,output,[roi()],ocr=fake_ocr,vision=fake_vision)
        assert source.read_bytes() == b'synthetic'
    def mutate(pdf,r):
        pdf.write_bytes(b'changed by synthetic backend')
        return fake_ocr(pdf,r)
    with pytest.raises(RuntimeError, match='source changed'):
        run_fallback(source,tmp_path/'changed',[roi()],ocr=mutate,vision=fake_vision)
    assert not (tmp_path/'changed/observations.json').exists()


def test_missing_values(tmp_path):
    from dt_ai.album.fallback import run_fallback
    source = tmp_path/'source.pdf'
    source.write_bytes(b'synthetic')
    result = run_fallback(source,tmp_path/'out',[roi()],ocr=fake_ocr,vision=fake_vision)
    assert result['regions'][0]['ocr']['text'] == ''
    assert result['regions'][0]['measured_geometry'] is None
    q = json.loads((tmp_path/'out/questions.json').read_text())['questions'][0]
    assert 'missing_value' in q['reasons']


def test_vision_usage_parser_rejects_failed_and_tool_runs():
    from dt_ai.album.fallback_backends import parse_codex_events
    events = [dict(type='turn.completed', usage=dict(input_tokens=12, output_tokens=3))]
    assert parse_codex_events(events) == dict(input_tokens=12, output_tokens=3)
    for extra in [dict(type='turn.failed'), dict(type='error'),
                  dict(type='item.completed', item=dict(type='command_execution')),
                  events[0]]:
        with pytest.raises(ValueError):
            parse_codex_events(events+[extra])
    for events in [[], [dict(type='turn.completed',usage={})]]:
        with pytest.raises(ValueError):
            parse_codex_events(events)


def test_render_rejects_outside_page_and_pixel_budget(tmp_path):
    pymupdf = pytest.importorskip('pymupdf')
    from dt_ai.album.fallback_backends import render_roi
    source = tmp_path/'synthetic.pdf'
    with pymupdf.open() as doc:
        doc.new_page(width=100,height=100)
        doc.save(source)
    image = render_roi(source,roi())
    assert image.size == (42,42)
    for region in [dict(roi(),page=2), dict(roi(),bbox=[0,0,101,100])]:
        with pytest.raises(ValueError):
            render_roi(source,region)
    with pytest.raises(ValueError):
        render_roi(source,roi(),max_pixels=100)


def test_late_report_alias_writes_no_other_report(tmp_path):
    from dt_ai.album.fallback import run_fallback
    source = tmp_path/'source.pdf'
    source.write_bytes(b'synthetic')
    output = tmp_path/'out'
    def alias(pdf,r,text):
        (output/'observations.json').hardlink_to(source)
        return fake_vision(pdf,r,text)
    with pytest.raises(FileExistsError):
        run_fallback(source,output,[roi()],ocr=fake_ocr,vision=alias)
    assert source.read_bytes() == b'synthetic'
    assert not (output/'questions.json').exists()


def test_duplicate_locator_rejected_before_write(tmp_path):
    from dt_ai.album.fallback import run_fallback
    source = tmp_path/'source.pdf'
    source.write_bytes(b'synthetic')
    with pytest.raises(ValueError, match='duplicate'):
        run_fallback(source,tmp_path/'out',[roi(),dict(roi(),id='other')],ocr=fake_ocr,vision=fake_vision)
    assert not (tmp_path/'out').exists()


def test_vision_error_item_is_not_completed_success():
    from dt_ai.album.fallback_backends import parse_codex_events
    with pytest.raises(ValueError):
        parse_codex_events([dict(type='turn.completed',usage=dict(input_tokens=12,output_tokens=3)),
                           dict(type='item.completed',item=dict(type='error',message='request failed'))])


@pytest.mark.parametrize('kwargs', [dict(max_tokens_per_page=12),dict(max_seconds_per_page=0.2)])
def test_exact_budget_boundary_opens_circuit(tmp_path,kwargs):
    from dt_ai.album.fallback import run_fallback
    source = tmp_path/'source.pdf'
    source.write_bytes(b'synthetic')
    result = run_fallback(source,tmp_path/'out',[roi(),roi('b')],ocr=fake_ocr,vision=fake_vision,**kwargs)
    assert result['passed'] is False
    assert result['regions'][1]['vision']['status'] == 'budget_excluded'


def test_cyrillic_word_scoring_and_unknown_denominators():
    from tools.research.pdf_album.fallback_eval import text_scores
    assert text_scores('Цвет белый белый','ЦВЕТ белый синий') == dict(correct=2,reference=3,predicted=3,recall=2/3,precision=2/3)
    assert text_scores('','')['recall'] is None
    assert text_scores('белый','')['precision'] is None


def test_generated_all_candidates_remain_unapproved(tmp_path):
    from dt_ai.album.fallback import run_fallback
    from itertools import product
    source = tmp_path/'source.pdf'
    source.write_bytes(b'synthetic')
    for i,(a,b) in enumerate(product(['','RAL 1001','unknown','87450'],repeat=2)):
        def ocr(pdf,r):
            return dict(fake_ocr(pdf,r),text=a)
        def vision(pdf,r,text):
            return dict(fake_vision(pdf,r,text),text=b)
        result = run_fallback(source,tmp_path/str(i),[roi()],ocr=ocr,vision=vision)
        assert result['passed'] is False
        assert result['regions'][0]['measured_geometry'] is None
        q = json.loads((tmp_path/str(i)/'questions.json').read_text())['questions']
        assert len(q)==1 and q[0]['ocr_label']==a and q[0]['vision_label']==b


def test_fresh_process_cli_help_and_missing_input(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[1]/'tools/research/pdf_album/fallback_eval.py'
    result = subprocess.run([sys.executable,str(script),'--help'],capture_output=True,text=True)
    assert result.returncode == 0 and '--corpus' in result.stdout
    result = subprocess.run([sys.executable,str(script),'--corpus',str(tmp_path/'absent'),
                             '--out',str(tmp_path/'out')],capture_output=True,text=True)
    assert result.returncode != 0
    assert not (tmp_path/'out').exists()


def test_frozen_real_receipts_keep_every_region_unresolved():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]/'tools/research/pdf_album'
    refs = json.loads((root/'fallback-reference.json').read_text(encoding='utf-8'))
    summary = json.loads((root/'fallback-results/summary.json').read_text(encoding='utf-8'))
    import hashlib
    assert summary['reference_sha256'] == hashlib.sha256((root/'fallback-reference.json').read_bytes()).hexdigest()
    assert refs['independence'] == 'not independent (agent-made reference)'
    for album,receipt in zip(refs['albums'],summary['albums']):
        observed = json.loads((root/'fallback-results'/album['id']/'observations.json').read_text(encoding='utf-8'))
        questions = json.loads((root/'fallback-results'/album['id']/'questions.json').read_text(encoding='utf-8'))
        assert observed['passed'] is False and questions['passed'] is False
        assert observed['sha256'] == questions['sha256'] == album['sha256']
        assert [r['id'] for r in album['regions']] == [r['id'] for r in observed['regions']] == [q['id'] for q in questions['questions']]
        assert all(r['measured_geometry'] is None for r in observed['regions'])
        assert all(q['status']=='unresolved' and q['bbox'] and q['page'] for q in questions['questions'])
        assert len(receipt['page_accounting']) == album['pages']
        assert all(p['metering_complete'] and p['input_tokens']>0 for p in receipt['pages'])
