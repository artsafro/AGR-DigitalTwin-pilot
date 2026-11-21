"""new-case: source-bound Cyrillic OCR and metered vision ROI observations (#1236).

No observation is measured geometry or approved material/row binding. Every ROI
has an architect question; no ground truth, calibration or approval is inferred.
Backends receive (PDF path, region), vision additionally receives raw OCR text.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _observation(call, *args, metered=False):
    value = None
    try:
        value = call(*args)
        if not isinstance(value, dict) or not isinstance(value.get('text'), str):
            raise ValueError('backend must supply original text')
        if not isinstance(value.get('engine'), str) or not value['engine'] or not _positive(value.get('seconds')):
            raise ValueError('missing engine or positive finite elapsed seconds')
        if metered and any(type(value.get(k)) is not int or value[k] <= 0 for k in ('input_tokens', 'output_tokens')):
            raise ValueError('missing positive integer token usage')
        if value.get('status', 'observed') != 'observed':
            raise ValueError(f'backend status: {value.get("status")}')
        return dict(json.loads(json.dumps(value, allow_nan=False)), status='observed')
    except Exception as exc:
        label = value.get('text') if isinstance(value, dict) else None
        return dict(status='failed', text=label if isinstance(label,str) else None,
                    error=f'{type(exc).__name__}: {exc}',
                    seconds=None, input_tokens=None, output_tokens=None)


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate_regions(regions):
    """Validate explicit source locators without running backends or writing."""
    if not isinstance(regions, list) or not regions:
        raise ValueError('regions must be a nonempty list')
    seen, locators = set(), set()
    for region in regions:
        if not isinstance(region, dict) or set(region) != {'id', 'page', 'bbox', 'kind'}:
            raise ValueError('region requires exactly id, page, bbox, kind')
        ident, page, box, kind = (region[k] for k in ('id', 'page', 'bbox', 'kind'))
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError(f'invalid or duplicate region id: {ident!r}')
        seen.add(ident)
        if type(page) is not int or page < 1:
            raise ValueError('page must be a positive integer')
        if not isinstance(box, (list, tuple)) or len(box) != 4 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in box
        ) or not (0 <= box[0] < box[2] and 0 <= box[1] < box[3]):
            raise ValueError('invalid finite positive-area bbox')
        if kind not in ('dimension', 'material', 'schedule', 'conflict', 'source_check'):
            raise ValueError(f'unsupported region kind: {kind!r}')
        locator = (page,tuple(box),kind)
        if locator in locators:
            raise ValueError(f'duplicate region locator: {ident}')
        locators.add(locator)


def run_fallback(pdf, output, regions, *, ocr, vision, max_calls_per_page=2,
                 max_tokens_per_page=80000, max_seconds_per_page=180):
    """Observe explicit ROIs; soft token/time circuit breakers, hard call cap.

    Agreement never certifies geometry. Concrete backends validate PDF bounds.
    Source mutation invalidates publication; existing destinations are refused.
    """
    validate_regions(regions)
    regions = json.loads(json.dumps(regions, allow_nan=False))
    if type(max_calls_per_page) is not int or max_calls_per_page <= 0 or not all(
        _positive(x) for x in (max_tokens_per_page, max_seconds_per_page)
    ):
        raise ValueError('budgets must be positive finite values; calls must be integer')
    pdf, output = Path(pdf).resolve(), Path(output).resolve()
    if str(pdf).casefold() == str(output).casefold() or output.exists():
        raise FileExistsError(f'output must be new and distinct from input: {output}')
    before = hashlib.sha256(pdf.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    records, questions, pages = [], [], {}
    for region in regions:
        stats = pages.setdefault(region['page'], dict(page=region['page'], calls=0, input_tokens=0,
            output_tokens=0, vision_seconds=0.0, metering_complete=True, circuit_open=False))
        raw = _observation(ocr, pdf, dict(region, bbox=list(region['bbox'])))
        if stats['calls'] >= max_calls_per_page or stats['circuit_open']:
            checked = dict(status='budget_excluded', text=None)
        else:
            stats['calls'] += 1
            checked = _observation(vision, pdf, dict(region, bbox=list(region['bbox'])), raw['text'], metered=True)
            if checked['status'] == 'observed':
                for key in ('input_tokens', 'output_tokens'):
                    stats[key] += checked[key]
                stats['vision_seconds'] += checked['seconds']
                stats['circuit_open'] = (stats['input_tokens'] + stats['output_tokens'] >= max_tokens_per_page
                                         or stats['vision_seconds'] >= max_seconds_per_page)
            else:
                stats['metering_complete'] = False
                stats['circuit_open'] = True
        reasons = ['binding_unresolved', 'scale_and_units_unverified',
                   'ground_truth_not_independent', 'approval_open']
        if raw['status'] == 'failed':
            reasons.append('ocr_failed')
        if checked['status'] != 'observed':
            reasons.append('vision_budget_excluded' if checked['status'] == 'budget_excluded' else 'vision_failed')
        if stats['circuit_open']:
            reasons.append('vision_budget_or_metering_requires_review')
        if not raw['text'] or not checked['text']:
            reasons.append('missing_value')
        if raw['text'] is not None and checked['text'] is not None and raw['text'] != checked['text']:
            reasons.append('ocr_vision_disagreement')
        records.append(dict(region, ocr=raw, vision=checked, measured_geometry=None))
        questions.append(dict(region, reasons=reasons, ocr_label=raw['text'], vision_label=checked['text'],
                              status='unresolved', recipient='architect'))
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != before:
        raise RuntimeError('source changed; observations invalid and not published')
    for stats in pages.values():
        if not stats['metering_complete']:
            for key in ('input_tokens', 'output_tokens', 'vision_seconds'):
                stats[key] = None
    result = dict(schema='album-fallback/1', sha256=before, passed=False,
                  regions=records, pages=list(pages.values()))
    # Refuse late-created aliases/stale files before writing either report.
    for name in ('questions.json','observations.json'):
        if (output/name).exists() or (output/name).is_symlink():
            raise FileExistsError(f'report destination already exists: {output/name}')
    for name, value in [('questions.json', dict(schema='album-questions/1', sha256=before,
                                               passed=False, questions=questions)),
                        ('observations.json', result)]:
        with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result

