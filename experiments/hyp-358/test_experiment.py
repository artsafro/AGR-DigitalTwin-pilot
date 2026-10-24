"""Synthetic fail-closed probes and real-excerpt checks for #358; new-case."""
import importlib.util
from pathlib import Path

import ezdxf
import pytest

spec = importlib.util.spec_from_file_location('hyp358', Path(__file__).with_name('experiment.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.mark.parametrize('tol', [float('nan'), float('inf'), -1.0, 0.0])
def test_nonfinite_or_nonpositive_tolerance_is_rejected(tol):
    doc = ezdxf.new()
    pl = doc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1)], close=True)
    with pytest.raises(ValueError, match='tolerance'):
        m.checked_boundary(doc, pl.dxf.handle, tol)


@pytest.mark.parametrize('key', sorted(m.LIMITS))
def test_generated_threshold_probes(key):
    import math

    limit = m.LIMITS[key]
    # Seven metrics, seven values each. Equality never passes.
    low, high = math.nextafter(limit, 0), math.nextafter(limit, math.inf)
    assert m.threshold_pass(key, limit) is False
    assert m.threshold_pass(key, low) is (key != 'reduction')
    assert m.threshold_pass(key, high) is (key == 'reduction')
    for value in (float('nan'), float('inf'), -1, None):
        with pytest.raises(ValueError, match=key):
            m.threshold_pass(key, value)


@pytest.mark.parametrize('key', ['absent', '', 'material/unknown'])
def test_unknown_metric_names_the_key(key):
    with pytest.raises(ValueError) as exc:
        m.threshold_pass(key, 0)
    assert repr(key)[1:-1] in str(exc.value)


@pytest.mark.parametrize('kind', ['empty', 'open', 'bowtie', 'nan', 'inf', 'unsupported', 'absent'])
def test_generated_bad_boundaries(kind):
    doc = ezdxf.new()
    pts = [(0, 0), (1, 0), (1, 1), (0, 1)]
    if kind == 'empty':
        pts = []
    if kind == 'bowtie':
        pts = [(0, 0), (1, 1), (1, 0), (0, 1)]
    if kind in ('nan', 'inf'):
        pts[1] = (float(kind), 0)
    pl = doc.modelspace().add_lwpolyline(pts, close=kind != 'open')
    handle = pl.dxf.handle
    if kind == 'unsupported':
        handle = doc.modelspace().add_line((0, 0), (1, 1)).dxf.handle
    if kind == 'absent':
        handle = 'ABSENT'
    with pytest.raises(ValueError):
        m.checked_boundary(doc, handle, 0.0005)


@pytest.mark.parametrize('radius', [0.1, 1, 10, 100])
def test_generated_circles_against_independent_oracle(radius):
    import math

    # Synthetic, two semicircles. Fixed A/B tolerances, not a search.
    doc = ezdxf.new()
    pl = doc.modelspace().add_lwpolyline(
        [(radius, 0, 1), (-radius, 0, 1)], format='xyb', close=True)
    area, perimeter = m.analytic(list(pl.get_points('xyb')))
    assert area == pytest.approx(math.pi*radius**2, rel=1e-12)
    assert perimeter == pytest.approx(2*math.pi*radius, rel=1e-12)
    for tol in (0.0001, 0.0005):
        poly = m.checked_boundary(doc, pl.dxf.handle, tol)
        assert 0 <= area-poly.area <= 2/3*tol*perimeter
        # Exact regular inscribed polygon perimeter, independent of arc_points.
        n = len(poly.exterior.coords)-1
        assert poly.length == pytest.approx(n*2*radius*math.sin(math.pi/n), rel=1e-12)
        coords = list(poly.exterior.coords)
        for a, b in zip(coords, coords[1:]):
            midpoint = ((a[0]+b[0])/2, (a[1]+b[1])/2)
            assert radius-math.hypot(*midpoint) <= tol+1e-12


