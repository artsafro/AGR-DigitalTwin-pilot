"""Batch three unchanged-tool jobs; reset only this job-owned, initially empty process."""
import json
import os
import runpy
import time
from pathlib import Path
import pymxs

rt = pymxs.runtime
ROOT = Path(__file__).resolve().parents[2]
BASE = Path('C:/Users/artsafro/.hermes/profiles/dt-experimenter-codex/cache/scratch/agr-exp-t_69ee7ca0')
OUT = BASE / 'agr-3dsmax-t_69ee7ca0'
session = os.environ['AGR_MAX_EXP_SESSION']
assert not len(rt.objects) and not str(rt.maxFileName)
rows = []
try:
    for rep in range(3):
        out = OUT / ('batched-' + session + '-r' + str(rep))
        assert not out.exists()
        config = BASE / ('batched-' + session + '-config' + str(rep) + '.json')
        with config.open('x') as f:
            json.dump({'fbx': str(BASE / 'bench-b01-box/etalon.fbx'), 'output_dir': str(out)}, f)
        rt.execute('maxOps.mxsCmdLineArgs[#config] = @"' + str(config) + '"')
        t = time.perf_counter()
        runpy.run_path(str(ROOT / 'tools/max_profile_roundtrip.py'))
        rows.append({'rep': rep, 'seconds': time.perf_counter()-t, 'output': str(out)})
        rt.delete(list(rt.objects))
        rt.resetMaxFile(rt.Name('noPrompt'))  # No user scene: all nodes/artifacts owned by this job.
finally:
    rt.delete(list(rt.objects))
with (OUT / ('batched-' + session + '-timing.json')).open('x') as f:
    json.dump(rows, f, indent=2)
print('AGR_BATCHED_EXISTING', json.dumps(rows), 'objects', len(rt.objects))
