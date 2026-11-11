"""new-case: disposable, page-referenced A/C/D PDF extraction benchmark (#1228).

No production rules or customer input is changed. Output is a new directory only.
Raw table cells, OCR strings and reader candidates are observations, not approved facts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time


def validate_pages(pages, count):
    if not pages or any(type(p) is not int or not 1 <= p <= count for p in pages):
        raise ValueError('pages must be nonempty, unique, 1-based integers in range')
    if len(set(pages)) != len(pages):
        raise ValueError('duplicate page')
    return pages


def score_numeric(actual, expected, tolerance):
    values = (actual, expected, tolerance)
    return (all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                for x in values) and tolerance > 0 and abs(actual - expected) < tolerance)


def reserve_output(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if str(source).casefold() == str(output).casefold():
        raise ValueError('output aliases input')
    if output.exists():
        if output.is_file() and source.samefile(output):
            raise ValueError('output aliases input (hardlink)')
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=False)
    return output


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--route', choices=['A', 'C', 'D'], required=True)
    parser.add_argument('--pages', type=int, nargs='+', required=True)
    args = parser.parse_args()
    import pymupdf
    before = digest(args.pdf)
    with pymupdf.open(args.pdf) as doc:
        if doc.needs_pass:
            raise ValueError('encrypted PDF')
        validate_pages(args.pages, len(doc))
        out = reserve_output(args.pdf, args.out)
        start = time.perf_counter()
        engine = None
        if args.route == 'D':
            from rapidocr import RapidOCR
            engine = RapidOCR(params={'Global.log_level': 'error'})
        records = []
        for number in args.pages:
            page = doc[number - 1]
            ref = {'pdf_sha256': before, 'pdf_page': number, 'sheet': None,
                   'sheet_note': 'physical PDF page; printed sheet must be verified'}
            t0 = time.perf_counter()
            record = {'reference': ref, 'route': args.route, 'status': 'observed'}
            if args.route == 'A':
                from dt_ai.album.reader import read_page
                reading = read_page(args.pdf, number)
                result = reading.to_dict()
                record.update({k: result[k] for k in ['status', 'axes', 'dimensions', 'level_marks',
                                                    'legend', 'scale', 'findings']})
                record['counts'] = {k: len(result[k]) for k in ['paths', 'lines', 'spans']}
                record['raw_text'] = [{'text': x['text'], 'bbox': x['bbox'], 'reference': ref}
                                      for x in result['spans']]
            elif args.route == 'C':
                tables = page.find_tables()
                record['pymupdf_tables'] = [{'bbox': list(t.bbox), 'cells': t.extract(), 'reference': ref}
                                             for t in tables.tables]
                import pdfplumber
                with pdfplumber.open(args.pdf) as plumber:
                    record['pdfplumber_tables'] = [
                        {'cells': cells, 'reference': ref}
                        for cells in plumber.pages[number - 1].extract_tables()]
            else:
                import numpy as np
                pix = page.get_pixmap(dpi=150, alpha=False)
                image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                ocr = engine(image)
                record['render'] = {'dpi': 150, 'width': pix.width, 'height': pix.height}
                record['ocr'] = [] if ocr.txts is None else [
                    {'text': text, 'confidence': float(score), 'bbox_px': box.tolist(), 'reference': ref}
                    for text, score, box in zip(ocr.txts, ocr.scores, ocr.boxes)]
                record['ocr_config'] = 'RapidOCR default bundled model; no language accuracy assumed'
            record['seconds'] = round(time.perf_counter() - t0, 4)
            records.append(record)
            print(f'{args.route} page={number} seconds={record["seconds"]}', flush=True)
        after = digest(args.pdf)
        summary = {'schema': 'pdf-research/1', 'source': str(args.pdf), 'sha256': before,
                   'input_unchanged': before == after, 'route': args.route,
                   'pages_requested': args.pages, 'pages': records,
                   'total_seconds': round(time.perf_counter() - start, 4),
                   'status': 'observed' if before == after else 'invalid_input_changed'}
        (out / 'result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False),
                                         encoding='utf-8')
        if before != after:
            raise RuntimeError('source changed; results invalid')
        print(json.dumps({'result': str(out / 'result.json'), 'seconds': summary['total_seconds']}))


if __name__ == '__main__':
    main()
