"""new-case: frozen three-album fallback text scoring and reproduction CLI (#1236).

Reference-first ROI audit, not exhaustive album accuracy or geometry acceptance.
Word precision/recall use multiset overlap of Cyrillic words after casefolding;
line splits/punctuation do not affect score, order/binding are NOT evaluated.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time


def text_scores(reference, prediction):
    """Cyrillic word bag P/R; absent denominators remain unknown."""
    expected = Counter(re.findall(r'[а-яё]+',reference.casefold()))
    actual = Counter(re.findall(r'[а-яё]+',prediction.casefold()))
    hit = sum((expected & actual).values())
    total, proposed = sum(expected.values()), sum(actual.values())
    return dict(correct=hit, reference=total, predicted=proposed,
                recall=hit/total if total else None, precision=hit/proposed if proposed else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--references',type=Path,default=Path(__file__).with_name('fallback-reference.json'))
    args = parser.parse_args()
    from dt_ai.album.fallback import run_fallback
    from dt_ai.album.fallback_backends import RapidCyrillicOCR, CodexROIVision
    import pymupdf
    refs_bytes = args.references.read_bytes()
    refs = json.loads(refs_bytes)
    # Resolve/verify all source identities before initializing models or writing outputs.
    sources = []
    for album in refs['albums']:
        source = (args.corpus/album['file']).resolve()
        if hashlib.sha256(source.read_bytes()).hexdigest() != album['sha256']:
            raise ValueError(f'source hash mismatch: {album["id"]}')
        with pymupdf.open(source) as doc:
            if doc.needs_pass or len(doc) != album['pages']:
                raise ValueError(f'source page count/encryption mismatch: {album["id"]}')
        sources.append(source)
    output = args.out.resolve()
    if output.exists() or any(output == p or output in p.parents for p in sources):
        raise ValueError('output must be a new directory, not an input or input ancestor')
    output.mkdir(parents=True,exist_ok=False)
    model_root = output/'models'
    start = time.perf_counter()
    baseline = RapidCyrillicOCR(model_root,cyrillic=False)
    cyrillic = RapidCyrillicOCR(model_root)
    setup_seconds = time.perf_counter()-start
    vision = CodexROIVision(output/'vision-raw')
    summary = dict(schema='album-fallback-benchmark/1', reference_sha256=hashlib.sha256(refs_bytes).hexdigest(),
                   label_provenance={k:refs[k] for k in ('labelled_by','labelled_on','independence','decision')},
                   setup_seconds=setup_seconds, passed=False, albums=[])
    for album,source in zip(refs['albums'],sources):
        start = time.perf_counter()
        regions = [{k:r[k] for k in ('id','page','bbox','kind')} for r in album['regions']]
        baseline_results = [baseline(source,r) for r in regions]
        observed = run_fallback(source,output/album['id'],regions,ocr=cyrillic,vision=vision)
        scores = []
        for reference,default,record in zip(album['regions'],baseline_results,observed['regions']):
            scored = dict(id=reference['id'], page=reference['page'], bbox=reference['bbox'],
                          baseline_seconds=default['seconds'],cyrillic_seconds=record['ocr']['seconds'])
            if reference['reference'] is not None:
                scored['baseline'] = text_scores(reference['reference'],default['text'])
                scored['cyrillic'] = text_scores(reference['reference'],record['ocr']['text'] or '')
                scored['vision'] = text_scores(reference['reference'],record['vision']['text'] or '')
            else:
                scored['critical_values'] = reference['critical_values']
                for key,text in [('baseline',default['text']),('cyrillic',record['ocr']['text']),('vision',record['vision']['text'])]:
                    scored[key] = {value: bool(re.search(r'(?<!\d)'+re.escape(value)+r'(?!\d)', text or ''))
                                   for value in reference['critical_values']}
            scores.append(scored)
        (output/album['id']/'baseline.json').write_text(json.dumps(baseline_results,ensure_ascii=False,indent=2),encoding='utf-8')
        questions_path = output/album['id']/'questions.json'
        questions = json.loads(questions_path.read_text(encoding='utf-8'))
        for question,reference in zip(questions['questions'],album['regions']):
            if reference.get('unresolved'):
                question['source_question'] = reference['unresolved']
        questions_path.write_text(json.dumps(questions,ensure_ascii=False,indent=2),encoding='utf-8')
        entry = dict(id=album['id'],sha256=album['sha256'],seconds=time.perf_counter()-start,
                     pages=observed['pages'],scores=scores,
                     page_accounting=[dict(page=p,status='ROI_observed' if any(r['page']==p for r in regions)
                                          else 'not_requested',reason='frozen targeted ROI audit, not full-album OCR')
                                      for p in range(1,album['pages']+1)])
        summary['albums'].append(entry)
        (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps(dict(album=album['id'],seconds=entry['seconds'],vision=observed['pages'])),flush=True)
    if args.references.read_bytes() != refs_bytes or any(hashlib.sha256(p.read_bytes()).hexdigest()!=a['sha256']
                                                       for a,p in zip(refs['albums'],sources)):
        raise RuntimeError('frozen input changed; benchmark invalid')


if __name__ == '__main__':
    main()