def test_real_evidence_three_reads_all_elements_and_thresholds():
    import json

    evidence = json.loads(Path(__file__).with_name('results.json').read_text())
    assert evidence['delivery_passed'] is False
    assert evidence['verdict'] == 'inconclusive'
    assert evidence['blockers']
    runs = evidence['runs']
    assert len(runs) == 3 and runs[0] == runs[1] == runs[2]
    assert evidence['repeatable'] is True
    assert all(evidence['measured_user_threshold_checks'].values())
    for run in runs:
        assert run['input_sha256'] == m.sha(m.FIXTURE)
        assert run['bulges'] == 4
        accounting = run['element_accounting']
        assert accounting['input'] == accounting['output']+len(accounting['drops']) == 4
        for row in run['rows'].values():
            assert set(row['hatches']) == set(m.HANDLES)
            assert row['valid'] and not row['empty'] and row['holes'] == 0
            for h in row['hatches'].values():
                assert h['issues'] == [] and h['area'] > 0 and h['area_in_plot'] > 0
            checks = row['inventory_checks']
            assert checks['msp_entities'] == checks['sum_layer_type_counts'] == 4
            assert checks['hatch_total'] == checks['hatches_measured'] == 3
            assert checks['hatches_invalid'] == 0
    for path, digest in evidence['code_hashes'].items():
        assert m.sha(m.ROOT/path) == digest


@pytest.mark.parametrize('kind', ['empty', 'partial', 'unknown', 'duplicate', 'unsupported_style', 'missing_xdata'])
def test_missing_or_unmapped_hatches_error_without_source_mutation(tmp_path, kind):
    doc = ezdxf.readfile(m.FIXTURE)
    hatches = list(doc.modelspace().query('HATCH'))
    if kind in ('empty', 'partial'):
        for h in hatches if kind == 'empty' else hatches[:1]:
            doc.modelspace().delete_entity(h)
    elif kind in ('unknown', 'duplicate'):
        key = 'unknown-key' if kind == 'unknown' else hatches[1].get_xdata('AGR')[0][1]
        hatches[0].set_xdata('AGR', [(1000, key)])
    elif kind == 'missing_xdata':
        hatches[0].discard_xdata('AGR')
    else:
        # ezdxf's property setter normalises invalid values; raw attribute is intentional.
        hatches[0].dxf.__dict__['hatch_style'] = 99
    path = tmp_path/'synthetic.dxf'
    doc.saveas(path)
    before = path.read_bytes()
    with pytest.raises(ValueError) as exc:
        m.measure(path)
    if kind == 'unknown':
        assert 'unknown-key' in str(exc.value)
    assert path.read_bytes() == before


def test_extra_element_has_named_drop(tmp_path):
    doc = ezdxf.readfile(m.FIXTURE)
    extra = doc.modelspace().add_point((1, 2))
    path = tmp_path/'synthetic-extra.dxf'
    doc.saveas(path)
    before = path.read_bytes()
    run = m.measure(path)
    accounting = run['element_accounting']
    assert accounting['input'] == accounting['output']+len(accounting['drops']) == 5
    assert accounting['drops'] == [{'handle': extra.dxf.handle, 'type': 'POINT',
                                    'reason': 'not the boundary or a target hatch'}]
    assert path.read_bytes() == before


def test_missing_input_produces_inconclusive_not_pass(tmp_path, monkeypatch):
    import json

    def missing():
        raise FileNotFoundError('synthetic-missing-input.dxf')

    monkeypatch.setattr(m, 'HERE', tmp_path)
    monkeypatch.setattr(m, 'measure', missing)
    m.main()
    result = json.loads((tmp_path/'results.json').read_text())
    assert result['verdict'] == 'inconclusive'
    assert result['delivery_passed'] is False
    assert result['runs'] == []
    assert 'synthetic-missing-input.dxf' in result['error']
    assert 'all_measured_thresholds_satisfied' not in result


@pytest.mark.parametrize('alias', ['existing', 'hardlink'])
def test_existing_output_or_input_alias_never_overwritten(tmp_path, monkeypatch, alias):
    import os

    source = tmp_path/'synthetic-input.dxf'
    source.write_bytes(b'synthetic input: do not overwrite')
    output = tmp_path/'results.json'
    if alias == 'hardlink':
        os.link(source, output)
    else:
        output.write_bytes(b'existing report')
    before = source.read_bytes(), output.read_bytes()

    def missing():
        raise ValueError('synthetic invalid input')

    monkeypatch.setattr(m, 'HERE', tmp_path)
    monkeypatch.setattr(m, 'measure', missing)
    with pytest.raises(FileExistsError):
        m.main()
    assert (source.read_bytes(), output.read_bytes()) == before
    assert not list(tmp_path.glob('*.partial'))
