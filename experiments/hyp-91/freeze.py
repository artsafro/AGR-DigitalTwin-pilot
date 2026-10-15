"""Freeze labelled synthetic inputs and tracked controls before any audit execution."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCES = ['technical_library/mesh_audit/core.py', 'tests/test_shared_library.py']
CONTROL_NAMES = ['outward_unit_cube', 'test_mesh_closed_cube_report_counters_are_zero',
                 'test_mesh_bowtie_quad_counts_one_polygon']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def control_nodes():
    tree = ast.parse((ROOT / SOURCES[1]).read_text(encoding='utf-8'))
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name in CONTROL_NAMES]


def controls():
    nodes = {node.name: node for node in control_nodes()}
    scope = {}
    exec(compile(ast.Module(body=[nodes['outward_unit_cube']], type_ignores=[]),
                 SOURCES[1], 'exec'), scope)
    cube = scope['outward_unit_cube']()
    # Execute the unchanged setup statements, stopping before inspect_mesh.
    setup = []
    for statement in nodes['test_mesh_bowtie_quad_counts_one_polygon'].body:
        if isinstance(statement, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'result' for t in statement.targets):
            break
        setup.append(statement)
    exec(compile(ast.Module(body=setup, type_ignores=[]), SOURCES[1], 'exec'), scope)
    return [dict(id='outward_unit_cube', vertices=cube[0], faces=cube[1], expected=0),
            dict(id='test_mesh_bowtie_quad_counts_one_polygon',
                 vertices=scope['vertices'], faces=scope['faces'], expected=1)]


def main():
    outlines = [
        ('square', 0, [(0,0),(3,0),(3,3),(0,3)]),
        ('L', 0, [(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)]),
        ('U', 0, [(0,0),(3,0),(3,3),(2,3),(2,1),(1,1),(1,3),(0,3)]),
        ('arrow', 0, [(0,0),(3,0),(1,1),(3,3),(0,3)]),
        ('crossed_A', 1, [(0,0),(3,3),(0,3),(3,0)]),
        ('crossed_B', 1, [(0,0),(4,3),(0,4),(3,0)]),
    ]
    cases = []
    for name, label, points in outlines:
        for plane in ('XY', 'XZ', 'YZ'):
            vertices = [(x,y,0) if plane == 'XY' else (x,0,y) if plane == 'XZ'
                        else (0,x,y) for x,y in points]
            for shift in range(len(points)):
                boundary = list(range(shift, len(points))) + list(range(shift))
                for reverse in (False, True):
                    cases.append(dict(id=f'{name}/{plane}/shift-{shift}/reverse-{int(reverse)}',
                                      outline=name, plane=plane, shift=shift, reverse=reverse,
                                      vertices=vertices, faces=[boundary[::-1] if reverse else boundary],
                                      expected=label, baseline_prediction=int(name != 'square')))
    for control in controls():
        cases.append(dict(control, outline='control', baseline_prediction=control['expected']))
    snapshot = dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                text=True).strip(),
                    branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT,
                                                  text=True).strip(),
                    source_sha256={p: sha(ROOT / p) for p in SOURCES})
    table = [
        ['Clean concave false positives per repetition', '>=1 predicted', '<1 baseline FP', None],
        ['Candidate clean false positives per repetition', 'may flag concave', '>0', None],
        ['Candidate crossed false negatives per repetition', '0 predicted', '>0', None],
        ['Tracked controls preserved per repetition', '2/2 predicted', '<2/2', None],
        ['Candidate transform-invariant outline groups', 'may vary by shift', '<6/6', None],
        ['Counter-identical repetitions', '3 predicted', '<3', None],
        ['Runtime seconds per complete batch (3 runs)', 'unmeasured', 'descriptive only', None],
    ]
    frozen = dict(snapshot=snapshot, synthetic=True, units='metres', repetitions=3,
                  orientation_tolerance_m2=1e-10,
                  prediction_columns=['metric', 'baseline', 'rejection threshold', 'measured median'],
                  acceptance_table=table, outlines=[dict(name=n, expected=e, points=p) for n,e,p in outlines],
                  transformations='Each shift s=0..n-1 of index boundary, then unchanged or reversed; XY/XZ/YZ',
                  cases=cases, delivery_passed=False)
    path = HERE / 'frozen.json'
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(frozen, indent=2) + '\n')
    with (HERE / 'frozen.sha256').open('x', encoding='utf-8') as stream:
        stream.write(sha(path) + '  frozen.json\n')
    print(f'FROZEN: {len(cases)} cases; sha256={sha(path)}; no audit calls executed')


if __name__ == '__main__':
    main()
