"""new-case: accepted geometry CLI regressions; fixtures are synthetic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/state/accepted_set.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup_job(tmp_path):
    folder = tmp_path / 'jobs' / 'synthetic'
    folder.mkdir(parents=True)
    accepted = tmp_path / 'body_A_v004.blend'
    accepted.write_bytes(b'synthetic accepted body A v004')
    later = tmp_path / 'body_A_v008e.blend'
    later.write_bytes(b'synthetic unauthorized body A v008e')
    record = folder / 'accepted.json'
    record.write_text(json.dumps({'schema': 'accepted-set/1', 'job': 'synthetic',
        'accepted': [{'part': 'body_A', 'version': 'v004', 'path': str(accepted),
                      'sha256': digest(accepted)}]}), encoding='utf-8')
    return record, accepted, later


def cli(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), '--root', str(root),
                           '--job', 'synthetic', *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8')


def test_incident4_cli(tmp_path):
    _, accepted, later = setup_job(tmp_path)
    good = cli(tmp_path, '--part', 'body_A', '--inputs', accepted)
    assert good.returncode == 0, good.stdout + good.stderr
    assert json.loads(good.stdout)['inputs'][0]['status'] == 'accepted'
    bad = cli(tmp_path, '--part', 'body_A', '--inputs', later)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert 'sha256' in bad.stdout and 'body_A' in bad.stdout
