"""new-case: synthetic public-seam fallback regression; no customer image in git."""
import importlib
import json


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
