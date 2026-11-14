"""tools/assets/intake_identify.py: status of an A101 article hit (PR #1098 review P1-1)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('intake_identify_t', ROOT / 'tools/assets/intake_identify.py')
assert _spec is not None and _spec.loader is not None
ii = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ii)


def _maf_rec(dims_mm, library_bboxes):
    """Build the MAF record the way identify() does for an A101 article hit."""
    return {'kind': 'maf', 'library': ['A101_Bench_AB-1234_High'] * len(library_bboxes), 'project_sets': [],
            'dims_mm': dims_mm,
            'library_dims': [ii.dims_check(dims_mm, (b or {}).get('high')) for b in library_bboxes]}


def test_spec_size_but_library_has_no_bbox_says_size_not_checked():
    status, why = ii._status(_maf_rec([3000, 600, 800], [{}]))
    assert 'no spec size' not in why
    assert status == 'exists' and 'not checked' in why.lower() and 'bbox' in why


def test_spec_without_size_still_reports_no_spec_size():
    status, why = ii._status(_maf_rec([None, None, None], [{'high': {'x': 3000, 'y': 600, 'z': 800}}]))
    assert (status, why) == ('exists', 'A101 article (no spec size to check)')


def test_spec_size_matches_library_bbox():
    status, why = ii._status(_maf_rec([3000, 600, 800], [{'high': {'x': 3010, 'y': 600, 'z': 800}}]))
    assert (status, why) == ('exists', 'A101 article')


def test_spec_size_off_library_bbox_is_variant():
    status, _ = ii._status(_maf_rec([3000, 600, 800], [{'high': {'x': 2000, 'y': 600, 'z': 800}}]))
    assert status == 'variant'
