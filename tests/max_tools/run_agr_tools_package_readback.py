"""new-case: #908 branch D: Blender-slot readback of the FBX written by run_agr_tools_package_native.py.

Lab DCC runner job (app blender): the job `inputs` are the FBX files of the Max run (copied into AGR_LAB_WORK_DIR).
For each FBX this runs the pilot validator `tools/qa/validate_package.py <fbx> --profile npm --scene --json` in the
project interpreter (AGR_PYTHON, repo AGR_TOOLS_REPO) with TWINQA_BLENDER = this Blender, inside this job's slot
lock, and requires V002 (FBX 7400, units), V003 'triangulated' and V012 (mesh names) to pass (lab L04 acceptance of
export.ground_fbx). Writes summary.json to AGR_LAB_OUT_DIR; exits non-zero on any miss.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import bpy

WORK = Path(os.environ['AGR_LAB_WORK_DIR'])
OUT = Path(os.environ['AGR_LAB_OUT_DIR'])
REPO = Path(os.environ['AGR_TOOLS_REPO'])
PY = os.environ['AGR_PYTHON']
env = dict(os.environ, TWINQA_BLENDER=bpy.app.binary_path)
summary, errors = {}, []
fbx = sorted(WORK.rglob('*.fbx'))
assert fbx, 'no FBX inputs'
for path in fbx:
    proc = subprocess.run([PY, str(REPO / 'tools' / 'qa' / 'validate_package.py'), str(path), '--profile', 'npm',
                           '--scene', '--json'], capture_output=True, env=env, cwd=str(REPO), timeout=1200)
    try:
        rep = json.loads(proc.stdout.decode('utf-8'))
    except ValueError:
        errors.append('{}: exit {} {}'.format(path.name, proc.returncode, proc.stderr.decode('utf-8', 'replace')[-1500:]))
        continue
    stages = {s['id']: s for s in rep['stages']}
    row = {'exit_code': rep['exit_code'], 'notes': rep['notes'],
           'stages': {k: v['status'] for k, v in stages.items()},
           'findings': {k: ['{}: {}: {}'.format(f['status'], f['name'], f['observed'])
                            for f in v['findings']] for k, v in stages.items() if k in ('V002', 'V003', 'V006', 'V012')}}
    summary[path.name] = row
    tri = [f for f in stages['V003']['findings'] if f['name'] == 'triangulated']
    if stages['V002']['status'] != 'pass' or stages['V012']['status'] != 'pass' or not tri \
            or any(f['status'] != 'pass' for f in tri):
        errors.append('{}: V002 {} V003 triangulated {} V012 {}'.format(
            path.name, stages['V002']['status'], [f['status'] for f in tri], stages['V012']['status']))
(OUT / 'summary.json').write_text(json.dumps({'files': summary, 'errors': errors}, indent=1), encoding='utf-8')
print('AGR_908D_READBACK ' + json.dumps({'errors': errors, 'files': {k: v['stages'] for k, v in summary.items()}})[:3000])
sys.exit(1 if errors else 0)
