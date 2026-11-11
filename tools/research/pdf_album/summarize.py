"""new-case: summarize measured PDF research outputs against frozen audit references.

Scores are text recall, not semantic acceptance; zero denominators stay null.
Table-row recall requires key and value in the SAME extracted table row.
"""
import argparse
import json
from pathlib import Path
import re


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def normalized(text):
    return re.sub(r'\s+', '', text).replace(',', '.').casefold()


def hits(values, texts, key):
    found = []
    for value in values:
        needle = normalized(str(value[key]))
        before = r'(?<![\d.])' if key in ('value', 'text') else r'(?<![a-z])'
        pattern = rf'{before}{re.escape(needle)}(?![\d.])'
        matched = any(re.search(pattern, normalized(text)) is not None for text in texts.get(value['page'], []))
        found.append({'reference': value, 'found': matched})
    return {'correct': sum(x['found'] for x in found), 'denominator': len(found),
            'share': sum(x['found'] for x in found) / len(found) if found else None, 'samples': found}


def make_summary(root, album, reference):
    inventory = read(root / f'{album}-inventory.json')
    summary = {k: inventory[k] for k in ['source', 'sha256', 'bytes', 'pages', 'metadata']}
    summary['album'] = album
    summary['scoring_note'] = 'Text recall only; numerical tokens are not axis/level/finish bindings. No calibrated geometry certified.'
    summary['ocg_count'] = len(inventory['ocg'])
    summary['embedded_files'] = inventory['embedded_files']
    summary['index'] = []
    for item in inventory['index']:
        text = item['text_preview'].casefold()
        kind = next((label for needle, label in [('экспликац', 'schedule'), ('спецификац', 'schedule'),
                    ('разрез', 'section'), ('фасад', 'facade'), ('план', 'plan'),
                    ('визуализац', '3D view')] if needle in text), 'unknown')
        printed = str(item['page']) if album == 'elv' and item['page'] in (18, 19, 27) else None
        if album == 'cod20207':
            printed = {1: '12', 2: '13', 3: '14', 4: '7', 5: 'unnumbered equipment specification'}.get(item['page'])
        summary['index'].append({'pdf_page': item['page'], 'sheet': printed,
                                 'kind_candidate': kind, 'kind_status': 'text heuristic; visual check required',
                                 'text_chars': item['text_chars']})
    summary['routes'] = {}
    for route in ['A', 'C', 'D']:
        path = root / f'{album}-{route}-all-v001/result.json'
        data = read(path)
        if (data.get('sha256') != inventory['sha256'] or data.get('input_unchanged') is not True
                or data.get('status') != 'observed'
                or data.get('pages_requested') != list(range(1, inventory['pages'] + 1))
                or [p['reference']['pdf_page'] for p in data['pages']] != data['pages_requested']
                or any(p['reference']['pdf_sha256'] != inventory['sha256'] for p in data['pages'])):
            raise ValueError(f'stale, partial or invalid route receipt: {path}')
        texts, tables = {}, {}
        for page in data['pages']:
            n = page['reference']['pdf_page']
            if route == 'A':
                texts[n] = [x['text'] for x in page['raw_text']]
            elif route == 'D':
                texts[n] = [x['text'] for x in page['ocr']]
            else:
                tables[n] = [row for t in page['pymupdf_tables'] for row in t['cells']]
                texts[n] = [' '.join(str(x or '') for x in row) for row in tables[n]]
        record = {'seconds': data['total_seconds'], 'pages_processed': len(data['pages']),
                  'input_unchanged': data['input_unchanged'],
                  'dimension_text': hits(reference['dimensions'], texts, 'value'),
                  'level_text': hits(reference['levels'], texts, 'text'),
                  'ral_code_text': hits(reference['materials'], texts, 'code'),
                  'structured_dimensions': sum(len(p.get('dimensions', [])) for p in data['pages']),
                  'structured_levels': sum(len(p.get('level_marks', [])) for p in data['pages']),
                  'scale_calibration': 'not certified',
                  'artifact': str(path.relative_to(root))}
        rows = []
        for ref in reference['rows']:
            matched = any(ref['key'] in ' '.join(str(x or '') for x in row)
                          and ref['value'] in [str(x) for x in row]
                          for row in tables.get(ref['page'], []))
            rows.append({'reference': ref, 'found': matched})
        record['schedule_rows'] = {'correct': sum(x['found'] for x in rows), 'denominator': len(rows), 'samples': rows}
        if route == 'A':
            record['reader_observations'] = [
                {'page': p['reference']['pdf_page'], 'status': p['status'], 'counts': p['counts'],
                 'axes': len(p['axes']), 'dimensions': len(p['dimensions']), 'levels': len(p['level_marks']),
                 'legend_candidates': len(p['legend']), 'scale': p['scale']}
                for p in data['pages']]
        if route == 'C':
            record['tables'] = {tool: sum(len(p[tool]) for p in data['pages'])
                                for tool in ['pymupdf_tables', 'pdfplumber_tables']}
        summary['routes'][route] = record
    bpages = {'elv': [(18, 'elv-B-inspected.json')],
              'cod20207': [(1, 'cod20207-B1-inspected.json'), (5, 'cod20207-B-inspected.json')],
              'tec26': [(3, 'tec26-B-inspected.json')]}[album]
    texts = {page: [x['text'] for x in read(root / filename)['text']] for page,filename in bpages}
    summary['routes']['B'] = {
        'pages': [{'page': page, **{k:v for k,v in read(root / filename).items() if k != 'text'}} for page,filename in bpages],
        'dimension_text': hits([x for x in reference['dimensions'] if x['page'] in texts], texts, 'value'),
        'level_text': hits([x for x in reference['levels'] if x['page'] in texts], texts, 'text'),
        'ral_code_text': hits([x for x in reference['materials'] if x['page'] in texts], texts, 'code'),
        'sample_only': True, 'model_scale': 'unknown', 'structured_dimensions': 0,
        'structured_rows': 0,
    }
    b2 = read(root / f'{album}-B2-v001/result.json')
    summary['routes']['B2'] = {k: v for k,v in b2.items() if k not in ['text', 'drops']}
    summary['routes']['B2']['drops_count'] = len(b2['drops'])
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    refs = read(Path(__file__).with_name('reference.json'))
    a.out.mkdir(parents=True, exist_ok=False)
    for album in ['elv', 'cod20207', 'tec26']:
        data = make_summary(a.root, album, refs[album])
        (a.out / f'{album}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(album, {k: {'seconds': v.get('seconds'), 'dimension_text':v.get('dimension_text',{}).get('correct'),
                         'levels':v.get('level_text',{}).get('correct'), 'ral':v.get('ral_code_text',{}).get('correct'),
                         'rows':v.get('schedule_rows',{}).get('correct')} for k,v in data['routes'].items()})


if __name__ == '__main__':
    main()
