"""new-case: immutable, budgeted PDF album indexing with region-level route proposals.

Run ``python -m dt_ai.album.intake INPUT --output NEW_DIRECTORY`` with pdf-review.
Coordinates are paper points, never model measurements. Kinds are unapproved text
heuristics on the first 700 characters (research #1228 compatibility). Outline
indicators are conservative candidates, not recognized glyphs. Routing does not
execute reader/table/OCR stages or certify their results. Every page is retained.

Each page runs in an isolated spawned process with a hard wall deadline including
startup/IPC; timed out workers are terminated and joined. Canonical artifacts omit
volatile wall times; manifest timings describe configured limits. Measure observed
wall time outside this API, so repeated successful indexing is byte-identical.
Output directories must be new: no overwrites, no shared .partial filenames.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import re
import shutil
import tempfile
import time

from dt_ai.album.reader import AlbumExtraMissing, AlbumReadError, EXTRA_HINT


KINDS = [('экспликац', 'schedule'), ('спецификац', 'schedule'),
         ('разрез', 'section'), ('фасад', 'facade'), ('план', 'plan'),
         ('визуализац', '3D')]


def _fitz():
    try:
        import pymupdf
    except ImportError as exc:
        raise AlbumExtraMissing(EXTRA_HINT) from exc
    return pymupdf


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf8')


def _hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _page_base(number):
    return dict(pdf_page=number, printed_sheet=None, title=None, kind='unknown',
                kind_status='unresolved', status='partial', reason='page_not_indexed',
                scale='unknown', units=None, regions=[])


def _inspect_page(source, number):
    fitz = _fitz()
    with fitz.open(source) as doc:
        page = doc[number - 1]
        text = page.get_text()
        blocks = page.get_text('blocks', flags=0)
        item = _page_base(number)
        item.update(kind=next((k for s, k in KINDS if s in text[:700].casefold()), 'unknown'),
                    kind_status='text_heuristic_unapproved', status='indexed', reason=None,
                    size_pt=[page.rect.width, page.rect.height])
        # A sheet must be explicitly labelled; standalone numbers are not guessed.
        match = re.search(r'(?:Лист|Sheet)\s*[:№]?\s*(\d+(?:[.\-/]\d+)*)\b', text, re.I)
        if match:
            item['printed_sheet'] = match.group(1)
        headings = [line.strip() for line in text.splitlines()
                    if any(needle in line.casefold() for needle, _ in KINDS)]
        item['title'] = headings[0] if headings else None
        regions = []
        for block in blocks:
            if block[6] != 0 or not block[4].strip():
                continue
            label = block[4]  # preserve original strings, including disagreements
            table = any(s in label.casefold() for s in ('экспликац', 'спецификац', 'schedule', 'specification'))
            regions.append(dict(bbox=list(block[:4]), indicator='text', label=label,
                                route='table_extraction' if table else 'vector_read',
                                reason='schedule_heading_candidate' if table else 'searchable_text'))
        # Bound output size without materializing the full get_drawings() path tree.
        # Separate indicator buckets even when searchable headers share a tile.
        buckets = {}
        for op, box, *_ in page.get_bboxlog():
            if op in ('fill-text', 'stroke-text', 'ignore-text'):
                continue
            x0, y0, x1, y1 = box
            if not all(math.isfinite(v) for v in box):
                raise ValueError('nonfinite region bbox')
            if op == 'fill-image':
                indicator, route, reason = 'raster', 'ocr_vision', 'raster_requires_roi_verification'
            elif op in ('fill-path', 'stroke-path'):
                if op == 'fill-path' and 0 < x1 - x0 <= 36 and 0 < y1 - y0 <= 36:
                    indicator, route, reason = 'outline_candidate', 'ocr_vision', 'small_filled_paths_may_be_outlined_labels'
                else:
                    indicator, route, reason = 'vector', 'vector_read', 'vector_geometry_scale_unresolved'
            else:
                indicator, route, reason = 'unknown', 'ocr_vision', 'unsupported_display_operation:' + op
            cell = (min(3, max(0, int((x0 + x1) / 2 / page.rect.width * 4))),
                    min(3, max(0, int((y0 + y1) / 2 / page.rect.height * 4))))
            key = (indicator, cell, route, reason)
            if key not in buckets:
                buckets[key] = [list(box), 0]
            bounds, count = buckets[key]
            buckets[key] = [[min(bounds[0], x0), min(bounds[1], y0),
                             max(bounds[2], x1), max(bounds[3], y1)], count + 1]
        for (indicator, cell, route, reason), (bbox, count) in sorted(buckets.items()):
            regions.append(dict(bbox=bbox, indicator=indicator, label=None,
                                route=route, reason=reason, operations=count))
        if not regions:
            item.update(status='partial', reason='empty_page')
        item['regions'] = [dict(region_id=f'p{number}-r{i + 1}', **r) for i, r in enumerate(regions)]
        return item


def _worker(source, number, destination):
    try:
        result = _inspect_page(source, number)
    except Exception as exc:
        result = _page_base(number)
        result['reason'] = 'page_error:' + type(exc).__name__
    Path(destination).write_bytes(_json_bytes(result))


def _budgeted_page(source, number, budget, scratch):
    destination = scratch / f'page-{number}.json'
    process = multiprocessing.get_context('spawn').Process(
        target=_worker, args=(str(source), number, str(destination)))
    started = time.monotonic()
    process.start()
    process.join(max(0, budget - (time.monotonic() - started)))
    expired = process.is_alive() or time.monotonic() - started >= budget
    if process.is_alive():
        process.terminate()
        process.join()
    exitcode = process.exitcode
    process.close()
    if expired or exitcode != 0 or not destination.is_file():
        item = _page_base(number)
        item['reason'] = 'page_budget_exhausted' if expired else 'page_worker_failed'
        return item
    return json.loads(destination.read_bytes())


def index_album(source, output, *, page_budget_s=10.0):
    """Freeze one source into a fresh directory; publish deterministic index/manifest.

    Return a non-certifying manifest. Errors raise before publication; a retained
    incomplete directory is never reused. Failed/partial page work is explicit.
    """
    if isinstance(page_budget_s, bool) or not isinstance(page_budget_s, (int, float)) or not math.isfinite(page_budget_s) or page_budget_s <= 0:
        raise ValueError('page_budget_s must be finite and positive')
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise AlbumReadError('not_found', str(source))
    if output.exists():
        raise FileExistsError('output must be a new directory: ' + str(output))
    digest = _hash(source)
    fitz = _fitz()
    # Snapshot before parsing: live source mutation cannot affect page workers.
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / 'source.pdf'
    with source.open('rb') as src, frozen.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    if _hash(frozen) != digest or _hash(source) != digest:
        raise AlbumReadError('source_changed', str(source))
    try:
        with fitz.open(frozen) as doc:
            if doc.needs_pass:
                raise AlbumReadError('encrypted', str(source))
            count = len(doc)
            if not count or not doc.is_pdf:
                raise AlbumReadError('unsupported', 'requires nonempty PDF')
            metadata = doc.metadata
            version = fitz.VersionBind
    except AlbumReadError:
        raise
    except Exception as exc:
        raise AlbumReadError('corrupt', str(source)) from exc
    with tempfile.TemporaryDirectory(prefix='.workers-', dir=output) as scratch:
        pages = [_budgeted_page(frozen, n, float(page_budget_s), Path(scratch))
                 for n in range(1, count + 1)]
    if _hash(source) != digest or _hash(frozen) != digest:
        raise AlbumReadError('source_changed', str(source))
    identity = dict(sha256=digest, bytes=frozen.stat().st_size, frozen_file='source.pdf')
    index = dict(schema='album-index/1', source=identity, page_count=count, pages=pages)
    payload = _json_bytes(index)
    manifest = dict(schema='album-manifest/1', source=identity, page_count=count,
                    accounted_pages=count, excluded_pages=[],
                    status='partial' if any(p['status'] == 'partial' for p in pages) else 'indexed',
                    passed=False, unresolved=['binding', 'calibration', 'ground_truth', 'approval'],
                    tools=dict(pymupdf=version, router='album-intake/1'), metadata=metadata,
                    timings=dict(page_budget_s=float(page_budget_s),
                                 policy='hard_wall_per_page_including_spawn',
                                 observed_seconds=None,
                                 reason='volatile wall times belong in external benchmark receipts'),
                    album_index_sha256=hashlib.sha256(payload).hexdigest())
    # Exclusive publication in a reserved directory; no clobbered .partial paths.
    for name, data in [('album_index.json', payload), ('manifest.json', _json_bytes(manifest))]:
        with (output / name).open('xb') as stream:
            stream.write(data)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--page-budget-s', type=float, default=10.0)
    args = parser.parse_args(argv)
    try:
        manifest = index_album(args.source, args.output, page_budget_s=args.page_budget_s)
    except (ValueError, OSError, AlbumExtraMissing) as exc:
        print(str(exc))
        return 2
    print(json.dumps({'status': manifest['status'], 'passed': False,
                      'accounted_pages': manifest['accounted_pages']}))
    return 2 if manifest['status'] == 'partial' else 0


if __name__ == '__main__':
    raise SystemExit(main())
