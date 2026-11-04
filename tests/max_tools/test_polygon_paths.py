"""new-case: polygon output paths that resolve to an input write nothing (#885)."""
from pathlib import Path


def test_output_equal_to_input_exits_and_writes_nothing(tmp_path):
    from test_polygon_support import check_paths
    src = tmp_path / 'in'
    src.mkdir()
    marker = src / 'keep.txt'
    marker.write_text('keep', encoding='utf-8')
    before = marker.read_bytes()
    try:
        check_paths(src, src, tmp_path / 'report.json', tmp_path / 'temp')
        raised = False
    except SystemExit:
        raised = True
    assert raised
    assert marker.read_bytes() == before
    assert not (tmp_path / 'report.json').exists()
    assert not (tmp_path / 'temp').exists()


def test_output_inside_input_and_same_file_aliases_are_refused(tmp_path):
    from test_polygon_support import check_paths
    src = tmp_path / 'src'
    (src / 'geojson').mkdir(parents=True)
    victim = src / 'geojson' / 'valid_oks.geojson'
    victim.write_text('{}', encoding='utf-8')
    before = victim.read_bytes()
    with_output_inside = False
    try:
        check_paths(src, src / 'out', src / 'out' / 'report.json', tmp_path / 'temp')
    except SystemExit:
        with_output_inside = True
    assert with_output_inside
    same = False
    try:
        check_paths(src, tmp_path / 'out', victim, tmp_path / 'temp')
    except SystemExit:
        same = True
    assert same
    twin = False
    try:
        check_paths(src, tmp_path / 'out', tmp_path / 'same.json', tmp_path / 'same.json')
    except SystemExit:
        twin = True
    assert twin
    assert victim.read_bytes() == before
    assert not (tmp_path / 'out').exists()


def test_distinct_paths_are_accepted_and_do_not_create_files(tmp_path):
    from test_polygon_support import check_paths
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'a.txt').write_text('a', encoding='utf-8')
    out = tmp_path / 'out'
    report = tmp_path / 'report.json'
    temp = tmp_path / 'temp'
    check_paths(src, out, report, temp)
    assert (src / 'a.txt').read_text(encoding='utf-8') == 'a'
    assert not out.exists() and not report.exists() and not temp.exists()


def test_builder_does_not_construct_editable_poly():
    """Max 2024/2026: Editable_Poly is not creatable. The builder converts a primitive."""
    root = Path(__file__).resolve().parents[2] / 'test-polygon' / 'build'
    text = '\n'.join(path.read_text(encoding='utf-8') for path in sorted(root.glob('*.py')))
    assert 'Editable_Poly(' not in text
    assert 'convertToPoly' in text
    assert 'setNumMaps' in text


def test_runner_does_not_delete_inputs():
    text = Path(__file__).resolve().parents[2].joinpath('test-polygon', 'run_polygon.py').read_text(encoding='utf-8')
    assert 'unlink' not in text
    assert 'rmtree' not in text
    assert '.remove(' not in text
