"""new-case: alternate free PDF->DXF geometry/text probe, not a production converter.

PyMuPDF + ezdxf; coordinates remain PAPER POINTS. No guessed model scale,
no invented DIMENSION entities. Fills/clips/images/dashes/fonts are not reproduced.
Every path item and text span is emitted or listed as dropped. Readback is mandatory.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import time


def inspect_dxf(path):
    import ezdxf
    from ezdxf import bbox
    doc = ezdxf.readfile(path)
    model = doc.modelspace()
    text = [{'text': e.plain_text() if e.dxftype() == 'MTEXT' else e.dxf.text,
             'insert': list(e.dxf.insert), 'layer': e.dxf.layer}
            for e in model if e.dxftype() in ('TEXT', 'MTEXT')]
    extents = bbox.extents(model, fast=True)
    return {'entity_types': dict(Counter(e.dxftype() for e in model)),
            'layers': [l.dxf.name for l in doc.layers], 'insunits': doc.header.get('$INSUNITS'),
            'extents': [list(extents.extmin), list(extents.extmax)] if extents.has_data else None,
            'text': text, 'model_scale': 'unknown', 'source': str(path)}


def main():
    import pymupdf
    import ezdxf
    from probe import reserve_output, validate_pages, digest
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', required=True, type=Path)
    parser.add_argument('--page', required=True, type=int)
    parser.add_argument('--out', required=True, type=Path)
    a = parser.parse_args()
    sha = digest(a.pdf)
    with pymupdf.open(a.pdf) as pdf:
        validate_pages([a.page], len(pdf))
        out = reserve_output(a.pdf, a.out)
        t0 = time.perf_counter()
        page = pdf[a.page - 1]
        dxf = ezdxf.new('R2018')
        dxf.header['$INSUNITS'] = 0  # deliberately unitless paper points
        dxf.appids.add('PDF_RESEARCH')
        model = dxf.modelspace()
        emitted, drops = 0, []
        def point(p):
            return (p[0], page.rect.height - p[1], 0)
        def ref(e):
            e.set_xdata('PDF_RESEARCH', [(1000, sha), (1071, a.page)])
        for path_index, path in enumerate(page.get_drawings()):
            for index, item in enumerate(path['items']):
                kind = item[0]
                if kind == 'l':
                    entity = model.add_line(point(item[1]), point(item[2]))
                elif kind in ('re', 'qu'):
                    box = item[1]
                    vertices = [box.top_left, box.top_right, box.bottom_right, box.bottom_left] if kind == 're' else [box.ul, box.ur, box.lr, box.ll]
                    entity = model.add_polyline3d([point(p) for p in vertices], close=True)
                elif kind == 'c':
                    entity = model.add_open_spline([point(p) for p in item[1:5]], degree=3)
                else:
                    drops.append({'path': path_index, 'item': index, 'reason': f'unsupported {kind}'})
                    continue
                ref(entity)
                emitted += 1
        spans = [span for block in page.get_text('dict')['blocks'] if 'lines' in block
                 for line in block['lines'] for span in line['spans']]
        for index, span in enumerate(spans):
            if not span['text'].strip():
                drops.append({'span': index, 'reason': 'blank text'})
                continue
            entity = model.add_text(span['text'], dxfattribs={'height': span['size'], 'insert': point(span['origin'])})
            ref(entity)
            emitted += 1
        path = out / 'page.dxf'
        dxf.saveas(path)
        result = inspect_dxf(path)
        result.update({'route': 'B2-PyMuPDF-ezdxf', 'reference': {'pdf_sha256': sha, 'pdf_page': a.page},
                       'emitted': emitted, 'drops': drops, 'seconds': round(time.perf_counter()-t0, 4),
                       'input_unchanged': digest(a.pdf) == sha,
                       'losses': ['fills', 'clips', 'images', 'fonts', 'dashes', 'text rotation']})
        (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        if not result['input_unchanged']:
            raise RuntimeError('input changed')
        print(json.dumps({k: v for k,v in result.items() if k not in ['text', 'drops']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
