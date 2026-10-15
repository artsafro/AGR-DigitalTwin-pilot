"""Run sequential negative/control Max calls through the required lock wrapper."""
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'experiments/max-headless-agr-roundtrip'
WRAPPER = 'C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py'
rows = []
for name, file in [('existing-direct', ROOT / 'tools/max_profile_roundtrip.py'),
                   ('existing-configured', OUT / 'existing_job.py'),
                   ('intentional-failure', OUT / 'fail_job.py'),
                   ('missing-file', OUT / 'does-not-exist.py')]:
    t = time.perf_counter()
    r = subprocess.run(['python', WRAPPER, 'max', '--card', 't_69ee7ca0', '--file', str(file),
                        '--timeout', '180', '--out', str(OUT / (name + '-session.json')),
                        '--max-chars', '1000'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    row = {'operation': name, 'returncode': r.returncode, 'wall_seconds': time.perf_counter()-t}
    rows.append(row)
    (OUT / 'controls.json').write_text(json.dumps(rows, indent=2))
    print(json.dumps(row), r.stdout[-1600:], flush=True)
