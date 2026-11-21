"""new-case: fail-closed probes of the cold-run #3 job.yaml through the procedure walker (#1313).

Usage: uv run python jobs/KPP1/cold-run-1313/probe_walk.py <repo root> <new output dir>
Each variant must make the walker report errors or a non-pass gate; none may yield passed=true.
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def _hash_after(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    if match is None:
        raise SystemExit(f'probe setup: pattern not found: {pattern}')
    return match.group(1)


def main(root: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=False)
    base = (root / 'jobs/KPP1/cold-run-1313/job.yaml').read_text(encoding='utf-8')
    parts_sha = re.search(r'parts-v001.json\n      sha256: ([0-9a-f]{64})', base).group(1)
    dup = base.replace('- path: jobs/KPP1/object.json',
                       '- path: ./jobs/KPP1/object.json\n  sha256: '
                       + re.search(r'object.json\n  sha256: ([0-9a-f]{64})', base).group(1)
                       + '\n- path: jobs/KPP1/object.json', 1)
    variants = {
        'baseline': (base, None),
        'duplicate_input_alias': (dup, 'inputs'),
        'parts_pass_without_gate1': (base.replace('  parts:\n    status: review\n    waits: user',
                                                  '  parts:\n    status: pass', 1), 'parts'),
        'parts_hash_off_by_one': (base.replace(parts_sha, parts_sha[:-1] + ('0' if parts_sha[-1] != '0' else '1')), 'parts'),
        'waits_on_pass': (base.replace('  report:\n    status: review', '  report:\n    status: pass\n    waits: user', 1), 'report'),
        'empty_inputs': (base.split('inputs: &inputs\n', 1)[0] + 'inputs: &inputs []\nartifacts:'
                         + base.split('\nartifacts:', 1)[1], 'inputs'),
        'malformed_yaml': (base.replace('inputs: &inputs\n', 'inputs: &inputs []\n', 1), 'inputs'),
    }
    rows, ok = [], 0
    for name, (text, gate) in variants.items():
        job = out / f'{name}.yaml'
        job.write_bytes(text.encode('utf-8'))
        walk = out / f'{name}.walk.json'
        rc = subprocess.run([sys.executable, '-m', 'dt_ai.procedure', str(job), '--root', str(root),
                             '--output', str(walk)], cwd=root, capture_output=True, text=True).returncode
        rep = json.loads(walk.read_text(encoding='utf-8')) if walk.is_file() else {}
        gates = {g.get('id') or g.get('gate'): g.get('status') for g in rep.get('gates', [])}
        rejected = rc != 0 and not rep.get('passed') and (gate is None or gates.get(gate) != 'pass'
                                                         or bool(rep.get('errors')))
        if not rep and rc != 0:  # parse error: walker prints errors to stdout and writes no report
            rejected, changed = True, True
        else:
            changed = name == 'baseline' or rep.get('errors') or gates.get(gate) == 'fail'
        good = rejected and bool(changed)
        ok += good
        rows.append({'variant': name, 'exit': rc, 'passed': rep.get('passed'), 'errors': len(rep.get('errors') or []),
                     'gate': gate, 'gate_status': gates.get(gate), 'fail_closed': good})
    (out / 'probe.json').write_bytes((json.dumps(rows, indent=1) + '\n').encode('utf-8'))
    print(json.dumps(rows, indent=1))
    print(f'{ok}/{len(rows)} fail-closed')
    return 0 if ok == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1]).resolve(), Path(sys.argv[2])))
