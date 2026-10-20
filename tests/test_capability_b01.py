"""new-case: repository-only capability session and benchmark evidence contracts."""
import json

from twinqa.evals.graders import GRADERS

IDS = ('bbox', 'levels', 'floor_areas', 'silhouettes', 'mesh', 'triangle_budget',
       'opening_planes', 'material_ids', 'decor', 'orientation')


def report():
    return {'passed': True, 'failed': [], 'not_measured': [],
            'checks': [{'id': name, 'status': 'pass', 'value': 0, 'limit': 0} for name in IDS]}


def test_complete_benchmark_reports(tmp_path):
    paths = []
    for name in ('report', 'etalon-self'):
        path = tmp_path / f'{name}.json'
        path.write_text(json.dumps(report()), encoding='utf-8')
        paths.append(path)
    assert 'capability_b01' in GRADERS
    row = GRADERS['capability_b01'][0]({'benchmark': [paths[0]], 'self_check': [paths[1]]})
    assert row['passed'] is True
    assert row['measured'] == '20/20'
