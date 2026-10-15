"""Exercise the unchanged repository script with only its documented config supplied."""
import json
import runpy
import time
import traceback
from pathlib import Path
import pymxs

rt = pymxs.runtime
ROOT = Path(__file__).resolve().parents[2]
BASE = Path('C:/Users/artsafro/.hermes/profiles/dt-experimenter-codex/cache/scratch/agr-exp-t_69ee7ca0')
rows = []
assert not len(rt.objects) and not str(rt.maxFileName)
for rep in [next(i for i in range(100) if not (BASE / 'agr-3dsmax-t_69ee7ca0' / ('existing-r' + str(i))).exists())]:
    out = BASE / 'agr-3dsmax-t_69ee7ca0' / ('existing-r' + str(rep))
    config = BASE / ('existing-config-r' + str(rep) + '.json')
    config.write_text(json.dumps({'fbx': str(BASE / 'bench-b01-box/etalon.fbx'), 'output_dir': str(out)}))
    rt.execute('maxOps.mxsCmdLineArgs[#config] = @"' + str(config) + '"')
    t = time.perf_counter()
    try:
        runpy.run_path(str(ROOT / 'tools/max_profile_roundtrip.py'))
        rows.append({'rep': rep, 'seconds': time.perf_counter()-t, 'result': 'completed'})
    except Exception as exc:
        rows.append({'rep': rep, 'seconds': time.perf_counter()-t, 'error': str(exc)})
        traceback.print_exc()
        raise
    finally:
        rt.delete(list(rt.objects))
        # Existing script saves max-import.max; permit next initially-empty run.
        # Stop after one successful invocation: each repetition needs a fresh process.
    break
(BASE / 'agr-3dsmax-t_69ee7ca0/existing-results.json').write_text(json.dumps(rows, indent=2))
print('AGR_EXISTING', json.dumps(rows))
